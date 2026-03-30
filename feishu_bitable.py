#!/usr/bin/env python3
"""
飞书多维表格写入模块

将每日新增合规动态写入飞书多维表格（Bitable）。
已写入的条目通过本地 JSON 文件去重，避免重复写入。

支持两种多维表格形式：
  1. 独立多维表格：URL 形如 /base/BmXXXX，直接填 FEISHU_BITABLE_APP_TOKEN
  2. 知识库（Wiki）中的多维表格：URL 形如 /wiki/JkHXXXX，填 FEISHU_BITABLE_WIKI_TOKEN，
     代码会自动调用 Wiki API 解析出实际 app_token。

必需环境变量:
    FEISHU_APP_ID                飞书自建应用 App ID
    FEISHU_APP_SECRET            飞书自建应用 App Secret
    FEISHU_BITABLE_TABLE_ID      表格 URL 中的 table_id（tblXXXXX 部分）

以下两个二选一（知识库形式用 WIKI_TOKEN，独立多维表格用 APP_TOKEN）:
    FEISHU_BITABLE_WIKI_TOKEN    知识库页面 token（wiki URL 中 /wiki/ 后面那段）
    FEISHU_BITABLE_APP_TOKEN     独立多维表格 app_token（base URL 中 /base/ 后面那段）

本地调试（知识库形式）:
    FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx \
    FEISHU_BITABLE_WIKI_TOKEN=JkHXXX FEISHU_BITABLE_TABLE_ID=tblXXX \
    python feishu_bitable.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import requests

from utils import _get_region_group
from feishu_client import get_tenant_access_token

# 将内部分组名映射到多维表格单选选项名（9 大分组，内部名与 Bitable 显示名一致）
_BITABLE_REGION_LABEL = {
    "北美":   "北美",
    "欧洲":   "欧洲",
    "日韩":   "日韩",
    "港澳台": "港澳台",
    "东南亚": "东南亚",
    "中东":   "中东",
    "南美":   "南美",
    "大洋洲": "大洋洲",
    "其他":   "其他",
}

# ── 本地去重文件（记录已写入的 source_url，最多保留 20000 条）────────────
_SYNCED_FILE = Path(__file__).parent / "data" / "bitable_synced_urls.json"
_MAX_SYNCED  = 20000

# ── 飞书 API ──────────────────────────────────────────────────────────
_WIKI_NODE_URL = "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node"
_BATCH_URL = (
    "https://open.feishu.cn/open-apis/bitable/v1/apps"
    "/{app_token}/tables/{table_id}/records/batch_create"
)
_BATCH_SIZE = 500  # 飞书 Bitable API 单次最多 500 条


# ── 去重工具 ──────────────────────────────────────────────────────────

def _load_synced_urls() -> set:
    if _SYNCED_FILE.exists():
        try:
            return set(json.loads(_SYNCED_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_synced_urls(urls: set) -> None:
    _SYNCED_FILE.parent.mkdir(parents=True, exist_ok=True)
    # 若超过上限，只保留最后 _MAX_SYNCED 条（list 保序）
    url_list = list(urls)
    if len(url_list) > _MAX_SYNCED:
        url_list = url_list[-_MAX_SYNCED:]
    _SYNCED_FILE.write_text(
        json.dumps(url_list, ensure_ascii=False), encoding="utf-8"
    )


# ── Wiki 解析 ────────────────────────────────────────────────────────

def resolve_wiki_app_token(wiki_token: str, access_token: str) -> str:
    """
    将知识库（Wiki）页面 token 解析为多维表格的实际 app_token。
    知识库中的多维表格 URL：/wiki/JkHXXX → 需调用 Wiki API 获取 obj_token。
    """
    resp = requests.get(
        _WIKI_NODE_URL,
        params={"token": wiki_token},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    # 先读取响应体，再判断状态码，确保能看到飞书的具体错误信息
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        raise

    if resp.status_code != 200 or data.get("code") != 0:
        raise RuntimeError(
            f"Wiki 节点解析失败: HTTP {resp.status_code}, "
            f"code={data.get('code')}, msg={data.get('msg')}, "
            f"完整响应={data}"
        )

    node = data.get("data", {}).get("node", {})
    obj_type  = node.get("obj_type", "")
    obj_token = node.get("obj_token", "")

    print(f"   节点类型: {obj_type}, obj_token: {obj_token}")

    if obj_type != "bitable":
        raise RuntimeError(
            f"Wiki 节点类型为 '{obj_type}'，不是多维表格（bitable），"
            f"请确认打开的是正确的知识库页面"
        )
    if not obj_token:
        raise RuntimeError(f"obj_token 为空，完整节点信息: {node}")
    return obj_token


# ── 字段转换 ──────────────────────────────────────────────────────────

def _date_to_ms(date_str: str) -> Optional[int]:
    """将 YYYY-MM-DD 字符串转为毫秒时间戳（飞书日期字段要求）。"""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def _build_record(item: dict) -> dict:
    """将一条 LegislationItem dict 转为飞书多维表格 record 格式。"""
    title   = (item.get("title_zh") or item.get("title") or "").strip()
    summary = (item.get("summary_zh") or item.get("summary") or "").strip()
    url     = (item.get("source_url") or "").strip()
    region  = (item.get("region") or "").strip()
    cat     = (item.get("category_l1") or "").strip()
    source  = (item.get("source_name") or "").strip()

    fields: dict = {
        "动态标题":   title,
        "摘要":       summary,
        "处理状态":   "🤖 待初筛",
    }

    if region:
        group = _get_region_group(region)
        fields["国家/地区"] = _BITABLE_REGION_LABEL.get(group, "其他")

    # 合规类别为多选字段，API 需传列表
    if cat:
        fields["合规类别"] = [cat]

    if source:
        fields["信源名称"] = source

    # 超链接字段
    if url:
        fields["原始链接"] = {"text": title or url, "link": url}

    # 日期字段（毫秒时间戳）
    date_ms = _date_to_ms(item.get("date", ""))
    if date_ms:
        fields["发布日期"] = date_ms

    # LLM 四维风险评估（数值字段，Bitable 表需手动添加对应数字列）
    if item.get("risk_source") == "llm":
        fields["营收影响"]   = item.get("risk_revenue", 0)
        fields["产品改动"]   = item.get("risk_product", 0)
        fields["时间紧迫性"] = item.get("risk_urgency", 0)
        fields["影响范围"]   = item.get("risk_scope", 0)

    return {"fields": fields}


# ── 批量写入 ──────────────────────────────────────────────────────────

def write_to_bitable(
    items: List[dict],
    app_token: str,
    table_id: str,
    access_token: str,
) -> int:
    """
    批量写入条目到飞书多维表格。
    返回成功写入的条数。
    """
    if not items:
        return 0

    url = _BATCH_URL.format(app_token=app_token, table_id=table_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    written = 0
    for i in range(0, len(items), _BATCH_SIZE):
        batch   = items[i : i + _BATCH_SIZE]
        records = [_build_record(item) for item in batch]

        resp = requests.post(
            url,
            headers=headers,
            json={"records": records},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print(
                f"⚠️  多维表格写入失败 (batch {i // _BATCH_SIZE + 1}): "
                f"code={data.get('code')} msg={data.get('msg')}"
            )
            continue

        written += len(data.get("data", {}).get("records", []))

    return written


# ── 对外接口 ──────────────────────────────────────────────────────────

def sync_items_to_bitable(items: List[dict]) -> None:
    """
    从环境变量读取凭证，将 items 写入飞书多维表格。

    - 支持知识库（Wiki）和独立多维表格两种形式，自动判断。
    - 自动去重：已写入的 source_url 不再重复写入。
    - 任何凭证缺失或 API 错误均不阻断主流程（只打印警告）。
    """
    app_id      = os.environ.get("FEISHU_APP_ID", "")
    app_secret  = os.environ.get("FEISHU_APP_SECRET", "")
    wiki_token  = os.environ.get("FEISHU_BITABLE_WIKI_TOKEN", "")
    app_token   = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")
    table_id    = os.environ.get("FEISHU_BITABLE_TABLE_ID", "")

    # 必须有：app_id、app_secret、table_id，以及 wiki_token 或 app_token 其中一个
    if not all([app_id, app_secret, table_id]) or not (wiki_token or app_token):
        print(
            "⏭️  未配置飞书多维表格凭证（需要 FEISHU_APP_ID、FEISHU_APP_SECRET、"
            "FEISHU_BITABLE_TABLE_ID，以及 FEISHU_BITABLE_WIKI_TOKEN 或 "
            "FEISHU_BITABLE_APP_TOKEN），跳过写入"
        )
        return

    if not items:
        return

    # 去重过滤
    synced_urls = _load_synced_urls()
    new_items   = [i for i in items if i.get("source_url") not in synced_urls]

    if not new_items:
        print("⏭️  所有条目已写入多维表格，无需重复写入")
        return

    print(f"📋 待写入多维表格：{len(new_items)} 条（已去重 {len(items) - len(new_items)} 条）")

    try:
        token = get_tenant_access_token(app_id, app_secret)

        # 知识库形式：调用 Wiki Node API 解析出实际 app_token
        if wiki_token:
            print(f"🔍 通过 Wiki Node API 解析 app_token ...")
            app_token = resolve_wiki_app_token(wiki_token, token)
            print(f"   解析成功，app_token: {app_token[:8]}...")

        written = write_to_bitable(new_items, app_token, table_id, token)
        print(f"✅ 飞书多维表格写入成功：{written} 条")

        # 只有实际写入成功才更新去重记录
        if written > 0:
            for item in new_items:
                url = item.get("source_url")
                if url:
                    synced_urls.add(url)
            _save_synced_urls(synced_urls)

    except Exception as e:
        print(f"⚠️  飞书多维表格写入失败（不阻断主流程）: {e}")


# ── 从多维表格读取数据（SSOT 链路）────────────────────────────────────

_LIST_URL = (
    "https://open.feishu.cn/open-apis/bitable/v1/apps"
    "/{app_token}/tables/{table_id}/records"
)

# 过滤掉这两种状态：待初筛 = 未人工确认，噪音 = 明确不推送
_EXCLUDE_STATUSES = {"🤖 待初筛", "🗑️ 噪音/不推送"}


def _ms_to_date(ms) -> str:
    """将飞书日期字段的毫秒时间戳转为 YYYY-MM-DD 字符串。"""
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _map_bitable_record(
    fields: dict,
    record_id: str = "",
    bitable_url: str = "",
) -> dict:
    """
    将飞书多维表格字段值映射为 reporter.py 所需的条目字典格式。

    字段格式说明：
    - 合规类别  ：多选数组 ["数据隐私", ...]  → 取第一项
    - 原始链接  ：超链接对象 {"text": ..., "link": "https://..."} → 取 link
    - 发布日期  ：毫秒时间戳 → YYYY-MM-DD
    - 归档日期  ：毫秒时间戳 → YYYY-MM-DD（由飞书自动化在拖入归档时写入）
    - 国家/地区 ：单选字符串，已是分组标签（北美/欧洲/日韩/港澳台/东南亚/中东/南美/大洋洲/其他）
    - 💡 核心结论：若存在则优先作为 summary_zh；否则使用「摘要」字段
    - 专项合规文档：超链接字段，仅归档条目展示
    """
    # ── 合规类别（多选字段）────────────────────────────────────────────
    cat_raw  = fields.get("合规类别", "")
    category = cat_raw[0] if isinstance(cat_raw, list) and cat_raw else str(cat_raw or "")

    # ── 原始链接（超链接字段）──────────────────────────────────────────
    link_raw   = fields.get("原始链接", "")
    if isinstance(link_raw, dict):
        source_url = link_raw.get("link") or link_raw.get("url") or link_raw.get("text", "")
    else:
        source_url = str(link_raw) if link_raw else ""

    # ── 发布日期（毫秒时间戳）──────────────────────────────────────────
    date_raw = fields.get("发布日期")
    date_str = _ms_to_date(date_raw) if isinstance(date_raw, (int, float)) else str(date_raw or "")

    # ── 归档日期（毫秒时间戳，由飞书自动化写入）────────────────────────
    archive_date_raw = fields.get("归档日期")
    archive_date = (
        _ms_to_date(archive_date_raw)
        if isinstance(archive_date_raw, (int, float))
        else str(archive_date_raw or "")
    )

    # ── 摘要：优先「💡 核心结论」，否则「摘要」──────────────────────────
    core     = str(fields.get("💡 核心结论") or "").strip()
    abstract = str(fields.get("摘要") or "").strip()
    summary_zh = core if core else abstract

    # ── 国家/地区：直接传 Bitable 显示标签，_get_region_group() 已可识别所有分组名 ──
    region = str(fields.get("国家/地区") or "其他")

    # ── 工作流状态（供 reporter 三分区）────────────────────────────────
    bitable_status = str(fields.get("处理状态") or "").strip()

    # ── 跟进 BP（可能为人员字段 list，也可能为文本）─────────────────────
    bp_raw = fields.get("跟进BP") or fields.get("跟进人") or ""
    if isinstance(bp_raw, list):
        assignee = "、".join(
            (p.get("name") or p.get("cn_name") or "")
            for p in bp_raw if isinstance(p, dict)
        ).strip()
    else:
        assignee = str(bp_raw).strip()

    # ── 协助 BP（协同支持的 BP，人员字段 list 或文本）───────────────────
    co_bp_raw = fields.get("协助BP") or ""
    if isinstance(co_bp_raw, list):
        co_assignee = "、".join(
            (p.get("name") or p.get("cn_name") or "")
            for p in co_bp_raw if isinstance(p, dict)
        ).strip()
    else:
        co_assignee = str(co_bp_raw).strip()

    # ── 法务结论（独立于「摘要」和「💡 核心结论」）──────────────────────
    legal_conclusion = str(fields.get("法务结论") or fields.get("💡 法务结论") or "").strip()

    # ── 专项合规文档（超链接字段，仅归档条目展示）──────────────────────
    doc_raw = fields.get("专项合规文档", "")
    if isinstance(doc_raw, dict):
        doc_url  = doc_raw.get("link") or doc_raw.get("url") or ""
        doc_text = doc_raw.get("text") or "专项合规文档"
    else:
        doc_url  = str(doc_raw).strip() if doc_raw else ""
        doc_text = "专项合规文档" if doc_url else ""

    return {
        "title":            "",             # Bitable 无原文标题字段（英文）
        "title_zh":         str(fields.get("动态标题") or "").strip(),
        "summary_zh":       summary_zh,
        "summary":          "",
        "region":           region,
        "status":           "",             # 法规生命周期状态（Bitable 未单独维护，留空）
        "bitable_status":   bitable_status, # 工作流状态：用于三分区
        "assignee":         assignee,       # 跟进 BP
        "co_assignee":      co_assignee,    # 协助 BP
        "legal_conclusion": legal_conclusion,
        "category_l1":      category,
        "source_url":       source_url,
        "date":             date_str,
        "archive_date":     archive_date,   # 归档日期（用于归档条目的时间窗口过滤）
        "record_id":        record_id,      # Bitable 记录 ID
        "bitable_url":      bitable_url,    # Bitable 记录深链（跳转到卡片按钮）
        "doc_url":          doc_url,        # 专项合规文档链接
        "doc_text":         doc_text,       # 专项合规文档显示名
        "impact_score":     5.0,            # 人工筛选后统一中等优先级，reporter 仍可正常排序
        "source_name":      str(fields.get("信源名称") or "").strip(),
    }


def fetch_valid_records_from_bitable(days: Optional[int] = None) -> List[dict]:
    """
    从飞书多维表格拉取所有经人工初筛的有效记录，供 reporter.py 生成 HTML 报告。

    过滤条件：「处理状态」不等于「🤖 待初筛」且不等于「🗑️ 噪音/不推送」。
    自动处理分页（page_size=500），直到拉取完所有数据。

    参数：
        days: 可选，仅返回最近 N 天内的记录（按「发布日期」过滤）。
              None 表示返回全部有效记录。

    返回：
        reporter.py 所需的 dict 列表（与 db.query_items() 格式相同）。
        若凭证未配置或 API 失败，返回空列表并打印错误。

    ⚠️  只读接口，不修改任何数据。写入链路（sync_items_to_bitable）保持不变。
    """
    app_id     = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    wiki_token = os.environ.get("FEISHU_BITABLE_WIKI_TOKEN", "")
    app_token  = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")
    table_id   = os.environ.get("FEISHU_BITABLE_TABLE_ID", "")

    if not all([app_id, app_secret, table_id]) or not (wiki_token or app_token):
        print(
            "⏭️  未配置飞书多维表格凭证（FEISHU_APP_ID / FEISHU_APP_SECRET / "
            "FEISHU_BITABLE_TABLE_ID / WIKI_TOKEN 或 APP_TOKEN），跳过从 Bitable 读取"
        )
        return []

    try:
        token = get_tenant_access_token(app_id, app_secret)

        if wiki_token:
            print("🔍 通过 Wiki Node API 解析 app_token …")
            app_token = resolve_wiki_app_token(wiki_token, token)
            print(f"   解析成功，app_token: {app_token[:8]}…")

        list_url = _LIST_URL.format(app_token=app_token, table_id=table_id)
        headers  = {"Authorization": f"Bearer {token}"}
        # 拼接 Bitable 记录深链前缀（跳转到卡片按钮用）
        bitable_record_base = f"https://feishu.cn/base/{app_token}?table={table_id}&record="

        # ── 分页拉取全量记录 ────────────────────────────────────────────
        all_records: list = []
        page_token: Optional[str] = None

        while True:
            params: dict = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(list_url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(
                    f"拉取记录失败: code={data.get('code')} msg={data.get('msg')}"
                )

            batch = data.get("data", {}).get("items", [])
            all_records.extend(batch)
            print(f"   已拉取 {len(all_records)} 条…")

            has_more   = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token")
            if not has_more or not page_token:
                break

        print(f"✅ 飞书多维表格共 {len(all_records)} 条记录，开始过滤…")

        # ── 过滤 + 映射 ─────────────────────────────────────────────────
        # 计算日期下限（若指定了 days）
        date_cutoff = ""
        if days:
            from datetime import timedelta
            date_cutoff = (
                datetime.now(tz=timezone.utc) - timedelta(days=days)
            ).strftime("%Y-%m-%d")

        valid: List[dict] = []
        skipped_status  = 0
        skipped_empty   = 0
        skipped_date    = 0

        for rec in all_records:
            fields    = rec.get("fields", {})
            record_id = rec.get("record_id", "")

            # 过滤工作流状态
            status_val = str(fields.get("处理状态", "")).strip()
            if status_val in _EXCLUDE_STATUSES:
                skipped_status += 1
                continue

            bitable_url = (bitable_record_base + record_id) if record_id else ""
            mapped = _map_bitable_record(fields, record_id=record_id, bitable_url=bitable_url)

            # 过滤空记录（既无标题也无链接）
            if not mapped["title_zh"] and not mapped["source_url"]:
                skipped_empty += 1
                continue

            # 按日期过滤（仅当指定了 days 时）
            # 归档条目用「归档日期」；若归档日期为空则不过滤（无法判断归档时间）
            # 其余条目用「发布日期」
            if date_cutoff:
                if "归档" in status_val:
                    ref_date = mapped["archive_date"]
                    # 归档条目没有归档日期时不过滤，保留供周报展示
                    if not ref_date:
                        ref_date = ""
                else:
                    ref_date = mapped["date"]
                if ref_date and ref_date < date_cutoff:
                    skipped_date += 1
                    continue

            valid.append(mapped)

        print(
            f"✅ 过滤完成：有效 {len(valid)} 条 "
            f"（排除待初筛/噪音 {skipped_status} 条"
            f"{f'、超期 {skipped_date} 条' if skipped_date else ''}"
            f"{f'、空记录 {skipped_empty} 条' if skipped_empty else ''}）"
        )
        return valid

    except Exception as exc:
        print(f"❌ 从飞书多维表格读取失败: {exc}")
        return []


def fetch_noise_source_stats() -> dict:
    """
    从 Bitable 读取所有「🗑️ 噪音/不推送」记录，统计各信源的噪音出现次数。

    返回：{"source_name": count, ...} 按 count 降序排列。
    若凭证未配置或 API 失败，返回空字典。
    """
    app_id     = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    wiki_token = os.environ.get("FEISHU_BITABLE_WIKI_TOKEN", "")
    app_token  = os.environ.get("FEISHU_BITABLE_APP_TOKEN", "")
    table_id   = os.environ.get("FEISHU_BITABLE_TABLE_ID", "")

    if not all([app_id, app_secret, table_id]) or not (wiki_token or app_token):
        print("⏭️  未配置飞书多维表格凭证，跳过噪音统计")
        return {}

    try:
        token = get_tenant_access_token(app_id, app_secret)
        if wiki_token:
            app_token = resolve_wiki_app_token(wiki_token, token)

        list_url = _LIST_URL.format(app_token=app_token, table_id=table_id)
        headers  = {"Authorization": f"Bearer {token}"}

        all_records: list = []
        page_token: Optional[str] = None
        while True:
            params: dict = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            resp = requests.get(list_url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"拉取记录失败: {data.get('msg')}")
            batch = data.get("data", {}).get("items", [])
            all_records.extend(batch)
            has_more   = data.get("data", {}).get("has_more", False)
            page_token = data.get("data", {}).get("page_token")
            if not has_more or not page_token:
                break

        # 只统计被标记为噪音的条目
        counts: dict = {}
        for rec in all_records:
            fields     = rec.get("fields", {})
            status_val = str(fields.get("处理状态", "")).strip()
            if "噪音" not in status_val and "不推送" not in status_val:
                continue
            # 信源名称字段
            source = str(fields.get("信源名称", "")).strip()
            if source:
                counts[source] = counts.get(source, 0) + 1

        # 按次数降序返回
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    except Exception as exc:
        print(f"❌ 获取噪音统计失败: {exc}")
        return {}


# ── 本地测试入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    # 用数据库最新 5 条数据做测试写入
    import sqlite3
    from pathlib import Path as _P

    db = _P(__file__).parent / "data" / "monitor.db"
    if not db.exists():
        print("❌ 数据库不存在，请先运行 monitor.py 抓取数据")
        sys.exit(1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT title, title_zh, summary_zh, summary, region, status, category_l1,
                  source_url, date, impact_score, source_name
           FROM legislation
           WHERE title_zh IS NOT NULL AND TRIM(title_zh) != ''
           ORDER BY impact_score DESC, date DESC LIMIT 5"""
    ).fetchall()
    conn.close()

    test_items = [dict(r) for r in rows]
    print(f"🧪 测试：准备写入 {len(test_items)} 条数据到多维表格")
    sync_items_to_bitable(test_items)
