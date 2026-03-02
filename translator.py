"""
翻译/摘要模块

优先路径：公司内部大模型（OpenAI 兼容 API）
  - 标题重塑："[地区/机构]+[动作]+[事件核心]" 纯中文结构
  - 摘要生成：监管对象 + 核心义务 + 违规后果，≤50 字，不重复标题

回退路径：Google Translate（LLM_API_KEY 未配置时）
"""

import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── 内部大模型客户端（OpenAI 兼容） ──────────────────────────────────

_LLM_BASE_URL = "https://llm-proxy.lilithgames.com/v1"
_LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
_LLM_MODEL    = os.environ.get("LLM_MODEL", "gpt-4o-mini")   # 可通过环境变量覆盖

try:
    from openai import OpenAI as _OpenAI
    _AI_CLIENT = _OpenAI(api_key=_LLM_API_KEY, base_url=_LLM_BASE_URL, timeout=25.0) if _LLM_API_KEY else None
    _HAS_AI = bool(_LLM_API_KEY)
    if not _HAS_AI:
        logger.info("LLM_API_KEY 未设置，将使用 Google Translate 回退")
except ImportError:
    _AI_CLIENT = None
    _HAS_AI = False
    logger.warning("openai 未安装，将使用 Google Translate。运行: pip install openai")

# ── Google Translate 回退 ─────────────────────────────────────────────

try:
    from deep_translator import GoogleTranslator
    _HAS_TRANSLATOR = True
except ImportError:
    _HAS_TRANSLATOR = False
    logger.warning("deep-translator 未安装。运行: pip install deep-translator")

_cache: dict = {}

# ── AI Prompt ─────────────────────────────────────────────────────────

_AI_SYSTEM = """你是全球游戏行业合规法规分析师，负责将法规新闻转化为规范中文标题和摘要。

【标题规则】
- 纯中文，禁止任何英文字母（法规专有名词须译为通用中文名）
- 结构："[地区/机构] [动作] [事件核心]"，可用冒号分隔，如"印度更新信息技术规则：严管深伪内容与游戏时长"
- 30字以内

【摘要规则】
- 纯中文，严格50字以内
- 必须依次包含：①监管对象 ②核心限制或义务 ③违规后果（如无则省略）
- 禁止重复标题文字，聚焦对游戏企业的实际合规影响
- 示例："游戏平台须在30日内完成深伪内容过滤备案，限日均游戏时长3小时；违者罚款最高500万卢比。"

【输出格式】
仅输出合法JSON，不含任何其他文字：
{"title_zh": "...", "summary_zh": "..."}"""


# ── 文章正文抓取（最优先给 AI 提供上下文）────────────────────────────

def _fetch_article_body(url: str) -> str:
    """尝试获取文章正文前 500 字；超时或失败时静默返回空字符串。"""
    if not url or not url.startswith("http"):
        return ""
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html",
        }
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if not resp.ok:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        # 移除噪音标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        # 优先提取语义化正文区域
        for selector in ("article", "main", "[class*='article-body']",
                         "[class*='post-content']", "[class*='entry-content']"):
            el = soup.select_one(selector)
            if el:
                text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                if len(text) > 80:
                    return text[:500]
        # 兜底：body 全文
        body = soup.find("body")
        if body:
            return re.sub(r"\s+", " ", body.get_text(" ", strip=True))[:500]
    except Exception:
        pass
    return ""


# ── Claude AI 处理 ────────────────────────────────────────────────────

def _ai_process(title: str, summary: str, body_snippet: str = "") -> Optional[dict]:
    """
    调用 Claude AI 重塑标题、生成深度摘要。
    返回 {"title_zh": ..., "summary_zh": ...} 或 None（调用失败时）。
    """
    if not _HAS_AI or not _AI_CLIENT:
        return None

    body_part = (
        f"\n文章正文片段（前500字）：{body_snippet}"
        if body_snippet and len(body_snippet) > 50
        else ""
    )
    user_msg = (
        f"英文标题：{title}\n"
        f"原始摘要：{summary or '（无摘要，请根据标题进行深度推导）'}"
        f"{body_part}"
    )

    try:
        resp = _AI_CLIENT.chat.completions.create(
            model=_LLM_MODEL,
            max_tokens=300,
            messages=[
                {"role": "system", "content": _AI_SYSTEM},
                {"role": "user",   "content": user_msg},
            ],
        )
        text = resp.choices[0].message.content.strip()
        logger.info(f"[AI raw] {text[:200]}")   # 打印返回内容，方便排查

        # 兼容三种输出格式：纯 JSON / ```json...``` / 含前缀文字
        # 1. 先尝试剥离 markdown 代码块
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = code_block.group(1) if code_block else None
        # 2. 没有代码块则直接找 {...}
        if not json_str:
            plain = re.search(r"\{.*\}", text, re.DOTALL)
            json_str = plain.group() if plain else None

        if json_str:
            data = json.loads(json_str)
            title_zh  = (data.get("title_zh")  or "").strip()
            summary_zh = (data.get("summary_zh") or "").strip()
            if title_zh and summary_zh:
                return {"title_zh": title_zh, "summary_zh": summary_zh}
            logger.warning(f"[AI] JSON 解析成功但字段为空: {json_str[:100]}")
        else:
            logger.warning(f"[AI] 返回内容中未找到 JSON: {text[:200]}")

    except Exception as e:
        logger.warning(f"[AI] 调用异常: {type(e).__name__}: {e}")
    return None


