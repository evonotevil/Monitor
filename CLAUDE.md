# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Global gaming compliance monitoring system (全球游戏合规动态监控) for Lilith Games. It tracks all markets outside mainland China via official RSS, Google News, and a best-effort GDELT supplement; translates/classifies/risk-scores articles with an LLM; and delivers daily Feishu notifications plus weekly HTML/PDF reports.

All user-facing text (UI, reports, Feishu cards, documentation) is in Chinese. Daily monitoring supports 12 languages: EN, JA, KO, VI, ID, TH, ZH-TW, PT, ES, DE, FR, and AR.

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
python monitor.py run --period day       # daily mode: natural-day window + compact queries
python monitor.py report --format html   # generate HTML report
python monitor.py report --format md     # generate Markdown report
python monitor.py report --format table  # terminal table output
python monitor.py query -k "loot box"    # search articles
python monitor.py stats                  # database statistics
python monitor.py schedule --interval 24 # scheduled periodic runs
python daily_check.py                    # sync Bitable + send daily Feishu card

# Import validation
python3 -c "import reporter, fetcher, config; print('OK')"
```

## Architecture

**Daily data pipeline:**
```
Official/legal/industry RSS
    + 12-locale Google News (4 lanes per locale)
    + GDELT (3 best-effort composite queries)
        ↓
fetcher.py: exact-title dedup → relevance filter → source-date enrichment → recency recheck
        ↓
classifier.py: jurisdiction/category/status/risk fallback
        ↓
translator.py: LLM relevance + translation + jurisdiction/scope/category/status + 4D risk
        ↓
monitor.py: post-LLM hierarchical geography normalization + cross-language event dedup
        ↓
models.py (SQLite) → daily_check.py → Feishu Bitable + daily card
                   → reporter.py / feishu_notify.py → weekly HTML/PDF + weekly card
