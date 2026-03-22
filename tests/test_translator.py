"""
translator.py 单元测试（纯本地逻辑，不调用 LLM/Google Translate）
覆盖：专有名词纠错、bigram 相似度、文本构建、区域前缀规则
"""
import pytest

from translator import (
    _apply_term_corrections,
    _bigram_similarity,
    _build_source_text,
    _ensure_complete_sentence,
    _is_mostly_chinese,
    _REGION_PREFIX_RULES,
    _TERM_CORRECTIONS,
    _VALID_REGIONS,
    _VALID_CATEGORIES_L1,
    _VALID_STATUSES,
)
import re


# ═══════════════════════════════════════════════════════════════════════
# 专有名词纠错
# ═══════════════════════════════════════════════════════════════════════

class TestTermCorrections:

    def test_valve_mistranslation(self):
        assert _apply_term_corrections("瓦尔维尔发布新政策") == "Valve发布新政策"
        assert _apply_term_corrections("维尔福公司") == "Valve公司"

    def test_steam_mistranslation(self):
        assert _apply_term_corrections("史蒂姆平台") == "Steam平台"

    def test_loot_box_mistranslation(self):
        assert _apply_term_corrections("战利品箱监管") == "Loot Box监管"
        assert _apply_term_corrections("战利品盒法规") == "Loot Box法规"
        assert _apply_term_corrections("战利品包规定") == "Loot Box规定"

    def test_gacha_mistranslation(self):
        assert _apply_term_corrections("加查机制被禁") == "Gacha机制被禁"

    def test_deepfake(self):
        assert _apply_term_corrections("深度伪造技术监管") == "Deepfake技术监管"

    def test_discord(self):
        assert _apply_term_corrections("迪斯科平台") == "Discord平台"

    def test_roblox(self):
        assert _apply_term_corrections("罗布乐思遭罚") == "Roblox遭罚"

    def test_iap(self):
        assert _apply_term_corrections("应用内购买规定") == "IAP规定"

    def test_no_change_when_correct(self):
        text = "Valve Steam Loot Box Gacha regulation"
        assert _apply_term_corrections(text) == text

    def test_multiple_corrections_in_one_text(self):
        text = "史蒂姆上的战利品箱和加查机制"
        result = _apply_term_corrections(text)
        assert "Steam" in result
        assert "Loot Box" in result
        assert "Gacha" in result


# ═══════════════════════════════════════════════════════════════════════
# Bigram 相似度（translator 版本）
# ═══════════════════════════════════════════════════════════════════════

class TestBigramSimilarity:

    def test_identical(self):
        assert _bigram_similarity("测试文本", "测试文本") == 1.0

    def test_completely_different(self):
        sim = _bigram_similarity("甲乙丙丁", "子丑寅卯")
        assert sim < 0.1

    def test_threshold_055(self):
        """验证相似度阈值 0.55 的实际行为"""
        # 标题和摘要雷同时应超过 0.55
        title = "[美国] FTC 对游戏公司处以隐私罚款"
        summary_bad = "FTC 对游戏公司处以隐私保护罚款"  # 只换了两个字
        sim = _bigram_similarity(title, summary_bad)
        assert sim > 0.5  # 高度相似

    def test_good_summary_low_sim(self):
        """好的摘要应与标题差异大，相似度低"""
        title = "[美国] FTC 对游戏公司处以隐私罚款"
        summary_good = "涉及未经家长同意收集儿童数据，须在30日内删除并缴纳500万美元罚金"
        sim = _bigram_similarity(title, summary_good)
        assert sim < 0.4

    def test_empty_or_short(self):
        assert _bigram_similarity("", "test") == 0.0
        assert _bigram_similarity("a", "b") == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 文本构建
# ═══════════════════════════════════════════════════════════════════════

