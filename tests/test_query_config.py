"""
查询配置回归测试
覆盖：新增弱覆盖地区的官方 site 查询和日报精选查询不被误删。
"""

from config.queries import (
    DAILY_GOOGLE_NEWS_AR,
    DAILY_GOOGLE_NEWS_DE,
    DAILY_GOOGLE_NEWS_EN,
    DAILY_GOOGLE_NEWS_ES,
    DAILY_GOOGLE_NEWS_FR,
    DAILY_GOOGLE_NEWS_ID,
    DAILY_GOOGLE_NEWS_JA,
    DAILY_GOOGLE_NEWS_KO,
    DAILY_GOOGLE_NEWS_PT,
    DAILY_GOOGLE_NEWS_TH,
    DAILY_GOOGLE_NEWS_VI,
    DAILY_GOOGLE_NEWS_ZH_TW,
    DAILY_LANGUAGE_PROFILES,
    OFFICIAL_SITE_QUERIES,
)
from config.feeds import GOOGLE_NEWS_REGIONS, RSS_FEEDS


def _joined(values: list[str]) -> str:
    return "\n".join(values).lower()


def test_official_site_queries_cover_expanded_regions():
    text = _joined(OFFICIAL_SITE_QUERIES)
    for expected in [
        "priv.gc.ca",
        "competition-bureau.canada.ca",
        "meity.gov.in",
        "pcpd.org.hk",
        "moda.gov.tw",
        "argentina.gob.ar/aaip",
        "sernac.cl",
        "sic.gov.co",
        "cra.gov.qa",
        "citra.gov.kw",
        "tra.org.bh",
        "gov.il",
        "komdigi.go.id",
        "gov.br/mj",
        "gov.br/cade",
    ]:
        assert expected in text


def test_broken_rss_feeds_removed_with_query_or_feed_fallbacks():
    feed_names = {feed["name"] for feed in RSS_FEEDS}
    assert not {
        "EUR-Lex Legislation",
        "GDPRHub",
        "JD Supra (Consumer Protection)",
        "Brazil ANPD",
    } & feed_names
    assert {"EU Digital Strategy", "EDPB News", "noyb", "JD Supra (Privacy)"} <= feed_names
    assert "gov.br/anpd" in _joined(OFFICIAL_SITE_QUERIES)
    assert "anpd" in _joined(DAILY_GOOGLE_NEWS_PT)


def test_daily_queries_use_four_lanes_in_every_supported_language():
    query_sets = [
        DAILY_GOOGLE_NEWS_EN, DAILY_GOOGLE_NEWS_JA, DAILY_GOOGLE_NEWS_KO,
        DAILY_GOOGLE_NEWS_VI, DAILY_GOOGLE_NEWS_ID, DAILY_GOOGLE_NEWS_PT,
        DAILY_GOOGLE_NEWS_TH, DAILY_GOOGLE_NEWS_ZH_TW, DAILY_GOOGLE_NEWS_AR,
        DAILY_GOOGLE_NEWS_DE, DAILY_GOOGLE_NEWS_FR, DAILY_GOOGLE_NEWS_ES,
    ]
    for queries in query_sets:
        assert len(queries) == 4
        assert "app store" in queries[2].lower()
        assert "google play" in queries[2].lower()
        company_lane = queries[3].lower()
        for company in ["lilith games", "hoyoverse", "kuro games", "riot games", "activision"]:
            assert company in company_lane

    assert set(DAILY_LANGUAGE_PROFILES) == {
        "en", "ja", "ko", "vi", "id", "pt", "th", "zh_tw", "ar", "de", "fr", "es",
    }
    assert all(len(profile["queries"]) == 4 for profile in DAILY_LANGUAGE_PROFILES.values())
    assert all(profile["game_terms"] for profile in DAILY_LANGUAGE_PROFILES.values())
    assert all(profile["filter_game_terms"] for profile in DAILY_LANGUAGE_PROFILES.values())
    assert all(profile["regulatory_terms"] for profile in DAILY_LANGUAGE_PROFILES.values())


def test_daily_queries_keep_named_local_regulations():
    assert "pp tunas" in _joined(DAILY_GOOGLE_NEWS_ID)
    assert "147/2024" in _joined(DAILY_GOOGLE_NEWS_VI)
    assert "174/2026" in _joined(DAILY_GOOGLE_NEWS_VI)
    assert "senacon" in _joined(DAILY_GOOGLE_NEWS_PT)
    assert "遊戲" in _joined(DAILY_GOOGLE_NEWS_ZH_TW)


def test_indonesia_uses_local_language_google_news():
    indonesia = GOOGLE_NEWS_REGIONS["id_ID"]
    assert indonesia["hl"] == "id"
    assert indonesia["gl"] == "ID"
    assert indonesia["ceid"] == "ID:id"
    assert indonesia["region"] == "东南亚"


def test_local_language_regions_have_classifier_hints():
    expected = {
        "ja_JP": "日本",
        "ko_KR": "韩国",
        "vi_VN": "东南亚",
        "zh_TW": "港澳台",
        "th_TH": "东南亚",
        "pt_BR": "南美",
        "ar_SA": "中东/非洲",
        "de_DE": "欧洲",
        "fr_FR": "欧洲",
        "es_MX": "北美",
    }
    for locale, region in expected.items():
        assert GOOGLE_NEWS_REGIONS[locale]["region"] == region
