"""
报告生成器 - 支持终端表格、Markdown、HTML 输出
HTML 报告支持:
  - 一级分类颜色区分
  - 区域分组展示（北美/欧洲/日韩/港澳台/东南亚/中东/南美/大洋洲/其他）
  - 时间列展示立法动态发布时间
  - Lilith Legal 品牌标识
"""

import base64
import os
import re
import html as html_mod
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# ── 模板目录 & 文件加载 ──────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _load_template_file(name: str) -> str:
    """从 templates/ 目录加载 CSS/JS 文件。"""
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")

from config import OUTPUT_DIR, REGION_DISPLAY_ORDER
from classifier import get_source_tier
from utils import (
    _REGION_GROUP_MAP, _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, normalize_status,
    _bigram_sim, _TIER_SORT,
)


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── 工具函数 ──────────────────────────────────────────────────────

def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


# 常见媒体机构后缀（Google News 有时把来源附在标题末尾）
_MEDIA_SUFFIXES = re.compile(
    r"\s*[-–|]\s*(?:GamesIndustry(?:\.biz)?|Eurogamer|Kotaku|IGN|Polygon"
    r"|PC Gamer|GamesBeat|VentureBeat|Reuters|BBC|The Guardian|Forbes"
    r"|TechCrunch|Bloomberg|Axios|Politico|The Verge|Ars Technica"
    r"|Game Developer|Develop(?:er)?|MCV|Pocketgamer(?:\.biz)?)\s*$",
    re.IGNORECASE,
)
# HTML 数字/命名实体（包括截断的实体如 Türk... → Türkiye）
_HTML_ENTITY = re.compile(r"&#?\w+;?")


def _clean_title(title: str) -> str:
    """
    清洗英文原标题：
    1. 解码 HTML 实体（&amp; → &, &#252; → ü 等）
    2. 去除媒体机构后缀（"FTC fines game - Reuters" → "FTC fines game"）
    3. 去除不完整的 HTML 实体残留（如截断的 Türk...）
    """
    t = html_mod.unescape(title or "")
    t = _MEDIA_SUFFIXES.sub("", t).strip()
    # 去除仍残留的不完整实体（如 &amp 没有分号）
    t = re.sub(r"&\w{2,8}$", "", t).strip()
    return t


def _get_display_title(item: dict) -> str:
    """标题显示原文（不使用中文翻译）"""
    return item.get("title", "")


def _get_summary_zh(item: dict) -> str:
    """摘要优先返回中文翻译，没有则返回原文"""
    return item.get("summary_zh") or item.get("summary", "")


# ─── 事件指纹（跨来源/跨区域快速候选匹配）─────────────────────────────

_FP_ENTITIES = re.compile(
    r"\b(google|alphabet|apple|microsoft|meta|facebook|amazon|epic|valve|steam"
    r"|sony|nintendo|bytedance|tencent|netflix|spotify"
    r"|ftc|doj|dma|cma|accc|pcc|ofcom|cnil|bfdi|agcm)\b",
    re.IGNORECASE,
)
_FP_TOPICS = [
    (re.compile(r"pay(?:ment|out)?|commission|fee\b|iap\b|抽成|分成", re.I), "payment"),
    (re.compile(r"privacy|data.?protect|gdpr|ccpa|隐私|数据保护", re.I), "privacy"),
    (re.compile(r"\bminor|child(?:ren)?|coppa|未成年|儿童", re.I), "minor"),
    (re.compile(r"antitrust|anti.?trust|monopol|反垄断|垄断", re.I), "antitrust"),
    (re.compile(r"loot.?box|gacha|probabil|抽卡|开箱|概率", re.I), "gacha"),
    (re.compile(r"\bbattery\b|电池", re.I), "battery"),
    (re.compile(r"fine|penalt|enforce|sanction|罚款|处罚|执法", re.I), "enforcement"),
    (re.compile(r"distribut|sideload|分发|侧载", re.I), "distribution"),
    (re.compile(r"adverti[sz]|广告", re.I), "ads"),
    (re.compile(r"age.?verif|rating|分级|年龄验证", re.I), "rating"),
    (re.compile(r"refund|退款", re.I), "refund"),
]


def _calculate_event_fingerprint(item: dict) -> frozenset:
    """
    计算事件指纹：{R:区域, E:实体, T:议题}
    用于在 LLM 语义检查前识别"候选合并池"。
    两条新闻共享同一实体 + 同一议题，视为同一事件候选对。
    """
    text = " ".join(filter(None, [
        item.get("title", ""),
        item.get("title_zh", ""),
        item.get("summary_zh", ""),
    ]))
    parts: set = set()
    group = _get_region_group(item.get("region", "其他"))
    if group != "其他":
        parts.add(f"R:{group}")
    for m in _FP_ENTITIES.findall(text):
        parts.add(f"E:{m.lower()}")
    for pattern, topic in _FP_TOPICS:
        if pattern.search(text):
            parts.add(f"T:{topic}")
    return frozenset(parts)


def _fp_same_event(fp_a: frozenset, fp_b: frozenset) -> bool:
    """指纹重叠：共享至少 1 个实体 AND 至少 1 个议题 → 视为同一事件候选。"""
    shared = fp_a & fp_b
    return (
        any(t.startswith("E:") for t in shared)
        and any(t.startswith("T:") for t in shared)
    )


# ─── 基于标题文本的分组推断（修复 region='其他' 条目）────────────────────

