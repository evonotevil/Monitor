"""搜索关键词库：多语言搜索关键词（聚焦手游出海合规）"""

# ─── 数字行业信号词（官方/法律信源宽松过滤用）────────────────────────────
#
# 官方监管机构（如消費者庁、FTC、OAIC）发布的内容不要求包含严格的"游戏"关键词，
# 但必须至少与数字/互联网行业相关，避免传统行业监管新闻（食品、通信贩卖等）混入。
#
# 纯字符串匹配（小写化后 in text_lower），无需正则语法，方便维护。
# 添加新词只需追加一行字符串即可。
#
DIGITAL_INDUSTRY_SIGNALS = [
    # ── 英语 ──
    "game", "gaming", "video game", "mobile game",
    "app", "application", "mobile app",
    "online", "internet", "digital", "software", "platform",
    "streaming", "e-commerce", "ecommerce",
    "in-app", "iap", "microtransaction", "loot box", "gacha",
    "virtual", "metaverse", "nft", "crypto", "blockchain",
    "ai", "artificial intelligence", "algorithm",
    "social media", "user-generated", "ugc",
    "app store", "google play", "steam", "playstation", "xbox", "nintendo",
    "esports", "e-sports",
    # ── 日语 ──
    "ゲーム", "アプリ", "オンライン", "インターネット", "デジタル",
    "ソフトウェア", "プラットフォーム", "課金", "ガチャ",
    "未成年", "sns", "人工知能", "電子商取引",
    "ストリーミング", "コンテンツ",
    # ── 韩语 ──
    "게임", "앱", "온라인", "인터넷", "디지털",
    "소프트웨어", "플랫폼", "과금", "미성년",
    "콘텐츠", "전자상거래",
    # ── 越南语 ──
    "trò chơi", "ứng dụng", "trực tuyến",
    # ── 泰语 ──
    "เกม", "แอป", "ออนไลน์",
    # ── 印尼语 ──
    "permainan", "aplikasi",
    # ── 阿拉伯语 ──
    "ألعاب", "لعبة", "تطبيق",
    # ── 中文（繁体，港澳台） ──
    "遊戲", "應用程式", "線上",
]

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
        "game addiction lawsuit",
        "game addiction class action",
        "product liability game addiction minor",
        "game designed addict children lawsuit",

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
        "AI bias audit game algorithm fairness",
        "AI training data consent game",
        "voice cloning game regulation",

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
        "crypto payment game regulation",
        "KYC game player verification",

        # === VIP 等级 / 消费分层 / 消费上限 ===
        "game VIP system spending tier regulation consumer",
        '"VIP level" game predatory monetization regulation',
        "game spending cap limit cooldown regulation law",
        "mobile game spending limit consumer protection",
        "game purchase cooling-off period regulation",

        # === 保底机制 / Pity System 公示 ===
        '"pity system" OR "guaranteed drop" gacha game regulation disclosure',
        "gacha pity rate disclosure transparency law",
        "game drop rate guarantee consumer regulation",

        # === Idle / 放置类参与度操纵 ===
        "idle game engagement manipulation regulation",
        '"engagement mechanic" game consumer regulation dark pattern',
        "game addiction mechanic idle reward regulation",

        # === 联盟 / 公会社交消费压力 ===
        '"social pressure" game spending guild alliance regulation',
        "game social spending mechanic consumer protection",
        "guild alliance donation game consumer regulation",

        # === SLG / 策略游戏竞争公平 ===
        '"pay to win" strategy game consumer regulation law',
        "mobile strategy game competitive fairness regulation",
        "game power advantage spending consumer protection",

        # === 射击游戏年龄分级 ===
        "shooter game age rating regulation violence",
        "FPS game content rating minor restriction",
        "battle royale game age restriction regulation",

        # === 账号交易 / RMT ===
        "game account trading regulation law",
        "real money trading game virtual item regulation",

        # === 战令/季票/FOMO 机制 ===
        '"battle pass" game regulation law',
        '"season pass" game consumer regulation',
        "FOMO game mechanic regulation dark pattern",
        "time-limited game content consumer protection",

        # === 电竞监管 ===
        "esports regulation law prize pool",
        "esports player contract labor law",
        "esports match fixing legislation",
        "esports gambling betting regulation",
        "professional gamer visa work permit",

        # === NFT/Web3 游戏 ===
        "NFT game regulation law",
        "blockchain game token regulation",
        "play-to-earn game regulation law",
        "Web3 game virtual asset regulation",
        "game token securities classification",

        # === 云游戏 ===
        "cloud gaming regulation law",
        "cloud gaming data privacy regulation",
        "game streaming service regulation",

        # === UGC / 用户生成内容 ===
        "user generated content game liability",
        "UGC game moderation regulation law",
        "game mod copyright regulation",

        # === 消费者保护补充 ===
        "forced arbitration game consumer",
        "class action game consumer lawsuit",
        "game self-exclusion mechanism regulation",
        "accidental in-app purchase child regulation",

        # === 数据隐私补充 ===
        "biometric data game regulation",
        "behavioral profiling game privacy law",
        "POPIA game South Africa data protection",
        "PIPEDA game Canada privacy",
        "UK GDPR game divergence",

        # === Lilith Games / 产品专项 ===
        '"Lilith Games" regulation OR lawsuit OR fine OR enforcement',
        '"AFK Arena" OR "Rise of Kingdoms" OR "Dislyte" regulation OR compliance OR lawsuit',

        # === 执法行动 / 诉讼专项 ===
        'FTC game enforcement OR settlement OR "consent decree" OR "consent order"',
        '"state attorney general" game enforcement OR lawsuit OR settlement',
        'game developer (fined OR penalized OR sanctioned OR sued OR investigated)',
        'game company "consent decree" OR "consent order" OR settlement',

        # === App Store 执法 / 下架 ===
        'game (removed OR suspended OR banned OR delisted) "App Store" OR "Google Play"',
        'app store (policy violation OR rejection OR enforcement) game developer',

        # === 游戏存续 / 在线服务停运 / 数字所有权 ===
        'game ("live service" OR "end of service" OR shutdown) consumer protection regulation',
        'game preservation (law OR regulation OR bill OR act)',
        '"digital ownership" (game OR gaming) (regulation OR law OR consumer)',
        '"Stop Killing Games" OR "Protect Our Games Act" game',
        'game server shutdown (consumer OR regulation OR law OR right)',
        '"right to play" game (law OR regulation OR bill)',

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
        # VIP / 課金上限 / 天井（保底）/ 放置ゲーム
        "ゲーム 課金 上限 規制 法律",
        "ガチャ 天井 確率表示 義務 規制",
        "ゲーム 課金 冷却期間 消費者保護",
        "放置ゲーム 課金 規制",
        "ゲーム アカウント売買 RMT 規制",
        # Lilith / 産品専項
        "リリスゲームズ OR AFK OR ライキン 規制 OR 訴訟 OR 処分",
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
        # VIP / 과금 상한 / 천장(보底) / 방치게임 / 계정거래
        "게임 과금 상한 규제 법안",
        "확률형 아이템 천장 공시 의무",
        "게임 결제 냉각기간 소비자 보호",
        "방치형 게임 과금 규제",
        "게임 계정 거래 RMT 규제 법률",
        # Lilith / 제품 전용
        "릴리스게임즈 OR AFK OR 라이즈오브킹덤즈 규제 OR 소송 OR 처분",
    ],
    "vi": [
        "quy định trò chơi điện tử",
        "luật game mobile đại lý nước ngoài",
        "nghị định trò chơi điện tử",
        "Bộ Thông tin Truyền thông game",
        "Bộ Thông tin và Truyền thông game di động",
        "bảo vệ dữ liệu cá nhân trò chơi điện tử",
        # 补充：未成年人保护、loot box、消费者保护
        "bảo vệ trẻ em trò chơi trực tuyến",
        "hộp chiến lợi phẩm trò chơi quy định",
        "quảng cáo game di động vi phạm",
        "giấy phép phát hành trò chơi điện tử",
        "thanh toán xuyên biên giới game",
        "quy định esports thể thao điện tử",
    ],
    "id": [
        "regulasi game mobile Indonesia",
        "penerbit game lokal Indonesia",
        "IGAC rating game mobile",
        "Kominfo regulasi game",
        "Kemenkominfo penerbit game asing",
        "perlindungan data pribadi game aplikasi",
        # 补充：未成年人保护、loot box、消费者保护
        "perlindungan anak game online",
        "loot box gacha regulasi Indonesia",
        "iklan game menyesatkan regulasi",
        "lisensi penerbitan game Indonesia",
        "pembayaran dalam aplikasi game regulasi",
        "esports regulasi Indonesia",
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
        # 补充：loot box、广告、许可
        "กล่องสุ่ม เกม กฎหมาย ไทย",
        "โฆษณาเกม หลอกลวง กฎหมาย",
        "ใบอนุญาต เกมออนไลน์ ไทย",
        "การชำระเงินข้ามพรมแดน เกม",
        "อีสปอร์ต กฎหมาย ไทย",
        "NFT เกม กฎระเบียบ ไทย",
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
        # 补充：未成年人、消费者保护、电竞
        "حماية القاصرين ألعاب فيديو قانون",
        "حماية المستهلك ألعاب إلكترونية",
        "الرياضات الإلكترونية تنظيم قانون",
        "صندوق الحظ لعبة تنظيم",
        "الدفع الإلكتروني ألعاب تنظيم",
        "محتوى الذكاء الاصطناعي ألعاب قانون",
    ],
}
