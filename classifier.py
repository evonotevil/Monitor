"""
文章分类器 - 自动分配区域、一级分类、二级分类、状态、影响评分
分类对齐 config.py: 数据隐私/玩法合规/未成年人保护/广告营销合规/消费者保护/
                    经营合规/平台政策/内容监管/PC & 跨平台合规

影响评分 (1.0–10.0, 面向中资游戏出海):
  高风险 ≥9.0 — 概率公示处罚 / 应用商店下架 / 移动端平台强制政策(DMA/IDFA/IAP) / PC反作弊隐私被诉
  中风险 ≥7.0 — 跨平台数据限制 / 强制年龄验证
  核心市场 (北美/欧洲/日本/韩国/东南亚) 自动 +2.0
  移动端优先：App Store/Google Play 政策变更 ≥ PC 合规风险（移动端是 Lilith/鹰角/米哈游营收主渠道）
"""

import json
import re
from pathlib import Path
from typing import Tuple

from config import (
    CATEGORIES, MONITORED_REGIONS, STATUS_LABELS,
    SOURCE_TIER_MAP, SOURCE_TIER_PATTERNS,
)
from models import LegislationItem
from utils import _get_region_group

# ── 噪音来源加载（由 monitor.py noise-sync 命令生成）───────────────────
# 若文件不存在则静默忽略，不影响正常分类流程。
_NOISE_SOURCES_PATH = Path(__file__).parent / "data" / "noise_sources.json"
_HIGH_NOISE_SOURCES: set = set()

def _reload_noise_sources() -> None:
    global _HIGH_NOISE_SOURCES
    if _NOISE_SOURCES_PATH.exists():
        try:
            data = json.loads(_NOISE_SOURCES_PATH.read_text(encoding="utf-8"))
            _HIGH_NOISE_SOURCES = set(data.get("blocklist", []))
        except Exception:
            pass

_reload_noise_sources()


# ─── 国家 → 区域 映射 ──────────────────────────────────────────────

COUNTRY_PATTERNS = {
    # 欧洲
    "欧盟": [r"european union|\bEU\b|GDPR|DSA\b|DMA\b|digital services act|digital markets act|european commission|european parliament|brussels|AI act|欧盟"],
    "英国": [r"united kingdom|\bUK\b|british|ofcom|online safety act|UK GDPR|英国|britain"],
    "德国": [r"germany|german|德国|deutschland|BfDI"],
    "法国": [r"france|french|法国|CNIL"],
    "荷兰": [r"netherlands|dutch|荷兰|kansspelautoriteit"],
    "奥地利": [r"austria|austrian|奥地利"],
    "比利时": [r"belgium|belgian|比利时"],
    "意大利": [r"italy|italian|意大利|AGCM"],
    "西班牙": [r"spain|spanish|西班牙|AEPD"],
    "波兰": [r"poland|polish|波兰"],
    "瑞典": [r"sweden|swedish|瑞典"],
    "挪威": [r"norway|norwegian|挪威"],
    # 北美
    "美国": [r"united states|\bUS\b|\bUSA\b|american|FTC\b|federal trade commission|CCPA|CPRA|COPPA|congress\b|senate\b|california|KIDS act|section 230|tennessee|florida|alabama|missouri|new york|south carolina|mississippi|connecticut|nevada|pennsylvania|harrisburg|attorney general"],
    "加拿大": [r"canada|canadian|加拿大|PIPEDA"],
    # 南美
    "巴西": [r"brazil|brazilian|巴西|LGPD"],
    "墨西哥": [r"mexico|mexican|墨西哥"],
    "阿根廷": [r"argentina|阿根廷"],
    "智利": [r"chile|chilean|智利"],
    "哥伦比亚": [r"colombia|colombian|哥伦比亚"],
    # 东南亚
    "越南": [r"vietnam|vietnamese|越南|việt nam|MIC.*vietnam|nghị định|thông tư"],
    "印度尼西亚": [r"indonesia|indonesian|印尼|印度尼西亚|IGAC|Kominfo|Kemenkominfo"],
    "泰国": [r"thailand|thai\b|泰国|PDPA.*thailand|thai.*PDPA"],
    "菲律宾": [r"philippines|filipino|菲律宾|NTC.*philippine"],
    "马来西亚": [r"malaysia|malaysian|马来西亚|MCMC"],
    "新加坡": [r"singapore|新加坡|IMDA|MDA.*singapore"],
    # 南亚
    "印度": [r"\bindia\b|indian|印度|DPDPA|Vaishnaw|MeitY"],
    "巴基斯坦": [r"pakistan|巴基斯坦"],
    # 港澳台
    "香港": [r"hong kong|香港|PCPD"],
    "澳门": [r"macau|macao|澳门"],
    "台湾": [r"taiwan|台湾|台灣|個資法"],
    # 日本
    "日本": [r"japan|japanese|日本|CERO|ガチャ|景品表示法|資金決済法|特商法|消費者庁|スマートフォン"],
    # 韩国
    "韩国": [r"korea|korean|韩国|한국|GRAC|게임|게임산업진흥|확률형|문화체육관광부"],
    # 大洋洲
    "澳大利亚": [r"australia|australian|澳大利亚|澳洲|ACCC|eSafety"],
    "新西兰": [r"new zealand|新西兰"],
    # 中东/非洲
    "沙特": [r"saudi|沙特|GAMERS"],
    "阿联酋": [r"UAE|united arab emirates|阿联酋|dubai"],
    "土耳其": [r"turkey|turkish|türkiye|土耳其"],
    "尼日利亚": [r"nigeria|尼日利亚"],
    "南非": [r"south africa|南非"],
}

