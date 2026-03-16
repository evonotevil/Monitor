"""
全球游戏行业立法动态监控工具 - 配置文件
面向中资手游出海合规视角 (以原神/Lilith/鹰角发行模式为参考)
重点覆盖: 数据隐私、玩法合规(开箱/抽卡/概率公示)、广告营销合规、涉赌合规、
         未成年保护(防沉迷)、消费者保护(虚拟货币/三方充值)、
         经营合规(本地代理/代表处/分级)、PC平台合规(Steam/Epic/驱动级反作弊/D2C)
"""

# ─── 重点监控区域（不含中国大陆）──────────────────────────────────────
#
# ⚠️  注意：MONITORED_REGIONS 和 REGION_DISPLAY_ORDER 是「纯文档字段」，
#    不被任何功能代码读取，仅供人工参考。
#    实际抓取覆盖范围由下方 KEYWORDS 字典决定（Google News 搜索词）。
#    如需新增某个国家/地区的抓取，请在 KEYWORDS 里添加对应搜索词，
#    而非修改 MONITORED_REGIONS。
#    区域显示分组的配置在 utils.py（_REGION_GROUP_MAP / _GROUP_ORDER）。
#
MONITORED_REGIONS = {
    "欧洲": {
        "countries": ["欧盟", "英国", "德国", "法国", "荷兰", "比利时", "奥地利", "意大利", "西班牙", "波兰", "瑞典", "挪威"],
        "focus": ["GDPR", "DSA", "DMA", "AI法案", "Loot Box", "Online Safety Act", "消费者保护"],
    },
    "北美": {
        "countries": ["美国", "加拿大", "墨西哥"],
        "focus": ["FTC执法", "COPPA", "CCPA", "KIDS Act", "Loot Box", "各州隐私法", "未成年保护"],
    },
    "南美": {
        "countries": ["巴西", "阿根廷", "智利", "哥伦比亚"],
        "focus": ["LGPD", "消费者保护", "游戏税务", "内容分级", "广告合规"],
    },
    "东南亚": {
        "countries": ["越南", "印度尼西亚", "泰国", "菲律宾", "马来西亚", "新加坡"],
        "focus": ["本地代理制度", "IGAC评级", "游戏许可", "PDPA", "本地代表处", "本地注册", "发行商资质"],
    },
    "南亚": {
        "countries": ["印度", "巴基斯坦", "孟加拉国"],
        "focus": ["DPDPA", "游戏禁令", "在线游戏监管", "GST税务", "数字税"],
    },
    "港澳台": {
        "countries": ["香港", "澳门", "台湾"],
        "focus": ["个资法", "游戏分级", "消费者保护", "未成年保护"],
    },
    "日本": {
        "countries": ["日本"],
        "focus": ["景品表示法", "资金決済法", "CERO分级", "特商法", "ガチャ規制", "未成年保护"],
    },
    "韩国": {
        "countries": ["韩国"],
        "focus": ["游戏产业振兴法", "确率型道具", "GRAC分级", "代理人制度", "青少年保护法", "海外游戏本地代理"],
    },
    "大洋洲": {
        "countries": ["澳大利亚", "新西兰"],
        "focus": ["Online Safety Act", "Privacy Act", "Age Verification", "Loot Box", "未成年保护"],
    },
    "中东/非洲": {
        "countries": ["沙特", "阿联酋", "土耳其", "尼日利亚", "南非"],
        "focus": ["内容监管", "游戏许可", "数据保护", "本地化要求"],
    },
}

REGION_DISPLAY_ORDER = [
    "欧洲", "北美", "南美", "东南亚", "南亚", "港澳台", "日本", "韩国", "大洋洲", "中东/非洲",
]

# ─── 一级分类 / 二级分类 (围绕手游出海合规) ─────────────────────────────