class TestBuildSourceText:

    def test_title_only(self):
        result = _build_source_text({"title": "FTC fines game", "summary": ""})
        assert result == "FTC fines game"

    def test_short_summary_ignored(self):
        result = _build_source_text({"title": "FTC fines game", "summary": "short"})
        assert result == "FTC fines game"

    def test_title_and_summary_combined(self):
        result = _build_source_text({
            "title": "FTC fines game company",
            "summary": "The Federal Trade Commission announced a major enforcement action against a mobile game developer."
        })
        assert "FTC" in result
        assert len(result) > len("FTC fines game company")

    def test_truncated_to_500(self):
        result = _build_source_text({
            "title": "Test",
            "summary": "x" * 1000,
        })
        assert len(result) <= 500

    def test_rss_truncation_cleaned(self):
        result = _build_source_text({
            "title": "News",
            "summary": "Some content about regulation and compliance [+2345 chars]",
        })
        assert "[+2345" not in result


class TestEnsureCompleteSentence:

    def test_ends_with_period(self):
        assert _ensure_complete_sentence("Hello world.") == "Hello world."

    def test_ends_with_chinese_period(self):
        assert _ensure_complete_sentence("你好世界。") == "你好世界。"

    def test_truncates_at_last_period(self):
        # 只有当末尾不以句号结尾且最后一个句号位置 > 40% 时才截断
        text = "第一句话已经完成。第二句话也已完成。第三句话被截断了没有句号"
        result = _ensure_complete_sentence(text)
        assert result.endswith("。")

    def test_empty(self):
        assert _ensure_complete_sentence("") == ""


class TestIsMostlyChinese:

    def test_chinese_text(self):
        assert _is_mostly_chinese("这是一段中文文字测试") is True

    def test_english_text(self):
        assert _is_mostly_chinese("This is English text only") is False

    def test_mixed_mostly_chinese(self):
        assert _is_mostly_chinese("FTC 对中国游戏公司进行合规审查") is True

    def test_empty(self):
        assert _is_mostly_chinese("") is False


# ═══════════════════════════════════════════════════════════════════════
# 区域前缀规则
# ═══════════════════════════════════════════════════════════════════════

class TestRegionPrefixRules:

    def _match_region(self, title: str) -> str:
        for region_cn, pattern in _REGION_PREFIX_RULES:
            if re.search(pattern, title, re.IGNORECASE):
                return region_cn
        return ""

    def test_us_ftc(self):
        assert self._match_region("FTC announces new game regulation") == "美国"

    def test_uk_asa(self):
        assert self._match_region("UK ASA bans misleading game ad") == "英国"

    def test_eu_gdpr(self):
        assert self._match_region("GDPR enforcement action against game") == "欧盟"

    def test_korea(self):
        assert self._match_region("South Korea GRAC game regulation") == "韩国"

    def test_japan(self):
        # 正则为 \b(Japan[ese]?)\b，匹配 Japan 或 Japanese（后者需 [ese] 可选）
        assert self._match_region("Japan game regulation update") == "日本"

    def test_australia(self):
        assert self._match_region("Australian eSafety commissioner") == "澳大利亚"

    def test_global(self):
        assert self._match_region("Global game regulation trend") == "全球"

    def test_no_match(self):
        assert self._match_region("random cooking recipe") == ""


# ═══════════════════════════════════════════════════════════════════════
# 合法值集合完整性
# ═══════════════════════════════════════════════════════════════════════

class TestValidSets:

    def test_valid_regions_not_empty(self):
        assert len(_VALID_REGIONS) > 50

    def test_valid_regions_includes_key_countries(self):
        for country in ["美国", "欧盟", "日本", "韩国", "越南", "香港", "澳大利亚", "巴西", "沙特"]:
            assert country in _VALID_REGIONS, f"'{country}' 不在 _VALID_REGIONS 中"

    def test_valid_categories_l1(self):
        expected = {"数据隐私", "玩法合规", "未成年人保护", "广告营销合规",
                    "消费者保护", "经营合规", "平台政策", "内容监管", "PC & 跨平台合规",
                    "AI内容合规", "金融合规与支付"}
        assert expected == _VALID_CATEGORIES_L1

    def test_valid_statuses(self):
        expected = {"已生效", "即将生效", "草案/征求意见", "立法进行中",
                    "已提案", "修订变更", "已废止", "执法动态", "立法动态"}
        assert expected == _VALID_STATUSES

    def test_term_corrections_not_empty(self):
        assert len(_TERM_CORRECTIONS) > 10
