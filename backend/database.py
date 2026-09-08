"""
SQLite database layer for the Fact Knowledge Layer.
Handles schema creation, CRUD operations, and queries.
"""

import sqlite3
import json
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from backend.config import DB_PATH
from backend.models import Document, Fact, Relationship, ExtractionFailure


def _dict_factory(cursor, row):
    """Convert sqlite3 rows to dictionaries."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create database tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                title TEXT DEFAULT '',
                upload_date TEXT NOT NULL,
                page_count INTEGER DEFAULT 0,
                extraction_mode TEXT DEFAULT 'rule_based',
                fact_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                fact_type TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                predicate TEXT DEFAULT '',
                value TEXT DEFAULT '',
                numeric_value REAL,
                unit TEXT DEFAULT '',
                time_period TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                source_page INTEGER DEFAULT 0,
                source_text TEXT DEFAULT '',
                context TEXT DEFAULT '',
                normalized_subject TEXT DEFAULT '',
                normalized_predicate TEXT DEFAULT '',
                normalized_period TEXT DEFAULT '',
                normalized_value REAL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                relationship_type TEXT NOT NULL,
                fact_ids TEXT DEFAULT '[]',
                reasoning TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                category TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extraction_failures (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                failure_type TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source_page INTEGER DEFAULT 0,
                source_text TEXT DEFAULT '',
                attempted_fact TEXT DEFAULT '{}',
                improvement TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_facts_document ON facts(document_id);
            CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(normalized_subject);
            CREATE INDEX IF NOT EXISTS idx_facts_predicate ON facts(normalized_predicate);
            CREATE INDEX IF NOT EXISTS idx_facts_period ON facts(normalized_period);
            CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(fact_type);
            CREATE INDEX IF NOT EXISTS idx_failures_document ON extraction_failures(document_id);
        """)


# ── Document CRUD ──────────────────────────────────────────────────────────────

def insert_document(doc: Document) -> Document:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO documents (id, filename, title, upload_date, page_count,
               extraction_mode, fact_count, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc.id, doc.filename, doc.title, doc.upload_date, doc.page_count,
             doc.extraction_mode, doc.fact_count, doc.metadata)
        )
    return doc


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return row


def get_all_documents() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY upload_date DESC").fetchall()
    return rows


def update_document_fact_count(doc_id: str, count: int):
    with get_db() as conn:
        conn.execute("UPDATE documents SET fact_count = ? WHERE id = ?", (count, doc_id))


def delete_document(doc_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ── Fact CRUD ──────────────────────────────────────────────────────────────────

def insert_facts(facts: List[Fact]) -> int:
    if not facts:
        return 0
    with get_db() as conn:
        conn.executemany(
            """INSERT INTO facts (id, document_id, fact_type, subject, predicate,
               value, numeric_value, unit, time_period, confidence, source_page,
               source_text, context, normalized_subject, normalized_predicate,
               normalized_period, normalized_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(f.id, f.document_id, f.fact_type, f.subject, f.predicate,
              f.value, f.numeric_value, f.unit, f.time_period, f.confidence,
              f.source_page, f.source_text, f.context, f.normalized_subject,
              f.normalized_predicate, f.normalized_period, f.normalized_value)
             for f in facts]
        )
    return len(facts)


def _enrich_fact(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    d = dict(row)
    if "confidence_factors" not in d or not d["confidence_factors"]:
        from backend.confidence import compute_fact_confidence_factors
        res = compute_fact_confidence_factors(d)
        d["confidence_factors"] = res["confidence_factors"]
    return d


def get_facts_by_document(doc_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE document_id = ? ORDER BY source_page, confidence DESC",
            (doc_id,)
        ).fetchall()
    return [_enrich_fact(r) for r in rows]


def get_all_facts(
    fact_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    subject: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM facts WHERE 1=1"
    params = []
    if fact_type:
        query += " AND fact_type = ?"
        params.append(fact_type)
    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)
    if subject:
        query += " AND (subject LIKE ? OR normalized_subject LIKE ?)"
        params.extend(["%" + subject + "%", "%" + subject.lower() + "%"])
    query += " ORDER BY confidence DESC, source_page"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_enrich_fact(r) for r in rows]


def get_fact_by_id(fact_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
    return _enrich_fact(row)


def get_facts_by_ids(fact_ids: List[str]) -> List[Dict[str, Any]]:
    if not fact_ids:
        return []
    placeholders = ",".join("?" for _ in fact_ids)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE id IN ({})".format(placeholders),
            fact_ids
        ).fetchall()
    return [_enrich_fact(r) for r in rows]


# ── Relationship CRUD ──────────────────────────────────────────────────────────

def insert_relationships(rels: List[Relationship]) -> int:
    if not rels:
        return 0
    with get_db() as conn:
        conn.executemany(
            """INSERT INTO relationships (id, relationship_type, fact_ids,
               reasoning, confidence, category, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(r.id, r.relationship_type, r.fact_ids, r.reasoning,
              r.confidence, r.category, r.created_at)
             for r in rels]
        )
    return len(rels)


def get_all_relationships() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM relationships ORDER BY confidence DESC"
        ).fetchall()
    # Parse fact_ids from JSON
    for row in rows:
        row["fact_ids"] = json.loads(row["fact_ids"])
    return rows


def get_relationship_by_id(rel_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM relationships WHERE id = ?", (rel_id,)).fetchone()
    if row:
        row["fact_ids"] = json.loads(row["fact_ids"])
    return row


def clear_relationships():
    """Remove all relationships (before re-analysis)."""
    with get_db() as conn:
        conn.execute("DELETE FROM relationships")


# ── Extraction Failures ────────────────────────────────────────────────────────

def insert_failure(failure: ExtractionFailure):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO extraction_failures (id, document_id, failure_type,
               description, source_page, source_text, attempted_fact,
               improvement, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (failure.id, failure.document_id, failure.failure_type,
             failure.description, failure.source_page, failure.source_text,
             failure.attempted_fact, failure.improvement, failure.created_at)
        )


def get_all_failures() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM extraction_failures ORDER BY created_at DESC"
        ).fetchall()
    for row in rows:
        row["attempted_fact"] = json.loads(row.get("attempted_fact", "{}"))
    return rows


# ── Statistics ─────────────────────────────────────────────────────────────────

def get_stats() -> Dict[str, Any]:
    with get_db() as conn:
        doc_count = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]
        fact_count = conn.execute("SELECT COUNT(*) as c FROM facts").fetchone()["c"]
        rel_count = conn.execute("SELECT COUNT(*) as c FROM relationships").fetchone()["c"]
        fail_count = conn.execute("SELECT COUNT(*) as c FROM extraction_failures").fetchone()["c"]

        type_breakdown = conn.execute(
            "SELECT relationship_type, COUNT(*) as c FROM relationships GROUP BY relationship_type"
        ).fetchall()

        fact_types = conn.execute(
            "SELECT fact_type, COUNT(*) as c FROM facts GROUP BY fact_type"
        ).fetchall()

    return {
        "documents": doc_count,
        "facts": fact_count,
        "relationships": rel_count,
        "failures": fail_count,
        "relationship_breakdown": {r["relationship_type"]: r["c"] for r in type_breakdown},
        "fact_type_breakdown": {r["fact_type"]: r["c"] for r in fact_types},
    }
