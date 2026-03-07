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
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 北京/新加坡时间 UTC+8
_TZ_CST = timezone(timedelta(hours=8))

import requests

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

from utils import _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, normalize_status
from classifier import get_source_tier, _is_hardware_noise, _is_google_apple_non_core

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

_TIER_SORT = {"official": 4, "legal": 3, "industry": 2, "news": 1}


def _impact_emoji(score: float) -> str:
    if score >= 9.0:
        return "🔴"
    elif score >= 7.0:
        return "🟠"
    return "🔵"


def _bigram_sim(a: str, b: str) -> float:
    a, b = (a or "").lower(), (b or "").lower()
    if len(a) < 2 or len(b) < 2:
        return 0.0
    bg_a = {a[i:i + 2] for i in range(len(a) - 1)}
    bg_b = {b[i:i + 2] for i in range(len(b) - 1)}
    union = bg_a | bg_b
    return len(bg_a & bg_b) / len(union) if union else 0.0


def _pick_group_items(candidates: list, max_items: int) -> list:
    """Bigram 去重 + 同分类限 1 条，取 max_items 条。"""
    selected: list = []
    cat_count: dict = {}
    for item in candidates:
        cat   = item.get("category_l1", "")
        title = (item.get("title_zh") or item.get("title") or "")
        if any(_bigram_sim(title, (s.get("title_zh") or s.get("title") or "")) > 0.45
               for s in selected):
            continue
        if cat_count.get(cat, 0) >= 1:
            continue
        selected.append(item)
        cat_count[cat] = cat_count.get(cat, 0) + 1
        if len(selected) >= max_items:
            break
    return selected


# ── 数据库查询 ────────────────────────────────────────────────────────

def get_daily_items() -> list:
    """
    查询昨日（北京时间）发布、且在过去 26 小时内新写入 DB 的条目。
    双重过滤确保：
      1. 文章发布日期是昨天或今天（北京时间）
      2. 是本次抓取才新入库的，不是历史旧数据
    噪音门控：impact_score > 0 且实时过滤硬件/非核心 Google-Apple 条目。
    """
    if not DB_PATH.exists():
        print(f"⚠️  数据库不存在: {DB_PATH}")
        return []

    now_cst = datetime.now(_TZ_CST)
    yesterday_str = (now_cst - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str     = now_cst.strftime("%Y-%m-%d")

    from datetime import timezone as _tz
    cutoff_utc = (datetime.now(_tz.utc) - timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")

    print(f"📅 日报筛选：date IN [{yesterday_str}, {today_str}]，created_at >= {cutoff_utc} (UTC)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT title, title_zh, summary_zh, summary, region, status, category_l1,
               source_url, date, created_at,
               COALESCE(impact_score, 1.0) AS impact_score,
               COALESCE(source_name, '')   AS source_name
        FROM legislation
        WHERE date IN (?, ?)
          AND created_at >= ?
          AND COALESCE(impact_score, 1.0) > 0
          AND title_zh IS NOT NULL AND TRIM(title_zh) != ''
        """,
        (yesterday_str, today_str, cutoff_utc),
    ).fetchall()

    conn.close()

    # 实时噪音门控（兜底旧 DB 评分）
    def _is_noise(d: dict) -> bool:
        text = " ".join(filter(None, [d.get("title", ""), d.get("title_zh", ""), d.get("summary", "")]))
        return _is_hardware_noise(text) or _is_google_apple_non_core(text)

    items = [dict(r) for r in rows if not _is_noise(dict(r))]

    # 按 source_tier DESC → impact_score DESC 排序
    for d in items:
        d["_tier"] = _TIER_SORT.get(get_source_tier(d.get("source_name", "")), 1)
    items.sort(key=lambda x: (x["_tier"], float(x.get("impact_score", 1.0))), reverse=True)

    return items


# ── 构建飞书卡片 ──────────────────────────────────────────────────────

_MAX_PER_GROUP = 2   # 日报每区域最多展示条数（比周报更精简）
_MAX_TOTAL     = 8   # 日报全局上限


def build_daily_card(items: list) -> dict:
    now_cst   = datetime.now(_TZ_CST)
    yesterday = now_cst - timedelta(days=1)
    date_range = f"{yesterday.strftime('%Y/%m/%d')} – {now_cst.strftime('%Y/%m/%d %H:%M')} CST"

    # 区域统计（用原始 items，未去重前的总数）
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
    region_line = "　".join(region_parts) if region_parts else "暂无数据"

    # 按区域分组，每组 bigram 去重 + 同分类限 1 条
    raw_grouped: dict = defaultdict(list)
    for item in items:
        raw_grouped[_get_region_group(item.get("region", "其他"))].append(item)
    grouped = {g: _pick_group_items(v, _MAX_PER_GROUP) for g, v in raw_grouped.items()}

    # 组装 elements
    elements: list = []

    # 副标题 + 统计
    elements.append({
        "tag": "markdown",
        "content": (
            f"📅 **今日合规动态** | {date_range}\n\n"
            f"昨日新增 **{len(items)}** 条合规动态\n\n"
            f"**🗺️ 按地区**\n{region_line}"
        ),
    })

    # 分区域展示
    total_shown = 0
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue

        elements.append({"tag": "hr"})
        group_cnt = group_counts.get(group, 0)
        elements.append({
            "tag": "markdown",
            "content": f"**{_GROUP_EMOJI.get(group, '🌐')} {group}** · 今日 {group_cnt} 条",
        })

        for item in group_items:
            if total_shown >= _MAX_TOTAL:
                break

            score   = float(item.get("impact_score", 1.0))
            risk_em = _impact_emoji(score)
            cat     = item.get("category_l1", "")
            cat_em  = CAT_EMOJI.get(cat, "")
            status  = normalize_status(item.get("status", ""))
            region  = item.get("region", "")

            title_zh = (item.get("title_zh") or "").strip()
            url      = item.get("source_url", "")
            title_md = f"[{title_zh}]({url})" if url else title_zh

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

    elements.append({"tag": "hr"})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {
                "tag": "plain_text",
                "content": "📡 Lilith Legal · 每日合规动态",
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