_TEXT_GROUP_PATTERNS = [
    # 顺序很重要：先匹配更具体的地区
    ("欧洲",   r'(?i)\b(uk\b|britain|british|ofcom|ico\b|england|scotland|wales'
               r'|germany|german|deutschland|bfdi'
               r'|france|french|cnil'
               r'|netherlands|dutch|kansspel'
               r'|belgi(?:um|an|sch)?'
               r'|austria[n]?|österreich'
               r'|italy|italian|agcm'
               r'|spain|spanish|aepd'
               r'|poland|polish'
               r'|sweden|swedish'
               r'|norway|norwegian'
               r'|russia[n]?|ukraine|ukrainian|belarus|belarusian'
               r'|eu\b|european union|european commission|european parliament'
               r'|gdpr\b|dsa\b|dma\b|ai act|asa\b)\b'
               r'|英国|德国|法国|荷兰|比利时|奥地利|意大利|西班牙|波兰|瑞典|挪威|欧盟|欧洲'
               r'|俄罗斯|乌克兰|白俄罗斯'),
    # 港澳台：香港/澳门/台湾（须在日韩之前）
    ("港澳台", r'(?i)\b(hong kong|hongkong|hksar\b|hk\b|pcpd\b|hkcma\b|hkma\b|sfc\b'
               r'|macau|macao|dicj\b|taiwan[ese]?)\b'
               r'|香港|澳门|台湾|港澳'),
    ("北美",   r'(?i)\b(usa\b|united states|america[n]?|ftc\b|federal trade commission'
               r'|fcc\b|federal communications commission'
               r'|doj\b|department of justice|cisa\b|sec\b'
               r'|congress\b|senate\b|house of representatives|white house'
               r'|california|new york|virginia|texas|florida|illinois|georgia'
               r'|connecticut|nevada|pennsylvania|colorado|washington\b|oregon'
               r'|massachusetts|new jersey|ohio|michigan|north carolina|utah|delaware'
               r'|attorney general|state ag\b'
               r'|canada|canadian|pipeda\b|cppa\b|opc\b'
               r'|mexico|mexican'
               r'|ccpa\b|cpra\b|coppa\b|kids act|kosa\b|shield act)\b'
               r'|美国|加拿大|纽约|加利福尼亚|德克萨斯|墨西哥|联邦贸易委员会|美国国会|白宫'),
    # 东南亚：十一国（与 utils.py _REGION_GROUP_MAP 定义一致）
    ("东南亚", r'(?i)\b(vietnam[ese]?|việt|indonesi[a]?[n]?|kominfo\b|igac\b'
               r'|thailand|thai\b|pdpa\b'
               r'|philippine[s]?|malaysia[n]?|mcmc\b'
               r'|singapore|imda\b|brunei|myanmar|cambodia|laos|timor)\b'
               r'|越南|印度尼西亚|印尼|泰国|菲律宾|马来西亚|新加坡|缅甸|柬埔寨|文莱'),
    ("日韩",   r'(?i)\b(japan[ese]?|korea[n]?|south korea|grac\b|kca\b|cero\b'
               r'|nintendo\b)\b'
               r'|韓[国國]?|日本|韩国|ゲーム|게임|확률형'),
    # 中东
    ("中东",   r'(?i)\b(saudi|uae\b|united arab emirates|turkey|turkish|türkiye'
               r'|iran[ian]?|iraq[i]?|kuwait[i]?|bahrain[i]?|qatar[i]?'
               r'|oman[i]?|yem[ae]n[i]?|jordan[ian]?|lebanon|lebanese'
               r'|israel[i]?|palestin[ian]?|syria[n]?)\b'
               r'|沙特|阿联酋|土耳其|伊朗|伊拉克|科威特|巴林|卡塔尔|阿曼|也门'
               r'|约旦|黎巴嫩|以色列|巴勒斯坦|叙利亚'),
    # 南美
    ("南美",   r'(?i)\b(brazil[ian]?|lgpd\b|argentina[n]?|chile[an]?|colombia[n]?'
               r'|venezuela[n]?|peru[vian]?|ecuador[ian]?|bolivia[n]?'
               r'|paraguay[an]?|uruguay[an]?|guyana|suriname)\b'
               r'|巴西|阿根廷|智利|哥伦比亚|委内瑞拉|秘鲁|厄瓜多尔|玻利维亚'
               r'|巴拉圭|乌拉圭|圭亚那|苏里南'),
    # 大洋洲
    ("大洋洲", r'(?i)\b(australia[n]?|new zealand|esafety\b|accc\b|oaic\b'
               r'|papua|fiji[an]?|samoa[n]?|tonga[n]?|vanuatu)\b'
               r'|澳大利亚|新西兰|巴布亚|斐济|萨摩亚|汤加'),
    # 其他：非洲 / 中亚 / 南亚
    ("其他",   r'(?i)\b(nigeria[n]?|south africa|kenya[n]?|ethiopia[n]?'
               r'|india[n]?|dpdpa\b|meity\b|pakistan[i]?|bangladesh[i]?)\b'
               r'|尼日利亚|南非|肯尼亚|埃塞俄比亚|印度|巴基斯坦|孟加拉'),
]


def _infer_group_from_text(title: str, title_zh: str) -> str:
    """
    从标题文本（英文原文 + 中文译文）推断显示分组。
    用于修复 region='其他' 或 '全球' 的条目，使其出现在正确的地区组。
    """
    text = f"{title} {title_zh}"
    for group, pattern in _TEXT_GROUP_PATTERNS:
        if re.search(pattern, text):
            return group
    return "其他"


def _resolve_group(item: dict) -> str:
    """解析条目的最终显示分组（含文本推断兜底）"""
    group = _get_region_group(item.get("region", "其他"))
    if group == "其他":
        group = _infer_group_from_text(
            item.get("title", ""),
            item.get("title_zh", ""),
        )
    return group


# ─── 报告渲染前去重 ───────────────────────────────────────────────────

def _dedup_for_display(items: List[dict]) -> List[dict]:
    """
    报告渲染前内容去重（三阶段）：
    1. URL 精确去重：同一 source_url → 保留优先级最高的条目
    2. Bigram 相似度 > 0.45 → 确定为同一事件，合并
    3. Bigram 相似度 0.25-0.45 → 送 LLM 批量验证，准确判断是否同一事件
    优先级：impact_score > source_tier（官方>法律>行业>媒体）> 发布日期
    """
    import time as _time
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    TIER_PRIORITY = _TIER_SORT

    def _priority(item: dict) -> tuple:
        impact = float(item.get("impact_score", 1.0))
        tier   = TIER_PRIORITY.get(get_source_tier(item.get("source_name", "")), 1)
        date   = item.get("date", "")
        return (impact, tier, date)

    # 按优先级降序排序 → 先处理高质量条目
    sorted_idx = sorted(range(len(items)), key=lambda i: _priority(items[i]), reverse=True)

    kept_idx: list   = []   # 已保留条目的原始索引
    extra_items: dict = {}  # kept_idx → 被合并的重复条目列表（用于 LLM 深度摘要融合）
    borderline: list  = []  # [(kidx, idx)] 需 LLM 验证的模糊重复对

    # 预计算事件指纹（用于跨区域/跨来源候选匹配）
    fps: dict = {i: _calculate_event_fingerprint(items[i]) for i in range(len(items))}

    for idx in sorted_idx:
        item    = items[idx]
        group   = _resolve_group(item)
        t_item  = (item.get("title_zh") or item.get("title") or "")
        url_item = (item.get("source_url") or "").strip()
        is_dup  = False

        for kidx in kept_idx:
            kitem = items[kidx]
            same_group = (_resolve_group(kitem) == group)

            # ① URL 精确去重（全局，不限区域）
            url_kept = (kitem.get("source_url") or "").strip()
            if url_item and url_kept and url_item == url_kept:
                extra_items.setdefault(kidx, []).append(dict(items[idx]))
                is_dup = True
                break

            if not same_group:
                # 跨区域：只在指纹重叠时才进一步比较，避免误合并
                if not _fp_same_event(fps[idx], fps[kidx]):
                    continue
                t_kept = (kitem.get("title_zh") or kitem.get("title") or "")
                sim = _bigram_sim(t_item, t_kept)
                tier_kept = TIER_PRIORITY.get(get_source_tier(kitem.get("source_name", "")), 1)
                tier_curr = TIER_PRIORITY.get(get_source_tier(item.get("source_name", "")), 1)
                # ② 权威源覆盖：任一方为 official（tier=4）时，bigram > 0.20 即合并
                if max(tier_kept, tier_curr) >= 4 and sim > 0.20:
                    extra_items.setdefault(kidx, []).append(dict(items[idx]))
                    is_dup = True
                    _logger.info(f"[dedup fp] 权威源覆盖跨区域重复: {item.get('title_zh','')[:40]}")
                    break
                # ③ 普通跨区域：指纹预筛后，bigram > 0.40 合并
                if sim > 0.40:
                    extra_items.setdefault(kidx, []).append(dict(items[idx]))
                    is_dup = True
                    _logger.info(f"[dedup fp] 跨区域去重合并: {item.get('title_zh','')[:40]}")
                    break
                continue  # 指纹匹配但 bigram 不足，不合并

            # ④ 同区域 Bigram 相似度（原有逻辑）
            t_kept = (kitem.get("title_zh") or kitem.get("title") or "")
            sim = _bigram_sim(t_item, t_kept)
            if sim > 0.45:          # 确定重复
                extra_items.setdefault(kidx, []).append(dict(items[idx]))
                is_dup = True
                break
            if sim > 0.35:          # 模糊，记录待 LLM 验证
                borderline.append((kidx, idx))

        if not is_dup:
            kept_idx.append(idx)

    # ③ LLM 批量验证模糊重复对
    if borderline:
        try:
            from translator import verify_duplicate_pairs
            kept_set_now = set(kept_idx)
            pairs_to_verify = []
            valid_bl = []
            for kidx, idx in borderline:
                # 两者都仍在保留集中才验证
                if kidx in kept_set_now and idx in kept_set_now:
                    t_kept = (items[kidx].get("title_zh") or items[kidx].get("title") or "")
                    t_item = (items[idx].get("title_zh")  or items[idx].get("title")  or "")
                    pairs_to_verify.append((t_kept, t_item))
                    valid_bl.append((kidx, idx))
            if pairs_to_verify:
                _time.sleep(4)
                llm_results = verify_duplicate_pairs(pairs_to_verify)
                for (kidx, idx), is_same in zip(valid_bl, llm_results):
                    if is_same and idx in kept_idx:
                        kept_idx.remove(idx)
                        extra_items.setdefault(kidx, []).append(dict(items[idx]))
                        _logger.info(f"[dedup LLM] 合并重复: {items[idx].get('title_zh','')[:40]}")
        except Exception as e:
            _logger.warning(f"[dedup LLM] 批量验证失败，跳过: {e}")

    kept_set = set(kept_idx)
    result   = []
    for idx, item in enumerate(items):
        if idx not in kept_set:
            continue
        if idx in extra_items:
            item = dict(item)   # 浅拷贝，避免污染原始数据
            dups = extra_items[idx]
            try:
                from translator import merge_duplicate_summaries
                merged = merge_duplicate_summaries(item, dups)
                if merged:
                    item["summary_zh"] = merged
            except Exception as _me:
                _logger.warning(f"[dedup merge] LLM 融合失败，保留主摘要: {_me}")
        result.append(item)

    return result