# 国家 → 区域 映射表
COUNTRY_TO_REGION = {}
for region_name, region_info in MONITORED_REGIONS.items():
    for country in region_info["countries"]:
        COUNTRY_TO_REGION[country] = region_name

# 中国大陆关键词（用于排除）
CHINA_MAINLAND_PATTERNS = [
    r"(?<!\bhong\s)(?<!\bmacau\s)(?<!\btaiwan\s)china(?!.*hong kong)(?!.*macau)(?!.*taiwan)",
    r"中国(?!.*香港)(?!.*澳门)(?!.*台湾)",
    r"中华人民共和国|版号|网信办|新闻出版署|PIPL|防沉迷|游戏出海",
]


# ─── 分类检测规则 ─────────────────────────────────────────────────────

CATEGORY_PATTERNS = {
    # ── 数据隐私 ──────────────────────────────────────────────────────
    "数据隐私": {
        "_l1": [
            r"privacy|data.?protection|GDPR|CCPA|CPRA|LGPD|DPDPA|隐私|データ保護|개인정보",
            r"data.?breach|data.?transfer|cookie|consent.*data|个人数据|個人資料|跨境数据|data.?local",
            r"biometric|behavioral.*profil|PIPEDA|POPIA|UK\s*GDPR",
        ],
        "GDPR合规": [r"GDPR|general data protection"],
        "CCPA/各州隐私法": [r"CCPA|CPRA|california.*privacy|state privacy law"],
        "儿童隐私(COPPA)": [r"COPPA|children.*privacy|kids.*privacy|儿童隐私|child.*data.*protect"],
        "跨境数据传输": [r"cross.?border.*data|data.*transfer|跨境数据|数据出境|standard.*contractual"],
        "数据本地化": [r"data.*local\w*|server.*local\w*|数据本地化"],
        "数据泄露通知": [r"data.*breach|breach.*notif|数据泄露"],
        "生物识别/行为画像": [r"biometric.*data|facial.*recognit|behavio\w+.*profil|player.*profil.*privac"],
    },

    # ── 玩法合规（开箱/抽卡/涉赌） ──────────────────────────────────────
    "玩法合规": {
        "_l1": [
            r"loot.?box|gacha|random.*(?:item|reward|drop)|probability.*disclos",
            r"gambling.*game|game.*gambling|gaming.*gambling",
            r"확률형|ガチャ|开箱|抽奖|抽卡|涉赌|随机道具",
            r"pay.?to.?win|microtransaction|virtual.*currenc|game.*monetiz",
            r"battle.?pass|season.?pass|FOMO.*game|NFT.*game|blockchain.*game|play.?to.?earn",
        ],
        "抽奖/开箱(Loot Box)": [r"loot.?box|gacha|random.*item|random.*reward|开箱|抽奖|抽卡|ガチャ|확률형"],
        "概率公示": [r"probability.*disclos|odds.*disclos|drop.*rate|概率公示|確率表示"],
        "虚拟货币": [r"virtual.*currenc|in.?game.*currenc|虚拟货币|仮想通貨|가상화폐"],
        "付费随机机制": [r"pay.*random|paid.*random|random.*purchas|random.*paid|무작위.*구매"],
        "涉赌认定": [r"gambling.*game|game.*gambling|gaming.*mechanic.*gambling|类赌博|涉赌|賭博.*ゲーム"],
        "游戏内购规范": [r"in.?app.*purchas|IAP|microtransaction|内购|인앱결제"],
        "战令/季票(Battle Pass)": [r"battle.?pass|season.?pass|seasonal.*content.*regulat|FOMO.*game.*regulat|time.?limited.*offer.*game"],
        "NFT/Web3游戏资产": [r"NFT.*game|blockchain.*game|play.?to.?earn|game.*token.*regulat|Web3.*game|crypto.*game.*asset"],
    },

    # ── 未成年人保护 ──────────────────────────────────────────────────
    "未成年人保护": {
        "_l1": [
            r"minor|children|child(?:ren)?|\bkid\b|youth|teen|underage|未成年|青少年|儿童|未成年者|청소년|未成年人",
            r"age.*verif|age.*restrict|anti.?addiction|年龄|COPPA|KIDS.*act",
            r"children.*online.*safety|parental.*control|family.*link",
        ],
        "年龄验证/分级": [r"age.*verif|age.*check|age.*gate|年龄验证|年齢確認|연령 확인"],
        "未成年消费限制": [r"minor.*spend|minor.*purchas|children.*spend|kids.*spend|未成年.*消费|課金制限|미성년.*결제"],
        "游戏时长限制": [r"play.*time.*limit|screen.*time|curfew|游戏时长|게임 이용시간|playtime.*restrict"],
        "内容分级制度": [r"age.*rat|content.*rat|ESRB|PEGI|CERO|GRAC|IGAC|分级|レーティング|등급"],
        "家长控制": [r"parental.*control|family.*link|parent.*setting|家长控制|保護者"],
        "防沉迷系统": [r"anti.?addiction|防沉迷|addiction.*prevent|game.*addict"],
        "自我排除机制": [r"self.?exclusion|self.?limit|自我排除|自己排除"],
        "心理健康/成瘾警告": [r"mental.*health.*game|gambling.*disorder.*game|addiction.*warning|成瘾警告|依存症"],
    },

    # ── 广告营销合规 ──────────────────────────────────────────────────
    "广告营销合规": {
        "_l1": [
            r"advertis.*regulat|advertis.*law|marketing.*(?:law|regulat|comply|rule)",
            r"dark.?pattern|misleading.*ad|deceptive.*ad|false.*advertis",
            r"influencer.*disclos|sponsorship.*disclos|KOL.*comply|网红.*合规",
            r"广告.*合规|广告.*规定|广告.*法|营销.*合规",
        ],
        "虚假广告": [r"misleading.*ad|false.*advertis|deceptive.*ad|虚假广告|誤認表示|허위광고"],
        "营销披露": [r"advertis.*disclos|marketing.*disclos|sponsor.*disclos|营销披露|広告表示"],
        "网红/KOL合规": [r"influencer.*(?:law|rule|disclos|comply)|KOL.*comply|streamer.*disclos|网红|YouTuber.*rule"],
        "价格透明度": [r"price.*transparen|pricing.*disclos|price.*disclos|价格透明|価格表示"],
        "暗黑模式": [r"dark.?pattern|manipulat.*design|deceptive.*design|暗黑模式|다크패턴"],
        "促销活动合规": [r"promotion.*law|promotion.*rule|sale.*law|促销.*合规|景品表示"],
    },

    # ── 消费者保护 ──────────────────────────────────────────────────
    "消费者保护": {
        "_l1": [
            r"consumer.*protect|consumer.*right|消费者保护|消費者保護|소비자 보호",
            r"refund.*game|chargeback.*game|game.*refund",
            r"subscription.*auto.?renew|auto.?renew.*subscript",
            r"FTC.*consumer|consumer.*fine|consumer.*law",
        ],
        "退款政策": [r"refund|chargeback|退款|返金|환불"],
        "订阅自动续费": [r"auto.?renew|subscription.*renew|自动续费|自動更新|자동갱신"],
        "价格歧视": [r"price.*discrimin|dynamic.*pricing.*unfair|价格歧视|価格差別"],
        "消费者权益诉讼": [r"consumer.*lawsuit|consumer.*litigation|class.*action.*consumer|消费者诉讼|집단소송"],
        "虚假宣传": [r"mislead.*consumer|deceptive.*consumer|false.*claim.*consumer|虚假宣传|不当表示"],
        "强制仲裁条款": [r"forced.*arbitrat|mandator.*arbitrat|arbitrat.*clause.*game|强制仲裁"],
        "误触消费/儿童误购": [r"accidental.*purchas|unintend.*purchas|child.*accidental.*buy|误触消费|误购"],
    },

    # ── 经营合规（本地代理/代表处/许可/分级） ──────────────────────────
    "经营合规": {
        "_l1": [
            r"local.*agent|local.*represent|local.*publisher|local.*entity",
            r"game.*licens|game.*permit|game.*registr|游戏许可|게임 등록|IGAC.*registr",
            r"foreign.*(?:game|developer|publisher).*(?:require|registr|agent|licens)",
            r"本地代理|本地代表|本地发行|经营合规|대리인.*게임|게임.*대리인",
            r"market.*access.*game|game.*market.*entry|game.*operation.*permit",
        ],
        "本地代理/代表处": [r"local.*agent|local.*represent|대리인|게임.*대리인|local.*entity.*game|本地代理"],
        "游戏许可/牌照": [r"game.*licens|game.*permit|游戏许可|游戏牌照|게임 사업자|사업자 등록"],
        "本地分级注册": [r"local.*rating|rating.*registr|local.*classif|本地分级|IGAC|GRAC.*registr|등급 신청"],
        "税务合规": [r"(?:digital|game).*tax|数字税|税务合规|GST.*game|VAT.*game|游戏税"],
        "外资限制": [r"foreign.*(?:invest|own|company).*restrict|外资限制|FDI.*game"],
        "本地发行商要求": [r"local.*publisher.*require|local.*distributor|overseas.*publisher.*local|海外.*本地发行"],
    },

    # ── 平台政策 ──────────────────────────────────────────────────────
    "平台政策": {
        "_l1": [
            r"app.*store.*(?:polic|rule|guideline|regulat)|apple.*(?:polic|guideline).*(?:game|app)",
            r"google.*play.*(?:polic|regulat|rule)|android.*polic.*(?:game|app)",
            r"side.?load|third.?party.*pay|第三方支付|平台政策|DMA.*app.*store",
        ],
        "App Store政策": [r"app.*store.*(?:polic|guideline|regulat|rule)|apple.*(?:polic|guideline).*(?:game|app|developer)"],
        "Google Play政策": [r"google.*play.*(?:polic|regulat|rule)|android.*polic.*(?:game|app)"],
        "第三方支付": [r"third.?party.*pay|alternative.*pay|第三方支付|alternative.*payment"],
        "佣金/分成比例": [r"commission.*(?:app|store)|revenue.*shar|佣金|分成|30%.*store"],
        "侧载政策": [r"side.?load|alternative.*(?:market|store)|侧载|sideload"],
    },

    # ── 内容监管 ──────────────────────────────────────────────────────
    "内容监管": {
        "_l1": [
            r"content.*(?:moder|censor|review|classif)|censor\w*|内容监管|内容审查",
            r"game.*rating.*system|classification.*(?:regulat|system)|分级制度",
            r"copyright.*(?:law|act|infring)|pirac\w*.*(?:law|enforce)|知识产权|著作権",
            r"user.?generated.*content|UGC.*(?:liab|regulat)|game.*mod.*(?:copyright|law)",
        ],
        "内容审查": [r"content.*(?:review|censor|moder).*(?:law|regulat|rule)|内容审查"],
        "AI生成内容": [r"AI.*(?:generat|act|regulat|law)|AIGC|generative.*AI.*(?:law|regulat)"],
        "知识产权保护": [r"intellectual.*property.*(?:law|regulat)|copyright.*(?:law|act)|知识产权|著作権"],
        "版权合规": [r"copyright.*infring|pirac.*(?:law|enforce)|版权合规|著作権侵害"],
        "UGC用户生成内容责任": [r"user.?generated.*content.*(?:liab|regulat|law)|UGC.*(?:liab|moder|regulat)|game.*mod.*copyright"],
    },

    # ── PC & 跨平台合规 ───────────────────────────────────────────────
    # 专门标记 PC 启动器权限、驱动级反作弊合规、PC充值绕开平台分成、跨平台数据流动限制
    # 与"平台政策"的区别：平台政策聚焦 App Store/Google Play（移动端）；
    # 本类聚焦 Steam/Epic/PC 启动器及 D2C/三方充值等 PC 特有风险
    "PC & 跨平台合规": {
        "_l1": [
            # 驱动级反作弊（唯一信号，不与其他分类重叠）
            r"kernel.?level.*anti.?cheat|anti.?cheat.*(?:driver|kernel)",
            # PC 启动器监管语境（Steam/Epic 须与法规词共现）
            r"(?:steam|epic.?games?\s*store|pc\s*launcher).*(?:polic|regulat|privac|law|ban|restrict)\w*",
            r"(?:polic|regulat|privac|law|ban|restrict)\w*.*(?:steam|epic.?games?\s*store|pc\s*launcher)",
            # D2C 直销 / 三方充值
            r"D2C.*(?:game|publisher|distribut)\w*",
            r"direct.to.consumer.*(?:game|publisher).*(?:regulat|law|polic)",
            r"third.?party.*top.?up.*(?:game|ban|regulat|consumer)",
            # 跨平台数据流
            r"cross.?platform.*(?:data|privac)\w*.*(?:restrict|limit|regulat|law)",
        ],
        "PC启动器权限": [
            r"pc\s*(?:game|launcher).*(?:permiss|privac|data|access)\w*",
            r"launcher.*(?:permiss|privac|data.*collect|regulat)",
        ],
        "反作弊程序合规": [
            r"kernel.?level.*anti.?cheat|anti.?cheat.*(?:driver|kernel)",
            r"anti.?cheat.*(?:privac|data.*collect|ban|regulat|lawsuit|sued)",
            r"(?:driver|kernel).*anti.?cheat.*(?:privac|fine|restrict)",
        ],
        "PC充值/D2C合规": [
            r"D2C.*(?:game|publisher)|direct.to.consumer.*game.*(?:regulat|law|polic)",
            r"third.?party.*top.?up.*(?:game|ban|regulat|consumer)",
            r"pc.*(?:payment|pay).*(?:bypass|circumvent|alternativ).*(?:store|platform)",
        ],
        "跨平台数据合规": [
            r"cross.?platform.*(?:data|privac|transfer)\w*.*(?:regulat|restrict|law|limit)",
            r"(?:pc.*mobile|mobile.*pc).*data.*(?:transfer|sync|share).*(?:regulat|restrict|law)",
        ],
    },

    # ── AI内容合规 ──────────────────────────────────────────────────────
    # 与"内容监管"的 AI生成内容 子类区别：本类聚焦 AI 专项法规（EU AI Act、
    # 算法审计、训练数据、深度合成），而非一般性内容审查
    "AI内容合规": {
        "_l1": [
            r"\bAI\s*act|EU\s*AI\b|artificial.*intelligence.*(?:act|regulat|law)",
            r"\bAI\b.*bias|algorithm.*(?:audit|fairness|transparen)",
            r"deepfake|synthetic.*media|deep.*synthe|虚拟数字人|深度合成",
            r"\bAI\b.*(?:train|label|disclos|generat).*(?:regulat|law|comply|mandate)",
        ],
        "EU AI Act合规(高风险/通用AI分类)": [r"EU\s*AI\s*act|AI\s*act.*(?:high.?risk|general.?purpose|GPAI)|欧盟.*AI.*法"],
        "AI生成内容标识义务": [r"AI.*(?:generat|content).*(?:label|disclos|watermark|标识)|AIGC.*标识|AI.*content.*label"],
        "深度合成/虚拟数字人合规": [r"deepfake|synthetic.*media|deep.*synthe|voice.*clon|虚拟数字人|深度合成|AI.*avatar"],
        "AI算法推荐透明度": [r"algorithm.*(?:recommend|transparen)|推荐算法.*透明|AI.*recommend.*(?:regulat|disclos)"],
        "AI偏见/公平性审计": [r"AI.*bias|algorithm.*(?:audit|fairness)|AI.*discriminat|算法.*(?:偏见|公平|审计)"],
        "AI训练数据合规": [r"train.*data.*(?:consent|copyright|regulat)|AI.*train.*(?:user|player).*data|训练数据.*(?:合规|同意)"],
    },
}


