#!/usr/bin/env python3
"""
每日合规动态检查 - 检查过去 24 小时内新增的立法监管动态
有新增条目则通过飞书机器人推送；无新增则静默退出。

必需环境变量:
    FEISHU_WEBHOOK_URL   飞书自定义机器人的 Webhook 地址

本地调试:
    FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
    python daily_check.py
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 北京/新加坡时间 UTC+8
_TZ_CST = timezone(timedelta(hours=8))

import requests

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

# ── 区域分组（与 reporter.py / feishu_notify.py 保持一致）────────────

_REGION_GROUP_MAP = {
    "东南亚": "东南亚", "越南": "东南亚", "印度尼西亚": "东南亚",
    "泰国": "东南亚", "菲律宾": "东南亚", "马来西亚": "东南亚", "新加坡": "东南亚",
    "南亚": "南亚", "印度": "南亚", "巴基斯坦": "南亚", "孟加拉国": "南亚",
    "中东/非洲": "中东", "中东": "中东", "沙特": "中东", "阿联酋": "中东", "土耳其": "中东",
    "欧洲": "欧洲", "欧盟": "欧洲", "英国": "欧洲", "德国": "欧洲",
    "法国": "欧洲", "荷兰": "欧洲", "意大利": "欧洲", "西班牙": "欧洲",
    "北美": "北美", "美国": "北美", "加拿大": "北美",
    "南美": "南美", "巴西": "南美", "墨西哥": "南美", "阿根廷": "南美",
    "日本": "日韩台", "韩国": "日韩台", "港澳台": "日韩台", "台湾": "日韩台",
    "大洋洲": "其他", "澳大利亚": "其他", "全球": "其他", "其他": "其他",
}

_GROUP_ORDER = ["东南亚", "南亚", "中东", "欧洲", "北美", "南美", "日韩台", "其他"]

_GROUP_EMOJI = {
    "东南亚": "🌏", "南亚": "🌏", "中东": "🕌",
    "欧洲": "🌍", "北美": "🌎", "南美": "🌎",
    "日韩台": "🌸", "其他": "🌐",
}

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


def _get_region_group(region: str) -> str:
    if region in _REGION_GROUP_MAP:
        return _REGION_GROUP_MAP[region]
    for key, group in _REGION_GROUP_MAP.items():
        if key in region or region in key:
            return group
    return "其他"


# ── 数据库查询 ────────────────────────────────────────────────────────

def get_daily_items() -> list:
    """
    查询昨日（北京时间）发布、且在过去 26 小时内新写入 DB 的条目。
    双重过滤确保：
      1. 文章发布日期是昨天或今天（北京时间）
      2. 是本次抓取才新入库的，不是历史旧数据
    """
    if not DB_PATH.exists():
        print(f"⚠️  数据库不存在: {DB_PATH}")
        return []

    now_cst = datetime.now(_TZ_CST)
    yesterday_str = (now_cst - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str = now_cst.strftime("%Y-%m-%d")

    # created_at 存储的是 UTC 时间；26 小时确保覆盖时区偏差
    from datetime import timezone as _tz
    cutoff_utc = (datetime.now(_tz.utc) - timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")

    print(f"📅 日报筛选：date IN [{yesterday_str}, {today_str}]，created_at >= {cutoff_utc} (UTC)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT title, summary_zh, summary, region, status, category_l1,
               source_url, date, created_at
        FROM legislation
        WHERE date IN (?, ?)
          AND created_at >= ?
        ORDER BY
          CASE status
            WHEN '执法动态'      THEN 0
            WHEN '已生效'        THEN 1
            WHEN '即将生效'      THEN 2
            WHEN '草案/征求意见'  THEN 3
            WHEN '立法进行中'    THEN 4
            ELSE 5 END,
          impact_score DESC,
          date DESC
        """,
        (yesterday_str, today_str, cutoff_utc),
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ── 构建飞书卡片 ──────────────────────────────────────────────────────

def build_daily_card(items: list) -> dict:
    today = datetime.now(_TZ_CST)
    yesterday = today - timedelta(days=1)
    date_label = f"{yesterday.strftime('%m/%d')} – {today.strftime('%m/%d %H:%M')} CST"

    # 按区域分组统计
    group_counts: dict = {}
    for item in items:
        group = _get_region_group(item.get("region", "其他"))
        group_counts[group] = group_counts.get(group, 0) + 1

    region_parts = []
    for group in _GROUP_ORDER:
        cnt = group_counts.get(group, 0)
        if cnt > 0:
            emoji = _GROUP_EMOJI.get(group, "•")
            region_parts.append(f"{emoji} {group} **{cnt}**")
    region_line = "　".join(region_parts)

    # 条目详情（最多展示 8 条，避免卡片过长）
    display_items = items[:8]
    item_elements = []
    for item in display_items:
        emoji = STATUS_EMOJI.get(item["status"], "•")
        cat_emoji = CAT_EMOJI.get(item["category_l1"], "")
        summary = (item.get("summary_zh") or item.get("summary") or "")[:80]
        if len(summary) >= 80:
            summary += "…"
        title_text = item["title"][:70] + ("…" if len(item["title"]) > 70 else "")
        url = item.get("source_url", "")
        title_md = f"[{title_text}]({url})" if url else title_text

        # 日期格式「YYYY-MM-DD」
        raw_date = item.get("date", "")
        date_tag = f"「{raw_date}」" if raw_date else ""

        item_elements.append({
            "tag": "markdown",
            "content": (
                f"{emoji} **[{item['region']}]** {item['status']} "
                f"· {cat_emoji} {item['category_l1']}\n"
                f"{date_tag} {title_md}\n"
                f"_{summary}_"
            ),
        })

    # 超出条目提示
    extra_note = []
    if len(items) > 8:
        extra_note.append({
            "tag": "markdown",
            "content": f"_… 另有 {len(items) - 8} 条动态，请查看完整 HTML 简报_",
        })

    elements = [
        {
            "tag": "markdown",
            "content": (
                f"昨日新增 **{len(items)}** 条立法 / 执法动态\n"
                f"{region_line}"
            ),
        },
        {"tag": "hr"},
        *item_elements,
        *extra_note,
    ]

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {
                "tag": "plain_text",
                "content": f"📡 Lilith Legal 每日合规动态 · {date_label}",
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
            print("✅ 飞书每日通知发送成功")
        else:
            print(f"⚠️  飞书返回异常: {result}")
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        sys.exit(1)


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        print("❌ 未设置 FEISHU_WEBHOOK_URL 环境变量")
        sys.exit(1)

    items = get_daily_items()
    if not items:
        print("✅ 过去 24 小时内无新增立法监管动态，无需推送")
        sys.exit(0)

    print(f"📡 发现 {len(items)} 条新增动态，发送飞书通知...")
    card = build_daily_card(items)
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
