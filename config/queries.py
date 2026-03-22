"""查询配置：官方站点查询、降噪后缀、日报精选查询"""

# ─── Google News 查询增强 ─────────────────────────────────────────────
#
# 行业媒体降噪后缀：附加至所有英文通用查询末尾，
# 在查询层面过滤峰会 / 融资 / 投资类内容（比正则后置过滤更高效）
INDUSTRY_QUERY_NOISE_SUFFIX = " -conference -summit -funding -investment"

# 官方政府域名精准查询：site: 过滤，直接获取法律原文和处罚决定书
# 这些查询不添加降噪后缀（政府网站不发布融资/峰会内容）
OFFICIAL_SITE_QUERIES = [
    # ── 北美 ──────────────────────────────────────────────────────────
    "game regulation site:ftc.gov",
    "children privacy game site:ftc.gov",
    "game privacy site:oag.ca.gov",                        # 加州 AG
    # ── 欧洲 / 英国 ────────────────────────────────────────────────────
    "game online safety regulation site:gov.uk",
    "game age verification site:gov.uk",
    "game privacy fine site:ico.org.uk",                   # UK ICO（信息专员）
    "loot box game regulation site:cnil.fr",               # 法国 CNIL（已有 RSS，此查询作补充）
    "game Datenschutz site:bfdi.bund.de",                  # 德国联邦数据保护局
    "age rating criteria update site:pegi.info",           # 欧洲 PEGI 官方公告
    "game data protection site:edpb.europa.eu",            # 欧盟 EDPB
    "game DSA DMA AI Act site:digital-strategy.ec.europa.eu",  # EU 数字战略（已有 RSS，此查询作补充）
    # ── 亚太 ────────────────────────────────────────────────────────────
    "game regulation site:grac.or.kr",                     # 韩国 GRAC
    "game regulation site:moleg.go.kr",                    # 韩国法制处
    "game consumer site:kftc.go.kr",                       # 韩国公正交易委员会
    "game regulation site:mic.gov.vn",                     # 越南信息通信部
    "game regulation site:kominfo.go.id",                  # 印尼 Kominfo
    "game regulation site:pdpc.gov.sg",                    # 新加坡个人数据保护委员会
    "game regulation site:imda.gov.sg",                    # 新加坡 IMDA（媒体内容分级）
    "game regulation site:accc.gov.au",                    # 澳大利亚竞争与消费者委员会
    "game regulation site:oaic.gov.au",                    # 澳大利亚信息专员办公室
    "game online safety site:acma.gov.au",                 # 澳大利亚通信和媒体局
    "game regulation site:meity.gov.in",                   # 印度电子信息技术部
    # ── 日本 ────────────────────────────────────────────────────────────
    "ゲーム 規制 site:caa.go.jp",                            # 消費者庁
    "ゲーム OR ガチャ site:soumu.go.jp",                     # 総務省
    # ── 韩国 ────────────────────────────────────────────────────────────
    "게임 규제 site:grac.or.kr",                              # GRAC 游戏管理委员会
    "게임 site:kcc.go.kr",                                    # 放送通信委员会
    # ── 南美 ────────────────────────────────────────────────────────────
    "jogo regulação site:gov.br/anpd",                       # 巴西 ANPD
    "game regulation site:gob.mx",                            # 墨西哥政府
    # ── 东南亚补充 ──────────────────────────────────────────────────────
    "game regulation site:privacy.gov.ph",                    # 菲律宾 NPC
    "game regulation site:pdpc.or.th",                        # 泰国 PDPC
    # ── 中东 ────────────────────────────────────────────────────────────
    "game content license site:gcam.gov.sa",               # 沙特 GCAM（游戏内容许可）
    "game regulation site:tra.gov.ae",                     # 阿联酋 TRA
]

# ── 日报专用精选 Google News 查询（每日 daily_mode=True 时使用）────────────
# 设计原则：每条覆盖一个大类，用 OR 合并同类关键词，避免长尾细化查询。
# 目标总量 ≤ 20 条，2s 间隔共计 ≤ 40 秒，不触发 Google IP 限速。
# 周报模式仍使用全量 KEYWORDS 以获得最大覆盖。
DAILY_GOOGLE_NEWS_EN = [
    # 玩法合规（loot box / gacha / 概率）
    '"loot box" OR gacha regulation OR law OR ban OR fine',
    # 数据隐私（GDPR / CCPA / 跨境）
    'game (GDPR OR CCPA OR privacy) enforcement OR fine',
    # 未成年人保护（COPPA / KOSA / 年龄验证）
    'game (children OR minor OR COPPA OR KOSA) protection law',
    # 广告营销（暗黑模式 / 网红披露 / 虚假广告）
    'game advertising (disclosure OR "dark pattern" OR misleading) enforcement',
    # 消费者保护（退款 / 微交易 / 订阅）
    'game (refund OR "in-app purchase" OR microtransaction) consumer regulation',
    # 平台政策（App Store / DMA / 第三方支付）
    'game ("App Store" OR "Google Play" OR DMA OR "third party payment") regulation',
    # EU 数字法规（DSA / DMA / AI Act）
    'EU (DSA OR DMA OR "AI Act") game compliance',
    # AI 内容合规（深度合成 / 生成内容标识）
    'AI (deepfake OR "generated content" OR synthetic) game regulation',
    # 金融合规（制裁 / AML / 虚拟资产）
    'game (OFAC OR sanctions OR AML OR "virtual asset") compliance',
    # 亚洲（韩国 / 东南亚）监管动态
    '(Korea OR Vietnam OR Indonesia OR Thailand OR Philippines) game regulation OR law',
    # 日本监管动态（英文媒体对日本的报道）
    'Japan game (regulation OR law OR "age rating" OR gacha OR privacy)',
    # 南美监管动态
    '(Brazil OR Mexico OR Argentina) game (regulation OR law OR LGPD OR privacy)',
    # 澳大利亚 / 大洋洲
    '(Australia OR "New Zealand") game (online safety OR privacy OR regulation)',
    # 经营合规（本地代理 / 许可证）
    'game ("local agent" OR license OR representative) regulation overseas publisher',
    # 年龄分级（PEGI / ESRB / 各国评级）
    'game age (rating OR verification) regulation law',
]

# 日报非英文精选（日韩各 2-3 条，重点覆盖本地监管机构动态）
DAILY_GOOGLE_NEWS_JA = [
    "ゲーム 規制 法律 OR 法案 OR 処分",
    "消費者庁 OR ガチャ OR 景品表示法 ゲーム 規制",
    "ステルスマーケティング OR AI規制 ゲーム 法律",
]
DAILY_GOOGLE_NEWS_KO = [
    "게임 규제 법안 OR 처분 OR 의무",
    "확률형 아이템 OR 게임산업진흥법 OR 대리인 규제",
]

# 日报东南亚/南美精选（补充薄弱地区的日常覆盖）
DAILY_GOOGLE_NEWS_VI = [
    "trò chơi điện tử quy định OR nghị định OR luật",
]
DAILY_GOOGLE_NEWS_PT = [
    "jogo regulação OR lei OR LGPD OR proteção",
]
DAILY_GOOGLE_NEWS_TH = [
    "เกม กฎหมาย OR ระเบียบ OR PDPA",
]