# ─── Lilith Legal Logo 嵌入 ─────────────────────────────────────────

_ASSETS_DIR = Path(__file__).parent / "assets"
_LOGO_PATH = next(
    (_ASSETS_DIR / f for f in ("lilith-logo.jpg", "lilith-logo.png") if (_ASSETS_DIR / f).exists()),
    _ASSETS_DIR / "lilith-logo.jpg",
)


def _get_logo_html() -> str:
    """返回 base64 内联 logo img 标签；文件不存在时返回空字符串"""
    if _LOGO_PATH.exists():
        with open(_LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        suffix = _LOGO_PATH.suffix.lower().lstrip(".")
        mime = "image/png" if suffix == "png" else f"image/{suffix}"
        return f'<img src="data:{mime};base64,{b64}" alt="Lilith Games" class="header-logo">'
    return ""


# ─── 分类颜色配置（舒适色系） ──────────────────────────────────────────

CATEGORY_STYLE = {
    "数据隐私":       {"row": "#F0F4FF", "bg": "#DBEAFE", "text": "#1E40AF", "border": "#93C5FD"},
    "玩法合规":       {"row": "#F5F0FF", "bg": "#EDE9FE", "text": "#5B21B6", "border": "#C4B5FD"},
    "未成年人保护":    {"row": "#F0FDF4", "bg": "#D1FAE5", "text": "#065F46", "border": "#6EE7B7"},
    "广告营销合规":    {"row": "#FFFBF0", "bg": "#FEF3C7", "text": "#92400E", "border": "#FCD34D"},
    "消费者保护":      {"row": "#F0FDFA", "bg": "#CCFBF1", "text": "#134E4A", "border": "#5EEAD4"},
    "经营合规":       {"row": "#FFF7ED", "bg": "#FFEDD5", "text": "#9A3412", "border": "#FCA369"},
    "平台政策":       {"row": "#FFF1F2", "bg": "#FFE4E6", "text": "#9F1239", "border": "#FDA4AF"},
    "内容监管":       {"row": "#F8FAFC", "bg": "#E2E8F0", "text": "#334155", "border": "#94A3B8"},
    "市场准入":       {"row": "#FFF7ED", "bg": "#FFEDD5", "text": "#9A3412", "border": "#FCA369"},
    "PC & 跨平台合规": {"row": "#F0F7FF", "bg": "#BAE6FD", "text": "#0C4A6E", "border": "#38BDF8"},
}
DEFAULT_STYLE = {"row": "#FAFAFA", "bg": "#F1F5F9", "text": "#334155", "border": "#CBD5E1"}

STATUS_CSS = {
    "已生效":      "background:#DCFCE7;color:#166534;",
    "即将生效":     "background:#FEF9C3;color:#713F12;",
    "草案/征求意见": "background:#DBEAFE;color:#1E40AF;",
    "立法进行中":   "background:#E0E7FF;color:#3730A3;",
    "已提案":      "background:#E2E8F0;color:#334155;",
    "修订变更":     "background:#7C3AED;color:#FFFFFF;",
    "已废止":      "background:#F1F5F9;color:#475569;",
    "执法动态":    "background:#FEE2E2;color:#991B1B;",
    "立法动态":    "background:#D97706;color:#FFFFFF;",
}

IMPACT_CONFIG = {
    # 10-point float scale: high ≥9.0, medium ≥7.0, low <7.0
    "high":   {"dots": "●●●", "label": "高优先",  "color": "#DC2626", "title": "高优先 ≥9.0：已生效/官方执法/核心市场"},
    "medium": {"dots": "●●○", "label": "中优先",  "color": "#D97706", "title": "中优先 ≥7.0：草案/立法中/执法动态"},
    "low":    {"dots": "●○○", "label": "低优先",  "color": "#16A34A", "title": "低优先 <7.0：立法动态/背景信息"},
}


def _impact_tier(score) -> str:
    """将 1.0–10.0 分值映射到 high/medium/low 三档。"""
    s = float(score) if score is not None else 1.0
    if s >= 9.0:
        return "high"
    if s >= 7.0:
        return "medium"
    return "low"

TIER_CONFIG = {
    "official": {"label": "官方",  "bg": "#EFF6FF", "text": "#1D4ED8", "border": "#BFDBFE"},
    "legal":    {"label": "法律",  "bg": "#F0FDF4", "text": "#166534", "border": "#BBF7D0"},
    "industry": {"label": "行业",  "bg": "#FFF7ED", "text": "#9A3412", "border": "#FED7AA"},
    "news":     {"label": "媒体",  "bg": "#F8FAFC", "text": "#475569", "border": "#E2E8F0"},
}


# ─── 终端彩色表格输出 ──────────────────────────────────────────────────

class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


TERMINAL_STATUS_COLORS = {
    "已生效": C.GREEN,
    "即将生效": C.YELLOW,
    "草案/征求意见": C.CYAN,
    "立法进行中": C.BLUE,
    "已提案": C.BLUE,
    "修订变更": C.YELLOW,
    "已废止": C.DIM,
    "执法动态": C.RED,
    "立法动态": C.DIM,
}


def print_table(items: List[dict], max_summary_len: int = 50):
    if not items:
        print(f"\n{C.YELLOW}暂无监控数据{C.RESET}\n")
        return

    print()
    print(f"{C.BOLD}{'='*140}{C.RESET}")
    print(f"{C.BOLD}  全球游戏行业立法动态监控报告  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}{C.RESET}")
    print(f"{C.BOLD}{'='*140}{C.RESET}")
    print()

    header = (
        f"{'区域':<8} | "
        f"{'类别':<12} | "
        f"{'标题(原文)':<50} | "
        f"{'发布时间':<12} | "
        f"{'状态':<12} | "
        f"摘要与合规提示"
    )
    print(f"{C.BOLD}{header}{C.RESET}")
    print(f"{'-'*140}")

    for item in items:
        status = item.get("status", "立法动态")
        color = TERMINAL_STATUS_COLORS.get(status, C.RESET)
        title = _get_display_title(item)
        summary_zh = _get_summary_zh(item)

        row = (
            f"{_truncate(item.get('region', ''), 8):<8} | "
            f"{_truncate(item.get('category_l1', ''), 12):<12} | "
            f"{_truncate(title, 50):<50} | "
            f"{item.get('date', ''):<12} | "
            f"{color}{_truncate(status, 12):<12}{C.RESET} | "
            f"{_truncate(summary_zh, max_summary_len)}"
        )
        print(row)

    print(f"{'-'*140}")
    print(f"{C.DIM}共 {len(items)} 条记录{C.RESET}\n")


# ─── Markdown 报告 ────────────────────────────────────────────────────

def generate_markdown(items: List[dict], title: str = "全球游戏行业立法动态监控报告") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# {title}",
        "",
        f"> 生成时间: {now}  ",
        f"> 监控条目: {len(items)} 条",
        "",
        "---",
        "",
    ]

    if not items:
        lines.append("*暂无监控数据*")
        return "\n".join(lines)

    by_region = {}
    for item in items:
        region = item.get("region", "其他")
        by_region.setdefault(region, []).append(item)

    for region in REGION_DISPLAY_ORDER:
        region_items = by_region.pop(region, [])
        if not region_items:
            continue
        _append_region_md(lines, region, region_items)

    for region, region_items in by_region.items():
        if region_items:
            _append_region_md(lines, region, region_items)

    return "\n".join(lines)