# ── Google Translate 工具函数（回退路径）─────────────────────────────

def _is_mostly_chinese(text: str) -> bool:
    if not text:
        return False
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_count > len(text) * 0.3


def translate_to_zh(text: str, source_lang: str = "auto") -> str:
    """将文本翻译为中文，失败时返回原文"""
    if not text or not text.strip():
        return text
    if not _HAS_TRANSLATOR:
        return text
    if _is_mostly_chinese(text):
        return text
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


def _build_source_text(item_dict: dict) -> str:
    """构建用于翻译的文本，智能拼接标题+摘要，清理 RSS 截断标记。"""
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()
    # 清理 RSS 截断标记
    summary = re.sub(r"\s*[\[【][\+\d].*?[\]】]\s*$", "", summary).strip()
    summary = re.sub(r"\s*\.{2,}\s*$", "", summary).strip()
    summary = re.sub(r"\s*…\s*$", "", summary).strip()

    if not summary or len(summary) < 20:
        return title

    title_norm = re.sub(r"\s+", " ", title.lower())
    summary_norm = re.sub(r"\s+", " ", summary.lower())
    if summary_norm.startswith(title_norm[:50]):
        extra = summary[len(title_norm[:50]):].strip(" .-")
        combined = f"{title}. {extra}" if len(extra) > 20 else title
    else:
        sep = "。" if title.endswith(("。", "！", "？")) else ". "
        combined = f"{title}{sep}{summary}"
    return combined[:500]


def _ensure_complete_sentence(text: str) -> str:
    """确保翻译结果以完整句子结尾。"""
    if not text:
        return text
    if text[-1] in "。！？.!?":
        return text
    for sep in ["。", "！", "？", ".", "!", "?"]:
        idx = text.rfind(sep)
        if idx > len(text) * 0.4:
            return text[:idx + 1]
    return text


# ── 主入口 ────────────────────────────────────────────────────────────

def translate_item_fields(item_dict: dict) -> dict:
    """
    生成 title_zh 和 summary_zh。

    优先：Claude AI（规范中文重塑 + 深度摘要）
    回退：Google Translate（字面翻译）
    """
    title = (item_dict.get("title") or "").strip()
    summary = (item_dict.get("summary") or "").strip()
    url = (item_dict.get("source_url") or item_dict.get("url") or "").strip()

    # ── 路径一：LLM AI ────────────────────────────────────────────────
    # 正文抓取已禁用：每条额外 HTTP 请求会在 CI 环境中累计大量超时
    # LLM 基于标题+RSS摘要推导已可满足质量要求
    if _HAS_AI:
        result = _ai_process(title, summary)
        if result:
            item_dict["title_zh"] = result["title_zh"]
            item_dict["summary_zh"] = result["summary_zh"]
            time.sleep(0.1)   # 控制 API 速率
            return item_dict
        logger.warning(f"AI 处理未返回有效结果，回退到 Google Translate: {title[:50]}")

    # ── 路径二：Google Translate 回退 ─────────────────────────────────
    if title and not _is_mostly_chinese(title):
        item_dict["title_zh"] = translate_to_zh(title[:200])
        time.sleep(0.15)
    else:
        item_dict["title_zh"] = title

    source_text = _build_source_text(item_dict)
    if _is_mostly_chinese(source_text):
        item_dict["summary_zh"] = source_text
    else:
        raw = translate_to_zh(source_text)
        item_dict["summary_zh"] = _ensure_complete_sentence(raw)
        time.sleep(0.2)

    return item_dict
