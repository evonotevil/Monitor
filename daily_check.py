#!/usr/bin/env python3
"""
每日合规动态检查 - 检查过去 24 小时内新增的立法监管动态
有新增条目则通过飞书机器人推送；无新增则静默退出。

必需环境变量:
    FEISHU_WEBHOOK_URL   飞书自定义机器人的 Webhook 地址

可选环境变量:
    LLM_API_KEY          用于生成 AI 综述（未设置时跳过综述）

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

from utils import (
    _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, normalize_status,
    CAT_EMOJI, _TIER_SORT, _impact_emoji, _bigram_sim, _pick_group_items,
)
from classifier import get_source_tier, _is_hardware_noise, _is_google_apple_non_core


# ── 全平台影响简短标签 ────────────────────────────────────────────────
# 按分类给出移动端 / PC 端最关键的合规关注点（一句话）

_MOBILE_SHORT: dict = {
    "数据隐私":        "App/SDK 数据同意流程合规",
    "玩法合规":        "Gacha/Loot Box 概率公示更新",
    "未成年人保护":    "实名/年龄验证 SDK 接入",
    "广告营销合规":    "IDFA 授权 + 广告 SDK 合规",
    "消费者保护":      "IAP 退款条款/订阅自动续费",
    "经营合规":        "App Store/Play 经营资质核查",
    "平台政策":        "IAP 分成及支付规则变动",
    "内容监管":        "移动端内容分级/审核接入",
    "PC & 跨平台合规": "跨端账号数据同步合规",
}

_PC_SHORT: dict = {
    "数据隐私":        "PC SDK/云存储数据合规",
    "玩法合规":        "Steam 概率公示/D2C 合规",
    "未成年人保护":    "PC 端年龄验证实名接入",
    "广告营销合规":    "PC 广告追踪 Cookie 合规",
    "消费者保护":      "D2C 官网退款/订阅条款",
    "经营合规":        "PC 官网经营资质/本地备案",
    "平台政策":        "D2C 充值及 Launcher 策略",
    "内容监管":        "PC 端内容分级证书更新",
    "PC & 跨平台合规": "Launcher 权限/Anti-cheat 合规",
}

_DEFAULT_MOBILE = "App Store/IAP 相关合规排查"
_DEFAULT_PC     = "PC Launcher/D2C 相关合规排查"


def _short_platform_impact(category_l1: str) -> str:
    """返回简洁的全平台合规影响一行文字。"""
    mobile = _MOBILE_SHORT.get(category_l1, _DEFAULT_MOBILE)
    pc     = _PC_SHORT.get(category_l1, _DEFAULT_PC)
    return f"📱 {mobile} | 💻 {pc}"


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

_MAX_PER_GROUP = 2   # 日报每区域最多展示条数
_MAX_TOTAL     = 8   # 日报全局上限


def build_daily_card(items: list, exec_summary: str = "") -> dict:
    now_cst   = datetime.now(_TZ_CST)
    yesterday = now_cst - timedelta(days=1)
    yesterday_date = yesterday.strftime("%Y-%m-%d")

    # Header 颜色：按最高 impact_score 分级
    max_score = max((float(i.get("impact_score", 1.0)) for i in items), default=0.0)
    if max_score >= 9.0:
        header_color = "red"
    elif max_score >= 7.0:
        header_color = "orange"
    else:
        header_color = "blue"

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

    # 统计概览
    elements.append({
        "tag": "markdown",
        "content": (
            f"昨日新增 **{len(items)}** 条合规动态　**{yesterday_date}**\n\n"
            f"**🗺️ 按地区**　{region_line}"
        ),
    })

    # AI 综述（有则展示为引用块）
    if exec_summary:
        elements.append({
            "tag": "markdown",
            "content": "\n".join(f"> {line}" for line in exec_summary.splitlines()),
        })

    elements.append({"tag": "hr"})

    # 分区域展示动态列表
    total_shown = 0
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue

        group_cnt = group_counts.get(group, 0)
        elements.append({
            "tag": "markdown",
            "content": f"**{_GROUP_EMOJI.get(group, '🌐')} {group}** · 今日 {group_cnt} 条",
        })

        for item in group_items:
            if total_shown >= _MAX_TOTAL:
                break

            score    = float(item.get("impact_score", 1.0))
            risk_em  = _impact_emoji(score)
            cat      = item.get("category_l1", "")
            cat_em   = CAT_EMOJI.get(cat, "")
            status   = normalize_status(item.get("status", ""))
            region   = item.get("region", "")

            title_zh = (item.get("title_zh") or "").strip()
            url      = item.get("source_url", "")
            title_md = f"[{title_zh}]({url})" if url else title_zh

            # 机制变动：从 summary_zh 提取前 55 字（已含监管核心要求）
            summary_zh = (item.get("summary_zh") or item.get("summary") or "").strip()
            mechanism  = summary_zh[:55] + "…" if len(summary_zh) > 55 else summary_zh

            # 全平台影响：分类驱动的简洁一行
            platform_impact = _short_platform_impact(cat)

            date_tag = item.get("date", "")

            elements.append({
                "tag": "markdown",
                "content": (
                    f"{risk_em} **[{region}]** {status} · {cat_em} {cat}\n"
                    f"{title_md}\n"
                    f"🔧 **机制变动**：{mechanism}\n"
                    f"🌐 **全平台影响**：{platform_impact}\n"
                    f"「{date_tag}」"
                ),
            })
            total_shown += 1

        elements.append({"tag": "hr"})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": header_color,
            "title": {
                "tag": "plain_text",
                "content": f"📅 [日报] 全球游戏合规动态 ({yesterday_date})",
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

    # AI 综述（150 字以内，失败不阻断）
    exec_summary = ""
    try:
        from translator import generate_daily_summary
        exec_summary = generate_daily_summary(items)
        if exec_summary:
            print(f"📝 日报综述生成成功，{len(exec_summary)} 字")
        else:
            print("📝 日报综述跳过（无 API Key 或调用失败）")
    except Exception as e:
        print(f"⚠️  综述生成失败（将跳过）: {e}")

    card = build_daily_card(items, exec_summary=exec_summary)
    send_card(webhook_url, card)


if __name__ == "__main__":
    main()