def _append_region_md(lines: list, region: str, region_items: list):
    lines.append(f"## {region} ({len(region_items)} 条)")
    lines.append("")
    lines.append("| 类别 | 标题(原文) | 发布时间 | 状态 | 摘要与合规提示 |")
    lines.append("|------|------------|----------|------|------------|")

    for item in sorted(region_items, key=lambda x: x.get("date", ""), reverse=True):
        title_orig = (item.get("title", "") or "").replace("|", "\\|")
        summary_zh = _get_summary_zh(item).replace("|", "\\|")
        url = item.get("source_url", "")

        if url:
            title_cell = f"[{_truncate(title_orig, 50)}]({url})"
        else:
            title_cell = _truncate(title_orig, 50)

        lines.append(
            f"| {item.get('category_l1', '')} "
            f"| {title_cell} "
            f"| {item.get('date', '')} "
            f"| **{item.get('status', '')}** "
            f"| {_truncate(summary_zh, 80)} |"
        )

    lines.append("")


def save_markdown(items: List[dict], filename: Optional[str] = None) -> str:
    ensure_output_dir()
    if not filename:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    content = generate_markdown(items)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# ─── HTML 报告 ─────────────────────────────────────────────────────────

def _build_legend_html() -> str:
    """构建分类颜色图例"""
    items_html = ""
    for cat, style in CATEGORY_STYLE.items():
        if cat == "市场准入":
            continue
        items_html += (
            f'<span class="legend-item" style="background:{style["bg"]};'
            f'color:{style["text"]};border:1px solid {style["border"]};'
            f'padding:3px 8px;border-radius:12px;font-size:11px;font-weight:500;">'
            f'{cat}</span>'
        )
    return f'<div class="legend">{items_html}</div>'


# ─── New-style report helpers (mobile + PC card designs) ─────────────────────

_ACCENT_BY_CAT = {
    "数据隐私":        "blue",
    "玩法合规":        "purple",
    "未成年人保护":     "green",
    "广告营销合规":     "orange",
    "消费者保护":       "teal",
    "经营合规":        "orange",
    "平台政策":        "red",
    "内容监管":        "magenta",
    "市场准入":        "orange",
    "PC & 跨平台合规":  "blue",
}

_ACCENT_HEX = {
    "red":     "#E8443A",
    "green":   "#27AE60",
    "purple":  "#8B5CF6",
    "magenta": "#DB2777",
    "teal":    "#0D9488",
    "blue":    "#2563EB",
    "orange":  "#D97706",
}


def _get_accent(item: dict) -> str:
    s = float(item.get("impact_score", 1.0))
    if s >= 9.0:
        return "red"
    if s >= 7.0:
        return "orange"
    return _ACCENT_BY_CAT.get(item.get("category_l1", ""), "blue")


def _week_cn(period_label: str) -> str:
    try:
        from math import ceil
        y, w = period_label.split("-W")
        d = datetime.strptime(f"{y}-W{int(w):02d}-1", "%G-W%V-%u")
        return f"{y} 年 {d.month} 月第 {ceil(d.day / 7)} 周"
    except Exception:
        return period_label


def _date_range_str(items: list, period_label: str = "") -> str:
    # 当 period_label 是 ISO 周格式（如 "2026-W11"）时，直接计算该周的周一至周日
    if "-W" in period_label:
        try:
            y, w = period_label.split("-W")
            monday = datetime.strptime(f"{y}-W{int(w):02d}-1", "%G-W%V-%u")
            sunday = monday + timedelta(days=6)
            return f"{monday.strftime('%Y-%m-%d')} ~ {sunday.strftime('%Y-%m-%d')}"
        except Exception:
            pass
    dates = sorted({i.get("date", "") for i in items if i.get("date")})
    return f"{dates[0]} ~ {dates[-1]}" if dates else ""


def _dots_html(group_items: list) -> str:
    seen: set = set()
    out = []
    for item in group_items:
        a = _get_accent(item)
        if a not in seen:
            seen.add(a)
            out.append(f'<div class="dot" style="background:{_ACCENT_HEX[a]};"></div>')
    return "".join(out)


def _risk_pills_html(items: list) -> str:
    high = [i for i in items if float(i.get("impact_score", 1.0)) >= 9.0]
    med  = [i for i in items if 7.0 <= float(i.get("impact_score", 1.0)) < 9.0]
    pills = []
    for item in high[:3]:
        t = ((item.get("title_zh") or "").strip() or _truncate(_get_summary_zh(item), 12))[:14]
        pills.append(f'<span class="risk-pill high">高优 · {html_mod.escape(t)}</span>')
    for item in med[:2]:
        t = ((item.get("title_zh") or "").strip() or _truncate(_get_summary_zh(item), 12))[:14]
        pills.append(f'<span class="risk-pill medium">中优 · {html_mod.escape(t)}</span>')
    return "".join(pills)


_BP_STATUS_DOT: dict = {
    "👤 待研判":       "#6366F1",
    "🏃 处理/跟进中":  "#F59E0B",
    "✅ 已合规/归档":  "#22C55E",
}


def _render_bp_breakdown_html(action_items: list) -> str:
    """将 action_items 按 assignee 分组，渲染为逐 BP 任务清单 HTML。"""
    from collections import defaultdict
    bp_groups: dict = defaultdict(list)
    for item in action_items:
        bp = (item.get("assignee") or "").strip() or "未分配"
        bp_groups[bp].append(item)
    if not bp_groups:
        return ""
    rows = []
    for bp, items in bp_groups.items():
        bp_esc   = html_mod.escape(bp)
        avatar   = html_mod.escape(bp[0]) if bp else "?"
        count    = len(items)
        items_html = ""
        for item in items:
            title  = html_mod.escape(((item.get("title_zh") or item.get("title") or "").strip())[:45])
            region = html_mod.escape((item.get("region") or "").strip())
            status = (item.get("bitable_status") or "").strip()
            dot_c  = _BP_STATUS_DOT.get(status, "#94A3B8")
            meta   = f'<span class="bp-item-meta">{region}</span>' if region else ""
            items_html += (
                f'<div class="bp-item">'
                f'<span class="bp-dot" style="background:{dot_c}"></span>'
                f'<span class="bp-item-text">{title}</span>'
                f'{meta}'
                f'</div>'
            )
        rows.append(
            f'<div class="bp-row">'
            f'<div class="bp-header-row">'
            f'<span class="bp-avatar">{avatar}</span>'
            f'<span class="bp-name">{bp_esc}</span>'
            f'<span class="bp-tally">{count} 项</span>'
            f'</div>'
            f'<div class="bp-items">{items_html}</div>'
            f'</div>'
        )
    return f'<div class="bp-breakdown">{"".join(rows)}</div>'


def _sort_group(group_items: list) -> list:
    return sorted(
        group_items,
        key=lambda x: (
            _TIER_SORT.get(get_source_tier(x.get("source_name", "")), 1),
            float(x.get("impact_score", 1.0)),
            x.get("date", ""),
        ),
        reverse=True,
    )