CATEGORIES = {
    "数据隐私": [
        "GDPR合规",
        "CCPA/各州隐私法",
        "儿童隐私(COPPA)",
        "跨境数据传输",
        "数据本地化",
        "数据泄露通知",
        "韩国PIPA合规",
        "日本APPI合规",
        "印度DPDP法案",
        "沙特PDPL合规",
        "泰国PDPA合规",
        "巴西LGPD合规",
    ],
    "玩法合规": [
        "抽奖/开箱(Loot Box)",
        "概率公示",
        "虚拟货币",
        "付费随机机制",
        "涉赌认定",
        "游戏内购规范",
        "日本完全ガチャ禁令",
        "荷兰/比利时赌博局认定",
        "韩国概率型道具强制公示",
    ],
    "未成年人保护": [
        "年龄验证/分级",
        "未成年消费限制",
        "游戏时长限制",
        "内容分级制度",
        "家长控制",
        "防沉迷系统",
        "英国儿童隐私设计规范(Children's Code)",
        "美国KOSA立法动态",
        "欧盟GDPR未成年同意年龄",
    ],
    "广告营销合规": [
        "虚假广告",
        "营销披露",
        "网红/KOL合规",
        "价格透明度",
        "暗黑模式",
        "促销活动合规",
        "日本景品表示法/ステマ禁令",
        "澳大利亚广告标准",
    ],
    "消费者保护": [
        "退款政策",
        "订阅自动续费",
        "价格歧视",
        "消费者权益诉讼",
        "虚假宣传",
        "澳大利亚ACL合规",
        "韩国消费者保护法",
    ],
    "经营合规": [
        "本地代理/代表处",
        "游戏许可/牌照",
        "本地分级注册",
        "税务合规",
        "外资限制",
        "本地发行商要求",
        "中东游戏内容许可(GCAM/TRA)",
        "印度外资规定",
        "俄罗斯RKN本地化要求",
    ],
    "平台政策": [
        "App Store政策",
        "Google Play政策",
        "第三方支付",
        "佣金/分成",
        "侧载政策",
        "欧盟DMA对应用商店影响",
        "Epic/Steam PC平台政策",
    ],
    "内容监管": [
        "内容审查",
        "AI生成内容",
        "知识产权保护",
        "版权合规",
        "欧盟DSA(数字服务法)",
        "德国NetzDG",
        "澳大利亚在线安全法",
    ],
    # PC 与跨平台合规 — 针对 Steam/Epic/驱动级反作弊/D2C/三方充值等 PC 端风险
    "PC & 跨平台合规": [
        "PC启动器权限",
        "反作弊程序合规",
        "PC充值/D2C合规",
        "跨平台数据合规",
    ],
    # AI 内容合规 — EU AI Act / 深度合成 / 算法推荐透明度
    "AI内容合规": [
        "EU AI Act合规(高风险/通用AI分类)",
        "AI生成内容标识义务",
        "深度合成/虚拟数字人合规",
        "AI算法推荐透明度",
        "各国AI监管立法动态",
    ],
    # 金融合规与支付 — OFAC制裁 / AML / 虚拟资产 / 跨境支付
    "金融合规与支付": [
        "跨境支付合规",
        "OFAC制裁合规",
        "反洗钱/反恐融资(AML/CTF)",
        "虚拟资产/游戏币监管",
        "第三方支付牌照要求",
        "自动续费透明度",
    ],
}

# ─── 状态标签 ───────────────────────────────────────────────────────

STATUS_LABELS = [
    "已生效",
    "即将生效",
    "草案/征求意见",
    "立法进行中",
    "已提案",
    "修订变更",
    "已废止",
    "执法动态",
    "立法动态",
]

# ─── 搜索关键词库 (聚焦手游出海合规 - 以原神发行方式为参考) ──────────────────

# ─── PC 平台合规关键词（独立导出，供 fetcher 路由使用）────────────────────────
#
# 覆盖米哈游/Lilith/鹰角等中资游戏在 PC 端的合规风险：
#   Steam / Epic Games Store 政策变更、驱动级反作弊隐私争议、
#   D2C（绕开平台直销）监管、三方充值平台合规。
#
PC_PLATFORM_KEYWORDS_EN = [
    # Steam / Epic / PC 启动器（精确短语 Boolean 查询）
    'Steam "alternative payment" (regulation OR ban OR law)',
    'Steam game (regulation OR ban OR privacy) consumer',
    'Epic Store OR "Epic Games Store" "Terms of Service" (game OR compliance)',
    '"Epic Games Store" policy (loot box OR regulation OR law)',
    '"PC Launcher" privacy (data collection OR regulation OR law)',
    "PC game launcher privacy data collection law",
    "PC game DRM consumer regulation",
    # 驱动级反作弊（精确短语）
    '"kernel-level anti-cheat" (regulation OR privacy OR ban)',
    "kernel-level anti-cheat privacy regulation",
    "game anti-cheat driver ban restriction consumer",
    # D2C 直销渠道
    "D2C game distribution regulation publisher",
    "direct-to-consumer game platform law",
    # 三方充值
    "third-party top-up game consumer protection regulation",
    "game top-up platform ban restriction",
    # 游戏分级机构 — PC 端延伸（ESRB/PEGI 对 Steam 上架内容的影响）
    "ESRB rating requirement PC game Steam regulation",
    "PEGI age rating PC game regulation Europe",
    "PEGI age rating criteria update Europe regulation",
]

