"""搜索关键词库：多语言搜索关键词（聚焦手游出海合规）"""

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
