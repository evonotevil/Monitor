"""
翻译/摘要模块

优先路径：Groq API（OpenAI 兼容格式，免费）
  - 标题格式：[地区/国家] 核心事件，专有名词保留英文（Valve/Loot Box/FTC 等）
  - 摘要格式：监管对象 + 具体限制 + 违规后果，30-50 字，内容须与标题显著不同

回退路径：Google Translate（LLM_API_KEY 未配置时）
"""

import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── 内部大模型客户端（OpenAI 兼容） ──────────────────────────────────

_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
_LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
_LLM_MODEL    = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # 可通过环境变量覆盖

try:
    from openai import OpenAI as _OpenAI
    _AI_CLIENT = _OpenAI(api_key=_LLM_API_KEY, base_url=_LLM_BASE_URL, timeout=25.0, max_retries=0) if _LLM_API_KEY else None
    _HAS_AI = bool(_LLM_API_KEY)
    if not _HAS_AI:
        logger.info("LLM_API_KEY 未设置，将使用 Google Translate 回退")
except ImportError:
    _AI_CLIENT = None
    _HAS_AI = False
    logger.warning("openai 未安装，将使用 Google Translate。运行: pip install openai")

# ── Google Translate 回退 ─────────────────────────────────────────────

try:
    from deep_translator import GoogleTranslator
    _HAS_TRANSLATOR = True
except ImportError:
    _HAS_TRANSLATOR = False
    logger.warning("deep-translator 未安装。运行: pip install deep-translator")

_cache: dict = {}

# ── 专有名词纠错表 ────────────────────────────────────────────────────
# 修正 AI 生成中常见的音译/意译错误，将其替换回受保护的英文原文

_TERM_CORRECTIONS: dict[str, str] = {
    # Valve
    "瓦尔维尔": "Valve", "瓦尔弗": "Valve", "瓦尔夫": "Valve", "维尔福": "Valve",
    # Steam
    "史蒂姆": "Steam", "史提姆": "Steam",
    # Epic Games
    "艾匹克游戏": "Epic Games", "艾匹克": "Epic Games",
    # Loot Box（最常见的错误意译）
    "战利品箱": "Loot Box", "战利品盒": "Loot Box", "战利品包": "Loot Box",
    "掉落箱":   "Loot Box", "收藏箱":   "Loot Box",
    # Gacha
    "加查": "Gacha", "扭蛋机制": "Gacha 机制",
    # Deepfake
    "深度伪造": "Deepfake",
    # Discord
    "迪斯科": "Discord",
    # Twitch
    "推趣": "Twitch",
    # Roblox（注意：罗布乐思是官方中文名，此处保留英文）
    "罗布乐思": "Roblox",
}


def _apply_term_corrections(text: str) -> str:
    """将 AI 常见音译/意译错误替换回受保护的英文原文。"""
    for wrong, right in _TERM_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return text


def _bigram_similarity(a: str, b: str) -> float:
    """
    计算两段中文文本的 Jaccard bigram 相似度（交集/并集，0~1）。
    用于检测 summary_zh 是否在复读 title_zh。

    用 Jaccard 而非 recall 的原因：
      - recall（交集/title_bigrams）会把"标题关键词全部出现在更长摘要中"误判为高相似
      - Jaccard（交集/并集）越长的摘要分母越大，好摘要（有增量信息）得分低，
        坏摘要（只是换个说法）得分高，符合直觉
    阈值建议：> 0.55 触发重新生成
    """
    if not a or not b or len(a) < 2 or len(b) < 2:
        return 0.0
    bigrams_a = {a[i:i + 2] for i in range(len(a) - 1)}
    bigrams_b = {b[i:i + 2] for i in range(len(b) - 1)}
    union = bigrams_a | bigrams_b
    if not union:
        return 0.0
    return len(bigrams_a & bigrams_b) / len(union)


# ── AI Prompt ─────────────────────────────────────────────────────────