KEYWORDS = {
    "en": [
        # === 玩法合规 / Loot Box / Gacha（Boolean 查询，无硬编码年份）===
        # 动态时效由 fetcher 附加 when:Xd 处理
        '"loot box" (regulation OR law OR ban OR enforcement OR fine)',
        '"loot box" OR gacha gambling classification game',
        '"probability disclosure" (game OR gacha OR "loot box") law',
        '("pay to win" OR "randomized purchase") game (regulation OR ban)',
        '"virtual goods" OR "in-game currency" gambling law game',
        '"in-game currency" consumer protection regulation',

        # === 未成年人保护 ===
        "children online safety act game",
        "COPPA game enforcement",
        "FTC children game fine",
        "game age verification law",
        "minor gaming restriction law",
        "game age rating regulation",
        "children game spending limit law",
        "kids game addiction law",
        "minor game purchase restriction",
        "parental control mobile game law",
        "teen online gaming curfew",
        '"Kids Online Safety Act" game',
        "KOSA game minor protection legislation",
        "GDPR minor consent age game",
        "UK Children Code game app",

        # === 数据隐私 ===
        "GDPR game enforcement",
        "GDPR mobile game fine",
        "CCPA game privacy law",
        "game data privacy law",
        "children data protection game app",
        "game app privacy regulation",
        "cross-border data transfer game",
        "data localization mobile game",
        "game player data protection fine",

        # === 广告营销合规 ===
        "game advertising regulation law",
        "misleading game advertising enforcement",
        "dark pattern game ban regulation",
        "influencer game advertising disclosure law",
        "game marketing compliance regulation",
        "deceptive game advertising fine",
        "mobile game promotion regulation",
        "game streamer sponsorship disclosure",

        # === 消费者保护 ===
        "in-app purchase regulation consumer",
        "game microtransaction consumer protection law",
        "game refund regulation law",
        "subscription auto-renewal game law",
        "game consumer protection enforcement",
        "virtual currency consumer protection",
        "game overcharge consumer fine",
        "mobile game subscription regulation",

        # === 经营合规 - 本地代理 / 代表处 / 许可 (东南亚重点) ===
        "Korea game local agent representative law",
        "Korea game industry promotion act amendment",
        "Korea foreign game publisher local agent",
        "Vietnam game license local agent requirement",
        "Vietnam game operation permit publisher",
        "Vietnam Ministry of Information game regulation",
        "Vietnam Decree game mobile publisher",
        "Indonesia game rating IGAC requirement",
        "Indonesia game publisher local registration",
        "Indonesia game operator local entity",
        "Indonesia Ministry game regulation Kominfo",
        "Thailand game regulation PDPA publisher",
        "Philippines game regulation publisher NTC",
        "Malaysia game regulation MCMC publisher",
        "Malaysia Communications game content classification",
        "Singapore game rating IMDA requirement",
        "India online gaming regulation GST",
        "India online gaming intermediary rules",
        "game publisher local representative requirement overseas",
        "foreign mobile game developer local entity requirement",
        "game operation license overseas developer",
        "mobile game local publisher license Southeast Asia",
        "game app store local representative requirement",

        # === 欧洲特定 ===
        "UK online safety act game age verification",
        "EU digital services act game platform",
        "DSA game compliance",
        "DMA app store game regulation",
        "EU AI act game",
        "EU AI Act high risk general purpose game",
        "EU loot box regulation",
        "Netherlands Belgium loot box ban game",
        "NetzDG game platform Germany",

        # === 澳大利亚 / 大洋洲 ===
        "Australia game loot box age verification",
        "Australia online safety act game",
        "Australia Privacy Act game",
        "Australian Consumer Law game refund",
        "Australia advertising standards game",
        "ACCC game consumer enforcement",

        # === 平台政策 ===
        "app store regulation game DMA antitrust",
        "google play policy game change",
        "apple app store game policy",
        "third party payment game regulation",
        "app store commission game fee regulation",

        # === AI 内容合规 ===
        "AI generated content game regulation",
        "AI deepfake game avatar regulation",
        "AI recommendation algorithm game transparency law",
        "synthetic media game regulation disclosure",
        "AI content labeling game law",

        # === 金融合规与支付 ===
        "OFAC gaming sanctions compliance",
        "game company sanctions fine",
        "AML game virtual currency regulation",
        "anti-money laundering game payment",
        "cross-border payment game regulation",
        "virtual asset game currency regulation",
        "third-party payment license game",
        "India DPDP gaming data protection",
        "India FDI game foreign investment regulation",

        # === PC 平台合规 (Steam / Epic / D2C / 驱动级反作弊) ===
        # 注: 该段由 PC_PLATFORM_KEYWORDS_EN 导入，fetcher 会对其单独做 UK/EU 路由
        *PC_PLATFORM_KEYWORDS_EN,
    ],
    "ja": [
        "ゲーム規制 法律",
        "ガチャ規制 法案 改正",
        "未成年者 ゲーム 規制",
        "景品表示法 ガチャ 処分",
        "資金決済法 ゲーム 改正",
        "特商法 ゲーム アプリ",
        "スマートフォンゲーム 課金 規制",
        "消費者庁 ゲーム 処分 罰則",
        "子ども ゲーム 利用 規制",
        "ゲーム 個人情報 保護 規制",
        # 消費者庁 / CESA 专项 — 景表法与抽卡规则（无硬编码年份）
        "消費者庁 ゲーム 景品表示法 処分",
        "消費者庁 ガチャ 確率 規制 改正",
        "CESA ゲーム 自主規制 ガチャ 改正",
        # ステマ / AI 规制
        "ステルスマーケティング ゲーム 規制 景品表示法",
        "AI 規制 ゲームコンテンツ 法律",
        "ゲーム AI 生成 コンテンツ 規制",
    ],
    "ko": [
        "게임 규제 법안",
        "확률형 아이템 규제 법안",
        "게임산업진흥법 개정",
        "미성년자 게임 규제 법률",
        "게임 대리인 제도 해외",
        "해외 게임사 국내 대리인",
        "게임 소비자 보호 법안",
        "게임 등급 분류 의무",
        "청소년 게임 이용 제한 법률",
        "게임 광고 규제 법안",
        # GRAC（게임물관리위원회）专项 — 关注确率型道具罚单（无硬编码年份）
        "게임물관리위원회 확률형 처분 제재",
        "GRAC 게임 등급 규제 제재",
        "확률형 아이템 과징금 처분 게임사",
        # 개인정보보호위원회 / 소비자보호 细化
        "개인정보보호위원회 게임 처분 제재",
        "확률형 아이템 공시 의무 게임사",
        "게임 소비자 분쟁 조정 법률",
    ],
    "vi": [
        "quy định trò chơi điện tử",
        "luật game mobile đại lý nước ngoài",
        "nghị định trò chơi điện tử",
        "Bộ Thông tin Truyền thông game",
        "Bộ Thông tin và Truyền thông game di động",
        "bảo vệ dữ liệu cá nhân trò chơi điện tử",
    ],
    "id": [
        "regulasi game mobile Indonesia",
        "penerbit game lokal Indonesia",
        "IGAC rating game mobile",
        "Kominfo regulasi game",
        "Kemenkominfo penerbit game asing",
        "perlindungan data pribadi game aplikasi",
    ],
    "de": [
        # 德语 - 德国/奥地利（无硬编码年份）
        "Spieleregulierung Gesetz",
        "Lootboxen Regulierung Deutschland",
        "Jugendschutz Videospiele Gesetz",
        "Datenschutz Mobile Games DSGVO",
        "Glücksspiel Videospiele Regulierung",
        "Onlinespiele Minderjährige Gesetz",
        "Spielsucht Gesetz Jugendschutz",
        "NetzDG Spieleplattform Inhalt Regulierung",
        "KI-Gesetz Videospiele Regulierung",
    ],
    "fr": [
        # 法语 - 法国/比利时（无硬编码年份）
        "réglementation loot box jeu vidéo",
        "protection mineurs jeux vidéo loi",
        "RGPD jeux mobiles France",
        "jeu vidéo régulation loi",
        "microtransactions jeux vidéo loi",
        "jeux mobiles mineurs protection loi",
        "dark pattern jeux vidéo France",
        "DSA jeux vidéo plateforme régulation",
        "loi IA jeux vidéo contenu généré",
    ],
    "pt": [
        # 葡萄牙语 - 巴西（无硬编码年份）
        "regulação jogos mobile Brasil",
        "LGPD jogos eletrônicos aplicativo",
        "lei loot box jogo online",
        "proteção menores jogos mobile Brasil",
        "regulamentação jogos SENACON Brasil",
        "jogos mobile privacidade crianças lei",
        "microtransação jogo regulação Brasil",
        "proteção de dados pessoais jogo aplicativo",
    ],
    "es": [
        # 西班牙语 - 墨西哥/西班牙/拉美（无硬编码年份）
        "regulación loot box videojuegos ley",
        "ley protección menores videojuegos España",
        "regulación videojuegos consumidor México",
        "privacidad datos videojuegos menores",
        "regulación juegos móviles",
        "microtransacciones videojuegos ley",
        "juegos online regulación España",
        "protección al consumidor videojuegos reembolso",
        "privacidad de datos juegos móviles regulación",
    ],
    "zh_tw": [
        # 繁体中文 - 台湾/港澳（无硬编码年份）
        "遊戲法規 台灣",
        "遊戲內購 消費者保護 法規",
        "未成年 遊戲 保護法 台灣",
        "個資法 遊戲 App 台灣",
        "遊戲分級 法規 台灣",
        "手機遊戲 廣告 規範",
        "抽獎合規 遊戲 法規",
        "未成年保護 手遊 法律 香港",
    ],
    "th": [
        # 泰语（无硬编码年份）
        "กฎหมายเกมมือถือ ไทย",
        "PDPA เกมออนไลน์ ไทย",
        "ระเบียบเกมมือถือ ผู้เยาว์",
        "คุ้มครองผู้บริโภค เกมออนไลน์ กฎหมาย",
        "คุ้มครองข้อมูลส่วนบุคคล เกม แอป",
        "ผู้เยาว์ เกมออนไลน์ กฎหมาย ไทย",
    ],
    "ar": [
        # 阿拉伯语 - 沙特/阿联酋（无硬编码年份）
        "تنظيم ألعاب الجوال السعودية",
        "قانون ألعاب الفيديو الإمارات",
        "حماية الأطفال ألعاب إلكترونية",
        "صناديق الغنائم لعبة قانون",
        "خصوصية البيانات ألعاب الجوال",
        "ترخيص الألعاب الإلكترونية GCAM السعودية",
        "هيئة الاتصالات والفضاء ألعاب تنظيم الإمارات",
    ],
}

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
    # EU Digital Strategy RSS (digital-strategy.ec.europa.eu) — malformed XML，已移除；改用 OFFICIAL_SITE_QUERIES site: 查询替代
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