# ── 工作流状态三分区逻辑 ──────────────────────────────────────────────
# 用关键词子串匹配，兼容带/不带 emoji、不同斜杠字符等 Bitable 存储差异

def _split_three_ways(items: List[dict]) -> tuple:
    """
    按 bitable_status 将条目分为三类：
    - archived : 已合规/归档（上周已完成任务）
    - news     : 行业动态（全球合规动态汇总，仅供阅读）
    - active   : 处理中/跟进中（本周跟进任务）
    「待研判」等未明确归类的状态不纳入周报。
    """
    archived: List[dict] = []
    news:     List[dict] = []
    active:   List[dict] = []
    skipped:  List[dict] = []
    status_values: set = set()
    for item in items:
        ws = item.get("bitable_status", "")
        status_values.add(ws)
        if "归档" in ws:
            archived.append(item)
        elif "行业动态" in ws:
            news.append(item)
        elif "处理" in ws or "跟进" in ws:
            active.append(item)
        else:
            skipped.append(item)
    print(f"📊 三分区结果：归档 {len(archived)} / 动态 {len(news)} / 跟进 {len(active)} / 未纳入 {len(skipped)}")
    print(f"   所有 bitable_status 值: {status_values}")
    return archived, news, active


def _prepare_report_data(items: List[dict]) -> tuple:
    """
    Dedup → filter → split into three zones → exec summary → group by region.
    Returns (archived, news, active, exec_summary,
             archived_grouped, news_grouped, active_grouped).
    """
    items = _dedup_for_display(items)
    items = [i for i in items if float(i.get("impact_score", 1.0)) > 0]

    archived, news, active = _split_three_ways(items)

    # 综述以 active + archived 为主（有跟进价值的内容），为空则退化到全量
    exec_summary = ""
    summary_src  = (active + archived) if (active or archived) else items
    try:
        from translator import generate_executive_summary
        exec_summary = generate_executive_summary(summary_src)
    except Exception:
        pass

    archived_grouped: dict = defaultdict(list)
    for item in archived:
        archived_grouped[_resolve_group(item)].append(item)

    news_grouped: dict = defaultdict(list)
    for item in news:
        news_grouped[_resolve_group(item)].append(item)

    active_grouped: dict = defaultdict(list)
    for item in active:
        active_grouped[_resolve_group(item)].append(item)

    return archived, news, active, exec_summary, archived_grouped, news_grouped, active_grouped


# ── CSS / JS constants (plain strings, no f-string brace escaping needed) ─────

_FONT_FACE = _load_template_file("_font_face.css")

_MOBILE_CSS = _load_template_file("_mobile.css")

_MOBILE_JS = _load_template_file("_mobile.js")

_PC_CSS = _load_template_file("_pc.css")

_REPORT_JS = _load_template_file("_report.js")

_ICON_DOC = '<svg class="icon-doc" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
_ICON_DL   = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'


def _render_region_sections_mobile(grouped: dict, zone_type: str) -> str:
    """渲染一个区块内按地区分组的卡片列表（供 mobile 三分区复用）。
    zone_type: "archived" | "news" | "active"
    """
    sections_html = ""
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue
        cats      = list(dict.fromkeys(i.get("category_l1", "") for i in group_items if i.get("category_l1")))
        cats_html = "".join(f'<span class="cat-tag">{html_mod.escape(c)}</span>' for c in cats[:5])
        dots      = _dots_html(group_items)
        group_esc = html_mod.escape(group)

        items_html = ""
        for item in _sort_group(group_items):
            accent  = _get_accent(item)
            cat     = html_mod.escape(item.get("category_l1", ""))
            status  = html_mod.escape(normalize_status(item.get("status", "")))
            date_s  = html_mod.escape(item.get("date", ""))
            raw_zh  = (item.get("title_zh") or "").strip()
            raw_sum = _get_summary_zh(item)
            zh      = html_mod.escape(raw_zh if raw_zh else _truncate(raw_sum, 80))
            orig    = html_mod.escape(_clean_title(item.get("title", "")))
            summ    = html_mod.escape(_truncate(raw_sum, 200))
            url     = html_mod.escape(item.get("source_url", ""))
            cat_status = f"{cat}{' · ' + status if status else ''}"
            title_tag  = (f'<a href="{url}" target="_blank" rel="noopener">{zh}</a>' if url else zh)

            extra_html = ""
            if zone_type == "archived":
                # 归档区：跟进 BP + 核心结论 + 专项合规文档按钮 + 跳转到 Bitable 卡片按钮
                assignee    = html_mod.escape((item.get("assignee") or "").strip())
                conclusion  = html_mod.escape((item.get("legal_conclusion") or "").strip())
                doc_url     = html_mod.escape((item.get("doc_url") or "").strip())
                doc_text    = html_mod.escape((item.get("doc_text") or "专项合规文档").strip())
                bitable_url = html_mod.escape((item.get("bitable_url") or "").strip())
                if assignee:
                    extra_html += (
                        f'<div class="log-bp-row">'
                        f'<span class="log-bp-label">跟进</span>'
                        f'<span class="log-bp-value">{assignee}</span>'
                        f'</div>'
                    )
                if conclusion:
                    extra_html += f'<div class="log-conclusion">{conclusion}</div>'
                buttons = ""
                if doc_url:
                    buttons += (
                        f'<a class="log-btn log-btn-doc" href="{doc_url}" '
                        f'target="_blank" rel="noopener">📄 {doc_text}</a>'
                    )
                if bitable_url:
                    buttons += (
                        f'<a class="log-btn log-btn-bitable" href="{bitable_url}" '
                        f'target="_blank" rel="noopener">↗ 查看卡片</a>'
                    )
                if buttons:
                    extra_html += f'<div class="log-btn-row">{buttons}</div>'
            elif zone_type == "active":
                # 跟进任务区：只展示跟进 BP
                assignee = html_mod.escape((item.get("assignee") or "").strip())
                if assignee:
                    extra_html += (
                        f'<div class="log-bp-row">'
                        f'<span class="log-bp-label">跟进</span>'
                        f'<span class="log-bp-value">{assignee}</span>'
                        f'</div>'
                    )
            # news 区：不展示额外信息

            items_html += (
                f'<article class="log-item" data-accent="{accent}">'
                f'<div class="log-inner">'
                f'<div class="log-tags"><span class="log-category">{cat_status}</span>'
                f'<span class="log-date">{date_s}</span></div>'
                f'<div class="log-title">{title_tag}</div>'
                f'<span class="log-title-orig">{orig}</span>'
                f'<div class="log-summary">{summ}</div>'
                f'{extra_html}'
                f'</div></article>\n'
            )

        sections_html += (
            f'<div class="section-group" data-region="{group_esc}">'
            f'<div class="section-header">'
            f'<span class="section-title">{group_esc}</span>'
            f'<span class="section-count">{len(group_items)} 条</span>'
            f'<div class="section-dots">{dots}</div>'
            f'</div>'
            f'<div class="section-cats">{cats_html}</div>'
            f'<div class="log-list">{items_html}</div>'
            f'</div>\n'
        )
    return sections_html