# ─── 状态检测规则 ─────────────────────────────────────────────────────

STATUS_PATTERNS = {
    "已生效": [r"\b(?:now )?effective\b|in force|enacted|enforced|takes? effect|已生效|已实施|施行|발효"],
    "即将生效": [r"coming into|will take effect|即将生效|goes into effect|set to take effect|将于.*生效|将要.*施行"],
    "草案/征求意见": [r"draft|consultation|comment period|草案|征求意见|意见稿|パブリックコメント|public comment|입법예고"],
    "立法进行中": [r"under review|reading|deliberat|审议中|进行中|under consideration|审议|审查"],
    "已提案": [r"\bpropos\w*\b|\bintroduc\w*\b|bill filed|已提案|提出|提交|new bill|发议案|법안 발의"],
    "修订变更": [r"\bamend\w*\b|已修订|修改|修正|개정|revision"],
    "已废止": [r"repeal|abolish|已废止|废除|폐지"],
    "执法动态": [r"enforcement|(?:fined?|penalty|penalised|penalized)\b|sanction|处罚|罚款|执法|violation|settle|consent order|enforcement.?action|벌금|제재"],
    "立法动态": [r"announce|plan to|consider|signal|intend|upcoming|将|拟|검토|예정"],
}


# ─── 影响评分体系 (10 分制) ───────────────────────────────────────────
#
# 面向中资游戏出海合规优先级 (Lilith/米哈游/鹰角视角)
#
# 分值区间含义：
#   ≥9.0 高风险 — 须立即响应（概率公示处罚 / 应用商店下架 / PC反作弊隐私被诉）
#   ≥7.0 中风险 — 需纳入季度合规审查
#   ≥5.0 关注   — 应跟踪立法进展
#   <5.0 低优先 — 知悉即可
#
# 计分逻辑：
#   基础分  (1.0–5.0) 由状态决定
#   +信源加成 official +2.0 / legal +1.0 / industry +0.5
#   +核心市场加成 北美/欧洲/日本/韩国/东南亚 +2.0
#   +高风险内容加成 概率公示处罚/下架风险/反作弊隐私 +1.5 / 跨平台数据/年龄验证 +0.5
#   上限 10.0，下限 1.0
#

