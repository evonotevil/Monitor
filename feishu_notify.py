#!/usr/bin/env python3
"""
飞书机器人通知 — 每周合规简报卡片

必需环境变量:
    FEISHU_WEBHOOK_URL   飞书自定义机器人的 Webhook 地址

可选环境变量:
    REPORT_MOBILE_URL    移动端 HTML 周报 URL
    REPORT_PC_URL        PC 端 HTML 周报 URL
    REPORT_HTML_URL      HTML 简报 URL（兼容旧配置，指向移动端）

本地调试:
    FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
    REPORT_MOBILE_URL=https://... \
    REPORT_PC_URL=https://... \
    python feishu_notify.py
"""

import os
import sys

from utils import _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, send_card


# ── 构建飞书卡片 ──────────────────────────────────────────────────────

def build_card(
    archived: list,
    news: list,
    active: list,
    ai_summary: str,
    mobile_url: str = "",
    pc_url: str    = "",
    html_url: str  = "",
) -> dict:
    """
    卡片结构：
    ① 上周已归档完成（条数 + 地区标签）
    ② AI 摘要引用块（关键词 + 风险提示）
    ③ 本周仍在跟进（条数 + 待研判/处理中拆分）
    ④ 按钮行（移动端 / PC 端周报）
    """
    elements: list = []

    # ── ① 上周已归档完成 ─────────────────────────────────────────────
    n_archived = len(archived)
    # 收集去重后的地区标签（保持 _GROUP_ORDER 顺序）
    seen_groups: dict = {}
    for item in archived:
        group = _get_region_group(item.get("region", ""))
        if group not in seen_groups:
            seen_groups[group] = f"{_GROUP_EMOJI.get(group, '🌐')} {group}"
    # 按标准顺序排列
    region_tags = "　".join(
        seen_groups[g] for g in _GROUP_ORDER if g in seen_groups
    ) or "—"

    elements.append({
        "tag": "markdown",
        "content": (
            f"✅ **上周已归档完成 · {n_archived} 条**\n"
            f"{region_tags}"
        ),
    })

    # ── ② AI 摘要（A+B：关键词 + 风险提示）──────────────────────────
    if ai_summary:
        elements.append({"tag": "hr"})
        quoted = "\n".join(
            f"> {line}" for line in ai_summary.splitlines() if line.strip()
        )
        elements.append({"tag": "markdown", "content": quoted})

    # ── ③ 本周仍在跟进 ───────────────────────────────────────────────
    n_active     = len(active)
    n_pending    = sum(1 for i in active if "待研判" in (i.get("bitable_status") or ""))
    n_processing = n_active - n_pending

    followup_line = ""
    parts = []
    if n_pending:
        parts.append(f"👤 待研判 {n_pending} 条")
    if n_processing:
        parts.append(f"🏃 处理中 {n_processing} 条")
    if parts:
        followup_line = "　".join(parts)

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": (
            f"🎯 **本周仍在跟进 · {n_active} 条**"
            + (f"\n{followup_line}" if followup_line else "")
        ),
    })

    # ── ④ 按钮行 ─────────────────────────────────────────────────────
    elements.append({"tag": "hr"})
    actions = []
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
            "template": "orange",
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
    pc_url      = os.environ.get("REPORT_PC_URL", "")    or os.environ.get("PC_URL", "")
    html_url    = os.environ.get("REPORT_HTML_URL", "")

    if not webhook_url:
        print("❌ 未设置 FEISHU_WEBHOOK_URL 环境变量")
        sys.exit(1)

    # ── 从 Bitable 读取已审核条目，作为唯一数据源 ────────────────────
    from feishu_bitable import fetch_valid_records_from_bitable
    from reporter import _split_three_ways

    try:
        bitable_items = fetch_valid_records_from_bitable(days=7)
        print(f"Bitable 已审核条目: {len(bitable_items)} 条")
    except Exception as e:
        print(f"❌ 获取 Bitable 条目失败: {e}")
        bitable_items = []

    archived, news, active = _split_three_ways(bitable_items)
    print(f"三分区：归档 {len(archived)} 条 / 动态 {len(news)} 条 / 跟进 {len(active)} 条")

    # ── AI 卡片摘要（基于行业动态类条目）────────────────────────────
    ai_summary = ""
    try:
        from translator import generate_weekly_card_summary
        ai_summary = generate_weekly_card_summary(news)
        if ai_summary:
            print(f"AI 摘要生成成功，{len(ai_summary)} 字")
        else:
            print("AI 摘要生成跳过（无 API Key 或无新闻条目）")
    except Exception as e:
        print(f"⚠️  AI 摘要生成失败（跳过）: {e}")

    card = build_card(
        archived, news, active, ai_summary,
        mobile_url=mobile_url, pc_url=pc_url, html_url=html_url,
    )
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
