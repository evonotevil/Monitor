"""
classifier.py 单元测试
覆盖：区域检测、分类检测、状态检测、影响评分、噪音过滤
"""
import pytest

from classifier import (
    classify_article,
    score_impact,
    get_source_tier,
    is_china_mainland,
    _detect_region,
    _detect_category,
    _detect_status,
    _is_hardware_noise,
    _is_google_apple_non_core,
    _high_risk_bonus,
    COUNTRY_PATTERNS,
    COUNTRY_TO_REGION,
)


# ═══════════════════════════════════════════════════════════════════════
# 区域检测
# ═══════════════════════════════════════════════════════════════════════

class TestDetectRegion:
    """_detect_region: 从文本识别区域"""

    def test_single_country_us(self):
        assert _detect_region("FTC fines game company for COPPA violation") == "北美"

    def test_single_country_eu(self):
        assert _detect_region("GDPR enforcement action against mobile game") == "欧洲"

    def test_single_country_japan(self):
        # _detect_region 返回 MONITORED_REGIONS 中的区域名（"日本"），非显示分组名
        assert _detect_region("日本 ガチャ規制 景品表示法 改正") == "日本"

    def test_single_country_korea(self):
        assert _detect_region("한국 게임산업진흥법 확률형 아이템 규제") == "韩国"

    def test_single_country_vietnam(self):
        assert _detect_region("Vietnam MIC game regulation decree") == "东南亚"

    def test_single_country_australia(self):
        assert _detect_region("Australia eSafety online safety act game") == "大洋洲"

    def test_single_country_brazil(self):
        assert _detect_region("Brazil LGPD game data protection") == "南美"

    def test_single_country_saudi(self):
        # MONITORED_REGIONS 中区域名为 "中东/非洲"
        assert _detect_region("Saudi Arabia GCAM game content license") == "中东/非洲"

    def test_multi_country_picks_dominant(self):
        # "US FTC" 出现两次关键词 (US + FTC)，UK 出现一次
        text = "US FTC announces new rules, UK ICO reviews compliance"
        result = _detect_region(text)
        assert result == "北美"

    def test_fallback_to_eu_pattern(self):
        assert _detect_region("EU announces new digital regulation") == "欧洲"

    def test_fallback_to_provided_region(self):
        assert _detect_region("some vague article about gaming", "欧洲") == "欧洲"

    def test_unknown_returns_other(self):
        assert _detect_region("random text about nothing specific") == "其他"

    def test_hong_kong(self):
        assert _detect_region("Hong Kong PCPD data protection game") == "港澳台"

    def test_taiwan(self):
        assert _detect_region("台灣 個資法 遊戲 合規") == "港澳台"

    def test_india(self):
        # MONITORED_REGIONS 中印度属于 "南亚" 区域
        assert _detect_region("India DPDPA gaming data protection MeitY") == "南亚"

    def test_indonesia(self):
        assert _detect_region("Indonesia IGAC game rating requirement Kominfo") == "东南亚"


class TestIsChinaMainland:
    """is_china_mainland: 检测中国大陆内容（应排除）"""

    def test_china_keyword(self):
        assert is_china_mainland("China issues new game regulation PIPL") is True

    def test_china_zh(self):
        assert is_china_mainland("中国版号审批新政策") is True

    def test_hong_kong_not_mainland(self):
        assert is_china_mainland("Hong Kong game regulation") is False

    def test_china_with_hong_kong_excluded(self):
        # "china" 后面跟着 "hong kong" 应该不匹配大陆模式
        assert is_china_mainland("China hong kong game policy") is False

    def test_taiwan_not_mainland(self):
        assert is_china_mainland("Taiwan game classification law") is False


# ═══════════════════════════════════════════════════════════════════════
# 分类检测
# ═══════════════════════════════════════════════════════════════════════

class TestDetectCategory:
    """_detect_category: 识别一级/二级分类"""

    def test_data_privacy(self):
        l1, l2 = _detect_category("GDPR enforcement fine data breach notification")
        assert l1 == "数据隐私"

    def test_loot_box(self):
        l1, l2 = _detect_category("loot box gacha probability disclosure regulation")
        assert l1 == "玩法合规"

    def test_minor_protection(self):
        l1, l2 = _detect_category("children age verification minor spending limit")
        assert l1 == "未成年人保护"

    def test_advertising(self):
        l1, l2 = _detect_category("misleading game advertising dark pattern regulation")
        assert l1 == "广告营销合规"

    def test_consumer_protection(self):
        l1, l2 = _detect_category("game refund consumer protection subscription auto-renew")
        assert l1 == "消费者保护"

    def test_platform_policy(self):
        l1, l2 = _detect_category("App Store policy change Google Play third party payment DMA")
        assert l1 == "平台政策"

    def test_pc_compliance(self):
        l1, l2 = _detect_category("kernel-level anti-cheat driver privacy regulation Steam")
        assert l1 == "PC & 跨平台合规"

    def test_business_compliance(self):
        l1, l2 = _detect_category("game license local agent representative registration foreign")
        assert l1 == "经营合规"

    def test_content_moderation(self):
        l1, l2 = _detect_category("content regulation censorship AI generated content act")
        assert l1 == "内容监管"

    def test_l2_subcategory(self):
        l1, l2 = _detect_category("GDPR general data protection regulation")
        assert l1 == "数据隐私"
        assert l2 == "GDPR合规"

    def test_l2_coppa(self):
        l1, l2 = _detect_category("COPPA children privacy data protection game")
        # COPPA 同时命中"数据隐私"和"未成年人保护"，取决于 match 数量
        assert l1 in ("数据隐私", "未成年人保护")

    def test_ambiguous_gdpr_lootbox(self):
        """GDPR + loot box 混合文章应归类到 match 数多的那个"""
        l1, _ = _detect_category("GDPR loot box")
        assert l1 in ("数据隐私", "玩法合规")

    def test_default_when_no_match(self):
        """完全无匹配时默认归入内容监管"""
        l1, _ = _detect_category("completely unrelated text about cooking recipes")
        assert l1 == "内容监管"


