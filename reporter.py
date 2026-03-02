"""
报告生成器 - 支持终端表格、Markdown、HTML 输出
HTML 报告支持:
  - 一级分类颜色区分
  - 区域分组展示（东南亚/南亚/中东/欧洲/北美/南美/日韩台/其他）
  - 时间列展示立法动态发布时间
  - Lilith Legal 品牌标识
"""

import base64
import os
import html as html_mod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config import OUTPUT_DIR, REGION_DISPLAY_ORDER


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── 工具函数 ──────────────────────────────────────────────────────

def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ""
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


def _get_display_title(item: dict) -> str:
    """标题显示原文（不使用中文翻译）"""
    return item.get("title", "")


def _get_summary_zh(item: dict) -> str:
    """摘要优先返回中文翻译，没有则返回原文"""
    return item.get("summary_zh") or item.get("summary", "")


# ─── 区域分组配置 ────────────────────────────────────────────────────

_REGION_GROUP_MAP = {
    # 东南亚
    "东南亚": "东南亚", "越南": "东南亚", "印度尼西亚": "东南亚",
    "泰国": "东南亚", "菲律宾": "东南亚", "马来西亚": "东南亚", "新加坡": "东南亚",
    "缅甸": "东南亚", "柬埔寨": "东南亚",
    # 南亚
    "南亚": "南亚", "印度": "南亚", "巴基斯坦": "南亚",
    "孟加拉国": "南亚", "斯里兰卡": "南亚",
    # 中东
    "中东/非洲": "中东", "中东": "中东", "沙特": "中东",
    "阿联酋": "中东", "土耳其": "中东", "以色列": "中东", "非洲": "中东",
    # 欧洲
    "欧洲": "欧洲", "欧盟": "欧洲", "英国": "欧洲", "德国": "欧洲",
    "法国": "欧洲", "荷兰": "欧洲", "比利时": "欧洲", "意大利": "欧洲",
    "西班牙": "欧洲", "波兰": "欧洲", "瑞典": "欧洲", "挪威": "欧洲",
    # 北美
    "北美": "北美", "美国": "北美", "加拿大": "北美",
    # 南美
    "南美": "南美", "巴西": "南美", "阿根廷": "南美", "墨西哥": "南美",
    "智利": "南美", "哥伦比亚": "南美",
    # 日韩台
    "日本": "日韩台", "韩国": "日韩台", "港澳台": "日韩台",
    "台湾": "日韩台", "香港": "日韩台", "澳门": "日韩台",
    # 其他
    "大洋洲": "其他", "澳大利亚": "其他", "新西兰": "其他",
    "全球": "其他", "其他": "其他",
}

_GROUP_ORDER = ["东南亚", "南亚", "中东", "欧洲", "北美", "南美", "日韩台", "其他"]

_GROUP_EMOJI = {
    "东南亚": "🌏", "南亚": "🌏", "中东": "🕌",
    "欧洲": "🌍", "北美": "🌎", "南美": "🌎",
    "日韩台": "🌸", "其他": "🌐",
}


def _get_region_group(region: str) -> str:
    if region in _REGION_GROUP_MAP:
        return _REGION_GROUP_MAP[region]
    # 模糊匹配
    for key, group in _REGION_GROUP_MAP.items():
        if key in region or region in key:
            return group
    return "其他"


# ─── Lilith Legal Logo 嵌入 ─────────────────────────────────────────

_LOGO_PATH = Path(__file__).parent / "assets" / "lilith-logo.png"


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
    "数据隐私":    {"row": "#F0F4FF", "bg": "#DBEAFE", "text": "#1E40AF", "border": "#93C5FD"},
    "玩法合规":    {"row": "#F5F0FF", "bg": "#EDE9FE", "text": "#5B21B6", "border": "#C4B5FD"},
    "未成年人保护": {"row": "#F0FDF4", "bg": "#D1FAE5", "text": "#065F46", "border": "#6EE7B7"},
    "广告营销合规": {"row": "#FFFBF0", "bg": "#FEF3C7", "text": "#92400E", "border": "#FCD34D"},
    "消费者保护":   {"row": "#F0FDFA", "bg": "#CCFBF1", "text": "#134E4A", "border": "#5EEAD4"},
    "经营合规":    {"row": "#FFF7ED", "bg": "#FFEDD5", "text": "#9A3412", "border": "#FCA369"},
    "平台政策":    {"row": "#FFF1F2", "bg": "#FFE4E6", "text": "#9F1239", "border": "#FDA4AF"},
    "内容监管":    {"row": "#F8FAFC", "bg": "#E2E8F0", "text": "#334155", "border": "#94A3B8"},
    "市场准入":    {"row": "#FFF7ED", "bg": "#FFEDD5", "text": "#9A3412", "border": "#FCA369"},
}
DEFAULT_STYLE = {"row": "#FAFAFA", "bg": "#F1F5F9", "text": "#334155", "border": "#CBD5E1"}

