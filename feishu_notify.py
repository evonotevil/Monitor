#!/usr/bin/env python3
"""
飞书机器人通知 - 每周合规简报卡片
发送内容: 本周统计 + 重点条目 + HTML/PDF 链接按钮

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

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

# ── 状态 emoji 映射 ──────────────────────────────────────────────────
STATUS_EMOJI = {
    "执法动态":     "🔴",
    "已生效":       "🟢",
    "即将生效":     "🟡",
    "草案/征求意见": "🔵",
    "立法进行中":   "🔵",
    "已提案":       "⚪",
    "已修订":       "🟠",
    "已废止":       "⬜",
    "政策信号":     "⚪",
}

CAT_EMOJI = {
    "数据隐私":    "🔒",
    "玩法合规":    "🎲",
    "未成年人保护": "🧒",
    "广告营销合规": "📣",
    "消费者保护":  "🛡️",
    "经营合规":    "🏢",
    "平台政策":    "📱",
    "内容监管":    "📋",
}


# ── 数据库查询 ────────────────────────────────────────────────────────

def get_weekly_data():
    if not DB_PATH.exists():
        print(f"⚠️  数据库不存在: {DB_PATH}")
        return 0, [], []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    total = conn.execute(
        "SELECT COUNT(*) FROM legislation WHERE date >= ?", (week_ago,)
    ).fetchone()[0]

    by_cat = conn.execute(
        """SELECT category_l1, COUNT(*) AS cnt
           FROM legislation WHERE date >= ?
           GROUP BY category_l1 ORDER BY cnt DESC""",
        (week_ago,),
    ).fetchall()

    # 本周重点：执法/已生效优先，最多 4 条
    highlights = conn.execute(
        """SELECT title, summary_zh, region, status, category_l1, source_url, date
           FROM legislation WHERE date >= ?
           ORDER BY
             CASE status
               WHEN '执法动态'      THEN 0
               WHEN '已生效'        THEN 1
               WHEN '即将生效'      THEN 2
               WHEN '草案/征求意见'  THEN 3
               WHEN '立法进行中'    THEN 4
               ELSE 5 END,
             impact_score DESC
           LIMIT 4""",
        (week_ago,),
    ).fetchall()

    conn.close()
    return total, [dict(r) for r in by_cat], [dict(r) for r in highlights]


# ── 构建飞书卡片 ──────────────────────────────────────────────────────

def build_card(total, by_cat, highlights, html_url, pdf_url):
    today    = datetime.now()
    week_ago = today - timedelta(days=7)
    date_range = f"{week_ago.strftime('%Y/%m/%d')} – {today.strftime('%m/%d')}"

    # 分类统计行
    cat_parts = [
        f"{CAT_EMOJI.get(r['category_l1'], '•')} {r['category_l1']} **{r['cnt']}**"
        for r in by_cat
    ]
    cat_line = "　".join(cat_parts)  # 使用全角空格分隔，更紧凑

    # 重点条目 elements
    hl_elements = []
    for item in highlights:
        emoji   = STATUS_EMOJI.get(item["status"], "•")
        summary = (item.get("summary_zh") or item.get("title", ""))[:80]
        if len(summary) >= 80:
            summary += "…"
        title_text = item["title"][:65] + ("…" if len(item["title"]) > 65 else "")
        url = item.get("source_url", "")
        title_md = f"[{title_text}]({url})" if url else title_text

        hl_elements.append({
            "tag": "markdown",
            "content": (
                f"{emoji} **[{item['region']}]** {item['status']} "
                f"· {CAT_EMOJI.get(item['category_l1'], '')} {item['category_l1']}\n"
                f"{title_md}\n"
                f"_{summary}_"
            ),
        })

    # 组装 elements
    elements = [
        {
            "tag": "markdown",
            "content": f"本周共监测到 **{total}** 条立法 / 执法动态\n{cat_line}",
        },
        {"tag": "hr"},
        {"tag": "markdown", "content": "**📌 本周重点**"},
        *hl_elements,
        {"tag": "hr"},
    ]

    # 操作按钮
    actions = []
    if html_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "🌐 查看 HTML 简报"},
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
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": f"🌍 全球游戏合规周报 · {date_range}",
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
        # 飞书成功返回 {"code": 0, "msg": "success", ...}
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

    total, by_cat, highlights = get_weekly_data()
    print(f"本周数据: {total} 条, 重点 {len(highlights)} 条")

    card = build_card(total, by_cat, highlights, html_url, pdf_url)
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
