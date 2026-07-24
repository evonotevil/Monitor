"""Push-rule activation and shadow-mode regression tests."""

from datetime import date

from monitor import _push_shadow_mode_enabled, _resolve_push_assessment


def _comparison(shadow_mode: bool):
    return _resolve_push_assessment(
        shadow_mode=shadow_mode,
        raw_title="Roblox child safety webinar in the United States",
        raw_summary=(
            "A long panel discussion reviewed community experiences and general industry views "
            "about children using Roblox, without announcing any government action or change."
        ),
        generated_title="FTC issues a Roblox child-safety enforcement order",
        generated_summary=(
            "The FTC issued a new enforcement order that requires Roblox to change its child-data "
            "flows and complete implementation before a stated deadline in the United States."
        ),
        source_name="Industry Blog",
        is_relevant=True,
        value_score=3,
        push_decision="push",
        noise_reason="高价值监管动态",
        decision_source="llm",
        risk_revenue=0,
        risk_product=2,
        risk_urgency=1,
        risk_scope=1,
        jurisdiction="美国",
        applicability_scope="single",
    )


def test_shadow_mode_applies_v1_but_only_compares_v2():
    active, v1, v2 = _comparison(shadow_mode=True)
    assert v1[0] == "push"
    assert v2[0] == "pool_only"
    assert active == v1


def test_normal_mode_applies_raw_evidence_v2():
    active, v1, v2 = _comparison(shadow_mode=False)
    assert v1[0] == "push"
    assert v2[0] == "pool_only"
    assert active == v2


def test_shadow_mode_env_is_explicit(monkeypatch):
    monkeypatch.delenv("MONITOR_SHADOW_MODE", raising=False)
    assert _push_shadow_mode_enabled() is False
    monkeypatch.setenv("MONITOR_SHADOW_MODE", "true")
    assert _push_shadow_mode_enabled() is True


def test_shadow_mode_automatically_expires_after_cutoff(monkeypatch):
    monkeypatch.setenv("MONITOR_SHADOW_MODE", "true")
    monkeypatch.setenv("MONITOR_SHADOW_UNTIL", "2026-07-31")
    assert _push_shadow_mode_enabled(today=date(2026, 7, 31)) is True
    assert _push_shadow_mode_enabled(today=date(2026, 8, 1)) is False
