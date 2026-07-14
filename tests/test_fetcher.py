"""
fetcher.py 单元测试 — is_legislation_relevant() 过滤逻辑
"""

import pytest
from datetime import datetime, timedelta
import fetcher
from fetcher import is_legislation_relevant, is_recent, _is_foreign_commentary, _sanitize_title


@pytest.mark.parametrize("title", [
    "ไทยออกกฎหมายใหม่สำหรับเกมออนไลน์",
    "فرض غرامة على شركة ألعاب إلكترونية",
    "Réglementation française des jeux vidéo",
    "Việt Nam xử phạt trò chơi điện tử",
])
def test_title_sanitizer_preserves_supported_unicode_scripts(title):
    assert _sanitize_title(title) == title


@pytest.mark.parametrize("title", [
    "Proibição muda o jogo político no Congresso",
    "DSI เปิดเกมคดี Forex ผิดกฎหมาย",
    "joker123 คาสิโนออนไลน์ กฎหมายใหม่",
    "โปร โทร ฟรี dtac รับคะแนนฟรีสำหรับเกมออนไลน์ ปรับประสบการณ์ใหม่",
    "South Dakota law lets rescuer save wild game bird eggs",
    "Alberta Online Gaming Regulation Announcement",
    "Curacao issues wind-down rules for gaming license holders",
    "WNBA to fine player after Indiana Fever game",
    "Gaming Laptop Review Canadian Auto Parts Settlement",
    "แอ พ เกม ยิง ปลา ได้ เงิน จริง ชนะรางวัลใหญ่",
    "死んだら復活しない兵士を操作して謎の塹壕を調査するホラーゲーム",
])
def test_non_video_game_metaphors_and_gambling_are_rejected(title):
    assert is_legislation_relevant({"title": title, "summary": "", "tier": ""}) is False


def test_daily_recency_uses_inclusive_calendar_dates():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    assert is_recent({"date": yesterday}, max_days=1) is True
    assert is_recent({"date": two_days_ago}, max_days=1) is False


