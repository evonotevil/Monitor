"""
全球游戏行业立法动态监控工具 - 配置文件
面向中资手游出海合规视角 (以原神/Lilith/鹰角发行模式为参考)
重点覆盖: 数据隐私、玩法合规(开箱/抽卡/概率公示)、广告营销合规、涉赌合规、
         未成年保护(防沉迷)、消费者保护(虚拟货币/三方充值)、
         经营合规(本地代理/代表处/分级)、PC平台合规(Steam/Epic/驱动级反作弊/D2C)
"""

from config.regions import MONITORED_REGIONS, REGION_DISPLAY_ORDER
from config.categories import CATEGORIES, STATUS_LABELS
from config.keywords import PC_PLATFORM_KEYWORDS_EN, KEYWORDS, DIGITAL_INDUSTRY_SIGNALS
from config.feeds import RSS_FEEDS, GOOGLE_NEWS_SEARCH_TEMPLATE, GOOGLE_NEWS_REGIONS
from config.sources import SOURCE_TIER_MAP, SOURCE_TIER_PATTERNS
from config.settings import (
    OUTPUT_DIR, DATABASE_PATH, MAX_ARTICLE_AGE_DAYS,
    FETCH_TIMEOUT, MAX_CONCURRENT_REQUESTS, PERIOD_DAYS,
)
from config.queries import (
    INDUSTRY_QUERY_NOISE_SUFFIX, OFFICIAL_SITE_QUERIES,
    DAILY_GOOGLE_NEWS_EN, DAILY_GOOGLE_NEWS_JA, DAILY_GOOGLE_NEWS_KO,
    DAILY_GOOGLE_NEWS_VI, DAILY_GOOGLE_NEWS_PT, DAILY_GOOGLE_NEWS_TH,
)
