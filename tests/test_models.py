"""
models.py 单元测试
覆盖：Database upsert、query、stats、archive（使用内存 SQLite）
"""
import pytest
import os
import sqlite3
import tempfile

from models import Database, LegislationItem


@pytest.fixture
def db(tmp_path):
    """创建临时数据库"""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    yield database
    database.close()


def _make_item(**overrides) -> LegislationItem:
    """创建测试用 LegislationItem"""
    defaults = {
        "region": "北美",
        "category_l1": "数据隐私",
        "category_l2": "GDPR合规",
        "title": "Test Article",
        "date": "2026-03-20",
        "status": "已生效",
        "summary": "Test summary",
        "source_name": "FTC News",
        "source_url": "https://example.com/test",
        "lang": "en",
        "title_zh": "测试文章",
        "summary_zh": "测试摘要",
        "impact_score": 7.5,
    }
    defaults.update(overrides)
    return LegislationItem(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# LegislationItem
# ═══════════════════════════════════════════════════════════════════════

class TestLegislationItem:

    def test_to_dict(self):
        item = _make_item()
        d = item.to_dict()
        assert d["region"] == "北美"
        assert d["impact_score"] == 7.5
        assert "id" in d

    def test_default_values(self):
        item = LegislationItem(
            region="欧洲", category_l1="玩法合规", category_l2="",
            title="Test", date="2026-01-01", status="草案/征求意见",
            summary="", source_name="", source_url=""
        )
        assert item.lang == "en"
        assert item.title_zh == ""
        assert item.impact_score == 1.0
        assert item.id is None
        assert item.jurisdiction == ""
        assert item.applicability_scope == "unknown"
        assert item.push_decision == "pool_only"
        assert item.value_score == 0


# ═══════════════════════════════════════════════════════════════════════
# Database - Upsert
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseUpsert:

    def test_insert_new_item(self, db):
        item = _make_item()
        result = db.upsert_item(item)
        assert result is True

    def test_duplicate_title_url_updates_translation(self, db):
        """UNIQUE(title, source_url) 冲突时应更新翻译字段"""
        item1 = _make_item(title_zh="", summary_zh="")
        db.upsert_item(item1)

        item2 = _make_item(title_zh="新中文标题", summary_zh="新中文摘要")
        db.upsert_item(item2)

        rows = db.query_items(days=0)
        assert len(rows) == 1
        assert rows[0]["title_zh"] == "新中文标题"

    def test_upsert_preserves_existing_translation(self, db):
        """当新记录翻译为空时，应保留已有翻译"""
        item1 = _make_item(title_zh="已有翻译", summary_zh="已有摘要")
        db.upsert_item(item1)

        item2 = _make_item(title_zh="", summary_zh="")
        db.upsert_item(item2)

        rows = db.query_items(days=0)
        assert rows[0]["title_zh"] == "已有翻译"

    def test_bulk_upsert(self, db):
        items = [_make_item(title=f"Article {i}", source_url=f"https://test.com/{i}")
                 for i in range(5)]
        count = db.bulk_upsert(items)
        assert count == 5

    def test_geography_fields_round_trip(self, db):
        db.upsert_item(_make_item(
            jurisdiction="美国", applicability_scope="single",
            jurisdiction_source="rule",
        ))
        row = db.query_items(days=0)[0]
        assert row["jurisdiction"] == "美国"
        assert row["applicability_scope"] == "single"
        assert row["jurisdiction_source"] == "rule"

    def test_push_assessment_fields_round_trip(self, db):
        db.upsert_item(_make_item(
            push_decision="push", value_score=3,
            noise_reason="高价值监管动态", decision_source="llm",
        ))
        row = db.query_items(days=0)[0]
        assert row["push_decision"] == "push"
        assert row["value_score"] == 3
        assert row["noise_reason"] == "高价值监管动态"
        assert row["decision_source"] == "llm"

    def test_event_key_round_trip(self, db):
        db.upsert_item(_make_item(
            title="FTC settles COPPA case against Roblox",
            summary="The settlement requires child privacy changes.",
        ))
        row = db.query_items(days=0)[0]
        assert row["event_key"].startswith("strong:")

    def test_pp_tunas_multi_source_cluster_collapses(self, db):
        items = [
            _make_item(
                title="Komdigi issues PP TUNAS duties for game platforms",
                title_zh="印尼发布 PP TUNAS 平台义务",
                summary="PP TUNAS requires online game platforms to protect children.",
                jurisdiction="印度尼西亚",
                category_l1="未成年人保护",
                source_name="Komdigi",
                source_url="https://example.com/pp-1",
                date="2026-07-20",
            ),
            _make_item(
                title="Aturan PP Nomor 17 Tahun 2025 bagi platform gim",
                title_zh="印尼明确 PP TUNAS 儿童保护要求",
                summary="PP TUNAS mewajibkan platform gim melindungi anak.",
                jurisdiction="印度尼西亚",
                category_l1="未成年人保护",
                source_name="Local News",
                source_url="https://example.com/pp-2",
                date="2026-07-20",
            ),
        ]

        accepted, dropped = db.filter_new_events(items)

        assert len(accepted) == 1
        assert len(dropped) == 1

    def test_same_translated_title_from_different_sources_collapses(self, db):
        items = [
            _make_item(
                title="France fines a mobile game publisher",
                title_zh="法国处罚手游发行商",
                jurisdiction="法国",
                source_url="https://example.com/fr-1",
                date="2026-07-20",
            ),
            _make_item(
                title="La France sanctionne un éditeur de jeu mobile",
                title_zh="法国处罚手游发行商",
                jurisdiction="法国",
                source_url="https://example.com/fr-2",
                date="2026-07-20",
            ),
        ]

        accepted, dropped = db.filter_new_events(items)

        assert len(accepted) == 1
        assert len(dropped) == 1

    def test_cross_day_same_stage_record_is_dropped(self, db):
        db.upsert_item(_make_item(
            title="Indonesia issues PP TUNAS obligations",
            jurisdiction="印度尼西亚",
            category_l1="未成年人保护",
            status="已生效",
            date="2026-07-01",
            source_url="https://example.com/old-pp",
        ))
        incoming = _make_item(
            title="Commentary on PP TUNAS obligations",
            jurisdiction="印度尼西亚",
            category_l1="未成年人保护",
            status="已生效",
            date="2026-07-20",
            source_url="https://example.com/new-pp",
        )

        accepted, dropped = db.filter_new_events([incoming])

        assert accepted == []
        assert len(dropped) == 1

    def test_explicit_later_legal_stage_is_retained(self, db):
        db.upsert_item(_make_item(
            title="California proposes AB 1921 Protect Our Games Act",
            summary="The bill was proposed for committee review.",
            jurisdiction="美国",
            category_l1="消费者保护",
            status="已提案",
            date="2026-07-01",
            source_url="https://example.com/ab-old",
        ))
        incoming = _make_item(
            title="California enacted AB 1921 Protect Our Games Act",
            summary="California enacted AB 1921 and the new requirements take effect next month.",
            jurisdiction="美国",
            category_l1="消费者保护",
            status="已生效",
            date="2026-07-20",
            source_url="https://example.com/ab-new",
        )

        accepted, dropped = db.filter_new_events([incoming])

        assert accepted == [incoming]
        assert dropped == []

    def test_enforcement_after_effective_law_is_retained(self, db):
        db.upsert_item(_make_item(
            title="Indonesia PP TUNAS takes effect for game platforms",
            summary="PP TUNAS is effective for online game services.",
            jurisdiction="印度尼西亚",
            category_l1="未成年人保护",
            status="已生效",
            date="2026-07-01",
            source_url="https://example.com/pp-effective",
        ))
        incoming = _make_item(
            title="Indonesia enforces PP TUNAS against a game platform",
            summary="Komdigi issued a sanction and fine under PP TUNAS.",
            jurisdiction="印度尼西亚",
            category_l1="未成年人保护",
            status="执法动态",
            date="2026-07-20",
            source_url="https://example.com/pp-enforcement",
        )

        accepted, dropped = db.filter_new_events([incoming])

        assert accepted == [incoming]
        assert dropped == []

    def test_repeal_after_effective_law_is_retained(self, db):
        db.upsert_item(_make_item(
            title="California AB 1921 takes effect",
            jurisdiction="美国",
            category_l1="消费者保护",
            status="已生效",
            date="2026-07-01",
            source_url="https://example.com/ab-effective",
        ))
        incoming = _make_item(
            title="California repeals AB 1921 Protect Our Games Act",
            summary="The legislature repealed AB 1921 and revoked its requirements.",
            jurisdiction="美国",
            category_l1="消费者保护",
            status="已废止",
            date="2026-07-20",
            source_url="https://example.com/ab-repealed",
        )

        accepted, dropped = db.filter_new_events([incoming])

        assert accepted == [incoming]
        assert dropped == []

    def test_different_company_lawsuits_are_not_merged(self, db):
        items = [
            _make_item(
                title="Nintendo sued over child safety controls",
                title_zh="美国游戏公司未成年人诉讼",
                jurisdiction="美国",
                category_l1="未成年人保护",
                status="执法动态",
                source_url="https://example.com/nintendo-case",
                date="2026-07-20",
            ),
            _make_item(
                title="Roblox sued over child safety controls",
                title_zh="美国游戏公司未成年人诉讼",
                jurisdiction="美国",
                category_l1="未成年人保护",
                status="执法动态",
                source_url="https://example.com/roblox-case",
                date="2026-07-20",
            ),
        ]

        accepted, dropped = db.filter_new_events(items)

        assert len(accepted) == 2
        assert dropped == []

    def test_same_company_distinct_lawsuits_need_title_similarity(self, db):
        items = [
            _make_item(
                title="Nintendo sued over missing child spending controls",
                title_zh="",
                jurisdiction="美国",
                category_l1="未成年人保护",
                status="执法动态",
                source_url="https://example.com/nintendo-spending",
                date="2026-07-20",
            ),
            _make_item(
                title="Families file child safety lawsuit after Nintendo chat abuse",
                title_zh="",
                jurisdiction="美国",
                category_l1="未成年人保护",
                status="执法动态",
                source_url="https://example.com/nintendo-chat",
                date="2026-07-20",
            ),
        ]

        accepted, dropped = db.filter_new_events(items)

        assert len(accepted) == 2
        assert dropped == []

    def test_old_database_schema_migrates_event_key(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE legislation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                category_l1 TEXT NOT NULL,
                category_l2 TEXT DEFAULT '',
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT '立法动态',
                summary TEXT DEFAULT '',
                source_name TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                lang TEXT DEFAULT 'en',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(title, source_url)
            )
        """)
        conn.commit()
        conn.close()

        migrated = Database(str(db_path))
        columns = {
            row[1] for row in migrated.conn.execute("PRAGMA table_info(legislation)")
        }
        migrated.close()

        assert "event_key" in columns

    def test_global_reclassification_clears_old_jurisdiction(self, db):
        db.upsert_item(_make_item(
            jurisdiction="美国", applicability_scope="single",
            jurisdiction_source="rule",
        ))
        db.upsert_item(_make_item(
            jurisdiction="", applicability_scope="global",
            jurisdiction_source="llm",
        ))
        row = db.query_items(days=0)[0]
        assert row["jurisdiction"] == ""
        assert row["applicability_scope"] == "global"

    def test_high_confidence_backfill_rejects_prefix_region_conflict(self, db):
        db.upsert_item(_make_item(
            region="欧洲", title="Vague gaming update",
            title_zh="[美国] 游戏监管动态",
        ))
        assert db.backfill_geography() == 0
        assert db.query_items(days=0)[0]["jurisdiction"] == ""

    def test_high_confidence_backfill_accepts_consistent_regulator(self, db):
        db.upsert_item(_make_item(
            region="欧洲", title="CNIL fines game publisher under GDPR",
            title_zh="法国数据保护执法",
        ))
        assert db.backfill_geography() == 1
        row = db.query_items(days=0)[0]
        assert row["jurisdiction"] == "法国"
        assert row["jurisdiction_source"] == "backfill"


# ═══════════════════════════════════════════════════════════════════════
# Database - Query
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseQuery:

    def test_query_all(self, db):
        db.upsert_item(_make_item())
        rows = db.query_items(days=0)
        assert len(rows) == 1

    def test_query_by_region(self, db):
        db.upsert_item(_make_item(region="北美", title="US News", source_url="https://us.com"))
        db.upsert_item(_make_item(region="欧洲", title="EU News", source_url="https://eu.com"))

        us_rows = db.query_items(region="北美", days=0)
        assert len(us_rows) == 1
        assert us_rows[0]["region"] == "北美"

    def test_query_by_category(self, db):
        db.upsert_item(_make_item(category_l1="数据隐私", title="Privacy", source_url="https://1.com"))
        db.upsert_item(_make_item(category_l1="玩法合规", title="Gacha", source_url="https://2.com"))

        rows = db.query_items(category_l1="玩法合规", days=0)
        assert len(rows) == 1

    def test_query_by_keyword(self, db):
        db.upsert_item(_make_item(title="FTC COPPA enforcement", source_url="https://1.com"))
        db.upsert_item(_make_item(title="GDPR fine", source_url="https://2.com"))

        rows = db.query_items(keyword="COPPA", days=0)
        assert len(rows) == 1

    def test_query_ordered_by_impact(self, db):
        db.upsert_item(_make_item(impact_score=3.0, title="Low", source_url="https://1.com"))
        db.upsert_item(_make_item(impact_score=9.0, title="High", source_url="https://2.com"))
        db.upsert_item(_make_item(impact_score=6.0, title="Mid", source_url="https://3.com"))

        rows = db.query_items(days=0)
        scores = [r["impact_score"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_query_limit(self, db):
        for i in range(10):
            db.upsert_item(_make_item(title=f"Item {i}", source_url=f"https://test.com/{i}"))
        rows = db.query_items(days=0, limit=3)
        assert len(rows) == 3

    def test_query_by_explicit_date_range(self, db):
        db.upsert_item(_make_item(date="2026-05-10", title="Old", source_url="https://old.com"))
        db.upsert_item(_make_item(date="2026-05-11", title="Start", source_url="https://start.com"))
        db.upsert_item(_make_item(date="2026-05-17", title="End", source_url="https://end.com"))
        db.upsert_item(_make_item(date="2026-05-18", title="New", source_url="https://new.com"))

        rows = db.query_items(days=90, date_start="2026-05-11", date_end="2026-05-17")
        titles = {r["title"] for r in rows}
        assert titles == {"Start", "End"}


# ═══════════════════════════════════════════════════════════════════════
# Database - Stats
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseStats:

    def test_stats(self, db):
        db.upsert_item(_make_item(region="北美", title="US1", source_url="https://1.com"))
        db.upsert_item(_make_item(region="欧洲", title="EU1", source_url="https://2.com"))
        db.upsert_item(_make_item(region="北美", title="US2", source_url="https://3.com"))

        stats = db.get_stats()
        assert stats["total"] == 3
        assert stats["by_region"]["北美"] == 2
        assert stats["by_region"]["欧洲"] == 1


# ═══════════════════════════════════════════════════════════════════════
# Database - Translation Management
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseTranslation:

    def test_update_translation(self, db):
        item = _make_item(title_zh="", summary_zh="")
        db.upsert_item(item)
        rows = db.query_items(days=0)
        item_id = rows[0]["id"]

        db.update_translation(item_id, "新标题", "新摘要")
        rows = db.query_items(days=0)
        assert rows[0]["title_zh"] == "新标题"
        assert rows[0]["summary_zh"] == "新摘要"

    def test_query_untranslated(self, db):
        db.upsert_item(_make_item(title="Translated", title_zh="有翻译",
                                  source_url="https://1.com"))
        db.upsert_item(_make_item(title="Untranslated", title_zh="",
                                  source_url="https://2.com"))

        rows = db.query_items_untranslated()
        assert len(rows) == 1
        assert rows[0]["title"] == "Untranslated"

    def test_clear_stale_translations(self, db):
        db.upsert_item(_make_item(title_zh="包含战利品箱的错误翻译",
                                  source_url="https://1.com"))
        db.upsert_item(_make_item(title_zh="正常翻译", title="Normal",
                                  source_url="https://2.com"))

        count = db.clear_stale_translations(["战利品箱"])
        assert count == 1

        rows = db.query_items(days=0)
        for r in rows:
            if r["source_url"] == "https://1.com":
                assert r["title_zh"] == ""


# ═══════════════════════════════════════════════════════════════════════
# Database - Delete & Archive
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseDelete:

    def test_delete_item(self, db):
        db.upsert_item(_make_item())
        rows = db.query_items(days=0)
        db.delete_item(rows[0]["id"])
        assert len(db.query_items(days=0)) == 0

    def test_archive_old_records(self, db):
        # 插入一条"旧"记录（200天前的日期）
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        db.upsert_item(_make_item(date=old_date, title="Old", source_url="https://old.com"))
        db.upsert_item(_make_item(date="2026-03-20", title="New", source_url="https://new.com"))

        archived = db.archive_old_records(keep_days=180)
        assert archived == 1

        remaining = db.query_items(days=0)
        assert len(remaining) == 1
        assert remaining[0]["title"] == "New"


# ═══════════════════════════════════════════════════════════════════════
# Database - Fetch Log
# ═══════════════════════════════════════════════════════════════════════

class TestDatabaseFetchLog:

    def test_log_fetch(self, db):
        db.log_fetch("FTC News", 15, "ok")
        db.log_fetch("GamesIndustry.biz", 0, "error", "timeout")

        rows = db.conn.execute("SELECT * FROM fetch_log ORDER BY id").fetchall()
        assert len(rows) == 2
        assert rows[0]["item_count"] == 15
        assert rows[1]["status"] == "error"