# 状态基础分
_IMPACT_STATUS_BASE = {
    "已生效":        5.0,
    "即将生效":      5.0,
    "执法动态":      5.0,
    "修订变更":      4.5,
    "草案/征求意见": 4.0,
    "立法进行中":    3.5,
    "已提案":        3.0,
    "立法动态":      2.0,
    "已废止":        1.0,
}

# 核心市场 — Lilith/米哈游/鹰角出海核心营收来源
# 同时包含显示分组名（北美/欧洲/东南亚）和具体国家名（美国/英国/越南等），
# 因为 DB region 字段可能是 LLM 返回的国家名，而非显示分组名。
_CORE_MARKETS = {
    "北美", "欧洲", "日韩", "港澳台", "东南亚", "大洋洲",
}

# 高风险内容检测规则 (addon_score, patterns)
# 每组内只计一次加成（不叠加），各组之间可叠加
_HIGH_RISK_PATTERNS: list = [
    # (+1.5) 概率公示不实处罚 — 直接触发监管执法 & 商店下架
    (1.5, [
        r"probability\s*disclos\w*.*(?:fine|penalt|enforce|violat|sanction)",
        r"(?:fine|penalt|enforce|sanction)\w*.*probability\s*disclos",
        r"gacha.*(?:fine|penalt|enforce|sanction|banned|illegal)",
        r"(?:fine|penalt|enforce|sanction)\w*.*gacha",
        r"loot.?box.*(?:fine|penalt|enforce|banned|illegal)",
        r"확률형.*(?:과징금|제재|처분|위반)",
        r"ガチャ.*(?:処分|罰則|違反|課徴金)",
        r"概率.*(?:罚款|处罚|违规|整改)",
    ]),
    # (+1.5) 应用商店下架风险 — 对出海运营直接致命
    (1.5, [
        r"(?:remov|delist|pull|taken?\s*down|ban)\w*\s+(?:from\s+)?(?:app.?store|google.?play|steam|epic)",
        r"(?:app.?store|google.?play|steam|epic)\w*.*(?:remov|delist|pull|ban)\w*",
        r"game\w*.*(?:remov|delist|banned)\w*.*(?:store|platform|market)",
        r"下架.*(?:应用商店|App\s*Store|Google\s*Play|Steam)",
        r"게임.*(?:삭제|퇴출).*(?:스토어|플랫폼)",
    ]),
    # (+1.5) 移动端平台政策强制执行 — App Store/Google Play 政策变更直接影响出海运营
    # 涵盖：DMA 强制第三方支付、IDFA/GAID 隐私新规、SDK 合规、IAP 分成新规
    # 这类动态对 Lilith/Hoyoverse/鹰角 移动端营收影响最直接，与下架风险同等优先级
    (1.5, [
        # DMA/反垄断强制要求平台开放第三方支付
        r"(?:app.?store|google.?play|apple|google).*(?:third.?party|alternative).*pay\w*.*(?:mandator|compel|require|DMA|force|law)",
        r"(?:mandator|compel|require|DMA|force|law)\w*.*(?:app.?store|google.?play).*(?:third.?party|alternative).*pay\w*",
        # IDFA/GAID 等移动广告标识符隐私管制
        r"\b(?:IDFA|GAID|advertising.?identifier|mobile.?tracking.?identifier)\b.*(?:restrict|ban|regulat|privac|fine|enforce)",
        r"(?:restrict|ban|regulat|privac|fine|enforce)\w*.*\b(?:IDFA|GAID|advertising.?identifier)\b",
        # 移动端 SDK 合规强制执行（影响 AppsFlyer/Adjust/Firebase 等分析 SDK）
        r"mobile.*(?:analytics|advertising|attribution).*SDK.*(?:fine|ban|privac|regulat|comply)",
        r"SDK.*(?:data.*collect|privac|consent).*(?:fine|regulat|ban|enforce).*(?:mobile|game|app)",
        # IAP 强制规范（Apple/Google 抽成争议已立法/监管落地）
        r"(?:in.?app.*purchas|IAP|app.*store.*commission).*(?:mandator|law|legislat|fine|ban|DMA)",
        r"(?:法规|法律|监管|禁止|要求).*(?:应用.*内购|IAP|App\s*Store.*分成|移动端.*支付)",
    ]),
    # (+1.0) PC端反作弊程序被诉侵犯隐私 — PC合规风险（低于移动端优先级）
    (1.0, [
        r"kernel.?level.*anti.?cheat.*(?:privac|sued|lawsuit|ban|fine|regulat)",
        r"anti.?cheat.*(?:privac\w*.*violat|sued|lawsuit|fine|regulat)",
        r"(?:driver|kernel).*anti.?cheat.*(?:privac|data.*collect|ban)",
    ]),
    # (+0.5) PC/移动端跨平台数据转移限制
    (0.5, [
        r"cross.?platform.*data.*(?:restrict|limit|transfer|regulat|law)",
        r"(?:pc|mobile).*data.*cross.?platform.*(?:restrict|regulat)",
        r"跨平台.*数据.*(?:限制|转移|合规|规定)",
    ]),
    # (+0.5) 要求强制年龄验证拦截机制
    (0.5, [
        r"mandator\w+\s+age.?verif",
        r"age.?verif\w*.*(?:mandator|required|compulsor|oblig)\w*",
        r"age.?gate.*(?:require|mandator|law|legislat)",
        r"强制.*年龄验证|年龄验证.*(?:强制|义务|必须)",
        r"強制.*年齢確認|年齢確認.*義務",
        r"연령\s*확인.*(?:의무|강제)",
    ]),
]


