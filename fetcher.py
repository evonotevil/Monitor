"""
数据抓取模块 - RSS 解析 & Google News 搜索
严格过滤：只保留真正的立法/监管/执法动态
"""

import re
import json
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote_plus
import concurrent.futures
from collections import Counter

from utils import MEDIA_SUFFIX_RE

import requests
from bs4 import BeautifulSoup

from config import (
    RSS_FEEDS,
    KEYWORDS,
    PC_PLATFORM_KEYWORDS_EN,
    DIGITAL_INDUSTRY_SIGNALS,
    OFFICIAL_SITE_QUERIES,
    INDUSTRY_QUERY_NOISE_SUFFIX,
    DAILY_LANGUAGE_PROFILES,
    GOOGLE_NEWS_SEARCH_TEMPLATE,
    GOOGLE_NEWS_REGIONS,
    FETCH_TIMEOUT,
    MAX_CONCURRENT_REQUESTS,
    MAX_ARTICLE_AGE_DAYS,
    DAILY_GOOGLE_NEWS_EN,
    DAILY_GOOGLE_NEWS_JA,
    DAILY_GOOGLE_NEWS_KO,
    DAILY_GOOGLE_NEWS_VI,
    DAILY_GOOGLE_NEWS_PT,
    DAILY_GOOGLE_NEWS_TH,
    DAILY_GOOGLE_NEWS_ID,
    DAILY_GOOGLE_NEWS_ZH_TW,
    DAILY_GOOGLE_NEWS_AR,
    DAILY_GOOGLE_NEWS_DE,
    DAILY_GOOGLE_NEWS_FR,
    DAILY_GOOGLE_NEWS_ES,
)
from models import LegislationItem
from classifier import classify_article, is_china_mainland

logger = logging.getLogger(__name__)

# ─── HTTP 工具 ────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,ja;q=0.6,ko;q=0.5",
}


def safe_get(url: str, timeout: int = FETCH_TIMEOUT, max_retries: int = 3) -> Optional[requests.Response]:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code == 429:
                wait = min(2 ** attempt * 5, 60)
                logger.warning(f"请求限速(429) {url}，等待 {wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 2  # 2s, 4s, 8s
                logger.warning(f"请求失败 {url}: {e}，{wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                logger.warning(f"请求失败 {url}: {e}（已重试 {max_retries} 次）")
    return None


# ─── RSS 解析 ─────────────────────────────────────────────────────────

def parse_rss_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:500]


def _sanitize_title(title: str) -> str:
    """
    清洗 RSS/Google News 原始标题：
    - 剔除 Unicode 替换字符和控制字符
    - 保留合法 Unicode 文字（泰文、阿拉伯文、重音拉丁文等均为有效标题）
    - 剔除媒体机构名称后缀（ - GamesIndustry.biz 等）
    - 折叠多余空白
    """
    if not title:
        return ""
    # 1. 替换字符 & 控制字符
    t = title.replace("\ufffd", "").replace("\ufffe", "").replace("\ufffc", "")
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
    # 2. 媒体机构后缀
    t = MEDIA_SUFFIX_RE.sub("", t)
    # 3. 整理空白
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _oaic_title_to_url(title: str) -> str:
    """OAIC RSS 不提供 <link>，根据标题生成媒体中心 URL（slug 规则与官网一致）。"""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return f"https://www.oaic.gov.au/news/media-centre/{slug}"


def fetch_rss_feed(feed_config: dict) -> List[dict]:
    url = feed_config["url"]
    resp = safe_get(url)
    if not resp:
        return []

    items = []
    try:
        # 部分 RSS（如日本総務省）使用 Shift_JIS 等非 UTF-8 编码，
        # ET.fromstring(bytes) 不支持非 UTF-8 multi-byte 编码。
        # 策略：先用声明的编码解码为文本，去掉 encoding 声明，再解析。
        raw = resp.content
        import re as _re
        enc_match = _re.search(rb'encoding=["\']([^"\']+)["\']', raw[:200])
        if enc_match:
            declared_enc = enc_match.group(1).decode("ascii")
            if declared_enc.lower() not in ("utf-8", "utf8"):
                xml_str = raw.decode(declared_enc, errors="replace")
                xml_str = _re.sub(r'encoding=["\'][^"\']+["\']', 'encoding="utf-8"', xml_str)
                raw = xml_str.encode("utf-8")
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")
            clean_title = _sanitize_title(clean_html(title))
            if not clean_title:
                continue
            items.append({
                "title": clean_title,
                "url": link,
                "date": parse_rss_date(pub_date),
                "summary": clean_html(description),
                "source": feed_config["name"],
                "region": feed_config.get("region", ""),
                "lang": feed_config.get("lang", "en"),
                "tier": feed_config.get("tier", ""),
            })

        for entry in root.findall(".//atom:entry", ns):
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            updated = entry.findtext("atom:updated", "", ns) or entry.findtext("atom:published", "", ns)
            summary = entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns)
            items.append({
                "title": _sanitize_title(clean_html(title)),
                "url": link,
                "date": parse_rss_date(updated),
                "summary": clean_html(summary or ""),
                "source": feed_config["name"],
                "region": feed_config.get("region", ""),
                "lang": feed_config.get("lang", "en"),
                "tier": feed_config.get("tier", ""),
            })

    except ET.ParseError as e:
        logger.warning(f"RSS 解析失败 {url}: {e}")
        # 一些政府 RSS 含未转义字符或截断标签。使用现有 BeautifulSoup
        # 做宽松回退，避免单个格式瑕疵让整个官方信源归零。
        soup = BeautifulSoup(resp.content, "html.parser")
        for node in soup.find_all(["item", "entry"]):
            title_el = node.find("title")
            link_el = node.find("link")
            date_el = (
                node.find("pubdate") or node.find("updated")
                or node.find("published") or node.find("date")
            )
            summary_el = (
                node.find("description") or node.find("summary")
                or node.find("content")
            )
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title:
                continue
            link = ""
            if link_el:
                link = link_el.get("href", "") or link_el.get_text(strip=True)
            items.append({
                "title": _sanitize_title(clean_html(title)),
                "url": link,
                "date": parse_rss_date(date_el.get_text(" ", strip=True) if date_el else ""),
                "summary": clean_html(summary_el.get_text(" ", strip=True) if summary_el else ""),
                "source": feed_config["name"],
                "region": feed_config.get("region", ""),
                "lang": feed_config.get("lang", "en"),
                "tier": feed_config.get("tier", ""),
            })

    # 部分 RSS 源不含 <link>，根据标题生成 URL（feeds.py 中声明 url_from_title）
    if feed_config.get("url_from_title"):
        for it in items:
            if not it.get("url"):
                it["url"] = _oaic_title_to_url(it["title"])

    logger.info(f"[RSS] {feed_config['name']}: 获取 {len(items)} 条")
    return items


# ─── Google News 搜索 ──────────────────────────────────────────────────

