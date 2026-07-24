"""Persistent event identity helpers used before SQLite/Base writes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, is_dataclass

from utils import _bigram_sim, normalize_jurisdiction


_ENTITY_PATTERNS = [
    ("pp-tunas", re.compile(r"\bPP\s*TUNAS\b|PP\s*(?:Nomor\s*)?17\s*(?:Tahun\s*)?2025", re.I)),
    ("vn-decree-147", re.compile(r"Ngh[iị]\s*đ[iị]nh\s*147/2024|147/2024/NĐ-CP", re.I)),
    ("vn-decree-174", re.compile(r"Ngh[iị]\s*đ[iị]nh\s*174/2026|174/2026/NĐ-CP", re.I)),
    ("ab-1921", re.compile(r"\bAB\s*1921\b|Protect\s+Our\s+Games", re.I)),
    ("kr-probability-items", re.compile(r"확률형\s*아이템|概率型(?:物品|道具)|probabilit(?:y|ies).{0,12}(?:item|loot)", re.I)),
    ("dma", re.compile(r"\bDMA\b|Digital\s+Markets\s+Act|数字市场法|數位市場法", re.I)),
    ("dsa", re.compile(r"\bDSA\b|Digital\s+Services\s+Act|数字服务法|數位服務法", re.I)),
    ("ai-act", re.compile(r"\bAI\s+Act\b|人工智能法案|人工智慧法案", re.I)),
    ("gdpr", re.compile(r"\bGDPR\b|通用数据保护条例|一般資料保護規則", re.I)),
    ("coppa", re.compile(r"\bCOPPA\b|Children'?s\s+Online\s+Privacy", re.I)),
    ("ftc", re.compile(r"\bFTC\b|Federal\s+Trade\s+Commission", re.I)),
    ("kca", re.compile(r"\bKCA\b|한국소비자원|韩国消费者院", re.I)),
    ("grac", re.compile(r"\bGRAC\b|게임물관리위원회", re.I)),
    ("komdigi", re.compile(r"\bKomdigi\b|Kementerian\s+Komunikasi\s+dan\s+Digital", re.I)),
    ("nintendo", re.compile(r"\bNintendo\b|任天堂", re.I)),
    ("microsoft", re.compile(r"\bMicrosoft\b|\bXbox\b|微软", re.I)),
    ("google", re.compile(r"\bGoogle\b|Google\s+Play|Play\s+Store|谷歌", re.I)),
    ("apple", re.compile(r"\bApple\b|App\s+Store|苹果", re.I)),
    ("steam", re.compile(r"\bSteam\b|\bValve\b", re.I)),
    ("roblox", re.compile(r"\bRoblox\b|罗布乐思", re.I)),
    ("nexon", re.compile(r"\bNexon\b|넥슨", re.I)),
]

_TOPIC_PATTERNS = [
    ("minor", re.compile(r"child(?:ren)?|minor|underage|未成年|儿童|兒童|아동|미성년|anak", re.I)),
    ("lootbox", re.compile(r"loot\s*box|gacha|probabilit|抽卡|概率|機率|ガチャ|확률형", re.I)),
    ("refund", re.compile(r"refund|reimburse|退款|返还|返還|환불|pengembalian", re.I)),
    ("lawsuit", re.compile(r"lawsuit|class\s*action|litigat|sued?|诉讼|起诉|訴訟|소송|gugatan", re.I)),
    ("fine", re.compile(r"fine|penalt|sanction|罚款|处罚|裁罰|과징금|벌금|denda|sanksi", re.I)),
    ("distribution", re.compile(r"app\s*store|google\s*play|play\s*store|sideload|third.party\s+store|应用商店|應用商店|侧载|側載", re.I)),
    ("payment", re.compile(r"payment|commission|fee|\bIAP\b|支付|抽成|결제|pembayaran", re.I)),
    ("privacy", re.compile(r"privacy|data\s+protect|隐私|個資|数据保护|개인정보|privasi", re.I)),
    ("ai", re.compile(r"artificial\s+intelligence|generative\s+AI|人工智能|人工智慧|生成式\s*AI", re.I)),
    ("rating", re.compile(r"age\s+rating|classification|分级|分級|レーティング|등급", re.I)),
    ("consumer", re.compile(r"consumer|消费者|消費者|소비자|konsumen", re.I)),
]

_SPECIFIC_LAW_KEYS = {"pp-tunas", "vn-decree-147", "vn-decree-174", "ab-1921"}
_COMPANY_KEYS = {
    "nintendo", "microsoft", "google", "apple", "steam", "roblox", "nexon",
}

_STAGE_EVIDENCE = re.compile(
    r"enact|enter(?:s|ed)?\s+into\s+force|effective|issued|adopted|amend|revis|repeal|revok|abolish|"
    r"enforc|fine|penalt|ruling|judgment|settlement|deadline|require"
    r"|发布|公布|出台|生效|实施|施行|修订|修正|废止|廢止|撤销|撤銷|执法|处罚|罚款|裁决|判决|和解|期限|要求"
    r"|시행|발표|공포|개정|처분|과징금|판결"
    r"|施行|公布|改正|処分|課徴金|判決"
    r"|diterbitkan|ditetapkan|berlaku|diubah|denda|putusan|mewajibkan"
    r"|ban\s+hành|có\s+hiệu\s+lực|sửa\s+đổi|xử\s+phạt|phán\s+quyết",
    re.I,
)

_STATUS_RANK = {
    "已废止": 1,
    "立法动态": 2,
    "已提案": 3,
    "立法进行中": 4,
    "草案/征求意见": 5,
    "修订变更": 6,
    "执法动态": 7,
    "即将生效": 8,
    "已生效": 9,
}


def _item_dict(item) -> dict:
    if isinstance(item, dict):
        return item
    if is_dataclass(item):
        return asdict(item)
    return vars(item)


def _event_text(item) -> str:
    data = _item_dict(item)
    return " ".join(filter(None, (
        data.get("title", ""),
        data.get("title_zh", ""),
        data.get("summary", ""),
        data.get("summary_zh", ""),
    )))


def _normalized_title(item) -> str:
    data = _item_dict(item)
    title = data.get("title_zh") or data.get("title") or ""
    title = re.sub(r"^\s*[\[【][^\]】]{1,16}[\]】]\s*", "", title)
    return re.sub(r"[^\w\u3400-\u9fff]+", "", title.lower())


def _matched_entity_keys(item) -> set[str]:
    text = _event_text(item)
    return {name for name, pattern in _ENTITY_PATTERNS if pattern.search(text)}


def build_event_key(item) -> str:
    """Build a stable internal key without exposing it to Bitable."""
    data = _item_dict(item)
    text = _event_text(data)
    entities = [name for name, pattern in _ENTITY_PATTERNS if pattern.search(text)]
    topics = [name for name, pattern in _TOPIC_PATTERNS if pattern.search(text)]

    specific = next((name for name in entities if name in _SPECIFIC_LAW_KEYS), "")
    if specific:
        return f"strong:{specific}"

    if entities and topics:
        core = ":".join(sorted(set(entities)) + sorted(set(topics)))
        return f"strong:{core}"

    jurisdiction = normalize_jurisdiction(data.get("jurisdiction", ""))
    title = _normalized_title(data)
    fallback = f"{jurisdiction}|{title}"
    digest = hashlib.sha1(fallback.encode("utf-8")).hexdigest()[:20]
    return f"title:{digest}"


def same_event(left, right) -> bool:
    """Conservative event match for records no more than 30 days apart."""
    left_data, right_data = _item_dict(left), _item_dict(right)
    left_key = left_data.get("event_key") or build_event_key(left_data)
    right_key = right_data.get("event_key") or build_event_key(right_data)
    left_geo = normalize_jurisdiction(left_data.get("jurisdiction", "")) or left_data.get("region", "")
    right_geo = normalize_jurisdiction(right_data.get("jurisdiction", "")) or right_data.get("region", "")
    if left_geo and right_geo and left_geo != right_geo:
        return False

    left_companies = _matched_entity_keys(left_data) & _COMPANY_KEYS
    right_companies = _matched_entity_keys(right_data) & _COMPANY_KEYS
    if left_companies and right_companies and left_companies.isdisjoint(right_companies):
        return False

    left_title, right_title = _normalized_title(left_data), _normalized_title(right_data)
    title_similarity = _bigram_sim(left_title, right_title)
    if left_key.startswith("strong:") and left_key == right_key:
        if left_key.removeprefix("strong:") in _SPECIFIC_LAW_KEYS:
            return True
        threshold = 0.55 if left_geo and right_geo else 0.60
        return title_similarity >= threshold

    if left_title and left_title == right_title:
        return True

    left_category = left_data.get("category_l1")
    same_category = bool(left_category) and left_category == right_data.get("category_l1")
    return bool(
        left_geo
        and left_geo == right_geo
        and same_category
        and title_similarity >= 0.62
    )


def is_meaningful_progress(existing, incoming) -> bool:
    """Allow a later legal stage only when the incoming raw text supports it."""
    existing_data, incoming_data = _item_dict(existing), _item_dict(incoming)
    old_rank = _STATUS_RANK.get(existing_data.get("status", ""), 0)
    new_rank = _STATUS_RANK.get(incoming_data.get("status", ""), 0)
    raw_text = " ".join(filter(None, (
        incoming_data.get("title", ""), incoming_data.get("summary", ""),
    )))
    if not _STAGE_EVIDENCE.search(raw_text):
        return False

    old_status = existing_data.get("status", "")
    new_status = incoming_data.get("status", "")
    if new_status == old_status:
        return False
    if new_status in {"修订变更", "执法动态", "已废止"}:
        return True
    return new_rank > old_rank