def test_date_enrichment_reapplies_recency_filter(monkeypatch):
    today = datetime.now().strftime("%Y-%m-%d")
    old_article = {
        "title": "Old game regulation announcement",
        "summary": "game regulation",
        "url": "https://example.com/old",
        "date": today,
        "source": "Apple Developer News",
        "region": "全球",
        "lang": "en",
    }
    monkeypatch.setattr(fetcher, "fetch_all_rss", lambda: [old_article])
    monkeypatch.setattr(fetcher, "fetch_google_news_all", lambda *args, **kwargs: [])
    monkeypatch.setattr(fetcher, "fetch_gdelt_all", lambda **kwargs: [])
    monkeypatch.setattr(fetcher, "is_legislation_relevant", lambda article: True)
    monkeypatch.setattr(
        fetcher,
        "enrich_article_dates",
        lambda articles: [{**article, "date": "2025-01-01"} for article in articles],
    )
    monkeypatch.setattr(
        fetcher,
        "classify_article",
        lambda article: pytest.fail("old corrected article must not be classified"),
    )

    assert fetcher.fetch_and_process(max_days=1, daily_mode=True) == []


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

    def test_mobile_game_cosmetic_item_ad_guidance_passes(self):
        article = {
            "title": "FTC issues guidance on advertising cosmetic items in mobile games",
            "summary": "Guidance covers misleading advertising for skins, loot boxes, and in-game cosmetics",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_mobile_game_cosmetic_ads_enforcement_passes(self):
        article = {
            "title": "UK ASA rules mobile game cosmetic ads were misleading",
            "summary": "The enforcement action concerns advertising for in-game cosmetic items and loot boxes",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_supplements_as_verb_in_game_guidance_passes(self):
        article = {
            "title": "FTC supplements guidance on dark patterns in mobile games",
            "summary": "Updated enforcement guidance covers in-app purchases and game advertising",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

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


class TestExpandedRegionCoverage:

    @pytest.mark.parametrize("title", [
        "Autoridade aplica multa a jogos digitais por violação do consumidor",
        "Autoridad impone multa a videojuegos por incumplimiento",
        "Behörde verhängt Geldbuße gegen Videospiele wegen Datenschutz",
        "Une autorité inflige une amende à un jeu vidéo pour violation de la vie privée",
        "หน่วยงานปรับเกมออนไลน์ฐานละเมิดกฎหมายคุ้มครองเด็ก",
        "Otoritas menjatuhkan denda pada gim karena pelanggaran privasi",
        "主管機關因違反個資法裁罰線上遊戲業者",
        "فرض غرامة على شركة ألعاب بسبب انتهاك قانون الخصوصية",
    ])
    def test_multilingual_enforcement_signals_pass(self, title):
        assert is_legislation_relevant({"title": title, "summary": "", "tier": ""}) is True

    def test_indonesia_pp_tunas_passes(self):
        article = {
            "title": "PP TUNAS mengatur pelindungan anak dalam penyelenggaraan sistem elektronik",
            "summary": "PP Nomor 17 Tahun 2025 mewajibkan platform digital melindungi anak",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_indonesia_pp_tunas_outreach_event_is_noise(self):
        article = {
            "title": "Sosialisasi PP TUNAS dan pelatihan literasi digital di sekolah",
            "summary": "Seminar edukasi untuk guru dan keluarga tanpa aturan baru",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is False

    def test_vietnam_game_enforcement_decrees_pass(self):
        article = {
            "title": "Nghị định 174/2026/NĐ-CP quy định xử phạt trò chơi điện tử",
            "summary": "Thực thi Nghị định 147/2024/NĐ-CP về tài khoản và vật phẩm ảo",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_brazil_game_consumer_fine_passes(self):
        article = {
            "title": "Senacon aplica multa a jogo por violação do consumidor",
            "summary": "Fiscalização de jogos digitais e itens virtuais no Brasil",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_taiwan_game_penalty_passes(self):
        article = {
            "title": "台灣主管機關裁罰線上遊戲業者",
            "summary": "遊戲虛擬寶物與消費者保護法規執法",
            "tier": "",
        }
        assert is_legislation_relevant(article) is True

    def test_taiwan_playground_penalty_is_not_a_video_game_signal(self):
        article = {
            "title": "兒童遊戲設施無法可罰，立委提案修法納管",
            "summary": "公園遊樂設施安全管理法規",
            "tier": "",
        }
        assert is_legislation_relevant(article) is False

    def test_normalized_local_language_regions_are_kept(self):
        assert _is_foreign_commentary("ko", "日韩") is False
        assert _is_foreign_commentary("ja", "日韩") is False
        assert _is_foreign_commentary("zh-TW", "港澳台") is False
        assert _is_foreign_commentary("ar", "中东") is False

    def test_foreign_reporting_is_retained_for_event_classification(self):
        assert _is_foreign_commentary("ko", "北美") is False
        assert _is_foreign_commentary("ja", "欧洲") is False

    def test_canada_pipeda_game_privacy_passes(self):
        article = {
            "title": "Canada OPC issues PIPEDA guidance for game apps",
            "summary": "The privacy commissioner addresses data protection rules for mobile games",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_india_online_gaming_rules_passes(self):
        article = {
            "title": "India online gaming rules require compliance for game platforms",
            "summary": "MeitY regulation covers gaming intermediaries and consumer protection",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_hong_kong_pcpd_game_privacy_passes(self):
        article = {
            "title": "Hong Kong PCPD guidance on online game app privacy",
            "summary": "Personal data protection requirements apply to gaming applications",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_latam_consumer_game_regulation_passes(self):
        article = {
            "title": "Chile SERNAC regulation targets video game consumer protection",
            "summary": "The consumer agency reviews refund and advertising practices in games",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True

    def test_middle_east_license_game_regulation_passes(self):
        article = {
            "title": "Qatar CRA regulation sets license requirements for online games",
            "summary": "The rule covers digital platforms and game content compliance",
            "tier": "official",
        }
        assert is_legislation_relevant(article) is True


class TestGdeltFallback:

    class FakeResponse:
        def __init__(self, status_code=200, articles=None, headers=None):
            self.status_code = status_code
            self._articles = articles or []
            self.headers = headers or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return {"articles": self._articles}

    def test_compact_query_set_has_three_daily_fallback_lanes(self):
        assert len(fetcher._GDELT_QUERIES) == 3

    def test_successful_query_returns_articles(self, monkeypatch):
        article = {
            "title": "FTC fines game company",
            "url": "https://example.com/story",
            "seendate": "20260714T010000Z",
            "domain": "example.com",
            "language": "English",
        }
        monkeypatch.setattr(fetcher.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(
            fetcher.requests,
            "get",
            lambda *args, **kwargs: self.FakeResponse(200, [article]),
        )

        result = fetcher.fetch_gdelt_all(daily_mode=True)

        assert len(result) == 3
        assert result[0]["lang"] == "en"
        assert result[0]["date"] == "2026-07-14"

    def test_daily_429_stops_immediately_without_blocking_other_sources(self, monkeypatch):
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(kwargs["params"]["query"])
            return self.FakeResponse(429, headers={"Retry-After": "1"})

        monkeypatch.setattr(fetcher.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(fetcher.requests, "get", fake_get)

        assert fetcher.fetch_gdelt_all(daily_mode=True) == []
        assert len(calls) == 1

    def test_weekly_429_retries_once_then_stops(self, monkeypatch):
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(kwargs["params"]["query"])
            return self.FakeResponse(429, headers={"Retry-After": "1"})

        monkeypatch.setattr(fetcher.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(fetcher.requests, "get", fake_get)

        assert fetcher.fetch_gdelt_all(daily_mode=False) == []
        assert len(calls) == 2