STATUS_CSS = {
    "已生效":      "background:#DCFCE7;color:#166534;",
    "即将生效":     "background:#FEF9C3;color:#713F12;",
    "草案/征求意见": "background:#DBEAFE;color:#1E40AF;",
    "立法进行中":   "background:#E0E7FF;color:#3730A3;",
    "已提案":      "background:#E2E8F0;color:#334155;",
    "已修订":      "background:#FEF3C7;color:#92400E;",
    "已废止":      "background:#F1F5F9;color:#475569;",
    "执法动态":    "background:#FEE2E2;color:#991B1B;",
    "政策信号":    "background:#F1F5F9;color:#475569;",
}

IMPACT_CONFIG = {
    3: {"dots": "●●●", "label": "高优先",  "color": "#DC2626", "title": "高优先：已生效/即将生效/官方执法"},
    2: {"dots": "●●○", "label": "中优先",  "color": "#D97706", "title": "中优先：草案/立法中/执法动态"},
    1: {"dots": "●○○", "label": "低优先",  "color": "#16A34A", "title": "低优先：政策信号/背景信息"},
}

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
    "已修订": C.YELLOW,
    "已废止": C.DIM,
    "执法动态": C.RED,
    "政策信号": C.DIM,
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
        f"摘要(中文)"
    )
    print(f"{C.BOLD}{header}{C.RESET}")
    print(f"{'-'*140}")

    for item in items:
        status = item.get("status", "政策信号")
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
    lines.append("| 类别 | 标题(原文) | 发布时间 | 状态 | 摘要(中文) |")
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


def generate_html(items: List[dict], title: str = "全球游戏行业立法动态监控报告",
                  period_label: str = "") -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    logo_html = _get_logo_html()

    # ── 按区域分组 ────────────────────────────────────────────────
    grouped: dict = defaultdict(list)
    for item in items:
        group = _get_region_group(item.get("region", "其他"))
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
        # 条目行（按日期倒序）
        for item in sorted(group_items, key=lambda x: x.get("date", ""), reverse=True):
            cat = item.get("category_l1", "")
            style = CATEGORY_STYLE.get(cat, DEFAULT_STYLE)
            status = item.get("status", "")
            status_css = STATUS_CSS.get(status, "background:#F1F5F9;color:#475569;")
            impact = int(item.get("impact_score", 1))

            from classifier import get_source_tier
            source_raw = item.get("source_name", "")
            tier = get_source_tier(source_raw)
            tier_cfg = TIER_CONFIG.get(tier, TIER_CONFIG["news"])

            title_orig = html_mod.escape(item.get("title", ""))
            summary_zh_full = html_mod.escape(_get_summary_zh(item))
            summary_zh = html_mod.escape(_truncate(_get_summary_zh(item), 200))
            url = item.get("source_url", "")
            item_date = item.get("date", "")
            region = html_mod.escape(item.get("region", ""))
            source_name = html_mod.escape(source_raw)

            if url:
                title_link = (f'<a href="{html_mod.escape(url)}" target="_blank" '
                              f'rel="noopener" title="{summary_zh_full}">{title_orig}</a>')
            else:
                title_link = f'<span title="{summary_zh_full}">{title_orig}</span>'

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

            rows_html += (
                f'\n        <tr data-date="{html_mod.escape(item_date)}" '
                f'data-cat="{html_mod.escape(cat)}" data-region="{region}" '
                f'data-group="{html_mod.escape(group)}" '
                f'data-impact="{impact}" '
                f'style="border-left:3px solid {style["border"]};">'
                f'<td class="td-region">{region}</td>'
                f'<td class="td-cat">{cat_badge}</td>'
                f'<td class="td-title">'
                f'{title_link}'
                f'{"<br><span class=td-source>" + tier_badge + " " + source_name + "</span>" if source_name else ""}'
                f'</td>'
                f'<td class="td-date">{html_mod.escape(item_date)}</td>'
                f'<td class="td-status">{status_badge}</td>'
                f'<td class="td-summary">{summary_zh}</td>'
                f'</tr>'
            )

    legend_html = _build_legend_html()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title)}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", "PingFang SC", sans-serif;
    background: #F1F5F9;
    color: #1E293B;
    padding: 24px 20px;
    min-height: 100vh;
}}
.container {{ max-width: 1700px; margin: 0 auto; }}

