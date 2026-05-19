"""
fetcher.py 单元测试 — is_legislation_relevant() 过滤逻辑
"""

from fetcher import is_legislation_relevant


# ═══════════════════════════════════════════════════════════════════════
# 监管信号词 (REGULATORY_SIGNALS)
# ═══════════════════════════════════════════════════════════════════════

class TestRegulatorySignals:

    def test_recommendation_passes(self):
        article = {
            "title": "EU Commission Recommendation on age verification for minors",
            "summary": "The Commission urges member states to implement age verification for gaming platforms",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_executive_order_passes(self):
        article = {
            "title": "Executive Order on AI Safety in gaming applications",
            "summary": "President signs executive order affecting game AI regulation",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_nprm_passes(self):
        article = {
            "title": "NPRM: FTC proposes new rules for in-app purchases in games",
            "summary": "Notice of proposed rulemaking for game monetization",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_guidance_passes(self):
        article = {
            "title": "FTC issues guidance on loot box disclosure for mobile games",
            "summary": "New guidance document for game developers",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_compound_decision_passes(self):
        article = {
            "title": "Commission decision on mobile game platform penalties",
            "summary": "Regulatory enforcement decision on gaming compliance issued",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_bare_decision_no_match(self):
        article = {
            "title": "Company decision to expand gaming business",
            "summary": "Business strategy announcement for game studios",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_japanese_tsuuchi(self):
        article = {
            "title": "消費者庁 ゲーム 通知",
            "summary": "ゲームアプリに関する新しい通知が発表された",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_japanese_shidou(self):
        article = {
            "title": "消費者庁 ゲーム課金 指導",
            "summary": "ガチャ課金に対する行政指導",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_korean_goshi(self):
        article = {
            "title": "게임물관리위원회 고시 게임 확률형",
            "summary": "새로운 고시에 따른 게임 규제 변경",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_korean_jichiim(self):
        article = {
            "title": "게임 확률형 아이템 지침 발표",
            "summary": "게임 산업 관련 새로운 지침",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True


# ═══════════════════════════════════════════════════════════════════════
# 数字行业信号词 — official/legal 信源第二道门槛
# ═══════════════════════════════════════════════════════════════════════

class TestDigitalIndustrySignals:

    def test_age_verification_official_source(self):
        article = {
            "title": "Recommendation on age verification systems",
            "summary": "Commission recommends age verification for online platforms",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_digital_identity_official_source(self):
        article = {
            "title": "New regulation on eIDAS digital identity wallets",
            "summary": "EUDI wallet implementation guidelines for digital platforms",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_child_safety_official_source(self):
        article = {
            "title": "New enforcement guidance on child safety online",
            "summary": "Child safety requirements for digital service providers",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_official_source_no_digital_signal_rejected(self):
        article = {
            "title": "New regulation on food safety standards",
            "summary": "Updated food labeling requirements for manufacturers",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is False

    def test_japanese_health_food_online_ad_guidance_rejected(self):
        article = {
            "title": "健康食品等のインターネット広告に係る虚偽・誇大表示の改善指導",
            "summary": "消費者庁は健康食品等の商品についてインターネット広告の虚偽・誇大表示に係る改善指導を行いました",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is False

    def test_health_food_supplement_ad_enforcement_rejected(self):
        article = {
            "title": "Consumer agency issues guidance on health food supplement advertising",
            "summary": "The enforcement action targets misleading online ads for supplements and cosmetics",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is False

    def test_japanese_gacha_ad_guidance_still_passes(self):
        article = {
            "title": "消費者庁 ゲーム ガチャ 景品表示法 指導",
            "summary": "ゲーム内ガチャの確率表示と広告表示について改善指導が行われた",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True


# ═══════════════════════════════════════════════════════════════════════
# 回归测试 — 确保已有行为不变
# ═══════════════════════════════════════════════════════════════════════

class TestExistingBehaviorPreserved:

    def test_ftc_game_fine_passes(self):
        article = {
            "title": "FTC fines game company for COPPA violation",
            "summary": "Federal Trade Commission enforcement action against gaming developer",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_gdpr_game_fine_passes(self):
        article = {
            "title": "GDPR fine issued to mobile game developer",
            "summary": "Data protection violation in gaming application",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_game_review_excluded(self):
        article = {
            "title": "Best game review score rating gameplay",
            "summary": "Top 10 games with stars rating and walkthrough",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_casino_excluded(self):
        article = {
            "title": "Casino regulation new law enforcement fine",
            "summary": "Sports betting gaming regulation update",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_china_mainland_excluded(self):
        article = {
            "title": "China issues new game regulation PIPL enforcement",
            "summary": "中华人民共和国 gaming law enforcement",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_no_game_signal_rejected(self):
        article = {
            "title": "New regulation on automobile emissions standards",
            "summary": "Environmental enforcement action on car manufacturers",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_loot_box_regulation_passes(self):
        article = {
            "title": "Loot box regulation proposed in EU member state",
            "summary": "New legislation targeting gacha and randomized purchases",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True