def _render_mobile_html(archived: List[dict], news: List[dict], active: List[dict],
                        exec_summary: str,
                        archived_grouped: dict, news_grouped: dict, active_grouped: dict,
                        period_label: str = "") -> str:
    logo_html  = _get_logo_html()
    week_label = _week_cn(period_label) if "-W" in period_label else period_label
    all_items  = archived + news + active
    date_range = _date_range_str(all_items, period_label)
    total      = len(all_items)
    n_archived = len(archived)
    n_news     = len(news)
    n_active   = len(active)
    n_regions  = len({
        g for g in _GROUP_ORDER
        if archived_grouped.get(g) or news_grouped.get(g) or active_grouped.get(g)
    })
    period_esc = html_mod.escape(period_label)
    week_esc   = html_mod.escape(week_label)
    range_esc  = html_mod.escape(date_range)

    exec_html = ""

    # 过滤按钮（只显示有数据的地区）
    present_regions = [
        g for g in _GROUP_ORDER
        if archived_grouped.get(g) or news_grouped.get(g) or active_grouped.get(g)
    ]
    filter_btns = ''.join(
        f'<button class="filter-btn" data-filter="{html_mod.escape(g)}" '
        f'onclick="filterRegion(\'{html_mod.escape(g)}\', this)">{html_mod.escape(g)}</button>'
        for g in present_regions
    )

    # ── 区块一：上周已完成任务 ──
    if archived:
        archived_sections = _render_region_sections_mobile(archived_grouped, zone_type="archived")
        archived_zone = (
            f'<div class="zone-divider zone-divider-action">'
            f'<div class="zone-inner">'
            f'<div class="zone-icon">🎉</div>'
            f'<div class="zone-info">'
            f'<div class="zone-title-action">上周已完成任务</div>'
            f'</div>'
            f'<div class="zone-count-action">{n_archived} 条</div>'
            f'</div></div>\n'
            f'{archived_sections}'
        )
    else:
        archived_zone = ""

    # ── 区块二：上周全球合规动态汇总 ──
    if news:
        news_sections = _render_region_sections_mobile(news_grouped, zone_type="news")
        news_zone = (
            f'<div class="zone-divider zone-divider-news">'
            f'<div class="zone-inner">'
            f'<div class="zone-icon">🌏</div>'
            f'<div class="zone-info">'
            f'<div class="zone-title-news">上周全球合规动态汇总</div>'
            f'</div>'
            f'<div class="zone-count-news">{n_news} 条</div>'
            f'</div></div>\n'
            f'{news_sections}'
        )
    else:
        news_zone = ""

    # ── 区块三：本周跟进任务 ──
    if active:
        active_sections = _render_region_sections_mobile(active_grouped, zone_type="active")
        active_zone = (
            f'<div class="zone-divider zone-divider-action">'
            f'<div class="zone-inner">'
            f'<div class="zone-icon">🎯</div>'
            f'<div class="zone-info">'
            f'<div class="zone-title-action">本周跟进任务</div>'
            f'</div>'
            f'<div class="zone-count-action">{n_active} 条</div>'
            f'</div></div>\n'
            f'{active_sections}'
        )
    else:
        active_zone = ""

    return (
        f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        f'<meta charset="UTF-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">\n'
        f'<meta http-equiv="Pragma" content="no-cache">\n'
        f'<meta http-equiv="Expires" content="0">\n'
        f'<title>Lilith Legal 全球合规动态周报</title>\n'
        f'<style>{_MOBILE_CSS}</style>\n</head>\n<body>\n'
        f'<div class="app-view">\n'
        f'<header class="global-header">{logo_html}'
        f'<div class="header-version">{range_esc}</div></header>\n'
        f'<main class="main-content">\n'
        f'<div class="page-title-block">'
        f'<div class="page-week">{week_esc}</div>'
        f'<div class="page-subtitle">全球游戏合规动态周报</div>'
        f'<div class="stat-chips">'
        f'<span class="stat-chip">{total} 条动态</span>'
        f'<span class="stat-chip">{n_regions} 大区域</span>'
        f'</div></div>\n'
        f'{exec_html}'
        f'<div class="filter-bar" id="filterBar">'
        f'<button class="filter-btn active" data-filter="all" onclick="filterRegion(\'all\', this)">全部</button>'
        f'{filter_btns}'
        f'</div>\n'
        f'{archived_zone}'
        f'{news_zone}'
        f'{active_zone}'
        f'<div class="page-footer"><div class="page-footer-text">{period_esc} · LILITH LEGAL</div></div>\n'
        f'</main></div>\n'
        f'<script>{_MOBILE_JS}</script>\n'
        f'</body>\n</html>'
    )


def _render_region_sections_pc(grouped: dict, is_action: bool) -> str:
    """渲染一个区块内按地区分组的卡片网格（供 PC action / news 两区块复用）。"""
    sections_html = ""
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue
        cats      = list(dict.fromkeys(i.get("category_l1", "") for i in group_items if i.get("category_l1")))
        cats_str  = " · ".join(cats[:4]) + f" · {len(group_items)} 条"
        dots      = "".join(
            f'<div class="dot" style="background:{_ACCENT_HEX[a]};"></div>'
            for a in list(dict.fromkeys(_get_accent(i) for i in group_items))[:5]
        )
        group_esc    = html_mod.escape(group)
        sorted_items = _sort_group(group_items)
        n = len(sorted_items)

        cards_html = ""
        for idx, item in enumerate(sorted_items):
            accent   = _get_accent(item)
            hex_col  = _ACCENT_HEX[accent]
            cat      = html_mod.escape(item.get("category_l1", ""))
            status   = html_mod.escape(normalize_status(item.get("status", "")))
            date_s   = html_mod.escape(item.get("date", ""))
            raw_zh   = (item.get("title_zh") or "").strip()
            raw_sum  = _get_summary_zh(item)
            zh       = html_mod.escape(raw_zh if raw_zh else _truncate(raw_sum, 80))
            orig     = html_mod.escape(_clean_title(item.get("title", "")))
            summ     = html_mod.escape(_truncate(raw_sum, 200))
            url      = html_mod.escape(item.get("source_url", ""))
            span_cls = " span-2" if (n % 2 == 1 and idx == n - 1) else ""
            meta_parts = [p for p in [cat, status, date_s] if p]
            meta = " · ".join(meta_parts)
            title_tag = (f'<a href="{url}" target="_blank" rel="noopener">{zh}</a>' if url else zh)

            # 跟进 BP 和法务结论（仅 action 区块）
            extra_html = ""
            if is_action:
                assignee   = html_mod.escape((item.get("assignee") or "").strip())
                conclusion = html_mod.escape((item.get("legal_conclusion") or "").strip())
                if assignee:
                    extra_html += (
                        f'<div class="card-bp-row">'
                        f'<span class="card-bp-label">跟进</span>'
                        f'<span class="card-bp-value">{assignee}</span>'
                        f'</div>'
                    )
                if conclusion:
                    extra_html += f'<div class="card-conclusion">{conclusion}</div>'

            cards_html += (
                f'<div class="card{span_cls}" data-accent="{accent}">'
                f'<div class="card-indicator"><div class="accent-bar" style="background:{hex_col}"></div></div>'
                f'<div class="card-body">'
                f'<div class="card-title">{title_tag}</div>'
                f'<div class="card-orig">{orig}</div>'
                f'<div class="card-meta">{meta}</div>'
                f'{extra_html}'
                f'<div class="card-note">{_ICON_DOC}<p>{summ}</p></div>'
                f'</div></div>\n'
            )

        sections_html += (
            f'<div class="section" data-region="{group_esc}">'
            f'<div class="section-header">'
            f'<span class="section-title">{group_esc}</span>'
            f'<div class="dot-cluster">{dots}</div>'
            f'</div>'
            f'<div class="section-meta">{html_mod.escape(cats_str)}</div>'
            f'<div class="card-grid">{cards_html}</div>'
            f'</div>\n'
        )
    return sections_html


def _render_pc_html(archived: List[dict], news: List[dict], active: List[dict],
                    exec_summary: str,
                    archived_grouped: dict, news_grouped: dict, active_grouped: dict,
                    period_label: str = "") -> str:
    # PC 端复用 mobile 渲染，仅注入更宽的容器尺寸
    mobile_html = _render_mobile_html(
        archived, news, active, exec_summary,
        archived_grouped, news_grouped, active_grouped, period_label
    )
    pc_override = (
        "<style>"
        "@media(min-width:600px){.app-view{max-width:860px;}}"
        "@media(min-width:1000px){.app-view{max-width:1080px;}}"
        "@media(min-width:1400px){.app-view{max-width:1280px;}}"
        "</style>"
    )
    return mobile_html.replace("</head>", f"{pc_override}\n</head>", 1)