def fetch_google_news(query: str, region_key: str = "en_US", max_results: int = 0) -> List[dict]:
    """
    抓取 Google News RSS 结果。
    max_results: 每个查询最多返回条数（0 = 不限，日报模式建议 20）。
    """
    region = GOOGLE_NEWS_REGIONS.get(region_key, GOOGLE_NEWS_REGIONS["en_US"])
    url = GOOGLE_NEWS_SEARCH_TEMPLATE.format(
        query=quote_plus(query),
        hl=region["hl"],
        gl=region["gl"],
        ceid=region["ceid"],
    )

    resp = safe_get(url)
    if not resp:
        return []

    items = []
    try:
        root = ET.fromstring(resp.content)
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")

            source_name = "Google News"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source_name = parts[1] if len(parts) > 1 else source_name

            items.append({
                "title": _sanitize_title(clean_html(title)),
                "url": link,
                "date": parse_rss_date(pub_date),
                "summary": clean_html(description),
                "source": source_name,
                # 本地语言入口提供地区提示；标题含明确国家时 classifier 仍会覆盖。
                "region": region.get("region", ""),
                "lang": region["hl"].split("-")[0],
            })
            if max_results and len(items) >= max_results:
                break
    except ET.ParseError as e:
        logger.warning(f"Google News RSS 解析失败: {e}")

    logger.info(f"[Google News] '{query}' ({region_key}): 获取 {len(items)} 条")
    return items


# ─── 严格相关性过滤 ──────────────────────────────────────────────────

def _profile_filter_patterns(field: str) -> List[str]:
    """从日报语言画像生成基础过滤正则，确保查询与过滤同步。"""
    patterns = []
    seen = set()
    for profile in DAILY_LANGUAGE_PROFILES.values():
        for term in profile[field]:
            normalized = term.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            escaped = re.escape(term)
            patterns.append(
                rf"(?<!\w){escaped}(?!\w)" if term.isascii() else escaped
            )
    return patterns

# 必须包含至少一个「法规/监管行动」信号词
REGULATORY_SIGNALS = _profile_filter_patterns("regulatory_terms") + [
    # 英文
    r"\bregulat\w*\b", r"\blegislat\w*\b", r"\b(?:new |proposed )?law\b", r"\bbill\b",
    r"\bact\b", r"\bordinance\b", r"\bstatute\b", r"\bdirective\b",
    r"\benforcement\b", r"\bfine[ds]?\b", r"\bpenalt\w+\b", r"\bsanction\w*\b",
    r"\bcompliance\b", r"\bmandat\w+\b", r"\bban(?:s|ned|ning)?\b",
    r"\brestrict\w*\b", r"\brequire\w*\b", r"\bprohibit\w*\b",
    r"\bruling\b", r"\bverdict\b", r"\bconsent order\b",
    r"\bpolicy\b", r"\bguideline\w*\b", r"\brule\w*\b",
    r"\bdraft\b", r"\bconsultation\b", r"\bproposal\b",
    r"\brecommendation\w*\b",
    r"\bguidance\b",
    r"\bexecutive order\b",
    r"\bNPRM\b", r"\bnotice of proposed rulemaking\b",
    r"\b(?:commission|regulatory|enforcement|court|board)\s+decision\b",
    r"\bdecision\b.*\b(?:regulat|enforc|compliance|penalt|fine)\w*\b",
    r"\bFTC\b", r"\bCOPPA\b", r"\bGDPR\b", r"\bCCPA\b", r"\bDSA\b", r"\bDMA\b",
    r"\bIGAC\b", r"\bGRAC\b", r"\bESRB\b", r"\bPEGI\b", r"\bCERO\b", r"\bCESA\b",
    r"\bOnline Safety Act\b", r"\bKIDS Act\b",
    r"消費者庁", r"게임물관리위원회",
    r"\bPP\s*TUNAS\b", r"PP\s*(?:Nomor\s*)?17\s*(?:Tahun\s*)?2025",
    # 民事诉讼 / 集体诉讼
    r"\blawsuit\w*\b", r"\bsue[ds]?\b", r"\bsuing\b",
    r"\bclass.?action\b", r"\bproduct.?liability\b",
    r"\bcomplaint\b", r"\blitigation\b", r"\bplaintiff\b",
    r"\binjunction\b", r"\bdamages\b.*\b(?:seek|award|claim)\w*\b",
    r"\bsettlement\b",
    # 日文
    r"規制", r"法律", r"法案", r"条例", r"施行", r"罰則", r"処分", r"義務",
    r"景品表示法", r"資金決済法", r"特商法",
    r"訴訟", r"提訴", r"集団訴訟",
    r"通知", r"告示", r"指導", r"答申",
    r"行政処分", r"課徴金", r"罰金", r"調査", r"和解", r"禁止", r"配信停止",
    # 韩文
    r"규제", r"법안", r"법률", r"의무", r"제재", r"개정",
    r"게임산업진흥법",
    r"소송", r"집단소송",
    r"지침", r"공고", r"고시",
    r"조사", r"행정처분", r"과징금", r"벌금", r"처벌", r"합의", r"금지", r"정책", r"퇴출",
    # 越南语
    r"quy định", r"nghị định", r"thông tư", r"luật",
    r"tuân thủ", r"điều tra", r"xử phạt", r"phạt tiền", r"cưỡng chế",
    r"khởi kiện", r"dàn xếp", r"cấm", r"chính sách", r"gỡ bỏ", r"đình chỉ",
    # 泰语
    r"กฎหมาย", r"ระเบียบ", r"ประกาศ", r"การกำกับดูแล", r"การปฏิบัติตาม",
    r"สอบสวน", r"บังคับใช้", r"ปรับ", r"ลงโทษ", r"ฟ้องร้อง", r"คดีแบบกลุ่ม",
    r"ยอมความ", r"ห้าม", r"นโยบาย", r"ถอดออก", r"ระงับ",
    # 印尼语
    r"\bperaturan\b", r"\bundang-undang\b", r"\bregulasi\b",
    r"\bsanksi\b", r"\bdenda\b", r"\bkewajiban\b", r"\bkeputusan\b",
    r"\bkepatuhan\b", r"\bpenyelidikan\b", r"\bpenegakan\b", r"\bgugatan\b",
    r"\bpenyelesaian\b", r"\blarangan\b", r"\bkebijakan\b", r"\bdihapus\b", r"\bditangguhkan\b",
    # 葡萄牙语（巴西）
    r"\bregula(?:ção|cao)\b", r"\bregulamenta(?:ção|cao)\b", r"\blei\b", r"\bmultas?\b",
    r"\bsanções?\b", r"\bfiscaliza(?:ção|cao)\b", r"\bresolução\b", r"\bconformidade\b",
    r"\binvestiga(?:ção|cao)\b", r"\bação coletiva\b", r"\bacordo (?:judicial|regulatório)\b",
    r"\bproibição\b", r"\bpolítica\b", r"\bremovido\b", r"\bsuspenso\b",
    # 繁体中文（港澳台）
    r"法規", r"修法", r"裁罰", r"處分", r"規範", r"行政命令", r"合規",
    r"調查", r"執法", r"罰款", r"訴訟", r"集體訴訟", r"和解", r"禁止",
    r"下架", r"停權", r"違規", r"政策",
    # 阿拉伯语
    r"تنظيم", r"قانون", r"لوائح", r"امتثال", r"تحقيق", r"إنفاذ", r"غرامة",
    r"عقوبة", r"دعوى", r"تسوية", r"حظر", r"سياسة", r"إزالة", r"تعليق",
    # 德语
    r"\bregulierung\b", r"\bgesetz\b", r"\bcompliance\b", r"\bermittlung\b",
    r"\bdurchsetzung\b", r"\bgeldbuße\b", r"\bstrafe\b", r"\bklage\b",
    r"\bsammelklage\b", r"\bvergleich\b", r"\bverbot\b", r"\brichtlinie\b",
    # 法语
    r"\bréglementation\b", r"\bloi\b", r"\bconformité\b", r"\benquête\b",
    r"\bamende\b", r"\bsanction\b", r"\bprocès\b", r"\brecours collectif\b",
    r"\binterdiction\b", r"\bpolitique\b", r"\bretiré\b", r"\bsuspendu\b",
    # 西班牙语
    r"\bregulación\b", r"\bley\b", r"\bcumplimiento\b", r"\binvestigación\b",
    r"\bejecución\b", r"\bmulta\b", r"\bsanción\b", r"\bdemanda\b",
    r"\bacción colectiva\b", r"\bprohibición\b", r"\bpolítica\b", r"\bretirado\b", r"\bsuspendido\b",
]

