"""
翻译模块 - 将摘要翻译为中文（标题保留原文）
使用 deep-translator (Google Translate)
"""

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator
    _HAS_TRANSLATOR = True
except ImportError:
    _HAS_TRANSLATOR = False
    logger.warning("deep-translator 未安装, 翻译功能不可用。运行: pip install deep-translator")

# 简单内存缓存，避免重复翻译
_cache: dict = {}


def translate_to_zh(text: str, source_lang: str = "auto") -> str:
    """将文本翻译为中文，失败时返回原文"""
    if not text or not text.strip():
        return text

    if not _HAS_TRANSLATOR:
        return text

    # 已经是中文就不翻译
    if _is_mostly_chinese(text):
        return text

    # 检查缓存
    cache_key = text[:200]
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        result = GoogleTranslator(source=source_lang, target="zh-CN").translate(text[:500])
        if result:
            _cache[cache_key] = result
            return result
    except Exception as e:
        logger.debug(f"翻译失败: {e}")

    return text


def _is_mostly_chinese(text: str) -> bool:
    """判断文本是否主要是中文"""
    if not text:
        return False
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_count > len(text) * 0.3


def _build_source_text(item_dict: dict) -> str:
    """
    构建用于翻译的文本，尽量提供充足上下文。
    - 清除 RSS 常见的尾部省略号（表示文本被截断）
    - 当摘要有实质内容时，拼接标题+摘要以获得更完整的中文概括
    """
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()

    # 清理 RSS 截断标记（"... [+1234 chars]" / "…" 结尾等）
    summary = re.sub(r"\s*[\[【][\+\d].*?[\]】]\s*$", "", summary).strip()
    summary = re.sub(r"\s*\.{2,}\s*$", "", summary).strip()
    summary = re.sub(r"\s*…\s*$", "", summary).strip()

    if not summary or len(summary) < 20:
        return title

    # 判断摘要是否只是在重复标题
    title_norm = re.sub(r"\s+", " ", title.lower())
    summary_norm = re.sub(r"\s+", " ", summary.lower())
    title_prefix = title_norm[:50]

    if summary_norm.startswith(title_prefix):
        # 摘要以标题开头：取标题 + 摘要中标题之后的部分
        extra = summary[len(title_prefix):].strip(" .-")
        if len(extra) > 20:
            combined = f"{title}. {extra}"
        else:
            combined = title
    else:
        # 摘要有独立内容：完整拼接
        sep = "。" if title.endswith(("。", "！", "？")) else ". "
        combined = f"{title}{sep}{summary}"

    return combined[:500]


def _ensure_complete_sentence(text: str) -> str:
    """
    确保翻译结果以完整句子结尾。
    若文本在句中截断，则回退到最后一个句末标点处。
    """
    if not text:
        return text
    # 已是完整句子
    if text[-1] in "。！？.!?":
        return text
    # 找最后一个句末标点，保留至少一半内容
    for sep in ["。", "！", "？", ".", "!", "?"]:
        idx = text.rfind(sep)
        if idx > len(text) * 0.4:
            return text[:idx + 1]
    return text


def translate_item_fields(item_dict: dict) -> dict:
    """
    生成中文摘要（summary_zh）和中文标题（title_zh）。
    - title_zh:  单独翻译标题，质量更稳定，供 HTML/飞书优先展示
    - summary_zh: 综合标题+摘要翻译，确保完整句子
    """
    # 1. 翻译标题 → title_zh
    title = (item_dict.get("title") or "").strip()
    if title and not _is_mostly_chinese(title):
        item_dict["title_zh"] = translate_to_zh(title[:200])
        time.sleep(0.15)
    else:
        item_dict["title_zh"] = title

    # 2. 翻译摘要 → summary_zh
    source_text = _build_source_text(item_dict)
    if _is_mostly_chinese(source_text):
        item_dict["summary_zh"] = source_text
    else:
        raw = translate_to_zh(source_text)
        item_dict["summary_zh"] = _ensure_complete_sentence(raw)
        time.sleep(0.2)

    return item_dict