def generate_html(items: List[dict], title: str = "全球游戏行业立法动态监控报告",
                  period_label: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_html = _get_logo_html()

    # ── 报告级去重（跨来源同事件合并）────────────────────────────
    items = _dedup_for_display(items)

    # ── 过滤噪音条目（impact_score == 0 表示硬件/Google-Apple非核心等无关内容）──
    items = [i for i in items if float(i.get("impact_score", 1.0)) > 0]

    # ── LLM 月报综述（在去重后、分组前生成）─────────────────────
    exec_summary = ""
    try:
        from translator import generate_executive_summary
        exec_summary = generate_executive_summary(items)
    except Exception as _e:
        pass  # 综述失败不影响主报告渲染

    # ── 按区域分组（含文本推断兜底）──────────────────────────────
    grouped: dict = defaultdict(list)
    for item in items:
        group = _resolve_group(item)
        grouped[group].append(item)

    # ── 生成表格行（含分组 header）────────────────────────────────
    rows_html = ""
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue
        emoji = _GROUP_EMOJI.get(group, "🌐")
        # 分组 header 行
        rows_html += (
            f'\n        <tr class="group-row" data-group="{html_mod.escape(group)}">'
            f'<td colspan="6" class="group-header">'
            f'{emoji} {html_mod.escape(group)}'
            f'<span class="group-count">{len(group_items)} 条</span>'
            f'</td></tr>'
        )
        # 条目行（按来源权威性排序：source_tier（官方>法律>行业>媒体）> impact_score > 日期）
        for item in sorted(
            group_items,
            key=lambda x: (
                _TIER_SORT.get(get_source_tier(x.get("source_name", "")), 1),
                float(x.get("impact_score", 1.0)),
                x.get("date", ""),
            ),
            reverse=True,
        ):
            cat = item.get("category_l1", "")
            style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
            status = normalize_status(item.get("status", ""))
            status_css = STATUS_CSS.get(status, "background:#F1F5F9;color:#475569;")
            impact = float(item.get("impact_score", 1.0))

            source_raw = item.get("source_name", "")
            tier = get_source_tier(source_raw)
            tier_cfg = TIER_CONFIG.get(tier, TIER_CONFIG["news"])

            title_orig = html_mod.escape(_clean_title(item.get("title", "")))
            summary_zh_raw = _get_summary_zh(item)
            summary_zh_full = html_mod.escape(summary_zh_raw)
            summary_zh = html_mod.escape(_truncate(summary_zh_raw, 200))
            url = item.get("source_url", "")
            item_date = item.get("date", "")
            region = html_mod.escape(item.get("region", ""))
            source_name = html_mod.escape(source_raw)

            # 中文主标题：优先 title_zh，回退到 summary_zh 前 80 字
            title_zh_raw = (item.get("title_zh") or "").strip()
            zh_headline = html_mod.escape(
                title_zh_raw if title_zh_raw else _truncate(summary_zh_raw, 80)
            )

            # 英文原标题作为次要链接
            if url:
                orig_link = (f'<a href="{html_mod.escape(url)}" target="_blank" '
                             f'rel="noopener" title="{summary_zh_full}">{title_orig}</a>')
            else:
                orig_link = f'<span title="{summary_zh_full}">{title_orig}</span>'

            cat_badge = (
                f'<span class="cat-badge" style="background:{style["bg"]};'
                f'color:{style["text"]};border:1px solid {style["border"]};">'
                f'{html_mod.escape(cat)}</span>'
            )
            status_badge = (
                f'<span class="status-badge" style="{status_css}">'
                f'{html_mod.escape(status)}</span>'
            )
            tier_badge = (
                f'<span class="tier-badge" style="background:{tier_cfg["bg"]};'
                f'color:{tier_cfg["text"]};border:1px solid {tier_cfg["border"]};">'
                f'{tier_cfg["label"]}</span>'
            )

            # Impact-based row highlight: red ≥9.0, orange ≥7.0
            if impact >= 9.0:
                row_bg = "background:#FFF5F5;"
            elif impact >= 7.0:
                row_bg = "background:#FFFBF0;"
            else:
                row_bg = ""

            rows_html += (
                f'\n        <tr data-date="{html_mod.escape(item_date)}" '
                f'data-cat="{html_mod.escape(cat)}" data-region="{region}" '
                f'data-group="{html_mod.escape(group)}" '
                f'data-impact="{impact}" '
                f'style="{row_bg}border-left:3px solid {style["border"]};">'
                f'<td class="td-region">{region}</td>'
                f'<td class="td-cat">{cat_badge}</td>'
                f'<td class="td-title">'
                f'<span class="td-title-zh">{zh_headline}</span>'
                f'<span class="td-title-orig">{orig_link}</span>'
                f'{"<br><span class=td-source>" + tier_badge + " " + source_name + "</span>" if source_name else ""}'
                f'</td>'
                f'<td class="td-date">{html_mod.escape(item_date)}</td>'
                f'<td class="td-status">{status_badge}</td>'
                f'<td class="td-summary">{summary_zh}</td>'
                f'</tr>'
            )

    # 综述 HTML 块提前计算（避免 f-string 内含反斜杠，Python <3.12 不支持）
    if exec_summary:
        exec_summary_html = (
            '<div class="exec-summary-card">'
            '<div class="exec-summary-label">📋 上周动态总结</div>'
            f'<div class="exec-summary-text">{html_mod.escape(exec_summary)}</div>'
            '</div>'
        )
    else:
        exec_summary_html = ""

    legend_html = _build_legend_html()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>{html_mod.escape(title)}</title>
<style>
/* ── 基础 Reset ── */
* {{ margin:0; padding:0; box-sizing:border-box; }}

/* ── 全局：Instagram 风清爽配色 ── */
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Noto Sans SC", "PingFang SC", "Helvetica Neue", sans-serif;
    background: #F5F5F7;
    color: #1D1D1F;
    padding: 28px 24px;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}}
.container {{ max-width: 1700px; margin: 0 auto; }}

/* ── 头部（白底，logo 原色显示） ── */
.header {{
    background: #FFFFFF;
    border-radius: 16px;
    padding: 18px 24px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    box-shadow: 0 1px 0 #E8E8ED, 0 2px 8px rgba(0,0,0,0.04);
}}
.header-left h1 {{
    font-size: 19px;
    font-weight: 700;
    color: #1D1D1F;
    letter-spacing: -0.2px;
}}
.header-left .meta {{
    font-size: 12px;
    color: #86868B;
    margin-top: 3px;
    letter-spacing: 0.1px;
}}
.header-brand {{
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}}
.header-logo {{
    height: 34px;
    width: auto;
    object-fit: contain;
}}
.brand-name {{
    font-size: 12px;
    font-weight: 700;
    color: #86868B;
    letter-spacing: 2px;
    text-transform: uppercase;
    border-left: 1px solid #E8E8ED;
    padding-left: 12px;
    white-space: nowrap;
}}

/* ── 卡片通用 ── */
.card {{
    background: #FFFFFF;
    border-radius: 12px;
    box-shadow: 0 1px 0 #E8E8ED, 0 2px 6px rgba(0,0,0,0.03);
    margin-bottom: 12px;
}}

/* ── 分类颜色图例 ── */
.legend {{
    padding: 12px 18px;
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    align-items: center;
}}
.legend::before {{
    content: "分类";
    font-size: 11px;
    color: #86868B;
    font-weight: 600;
    white-space: nowrap;
    margin-right: 4px;
}}
.legend-item {{
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}}