# 必须包含至少一个「游戏/互动娱乐」信号词
GAME_SIGNALS = _profile_filter_patterns("filter_game_terms") + [
    r"\bvideo\s*game\w*\b", r"\bmobile\s*game\w*\b", r"\bonline\s*game\w*\b",
    r"\bgaming\b",
    r"\bloot\s*box\w*\b", r"\bgacha\b", r"\bmicrotransaction\w*\b",
    r"\bin.?app\s*purchas\w*\b", r"\bapp\s*store\b", r"\bgoogle\s*play\b",
    r"\bplay\s*store\b", r"\bvirtual\s*currenc\w*\b",
    r"\bminor\w*\b.*\b(?:online|digital|screen)\b",
    r"\bchildren\b.*\b(?:online|digital|app|internet)\b",
    r"\bgame\s*(?:developer|publish|industr|compan|rating|age)\w*\b",
    r"\bgame\b.*\b(?:regulat|law|legislat|ban|restrict|fine|enforc)\b",
    r"\b(?:regulat|law|legislat|ban|restrict|fine|enforc)\w*\b.*\bgame\b",
    r"ゲーム", r"ガチャ",
    r"게임", r"확률형",

    # ── PC 平台信号 (Steam / Epic / D2C / 驱动级反作弊 / Launcher / 跨平台) ──
    # Steam/Epic 须与监管词共现，避免误捕普通游戏新闻
    r"\bsteam\b.*\b(?:regulat|law|ban|polic|privac|restrict|fine)\w*\b",
    r"\b(?:regulat|law|ban|polic|privac|restrict|fine)\w*\b.*\bsteam\b",
    r"\bepic\s*games?\s*store\b.*\b(?:regulat|law|polic|ban)\w*\b",
    r"\b(?:regulat|law|polic|ban)\w*\b.*\bepic\s*games?\s*store\b",
    r"\bpc\s*(?:game|gaming|launcher)\b.*\b(?:regulat|law|polic|privac)\w*\b",
    r"\bkernel.?level\s*anti.?cheat\b",
    r"\banti.?cheat\s*driver\b.*\b(?:ban|regulat|privac|restrict)\w*\b",
    r"\b(?:D2C|direct.to.consumer)\b.*\bgame\w*\b",
    r"\bgame\w*\b.*\b(?:D2C|direct.to.consumer)\b",
    r"\bthird.?party\s*top.?up\b",
    # Launcher 隐私 / 数据收集（含驱动/内核权限争议）
    r"\bgame\s*launcher\b.*\b(?:privac|data.collect|permission|telemetr)\w*\b",
    r"\b(?:privac|data.collect|permission|telemetr)\w*\b.*\bgame\s*launcher\b",
    # 跨平台进度同步（数据主权/GDPR 互操作性要求）
    r"\bcross.?(?:platform|progression)\b.*\b(?:data|privac|account|regulat)\w*\b",
    r"\b(?:data|privac|account|regulat)\w*\b.*\bcross.?(?:platform|progression)\b",

    # ── 核心游戏合规信号（Loot Box/Gacha Probability/In-game Currency/Minor）──
    r"\bgacha\s*probability\b",
    r"\bprobability\s*disclosur\w*\b.*\bgame\b",
    r"\bgame\b.*\bprobability\s*disclosur\w*\b",
    r"\bin.?game\s*currenc\w*\b.*\b(?:regulat|law|ban|restrict)\w*\b",
    r"\b(?:regulat|law|ban|restrict)\w*\b.*\bin.?game\s*currenc\w*\b",
    r"\bgame\s*addiction\s*(?:prevent|protect|law|ban|limit)\w*\b",
    r"\bscreen\s*time\s*(?:limit|law|regulat)\w*\b.*\bgame\b",
    # 中文核心概念（出现即视为强信号，无需与英文监管词共现）
    r"防沉迷", r"概率公示", r"虚拟货币",
    # 日文增强
    r"確率.*ガチャ|ガチャ.*確率",
    r"未成年.*ゲーム|ゲーム.*未成年",
    # 韩文增强
    r"게임.*미성년|미성년.*게임",
    r"가챠.*확률|확률.*가챠",
    # 越南语
    r"trò chơi",                        # 游戏
    # 印尼语
    r"\bpermainan\b", r"\bgim\b",
    r"\bgame\b.*\b(?:regulasi|peraturan|sanksi|denda|gugatan|larangan)\b",
    r"\b(?:regulasi|peraturan|sanksi|denda|gugatan|larangan)\b.*\bgame\b",
    r"\bPP\s*TUNAS\b", r"PP\s*(?:Nomor\s*)?17\s*(?:Tahun\s*)?2025",
    r"pelindungan anak.*sistem elektronik|sistem elektronik.*pelindungan anak",
    # 葡萄牙语（巴西）
    r"\bjogos?\b", r"\bvideogames?\b", r"\bitem\s+virtual\b",
    # 泰语
    r"เกม",                              # 游戏
    # 繁体中文
    r"線上遊戲", r"手機遊戲", r"電子遊戲", r"虛擬寶物",
    r"遊戲.*(?:平台|發行|玩家|帳號|虛擬|分級|課金|數位)",
    r"(?:平台|發行商|玩家|帳號|虛擬物品|分級).*遊戲",
    # 阿拉伯语
    r"ألعاب|لعبة",                       # 游戏/一个游戏
    # 德语 / 法语 / 西班牙语
    r"\bspiele?\b", r"\bvideospiele?\b", r"\bonline-spiel\b",
    r"\bjeux?\b", r"\bjeu vidéo\b", r"\bjeux en ligne\b",
    r"\bjuegos?\b", r"\bvideojuegos?\b", r"\bjuegos en línea\b",

    # ── 游戏公司名信号（公司名 + REGULATORY_SIGNAL = 通过过滤）──
    # Lilith 自家
    r"\bLilith\s*Games?\b",
    r"\bAFK\s*(?:Arena|Journey)\b", r"\bRise\s*of\s*Kingdoms?\b",
    r"\bDislyte\b", r"\bWarpath\b", r"\bFarlight\b",
    # 中资出海发行商
    r"\bTencent\b", r"\bNetEase\b", r"\bmiHoYo\b", r"\bHoYoverse\b",
    r"\bCentury\s*Games?\b", r"\bWhiteout\s*Survival\b",
    r"\bFunPlus\b", r"\bFun\s*Plus\b", r"\bKings?\s*Group\b",
    r"\bFUNFLY\b", r"\bLast\s*War\b",
    r"\b37(?:Games|Interactive)\b",
    r"\bYotta\s*Games?\b", r"\bTop\s*War\b",
    r"\bIGG\b", r"\bLords?\s*Mobile\b",
    r"\bMoonton\b", r"\bMobile\s*Legends?\b",
    r"\bGame\s*Science\b", r"\bBlack\s*Myth\b",
    r"\bPapergames\b", r"\bInfold\s*Games?\b",
    r"\bInfinity\s*Nikki\b", r"\bLove\s*and\s*Deepspace\b",
    r"\bKuro\s*Games?\b", r"\bWuthering\s*Waves\b", r"\bPunishing:\s*Gray\s*Raven\b",
    r"\bHypergryph\b", r"\bGRYPHLINE\b", r"\bArknights\b",
    # 韩国发行商
    r"\bNexon\b", r"\bMapleStory\b",
    r"\bKrafton\b", r"\bPUBG\b",
    r"\bNCsoft\b", r"\bLineage\b.*\b(?:game|MMORPG|NCsoft|mobile)\b",
    r"\bNetmarble\b",
    r"\bKakao\s*Games?\b",
    r"\bCom2uS\b", r"\bSummoners?\s*War\b",
    r"\bSmilegate\b", r"\bCross\s*Fire\b.*\b(?:game|Smilegate|mobile|shooter)\b", r"\bLost\s*Ark\b",
    r"\bShift\s*Up\b", r"\bStellar\s*Blade\b",
    # 日本发行商
    r"\bBandai\s*Namco\b",
    r"\bSquare\s*Enix\b",
    r"\bCapcom\b",
    r"\bSEGA\b", r"\bAtlus\b",
    r"\bKonami\b",
    r"\bCygames\b", r"\bCyber\s*Agent\b",
    r"\bDeNA\b",
    r"\bGungHo\b",
    r"\bCOLOPL\b",
    # 欧美大厂
    r"\bSupercell\b", r"\bEpic\s*Games\b", r"\bActivision\b", r"\bBlizzard\b",
    r"\bRiot\s*Games?\b", r"\bLeague\s*of\s*Legends\b", r"\bVALORANT\b",
    r"\bElectronic\s*Arts?\b", r"\bEA\s*Games?\b",
    r"\bNintendo\b", r"\bSony\b.*\b(?:PlayStation|game)\b",
    r"\bMicrosoft\s*Gaming\b", r"\bXbox\s*Game\b",
    r"\bTake.?Two\b", r"\bRockstar\s*Games?\b", r"\b2K\s*Games?\b",
    r"\bUbisoft\b",
    r"\bValve\b.*\b(?:Steam|game|Half.Life|software|Gabe)\b",
    r"\bWarner\s*Bros\.?\s*Games?\b",
    r"\bEmbracer\b", r"\bTHQ\s*Nordic\b",
    # 手游专业发行商
    r"\bScopely\b", r"\bMonopoly\s*Go\b",
    r"\bKing\b.*\b(?:game|Candy|Crush)\b",
    r"\bPlayrix\b",
    r"\bDream\s*Games\b", r"\bRoyal\s*Match\b",
    r"\bZynga\b",
    r"\bJam\s*City\b",
    # 东南亚 / 其他
    r"\bGarena\b", r"\bSea\s*Ltd\b", r"\bFree\s*Fire\b.*\b(?:game|Garena|mobile|battle)\b",
    r"\bVNG\b.*\b(?:game|Garena|ZingPlay|mobile)\b",
    # 平台 / 产品
    r"\bRoblox\b", r"\bFortnite\b", r"\bApple\s*Arcade\b",

    # ── App Store 执法信号 ──
    r"\b(?:app\s*store|google\s*play)\b.*\b(?:remov|suspend|delist|reject|ban|violat)\w*\b",
    r"\b(?:remov|suspend|delist|reject|ban|violat)\w*\b.*\b(?:app\s*store|google\s*play)\b",

    # ── 执法行动补充信号 ──
    r"\bgame\b.*\b(?:settlement|consent\s*(?:order|decree)|plea)\b",
    r"\b(?:settlement|consent\s*(?:order|decree)|plea)\b.*\bgame\b",
    r"\bgame\s*(?:studio|maker|creator)\b",
    r"\bmobile\s*(?:app|developer)\b.*\b(?:fine|penalt|enforc|sued|lawsuit)\w*\b",
]