# ── 硬件/系统层噪音模式（命中则 impact_score 归零）────────────────────
# 这类文章与游戏合规无关，应在评分阶段直接抑制
_HARDWARE_NOISE_PATTERNS = [
    # 电池/能耗
    r"\bbattery\s*optim\w+\b",                          # battery optimization
    r"\bbattery\s+(?:tech\w*|standard\w*|guidelin\w*|requir\w*|charg\w*|sav\w*|effici\w*)\b",
    r"\benergy.?sav\w+\b",                              # energy saving
    r"\benergy\s*(?:effici\w+|standard\w*|certif\w*|star\b|label\w*|consum\w*)\b",
    r"\bpower\s*(?:consumption|efficiency|management)\b",
    # 硬件性能
    r"\bhardware\s*(?:performance|architect\w+|standard\w*|spec\w*)\b",
    r"\bdevice\s*performance\s*(?:test|benchmark|review)\b",
    # 无线标准
    r"\bwi-?fi\s*(?:\d+[a-z]*|standard\w*|protocol\w*)\b",  # Wi-Fi 6/7/standards
    r"\bbluetooth\s*(?:\d+[a-z]*|standard\w*|protocol\w*)\b",
    r"\bwireless\s*standard\w*\b",
    # 处理器/芯片
    r"\bprocessor\s*architect\w+\b",
    r"\bchipset\s*(?:spec|feature|model|update|launch)\b",
    r"\b(?:cpu|gpu)\s*(?:architect\w+|benchmark|overcloc\w+|spec\w*|driver\s*update|standard\w*)\b",
    # 显示/内存
    r"\bdisplay\s*(?:refresh\s*rate|panel|resolution)\b",
    r"\bram\s*(?:speed|type|capacity)\b",
    # 设备评测/发布（英文）
    r"\b(?:pixel|macbook|iphone|ipad)\s*(?:\d+|pro|mini|air|max|review|spec|launch|release)\b",
    # 中文硬件噪音兜底
    r"电池优化|电池技术|电池标准|续航优化|能效(?:评测|测试)|能耗标准|芯片性能|处理器架构|硬件架构|Wi-Fi标准|蓝牙标准|无线标准",
]

