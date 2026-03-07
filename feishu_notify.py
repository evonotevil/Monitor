#!/usr/bin/env python3
"""
飞书机器人通知 — 每周合规简报卡片（决策参考版）

必需环境变量:
    FEISHU_WEBHOOK_URL   飞书自定义机器人的 Webhook 地址

可选环境变量:
    REPORT_HTML_URL      HTML 简报的公开访问 URL
    REPORT_PDF_URL       PDF 报告的公开访问/下载 URL

本地调试:
    FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
    REPORT_HTML_URL=https://... \
    python feishu_notify.py
"""

import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

from utils import _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, normalize_status
from classifier import get_source_tier, _is_hardware_noise, _is_google_apple_non_core


# ── 影响力红绿灯 ──────────────────────────────────────────────────────

def _impact_emoji(score: float) -> str:
    """根据 impact_score 返回红绿灯 Emoji。"""
    if score >= 9.0:
        return "🔴"
    elif score >= 7.0:
        return "🟠"
    else:
        return "🔵"


# ── 分类 Emoji ────────────────────────────────────────────────────────

CAT_EMOJI = {
    "数据隐私":        "🔒",
    "玩法合规":        "🎲",
    "未成年人保护":    "🧒",
    "广告营销合规":    "📣",
    "消费者保护":      "🛡️",
    "经营合规":        "🏢",
    "平台政策":        "📱",
    "内容监管":        "📋",
    "PC & 跨平台合规": "💻",
}

# ── 业务影响标签（按 category_l1 分别给出移动端 / PC 端关注点）──────────

_MOBILE_IMPACT: dict = {
    "平台政策":        "商店分成比例、IAP 规则合规、IDFA/GAID 采集授权",
    "玩法合规":        "Gacha 概率公示、Loot Box 合规、IAP 道具随机机制",
    "未成年人保护":    "移动端实名/年龄验证 SDK、防沉迷机制接入",
    "广告营销合规":    "移动端广告 SDK 合规、IDFA 授权流程",
    "消费者保护":      "IAP 退款政策、虚拟货币兑换透明度",
    "数据隐私":        "IDFA/GAID 采集同意、数据跨境传输合规",
    "经营合规":        "App Store/Google Play 经营资质、本地化实体要求",
    "内容监管":        "移动端分级证书、平台内容审核接入",
    "PC & 跨平台合规": "账号体系跨端打通、移动端同步政策核查",
}

_PC_IMPACT: dict = {
    "平台政策":        "D2C 充值页支付合规、第三方 Launcher 接入规则",
    "玩法合规":        "PC 端 Loot Box 概率展示、Steam 概率公示合规",
    "未成年人保护":    "PC 端年龄验证机制、防沉迷实名接入",
    "广告营销合规":    "PC 端广告追踪合规、Cookie 同意管理",
    "消费者保护":      "PC 官网充值退款条款、D2C 消费者权益",
    "数据隐私":        "PC 端 SDK 数据采集合规、跨境传输合规",
    "经营合规":        "PC 官网经营资质、本地化合规备案",
    "内容监管":        "PC 端分级证书、内核级安全软件合规",
    "PC & 跨平台合规": "PC 启动器权限、Anti-cheat 内核安全、D2C 发行服务、跨端账号体系",
}

_DEFAULT_MOBILE = "关注商店分成、IDFA 采集、SDK 合规"
_DEFAULT_PC     = "关注 PC 启动器隐私、D2C 发行服务、跨端账号体系"


def _business_label(category_l1: str) -> str:
    """返回每条动态的全平台合规影响标签（移动端优先）。"""
    mobile = _MOBILE_IMPACT.get(category_l1, _DEFAULT_MOBILE)
    pc     = _PC_IMPACT.get(category_l1, _DEFAULT_PC)
    return (
        f"**【全平台合规影响】**\n"
        f"📱 **移动端**：{mobile}\n"
        f"💻 **PC 渠道**：{pc}"
    )


# ── 数据库查询 ────────────────────────────────────────────────────────

_TIER_SORT = {"official": 4, "legal": 3, "industry": 2, "news": 1}