# 排除词 - 即使匹配了上面的词，如果标题中大量出现这些词，基本可以判断不是法规新闻
EXCLUSION_PATTERNS = [
    r"\breview\b.*\b(?:score|rating|stars?|gameplay)\b",  # 游戏评测
    r"\breleas\w*\b.*\b(?:date|trailer|gameplay)\b",  # 游戏发布
    r"\btrailer\b", r"\bgameplay\b", r"\bwalkthrough\b",
    r"\btournament\b", r"\besports? (?:team|event|match)\b",
    r"\bsale\b.*\b(?:off|discount|deal)\b",
    r"\bbest game\w*\b", r"\btop \d+ game\b",
    r"\bhow to play\b", r"\bgame guide\b",
    r"\bpatch note\b", r"\bupdate.*(?:v\d|version|season)\b", r"\bcontent update\b",
    r"\bGemini\b", r"\bCopilot\b", r"\bChatGPT\b",  # AI 产品新闻
    r"\bSDK\b.*\b(?:release|update|version)\b",  # SDK 更新
    r"\bAPI\b.*\b(?:release|update|version|new)\b",  # API 更新
    r"\bWWDC\d*\b", r"\bGoogle I/O\b",  # 开发者大会（含WWDC25/26等）
    r"@\s*WWDC",                         # @WWDC25 格式
    r"\bdeveloper tool\b", r"\bXcode\b", r"\bSwift\b", r"\bKotlin\b",
    # Apple/Google 开发者博客通用噪音（非立法）
    r"developer activit",                # "developer activities" / "开发者活动"
    r"最新的开发者活动",                   # 中文"查看我们最新的开发者活动"
    r"\bjoin us (?:at|in|for)\b",        # 活动邀请
    r"今天@",                             # "今天@WWDC25：第X天"
    r"\btech talk\b",                    # Apple Tech Talk
    r"storefront.*currenc|currenc.*storefront",   # Apple全球定价页（175 storefronts, 44 currencies）
    r"(?:tax.*price|price.*tax).*(?:\d{2,3}\s*(?:store|market)|storefronts?)",  # Apple价格/税收更新
    r"应用.*价格.*税收|价格.*税收.*更新|税收.*价格.*更新",  # 中文版苹果价格税收更新
    r"应用.*税收.*价格|税收.*更新.*店面",  # 中文版苹果税收价格
    # ── 纯硬件/性能类文章（无监管背景）──────────────────────────────────
    r"\bbattery\s*(?:life|health|optim\w+|drain|test|review|sav\w+)\b",  # battery optimization
    r"\benergy\s*(?:sav\w+|efficien\w+|consumption|optim\w+)\b",         # energy saving
    r"\bperformance\s*(?:optim\w+|benchmark|boost|test)\b",              # performance optimization
    r"\bprocessor\s*(?:speed|test|benchmark|review|launch|spec\w*|architect\w+)\b",
    r"\bhardware\s*(?:spec|test|review|benchmark|perform\w+|launch|upgrade)\b",
    # 博彩/赌场 (casino gambling) 不是游戏行业法规
    r"\bcasino\b", r"\bsports?\s*bet", r"\bpoker\b", r"\bslot\s*machine\b",
    r"\bbookie\b", r"\bhorse\s*rac", r"\b赌场\b",
    r"\bfishing\b.*\b(?:season|rule)\b",  # 钓鱼 (fishing game 误匹配)
    r"\bNBA\b.*\bfine\b", r"\bNFL\b.*\bfine\b",  # 体育罚款
    r"\bprediction\s*market\b",  # 预测市场
    r"\bforex\b", r"คาสิโน", r"พนัน", r"บาคาร่า", r"สล็อต", r"หวย", r"joker\d*", r"\bufa\b",
    r"\bdtac\b", r"โปร โทร ฟรี", r"รับคะแนนฟรี",
    r"เกม\s*ยิง\s*ปลา|ยิงปลา|ได้\s*เงิน\s*จริง|ชนะรางวัลใหญ่",
    r"\bcuracao\b|\bcuraçao\b", r"\balberta\b.*\bonline gaming\b",
    r"\bwild game birds?\b|\bgame bird eggs?\b",
    r"\bWNBA\b|\bfootball\b|\bsoccer\b|\bWest Ham\b",
    r"\bgaming laptop review\b",
    r"เดินเกม|เปิดเกมคดี|เปลี่ยนเกม",  # 泰语中的政治/商业“博弈”隐喻
    r"\bjogo político\b", r"\bjuego político\b",
    r"操作して.*調査.*(?:ホラー)?ゲーム",  # 游戏剧情中的“调查”，不是监管调查
    r"\bIAG\b", r"\bInside Asian Gaming\b",  # 博彩行业会议
    r"\btribal\s*gam", r"\btribal\s*bet",  # 部落博彩
    r"\bskill\s*game.*(?:ban|legal|tax)\b",  # "技巧游戏"(实为赌博机)
    r"\bdigital\s*lotter", r"\blottery\s*game\b",  # 数字彩票
    r"\bPAGCOR\b",  # 菲律宾博彩
    r"\bwatchOS\b", r"\b64.?bit\s*require\b",  # 纯技术要求
    r"\bNBA\b", r"\bNFL\b", r"\bNHL\b", r"\bMLB\b",  # 体育联赛
    r"\bCOMESA\b",  # 非洲区域贸易组织(非游戏)
    r"\bCleveland\s*Cavaliers\b",
    r"骑士队",
    r"^(?!.*\b(?:games?|gaming|loot|gacha|mechanic)\b).*\blottery\b",  # 彩票（保留游戏内抽奖机制）
    r"^(?!.*\b(?:games?|gaming|loot|gacha|in.?app)\b).*\bbetting\b",  # 投注（保留游戏内博彩合规）
    # ── 行业会议 / 商务峰会（不涉及立法）────────────────────────────────
    r"\bPocket Gamer Connects\b",            # Pocket Gamer Connects 系列峰会
    r"\bThinkingData\b",                     # 数据分析服务商活动（非监管）
    r"\bGDC\s*\d{0,4}\b",                   # Game Developers Conference
    r"\bPAX\s*(?:East|West|South|Aus|Online)?\b",  # PAX 展会
    r"\bGamescom\b", r"\bE3\b",             # 欧洲/北美游戏展
    # 开发者大会主旨演讲（无监管内容）— 须有 game/gaming/apple/google 共现
    r"\bkeynote\b.*\b(?:game|gaming|apple|google|wwdc)\b",
    r"\binvestor\s*day\b",                   # 投资者日（无监管内容）
    r"\bearnings\s*call\b", r"\bQ[1-4]\s*result\b",  # 财报电话会
    # PP TUNAS 纯宣讲/培训活动；平台义务、执法、处罚和实施进展仍保留
    r"\b(?:sosialisasi|pelatihan|seminar|festival|literasi|edukasi)\b.*\bPP\s*TUNAS\b",
    r"\bPP\s*TUNAS\b.*\b(?:sosialisasi|pelatihan|seminar|festival|literasi|edukasi)\b",
    # "game industry X summit/expo" 组合（允许1个中间词，如"industry"）
    r"\b(?:game|gaming)\s+industry\s+(?:summit|expo)\b",
]


