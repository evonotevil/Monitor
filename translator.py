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
    构建用于翻译的文本。
    Google News 的 description 通常就是标题 + 来源名，所以优先用标题。
    若摘要比标题长且内容不同，则拼接标题+摘要以获得更丰富的中文概括。
    """
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()

    # 若摘要基本等于标题（Google News 常见情况），只翻译标题
    title_norm = re.sub(r"\s+", " ", title.lower())
    summary_norm = re.sub(r"\s+", " ", summary.lower())
    if not summary or summary_norm.startswith(title_norm[:40]):
        return title

    # 摘要有额外信息时，拼接翻译
    combined = f"{title}。{summary}" if title else summary
    return combined[:500]


def translate_item_fields(item_dict: dict) -> dict:
    """
    生成中文摘要概括（summary_zh），标题保留原文。
    - summary_zh: 综合标题+摘要翻译为简明中文概括（必须有）
    - title_zh: 不生成（保留原文标题）
    """
    source_text = _build_source_text(item_dict)

    if _is_mostly_chinese(source_text):
        item_dict["summary_zh"] = source_text
    else:
        item_dict["summary_zh"] = translate_to_zh(source_text)
        time.sleep(0.2)  # 控制请求速率

    # title_zh 不翻译，reporter 直接展示原文
    item_dict["title_zh"] = ""

    return item_dict