# ═══════════════════════════════════════════════════════════════════════
# 状态检测
# ═══════════════════════════════════════════════════════════════════════

class TestDetectStatus:

    def test_effective(self):
        assert _detect_status("The new law is now effective and enacted") == "已生效"

    def test_draft(self):
        assert _detect_status("Draft regulation open for public comment consultation") == "草案/征求意见"

    def test_enforcement(self):
        assert _detect_status("FTC fined the company $10M penalty enforcement") == "执法动态"

    def test_proposed(self):
        assert _detect_status("Senator introduced a new bill proposal") == "已提案"

    def test_amendment(self):
        assert _detect_status("The act was amended and revised") == "修订变更"

    def test_default(self):
        assert _detect_status("some vague signal about future plans") == "立法动态"


# ═══════════════════════════════════════════════════════════════════════
# 信源层级
# ═══════════════════════════════════════════════════════════════════════

class TestGetSourceTier:

    def test_exact_match_official(self):
        assert get_source_tier("FTC News") == "official"

    def test_exact_match_industry(self):
        assert get_source_tier("GamesIndustry.biz") == "industry"

    def test_exact_match_legal(self):
        assert get_source_tier("IAPP News") == "legal"

    def test_pattern_match_official(self):
        assert get_source_tier("Federal Trade Commission Press Release") == "official"

    def test_pattern_match_legal(self):
        assert get_source_tier("Baker McKenzie Legal Alert") == "legal"

    def test_pattern_match_industry(self):
        assert get_source_tier("Kotaku Japan") == "industry"

    def test_unknown_defaults_to_news(self):
        assert get_source_tier("Random Blog Post") == "news"

    def test_apple_developer(self):
        assert get_source_tier("Apple Developer News") == "official"


# ═══════════════════════════════════════════════════════════════════════
# 噪音过滤
# ═══════════════════════════════════════════════════════════════════════

class TestHardwareNoise:

    def test_battery_optimization(self):
        assert _is_hardware_noise("battery optimization for mobile devices") is True

    def test_cpu_benchmark(self):
        assert _is_hardware_noise("CPU benchmark GPU architecture performance test") is True

    def test_wifi_standard(self):
        assert _is_hardware_noise("Wi-Fi 7 standard protocol update") is True

    def test_iphone_review(self):
        assert _is_hardware_noise("iPhone 16 Pro review specs launch") is True

    def test_chinese_hardware(self):
        assert _is_hardware_noise("芯片性能评测 处理器架构 续航优化") is True

    def test_game_regulation_not_noise(self):
        assert _is_hardware_noise("game regulation loot box fine") is False

    def test_privacy_not_noise(self):
        assert _is_hardware_noise("GDPR data privacy enforcement game app") is False


class TestGoogleAppleNonCore:

    def test_apple_core_topic_kept(self):
        """Apple + 支付/IAP 是核心合规话题，应保留"""
        assert _is_google_apple_non_core("Apple App Store policy payment commission") is False

    def test_apple_privacy_kept(self):
        assert _is_google_apple_non_core("Apple privacy data protection GDPR") is False

    def test_google_consumer_kept(self):
        assert _is_google_apple_non_core("Google Play consumer fine penalty") is False

    def test_apple_product_noise(self):
        """Apple + 产品评测（无合规关键词）应被过滤"""
        assert _is_google_apple_non_core("Apple launches new MacBook with M4 chip") is True

    def test_google_maps_noise(self):
        assert _is_google_apple_non_core("Google Maps adds new navigation feature") is True

    def test_no_google_apple_irrelevant(self):
        """不含 Google/Apple 的文章不受此规则影响"""
        assert _is_google_apple_non_core("FTC fines game company") is False

    def test_loot_box_with_apple(self):
        assert _is_google_apple_non_core("Apple App Store loot box probability") is False

    def test_children_with_google(self):
        assert _is_google_apple_non_core("Google Play children minor COPPA") is False


# ═══════════════════════════════════════════════════════════════════════
# 影响评分
# ═══════════════════════════════════════════════════════════════════════

