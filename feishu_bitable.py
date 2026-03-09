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

# ── 本地去重文件（记录已写入的 source_url，最多保留 5000 条）─────────────
_SYNCED_FILE = Path(__file__).parent / "data" / "bitable_synced_urls.json"
_MAX_SYNCED  = 5000

# ── 飞书 API ──────────────────────────────────────────────────────────
_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
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


# ── 认证 ──────────────────────────────────────────────────────────────

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token（有效期 2 小时）。"""
    resp = requests.post(
        _TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 access token 失败: {data}")
    return data["tenant_access_token"]


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
    status  = (item.get("status") or "").strip()
    source  = (item.get("source_name") or "").strip()
    score   = float(item.get("impact_score") or 1.0)

    fields: dict = {
        "动态标题":   title,
        "摘要":       summary,
        "影响": round(score, 1),
        "处理状态":   "待阅读",
    }

    if region:
        fields["国家/地区"] = region

    # 合规类别为多选字段，API 需传列表
    if cat:
        fields["合规类别"] = [cat]

    if status:
        fields["立法状态"] = status

    if source:
        fields["信源名称"] = source

    # 超链接字段
    if url:
        fields["原始链接"] = {"text": title or url, "link": url}

    # 日期字段（毫秒时间戳）
    date_ms = _date_to_ms(item.get("date", ""))
    if date_ms:
        fields["发布日期"] = date_ms

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

        # 更新去重记录
        for item in new_items:
            url = item.get("source_url")
            if url:
                synced_urls.add(url)
        _save_synced_urls(synced_urls)

    except Exception as e:
        print(f"⚠️  飞书多维表格写入失败（不阻断主流程）: {e}")


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
