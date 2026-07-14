"""
daily_check.py 单元测试
覆盖：飞书通知失败时不写入机器人推送去重记录。
"""

import pytest
from datetime import datetime
from pathlib import Path

import daily_check
import feishu_bitable
import translator


def test_monday_window_only_includes_weekend_and_monday():
    dates, hours = daily_check._daily_window(datetime(2026, 7, 13, 8, 0))
    assert dates == ["2026-07-13", "2026-07-12", "2026-07-11"]
    assert hours == 74


def test_regular_window_includes_today_and_yesterday():
    dates, hours = daily_check._daily_window(datetime(2026, 7, 14, 8, 0))
    assert dates == ["2026-07-14", "2026-07-13"]
    assert hours == 26


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


def test_empty_status_card_failure_exits_nonzero(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 14, 8, 0, tzinfo=tz)

    monkeypatch.setenv("FEISHU_CHAT_ID", "oc_test")
    monkeypatch.setattr(daily_check, "datetime", FixedDateTime)
    monkeypatch.setattr(daily_check, "get_daily_items", lambda: [])
    monkeypatch.setattr(daily_check, "_load_pushed_urls", lambda: set())
    monkeypatch.setattr(daily_check, "send_card", lambda chat_id, card: False)

    with pytest.raises(SystemExit) as exc:
        daily_check.main()

    assert exc.value.code == 1


def test_fetch_failure_sends_red_card_and_skips_daily_query(monkeypatch):
    sent_cards = []

    monkeypatch.setenv("FEISHU_CHAT_ID", "oc_test")
    monkeypatch.setenv("FETCH_STEP_OUTCOME", "failure")
    monkeypatch.setattr(
        daily_check,
        "get_daily_items",
        lambda: pytest.fail("fetch failure must skip normal daily query"),
    )
    monkeypatch.setattr(
        daily_check,
        "send_card",
        lambda chat_id, card: sent_cards.append(card) or True,
    )

    with pytest.raises(SystemExit) as exc:
        daily_check.main()

    assert exc.value.code == 1
    assert sent_cards[0]["header"]["template"] == "red"
    assert "不能据此判断为‘无新增’" in sent_cards[0]["elements"][0]["content"]


def test_daily_workflow_persists_push_state_and_serializes_runs():
    workflow = (
        Path(__file__).parents[1] / ".github/workflows/daily_check.yml"
    ).read_text(encoding="utf-8")
    assert "group: monitor-daily-main" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "id: fetch" in workflow
    assert "FETCH_STEP_OUTCOME: ${{ steps.fetch.outcome }}" in workflow
    assert "git add -f data/daily_pushed_urls.json" in workflow
