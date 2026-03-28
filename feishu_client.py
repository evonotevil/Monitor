#!/usr/bin/env python3
"""
飞书应用客户端 — token 管理 + 消息发送

统一管理飞书自建应用的认证和消息推送，供以下模块引用：
  feishu_bitable.py / daily_check.py / feishu_notify.py

必需环境变量:
    FEISHU_APP_ID        飞书自建应用 App ID
    FEISHU_APP_SECRET    飞书自建应用 App Secret
    FEISHU_CHAT_ID       目标群聊的 chat_id（消息推送用）
"""

import json
import os
import time

import requests

# ── 飞书 API 端点 ────────────────────────────────────────────────────────
_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


# ── 认证 ─────────────────────────────────────────────────────────────────

def get_tenant_access_token(app_id: str = "", app_secret: str = "") -> str:
    """获取 tenant_access_token（有效期 2 小时）。"""
    app_id = app_id or os.environ["FEISHU_APP_ID"]
    app_secret = app_secret or os.environ["FEISHU_APP_SECRET"]
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


# ── 消息发送 ─────────────────────────────────────────────────────────────

def send_card(chat_id: str, card: dict, max_retries: int = 3) -> None:
    """通过应用机器人向群聊发送交互卡片，失败指数退避重试。"""
    token = get_tenant_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card),
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{_MSG_URL}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 0:
                print("✅ 飞书通知发送成功")
                return
            else:
                print(f"⚠️  飞书返回异常: {result}")
                return  # 业务层错误不重试
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2  # 2s, 4s, 8s
                print(f"⚠️  发送失败: {e}，{wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"❌ 发送失败（已重试 {max_retries} 次）: {e}")