class TestScoreImpact:

    def test_basic_score_range(self):
        score = score_impact("立法动态", "Random News", region="其他", text="game regulation")
        assert 1.0 <= score <= 10.0

    def test_effective_official_core_market(self):
        """已生效 + 官方源 + 核心市场 = 高分"""
        score = score_impact("已生效", "FTC News", region="美国", text="game regulation fine")
        assert score >= 9.0

    def test_draft_news_non_core(self):
        """草案 + 媒体源 + 非核心市场 = 低分"""
        score = score_impact("草案/征求意见", "Random Blog", region="尼日利亚", text="game draft")
        assert score < 7.0

    def test_core_market_bonus(self):
        """核心市场（北美/欧洲/日韩/东南亚）应获得 +2.0 加成"""
        score_core = score_impact("立法动态", "Random News", region="美国", text="game regulation")
        score_non = score_impact("立法动态", "Random News", region="尼日利亚", text="game regulation")
        assert score_core > score_non

    def test_high_risk_gacha_fine(self):
        """概率公示处罚 = +1.5 高风险加成"""
        text_risk = "gacha fine penalty enforcement probability disclosure violation"
        text_safe = "game regulation general discussion"
        score_risk = score_impact("执法动态", "FTC News", region="美国", text=text_risk)
        score_safe = score_impact("执法动态", "FTC News", region="美国", text=text_safe)
        assert score_risk > score_safe

    def test_high_risk_app_store_delist(self):
        """应用商店下架 = +1.5"""
        text = "game removed from App Store delisted banned"
        bonus = _high_risk_bonus(text)
        assert bonus >= 1.5

    def test_high_risk_kernel_anticheat(self):
        """内核反作弊隐私 = +1.0"""
        text = "kernel-level anti-cheat privacy sued lawsuit"
        bonus = _high_risk_bonus(text)
        assert bonus >= 1.0

    def test_high_risk_age_verification(self):
        """强制年龄验证 = +0.5"""
        text = "mandatory age verification required by law"
        bonus = _high_risk_bonus(text)
        assert bonus >= 0.5

    def test_hardware_noise_zero_score(self):
        """硬件噪音文章 → 0 分"""
        score = score_impact("已生效", "FTC News", region="美国",
                             text="battery optimization mobile device energy saving")
        assert score == 0.0

    def test_google_non_core_zero_score(self):
        """Google 非核心话题 → 0 分"""
        score = score_impact("已生效", "FTC News", region="美国",
                             text="Google launches new Pixel phone camera")
        assert score == 0.0

    def test_score_clamped_to_10(self):
        """分数上限 10.0"""
        score = score_impact(
            "已生效", "FTC News", region="美国",
            text="gacha fine penalty probability disclosure App Store removed delisted "
                 "kernel-level anti-cheat privacy mandatory age verification"
        )
        assert score == 10.0

    def test_score_minimum_1(self):
        """分数下限 1.0（非噪音文章）"""
        score = score_impact("已废止", "Random Blog", region="其他", text="old repealed law")
        assert score >= 1.0

    def test_multiple_high_risk_groups_stack(self):
        """不同高风险组可叠加"""
        text_one = "gacha fine penalty violation"
        text_two = "gacha fine penalty violation App Store removed banned"
        b1 = _high_risk_bonus(text_one)
        b2 = _high_risk_bonus(text_two)
        assert b2 > b1


# ═══════════════════════════════════════════════════════════════════════
# classify_article 集成
# ═══════════════════════════════════════════════════════════════════════

class TestClassifyArticle:

    def test_returns_legislation_item(self):
        from models import LegislationItem
        article = {
            "title": "FTC fines game company $5M for COPPA violation",
            "summary": "Federal Trade Commission announced enforcement action",
            "date": "2026-03-20",
            "source": "FTC News",
            "url": "https://ftc.gov/news/123",
            "lang": "en",
        }
        result = classify_article(article)
        assert isinstance(result, LegislationItem)
        assert result.region == "北美"
        assert result.impact_score > 0

    def test_summary_truncated_to_500(self):
        article = {
            "title": "Test",
            "summary": "x" * 1000,
            "date": "2026-01-01",
            "source": "Test",
            "url": "http://test.com",
        }
        result = classify_article(article)
        assert len(result.summary) <= 500

    def test_hardware_noise_gets_zero(self):
        article = {
            "title": "iPhone 16 Pro review specs battery optimization",
            "summary": "CPU benchmark GPU architecture performance",
            "date": "2026-01-01",
            "source": "Tech Blog",
            "url": "http://test.com",
        }
        result = classify_article(article)
        assert result.impact_score == 0.0


# ═══════════════════════════════════════════════════════════════════════
# 数据完整性
# ═══════════════════════════════════════════════════════════════════════

class TestDataIntegrity:

    def test_all_countries_have_region_mapping(self):
        """COUNTRY_PATTERNS 中的每个国家都应在 COUNTRY_TO_REGION 中有映射"""
        for country in COUNTRY_PATTERNS:
            assert country in COUNTRY_TO_REGION, f"'{country}' 在 COUNTRY_PATTERNS 中但不在 COUNTRY_TO_REGION"
