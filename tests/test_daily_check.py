"""
daily_check.py 单元测试
覆盖：飞书通知失败时不写入机器人推送去重记录。
"""

import pytest
from datetime import datetime

import daily_check
import feishu_bitable
import translator


def test_push_urls_not_saved_when_send_card_fails(monkeypatch):
    item = {
        "source_url": "https://example.com/news",
        "title_zh": "[美国] 测试动态",
        "summary_zh": "测试摘要",
        "region": "北美",
        "category_l1": "数据隐私",
        "impact_score": 7.0,
    }

    saved = {"called": False}

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 19, 8, 0, tzinfo=tz)

    monkeypatch.setenv("FEISHU_CHAT_ID", "oc_test")
    monkeypatch.setattr(daily_check, "datetime", FixedDateTime)
    monkeypatch.setattr(daily_check, "get_daily_items", lambda: [item])
    monkeypatch.setattr(daily_check, "_load_pushed_urls", lambda: set())
    monkeypatch.setattr(
        daily_check,
        "_save_pushed_urls",
        lambda urls: saved.__setitem__("called", True),
    )
    monkeypatch.setattr(feishu_bitable, "sync_items_to_bitable", lambda items: None)
    monkeypatch.setattr(translator, "generate_daily_summary", lambda items: "")
    monkeypatch.setattr(daily_check, "send_card", lambda chat_id, card: False)

    with pytest.raises(SystemExit):
        daily_check.main()

    assert saved["called"] is False