# ─── 信源权威层级映射 ─────────────────────────────────────────────────
#
# 用于影响评分: official > legal > industry > news
# get_source_tier() 先精确匹配 SOURCE_TIER_MAP，再用 SOURCE_TIER_PATTERNS 模糊匹配
#
SOURCE_TIER_MAP = {
    # ── official ──────────────────────────────────────────────────────
    "FTC News":                       "official",
    "Federal Register (FTC)":         "official",
    "ICO News (UK)":                  "official",
    "UK Gov (Ofcom/Gaming)":          "official",
    "UK Gov (Children Online Safety)":"official",
    "CNIL":                           "official",
    "Korean MOLEG":                   "official",
    "GRAC":                           "official",
    "KCA":                            "official",
    "GDPR.eu News":                   "official",   # 官方解读机构
    "EDPB News":                      "official",   # 欧盟数据保护委员会
    # 游戏分级机构 — PC 平台合规关键信源
    "ESRB":                           "official",
    "PEGI":                           "official",
    "CESA":                           "official",   # 日本コンピュータエンターテインメント協会
    "消費者庁":                        "official",   # 日本消費者庁
    # 平台官方 — 出海"宪法"
    "Apple Developer News":           "official",
    # ── legal ─────────────────────────────────────────────────────────
    "IAPP News":                      "legal",
    "IAPP":                           "legal",
    "Lexology":                       "legal",
    "JD Supra":                       "legal",
    "Law360":                         "legal",
    # ── industry ──────────────────────────────────────────────────────
    "GamesIndustry.biz":              "industry",
    "Android Developers Blog":        "industry",
    "GamesBeat":                      "industry",
    "Kotaku":                         "industry",
    "Polygon":                        "industry",
    "Eurogamer":                      "industry",
    "PC Gamer":                       "industry",
    "IGN":                            "industry",
    "ISFE":                           "industry",
    "ESA":                            "industry",
}

