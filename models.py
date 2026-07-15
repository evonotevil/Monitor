"""
数据模型 & SQLite 数据库管理
"""

import sqlite3
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List

from config import DATABASE_PATH


@dataclass
class LegislationItem:
    """一条立法/监管动态条目"""
    region: str             # 区域 (欧洲/北美/东南亚/...)
    category_l1: str        # 一级分类
    category_l2: str        # 二级分类
    title: str              # 原文标题
    date: str               # 时间 (YYYY-MM-DD)
    status: str             # 状态
    summary: str            # 原文摘要
    source_name: str        # 数据源名称
    source_url: str         # 原文链接
    lang: str = "en"        # 语言
    title_zh: str = ""      # 标题中文翻译
    summary_zh: str = ""    # 摘要中文翻译
    impact_score: float = 1.0  # 影响评分 1.0–10.0 (状态 × 信源层级 × 核心市场 × 高风险内容)
    risk_revenue: int = 0     # 营收影响 0-3
    risk_product: int = 0     # 产品改动 0-3
    risk_urgency: int = 0     # 时间紧迫性 0-3
    risk_scope: int = 0       # 影响范围 0-3
    risk_source: str = "regex"  # 评分来源: "regex" / "llm"
    jurisdiction: str = ""      # 具体国家/地区或欧盟；全球/多国/未知时留空
    applicability_scope: str = "unknown"  # single/supranational/multi/global/unknown
    jurisdiction_source: str = "unknown"  # rule/official_source/llm/locale/backfill/unknown
    push_decision: str = "pool_only"  # push / pool_only
    value_score: int = 0              # 信息价值 0-3
    noise_reason: str = "判定失败"     # 固定枚举，便于人工反馈分析
    decision_source: str = "fallback" # llm / rule / fallback
    id: Optional[int] = None

    def to_dict(self):
        return asdict(self)