TRADITIONAL_CONSUMER_GOODS_SIGNALS = [
    r"健康食品|食品表示|食品安全|サプリ|サプリメント|医薬品|化粧品",
    r"\bhealth\s*food\b",
    r"\bfood\s*safety\b",
    r"\bfood\s*label(?:ing|ling)\b",
    r"\bsupplement(?:s)?\s+(?:advertis\w*|marketing|label(?:ing|ling)|claim\w*)\b",
    r"\b(?:advertis\w*|marketing|label(?:ing|ling)|claim\w*)\s+(?:for\s+)?supplements?\b",
    r"\bcosmetic\s+(?:product|advertis\w*|marketing|label(?:ing|ling)|claim\w*)\b",
    r"\b(?:advertis\w*|marketing|label(?:ing|ling)|claim\w*)\s+(?:for\s+)?cosmetics?\b",
    r"\bpharmaceutical\s+(?:product|advertis\w*|marketing|label(?:ing|ling)|claim\w*)\b",
    r"\b(?:advertis\w*|marketing|label(?:ing|ling)|claim\w*)\s+(?:for\s+)?pharmaceuticals?\b",
]

GAME_STRONG_SIGNALS = [
    r"\bgames?\b",
    r"\bgaming\b",
    r"\bmobile\s+games?\b",
    r"\bin-?game\b",
    r"\bapp\s*store\b",
    r"\bgoogle\s*play\b",
    r"\bIAP\b",
    r"\bmicrotransaction\b",
    r"\bloot\s*box(?:es)?\b",
    r"\bgacha\b",
    r"\bskins?\b",
    r"\bcosmetic\s+items?\b",
    r"ゲーム|ガチャ|課金",
]


def _is_traditional_consumer_goods_noise(text_lower: str) -> bool:
    """排除传统消费品监管噪音，但保留游戏内 cosmetics/skins/IAP 等合规动态。"""
    has_traditional_signal = any(
        re.search(pattern, text_lower, re.IGNORECASE)
        for pattern in TRADITIONAL_CONSUMER_GOODS_SIGNALS
    )
    if not has_traditional_signal:
        return False

    has_game_signal = any(
        re.search(pattern, text_lower, re.IGNORECASE)
        for pattern in GAME_STRONG_SIGNALS
    )
    return not has_game_signal


