#!/usr/bin/env python3
"""
每日合规动态检查 - 检查过去 24 小时内新增的立法监管动态
有新增条目则通过飞书应用机器人推送；无新增则静默退出。

必需环境变量:
    FEISHU_APP_ID                飞书自建应用 App ID
    FEISHU_APP_SECRET            飞书自建应用 App Secret
    FEISHU_CHAT_ID               目标群聊的 chat_id（消息推送用）

可选环境变量:
    LLM_API_KEY                  用于生成 AI 综述（未设置时跳过综述）
    FEISHU_BITABLE_APP_TOKEN     多维表格 app_token（多维表格写入）
    FEISHU_BITABLE_TABLE_ID      多维表格 table_id（多维表格写入）

本地调试:
    FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx \
    FEISHU_CHAT_ID=oc_xxx \
    python daily_check.py
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 北京/新加坡时间 UTC+8
_TZ_CST = timezone(timedelta(hours=8))

DB_PATH = Path(__file__).parent / "data" / "monitor.db"

from utils import (
    _GROUP_ORDER, _GROUP_EMOJI, _get_region_group, normalize_status,
    _TIER_SORT, _impact_emoji, _bigram_sim, _pick_group_items,
)
from feishu_client import send_card
from classifier import get_source_tier, _is_hardware_noise, _is_google_apple_non_core


# ── 机器人推送去重（记录已推送的 source_url，避免跨天重复推送）────────────
_PUSHED_FILE = Path(__file__).parent / "data" / "daily_pushed_urls.json"
_MAX_PUSHED  = 5000  # 保留上限，防止文件无限增长


def _load_pushed_urls() -> set:
    if _PUSHED_FILE.exists():
        try:
            return set(json.loads(_PUSHED_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_pushed_urls(urls: set) -> None:
    _PUSHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    url_list = list(urls)
    if len(url_list) > _MAX_PUSHED:
        url_list = url_list[-_MAX_PUSHED:]
    _PUSHED_FILE.write_text(
        json.dumps(url_list, ensure_ascii=False), encoding="utf-8"
    )


def _smart_truncate(text: str, max_len: int = 100) -> str:
    """在句号/分号/逗号处智能截断，避免在词语中间切断。"""
    if len(text) <= max_len:
        return text
    # 在 max_len 范围内找最后一个断句符
    chunk = text[:max_len]
    for sep in ("。", "；", "；", "，", ",", "、", ". ", "; "):
        pos = chunk.rfind(sep)
        if pos >= max_len // 2:  # 至少保留一半长度
            return chunk[:pos + len(sep)].rstrip() + "…"
    # 没找到合适断句符，硬切
    return chunk.rstrip() + "…"


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
    today_str = now_cst.strftime("%Y-%m-%d")

    # 周一覆盖周六+周日+周一（74h），其余工作日只覆盖昨天（26h）
    is_monday = now_cst.weekday() == 0
    lookback_days = 3 if is_monday else 1
    lookback_hours = 74 if is_monday else 26

    date_list = [
        (now_cst - timedelta(days=d)).strftime("%Y-%m-%d")
        for d in range(lookback_days + 1)  # 含今天
    ]

    cutoff_utc = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d %H:%M:%S")

    date_range_label = f"{date_list[-1]} ~ {date_list[0]}" if is_monday else f"{date_list[-1]}, {date_list[0]}"
    print(f"📅 日报筛选：date IN [{date_range_label}]，created_at >= {cutoff_utc} (UTC)"
          + (" (周一含周末)" if is_monday else ""))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    placeholders = ",".join("?" for _ in date_list)
    rows = conn.execute(
        f"""
        SELECT title, title_zh, summary_zh, summary, region, status, category_l1,
               source_url, date, created_at,
               COALESCE(impact_score, 1.0) AS impact_score,
               COALESCE(source_name, '')   AS source_name,
               COALESCE(risk_revenue, 0)   AS risk_revenue,
               COALESCE(risk_product, 0)   AS risk_product,
               COALESCE(risk_urgency, 0)   AS risk_urgency,
               COALESCE(risk_scope, 0)     AS risk_scope,
               COALESCE(risk_source, 'regex') AS risk_source
        FROM legislation
        WHERE date IN ({placeholders})
          AND created_at >= ?
          AND COALESCE(impact_score, 1.0) > 0
          AND title_zh IS NOT NULL AND TRIM(title_zh) != ''
        """,
        (*date_list, cutoff_utc),
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

_MAX_PER_GROUP = int(os.environ.get("DAILY_MAX_PER_GROUP", "3"))   # 日报每区域最多展示条数
_MAX_TOTAL     = int(os.environ.get("DAILY_MAX_ITEMS", "12"))     # 日报全局上限


def build_daily_card(items: list, exec_summary: str = "", is_monday: bool = False) -> dict:
    now_cst   = datetime.now(_TZ_CST)
    yesterday = now_cst - timedelta(days=1)

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

    # 全局跨区域去重：同一事件被多家媒体报道时，保留信源最权威的那条
    # 优先级：official(4) > legal(3) > industry(2) > news(1)，同级比 impact_score
    deduped: list = []
    for item in items:
        title = (item.get("title_zh") or item.get("title") or "")
        tier  = _TIER_SORT.get(get_source_tier(item.get("source_name", "")), 1)
        score = float(item.get("impact_score", 1.0))
        is_dup = False
        for j, kept in enumerate(deduped):
            kept_title = (kept.get("title_zh") or kept.get("title") or "")
            if _bigram_sim(title, kept_title) > 0.45:
                # 保留更权威的：先比 tier，再比 score
                kept_tier  = _TIER_SORT.get(get_source_tier(kept.get("source_name", "")), 1)
                kept_score = float(kept.get("impact_score", 1.0))
                if (tier, score) > (kept_tier, kept_score):
                    deduped[j] = item  # 替换为更权威的
                is_dup = True
                break
        if not is_dup:
            deduped.append(item)

    # 按区域分组，每组 bigram 去重 + 同分类限 1 条
    raw_grouped: dict = defaultdict(list)
    for item in deduped:
        raw_grouped[_get_region_group(item.get("region", "其他"))].append(item)
    grouped = {g: _pick_group_items(v, _MAX_PER_GROUP) for g, v in raw_grouped.items()}

    # 组装 elements
    elements: list = []

    # 统计概览
    if is_monday:
        saturday = (now_cst - timedelta(days=2)).strftime("%Y-%m-%d")
        date_label = f"{saturday} ~ {yesterday.strftime('%Y-%m-%d')}"
        count_label = f"周末至今新增 **{len(items)}** 条合规动态"
    else:
        date_label = yesterday.strftime("%Y-%m-%d")
        count_label = f"昨日新增 **{len(items)}** 条合规动态"

    elements.append({
        "tag": "markdown",
        "content": (
            f"{count_label}　{date_label}\n"
            f"{region_line}"
        ),
    })

    # AI 综述（有则展示为引用块；跳过空行避免飞书渲染孤立 >）
    if exec_summary:
        quoted_lines = [
            f"> {line}" for line in exec_summary.splitlines() if line.strip()
        ]
        elements.append({
            "tag": "markdown",
            "content": "\n".join(quoted_lines),
        })

    elements.append({"tag": "hr"})

    # 分区域展示动态列表
    total_shown = 0
    for group in _GROUP_ORDER:
        group_items = grouped.get(group, [])
        if not group_items:
            continue

        group_cnt  = group_counts.get(group, 0)
        shown_cnt  = len(group_items)
        count_text = f"{group_cnt} 条（展示 {shown_cnt} 条）" if shown_cnt < group_cnt else f"{group_cnt} 条"
        elements.append({
            "tag": "markdown",
            "content": f"**{_GROUP_EMOJI.get(group, '🌐')} {group}** · 昨日 {count_text}",
        })

        for item in group_items:
            if total_shown >= _MAX_TOTAL:
                break

            score    = float(item.get("impact_score", 1.0))
            risk_em  = _impact_emoji(score)
            cat      = item.get("category_l1", "")
            status   = normalize_status(item.get("status", ""))
            region   = item.get("region", "")

            title_zh = (item.get("title_zh") or "").strip()
            url      = item.get("source_url", "")
            title_md = f"[{title_zh}]({url})" if url else title_zh

            summary_zh = (item.get("summary_zh") or item.get("summary") or "").strip()
            mechanism  = _smart_truncate(summary_zh, 100)

            elements.append({
                "tag": "markdown",
                "content": (
                    f"{risk_em} **{status}** · {region} · {cat}\n"
                    f"{title_md}\n"
                    f"机制变动：{mechanism}"
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
                "content": f"📅 [日报] 全球游戏合规动态 ({date_label})",
            },
        },
        "elements": elements,
    }


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    if not chat_id:
        print("❌ 未设置 FEISHU_CHAT_ID 环境变量")
        sys.exit(1)

    now_cst = datetime.now(_TZ_CST)
    weekday = now_cst.weekday()  # 0=周一, 6=周日
    is_monday = weekday == 0

    items = get_daily_items()

    # ── 写入飞书多维表格（每天写入，包含周末，有数据才写）────────────────
    if items:
        from feishu_bitable import sync_items_to_bitable
        sync_items_to_bitable(items)

    # ── 飞书机器人推送（仅工作日：周一至周五）─────────────────────────
    if weekday >= 5:
        print(f"📅 今天是{'周六' if weekday == 5 else '周日'}，跳过飞书机器人推送")
        return

    # ── 机器人推送去重：过滤已推送过的条目 ────────────────────────────
    pushed_urls = _load_pushed_urls()
    push_items = [i for i in items if i.get("source_url") not in pushed_urls]

    if push_items:
        print(f"📡 机器人推送去重：{len(items)} 条中 {len(items) - len(push_items)} 条已推送，本次推送 {len(push_items)} 条")

    if not push_items:
        # 无新增动态也推送一张简洁卡片，让团队知道系统正常运行
        print("✅ 无新增动态（或均已推送），推送'今日无新增'卡片")
        yesterday = now_cst - timedelta(days=1)
        if is_monday:
            date_label = f"{(now_cst - timedelta(days=2)).strftime('%Y-%m-%d')} ~ {yesterday.strftime('%Y-%m-%d')}"
            no_update_text = "周末至今无新增合规动态"
        else:
            date_label = yesterday.strftime("%Y-%m-%d")
            no_update_text = "昨日无新增合规动态"
        empty_card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green",
                "title": {"tag": "plain_text", "content": f"📅 [日报] 全球游戏合规动态 ({date_label})"},
            },
            "elements": [
                {"tag": "markdown", "content": f"✅ {no_update_text}"},
            ],
        }
        send_card(chat_id, empty_card)
        return

    print(f"📡 发现 {len(push_items)} 条新增动态，发送飞书通知...")

    # AI 综述（150 字以内，失败不阻断）
    exec_summary = ""
    try:
        from translator import generate_daily_summary
        exec_summary = generate_daily_summary(push_items)
        if exec_summary:
            print(f"📝 日报综述生成成功，{len(exec_summary)} 字")
        else:
            print("📝 日报综述跳过（无 API Key 或调用失败）")
    except Exception as e:
        print(f"⚠️  综述生成失败（将跳过）: {e}")

    card = build_daily_card(push_items, exec_summary=exec_summary, is_monday=is_monday)
    send_card(chat_id, card)

    # 推送成功后记录已推送的 URL
    for item in push_items:
        url = item.get("source_url")
        if url:
            pushed_urls.add(url)
    _save_pushed_urls(pushed_urls)


if __name__ == "__main__":
    main()