_AI_SYSTEM = """你是全球游戏行业合规法规分析师，负责将英文法规新闻转化为规范中文标题和摘要，供中资手游出海合规团队阅读。

【专有名词保护清单】——以下术语禁止音译或意译，必须保留英文原文：
公司/平台：Valve、Steam、Epic Games、Apple、Google、Microsoft、Xbox、PlayStation、Roblox、Nintendo、TikTok、Meta、Reddit、Discord、Twitch、Unity、Ubisoft、Riot Games
监管机构：FTC、ASA、ICO、CNIL、KCA、GRAC、ESRB、PEGI、Ofcom
法规/机制：GDPR、COPPA、CCPA、DSA、DMA、PDPA、LGPD、Loot Box、Gacha、NFT、DLC
技术术语：Deepfake、App Store、Google Play（AI 可译为"人工智能"）

【标题规则】
- 格式固定：[地区/国家] 核心事件简述
- 正确示例：[美国] 纽约州起诉 Valve，称 Loot Box 机制涉嫌非法赌博
- 正确示例：[欧盟] DSA 新规强制游戏平台披露算法推荐逻辑
- 专有名词保留英文（见清单），其余文字必须为中文
- 严格 35 字以内（含方括号）
- 禁止出现媒体机构名称（如 GamesIndustry、Reuters、BBC 等后缀）
- 禁止以【xxx】【专栏】【分析】等媒体栏目标记开头，一律去除后重新提炼事件核心
- 禁止疑问句或问题形式标题（"如何…？""…是否…？"），一律改为陈述句

【摘要规则】
- 内容必须与标题有显著差异，严禁直接复制或改写标题句子
- 严格控制在 30-50 字之间
- 必须严格遵循公式：[背景/起因] + [核心监管动作] + [具体后果（金额/期限/要求）]
- 聚焦对中资手游出海合规的实际影响，落到具体义务或数字
- 正确示例："纽约总检察长以非法赌博为由起诉 Valve，要求停售旗下三款游戏的 Loot Box 并退还玩家损失，违者面临民事罚款及禁止令。"
- 错误示例（禁止）："纽约起诉 Valve，其 Loot Box 机制违法。"（信息量不足，仅复述标题）

【无正文时的处理】
- 若原始内容仅有标题或摘要极短，必须基于专业背景知识合理扩充摘要
- 重点推断：该规定针对哪类游戏行为、企业须履行什么义务、不合规的法律代价
- 严禁输出"暂无详细信息"或简单复述标题的无效内容

【输出格式】
仅输出合法 JSON，不含任何其他文字、注释或代码块标记：
{"title_zh": "...", "summary_zh": "..."}"""


# ── 文章正文抓取（最优先给 AI 提供上下文）────────────────────────────

def _fetch_article_body(url: str) -> str:
    """尝试获取文章正文前 500 字；超时或失败时静默返回空字符串。"""
    if not url or not url.startswith("http"):
        return ""
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html",
        }
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if not resp.ok:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # 移除噪音标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        # 优先提取语义化正文区域
        for selector in ("article", "main", "[class*='article-body']",
                         "[class*='post-content']", "[class*='entry-content']"):
            el = soup.select_one(selector)
            if el:
                text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                if len(text) > 80:
                    return text[:500]
        # 兜底：body 全文
        body = soup.find("body")
        if body:
            return re.sub(r"\s+", " ", body.get_text(" ", strip=True))[:500]
    except Exception:
        pass
    return ""


# ── Claude AI 处理 ────────────────────────────────────────────────────

