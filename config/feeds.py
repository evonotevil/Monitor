"""数据源配置：RSS 订阅源与 Google News 搜索区域"""

# ─── RSS / 数据源 ────────────────────────────────────────────────────
#
# tier 字段标记信源权威层级（对应三层信源金字塔）:
#   "official" — 政府机构 / 监管机构官方公报（最高可信度）
#   "legal"    — 律所 / 法律情报机构（专业法律解读）
#   "industry" — 行业媒体 / 贸易协会（市场视角）
#
RSS_FEEDS = [
    # ── 平台官方 (Official tier) ─ 出海"宪法"级别 ──────────────────────
    {
        # Apple Developer News — App Store 政策、隐私框架、分级规则变更
        # 与 Android Developers Blog 同列 RECYCLED_DATE_SOURCES（日期需二次抓取）
        "name": "Apple Developer News",
        "url": "https://developer.apple.com/news/rss/news.rss",
        "lang": "en",
        "type": "rss",
        "region": "全球",
        "tier": "official",
    },

    # ── 行业媒体 (Industry tier) ──────────────────────────────────────
    {
        "name": "GamesIndustry.biz",
        "url": "https://www.gamesindustry.biz/feed",
        "lang": "en",
        "type": "rss",
        "region": "全球",
        "tier": "industry",
    },
    {
        "name": "Android Developers Blog",
        "url": "https://feeds.feedburner.com/blogspot/hsDu",
        "lang": "en",
        "type": "rss",
        "region": "全球",
        "tier": "industry",
    },

    # ── 官方公报 (Official tier) ──────────────────────────────────────
    {
        "name": "FTC News",
        "url": "https://www.ftc.gov/feeds/press-release-consumer-protection.xml",
        "lang": "en",
        "type": "rss",
        "region": "北美",
        "tier": "official",
    },
    # Federal Register (FTC) — 403 Forbidden，已移除；FTC 动态改由 site:ftc.gov OFFICIAL_SITE_QUERIES 覆盖
    {
        # 英国政府官方 Atom — Ofcom 发布的游戏/在线安全动态 (ICO RSS 已失效改用此源)
        "name": "UK Gov (Ofcom/Gaming)",
        "url": "https://www.gov.uk/search/news-and-communications.atom?keywords=gaming+online+safety&organisations%5B%5D=ofcom",
        "lang": "en",
        "type": "rss",   # fetcher 用 atom:entry 解析，兼容 Atom 格式
        "region": "欧洲",
        "tier": "official",
    },
    {
        # 英国政府官方 Atom — 儿童在线安全 (age verification / children act)
        "name": "UK Gov (Children Online Safety)",
        "url": "https://www.gov.uk/search/news-and-communications.atom?keywords=children+online+safety+age+verification",
        "lang": "en",
        "type": "rss",
        "region": "欧洲",
        "tier": "official",
    },

    # ── 法律情报 (Legal tier) ─────────────────────────────────────────
    # GDPR.eu News — 持续超时，已移除

    # ── 更多官方来源 (Official tier) ──────────────────────────────────
    {
        # EDPB — 欧盟数据保护委员会官方新闻（GDPR 执法、跨境数据传输、标准合同条款）
        "name": "EDPB News",
        "url": "https://www.edpb.europa.eu/rss.xml",
        "lang": "en",
        "type": "rss",
        "region": "欧洲",
        "tier": "official",
    },
    {
        # EU Digital Strategy — DSA/DMA/AI Act 官方通道（2026-03 验证有效，之前 malformed XML 已修复）
        "name": "EU Digital Strategy",
        "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",
        "lang": "en",
        "type": "rss",
        "region": "欧洲",
        "tier": "official",
    },
    {
        # 法国 CNIL — GDPR 执法、数据保护处罚决定（英文频道）
        "name": "CNIL (France)",
        "url": "https://cnil.fr/en/rss.xml",
        "lang": "en",
        "type": "rss",
        "region": "欧洲",
        "tier": "official",
    },
    {
        # 欧洲 PEGI — 游戏年龄评级标准更新和公告
        "name": "PEGI",
        "url": "https://pegi.info/rss.xml",
        "lang": "en",
        "type": "rss",
        "region": "欧洲",
        "tier": "official",
    },
    {
        # 加州 AG — CCPA 执法、消费者保护诉讼（之前仅靠 site:oag.ca.gov 查询覆盖）
        "name": "California AG",
        "url": "https://oag.ca.gov/news/feed",
        "lang": "en",
        "type": "rss",
        "region": "北美",
        "tier": "official",
    },
    {
        # 澳大利亚信息专员 OAIC — 隐私执法、数据泄露通知（之前 timeout 已移除，2026-03 验证恢复）
        "name": "OAIC (Australia)",
        "url": "https://oaic.gov.au/rss",
        "lang": "en",
        "type": "rss",
        "region": "大洋洲",
        "tier": "official",
    },
    # Australian eSafety Commissioner RSS — timeout，已移除
    # Canada Competition Bureau RSS — timeout，已移除
    # 新加坡 IMDA — 官方 RSS 已下线，由 Google News en_SG 关键词搜索替代

    # ── 更多行业媒体 (Industry tier) ──────────────────────────────────
    {
        "name": "Pocket Gamer",
        "url": "https://www.pocketgamer.biz/rss/",
        "lang": "en",
        "type": "rss",
        "region": "全球",
        "tier": "industry",
    },
    {
        # GamesBeat 已并入 VentureBeat，/category/games/feed/ 已失效
        "name": "GamesBeat",
        "url": "https://venturebeat.com/feed/",
        "lang": "en",
        "type": "rss",
        "region": "全球",
        "tier": "industry",
    },
    # IAPP RSS (iapp.org/rss/daily-dashboard) — 返回 0 条，已移除
]