def is_legislation_relevant(article: dict) -> bool:
    """
    严格过滤：必须同时满足:
    1. 包含法规/监管行动信号词
    2. 包含游戏/互动娱乐信号词（官方/法律信源可豁免此条件）
    3. 不匹配排除词模式
    4. 非中国大陆内容
    """
    title = article.get("title", "")
    summary = article.get("summary", "")
    text = f"{title} {summary}"
    text_lower = text.lower()

    # 排除中国大陆
    if is_china_mainland(text):
        return False

    if _is_traditional_consumer_goods_noise(text_lower):
        return False

    # 检查排除词（在标题和摘要中）
    for p in EXCLUSION_PATTERNS:
        if re.search(p, text_lower, re.IGNORECASE):
            return False

    # 必须有法规信号
    has_regulatory = False
    for p in REGULATORY_SIGNALS:
        if re.search(p, text_lower, re.IGNORECASE):
            has_regulatory = True
            break
    if not has_regulatory:
        return False

    # 官方/法律信源：放宽但不取消数字行业关键词检查
    # 避免传统行业监管新闻（食品、通信贩卖等）混入，但不要求严格的"游戏"关键词
    # 信号词列表维护在 config/keywords.py → DIGITAL_INDUSTRY_SIGNALS
    source_tier = article.get("tier", "")
    if source_tier in ("official", "legal"):
        for signal in DIGITAL_INDUSTRY_SIGNALS:
            if signal.isascii():
                # ASCII 词用词边界匹配，避免 "ai" 误中 "oaic"、"complaint" 等
                if re.search(r"\b" + re.escape(signal) + r"\b", text_lower, re.IGNORECASE):
                    return True
            else:
                # CJK 等非 ASCII 直接子串匹配（每个字本身就是词边界）
                if signal in text_lower:
                    return True
        return False

    # 其他信源：必须有游戏信号
    has_game = False
    for p in GAME_SIGNALS:
        if re.search(p, text_lower, re.IGNORECASE):
            has_game = True
            break
    if not has_game:
        return False

    return True


def is_recent(article: dict, max_days: int = MAX_ARTICLE_AGE_DAYS) -> bool:
    try:
        article_date = datetime.strptime(article["date"], "%Y-%m-%d").date()
        cutoff = datetime.now().date() - timedelta(days=max_days)
        return article_date >= cutoff
    except (ValueError, KeyError):
        return True


# ─── 精确发布时间抓取 ─────────────────────────────────────────────────

# 已知RSS日期不可信的来源（会把抓取日期当作发布日期）
# Apple Developer News 与 Android Developers Blog 行为相同：RSS pubDate 为当日
RECYCLED_DATE_SOURCES = {
    "Android Developers Blog",
    "Apple Developer News",
}

def try_fetch_article_date(url: str, timeout: int = 8) -> Optional[str]:
    """
    从原始文章页面抓取更精确的发布时间。
    优先级: article:published_time > datePublished JSON-LD > <time> 标签
    返回 YYYY-MM-DD 格式，失败返回 None。
    """
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(
            url,
            headers={**HEADERS, "Accept": "text/html"},
            timeout=timeout,
            allow_redirects=True,
        )
        if not resp.ok:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Open Graph / article meta 标签
        for prop in [
            "article:published_time", "og:article:published_time",
            "datePublished", "date", "pubdate", "article:modified_time",
        ]:
            tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
            if tag and tag.get("content"):
                d = _parse_iso_date(tag["content"])
                if d:
                    return d

        # 2. JSON-LD
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                # data 可能是 dict 或 list
                entries = data if isinstance(data, list) else [data]
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    for key in ("datePublished", "dateCreated"):
                        val = entry.get(key, "")
                        d = _parse_iso_date(str(val))
                        if d:
                            return d
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        # 3. <time> 标签 - 先检查属性，再检查文本内容
        for time_tag in soup.find_all("time"):
            for attr in ("datetime", "pubdate", "content"):
                val = time_tag.get(attr, "")
                d = _parse_iso_date(str(val))
                if d:
                    return d
            # 检查 <time> 标签的可见文字（如 "February 26, 2026"）
            d = _parse_human_date(time_tag.get_text(" ", strip=True))
            if d:
                return d

        # 4. 在常见的日期容器元素中搜索（class 含 date / time / published / meta 等）
        DATE_CLASSES = re.compile(
            r"\b(?:date|time|published|updated|posted|created|pubdate|timestamp|byline|article-meta)\b",
            re.IGNORECASE,
        )
        for el in soup.find_all(class_=DATE_CLASSES):
            text = el.get_text(" ", strip=True)
            d = _parse_iso_date(text) or _parse_human_date(text)
            if d:
                return d

        # 5. 在 <header> / <article> 头部搜索可见日期文字（最多扫描前 2000 字符正文）
        for container in (soup.find("header"), soup.find("article"), soup.find("main")):
            if container is None:
                continue
            snippet = container.get_text(" ", strip=True)[:2000]
            d = _parse_human_date(snippet)
            if d:
                return d

    except Exception as e:
        logger.debug(f"[日期抓取] {url}: {e}")
    return None


def _parse_iso_date(s: str) -> Optional[str]:
    """从 ISO 8601 字符串提取 YYYY-MM-DD，超出今天则忽略"""
    if not s:
        return None
    s = s.strip()
    # 常见格式: 2026-02-15T10:30:00Z / 2026-02-15 / 20260215
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z", "%Y%m%d"):
        try:
            dt = datetime.strptime(s[:len(fmt.replace('%Y','0000').replace('%m','00')
                                        .replace('%d','00').replace('%H','00')
                                        .replace('%M','00').replace('%S','00')
                                        .replace('%z',''))], fmt)
            result = dt.strftime("%Y-%m-%d")
            # 合理性校验：2020-01-01 ~ 今天
            if "2020-01-01" <= result <= datetime.now().strftime("%Y-%m-%d"):
                return result
        except ValueError:
            continue
    # 简单提取 YYYY-MM-DD
    m = re.search(r"(202[0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))", s)
    if m:
        candidate = m.group(1)
        if candidate <= datetime.now().strftime("%Y-%m-%d"):
            return candidate
    return None


# 月份名称映射（英文全称和缩写）
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_human_date(text: str) -> Optional[str]:
    """
    从自然语言文本中提取英文日期，如 'February 26, 2026' 或 '26 Feb 2026'。
    返回 YYYY-MM-DD，失败返回 None。
    """
    if not text:
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    tl = text.lower()

    # 格式1: "Month DD, YYYY" 或 "Month DD YYYY"
    m = re.search(
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december'
        r'|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)'
        r'\s+(\d{1,2}),?\s+(20[2-9]\d)\b',
        tl,
    )
    if m:
        month = _MONTH_MAP.get(m.group(1))
        day, year = int(m.group(2)), int(m.group(3))
        if month:
            try:
                result = datetime(year, month, day).strftime("%Y-%m-%d")
                if "2020-01-01" <= result <= today:
                    return result
            except ValueError:
                pass

    # 格式2: "DD Month YYYY" (英国/欧洲格式)
    m = re.search(
        r'\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december'
        r'|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)'
        r'\s+(20[2-9]\d)\b',
        tl,
    )
    if m:
        day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
        month = _MONTH_MAP.get(month_name)
        if month:
            try:
                result = datetime(year, month, day).strftime("%Y-%m-%d")
                if "2020-01-01" <= result <= today:
                    return result
            except ValueError:
                pass

    return None