# Google News 源名称模糊匹配（按优先级从高到低）
SOURCE_TIER_PATTERNS = [
    ("official", (
        r"\bFTC\b|\bFederal Trade Commission\b"
        r"|Information Commissioner(?:'s Office)?"
        r"|\bCNIL\b|\bICO\b|\beSafety\b"
        r"|\bGRAC\b|\b게임물관리위원회\b|\bKCA\b|\bMOLEG\b"
        r"|\bESRB\b|\bPEGI\b|\bCESA\b"
        r"|消費者庁|게임물관리위원회"
        r"|Federal Register"
        r"|Ministry of (?:Culture|Information|Communication|Justice)"
        r"|Kominfo|KemenKominfo"
        r"|MIC.*Viet|Bộ Thông tin"
        r"|Senado|Senaat|Bundestag|Parliament"
        r"|Consumer Financial Protection"
        r"|Attorney General"
        r"|Data Protection Authority|Data Protection Board"
        r"|Office of (?:the |)Privacy Commissioner"
        r"|Apple Developer"
    )),
    ("legal", (
        r"\bIAPP\b|Lexology|JD Supra|Law360"
        r"|Baker McKenzie|Latham & Watkins|White & Case"
        r"|Clifford Chance|Dentons|Covington"
        r"|law firm|law office|legal (?:news|update|alert)"
        r"|counsel|attorney|solicitor"
    )),
    ("industry", (
        r"GamesIndustry|GamesBeat|Kotaku|Polygon|Eurogamer"
        r"|PC Gamer|\bIGN\b|\bISFE\b|\bESA\b"
        r"|game.*industry|gaming.*media|game.*news"
    )),
]