# ── Google/Apple 核心合规话题白名单（命中则保留，否则视为噪音）──────────
# 覆盖：支付分成(IAP/Commission)、应用分发(Distribution)、分级、隐私、消保、抽卡
_GOOGLE_APPLE_CORE_TOPICS = re.compile(
    r"pay(?:ment|ments|out)?|commission|distribut\w+|rating\w*|age.?verif\w*"
    r"|privacy|data.?protect|consumer|fine|penalt|lawsuit|regulat\w+"
    r"|DMA\b|anti.?trust|monopol|IAP|app.?store.?polic|google.?play.?polic"
    r"|third.?party|side.?load|refund|GDPR|COPPA|children|minor"
    r"|gacha|loot.?box|random.*item|probabil\w+|battle.?pass|NFT|blockchain"
    r"|支付|分成|分发|分级|隐私|消保|未成年|罚款|处罚|监管|合规|抽卡|抽奖|开箱|概率|战令",
    re.IGNORECASE,
)
_GOOGLE_APPLE_MENTION = re.compile(
    r"\b(?:google|apple|android|ios|app\s*store|google\s*play)\b", re.IGNORECASE,
)


def _is_hardware_noise(text: str) -> bool:
    """返回 True 表示纯硬件/系统文章，应将 impact_score 归零。"""
    for p in _HARDWARE_NOISE_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _is_google_apple_non_core(text: str) -> bool:
    """
    返回 True 表示文章含 Google/Apple 关键词但不涉及核心合规话题
    （支付分成/应用分发/分级/隐私/消保/抽卡），应将 impact_score 归零。
    策略：宽进严出——只要未命中核心合规白名单，一律视为噪音。
    """
    if not _GOOGLE_APPLE_MENTION.search(text):
        return False  # 不含 Google/Apple，与此规则无关
    return not bool(_GOOGLE_APPLE_CORE_TOPICS.search(text))


