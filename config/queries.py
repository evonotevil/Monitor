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
    "game privacy PIPEDA site:priv.gc.ca",                  # 加拿大 OPC / PIPEDA
    "game consumer competition site:competition-bureau.canada.ca",  # 加拿大竞争局
    "online gaming privacy PIPEDA site:justice.gc.ca",      # 加拿大 PIPEDA 法规文本/修订
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
    "game regulation site:komdigi.go.id",                  # 印尼 Komdigi（现用域名）
    '"PP TUNAS" site:komdigi.go.id',                       # 印尼儿童数字保护 PP 17/2025
    "game regulation site:pdpc.gov.sg",                    # 新加坡个人数据保护委员会
    "game regulation site:imda.gov.sg",                    # 新加坡 IMDA（媒体内容分级）
    "game regulation site:accc.gov.au",                    # 澳大利亚竞争与消费者委员会
    "game regulation site:oaic.gov.au",                    # 澳大利亚信息专员办公室
    "game online safety site:acma.gov.au",                 # 澳大利亚通信和媒体局
    "game regulation site:meity.gov.in",                   # 印度电子信息技术部
    "online gaming regulation site:meity.gov.in",          # 印度在线游戏/中介规则
    "game DPDP data protection site:meity.gov.in",         # 印度 DPDP / 游戏数据
    "game regulation site:pcpd.org.hk",                    # 香港隐私专员公署
    "online game regulation site:ofca.gov.hk",             # 香港通讯事务管理局
    "遊戲 個資 法規 site:moda.gov.tw",                       # 台湾数位发展部
    "遊戲 分級 規範 site:gamerating.org.tw",                 # 台湾游戏软件分级查询
    # ── 日本 ────────────────────────────────────────────────────────────
    "ゲーム 規制 site:caa.go.jp",                            # 消費者庁
    "ゲーム OR ガチャ site:soumu.go.jp",                     # 総務省
    # ── 韩国 ────────────────────────────────────────────────────────────
    "게임 규제 site:grac.or.kr",                              # GRAC 游戏管理委员会
    "게임 site:kcc.go.kr",                                    # 放送通信委员会
    # ── 南美 ────────────────────────────────────────────────────────────
    "jogo regulação site:gov.br/anpd",                       # 巴西 ANPD
    "jogo consumidor plataforma digital site:gov.br/mj",     # 巴西 Senacon / 司法部
    "game mercado digital site:gov.br/cade",                 # 巴西 CADE 竞争执法
    "game regulation site:gob.mx",                            # 墨西哥政府
    "videojuegos datos personales site:argentina.gob.ar/aaip", # 阿根廷 AAIP
    "videojuegos consumidor site:sernac.cl",                   # 智利 SERNAC
    "videojuegos proteccion datos site:sic.gov.co",            # 哥伦比亚 SIC
    # ── 加州立法 ──────────────────────────────────────────────────────────
    "game consumer protection site:leginfo.legislature.ca.gov",  # 加州立法机关（AB 1921 等）
    # ── 东南亚补充 ──────────────────────────────────────────────────────
    "game regulation site:privacy.gov.ph",                    # 菲律宾 NPC
    "game regulation site:pdpc.or.th",                        # 泰国 PDPC
    # ── 中东 ────────────────────────────────────────────────────────────
    "game content license site:gcam.gov.sa",               # 沙特 GCAM（游戏内容许可）
    "game regulation site:tra.gov.ae",                     # 阿联酋 TRA
    "game regulation site:cra.gov.qa",                     # 卡塔尔 CRA
    "game regulation site:mcit.gov.qa",                    # 卡塔尔 MCIT
    "game regulation site:citra.gov.kw",                   # 科威特 CITRA
    "game regulation site:tra.org.bh",                     # 巴林 TRA
    "online game privacy site:gov.il",                     # 以色列政府/隐私保护局
    # ── 执法/诉讼补充 ──────────────────────────────────────────────────
    '"Lilith" OR "AFK" OR game site:ftc.gov',              # FTC 涉 Lilith/游戏动态
    "game enforcement OR settlement site:ag.ny.gov",       # 纽约州 AG 游戏执法
]

# ── 日报专用 Google News 四通道查询（daily_mode=True）────────────────
# 每种语言都覆盖：监管合规、执法诉讼、平台政策、重点公司/产品。
# 总量固定为每 locale 4 条，避免多语种扩展后放大 Google News 限速风险。
PRIORITY_GAME_ENTITIES = (
    '"Lilith Games" OR "AFK Arena" OR "AFK Journey" OR "Rise of Kingdoms"'
    ' OR HoYoverse OR miHoYo OR Genshin OR "Honkai Star Rail"'
    ' OR "Kuro Games" OR "Wuthering Waves" OR Papergames OR Infold'
    ' OR "Infinity Nikki" OR "Love and Deepspace" OR Hypergryph OR GRYPHLINE'
    ' OR Arknights OR Tencent OR NetEase OR "Riot Games" OR VALORANT'
    ' OR Activision OR Blizzard'
)


DAILY_LANGUAGE_PROFILES = {}


# Google News 仍采用宽查询保证召回，但在搜索端先排除各语言最常见的
# 传统体育和博彩词。后续 fetcher.py 还会基于全文做一次硬过滤。
DAILY_QUERY_NOISE_SUFFIXES = {
    "en": "-football -soccer -rugby -basketball -betting -casino",
    "ja": "-サッカー -野球 -競馬 -カジノ",
    "ko": "-축구 -야구 -농구 -도박 -카지노",
    "vi": ' -"bóng đá" -"cá cược" -"sòng bạc"',
    "id": ' -"sepak bola" -olahraga -judi -kasino',
    "pt": "-futebol -basquete -apostas -cassino",
    "th": "-ฟุตบอล -บาสเกตบอล -พนัน -คาสิโน",
    "zh_tw": "-足球 -籃球 -賽馬 -博彩 -賭博",
    "ar": ' -"كرة القدم" -مراهنات -قمار -كازينو',
    "de": "-Fußball -Rugby -Sportwetten -Casino",
    "fr": ' -football -rugby -"paris sportifs" -casino',
    "es": "-fútbol -baloncesto -apuestas -casino",
}


def _four_lane_queries(
    language: str,
    regulation: str,
    enforcement: str,
    platform: str,
    company_actions: str,
    *,
    game_terms: tuple[str, ...],
    regulatory_terms: tuple[str, ...],
    filter_game_terms: tuple[str, ...] | None = None,
):
    suffix = DAILY_QUERY_NOISE_SUFFIXES.get(language, "")
    queries = [
        regulation,
        enforcement,
        platform,
        f"({PRIORITY_GAME_ENTITIES}) ({company_actions})",
    ]
    queries = [f"{query} {suffix}".strip() for query in queries]
    DAILY_LANGUAGE_PROFILES[language] = {
        "queries": tuple(queries),
        "game_terms": game_terms,
        "filter_game_terms": filter_game_terms or game_terms,
        "regulatory_terms": regulatory_terms,
    }
    return queries


