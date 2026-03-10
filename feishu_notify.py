#!/usr/bin/env python3
"""
飞书机器人通知 — 每周合规简报卡片（决策参考版）

必需环境变量:
    FEISHU_WEBHOOK_URL   飞书自定义机器人的 Webhook 地址

可选环境变量:
    REPORT_MOBILE_URL    移动端 HTML 周报 URL
    REPORT_PC_URL        PC 端 HTML 周报 URL
    REPORT_HTML_URL      HTML 简报 URL（兼容旧配置，指向移动端）
    REPORT_PDF_URL       PDF 报告的公开访问/下载 URL

本地调试:
    FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
    REPORT_MOBILE_URL=https://... \
    REPORT_PC_URL=https://... \
    python feishu_notify.py
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

from utils import (
    _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, _TIER_SORT, send_card, CAT_EMOJI,
)
from classifier import get_source_tier, _is_hardware_noise, _is_google_apple_non_core

# 与 reporter.py 一致：这三种状态的条目进入「重点跟进」区块
_ACTION_STATUSES = {"👤 待研判", "🏃 处理/跟进中", "✅ 已合规/归档"}


# ── 数据库查询 ────────────────────────────────────────────────────────


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

    return today, week_ago, total, by_region_group, items


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


def build_card(
    today: datetime,
    week_ago: datetime,
    total: int,
    by_region_group: dict,
    exec_summary: str,
    html_url: str,
    mobile_url: str = "",
    pc_url: str = "",
    action_items: list = None,
) -> dict:
    if action_items is None:
        action_items = []

    # ── 日期范围文案 ─────────────────────────────────────────────────
    date_range = (
        f"{week_ago.strftime('%Y/%m/%d')} – {today.strftime('%Y/%m/%d')}"
    )

    # ── 区域分组统计行（按 _GROUP_ORDER 排序）──────────────────────
    region_parts = []
    for group in _GROUP_ORDER:
        cnt = by_region_group.get(group, 0)
        if cnt > 0:
            emoji = _GROUP_EMOJI.get(group, "•")
            region_parts.append(f"{emoji} {group} **{cnt}**")
    region_line = "　".join(region_parts) if region_parts else "暂无数据"

    # ── 组装卡片 elements ────────────────────────────────────────────
    elements: list = []

    # 日期 + 总量
    elements.append({
        "tag": "markdown",
        "content": f"📅 **上周合规动态回顾** | {date_range}\n共监测到 **{total}** 条合规动态",
    })

    # 区域分布
    elements.append({
        "tag": "markdown",
        "content": f"**🗺️ 按地区**\n{region_line}",
    })

    # 引用块：综述（跳过空行，避免飞书渲染出孤立的 >）
    if exec_summary:
        elements.append({"tag": "hr"})
        quoted_lines = [
            f"> {line}" for line in exec_summary.splitlines() if line.strip()
        ]
        elements.append({
            "tag": "markdown",
            "content": "\n".join(quoted_lines),
        })

    # ── 本周重点跟进（来自 Bitable 待研判条目）──────────────────────
    if action_items:
        from collections import defaultdict
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": f"**📋 本周重点跟进** · {len(action_items)} 条",
        })

        grouped: dict = defaultdict(list)
        for item in action_items:
            group = _get_region_group(item.get("region", "其他"))
            grouped[group].append(item)

        for group in _GROUP_ORDER:
            group_items = grouped.get(group, [])
            if not group_items:
                continue
            emoji = _GROUP_EMOJI.get(group, "•")
            lines = [f"**{emoji} {group}**"]
            for item in group_items:
                title = item.get("title_zh", "").strip()
                url   = item.get("source_url", "")
                cat   = item.get("category_l1", "")
                cat_em = CAT_EMOJI.get(cat, "")
                assignee = item.get("assignee", "")
                title_md = f"[{title}]({url})" if url else title
                line = f"· {title_md}　{cat_em} {cat}"
                if assignee:
                    line += f"　👤 {assignee}"
                lines.append(line)
            elements.append({
                "tag": "markdown",
                "content": "\n".join(lines),
            })

    # ── 底部按钮 ─────────────────────────────────────────────────────
    elements.append({"tag": "hr"})

    actions = []
    # Prefer explicit mobile/PC URLs; fall back to legacy html_url
    effective_mobile = mobile_url or html_url
    if effective_mobile:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📱 移动端周报"},
            "type": "primary",
            "url": effective_mobile,
        })
    if pc_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🖥️ PC 端周报"},
            "type": "default",
            "url": pc_url,
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


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    mobile_url  = os.environ.get("REPORT_MOBILE_URL", "") or os.environ.get("MOBILE_URL", "")
    pc_url      = os.environ.get("REPORT_PC_URL", "") or os.environ.get("PC_URL", "")
    html_url    = os.environ.get("REPORT_HTML_URL", "")

    if not webhook_url:
        print("❌ 未设置 FEISHU_WEBHOOK_URL 环境变量")
        sys.exit(1)

    today, week_ago, total, by_region_group, all_items = get_weekly_data()
    print(f"本周数据: {total} 条（噪音过滤后），区域分布: {by_region_group}，展示条目: {len(all_items)}")

    # 综述生成（LLM，失败不阻断）
    exec_summary = _get_exec_summary(all_items)
    if exec_summary:
        print(f"综述生成成功，{len(exec_summary)} 字")
    else:
        print("综述生成跳过（无 API Key 或调用失败）")

    # 从 Bitable 读取待研判条目（不传 days，取全量有效记录再自行筛选本周）
    action_items: list = []
    try:
        from feishu_bitable import fetch_valid_records_from_bitable
        bitable_items = fetch_valid_records_from_bitable(days=7)
        action_items = [
            i for i in bitable_items
            if i.get("bitable_status") in _ACTION_STATUSES
        ]
        print(f"Bitable 待研判条目: {len(action_items)} 条")
    except Exception as e:
        print(f"⚠️  获取 Bitable 待研判条目失败（不阻断推送）: {e}")

    card = build_card(
        today, week_ago, total, by_region_group,
        exec_summary, html_url,
        mobile_url=mobile_url, pc_url=pc_url,
        action_items=action_items,
    )
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