/* ── 筛选栏 ── */
.toolbar {{
    padding: 12px 18px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    align-items: center;
}}
.toolbar label {{
    font-size: 11px;
    color: #86868B;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
.toolbar select, .toolbar input {{
    padding: 6px 10px;
    border: 1px solid #E8E8ED;
    border-radius: 8px;
    font-size: 12px;
    color: #1D1D1F;
    background: #F5F5F7;
    outline: none;
    transition: border-color 0.15s, background 0.15s;
}}
.toolbar select:focus, .toolbar input:focus {{
    border-color: #6E6EF7;
    background: #FFFFFF;
    box-shadow: 0 0 0 3px rgba(110,110,247,0.08);
}}
.toolbar input {{ width: 210px; }}
.result-count {{ margin-left: auto; font-size: 11px; color: #86868B; }}

/* ── 表格 ── */
.table-wrap {{
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 0 #E8E8ED, 0 2px 6px rgba(0,0,0,0.03);
}}
table {{ width: 100%; border-collapse: collapse; background: white; }}
thead tr {{ background: #F5F5F7; border-bottom: 1px solid #E8E8ED; }}
th {{
    padding: 10px 12px;
    text-align: left;
    font-size: 10.5px;
    font-weight: 700;
    color: #86868B;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
}}
th:hover {{ color: #1D1D1F; }}
th .sort-icon {{ opacity: 0.35; margin-left: 3px; font-size: 9px; }}
th.sorted .sort-icon {{ opacity: 0.9; color: #6E6EF7; }}

/* ── 分组 header 行（柔和紫蓝） ── */
.group-row td.group-header {{
    background: #F0F0FF;
    color: #3D3D9E;
    font-size: 11.5px;
    font-weight: 700;
    padding: 8px 14px;
    letter-spacing: 0.4px;
    border-left: 3px solid #6E6EF7;
}}
.group-count {{
    display: inline-block;
    background: rgba(110,110,247,0.12);
    color: #5757D9;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 10px;
    margin-left: 8px;
    vertical-align: middle;
}}

/* ── 数据行 ── */
tbody tr:not(.group-row) {{
    border-bottom: 1px solid #F5F5F7;
    transition: background 0.12s;
}}
tbody tr:not(.group-row):hover {{ background: #FAFAFF; }}
td {{ padding: 9px 12px; font-size: 12px; vertical-align: top; }}

.td-region {{
    white-space: nowrap;
    font-weight: 600;
    color: #6E6EF7;
    font-size: 11px;
    width: 5%;
}}
.td-cat {{ white-space: nowrap; width: 8%; }}
.td-title {{ width: 16%; min-width: 160px; max-width: 280px; line-height: 1.55; }}
.td-title-zh {{
    display: block;
    font-weight: 600;
    color: #1D1D1F;
    font-size: 12.5px;
    line-height: 1.6;
    margin-bottom: 4px;
}}
.td-title-orig {{
    display: block;
    font-size: 10.5px;
    color: #AEAEB2;
    margin-top: 1px;
}}
.td-title-orig a {{ color: #AEAEB2; text-decoration: none; }}
.td-title-orig a:hover {{ text-decoration: underline; color: #636366; }}
.td-source {{
    font-size: 10px;
    color: #AEAEB2;
    margin-top: 3px;
    display: block;
}}
.td-date {{
    white-space: nowrap;
    font-size: 11.5px;
    color: #636366;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
    width: 6%;
}}
.td-status {{ white-space: nowrap; width: 7%; }}
.td-summary {{ width: 65%; min-width: 320px; color: #636366; line-height: 1.65; font-size: 11.5px; word-break: break-word; overflow-wrap: break-word; }}

/* ── 标签 badges ── */
.cat-badge {{
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
}}
.status-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
}}
.tier-badge {{
    display: inline-block;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    white-space: nowrap;
    vertical-align: middle;
}}

/* ── 无数据提示 ── */
.no-data {{
    text-align: center;
    padding: 56px;
    color: #AEAEB2;
    font-size: 13px;
    display: none;
}}

/* ── 月报综述卡片 ── */
.exec-summary-card {{
    background: linear-gradient(135deg, #F0F4FF 0%, #E8F0FE 100%);
    border: 1px solid #C7D7FD;
    border-left: 4px solid #6366F1;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 4px rgba(99,102,241,0.08);
}}
.exec-summary-label {{
    font-size: 11px;
    font-weight: 700;
    color: #6366F1;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 8px;
}}
.exec-summary-text {{
    font-size: 13px;
    line-height: 1.75;
    color: #1D1D1F;
    white-space: pre-wrap;
    word-break: break-word;
}}

/* ── 页脚 ── */
.footer {{
    margin-top: 24px;
    text-align: center;
    font-size: 11px;
    color: #AEAEB2;
    padding-bottom: 8px;
    letter-spacing: 0.3px;
}}

/* ── 响应式 ── */
@media (max-width: 900px) {{
    .td-summary {{ display: none; }}
}}
</style>
</head>
<body>
<div class="container">

  <!-- 头部 -->
  <div class="header">
    <div class="header-left">
      <h1>{html_mod.escape(title)}</h1>
      <div class="meta">生成时间：{now}&nbsp;&nbsp;·&nbsp;&nbsp;共 {len(items)} 条动态</div>
    </div>
    <div class="header-brand">
      {logo_html}
      <span class="brand-name">Lilith Legal</span>
    </div>
  </div>

  <!-- 月报综述 -->
  {exec_summary_html}

  <!-- 筛选栏 -->
  <div class="card">
  <div class="toolbar">
    <label>地区</label>
    <select id="fGroup" onchange="applyFilters()">
      <option value="">全部地区</option>
    </select>
    <label>分类</label>
    <select id="fCat" onchange="applyFilters()">
      <option value="">全部</option>
    </select>
    <label>状态</label>
    <select id="fStatus" onchange="applyFilters()">
      <option value="">全部</option>
    </select>
    <input type="search" id="fKeyword" placeholder="🔍 关键词搜索..." oninput="applyFilters()">
    <span class="result-count" id="resultCount"></span>
  </div>
  </div>

  <!-- 表格 -->
  <div class="table-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">区域 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(1)">类别 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(2)">标题 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(3)">发布时间 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(4)">标签 <span class="sort-icon">⇅</span></th>
          <th>摘要与合规提示</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>
    <div class="no-data" id="noData">暂无匹配数据</div>
  </div>

  <!-- 页脚 -->
  <div class="footer">Lilith Legal &nbsp;·&nbsp; 全球游戏合规监控 &nbsp;·&nbsp; 仅供内部参考</div>

</div>
<script>
{_REPORT_JS}
</script>
</body>
</html>"""


def save_html(items: List[dict], period_label: str = "") -> tuple:
    """Generate mobile + PC HTML reports. Returns (mobile_path, pc_path)."""
    ensure_output_dir()

    # Process data once (dedup, filter, split, exec summary, grouping)
    archived, news, active, exec_summary, archived_grouped, news_grouped, active_grouped = (
        _prepare_report_data(items)
    )

    mobile_html = _render_mobile_html(
        archived, news, active, exec_summary,
        archived_grouped, news_grouped, active_grouped, period_label
    )
    pc_html = _render_pc_html(
        archived, news, active, exec_summary,
        archived_grouped, news_grouped, active_grouped, period_label
    )

    mobile_path = os.path.join(OUTPUT_DIR, "latest-mobile.html")
    pc_path     = os.path.join(OUTPUT_DIR, "latest-pc.html")

    with open(mobile_path, "w", encoding="utf-8") as f:
        f.write(mobile_html)
    with open(pc_path, "w", encoding="utf-8") as f:
        f.write(pc_html)

    # Keep latest.html as mobile for backward compatibility with generate_pdf.py
    latest_path = os.path.join(OUTPUT_DIR, "latest.html")
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(mobile_html)

    return mobile_path, pc_path