def get_source_tier(source_name: str) -> str:
    """
    返回信源权威层级: 'official' / 'legal' / 'industry' / 'news'
    优先精确匹配 SOURCE_TIER_MAP，其次用 SOURCE_TIER_PATTERNS 正则匹配。
    """
    if source_name in SOURCE_TIER_MAP:
        return SOURCE_TIER_MAP[source_name]
    for tier, pattern in SOURCE_TIER_PATTERNS:
        if re.search(pattern, source_name, re.IGNORECASE):
            return tier
    return "news"


def _high_risk_bonus(text: str) -> float:
    """
    检测文章是否触及高风险合规场景，返回累计附加分。
    每组模式只计一次（命中第一条即止），各组可叠加。
    """
    text_lower = text.lower()
    bonus = 0.0
    for add, patterns in _HIGH_RISK_PATTERNS:
        for p in patterns:
            if re.search(p, text_lower, re.IGNORECASE):
                bonus += add
                break
    return bonus


def compute_composite_score(
    risk_revenue: int,
    risk_product: int,
    risk_urgency: int,
    risk_scope: int,
    region: str = "",
    source_name: str = "",
    text: str = "",
) -> float:
    """
    基于 LLM 四维风险评估计算综合影响评分 (1.0–10.0)。

    公式：
      weighted = revenue×0.35 + product×0.25 + urgency×0.25 + scope×0.15
      composite = weighted / 3.0 × 9.0 + 1.0    → [1.0, 10.0]

    噪音过滤和高噪音来源降分逻辑与 score_impact() 保持一致。
    """
    # 硬件噪音 / Google-Apple 非核心文章 → 直接归零
    if text and (_is_hardware_noise(text) or _is_google_apple_non_core(text)):
        return 0.0

    weighted = (
        risk_revenue * 0.35
        + risk_product * 0.25
        + risk_urgency * 0.25
        + risk_scope * 0.15
    )
    composite = weighted / 3.0 * 9.0 + 1.0

    # 高噪音来源降分
    if source_name and source_name in _HIGH_NOISE_SOURCES:
        composite = max(1.0, composite * 0.5)

    return round(min(10.0, max(1.0, composite)), 1)


