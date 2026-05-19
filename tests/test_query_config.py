"""
查询配置回归测试
覆盖：新增弱覆盖地区的官方 site 查询和日报精选查询不被误删。
"""

from config.queries import (
    DAILY_GOOGLE_NEWS_AR,
    DAILY_GOOGLE_NEWS_EN,
    OFFICIAL_SITE_QUERIES,
)


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
    ]:
        assert expected in text


def test_daily_queries_cover_expanded_regions():
    en_text = _joined(DAILY_GOOGLE_NEWS_EN)
    ar_text = _joined(DAILY_GOOGLE_NEWS_AR)

    for expected in ["canada", "india", "hong kong", "taiwan", "qatar", "kuwait", "bahrain", "israel"]:
        assert expected in en_text

    for expected in ["قطر", "الكويت", "البحرين"]:
        assert expected in ar_text