class Database:
    """SQLite 数据库操作"""

    def __init__(self, db_path: str = DATABASE_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS legislation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                category_l1 TEXT NOT NULL,
                category_l2 TEXT DEFAULT '',
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT '政策信号',
                summary TEXT DEFAULT '',
                source_name TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                lang TEXT DEFAULT 'en',
                title_zh TEXT DEFAULT '',
                summary_zh TEXT DEFAULT '',
                impact_score REAL DEFAULT 1.0,
                jurisdiction TEXT DEFAULT '',
                applicability_scope TEXT DEFAULT 'unknown',
                jurisdiction_source TEXT DEFAULT 'unknown',
                push_decision TEXT DEFAULT 'pool_only',
                value_score INTEGER DEFAULT 0,
                noise_reason TEXT DEFAULT '判定失败',
                decision_source TEXT DEFAULT 'fallback',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(title, source_url)
            );

            CREATE INDEX IF NOT EXISTS idx_region ON legislation(region);
            CREATE INDEX IF NOT EXISTS idx_category ON legislation(category_l1);
            CREATE INDEX IF NOT EXISTS idx_date ON legislation(date);

            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                fetched_at TEXT DEFAULT (datetime('now')),
                item_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                error_msg TEXT DEFAULT ''
            );
        """)
        # ── 迁移: 旧表补列 ────────────────────────────────────────────
        for col, definition in [
            ("title_zh",     "TEXT DEFAULT ''"),
            ("summary_zh",   "TEXT DEFAULT ''"),
            ("impact_score", "REAL DEFAULT 1.0"),
            ("risk_revenue", "INTEGER DEFAULT 0"),
            ("risk_product", "INTEGER DEFAULT 0"),
            ("risk_urgency", "INTEGER DEFAULT 0"),
            ("risk_scope",   "INTEGER DEFAULT 0"),
            ("risk_source",  "TEXT DEFAULT 'regex'"),
            ("jurisdiction", "TEXT DEFAULT ''"),
            ("applicability_scope", "TEXT DEFAULT 'unknown'"),
            ("jurisdiction_source", "TEXT DEFAULT 'unknown'"),
            ("push_decision", "TEXT DEFAULT 'pool_only'"),
            ("value_score", "INTEGER DEFAULT 0"),
            ("noise_reason", "TEXT DEFAULT '判定失败'"),
            ("decision_source", "TEXT DEFAULT 'fallback'"),
        ]:
            try:
                self.conn.execute(f"SELECT {col} FROM legislation LIMIT 1")
            except sqlite3.OperationalError:
                self.conn.execute(
                    f"ALTER TABLE legislation ADD COLUMN {col} {definition}"
                )
        # idx_impact 依赖 impact_score 列，必须在迁移之后再建
        self.conn.executescript(
            "CREATE INDEX IF NOT EXISTS idx_impact ON legislation(impact_score);"
        )
        self.conn.commit()

    def upsert_item(self, item: LegislationItem) -> bool:
        try:
            self.conn.execute("""
                INSERT INTO legislation
                    (region, category_l1, category_l2, title, date, status, summary,
                     source_name, source_url, lang, title_zh, summary_zh, impact_score,
                     risk_revenue, risk_product, risk_urgency, risk_scope, risk_source,
                     jurisdiction, applicability_scope, jurisdiction_source,
                     push_decision, value_score, noise_reason, decision_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(title, source_url) DO UPDATE SET
                    region     = excluded.region,
                    category_l1 = CASE WHEN excluded.category_l1 != '' THEN excluded.category_l1 ELSE legislation.category_l1 END,
                    status     = CASE WHEN excluded.status     != '' THEN excluded.status     ELSE legislation.status     END,
                    impact_score = CASE WHEN excluded.impact_score > 0 THEN excluded.impact_score ELSE legislation.impact_score END,
                    title_zh   = CASE WHEN excluded.title_zh   != '' THEN excluded.title_zh   ELSE legislation.title_zh   END,
                    summary_zh = CASE WHEN excluded.summary_zh != '' THEN excluded.summary_zh ELSE legislation.summary_zh END,
                    risk_revenue = CASE WHEN excluded.risk_source = 'llm' THEN excluded.risk_revenue ELSE legislation.risk_revenue END,
                    risk_product = CASE WHEN excluded.risk_source = 'llm' THEN excluded.risk_product ELSE legislation.risk_product END,
                    risk_urgency = CASE WHEN excluded.risk_source = 'llm' THEN excluded.risk_urgency ELSE legislation.risk_urgency END,
                    risk_scope   = CASE WHEN excluded.risk_source = 'llm' THEN excluded.risk_scope   ELSE legislation.risk_scope   END,
                    risk_source  = CASE WHEN excluded.risk_source = 'llm' THEN excluded.risk_source  ELSE legislation.risk_source  END,
                    jurisdiction = CASE
                        WHEN excluded.applicability_scope IN ('global', 'multi') AND excluded.jurisdiction = '' THEN ''
                        WHEN excluded.jurisdiction != '' THEN excluded.jurisdiction
                        ELSE legislation.jurisdiction
                    END,
                    applicability_scope = CASE WHEN excluded.applicability_scope != 'unknown' THEN excluded.applicability_scope ELSE legislation.applicability_scope END,
                    jurisdiction_source = CASE WHEN excluded.jurisdiction_source != 'unknown' THEN excluded.jurisdiction_source ELSE legislation.jurisdiction_source END,
                    push_decision = excluded.push_decision,
                    value_score = excluded.value_score,
                    noise_reason = excluded.noise_reason,
                    decision_source = excluded.decision_source
            """, (
                item.region, item.category_l1, item.category_l2,
                item.title, item.date, item.status, item.summary,
                item.source_name, item.source_url, item.lang,
                item.title_zh, item.summary_zh, item.impact_score,
                item.risk_revenue, item.risk_product, item.risk_urgency,
                item.risk_scope, item.risk_source,
                item.jurisdiction, item.applicability_scope,
                item.jurisdiction_source,
                item.push_decision, item.value_score,
                item.noise_reason, item.decision_source,
            ))
            self.conn.commit()
            return self.conn.total_changes > 0
        except sqlite3.Error:
            return False

    def bulk_upsert(self, items: List[LegislationItem]) -> int:
        count = 0
        for item in items:
            if self.upsert_item(item):
                count += 1
        return count

    def log_fetch(self, source_name: str, item_count: int, status: str = "ok", error_msg: str = ""):
        self.conn.execute("""
            INSERT INTO fetch_log (source_name, item_count, status, error_msg)
            VALUES (?, ?, ?, ?)
        """, (source_name, item_count, status, error_msg))
        self.conn.commit()

    def query_items(
        self,
        region: Optional[str] = None,
        category_l1: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        days: int = 90,
        limit: int = 500,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
    ) -> List[dict]:
        conditions = []
        params = []

        if region:
            conditions.append("region = ?")
            params.append(region)
        if category_l1:
            conditions.append("category_l1 = ?")
            params.append(category_l1)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if keyword:
            conditions.append("(title LIKE ? OR summary LIKE ? OR title_zh LIKE ? OR summary_zh LIKE ?)")
            params.extend([f"%{keyword}%"] * 4)
        if date_start and date_end:
            conditions.append("date >= ?")
            params.append(date_start)
            conditions.append("date <= ?")
            params.append(date_end)
        elif days:
            conditions.append("date >= date('now', ?)")
            params.append(f"-{days} days")

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT * FROM legislation
            WHERE {where}
            ORDER BY impact_score DESC, date DESC
            LIMIT ?
        """
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM legislation").fetchone()[0]
        by_region = self.conn.execute(
            "SELECT region, COUNT(*) as cnt FROM legislation GROUP BY region ORDER BY cnt DESC"
        ).fetchall()
        by_category = self.conn.execute(
            "SELECT category_l1, COUNT(*) as cnt FROM legislation GROUP BY category_l1 ORDER BY cnt DESC"
        ).fetchall()
        latest = self.conn.execute(
            "SELECT MAX(date) FROM legislation"
        ).fetchone()[0]
        by_impact = self.conn.execute(
            "SELECT impact_score, COUNT(*) as cnt FROM legislation GROUP BY impact_score ORDER BY impact_score DESC"
        ).fetchall()
        return {
            "total": total,
            "by_region": {r["region"]: r["cnt"] for r in by_region},
            "by_category": {r["category_l1"]: r["cnt"] for r in by_category},
            "by_impact": {r["impact_score"]: r["cnt"] for r in by_impact},
            "latest_date": latest,
        }

    def clear_stale_translations(self, dirty_terms: list) -> int:
        """
        将 title_zh 或 summary_zh 中包含脏词（音译错误、栏目前缀等）的条目
        翻译字段清空，以便下次 run 时重新翻译。返回清空的条目数。
        """
        if not dirty_terms:
            return 0
        conditions = []
        params = []
        for term in dirty_terms:
            conditions.append("title_zh LIKE ? OR summary_zh LIKE ?")
            params.extend([f"%{term}%", f"%{term}%"])
        where = " OR ".join(f"({c})" for c in conditions)
        cur = self.conn.execute(
            f"UPDATE legislation SET title_zh = '', summary_zh = '' WHERE {where}",
            params,
        )
        self.conn.commit()
        return cur.rowcount

    def query_items_untranslated(self, limit: int = 200) -> List[dict]:
        """查询尚未翻译（title_zh 为空）的条目，优先处理高 impact 的。"""
        rows = self.conn.execute("""
            SELECT * FROM legislation
            WHERE title_zh = '' OR title_zh IS NULL
            ORDER BY impact_score DESC, date DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def update_translation(self, item_id: int, title_zh: str, summary_zh: str,
                           region: str = "", category_l1: str = "",
                           status: str = "", impact_score: float = 0.0,
                           risk_revenue: int = 0, risk_product: int = 0,
                           risk_urgency: int = 0, risk_scope: int = 0,
                           risk_source: str = "", jurisdiction: Optional[str] = None,
                           applicability_scope: str = "",
                           jurisdiction_source: str = "",
                           push_decision: str = "", value_score: Optional[int] = None,
                           noise_reason: str = "", decision_source: str = ""):
        """直接按 id 更新翻译字段，可选更新分类/地区/风险评估。"""
        sql = "UPDATE legislation SET title_zh = ?, summary_zh = ?"
        params: list = [title_zh, summary_zh]
        if region:
            sql += ", region = ?"
            params.append(region)
        if category_l1:
            sql += ", category_l1 = ?"
            params.append(category_l1)
        if status:
            sql += ", status = ?"
            params.append(status)
        if impact_score > 0:
            sql += ", impact_score = ?"
            params.append(impact_score)
        if risk_source:
            sql += ", risk_revenue = ?, risk_product = ?, risk_urgency = ?, risk_scope = ?, risk_source = ?"
            params.extend([risk_revenue, risk_product, risk_urgency, risk_scope, risk_source])
        if jurisdiction is not None:
            sql += ", jurisdiction = ?"
            params.append(jurisdiction)
        if applicability_scope:
            sql += ", applicability_scope = ?"
            params.append(applicability_scope)
        if jurisdiction_source:
            sql += ", jurisdiction_source = ?"
            params.append(jurisdiction_source)
        if push_decision:
            sql += ", push_decision = ?"
            params.append(push_decision)
        if value_score is not None:
            sql += ", value_score = ?"
            params.append(value_score)
        if noise_reason:
            sql += ", noise_reason = ?"
            params.append(noise_reason)
        if decision_source:
            sql += ", decision_source = ?"
            params.append(decision_source)
        sql += " WHERE id = ?"
        params.append(item_id)
        self.conn.execute(sql, params)
        self.conn.commit()

    def backfill_geography(self) -> int:
        """只用与现有一级区域一致的强证据回填历史地理字段。"""
        from classifier import _detect_geography
        from utils import _get_region_group, normalize_jurisdiction, region_for_jurisdiction

        rows = self.conn.execute("""
            SELECT id, region, title, title_zh, summary, source_name
            FROM legislation
            WHERE COALESCE(jurisdiction, '') = ''
              AND COALESCE(applicability_scope, 'unknown') = 'unknown'
        """).fetchall()
        updated = 0
        for row in rows:
            current_group = _get_region_group(row["region"] or "其他")
            prefix = re.match(r"^\[([^\]]+)\]", row["title_zh"] or "")
            prefix_jurisdiction = normalize_jurisdiction(prefix.group(1)) if prefix else ""
            if prefix_jurisdiction and region_for_jurisdiction(prefix_jurisdiction) != current_group:
                continue

            text = " ".join(filter(None, [row["title"], row["title_zh"], row["summary"]]))
            jurisdiction, scope, source = _detect_geography(
                text,
                source_name=row["source_name"] or "",
                allow_locale_fallback=False,
            )
            if prefix_jurisdiction:
                jurisdiction = prefix_jurisdiction
                scope = "supranational" if jurisdiction == "欧盟" else "single"
                source = "rule"

            if jurisdiction:
                if region_for_jurisdiction(jurisdiction) != current_group:
                    continue
            elif scope not in {"global", "multi"} or current_group != "其他":
                continue
            if source not in {"rule", "official_source"}:
                continue

            self.conn.execute("""
                UPDATE legislation
                SET jurisdiction = ?, applicability_scope = ?, jurisdiction_source = 'backfill'
                WHERE id = ?
            """, (jurisdiction, scope, row["id"]))
            updated += 1
        self.conn.commit()
        return updated

    def delete_item(self, item_id: int):
        """按 id 删除条目（用于 retranslate 清理 LLM 判定不相关的历史垃圾条目）。"""
        self.conn.execute("DELETE FROM legislation WHERE id = ?", (item_id,))
        self.conn.commit()

    def archive_old_records(self, keep_days: int = 180) -> int:
        """
        将超过 keep_days 天以前的记录移入 legislation_archive 表并从主表删除。
        返回实际归档条数。
        """
        # 建归档表（首次调用时自动创建）
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS legislation_archive (
                id INTEGER,
                region TEXT,
                category_l1 TEXT,
                category_l2 TEXT,
                title TEXT,
                date TEXT,
                status TEXT,
                summary TEXT,
                source_name TEXT,
                source_url TEXT,
                lang TEXT,
                title_zh TEXT,
                summary_zh TEXT,
                impact_score REAL,
                risk_revenue INTEGER DEFAULT 0,
                risk_product INTEGER DEFAULT 0,
                risk_urgency INTEGER DEFAULT 0,
                risk_scope INTEGER DEFAULT 0,
                risk_source TEXT DEFAULT 'regex',
                jurisdiction TEXT DEFAULT '',
                applicability_scope TEXT DEFAULT 'unknown',
                jurisdiction_source TEXT DEFAULT 'unknown',
                created_at TEXT,
                archived_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (id)
            );
        """)
        for col, definition in [
            ("jurisdiction", "TEXT DEFAULT ''"),
            ("applicability_scope", "TEXT DEFAULT 'unknown'"),
            ("jurisdiction_source", "TEXT DEFAULT 'unknown'"),
        ]:
            try:
                self.conn.execute(f"SELECT {col} FROM legislation_archive LIMIT 1")
            except sqlite3.OperationalError:
                self.conn.execute(
                    f"ALTER TABLE legislation_archive ADD COLUMN {col} {definition}"
                )
        self.conn.commit()

        cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d")

        # 复制到归档表（已存在则跳过）
        self.conn.execute("""
            INSERT OR IGNORE INTO legislation_archive
                (id, region, category_l1, category_l2, title, date, status,
                 summary, source_name, source_url, lang, title_zh, summary_zh,
                 impact_score, risk_revenue, risk_product, risk_urgency,
                 risk_scope, risk_source, jurisdiction, applicability_scope,
                 jurisdiction_source, created_at)
            SELECT id, region, category_l1, category_l2, title, date, status,
                   summary, source_name, source_url, lang, title_zh, summary_zh,
                   impact_score,
                   COALESCE(risk_revenue, 0), COALESCE(risk_product, 0),
                   COALESCE(risk_urgency, 0), COALESCE(risk_scope, 0),
                   COALESCE(risk_source, 'regex'),
                   COALESCE(jurisdiction, ''),
                   COALESCE(applicability_scope, 'unknown'),
                   COALESCE(jurisdiction_source, 'unknown'),
                   created_at
            FROM legislation
            WHERE date < ?
        """, (cutoff,))

        archived = self.conn.execute("SELECT changes()").fetchone()[0]

        # 从主表删除
        self.conn.execute("DELETE FROM legislation WHERE date < ?", (cutoff,))
        self.conn.commit()

        # 释放磁盘空间
        self.conn.execute("VACUUM")

        return archived

    def close(self):
        self.conn.close()
