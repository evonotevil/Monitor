"""
daily_check.py 单元测试
覆盖：飞书通知失败时不写入机器人推送去重记录。
"""

import pytest
import json
from datetime import datetime
from pathlib import Path

import daily_check
import feishu_bitable
import translator


def _push_item(index, *, value=2, impact=5.0, decision="push", risk=1):
    return {
        "source_url": f"https://example.com/{index}",
        "title_zh": f"[美国] 动态 {index}",
        "summary_zh": "监管机构发布了明确要求，企业需要在规定期限内完成产品调整。",
        "region": "北美",
        "category_l1": "数据隐私",
        "source_name": "FTC News",
        "date": "2026-07-14",
        "impact_score": impact,
        "push_decision": decision,
        "value_score": value,
        "risk_revenue": risk,
        "risk_product": 0,
        "risk_urgency": 0,
        "risk_scope": 0,
    }


def test_select_daily_push_items_applies_gate_sort_and_cap(monkeypatch):
    monkeypatch.setattr(daily_check, "_MAX_TOTAL", 8)
    items = [_push_item(i, impact=float(i)) for i in range(10)]
    items.extend([
        _push_item("pool", decision="pool_only", impact=99),
        _push_item("zero-risk", risk=0, impact=99),
    ])
    selected = daily_check.select_daily_push_items(items)
    assert len(selected) == 8
    assert selected[0]["source_url"].endswith("/9")
    assert all(item["push_decision"] == "push" for item in selected)
    assert all(item["risk_revenue"] > 0 for item in selected)


def test_select_daily_push_items_prefers_value_before_impact():
    selected = daily_check.select_daily_push_items([
        _push_item("medium", value=2, impact=9),
        _push_item("high", value=3, impact=4),
    ])
    assert selected[0]["source_url"].endswith("/high")


def test_july_14_golden_replay_keeps_19_noise_items_out_of_push():
    fixture_path = Path(__file__).parent / "fixtures" / "daily_2026_07_14.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    items = []
    for index, row in enumerate(fixture):
        is_push = row["expected"] == "push"
        item = _push_item(
            index,
            decision="push" if is_push else "pool_only",
            value=2 if is_push else 0,
            risk=1 if is_push else 0,
        )
        item["title_zh"] = row["title"]
        items.append(item)

    selected = daily_check.select_daily_push_items(items)
    assert len(fixture) == 26
    assert sum(row["expected"] == "pool_only" for row in fixture) == 19
    assert len(selected) == 7
    assert all(item["push_decision"] == "push" for item in selected)


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