def get_weekly_data():
    """
    返回 (today, week_ago, total, by_cat, by_region_group, all_items)

    all_items 为本周内 impact_score > 0、已有中文标题的条目列表，
    已按 source_tier DESC → impact_score DESC 排序，供区域分组直接使用。
    """
    if not DB_PATH.exists():
        print(f"⚠️  数据库不存在: {DB_PATH}")
        return datetime.now(), datetime.now() - timedelta(days=7), 0, [], {}, []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    today    = datetime.now()
    week_ago = today - timedelta(days=7)
    since    = week_ago.strftime("%Y-%m-%d")

    # ── 噪音门控：仅计 impact_score > 0 的条目 ──────────────────────
    NOISE_GUARD = "COALESCE(impact_score, 1.0) > 0"

    total = conn.execute(
        f"SELECT COUNT(*) FROM legislation WHERE date >= ? AND {NOISE_GUARD}",
        (since,),
    ).fetchone()[0]

    by_cat = conn.execute(
        f"""SELECT category_l1, COUNT(*) AS cnt
            FROM legislation WHERE date >= ? AND {NOISE_GUARD}
            GROUP BY category_l1 ORDER BY cnt DESC""",
        (since,),
    ).fetchall()

    by_region_raw = conn.execute(
        f"""SELECT region, COUNT(*) AS cnt
            FROM legislation WHERE date >= ? AND {NOISE_GUARD}
            GROUP BY region""",
        (since,),
    ).fetchall()

    # 所有条目（用于综述生成 + 区域分组展示）
    # title_zh 过滤：没有中文标题的条目不展示在卡片中
    all_rows = conn.execute(
        f"""SELECT title, title_zh, summary_zh, summary, region, status, category_l1,
                   source_url, date,
                   COALESCE(impact_score, 1.0) AS impact_score,
                   COALESCE(source_name, '') AS source_name
            FROM legislation
            WHERE date >= ?
              AND {NOISE_GUARD}
              AND title_zh IS NOT NULL AND TRIM(title_zh) != ''
            ORDER BY COALESCE(impact_score, 1.0) DESC""",
        (since,),
    ).fetchall()

    conn.close()

    by_region_group: dict = {}
    for row in by_region_raw:
        group = _get_region_group(row["region"])
        by_region_group[group] = by_region_group.get(group, 0) + row["cnt"]

    # ── 实时噪音门控（兜底 DB 中旧评分残留）──────────────────────────
    # DB 中 impact_score 可能是旧版分类结果，用最新规则再过滤一次
    def _is_noise(item: dict) -> bool:
        text = " ".join(filter(None, [
            item.get("title", ""),
            item.get("title_zh", ""),
            item.get("summary", ""),
        ]))
        return _is_hardware_noise(text) or _is_google_apple_non_core(text)

    # ── 每条目补充 source_tier，排序：tier DESC → score DESC ──────────
    items = []
    for r in all_rows:
        d = dict(r)
        if _is_noise(d):
            continue
        d["_tier"] = _TIER_SORT.get(get_source_tier(d.get("source_name", "")), 1)
        items.append(d)
    items.sort(key=lambda x: (x["_tier"], float(x.get("impact_score", 1.0))), reverse=True)

    return today, week_ago, total, [dict(r) for r in by_cat], by_region_group, items


# ── 执行摘要（复用 HTML 报告同一 LLM 函数）───────────────────────────

def _get_exec_summary(items: list) -> str:
    """调用 translator.generate_executive_summary 获取 300 字综述；失败静默返回空。"""
    try:
        from translator import generate_executive_summary
        return generate_executive_summary(items)
    except Exception as e:
        print(f"⚠️  综述生成失败（将跳过）: {e}")
        return ""


# ── 构建飞书卡片 ──────────────────────────────────────────────────────

# 每个区域分组最多展示条目数（避免卡片过长）
_MAX_PER_GROUP = 3
# 全局条目上限
_MAX_TOTAL_ITEMS = 12


def _bigram_sim(a: str, b: str) -> float:
    a, b = (a or "").lower(), (b or "").lower()
    if len(a) < 2 or len(b) < 2:
        return 0.0
    bg_a = {a[i:i + 2] for i in range(len(a) - 1)}
    bg_b = {b[i:i + 2] for i in range(len(b) - 1)}
    union = bg_a | bg_b
    return len(bg_a & bg_b) / len(union) if union else 0.0


def _pick_group_items(candidates: list, max_items: int) -> list:
    """
    从候选条目中筛选 max_items 条，应用两层去重：
    1. Bigram 相似度 > 0.45 → 视为同一事件，保留首条
    2. 同一 category_l1 最多保留 2 条（避免同分类扎堆）
    """
    selected: list = []
    cat_count: dict = {}
    for item in candidates:
        cat   = item.get("category_l1", "")
        title = (item.get("title_zh") or item.get("title") or "")
        # Bigram 去重
        if any(
            _bigram_sim(title, (s.get("title_zh") or s.get("title") or "")) > 0.45
            for s in selected
        ):
            continue
        # 同分类上限 1 条（飞书卡片空间有限，同分类只取最优一条）
        if cat_count.get(cat, 0) >= 1:
            continue
        selected.append(item)
        cat_count[cat] = cat_count.get(cat, 0) + 1
        if len(selected) >= max_items:
            break
    return selected