def _ai_process(title: str, summary: str, body_snippet: str = "") -> Optional[dict]:
    """
    调用 Claude AI 重塑标题、生成深度摘要。
    返回 {"title_zh": ..., "summary_zh": ...} 或 None（调用失败时）。
    """
    if not _HAS_AI or not _AI_CLIENT:
        return None

    body_part = (
        f"\n文章正文片段（前500字）：{body_snippet}"
        if body_snippet and len(body_snippet) > 50
        else ""
    )
    # 内容不足时明确提示 AI 须扩充而非复述
    has_enough_context = (summary and len(summary) > 40) or (body_snippet and len(body_snippet) > 50)
    lean_warning = (
        "\n⚠️ 原始内容极少，请依据专业背景知识扩充摘要，禁止简单复述标题。"
        if not has_enough_context else ""
    )
    user_msg = (
        f"英文标题：{title}\n"
        f"原始摘要：{summary or '（无）'}"
        f"{body_part}"
        f"{lean_warning}"
    )

    try:
        resp = _AI_CLIENT.chat.completions.create(
            model=_LLM_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content.strip()
        logger.info(f"[AI raw] {text[:200]}")   # 打印返回内容，方便排查

        # 兼容多种输出格式，含截断修复
        # 1. 先尝试剥离 markdown 代码块
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = code_block.group(1) if code_block else None
        # 2. 完整 {...}
        if not json_str:
            plain = re.search(r"\{.*\}", text, re.DOTALL)
            json_str = plain.group() if plain else None
        # 3. 截断修复：找到以 { 开头但没有结尾 } 的片段，补上
        if not json_str:
            partial = re.search(r"\{.*", text, re.DOTALL)
            if partial:
                json_str = partial.group().rstrip() + "}"

        if json_str:
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = {}
            title_zh   = (data.get("title_zh")  or "").strip()
            summary_zh = (data.get("summary_zh") or "").strip()
            # 4. JSON 解析失败兜底：直接用正则从原文提取字段值
            if not title_zh or not summary_zh:
                tm = re.search(r'"title_zh"\s*:\s*"([^"]{2,})"', text)
                sm = re.search(r'"summary_zh"\s*:\s*"([^"]{2,})"', text)
                if tm:
                    title_zh = tm.group(1).strip()
                if sm:
                    summary_zh = sm.group(1).strip()
            if title_zh and summary_zh:
                # ── 步骤 5：JSON 残留字符清理 ─────────────────────────
                # 部分模型（如 Qwen）偶尔将 JSON 结构字符混入字段值
                title_zh   = re.sub(r'[\}\{"\s,]+$', '', title_zh).strip()
                summary_zh = re.sub(r'[\}\{"\s,]+$', '', summary_zh).strip()

                # ── 步骤 6：[地区] 前缀兜底修复 ──────────────────────
                # 若标题未以 [xxx] 开头，从原始英文标题或 item region 推断并补充
                if not re.match(r'^\[.+?\]', title_zh):
                    # 尝试从英文标题里找地区关键词（优先顺序：美国/英国/EU等）
                    _region_hints = [
                        ("美国",  r'\b(US|USA|United States|America[n]?|FTC|Congress|Senate|White House)\b'),
                        ("英国",  r'\b(UK|United Kingdom|Britain|British|ASA|Ofcom|ICO)\b'),
                        ("欧盟",  r'\b(EU|European Union|Europe[an]?|GDPR|DSA|DMA|CNIL)\b'),
                        ("韩国",  r'\b(Korea[n]?|South Korea|GRAC|KCA)\b'),
                        ("日本",  r'\b(Japan[ese]?)\b'),
                        ("澳大利亚", r'\b(Austral[ia]+[n]?|eSafety)\b'),
                        ("加拿大", r'\b(Canada[ian]?)\b'),
                        ("越南",  r'\b(Vietnam[ese]?)\b'),
                        ("印度",  r'\b(India[n]?)\b'),
                        ("中国",  r'\b(China|Chinese)\b'),
                        ("全球",  r'\b(global[ly]?|worldwide|international)\b'),
                    ]
                    inferred = None
                    for region_cn, pattern in _region_hints:
                        if re.search(pattern, title, re.IGNORECASE):
                            inferred = region_cn
                            break
                    if inferred:
                        title_zh = f"[{inferred}] {title_zh}"
                        logger.info(f"[AI] 补充 [地区] 前缀: [{inferred}] → {title_zh[:40]}")

                # ── 步骤 7：专有名词纠错 ──────────────────────────────
                title_zh   = _apply_term_corrections(title_zh)
                summary_zh = _apply_term_corrections(summary_zh)

                # ── 步骤 8：相似度检测，>55% 则要求重新生成摘要 ─────
                sim = _bigram_similarity(title_zh, summary_zh)
                if sim > 0.55:
                    logger.warning(
                        f"[AI] 摘要与标题 bigram 相似度 {sim:.0%}，触发重新生成"
                    )
                    time.sleep(4)
                    dedup_msg = (
                        f"{user_msg}\n\n"
                        f"上一次生成的摘要【{summary_zh}】与标题【{title_zh}】"
                        f"高度重复（相似度 {sim:.0%}），不符合要求。\n"
                        f"请严格按照公式重写摘要：[背景/起因] + [核心监管动作] + [具体后果（金额/期限/要求）]。"
                        f"摘要必须包含标题中没有的具体信息，30-50 字。"
                    )
                    try:
                        resp3 = _AI_CLIENT.chat.completions.create(
                            model=_LLM_MODEL,
                            max_tokens=300,
                            messages=[
                                {"role": "system", "content": _AI_SYSTEM},
                                {"role": "user",   "content": dedup_msg},
                            ],
                        )
                        t3 = resp3.choices[0].message.content.strip()
                        logger.info(f"[AI dedup retry] {t3[:200]}")
                        tm3 = re.search(r'"title_zh"\s*:\s*"([^"]{2,})"', t3)
                        sm3 = re.search(r'"summary_zh"\s*:\s*"([^"]{2,})"', t3)
                        if sm3:
                            summary_zh = _apply_term_corrections(sm3.group(1).strip())
                        if tm3:
                            title_zh = _apply_term_corrections(tm3.group(1).strip())
                    except Exception as e3:
                        logger.warning(f"[AI] 相似度重试失败: {e3}")

                return {"title_zh": title_zh, "summary_zh": summary_zh}
            logger.warning(f"[AI] JSON 字段为空: {json_str[:100]}")
        else:
            logger.warning(f"[AI] 返回内容中未找到 JSON: {text[:200]}")

    except Exception as e:
        err_msg = str(e)
        # 速率限制：提取建议等待时间，休眠后重试一次
        retry_m = re.search(r'try again in (\d+\.?\d*)s', err_msg, re.IGNORECASE)
        if retry_m:
            wait_sec = min(float(retry_m.group(1)) + 1.5, 35.0)
            logger.warning(f"[AI] 速率限制，等待 {wait_sec:.1f}s 后重试")
            time.sleep(wait_sec)
            try:
                resp2 = _AI_CLIENT.chat.completions.create(
                    model=_LLM_MODEL,
                    max_tokens=300,
                    messages=[
                        {"role": "system", "content": _AI_SYSTEM},
                        {"role": "user",   "content": user_msg},
                    ],
                )
                text2 = resp2.choices[0].message.content.strip()
                logger.info(f"[AI raw retry] {text2[:200]}")
                tm = re.search(r'"title_zh"\s*:\s*"([^"]{2,})"', text2)
                sm = re.search(r'"summary_zh"\s*:\s*"([^"]{2,})"', text2)
                if tm and sm:
                    return {"title_zh": tm.group(1).strip(), "summary_zh": sm.group(1).strip()}
            except Exception as e2:
                logger.warning(f"[AI] 重试失败: {type(e2).__name__}: {e2}")
        else:
            logger.warning(f"[AI] 调用异常: {type(e).__name__}: {e}")
    return None


# ── Google Translate 工具函数（回退路径）─────────────────────────────

def _is_mostly_chinese(text: str) -> bool:
    if not text:
        return False
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_count > len(text) * 0.3


def translate_to_zh(text: str, source_lang: str = "auto") -> str:
    """将文本翻译为中文，失败时返回原文"""
    if not text or not text.strip():
        return text
    if not _HAS_TRANSLATOR:
        return text
    if _is_mostly_chinese(text):
        return text
    cache_key = text[:200]
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        result = GoogleTranslator(source=source_lang, target="zh-CN").translate(text[:500])
        if result:
            _cache[cache_key] = result
            return result
    except Exception as e:
        logger.debug(f"翻译失败: {e}")
    return text


def _build_source_text(item_dict: dict) -> str:
    """构建用于翻译的文本，智能拼接标题+摘要，清理 RSS 截断标记。"""
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()
    # 清理 RSS 截断标记
    summary = re.sub(r"\s*[\[【][\+\d].*?[\]】]\s*$", "", summary).strip()
    summary = re.sub(r"\s*\.{2,}\s*$", "", summary).strip()
    summary = re.sub(r"\s*…\s*$", "", summary).strip()

    if not summary or len(summary) < 20:
        return title

    title_norm = re.sub(r"\s+", " ", title.lower())
    summary_norm = re.sub(r"\s+", " ", summary.lower())
    if summary_norm.startswith(title_norm[:50]):
        extra = summary[len(title_norm[:50]):].strip(" .-")
        combined = f"{title}. {extra}" if len(extra) > 20 else title
    else:
        sep = "。" if title.endswith(("。", "！", "？")) else ". "
        combined = f"{title}{sep}{summary}"
    return combined[:500]


def _ensure_complete_sentence(text: str) -> str:
    """确保翻译结果以完整句子结尾。"""
    if not text:
        return text
    if text[-1] in "。！？.!?":
        return text
    for sep in ["。", "！", "？", ".", "!", "?"]:
        idx = text.rfind(sep)
        if idx > len(text) * 0.4:
            return text[:idx + 1]
    return text


# ── AI 连通性预检（模块级缓存，只检测一次）──────────────────────────

_ai_reachable: Optional[bool] = None   # None=未检测, True=可用, False=不可用


def _check_ai_reachable() -> bool:
    """
    发送一个极小请求测试 LLM 代理是否可达。
    超时 10 秒即判定不可达，后续所有文章直接走 Google Translate，
    避免逐条等待 25 秒超时造成 CI 任务大幅延误。
    """
    global _ai_reachable
    if _ai_reachable is not None:
        return _ai_reachable
    try:
        _AI_CLIENT.chat.completions.create(
            model=_LLM_MODEL,
            max_tokens=5,
            timeout=10.0,
            messages=[{"role": "user", "content": "hi"}],
        )
        logger.info("[AI] 连通性预检通过，将使用 LLM 处理")
        _ai_reachable = True
    except Exception as e:
        err_str = str(e)
        # 429 表示 API 可达但触发速率限制，仍视为可用
        if "429" in err_str or "rate_limit" in err_str.lower():
            logger.info("[AI] 连通性预检触发速率限制，但 API 可达，将使用 LLM 处理")
            _ai_reachable = True
        else:
            logger.warning(
                f"[AI] 连通性预检失败，本次批量翻译全部使用 Google Translate 回退。"
                f"原因：{type(e).__name__}: {e}"
            )
            _ai_reachable = False
    return _ai_reachable


# ── 主入口 ────────────────────────────────────────────────────────────

def translate_item_fields(item_dict: dict) -> dict:
    """
    生成 title_zh 和 summary_zh。

    优先：Claude AI（规范中文重塑 + 深度摘要）
    回退：Google Translate（字面翻译）
    """
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()

    # ── 路径一：LLM AI ────────────────────────────────────────────────
    if _HAS_AI and _check_ai_reachable():
        result = _ai_process(title, summary)
        if result:
            item_dict["title_zh"] = result["title_zh"]
            item_dict["summary_zh"] = result["summary_zh"]
            time.sleep(4)   # Groq 免费层 6000 TPM，每条约300 token，4s间隔确保不超限
            return item_dict
        logger.warning(f"AI 处理未返回有效结果，回退到 Google Translate: {title[:50]}")

    # ── 路径二：Google Translate 回退 ─────────────────────────────────
    if title and not _is_mostly_chinese(title):
        item_dict["title_zh"] = translate_to_zh(title[:200])
        time.sleep(0.15)
    else:
        item_dict["title_zh"] = title

    source_text = _build_source_text(item_dict)
    if _is_mostly_chinese(source_text):
        item_dict["summary_zh"] = source_text
    else:
        raw = translate_to_zh(source_text)
        item_dict["summary_zh"] = _ensure_complete_sentence(raw)
        time.sleep(0.2)

    return item_dict