def enrich_article_dates(articles: List[dict]) -> List[dict]:
    """
    对通过过滤的文章，尝试从原文页面获取更精确的发布时间。
    只对来源日期不可信 OR 日期为今天的文章执行（节省时间）。
    """
    today = datetime.now().strftime("%Y-%m-%d")

    def needs_enrichment(a: dict) -> bool:
        return (
            a.get("source") in RECYCLED_DATE_SOURCES
            or a.get("date", "") >= today  # 日期为今天（疑似动态RSS）
        )

    to_enrich = [a for a in articles if needs_enrichment(a)]
    if not to_enrich:
        return articles

    logger.info(f"[日期校正] 对 {len(to_enrich)} 条文章抓取精确发布时间...")

    url_to_date: dict = {}

    def fetch_date(article: dict):
        url = article.get("url", "")
        result = try_fetch_article_date(url)
        if result:
            url_to_date[url] = result

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_date, a) for a in to_enrich]
        concurrent.futures.wait(futures, timeout=30)

    enriched = 0
    for a in articles:
        url = a.get("url", "")
        if url in url_to_date and url_to_date[url] != a.get("date"):
            logger.debug(f"[日期校正] {a.get('title','')[:40]} {a.get('date')} → {url_to_date[url]}")
            a["date"] = url_to_date[url]
            enriched += 1

    logger.info(f"[日期校正] 完成, 更新 {enriched} 条")
    return articles


# ─── 聚合抓取入口 ─────────────────────────────────────────────────────