# ─── Google News 搜索 ────────────────────────────────────────────────

GOOGLE_NEWS_SEARCH_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"

GOOGLE_NEWS_REGIONS = {
    # ── 英语圈 ──────────────────────────────────────────────────────
    "en_US": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
    "en_UK": {"hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    "en_AU": {"hl": "en-AU", "gl": "AU", "ceid": "AU:en"},
    "en_CA": {"hl": "en-CA", "gl": "CA", "ceid": "CA:en"},
    "en_SG": {"hl": "en",    "gl": "SG", "ceid": "SG:en"},
    "en_IN": {"hl": "en",    "gl": "IN", "ceid": "IN:en"},
    "en_PH": {"hl": "en",    "gl": "PH", "ceid": "PH:en"},
    "en_MY": {"hl": "en",    "gl": "MY", "ceid": "MY:en"},
    "en_ID": {"hl": "en",    "gl": "ID", "ceid": "ID:en"},
    # ── 亚洲 ──────────────────────────────────────────────────────
    "ja_JP": {"hl": "ja",    "gl": "JP", "ceid": "JP:ja"},
    "ko_KR": {"hl": "ko",    "gl": "KR", "ceid": "KR:ko"},
    "vi_VN": {"hl": "vi",    "gl": "VN", "ceid": "VN:vi"},
    "zh_TW": {"hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
    "th_TH": {"hl": "th",    "gl": "TH", "ceid": "TH:th"},
    # ── 欧洲 ──────────────────────────────────────────────────────
    "de_DE": {"hl": "de",    "gl": "DE", "ceid": "DE:de"},
    "fr_FR": {"hl": "fr",    "gl": "FR", "ceid": "FR:fr"},
    "nl_NL": {"hl": "nl",    "gl": "NL", "ceid": "NL:nl"},
    # ── 南美 ──────────────────────────────────────────────────────
    "pt_BR": {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"},
    "es_MX": {"hl": "es",    "gl": "MX", "ceid": "MX:es"},
    # ── 中东 ──────────────────────────────────────────────────────
    "ar_SA": {"hl": "ar",    "gl": "SA", "ceid": "SA:ar"},
}