/* ── 头部 ── */
.header {{
    background: linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #0F3460 100%);
    color: white;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
}}
.header-left h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }}
.header-left .meta {{ font-size: 12px; color: #94A3B8; margin-top: 4px; }}
.header-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}}
.header-logo {{
    height: 36px;
    width: auto;
    object-fit: contain;
    filter: brightness(0) invert(1);
    opacity: 0.9;
}}
.brand-name {{
    font-size: 14px;
    font-weight: 700;
    color: rgba(255,255,255,0.85);
    letter-spacing: 1.5px;
    text-transform: uppercase;
    border-left: 1px solid rgba(255,255,255,0.25);
    padding-left: 10px;
    white-space: nowrap;
}}

/* ── 颜色图例 ── */
.legend {{
    background: white;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
.legend::before {{
    content: "分类色标：";
    font-size: 11px;
    color: #64748B;
    font-weight: 600;
    white-space: nowrap;
}}
.legend-item {{
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}}

/* ── 筛选栏 ── */
.toolbar {{
    background: white;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 12px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}
.toolbar label {{ font-size: 12px; color: #64748B; font-weight: 600; }}
.toolbar select, .toolbar input {{
    padding: 6px 10px;
    border: 1px solid #E2E8F0;
    border-radius: 7px;
    font-size: 13px;
    color: #334155;
    background: #F8FAFC;
    outline: none;
}}
.toolbar select:focus, .toolbar input:focus {{
    border-color: #94A3B8;
    background: white;
}}
.toolbar input {{ width: 220px; }}
.result-count {{ margin-left: auto; font-size: 12px; color: #64748B; }}

/* ── 表格 ── */
.table-wrap {{ border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
thead tr {{ background: #1E293B; }}
th {{
    padding: 11px 10px;
    text-align: left;
    font-size: 11px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    cursor: pointer;
    white-space: nowrap;
    user-select: none;
}}
th:hover {{ color: white; }}
th .sort-icon {{ opacity: 0.4; margin-left: 3px; font-size: 10px; }}
th.sorted .sort-icon {{ opacity: 1; }}

/* ── 分组 header 行 ── */
.group-row td.group-header {{
    background: linear-gradient(90deg, #1E293B 0%, #334155 100%);
    color: #E2E8F0;
    font-size: 12px;
    font-weight: 700;
    padding: 8px 14px;
    letter-spacing: 0.5px;
}}
.group-count {{
    display: inline-block;
    background: rgba(255,255,255,0.15);
    color: #CBD5E1;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 7px;
    border-radius: 8px;
    margin-left: 8px;
    vertical-align: middle;
}}

tbody tr:not(.group-row) {{
    border-bottom: 1px solid #F1F5F9;
    transition: filter 0.1s;
}}
tbody tr:not(.group-row):hover {{ filter: brightness(0.97); }}
td {{ padding: 9px 10px; font-size: 12px; vertical-align: top; }}

.td-region {{ white-space: nowrap; font-weight: 600; color: #475569; font-size: 11px; }}
.td-cat {{ white-space: nowrap; }}
.td-sub {{ color: #64748B; font-size: 11px; min-width: 90px; }}
.td-title {{ min-width: 200px; max-width: 320px; font-weight: 500; line-height: 1.5; }}
.td-title a {{ color: #1D4ED8; text-decoration: none; }}
.td-title a:hover {{ text-decoration: underline; color: #1E40AF; }}
.td-source {{ font-size: 10px; color: #94A3B8; margin-top: 2px; display: block; }}
.td-date {{
    white-space: nowrap;
    font-size: 12px;
    color: #475569;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}}
.td-status {{ white-space: nowrap; }}
.td-summary {{ max-width: 320px; color: #475569; line-height: 1.5; font-size: 11px; }}

.cat-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
}}
.status-badge {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 5px;
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
    padding: 48px;
    color: #94A3B8;
    font-size: 14px;
    display: none;
}}

/* ── 页脚 ── */
.footer {{
    margin-top: 20px;
    text-align: center;
    font-size: 11px;
    color: #94A3B8;
    padding-bottom: 12px;
}}

/* ── 响应式 ── */
@media (max-width: 900px) {{
    .td-summary {{ display: none; }}
    .td-sub {{ display: none; }}
}}
</style>
</head>
<body>
<div class="container">

  <!-- 头部 -->
  <div class="header">
    <div class="header-left">
      <h1>{html_mod.escape(title)}</h1>
      <div class="meta">生成时间：{now}&nbsp;&nbsp;|&nbsp;&nbsp;共 {len(items)} 条动态</div>
    </div>
    <div class="header-brand">
      {logo_html}
      <span class="brand-name">Lilith Legal</span>
    </div>
  </div>

  <!-- 分类颜色图例 -->
  {legend_html}

  <!-- 筛选栏 -->
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

  <!-- 表格 -->
  <div class="table-wrap">
    <table id="mainTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">区域 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(1)">类别 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(2)">标题 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(3)">发布时间 <span class="sort-icon">⇅</span></th>
          <th onclick="sortTable(4)">状态 <span class="sort-icon">⇅</span></th>
          <th>摘要(中文)</th>
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
(function() {{
  // 初始化地区分组下拉
  const rows = document.querySelectorAll('#mainTable tbody tr:not(.group-row)');
  const groups = new Set(), cats = new Set(), statuses = new Set();
  rows.forEach(r => {{
    if (r.dataset.group) groups.add(r.dataset.group);
    if (r.dataset.cat)   cats.add(r.dataset.cat);
    const badge = r.querySelector('.status-badge');
    if (badge) statuses.add(badge.textContent.trim());
  }});

  // 按预设顺序填充地区下拉
  const groupOrder = ["东南亚","南亚","中东","欧洲","北美","南美","日韩台","其他"];
  const fGroup = document.getElementById('fGroup');
  groupOrder.forEach(g => {{
    if (groups.has(g)) {{
      const o = document.createElement('option');
      o.value = g; o.textContent = g; fGroup.appendChild(o);
    }}
  }});

  const fill = (sel, vals) => {{
    [...vals].filter(Boolean).sort().forEach(v => {{
      const o = document.createElement('option');
      o.value = v; o.textContent = v; sel.appendChild(o);
    }});
  }};
  fill(document.getElementById('fCat'), cats);
  fill(document.getElementById('fStatus'), statuses);
  updateCount();
}})();

function applyFilters() {{
  const group  = document.getElementById('fGroup').value;
  const cat    = document.getElementById('fCat').value;
  const status = document.getElementById('fStatus').value;
  const kw     = document.getElementById('fKeyword').value.toLowerCase();

  const rows = document.querySelectorAll('#mainTable tbody tr:not(.group-row)');
  const groupVisible = {{}};
  let visible = 0;

  rows.forEach(r => {{
    let show = true;
    if (show && group  && r.dataset.group !== group) show = false;
    if (show && cat    && r.dataset.cat   !== cat)   show = false;
    if (show && status) {{
      const badge = r.querySelector('.status-badge');
      if (!badge || badge.textContent.trim() !== status) show = false;
    }}
    if (show && kw && !r.textContent.toLowerCase().includes(kw)) show = false;
    r.style.display = show ? '' : 'none';
    if (show) {{ visible++; groupVisible[r.dataset.group] = true; }}
  }});

  // 控制分组 header 显隐
  document.querySelectorAll('.group-row').forEach(r => {{
    r.style.display = groupVisible[r.dataset.group] ? '' : 'none';
  }});

  updateCount(visible);
}}

function updateCount(n) {{
  const total = document.querySelectorAll('#mainTable tbody tr:not(.group-row)').length;
  const cnt = (n === undefined) ? total : n;
  document.getElementById('resultCount').textContent = `显示 ${{cnt}} / ${{total}} 条`;
  document.getElementById('noData').style.display = cnt === 0 ? 'block' : 'none';
}}

let _sortDir = {{}};
function sortTable(col) {{
  const tbody = document.querySelector('#mainTable tbody');
  const dataRows = [...tbody.querySelectorAll('tr:not(.group-row)')];
  _sortDir[col] = !_sortDir[col];

  document.querySelectorAll('th').forEach((th, i) => {{
    th.classList.toggle('sorted', i === col);
    const icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = (i === col) ? (_sortDir[col] ? '↑' : '↓') : '⇅';
  }});

  // 按列排序（忽略分组 header，排序后重新按分组插入）
  dataRows.sort((a, b) => {{
    let va = a.cells[col]?.textContent.trim() ?? '';
    let vb = b.cells[col]?.textContent.trim() ?? '';
    if (col === 3) return _sortDir[col] ? va.localeCompare(vb) : vb.localeCompare(va);
    return _sortDir[col] ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
  }});

  // 把分组 header 和对应数据行重新排列
  const groupRows = [...tbody.querySelectorAll('.group-row')];
  const groupOrder = ["东南亚","南亚","中东","欧洲","北美","南美","日韩台","其他"];
  tbody.innerHTML = '';

  groupOrder.forEach(grp => {{
    const hdr = groupRows.find(r => r.dataset.group === grp);
    if (!hdr) return;
    const grpDataRows = dataRows.filter(r => r.dataset.group === grp);
    if (grpDataRows.length === 0) return;
    tbody.appendChild(hdr);
    grpDataRows.forEach(r => tbody.appendChild(r));
  }});
}}
</script>
</body>
</html>"""


def save_html(items: List[dict], filename: Optional[str] = None,
              period_label: str = "") -> str:
    ensure_output_dir()
    if not filename:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    content = generate_html(items, period_label=period_label)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath
