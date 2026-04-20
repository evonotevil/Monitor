"""信源层级配置：信源权威层级精确映射与模糊匹配规则"""

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
    "EUR-Lex Legislation":            "official",   # 欧盟立法公报
    # 平台官方 — 出海"宪法"
    "Apple Developer News":           "official",
    # ── legal ─────────────────────────────────────────────────────────
    "GDPRHub":                        "legal",     # GDPR 执法案例库
    "noyb":                           "legal",     # 隐私执法组织
    "IAPP News":                      "legal",
    "IAPP":                           "legal",
    "Lexology":                       "legal",
    "JD Supra":                       "legal",
    "JD Supra (Consumer Protection)": "legal",
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
        r"|EUR-Lex|eur-lex"
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
        r"\bIAPP\b|Lexology|JD Supra|Law360|GDPRHub|gdprhub|\bnoyb\b"
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