```

**Entry points:**
- `monitor.py` — CLI orchestrator (argparse-based, subcommands: run/report/query/stats/schedule)
- `daily_check.py` — standalone daily Feishu notification (called by GitHub Actions)
- `reporter.py` — standalone report generator, renders Jinja2 templates with CSS from `templates/`
- `feishu_bitable.py` — sync articles to Feishu multi-dimensional table

**Key modules:**
- `fetcher.py` — RSS/Google News/GDELT fetching, exact-title dedup, multilingual relevance filtering, source-date enrichment, and language-funnel logging. Core filter: `is_legislation_relevant()` (see below).
- `classifier.py` — regex jurisdiction/applicability/category/status classification, mainland-China exclusion, noise helpers, and 4-dimensional fallback risk scoring. Owns `is_china_mainland()`, imported by `fetcher.py`.
- `translator.py` — LLM relevance, translation, jurisdiction/category/status correction, 4-dimensional risk scoring, summaries, and duplicate verification/merge
- `monitor.py` — CLI orchestration plus source cap, title similarity dedup, 30-day event clustering, and conservative post-LLM event-fingerprint dedup
- `models.py` — SQLite ORM with automatic schema migrations and conservative geography backfill
- `daily_check.py` — daily date/created-at window, Bitable sync, display dedup, normal/empty/failure Feishu cards
- `utils.py` — Level-1 region, concrete jurisdiction and applicability-scope normalization; source tier ordering; bigram similarity

**Config system** (`config/`):
- `settings.py` — output paths, DB path, timeouts, concurrency
- `regions.py` — monitored jurisdictions and reference priorities; display-group normalization is in `utils.py`
- `categories.py` — 11 L1 compliance categories, 70+ L2 subcategories, status labels
- `feeds.py` — validated RSS sources with tier classification (official/legal/industry)
- `sources.py` — source authority ranking for deduplication
- `keywords.py` — full/weekly keywords and broad digital-industry signals
- `queries.py` — official-site queries plus `DAILY_LANGUAGE_PROFILES`; each locale defines four daily query lanes and safe filter terms in one place

**LLM prompts** (`prompts/`): system prompt for classification/translation/risk assessment, daily/weekly summary prompts, duplicate verification/merge prompts.

**Report templates** (`templates/`): separate PC and mobile CSS, interactive JS, font configurations.

## Key Design Decisions

- **LLM provider**: Silicon Flow (硅基流动) via OpenAI-compatible SDK, model Qwen3-8B. Translation, classification, and risk scoring happen in a single LLM call to minimize API cost.
- **Risk scoring**: 4 dimensions (revenue impact, product changes, time urgency, scope) each 0-3, weighted into composite 1.0-10.0 score. Regex fallback when LLM unavailable.
- **Daily multilingual queries**: 12 locales × 4 lanes (regulation/compliance, enforcement/litigation, platform policy, priority companies/products). Keep query terms and safe filter terms together in `DAILY_LANGUAGE_PROFILES`.
- **Jurisdiction is not language**: classify the event's actual jurisdiction from country/state/regulator/law evidence. Google News locale is fallback-only. Never drop an article merely because its language and jurisdiction differ.
- **Hierarchical geography semantics**: `region` remains one of the nine display groups; nullable `jurisdiction` is a country/territory or the EU; `applicability_scope` is `single`, `supranational`, `multi`, `global`, or `unknown`. Global/multi/unknown are never jurisdiction values. Reports group by `region` and display the concrete jurisdiction when available.
- **Geography migration**: SQLite adds the three geography columns automatically. Historical rows are backfilled only from strong evidence consistent with their existing Level-1 region; title-prefix conflicts remain unresolved. Bitable keeps `国家/地区` and optionally accepts `具体国家/地区` plus `适用范围` after live field discovery.
- **Date semantics**: daily `max_days=1` includes today and yesterday as calendar dates. Re-run recency filtering after fetching the source page date; recycled Apple/Android RSS dates must not reach the LLM or DB as current news.
- **Deduplication**: source cap + same-region title similarity + 30-day stage clustering. After LLM correction, event fingerprints may nominate low-similarity cross-language pairs, but only LLM confirmation may merge them. Without LLM confirmation, retain both.
- **Source priority**: Official government > Legal intelligence > Industry media (for dedup winner selection).
- **GDELT is non-critical**: only 3 composite fallback queries. Daily mode stops on the first 429 with no retry; weekly mode retries once with a capped wait. GDELT failure must not fail RSS/Google News.
- **Failure semantics**: a failed fetch must never become a green “no updates” card. GitHub Actions passes `steps.fetch.outcome` as `FETCH_STEP_OUTCOME`; `daily_check.py` sends a red failure card, skips Bitable/normal daily processing, and exits non-zero.
- **Broken feed policy**: remove persistently malformed/HTML feeds rather than adding unsafe parser hacks. EUR-Lex RSS, GDPRHub Atom, JD Supra Consumer Protection, and Brazil ANPD RSS are intentionally removed; coverage comes from working feeds and query lanes.
- **Weekly report 3-section structure**: completed tasks (✅已合规/归档), global dynamics (📰行业动态), follow-up tasks (🏃处理/跟进中). Modifying report generation must preserve all three sections.

### `is_legislation_relevant()` filter chain (fetcher.py)

Five sequential gates; any failed gate drops the article:

1. **China mainland exclusion** (`is_china_mainland()` from `classifier.py`): drops domestic mainland-China regulation such as 中华人民共和国, 中国大陆, 网信办, 版号, and PIPL-only developments. **This is a hard business constraint: do not start tracking mainland domestic regulation. However, overseas regulators' enforcement, litigation, bans, or platform actions against Chinese game companies must be retained because the event jurisdiction is overseas.**

2. **Traditional consumer-goods guard**: rejects food/supplement/cosmetic/pharma enforcement unless a strong game/digital signal is also present.

3. **EXCLUSION_PATTERNS**: drops reviews, patch notes, hardware, gambling, sports, promotions, political “game” metaphors, AI product news, developer tools, etc. Keep exclusions specific enough not to suppress legitimate content-moderation or game-platform regulation.

4. **REGULATORY_SIGNALS** (must match at least one): shared terms from `DAILY_LANGUAGE_PROFILES` plus high-precision regex covering:
   - EN: regulation/law/enforcement/fine/ban/ruling + recommendation/guidance/executive order/NPRM/notice of proposed rulemaking + compound decision patterns (e.g., "commission decision on X")
   - Agency acronyms: FTC, COPPA, GDPR, CCPA, DSA, DMA, IGAC, GRAC, ESRB, PEGI, CERO, CESA
   - Litigation: lawsuit/class action/settlement/consent order
   - JA: 規制/法律/処分/通知/告示/指導/答申 + 景品表示法/資金決済法
   - KO: 규제/법안/제재 + 지침/공고/고시 + 게임산업진흥법
   - VI/ID/TH/ZH-TW/PT/ES/DE/FR/AR regulatory and enforcement terms
   - Note: bare "decision" alone does NOT match; it requires a co-occurring regulatory context word.

5. **Game/digital industry signal** (must match at least one):
   - **All sources**: `GAME_SIGNALS` (~90 patterns) — game/gaming/gacha/loot box/mobile game/in-app purchase, ESRB/PEGI ratings, platform names, 50+ company names, etc.
   - **Official/legal tier sources only (relaxed path)**: `DIGITAL_INDUSTRY_SIGNALS` from `config/keywords.py` — broader digital industry terms (app/online/digital/platform/streaming + age verification/digital identity/eIDAS/EUDI/child safety/content moderation + CJK equivalents). This allows official regulators (FTC, 消費者庁, etc.) to pass without a strict game mention, while blocking traditional-industry content (food safety, telecom retail, etc.).

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY` | Silicon Flow API key (required) |
| `LLM_MODEL` | Optional OpenAI-compatible model override; defaults to `Qwen/Qwen3-8B` |
| `FEISHU_CHAT_ID` | 目标群聊的 chat_id（消息推送用） |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | Feishu app credentials (for Bitable) |
| `FEISHU_BITABLE_APP_TOKEN` | Bitable app token |
| `FEISHU_BITABLE_WIKI_TOKEN` | Wiki-hosted Bitable token alternative |
| `FEISHU_BITABLE_TABLE_ID` | Bitable table ID |

`FETCH_STEP_OUTCOME` is an internal GitHub Actions handoff, not a secret. If unset during local runs, `daily_check.py` assumes the fetch succeeded.

## CI/CD

- `test.yml` — runs the full pytest suite on push/PR to main. Current suite covers fetch failures, calendar-date windows, multilingual filtering, jurisdiction aliases, GDELT limits, Feishu behavior, and cross-language dedup.
- `daily_check.yml` — scheduled around 8am (UTC+8): fetch, red failure alert or normal daily processing, then commit `monitor.db` and push-state files back with `[skip ci]` only after success.
- `publish_report.yml` — manual trigger for weekly report publication

Before finishing behavior changes, run:

```bash
python -m pytest tests/ -q
python3 -m py_compile config/queries.py fetcher.py classifier.py translator.py monitor.py daily_check.py reporter.py
git diff --check
```

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