# ─── 输出配置 ─────────────────────────────────────────────────────────

OUTPUT_DIR = "reports"
DATABASE_PATH = "data/monitor.db"
MAX_ARTICLE_AGE_DAYS = 90
FETCH_TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 5

# 周报/月报对应天数
PERIOD_DAYS = {
    "week":  7,
    "month": 30,
    "all":   90,
}

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
    "loot box game regulation site:cnil.fr",               # 法国 CNIL
    "game Datenschutz site:bfdi.bund.de",                  # 德国联邦数据保护局
    "age rating criteria update site:pegi.info",           # 欧洲 PEGI 官方公告
    "game data protection site:edpb.europa.eu",            # 欧盟 EDPB
    "game DSA DMA AI Act site:digital-strategy.ec.europa.eu",  # EU 数字战略（DSA/DMA/AI Act）
    # ── 亚太 ────────────────────────────────────────────────────────────
    "game regulation site:grac.or.kr",                     # 韩国 GRAC
    "game regulation site:moleg.go.kr",                    # 韩국法制处
    "game consumer site:kftc.go.kr",                       # 韩国公正交易委员会
    "game regulation site:mic.gov.vn",                     # 越南信息通信部
    "game regulation site:kominfo.go.id",                  # 印尼 Kominfo
    "game regulation site:pdpc.gov.sg",                    # 新加坡个人数据保护委员会
    "game regulation site:imda.gov.sg",                    # 新加坡 IMDA（媒体内容分级）
    "game regulation site:accc.gov.au",                    # 澳大利亚竞争与消费者委员会
    "game regulation site:oaic.gov.au",                    # 澳大利亚信息专员办公室
    "game online safety site:acma.gov.au",                 # 澳大利亚通信和媒体局
    "game regulation site:meity.gov.in",                   # 印度电子信息技术部
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

