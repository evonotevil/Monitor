"""
reporter.py 单元测试
覆盖：事件指纹、去重逻辑、区域推断、报告生成辅助函数
"""
import pytest

from reporter import (
    _calculate_event_fingerprint,
    _fp_same_event,
    _infer_group_from_text,
    _resolve_group,
    _impact_tier,
    _clean_title,
    _truncate,
    _get_display_title,
    _get_summary_zh,
    _date_range_str,
    _sort_group,
    _split_three_ways,
    CATEGORY_STYLE,
    STATUS_CSS,
    IMPACT_CONFIG,
)


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════

class TestTruncate:

    def test_short_string(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_string(self):
        result = _truncate("hello world", 8)
        assert len(result) == 8
        assert result.endswith("…")

    def test_empty(self):
        assert _truncate("", 10) == ""

    def test_none(self):
        assert _truncate(None, 10) == ""


class TestCleanTitle:

    def test_html_entities(self):
        assert _clean_title("FTC &amp; Game") == "FTC & Game"

    def test_media_suffix_removed(self):
        result = _clean_title("FTC fines game company - Reuters")
        assert "Reuters" not in result

    def test_gamesindustry_suffix(self):
        result = _clean_title("Loot box ban proposed - GamesIndustry.biz")
        assert "GamesIndustry" not in result

    def test_no_suffix(self):
        assert _clean_title("FTC fines game company") == "FTC fines game company"

    def test_empty(self):
        assert _clean_title("") == ""

    def test_none(self):
        assert _clean_title(None) == ""


class TestGetDisplayTitle:

    def test_returns_title(self):
        assert _get_display_title({"title": "Hello"}) == "Hello"

    def test_missing_title(self):
        assert _get_display_title({}) == ""


class TestGetSummaryZh:

    def test_prefers_chinese(self):
        item = {"summary_zh": "中文摘要", "summary": "English summary"}
        assert _get_summary_zh(item) == "中文摘要"

    def test_falls_back_to_english(self):
        item = {"summary_zh": "", "summary": "English summary"}
        assert _get_summary_zh(item) == "English summary"

    def test_empty(self):
        assert _get_summary_zh({}) == ""


# ═══════════════════════════════════════════════════════════════════════
# Impact Tier
# ═══════════════════════════════════════════════════════════════════════

class TestImpactTier:

    def test_high(self):
        assert _impact_tier(9.0) == "high"
        assert _impact_tier(10.0) == "high"

    def test_medium(self):
        assert _impact_tier(7.0) == "medium"
        assert _impact_tier(8.9) == "medium"

    def test_low(self):
        assert _impact_tier(6.9) == "low"
        assert _impact_tier(1.0) == "low"

    def test_none(self):
        assert _impact_tier(None) == "low"


# ═══════════════════════════════════════════════════════════════════════
# 事件指纹
# ═══════════════════════════════════════════════════════════════════════

class TestEventFingerprint:

    def test_contains_entity(self):
        item = {"title": "Google Play policy change", "region": "全球"}
        fp = _calculate_event_fingerprint(item)
        assert any(t.startswith("E:") for t in fp)
        assert "E:google" in fp

    def test_contains_topic(self):
        item = {"title": "Privacy regulation game data", "region": "欧洲"}
        fp = _calculate_event_fingerprint(item)
        assert "T:privacy" in fp

    def test_contains_region(self):
        item = {"title": "test", "region": "美国"}
        fp = _calculate_event_fingerprint(item)
        assert "R:北美" in fp

    def test_other_region_excluded(self):
        item = {"title": "test", "region": "其他"}
        fp = _calculate_event_fingerprint(item)
        assert not any(t.startswith("R:") for t in fp)

    def test_multiple_entities(self):
        item = {"title": "Apple Google payment dispute DMA", "region": "欧洲"}
        fp = _calculate_event_fingerprint(item)
        assert "E:apple" in fp
        assert "E:google" in fp


class TestFpSameEvent:

    def test_shared_entity_and_topic(self):
        fp_a = frozenset({"E:apple", "T:payment", "R:北美"})
        fp_b = frozenset({"E:apple", "T:payment", "R:欧洲"})
        assert _fp_same_event(fp_a, fp_b) is True

    def test_shared_entity_only(self):
        fp_a = frozenset({"E:apple", "T:payment"})
        fp_b = frozenset({"E:apple", "T:privacy"})
        assert _fp_same_event(fp_a, fp_b) is False

    def test_shared_topic_only(self):
        fp_a = frozenset({"E:apple", "T:payment"})
        fp_b = frozenset({"E:google", "T:payment"})
        assert _fp_same_event(fp_a, fp_b) is False

    def test_no_overlap(self):
        fp_a = frozenset({"E:apple", "T:payment"})
        fp_b = frozenset({"E:meta", "T:privacy"})
        assert _fp_same_event(fp_a, fp_b) is False


# ═══════════════════════════════════════════════════════════════════════
# 区域推断
# ═══════════════════════════════════════════════════════════════════════

class TestInferGroupFromText:

    def test_us_ftc(self):
        assert _infer_group_from_text("FTC fines game company", "") == "北美"

    def test_uk(self):
        assert _infer_group_from_text("UK Ofcom online safety regulation", "") == "欧洲"

    def test_eu_gdpr(self):
        assert _infer_group_from_text("GDPR enforcement fine", "") == "欧洲"

    def test_korea(self):
        assert _infer_group_from_text("South Korea GRAC game regulation", "") == "日韩"

    def test_japan(self):
        assert _infer_group_from_text("Japan game ゲーム regulation", "") == "日韩"

    def test_hong_kong(self):
        assert _infer_group_from_text("Hong Kong PCPD data protection", "") == "港澳台"

    def test_australia(self):
        assert _infer_group_from_text("Australia eSafety game", "") == "大洋洲"

    def test_vietnam(self):
        assert _infer_group_from_text("Vietnam game regulation", "") == "东南亚"

    def test_brazil(self):
        assert _infer_group_from_text("Brazil LGPD game data", "") == "南美"

    def test_saudi(self):
        assert _infer_group_from_text("Saudi game content regulation", "") == "中东"

    def test_chinese_title(self):
        assert _infer_group_from_text("", "美国 FTC 对游戏公司处以罚款") == "北美"

    def test_unknown(self):
        assert _infer_group_from_text("random text", "") == "其他"


class TestResolveGroup:

    def test_known_region(self):
        assert _resolve_group({"region": "美国"}) == "北美"

    def test_other_fallback_to_text(self):
        item = {"region": "其他", "title": "FTC game regulation", "title_zh": ""}
        result = _resolve_group(item)
        assert result == "北美"

    def test_other_no_text_clue(self):
        item = {"region": "其他", "title": "random text", "title_zh": ""}
        assert _resolve_group(item) == "其他"


# ═══════════════════════════════════════════════════════════════════════
# 日期范围
# ═══════════════════════════════════════════════════════════════════════

class TestDateRangeStr:

    def test_iso_week(self):
        result = _date_range_str([], "2026-W12")
        assert "2026-03-16" in result
        assert "2026-03-22" in result

    def test_from_items(self):
        items = [
            {"date": "2026-03-20"},
            {"date": "2026-03-18"},
            {"date": "2026-03-22"},
        ]
        result = _date_range_str(items, "")
        assert "2026-03-18" in result
        assert "2026-03-22" in result

    def test_empty(self):
        assert _date_range_str([], "") == ""


# ═══════════════════════════════════════════════════════════════════════
# 三分区逻辑
# ═══════════════════════════════════════════════════════════════════════

class TestSplitThreeWays:

    def test_archived(self):
        items = [{"bitable_status": "✅ 已合规/归档"}]
        archived, news, active = _split_three_ways(items)
        assert len(archived) == 1
        assert len(news) == 0
        assert len(active) == 0

    def test_news(self):
        items = [{"bitable_status": "📰 行业动态"}]
        archived, news, active = _split_three_ways(items)
        assert len(news) == 1

    def test_pending_review_skipped(self):
        """「待研判」不纳入周报三分区"""
        items = [{"bitable_status": "👤 待研判"}]
        archived, news, active = _split_three_ways(items)
        assert len(archived) == 0
        assert len(news) == 0
        assert len(active) == 0

    def test_unknown_status_skipped(self):
        """未知状态不纳入周报三分区"""
        items = [{"bitable_status": ""}]
        archived, news, active = _split_three_ways(items)
        assert len(archived) == 0
        assert len(news) == 0
        assert len(active) == 0

    def test_mixed(self):
        items = [
            {"bitable_status": "✅ 已合规/归档"},
            {"bitable_status": "📰 行业动态"},
            {"bitable_status": "👤 待研判"},
            {"bitable_status": "🏃 处理/跟进中"},
        ]
        archived, news, active = _split_three_ways(items)
        assert len(archived) == 1
        assert len(news) == 1
        assert len(active) == 1


# ═══════════════════════════════════════════════════════════════════════
# 排序
# ═══════════════════════════════════════════════════════════════════════

class TestSortGroup:

    def test_sorts_by_tier_then_impact_then_date(self):
        items = [
            {"source_name": "Random Blog", "impact_score": 5.0, "date": "2026-03-20"},
            {"source_name": "FTC News", "impact_score": 9.0, "date": "2026-03-19"},
            {"source_name": "GamesIndustry.biz", "impact_score": 7.0, "date": "2026-03-21"},
        ]
        result = _sort_group(items)
        # FTC (official, 9.0) 应排第一
        assert result[0]["source_name"] == "FTC News"


# ═══════════════════════════════════════════════════════════════════════
# 常量完整性
# ═══════════════════════════════════════════════════════════════════════

class TestReporterConstants:

    def test_category_style_covers_main_categories(self):
        expected = ["数据隐私", "玩法合规", "未成年人保护", "广告营销合规",
                    "消费者保护", "经营合规", "平台政策", "内容监管", "PC & 跨平台合规"]
        for cat in expected:
            assert cat in CATEGORY_STYLE, f"'{cat}' 缺少样式配置"

    def test_status_css_covers_all(self):
        expected = ["已生效", "即将生效", "草案/征求意见", "立法进行中",
                    "已提案", "修订变更", "已废止", "执法动态", "立法动态"]
        for s in expected:
            assert s in STATUS_CSS, f"'{s}' 缺少 CSS 配置"

    def test_impact_config_has_three_tiers(self):
        assert "high" in IMPACT_CONFIG
        assert "medium" in IMPACT_CONFIG
        assert "low" in IMPACT_CONFIG