def score_impact(
    status: str,
    source_name: str,
    region: str = "",
    text: str = "",
) -> float:
    """
    计算影响评分 (1.0–10.0):

      基础分   = 状态权重 (1.0–5.0)
      + 信源加成  official +2.0 / legal +1.0 / industry +0.5
      + 核心市场  北美/欧洲/日本/韩国/东南亚 +2.0
      + 高风险内容 概率公示处罚/下架/反作弊隐私 +1.5 各一次
                   跨平台数据/强制年龄验证 +0.5 各一次

    高风险 ≥9.0 / 中风险 ≥7.0 / 关注 ≥5.0 / 低优先 <5.0
    """
    # 硬件噪音 / Google-Apple 非核心文章 → 直接归零，不进入评分链
    if text and (_is_hardware_noise(text) or _is_google_apple_non_core(text)):
        return 0.0

    base = _IMPACT_STATUS_BASE.get(status, 2.0)

    tier = get_source_tier(source_name)
    tier_bonus = {"official": 2.0, "legal": 1.0, "industry": 0.5}.get(tier, 0.0)

    market_bonus = 2.0 if region in _CORE_MARKETS else 0.0

    risk_bonus = _high_risk_bonus(text) if text else 0.0

    total = base + tier_bonus + market_bonus + risk_bonus

    # 高噪音来源降分（Bitable 噪音反馈，阈值由 noise-sync 命令配置）
    # 不直接归零：即使高噪音来源偶尔发出真实监管动态，仍可进入日报，只是优先级更低。
    if source_name and source_name in _HIGH_NOISE_SOURCES:
        total = max(1.0, total * 0.5)

    return round(min(10.0, max(1.0, total)), 1)


# ─── 分类入口 ────────────────────────────────────────────────────────

def classify_article(article: dict) -> LegislationItem:
    """对一篇文章进行区域、分类、状态、影响评分判定"""
    text = f"{article.get('title', '')} {article.get('summary', '')}".strip()

    region = _get_region_group(_detect_region(text, article.get("region", "")))
    l1, l2 = _detect_category(text)
    status = _detect_status(text)
    source_name = article.get("source", "")
    impact = score_impact(status, source_name, region=region, text=text)

    return LegislationItem(
        region=region,
        category_l1=l1,
        category_l2=l2,
        title=article.get("title", ""),
        date=article.get("date", ""),
        status=status,
        summary=article.get("summary", "")[:500],
        source_name=source_name,
        source_url=article.get("url", ""),
        lang=article.get("lang", "en"),
        impact_score=impact,
    )


def _detect_region(text: str, fallback: str = "") -> str:
    """检测文章所属区域（返回大区名称如 '欧洲', '北美'）"""
    text_combined = text.lower()

    country_scores = {}
    for country, patterns in COUNTRY_PATTERNS.items():
        score = 0
        for p in patterns:
            score += len(re.findall(p, text_combined, re.IGNORECASE))
        if score > 0:
            country_scores[country] = score

    if country_scores:
        best_country = max(country_scores, key=country_scores.get)
        region = COUNTRY_TO_REGION.get(best_country)
        if region:
            return region

    if re.search(r"\beu\b|欧盟|european|europe", text_combined, re.IGNORECASE):
        return "欧洲"

    if fallback and fallback in MONITORED_REGIONS:
        return fallback
    return "其他"


def is_china_mainland(text: str) -> bool:
    """检测是否为中国大陆相关内容"""
    for p in CHINA_MAINLAND_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _detect_category(text: str) -> Tuple[str, str]:
    """检测一级/二级分类"""
    text_lower = text.lower()
    best_l1 = "经营合规"  # 默认兜底：通用监管动态归入经营合规，避免"内容监管"成垃圾桶
    best_l1_score = 0
    best_l2 = ""

    for l1, sub_patterns in CATEGORY_PATTERNS.items():
        l1_score = 0
        l1_patterns = sub_patterns.get("_l1", [])
        for p in l1_patterns:
            l1_score += len(re.findall(p, text_lower, re.IGNORECASE))

        if l1_score > best_l1_score:
            best_l1_score = l1_score
            best_l1 = l1

            best_l2_score = 0
            best_l2 = ""
            for l2_name, l2_patterns in sub_patterns.items():
                if l2_name == "_l1":
                    continue
                l2_score = 0
                for p in l2_patterns:
                    l2_score += len(re.findall(p, text_lower, re.IGNORECASE))
                if l2_score > best_l2_score:
                    best_l2_score = l2_score
                    best_l2 = l2_name

    return best_l1, best_l2


def _detect_status(text: str) -> str:
    """检测状态"""
    text_lower = text.lower()
    best_status = "立法动态"
    best_score = 0

    for status, patterns in STATUS_PATTERNS.items():
        score = 0
        for p in patterns:
            score += len(re.findall(p, text_lower, re.IGNORECASE))
        if score > best_score:
            best_score = score
            best_status = status

    return best_status