def fetch_all_rss() -> List[dict]:
    all_items = []
    rss_sources = [f for f in RSS_FEEDS if f.get("type") == "rss"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        futures = {executor.submit(fetch_rss_feed, feed): feed for feed in rss_sources}
        for future in concurrent.futures.as_completed(futures):
            feed = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as e:
                logger.error(f"抓取失败 {feed['name']}: {e}")

    return all_items


def fetch_google_news_all(max_days: int = MAX_ARTICLE_AGE_DAYS, daily_mode: bool = False) -> List[dict]:
    """
    聚合所有语言/地区的 Google News 查询。
    daily_mode=True：使用精选小查询集，控制请求量避免 IP 限速，每查询取前 20 条。
    weekly 模式：使用全量 KEYWORDS，以获得最大覆盖。
    """
    all_items = []
    when = f" when:{1 if daily_mode else max_days}d"
    max_results_per_query = 20 if daily_mode else 0
    # 英文通用查询降噪后缀（附加 -conference -summit -funding -investment）
    noise = INDUSTRY_QUERY_NOISE_SUFFIX

    if daily_mode:
        # 日报：精选查询，约 40 秒完成，避免 IP 限速
        locale_groups = [
            [(kw + when, "en_US") for kw in DAILY_GOOGLE_NEWS_EN],
            [(kw + when, "ja_JP") for kw in DAILY_GOOGLE_NEWS_JA],
            [(kw + when, "ko_KR") for kw in DAILY_GOOGLE_NEWS_KO],
            (
                [(kw + when, "vi_VN") for kw in DAILY_GOOGLE_NEWS_VI]
                + [(kw + when, "pt_BR") for kw in DAILY_GOOGLE_NEWS_PT]
                + [(kw + when, "th_TH") for kw in DAILY_GOOGLE_NEWS_TH]
                + [(kw + when, "id_ID") for kw in DAILY_GOOGLE_NEWS_ID]
                + [(kw + when, "zh_TW") for kw in DAILY_GOOGLE_NEWS_ZH_TW]
                + [(kw + when, "ar_SA") for kw in DAILY_GOOGLE_NEWS_AR]
                + [(kw + when, "de_DE") for kw in DAILY_GOOGLE_NEWS_DE]
                + [(kw + when, "fr_FR") for kw in DAILY_GOOGLE_NEWS_FR]
                + [(kw + when, "es_MX") for kw in DAILY_GOOGLE_NEWS_ES]
            ),
        ]
    else:
        # 周报：全量查询，最大覆盖
        locale_groups = [
            # 1. 英语圈：美国（最大量，优先发出）
            [(kw + noise + when, "en_US") for kw in KEYWORDS["en"]],
            # 2. 英语圈：英国 / 澳洲 / 新加坡 补充视角 + PC 平台专项
            (
                [(kw + noise + when, "en_UK") for kw in KEYWORDS["en"][30:50]]
                + [(kw + when, "en_UK") for kw in PC_PLATFORM_KEYWORDS_EN]
                + [(kw + noise + when, "en_AU") for kw in KEYWORDS["en"][10:30]]
                + [(kw + noise + when, "en_SG") for kw in KEYWORDS["en"][30:50]]
            ),
            # 3. 官方政府域名精准查询（site:，不加降噪后缀）
            [(kw + when, "en_US") for kw in OFFICIAL_SITE_QUERIES],
            # 4. 日语
            [(kw + when, "ja_JP") for kw in KEYWORDS["ja"]],
            # 5. 韩语
            [(kw + when, "ko_KR") for kw in KEYWORDS["ko"]],
            # 6. 越南语 + 印尼语
            (
                [(kw + when, "vi_VN") for kw in KEYWORDS.get("vi", [])]
                + [(kw + when, "id_ID") for kw in KEYWORDS.get("id", [])]
            ),
            # 7. 繁中 + 泰语
            (
                [(kw + when, "zh_TW") for kw in KEYWORDS.get("zh_tw", [])]
                + [(kw + when, "th_TH") for kw in KEYWORDS.get("th", [])]
            ),
            # 8. 欧洲本地语言 + 南美 + 中东（量少，合并一组）
            (
                [(kw + when, "de_DE") for kw in KEYWORDS.get("de", [])]
                + [(kw + when, "fr_FR") for kw in KEYWORDS.get("fr", [])]
                + [(kw + when, "pt_BR") for kw in KEYWORDS.get("pt", [])]
                + [(kw + when, "es_MX") for kw in KEYWORDS.get("es", [])]
                + [(kw + when, "ar_SA") for kw in KEYWORDS.get("ar", [])]
            ),
        ]

    # Google News 所有请求均指向同一域名，并发只会加剧限速。
    # 改为严格顺序执行：同一时刻最多 1 个请求在途，组间额外冷却。
    _GROUP_COOLDOWN = 5.0   # 秒，locale 组间冷却
    _TASK_INTERVAL  = 2.0   # 秒，每次请求后等待（顺序模式）

    for g_idx, group in enumerate(locale_groups):
        if g_idx > 0:
            time.sleep(_GROUP_COOLDOWN)
        for query, region in group:
            try:
                items = fetch_google_news(query, region, max_results_per_query)
                all_items.extend(items)
            except Exception as e:
                logger.error(f"Google News 搜索失败 '{query}': {e}")
            time.sleep(_TASK_INTERVAL)

    return all_items


# ─── GDELT DOC API 抓取 ──────────────────────────────────────────────
#
# GDELT 补充 Google News 覆盖薄弱的两类来源：
#   1. 东南亚/中东官方政府网站（越南 mic.gov.vn、印尼 Kominfo 等）
#   2. theme:LEGISLATION / theme:REGULATION 预标注的全球立法类文章
#
# 文档: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

_GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"

_GDELT_LANG_MAP = {
    "English": "en", "Vietnamese": "vi", "Indonesian": "id",
    "Thai": "th", "Korean": "ko", "Japanese": "ja",
    "Arabic": "ar", "German": "de", "French": "fr",
    "Portuguese": "pt", "Spanish": "es",
}

# GDELT 仅作为每日兜底。查询保持少而宽，避免按国家逐条请求触发免费接口限速。
_GDELT_QUERIES = [
    (
        '(theme:LEGISLATION OR theme:REGULATION)'
        ' (game OR gaming OR "video game" OR "online game" OR "loot box" OR gacha)'
        ' (law OR regulation OR privacy OR children OR consumer OR license)',
        "全球-立法监管",
    ),
    (
        '(game OR gaming OR "video game")'
        ' (enforcement OR investigation OR fine OR penalty OR lawsuit'
        ' OR "class action" OR settlement OR injunction OR ban)',
        "全球-执法诉讼",
    ),
    (
        '(ゲーム OR 게임 OR "trò chơi" OR permainan OR jogo OR videojuegos OR 遊戲 OR เกม OR ألعاب)'
        ' (規制 OR 규제 OR nghị định OR regulasi OR regulação OR regulación'
        ' OR 法規 OR กฎหมาย OR تنظيم OR fine OR lawsuit)',
        "弱覆盖市场-本地语",
    ),
]


def _parse_gdelt_date(seendate: str) -> str:
    """将 GDELT seendate (20260310T031000Z) 转为 YYYY-MM-DD。"""
    try:
        return datetime.strptime(seendate[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def fetch_gdelt_all(daily_mode: bool = False) -> List[dict]:
    """
    通过 GDELT DOC API 补充抓取合规监管文章。
    返回格式与 fetch_rss_feed / fetch_google_news 一致，直接进入下游过滤流水线。
    """
    timespan = "1d" if daily_mode else "7d"
    all_items: List[dict] = []
    started = time.monotonic()
    requests_made = 0
    successful_queries = 0
    rate_limits = 0
    stopped_for_rate_limit = False

    for query_index, (query, label) in enumerate(_GDELT_QUERIES):
        if query_index:
            time.sleep(12)
        for attempt in range(2):   # 429 时最多重试一次
            try:
                requests_made += 1
                resp = requests.get(
                    _GDELT_API,
                    params={
                        "query":      query,
                        "mode":       "artlist",
                        "maxrecords": 25,
                        "timespan":   timespan,
                        "format":     "json",
                        "sort":       "DateDesc",
                    },
                    timeout=20,
                )
                if resp.status_code == 429:
                    rate_limits += 1
                    if daily_mode:
                        logger.warning(
                            f"[GDELT] {label} 触发限速，日报模式立即停止补充抓取"
                        )
                        stopped_for_rate_limit = True
                        break
                    if attempt == 0:
                        retry_after = resp.headers.get("Retry-After", "5")
                        try:
                            wait_seconds = min(15.0, max(1.0, float(retry_after)))
                        except (TypeError, ValueError):
                            wait_seconds = 5.0
                        logger.warning(
                            f"[GDELT] {label} 触发限速，等待 {wait_seconds:g} 秒后重试…"
                        )
                        time.sleep(wait_seconds)
                        continue
                    logger.warning("[GDELT] 持续限速，本轮停止 GDELT 补充抓取")
                    stopped_for_rate_limit = True
                    break
                resp.raise_for_status()
                articles = resp.json().get("articles") or []
                count = 0
                for a in articles:
                    title = _sanitize_title(a.get("title", ""))
                    if not title:
                        continue
                    all_items.append({
                        "title":   title,
                        "url":     a.get("url", ""),
                        "date":    _parse_gdelt_date(a.get("seendate", "")),
                        "summary": "",
                        "source":  a.get("domain", "GDELT"),
                        "region":  "",
                        "lang":    _GDELT_LANG_MAP.get(a.get("language", ""), "en"),
                    })
                    count += 1
                successful_queries += 1
                logger.info(f"[GDELT] {label}: 获取 {count} 条")
                break
            except Exception as e:
                logger.warning(f"[GDELT] {label} 请求失败: {e}")
                break
        if stopped_for_rate_limit:
            break

    logger.info(
        "[GDELT统计] 请求=%d 成功查询=%d 429=%d 贡献=%d 耗时=%.1fs",
        requests_made,
        successful_queries,
        rate_limits,
        len(all_items),
        time.monotonic() - started,
    )

    return all_items


def _is_foreign_commentary(lang: str, region: str) -> bool:
    """兼容旧调用：文章语言不再作为删除事件的依据。"""
    return False


def _count_by_language(items: List[dict]) -> Counter:
    return Counter((item.get("lang") or "unknown").split("-")[0] for item in items)


def _log_language_funnel(stage: str, items: List[dict]) -> None:
    counts = _count_by_language(items)
    detail = " ".join(f"{lang}={counts[lang]}" for lang in sorted(counts))
    logger.info(f"[语种漏斗] {stage}: total={len(items)} {detail}".rstrip())


def fetch_and_process(max_days: int = MAX_ARTICLE_AGE_DAYS, daily_mode: bool = False) -> List[LegislationItem]:
    """
    完整抓取 & 处理流水线:
    1. 抓取 RSS + Google News
    2. 严格过滤 (法规 + 游戏 + 排除中国大陆 + 排除噪音)
    3. 分类为 LegislationItem
    4. 按事件实际司法辖区分类（语言仅作为输入信息，不用于删除）

    daily_mode=True: Google News 强制 when:1d，每查询限 10 条，适合日报场景。
    """
    logger.info("=" * 60)
    logger.info(f"开始抓取数据 ({'日报模式 when:1d' if daily_mode else f'when:{max_days}d'})...")

    # 1. 抓取
    rss_items = fetch_all_rss()
    logger.info(f"RSS 抓取完成: {len(rss_items)} 条原始数据")

    news_items = fetch_google_news_all(max_days, daily_mode=daily_mode)
    logger.info(f"Google News 抓取完成: {len(news_items)} 条原始数据")

    gdelt_items = fetch_gdelt_all(daily_mode=daily_mode)
    logger.info(f"GDELT 抓取完成: {len(gdelt_items)} 条原始数据")

    all_raw = rss_items + news_items + gdelt_items
    logger.info(f"合计原始数据: {len(all_raw)} 条")
    _log_language_funnel("raw", all_raw)

    # 2. 去重 (按 title 归一化)
    seen_titles = set()
    unique_items = []
    for item in all_raw:
        title_key = re.sub(r"\s+", " ", item["title"].strip().lower())
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_items.append(item)
    logger.info(f"去重后: {len(unique_items)} 条")
    _log_language_funnel("title_unique", unique_items)

    # 3. 严格过滤: 法规+游戏+排除中国大陆+排除噪音+时间范围
    relevant = [a for a in unique_items if is_legislation_relevant(a) and is_recent(a, max_days)]
    logger.info(f"严格过滤后: {len(relevant)} 条立法相关文章")
    _log_language_funnel("rule_relevant", relevant)

    # 4. 日期精准化（对来源日期不可信的文章抓取真实发布时间）
    relevant = enrich_article_dates(relevant)
    before_date_recheck = len(relevant)
    relevant = [article for article in relevant if is_recent(article, max_days)]
    removed_after_enrichment = before_date_recheck - len(relevant)
    if removed_after_enrichment:
        logger.info(
            f"[日期校正] 二次时间过滤移除旧文 {removed_after_enrichment} 条"
        )
    _log_language_funnel("date_rechecked", relevant)

    # 5. 分类。外语媒体可以报道任何司法辖区，跨语言重复留给翻译后去重。
    legislation_items = [classify_article(article) for article in relevant]
    classified_dicts = [item.to_dict() for item in legislation_items]
    _log_language_funnel("classified", classified_dicts)
    logger.info(f"分类完成: {len(legislation_items)} 条立法动态")
    return legislation_items
