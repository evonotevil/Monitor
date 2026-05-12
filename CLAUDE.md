# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Global gaming compliance monitoring system (全球游戏合规动态监控) for Lilith Games. Automatically tracks regulatory dynamics across 50+ markets via RSS feeds and Google News, translates/classifies/risk-scores articles with LLM, and delivers daily Feishu notifications + weekly HTML reports.

All user-facing text (UI, reports, Feishu cards, documentation) is in Chinese. Source data is multilingual (EN/JA/KO/VI/PT/TH).

## Commands

```bash
# Setup
pip install -r requirements.txt
pip install pytest
playwright install chromium  # only needed for PDF generation

# Run tests
python -m pytest tests/ -v --tb=short

# Run single test file
python -m pytest tests/test_classifier.py -v

# CLI usage
python monitor.py run                    # fetch + classify + translate
python monitor.py report --format html   # generate HTML report
python monitor.py report --format md     # generate Markdown report
python monitor.py report --format table  # terminal table output
python monitor.py query -k "loot box"    # search articles
python monitor.py stats                  # database statistics
python monitor.py schedule --interval 24 # scheduled periodic runs

# Import validation
python3 -c "import reporter, fetcher, config; print('OK')"
```

## Architecture

**Data pipeline flow:**
```
RSS Feeds (100+) + Google News → fetcher.py → classifier.py → translator.py → models.py (SQLite)
                                                                                    ↓
                                              daily_check.py → Feishu webhook (日报卡片)
                                              feishu_bitable.py → Feishu Bitable API (多维表格)
                                              reporter.py → HTML/PDF reports (周报)
                                              feishu_notify.py → Feishu webhook (周报卡片)
```

**Entry points:**
- `monitor.py` — CLI orchestrator (argparse-based, subcommands: run/report/query/stats/schedule)
- `daily_check.py` — standalone daily Feishu notification (called by GitHub Actions)
- `reporter.py` — standalone report generator, renders Jinja2 templates with CSS from `templates/`
- `feishu_bitable.py` — sync articles to Feishu multi-dimensional table

**Key modules:**
- `fetcher.py` — RSS parsing + Google News scraping, deduplication stage 0 (per-source cap). Core filter: `is_legislation_relevant()` (see below).
- `classifier.py` — article classification into 11 categories, noise filtering, 4-dimensional risk scoring (LLM + regex fallback), deduplication stages 1-2. Owns `is_china_mainland()` which is imported by `fetcher.py`.
- `translator.py` — LLM translation via Silicon Flow (OpenAI SDK), executive summary generation, duplicate merging
- `models.py` — SQLite ORM with automatic schema migrations
- `utils.py` — region mapping, bigram similarity

**Config system** (`config/`):
- `settings.py` — output paths, DB path, timeouts, concurrency
- `regions.py` — 9 regional display groups, country-to-region mapping
- `categories.py` — 11 L1 compliance categories, 70+ L2 subcategories, status labels
- `feeds.py` — 100+ RSS sources with tier classification (official/legal/industry)
- `sources.py` — source authority ranking for deduplication
- `keywords.py` — search keywords (6 languages), digital industry signal words for noise filtering
- `queries.py` — Google News search queries

**LLM prompts** (`prompts/`): system prompt for classification/translation/risk assessment, daily/weekly summary prompts, duplicate verification/merge prompts.

**Report templates** (`templates/`): separate PC and mobile CSS, interactive JS, font configurations.

## Key Design Decisions

- **LLM provider**: Silicon Flow (硅基流动) via OpenAI-compatible SDK, model Qwen3-8B. Translation, classification, and risk scoring happen in a single LLM call to minimize API cost.
- **Risk scoring**: 4 dimensions (revenue impact, product changes, time urgency, scope) each 0-3, weighted into composite 1.0-10.0 score. Regex fallback when LLM unavailable.
- **Deduplication**: 3 stages — per-source cap, semantic bigram similarity within 2-day window, 30-day event clustering with LLM verification.
- **Source priority**: Official government > Legal intelligence > Industry media (for dedup winner selection).
- **Weekly report 3-section structure**: completed tasks (✅已合规/归档), global dynamics (📰行业动态), follow-up tasks (🏃处理/跟进中). Modifying report generation must preserve all three sections.

### `is_legislation_relevant()` filter chain (fetcher.py)

Four sequential gates; any failed gate drops the article:

1. **China mainland exclusion** (`is_china_mainland()` from `classifier.py`): drops articles mentioning 中华人民共和国, 中国大陆, 网信办, 版号, 游戏出海, etc. **This exclusion is a hard business constraint — do NOT remove or relax it. The system intentionally does not track Chinese mainland regulatory content.**

2. **EXCLUSION_PATTERNS**: drops noise — game reviews, patch notes, hardware, casino/sports betting, AI product news (Gemini/Copilot), developer tools, etc. Key subtlety: `r"\bupdate.*(?:v\d|version|season)\b"` and `r"\bcontent update\b"` filter patch notes, but bare `content` was deliberately removed from this pattern to avoid suppressing legitimate "content moderation" regulatory articles.

3. **REGULATORY_SIGNALS** (must match at least one): ~75 regex patterns covering:
   - EN: regulation/law/enforcement/fine/ban/ruling + recommendation/guidance/executive order/NPRM/notice of proposed rulemaking + compound decision patterns (e.g., "commission decision on X")
   - Agency acronyms: FTC, COPPA, GDPR, CCPA, DSA, DMA, IGAC, GRAC, ESRB, PEGI, CERO, CESA
   - Litigation: lawsuit/class action/settlement/consent order
   - JA: 規制/法律/処分/通知/告示/指導/答申 + 景品表示法/資金決済法
   - KO: 규제/법안/제재 + 지침/공고/고시 + 게임산업진흥법
   - VI/TH/ID regulatory terms
   - Note: bare "decision" alone does NOT match; it requires a co-occurring regulatory context word.

4. **Game/digital industry signal** (must match at least one):
   - **All sources**: `GAME_SIGNALS` (~90 patterns) — game/gaming/gacha/loot box/mobile game/in-app purchase, ESRB/PEGI ratings, platform names, 50+ company names, etc.
   - **Official/legal tier sources only (relaxed path)**: `DIGITAL_INDUSTRY_SIGNALS` from `config/keywords.py` — broader digital industry terms (app/online/digital/platform/streaming + age verification/digital identity/eIDAS/EUDI/child safety/content moderation + CJK equivalents). This allows official regulators (FTC, 消費者庁, etc.) to pass without a strict game mention, while blocking traditional-industry content (food safety, telecom retail, etc.).

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | Silicon Flow API key (required) |
| `FEISHU_CHAT_ID` | 目标群聊的 chat_id（消息推送用） |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | Feishu app credentials (for Bitable) |
| `FEISHU_BITABLE_APP_TOKEN` | Bitable app token |
| `FEISHU_BITABLE_TABLE_ID` | Bitable table ID |

## CI/CD

- `test.yml` — runs pytest on push/PR to main. Covers `tests/test_fetcher.py` (22 cases for `is_legislation_relevant()` including REGULATORY_SIGNALS, DIGITAL_INDUSTRY_SIGNALS, and regression cases), `tests/test_classifier.py`, `tests/test_utils.py`, `tests/test_reporter.py`.
- `daily_check.yml` — daily 8am (UTC+8) fetch + Feishu notification; commits updated `data/monitor.db` back to repo with `[skip ci]` tag.
- `publish_report.yml` — manual trigger for weekly report publication

## Design Context

### Users
- **Primary audience**: Lilith Games compliance team (legal BPs) and department leadership
- **Context**: BPs check on mobile throughout the week; leadership reviews on desktop during meetings. Both equally important.
- **Job to be done**: Quickly scan global gaming regulatory changes, assess risk priority, track follow-up tasks

### Brand Personality
- **Voice**: Warm, approachable, informative — like a well-designed internal newsletter
- **3 words**: Clear, Trustworthy, Efficient

### Aesthetic Direction
- Light theme with dark header, color-coded accents, card-based layout — refine, don't reinvent
- Inter (variable) + JetBrains Mono + PingFang SC/Noto Sans SC CJK fallback
- Light mode only (report is often printed/PDF'd)

### Design Principles
1. **Scan-first hierarchy**: Risk level, region, status visible without reading full text
2. **Mobile-desktop parity**: Equally effective on 375px phone and 1400px desktop
3. **Quiet confidence**: Color signals category, not decoration
4. **Content density over chrome**: Every pixel serves information or navigation
5. **Three-zone integrity**: Archived/news/active structure is the backbone — reinforce visually