DAILY_GOOGLE_NEWS_EN = _four_lane_queries(
    "en",
    '(game OR gaming OR "video game" OR "online game") (regulation OR law OR bill OR compliance OR privacy OR children OR "age verification" OR "loot box" OR gacha OR consumer OR advertising OR license)',
    '(game OR gaming OR "video game") (enforcement OR investigation OR fine OR penalty OR lawsuit OR "class action" OR settlement OR injunction OR ban)',
    '(game OR gaming) ("App Store" OR "Google Play" OR Steam OR PlayStation OR Xbox OR "Nintendo eShop") (policy OR payment OR removed OR delisted OR rejected OR regulation)',
    'regulation OR compliance OR investigation OR enforcement OR fine OR lawsuit OR settlement OR ban OR removed',
    game_terms=("game", "gaming", "video game", "online game"),
    filter_game_terms=("gaming", "video game", "online game"),
    regulatory_terms=("regulation", "law", "bill", "compliance", "enforcement", "investigation", "fine", "penalty", "lawsuit", "class action", "settlement", "injunction", "ban", "policy", "removed"),
)
DAILY_GOOGLE_NEWS_JA = _four_lane_queries(
    "ja",
    '(ゲーム OR オンラインゲーム OR ビデオゲーム) (規制 OR 法律 OR 法案 OR コンプライアンス OR 個人情報 OR 未成年 OR 年齢確認 OR ガチャ OR 景品表示法 OR 資金決済法)',
    '(ゲーム OR オンラインゲーム) (行政処分 OR 課徴金 OR 罰金 OR 調査 OR 訴訟 OR 集団訴訟 OR 和解 OR 禁止)',
    '(ゲーム OR オンラインゲーム) (App Store OR Google Play OR Steam OR PlayStation OR Xbox OR ニンテンドーeショップ) (ポリシー OR 決済 OR 削除 OR 配信停止 OR 規制)',
    '規制 OR 法令 OR コンプライアンス OR 調査 OR 行政処分 OR 課徴金 OR 訴訟 OR 和解 OR 配信停止',
    game_terms=("ゲーム", "オンラインゲーム", "ビデオゲーム"),
    regulatory_terms=("規制", "法律", "法案", "コンプライアンス", "行政処分", "課徴金", "罰金", "調査", "訴訟", "集団訴訟", "和解", "禁止", "配信停止"),
)
DAILY_GOOGLE_NEWS_KO = _four_lane_queries(
    "ko",
    '(게임 OR 온라인게임 OR 비디오게임) (규제 OR 법률 OR 법안 OR 준수 OR 개인정보 OR 미성년자 OR 연령확인 OR 확률형 아이템 OR 게임산업진흥법)',
    '(게임 OR 온라인게임) (조사 OR 행정처분 OR 과징금 OR 벌금 OR 제재 OR 소송 OR 집단소송 OR 합의 OR 금지)',
    '(게임 OR 온라인게임) (App Store OR Google Play OR Steam OR PlayStation OR Xbox OR 닌텐도 e숍) (정책 OR 결제 OR 삭제 OR 퇴출 OR 규제)',
    '규제 OR 법률 OR 준수 OR 조사 OR 행정처분 OR 과징금 OR 소송 OR 합의 OR 퇴출',
    game_terms=("게임", "온라인게임", "비디오게임"),
    regulatory_terms=("규제", "법률", "법안", "준수", "조사", "행정처분", "과징금", "벌금", "제재", "소송", "집단소송", "합의", "금지", "퇴출"),
)
DAILY_GOOGLE_NEWS_VI = _four_lane_queries(
    "vi",
    '(trò chơi OR trò chơi điện tử OR trò chơi trực tuyến) (quy định OR luật OR nghị định OR tuân thủ OR dữ liệu cá nhân OR trẻ em OR xác thực tuổi OR vật phẩm ảo OR "Nghị định 147/2024/NĐ-CP" OR "Nghị định 174/2026/NĐ-CP")',
    '(trò chơi OR trò chơi điện tử) (điều tra OR xử phạt OR phạt tiền OR cưỡng chế OR kiện OR khởi kiện tập thể OR dàn xếp OR cấm)',
    '(trò chơi OR trò chơi điện tử) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (chính sách OR thanh toán OR gỡ bỏ OR đình chỉ OR quy định)',
    'quy định OR tuân thủ OR điều tra OR xử phạt OR phạt tiền OR kiện OR dàn xếp OR cấm OR gỡ bỏ',
    game_terms=("trò chơi", "trò chơi điện tử", "trò chơi trực tuyến"),
    filter_game_terms=("trò chơi điện tử", "trò chơi trực tuyến", "game online"),
    regulatory_terms=("quy định", "luật", "nghị định", "tuân thủ", "điều tra", "xử phạt", "phạt tiền", "cưỡng chế", "khởi kiện", "dàn xếp", "cấm", "gỡ bỏ", "đình chỉ"),
)
DAILY_GOOGLE_NEWS_ID = _four_lane_queries(
    "id",
    '(game OR gim OR permainan) (regulasi OR peraturan OR undang-undang OR kepatuhan OR privasi OR anak OR verifikasi usia OR loot box OR "PP TUNAS" OR "PP Nomor 17 Tahun 2025")',
    '(game OR gim OR permainan) (penyelidikan OR penegakan OR sanksi OR denda OR gugatan OR gugatan kelompok OR penyelesaian OR larangan)',
    '(game OR gim OR permainan) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (kebijakan OR pembayaran OR dihapus OR ditangguhkan OR regulasi)',
    'regulasi OR kepatuhan OR penyelidikan OR penegakan OR sanksi OR denda OR gugatan OR penyelesaian OR larangan OR dihapus',
    game_terms=("game", "gim", "permainan"),
    filter_game_terms=("gim", "game online", "permainan video"),
    regulatory_terms=("regulasi", "peraturan", "undang-undang", "kepatuhan", "penyelidikan", "penegakan", "sanksi", "denda", "gugatan", "penyelesaian", "larangan", "dihapus", "ditangguhkan", "PP TUNAS"),
)
DAILY_GOOGLE_NEWS_PT = _four_lane_queries(
    "pt",
    '(jogo OR jogos OR videogame OR jogos online) (regulação OR lei OR conformidade OR LGPD OR ANPD OR Senacon OR CADE OR privacidade OR criança OR verificação de idade OR loot box)',
    '(jogo OR jogos OR videogame) (investigação OR fiscalização OR multa OR sanção OR processo OR ação coletiva OR acordo OR proibição)',
    '(jogo OR jogos OR videogame) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (política OR pagamento OR removido OR suspenso OR regulação)',
    'regulação OR conformidade OR investigação OR fiscalização OR multa OR processo OR ação coletiva OR acordo OR proibição OR removido',
    game_terms=("jogo", "jogos", "videogame", "jogos online"),
    filter_game_terms=("videogame", "jogos online", "jogo eletrônico", "jogos eletrônicos"),
    regulatory_terms=("regulação", "lei", "conformidade", "investigação", "fiscalização", "multa", "sanção", "ação coletiva", "proibição", "removido", "suspenso"),
)
DAILY_GOOGLE_NEWS_TH = _four_lane_queries(
    "th",
    '(เกม OR วิดีโอเกม OR เกมออนไลน์) (กฎหมาย OR ระเบียบ OR การกำกับดูแล OR การปฏิบัติตาม OR PDPA OR ความเป็นส่วนตัว OR เด็ก OR การยืนยันอายุ OR กล่องสุ่ม)',
    '(เกม OR เกมออนไลน์) (สอบสวน OR บังคับใช้ OR ปรับ OR ลงโทษ OR ฟ้องร้อง OR คดีแบบกลุ่ม OR ยอมความ OR ห้าม)',
    '(เกม OR เกมออนไลน์) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (นโยบาย OR การชำระเงิน OR ถอดออก OR ระงับ OR กฎระเบียบ)',
    'กำกับดูแล OR ปฏิบัติตาม OR สอบสวน OR บังคับใช้ OR ปรับ OR ฟ้องร้อง OR ยอมความ OR ห้าม OR ถอดออก',
    game_terms=("เกม", "วิดีโอเกม", "เกมออนไลน์"),
    filter_game_terms=("วิดีโอเกม", "เกมออนไลน์", "เกมมือถือ"),
    regulatory_terms=("กฎหมาย", "ระเบียบ", "การกำกับดูแล", "การปฏิบัติตาม", "สอบสวน", "บังคับใช้", "ปรับ", "ลงโทษ", "ฟ้องร้อง", "คดีแบบกลุ่ม", "ยอมความ", "ห้าม", "ถอดออก", "ระงับ"),
)
DAILY_GOOGLE_NEWS_ZH_TW = _four_lane_queries(
    "zh_tw",
    '(遊戲 OR 線上遊戲 OR 電子遊戲 OR 手機遊戲) (法規 OR 修法 OR 合規 OR 個資 OR 隱私 OR 未成年人 OR 年齡驗證 OR 轉蛋 OR 虛擬寶物 OR 消費者保護 OR 分級)',
    '(遊戲 OR 線上遊戲 OR 電子遊戲) (調查 OR 執法 OR 裁罰 OR 罰款 OR 行政處分 OR 訴訟 OR 集體訴訟 OR 和解 OR 禁止)',
    '(遊戲 OR 線上遊戲) (App Store OR Google Play OR Steam OR PlayStation OR Xbox OR Nintendo eShop) (政策 OR 支付 OR 下架 OR 停權 OR 違規 OR 法規)',
    '法規 OR 合規 OR 調查 OR 執法 OR 裁罰 OR 訴訟 OR 和解 OR 禁止 OR 下架',
    game_terms=("遊戲", "線上遊戲", "電子遊戲", "手機遊戲"),
    filter_game_terms=("線上遊戲", "電子遊戲", "手機遊戲"),
    regulatory_terms=("法規", "修法", "合規", "調查", "執法", "裁罰", "罰款", "行政處分", "訴訟", "集體訴訟", "和解", "禁止", "下架", "停權", "違規"),
)
DAILY_GOOGLE_NEWS_AR = _four_lane_queries(
    "ar",
    '(ألعاب OR لعبة فيديو OR ألعاب إلكترونية OR ألعاب عبر الإنترنت) (تنظيم OR قانون OR امتثال OR خصوصية OR أطفال OR التحقق من العمر OR صناديق الغنائم OR ترخيص)',
    '(ألعاب OR ألعاب إلكترونية) (تحقيق OR إنفاذ OR غرامة OR عقوبة OR دعوى OR دعوى جماعية OR تسوية OR حظر)',
    '(ألعاب OR ألعاب إلكترونية) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (سياسة OR دفع OR إزالة OR تعليق OR تنظيم)',
    'تنظيم OR امتثال OR تحقيق OR إنفاذ OR غرامة OR دعوى OR تسوية OR حظر OR إزالة',
    game_terms=("ألعاب", "لعبة فيديو", "ألعاب إلكترونية", "ألعاب عبر الإنترنت"),
    filter_game_terms=("لعبة فيديو", "ألعاب إلكترونية", "ألعاب عبر الإنترنت"),
    regulatory_terms=("تنظيم", "قانون", "امتثال", "تحقيق", "إنفاذ", "غرامة", "عقوبة", "دعوى", "دعوى جماعية", "تسوية", "حظر", "إزالة", "تعليق"),
)
DAILY_GOOGLE_NEWS_DE = _four_lane_queries(
    "de",
    '(Spiel OR Spiele OR Videospiel OR Online-Spiel) (Regulierung OR Gesetz OR Compliance OR Datenschutz OR Kinder OR Altersverifikation OR Lootbox OR Verbraucherschutz)',
    '(Spiel OR Spiele OR Videospiel) (Ermittlung OR Durchsetzung OR Geldbuße OR Strafe OR Klage OR Sammelklage OR Vergleich OR Verbot)',
    '(Spiel OR Spiele OR Videospiel) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (Richtlinie OR Zahlung OR entfernt OR gesperrt OR Regulierung)',
    'Regulierung OR Compliance OR Ermittlung OR Durchsetzung OR Geldbuße OR Klage OR Vergleich OR Verbot OR entfernt',
    game_terms=("Spiel", "Spiele", "Videospiel", "Online-Spiel"),
    filter_game_terms=("Videospiel", "Videospiele", "Online-Spiel", "Computerspiel"),
    regulatory_terms=("Regulierung", "Gesetz", "Compliance", "Ermittlung", "Durchsetzung", "Geldbuße", "Strafe", "Klage", "Sammelklage", "Vergleich", "Verbot", "entfernt", "gesperrt"),
)
DAILY_GOOGLE_NEWS_FR = _four_lane_queries(
    "fr",
    '(jeu OR jeux OR jeu vidéo OR jeux en ligne) (réglementation OR loi OR conformité OR vie privée OR enfants OR vérification de l’âge OR loot box OR consommateur)',
    '(jeu OR jeux OR jeu vidéo) (enquête OR application OR amende OR sanction OR procès OR recours collectif OR accord OR interdiction)',
    '(jeu OR jeux OR jeu vidéo) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (politique OR paiement OR retiré OR suspendu OR réglementation)',
    'réglementation OR conformité OR enquête OR application OR amende OR procès OR recours collectif OR accord OR interdiction OR retiré',
    game_terms=("jeu", "jeux", "jeu vidéo", "jeux en ligne"),
    filter_game_terms=("jeu vidéo", "jeux vidéo", "jeux en ligne"),
    regulatory_terms=("réglementation", "loi", "conformité", "enquête", "amende", "sanction", "procès", "recours collectif", "interdiction", "retiré", "suspendu"),
)
DAILY_GOOGLE_NEWS_ES = _four_lane_queries(
    "es",
    '(juego OR juegos OR videojuego OR juegos en línea) (regulación OR ley OR cumplimiento OR privacidad OR menores OR verificación de edad OR loot box OR consumidor)',
    '(juego OR juegos OR videojuego) (investigación OR ejecución OR multa OR sanción OR demanda OR demanda colectiva OR acuerdo OR prohibición)',
    '(juego OR juegos OR videojuego) (App Store OR Google Play OR Steam OR PlayStation OR Xbox) (política OR pago OR retirado OR suspendido OR regulación)',
    'regulación OR cumplimiento OR investigación OR ejecución OR multa OR demanda OR demanda colectiva OR acuerdo OR prohibición OR retirado',
    game_terms=("juego", "juegos", "videojuego", "juegos en línea"),
    filter_game_terms=("videojuego", "videojuegos", "juegos en línea"),
    regulatory_terms=("regulación", "ley", "cumplimiento", "investigación", "ejecución", "multa", "sanción", "demanda", "demanda colectiva", "prohibición", "retirado", "suspendido"),
)
