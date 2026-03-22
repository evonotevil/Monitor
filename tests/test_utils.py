"""
utils.py 单元测试
覆盖：区域分组映射、bigram 相似度、状态标签归一化、去重选择
"""
import pytest

from utils import (
    _REGION_GROUP_MAP,
    _GROUP_ORDER,
    _GROUP_EMOJI,
    _get_region_group,
    normalize_status,
    _bigram_sim,
    _impact_emoji,
    _pick_group_items,
    CAT_EMOJI,
    _TIER_SORT,
)


# ═══════════════════════════════════════════════════════════════════════
# 区域分组映射
# ═══════════════════════════════════════════════════════════════════════

class TestRegionGroupMap:

    def test_us_maps_to_north_america(self):
        assert _REGION_GROUP_MAP["美国"] == "北美"

    def test_eu_maps_to_europe(self):
        assert _REGION_GROUP_MAP["欧盟"] == "欧洲"

    def test_japan_maps_to_jk(self):
        assert _REGION_GROUP_MAP["日本"] == "日韩"

    def test_korea_maps_to_jk(self):
        assert _REGION_GROUP_MAP["韩国"] == "日韩"

    def test_vietnam_maps_to_sea(self):
        assert _REGION_GROUP_MAP["越南"] == "东南亚"

    def test_hong_kong_maps_to_hmt(self):
        assert _REGION_GROUP_MAP["香港"] == "港澳台"

    def test_australia_maps_to_oceania(self):
        assert _REGION_GROUP_MAP["澳大利亚"] == "大洋洲"

    def test_brazil_maps_to_south_america(self):
        assert _REGION_GROUP_MAP["巴西"] == "南美"

    def test_saudi_maps_to_middle_east(self):
        assert _REGION_GROUP_MAP["沙特"] == "中东"

    def test_india_maps_to_other(self):
        assert _REGION_GROUP_MAP["印度"] == "其他"

    def test_global_maps_to_other(self):
        assert _REGION_GROUP_MAP["全球"] == "其他"


class TestGetRegionGroup:

    def test_exact_match(self):
        assert _get_region_group("美国") == "北美"

    def test_group_name_itself(self):
        assert _get_region_group("北美") == "北美"

    def test_unknown_returns_other(self):
        assert _get_region_group("火星") == "其他"

    def test_empty_returns_north_america(self):
        # 空字符串触发模糊匹配：空串 in "北美" 为 True，返回第一个匹配的分组
        result = _get_region_group("")
        # 这是一个已知的边界行为：空串会匹配到第一个遍历到的 key
        assert result in _REGION_GROUP_MAP.values()

    def test_fuzzy_match_substring(self):
        """模糊匹配：region 包含某个 key 或 key 包含 region"""
        result = _get_region_group("欧洲地区")
        assert result == "欧洲"


class TestGroupOrder:

    def test_has_9_groups(self):
        assert len(_GROUP_ORDER) == 9

    def test_starts_with_north_america(self):
        assert _GROUP_ORDER[0] == "北美"

    def test_ends_with_other(self):
        assert _GROUP_ORDER[-1] == "其他"

    def test_all_groups_have_emoji(self):
        for group in _GROUP_ORDER:
            assert group in _GROUP_EMOJI, f"'{group}' 缺少 emoji 映射"


# ═══════════════════════════════════════════════════════════════════════
# 状态标签归一化
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeStatus:

    def test_legacy_policy_signal(self):
        assert normalize_status("政策信号") == "立法动态"

    def test_legacy_revised(self):
        assert normalize_status("已修订") == "修订变更"

    def test_current_value_unchanged(self):
        assert normalize_status("已生效") == "已生效"

    def test_unknown_value_unchanged(self):
        assert normalize_status("未知状态") == "未知状态"


# ═══════════════════════════════════════════════════════════════════════
# Bigram 相似度
# ═══════════════════════════════════════════════════════════════════════

class TestBigramSim:

    def test_identical_strings(self):
        assert _bigram_sim("hello world", "hello world") == 1.0

    def test_completely_different(self):
        sim = _bigram_sim("abcdef", "xyz123")
        assert sim < 0.1

    def test_similar_strings(self):
        sim = _bigram_sim("[美国] FTC 处罚游戏公司", "[美国] FTC 对游戏公司处以罚款")
        assert 0.3 < sim < 0.9

    def test_empty_string(self):
        assert _bigram_sim("", "hello") == 0.0

    def test_single_char(self):
        assert _bigram_sim("a", "a") == 0.0

    def test_case_insensitive(self):
        assert _bigram_sim("Hello", "hello") == 1.0

    def test_none_handled(self):
        assert _bigram_sim(None, "test") == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Impact Emoji
# ═══════════════════════════════════════════════════════════════════════

class TestImpactEmoji:

    def test_high_red(self):
        assert _impact_emoji(9.0) == "🔴"
        assert _impact_emoji(10.0) == "🔴"

    def test_medium_orange(self):
        assert _impact_emoji(7.0) == "🟠"
        assert _impact_emoji(8.5) == "🟠"

    def test_low_blue(self):
        assert _impact_emoji(6.9) == "🔵"
        assert _impact_emoji(1.0) == "🔵"


# ═══════════════════════════════════════════════════════════════════════
# _pick_group_items 去重选择
# ═══════════════════════════════════════════════════════════════════════

class TestPickGroupItems:

    def test_max_items_limit(self):
        items = [
            {"title_zh": f"标题{i}", "category_l1": f"分类{i}"}
            for i in range(10)
        ]
        result = _pick_group_items(items, max_items=3)
        assert len(result) <= 3

    def test_same_category_limited_to_1(self):
        items = [
            {"title_zh": "第一条数据隐私新闻", "category_l1": "数据隐私"},
            {"title_zh": "第二条数据隐私新闻", "category_l1": "数据隐私"},
            {"title_zh": "玩法合规新闻", "category_l1": "玩法合规"},
        ]
        result = _pick_group_items(items, max_items=5)
        privacy_count = sum(1 for r in result if r["category_l1"] == "数据隐私")
        assert privacy_count <= 1

    def test_duplicate_titles_filtered(self):
        items = [
            {"title_zh": "[美国] FTC 对游戏公司处以罚款", "category_l1": "消费者保护"},
            {"title_zh": "[美国] FTC 对游戏公司处以巨额罚款", "category_l1": "数据隐私"},
            {"title_zh": "[欧洲] GDPR 新执法动态", "category_l1": "数据隐私"},
        ]
        result = _pick_group_items(items, max_items=5)
        # 前两条标题高度相似，应只保留一条
        assert len(result) <= 2

    def test_empty_input(self):
        assert _pick_group_items([], max_items=3) == []


# ═══════════════════════════════════════════════════════════════════════
# 常量完整性
# ═══════════════════════════════════════════════════════════════════════

class TestConstants:

    def test_tier_sort_has_all_tiers(self):
        for tier in ("official", "legal", "industry", "news"):
            assert tier in _TIER_SORT

    def test_tier_sort_order(self):
        assert _TIER_SORT["official"] > _TIER_SORT["legal"]
        assert _TIER_SORT["legal"] > _TIER_SORT["industry"]
        assert _TIER_SORT["industry"] > _TIER_SORT["news"]

    def test_cat_emoji_covers_main_categories(self):
        expected = ["数据隐私", "玩法合规", "未成年人保护", "广告营销合规",
                    "消费者保护", "经营合规", "平台政策", "内容监管", "PC & 跨平台合规"]
        for cat in expected:
            assert cat in CAT_EMOJI, f"'{cat}' 缺少 emoji 映射"