def build_card(
    today: datetime,
    week_ago: datetime,
    total: int,
    by_cat: list,
    by_region_group: dict,
    all_items: list,
    exec_summary: str,
    html_url: str,
    pdf_url: str,
) -> dict:

    # ── 日期范围文案 ─────────────────────────────────────────────────
    date_range = (
        f"{week_ago.strftime('%Y/%m/%d')} – {today.strftime('%Y/%m/%d')}"
    )

    # ── 分类统计行 ───────────────────────────────────────────────────
    cat_parts = [
        f"{CAT_EMOJI.get(r['category_l1'], '•')} {r['category_l1']} **{r['cnt']}**"
        for r in by_cat if r.get("category_l1")
    ]
    cat_line = "　".join(cat_parts) if cat_parts else "暂无数据"

    # ── 区域分组统计行（按 _GROUP_ORDER 排序）──────────────────────
    region_parts = []
    for group in _GROUP_ORDER:
        cnt = by_region_group.get(group, 0)
        if cnt > 0:
            emoji = _GROUP_EMOJI.get(group, "•")
            region_parts.append(f"{emoji} {group} **{cnt}**")
    region_line = "　".join(region_parts) if region_parts else "暂无数据"

    # ── 将条目按区域分组，每组 bigram 去重后限 _MAX_PER_GROUP 条 ──────
    raw_grouped: dict = defaultdict(list)
    for item in all_items:
        group = _get_region_group(item.get("region", "其他"))
        raw_grouped[group].append(item)

    grouped = {g: _pick_group_items(v, _MAX_PER_GROUP) for g, v in raw_grouped.items()}

    # ── 组装卡片 elements ────────────────────────────────────────────
    elements: list = []

    # 副标题
    elements.append({
        "tag": "markdown",
        "content": f"📅 **上周合规动态回顾** | {date_range}",
    })

    # 引用块：综述（有内容才展示，不带标题直接显示正文）
    if exec_summary:
        elements.append({
            "tag": "markdown",
            "content": "\n".join(f"> {line}" for line in exec_summary.splitlines()),
        })

    # 统计数据
    elements.append({
        "tag": "markdown",
        "content": (
            f"共监测到 **{total}** 条合规动态\n\n"
            f"**🗺️ 按地区**\n{region_line}"
        ),
    })

    # ── 分区域展示重点条目 ───────────────────────────────────────────
    total_shown = 0
    for group in _GROUP_ORDER:
        items_in_group = grouped.get(group, [])
        if not items_in_group:
            continue

        elements.append({"tag": "hr"})

        group_emoji = _GROUP_EMOJI.get(group, "🌐")
        group_cnt   = by_region_group.get(group, 0)
        elements.append({
            "tag": "markdown",
            "content": f"**{group_emoji} {group}** · 本周 {group_cnt} 条",
        })

        for item in items_in_group:
            if total_shown >= _MAX_TOTAL_ITEMS:
                break

            score   = float(item.get("impact_score", 1.0))
            risk_em = _impact_emoji(score)
            cat     = item.get("category_l1", "")
            cat_em  = CAT_EMOJI.get(cat, "")
            status  = normalize_status(item.get("status", ""))
            region  = item.get("region", "")

            # 使用清洗后的中文标题
            title_zh = (item.get("title_zh") or "").strip()
            url      = item.get("source_url", "")
            title_md = f"[{title_zh}]({url})" if url else title_zh

            # 摘要（优先中文，截断至 90 字）
            summary = (item.get("summary_zh") or item.get("summary") or "").strip()
            if len(summary) > 90:
                summary = summary[:90] + "…"

            date_tag = item.get("date", "")

            elements.append({
                "tag": "markdown",
                "content": (
                    f"{risk_em} **[{region}]** {status} · {cat_em} {cat}\n"
                    f"{title_md}\n"
                    f"_{summary}_\n"
                    f"「{date_tag}」"
                ),
            })
            total_shown += 1

    # ── 底部按钮 ─────────────────────────────────────────────────────
    elements.append({"tag": "hr"})

    actions = []
    if html_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🌐 查看完整报告"},
            "type": "primary",
            "url": html_url,
        })
    if pdf_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📄 下载 PDF 报告"},
            "type": "default",
            "url": pdf_url,
        })
    if actions:
        elements.append({"tag": "action", "actions": actions})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {
                "tag": "plain_text",
                "content": "🌍 Lilith Legal · 全球游戏合规周报",
            },
        },
        "elements": elements,
    }


# ── 发送 ─────────────────────────────────────────────────────────────

def send_card(webhook_url: str, card: dict) -> None:
    payload = {"msg_type": "interactive", "card": card}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        code = result.get("code", result.get("StatusCode", -1))
        if code == 0:
            print("✅ 飞书通知发送成功")
        else:
            print(f"⚠️  飞书返回异常: {result}")
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        sys.exit(1)


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    html_url    = os.environ.get("REPORT_HTML_URL", "")
    pdf_url     = os.environ.get("REPORT_PDF_URL", "")

    if not webhook_url:
        print("❌ 未设置 FEISHU_WEBHOOK_URL 环境变量")
        sys.exit(1)

    today, week_ago, total, by_cat, by_region_group, all_items = get_weekly_data()
    print(f"本周数据: {total} 条（噪音过滤后），区域分布: {by_region_group}，展示条目: {len(all_items)}")

    # 综述生成（LLM，失败不阻断）
    exec_summary = _get_exec_summary(all_items)
    if exec_summary:
        print(f"综述生成成功，{len(exec_summary)} 字")
    else:
        print("综述生成跳过（无 API Key 或调用失败）")

    card = build_card(
        today, week_ago, total, by_cat, by_region_group, all_items,
        exec_summary, html_url, pdf_url,
    )
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
