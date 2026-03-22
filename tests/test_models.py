"""
models.py 单元测试
覆盖：Database upsert、query、stats、archive（使用内存 SQLite）
"""
import pytest
import os
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
