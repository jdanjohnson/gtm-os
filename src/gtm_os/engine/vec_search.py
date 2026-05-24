"""sqlite-vec integration for scalable vector search (Workstream 6).

Currently: numpy cosine similarity over all rows. Fine for <1000 memories.
This module adds sqlite-vec virtual table support for efficient kNN search.
Falls back to numpy approach if sqlite-vec is not available.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

_VEC_AVAILABLE: bool | None = None


def is_vec_available(conn: sqlite3.Connection) -> bool:
    """Check if sqlite-vec extension is loadable."""
    global _VEC_AVAILABLE
    if _VEC_AVAILABLE is not None:
        return _VEC_AVAILABLE
    try:
        import sqlite_vec

        sqlite_vec.load(conn)
        _VEC_AVAILABLE = True
    except Exception:
        _VEC_AVAILABLE = False
    return _VEC_AVAILABLE


def init_vec_table(conn: sqlite3.Connection, *, dimensions: int = 1536) -> bool:
    """Create the virtual table for vector search. Returns True if successful."""
    if not is_vec_available(conn):
        return False
    try:
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec
            USING vec0(
                memory_id TEXT PRIMARY KEY,
                embedding float[{dimensions}]
            )
            """
        )
        return True
    except Exception as exc:
        logger.warning("failed to create memory_vec table: %s", exc)
        return False


def upsert_embedding(
    conn: sqlite3.Connection,
    *,
    memory_id: str,
    embedding: bytes,
) -> bool:
    """Insert or update an embedding in the vec table."""
    if not is_vec_available(conn):
        return False
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO memory_vec(memory_id, embedding)
            VALUES (?, ?)
            """,
            (memory_id, embedding),
        )
        return True
    except Exception as exc:
        logger.debug("vec upsert failed: %s", exc)
        return False


def search_vec(
    conn: sqlite3.Connection,
    *,
    query_embedding: bytes,
    limit: int = 10,
    min_confidence: float = 0.0,
) -> list[tuple[str, float]]:
    """Search for similar vectors. Returns list of (memory_id, distance).

    Lower distance = more similar (L2 distance). Convert to similarity if needed.
    Falls back to empty list if sqlite-vec is not available.
    """
    if not is_vec_available(conn):
        return []
    try:
        rows = conn.execute(
            """
            SELECT memory_id, distance
            FROM memory_vec
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_embedding, limit),
        ).fetchall()
        return [(row[0], float(row[1])) for row in rows]
    except Exception as exc:
        logger.debug("vec search failed: %s", exc)
        return []


def delete_embedding(conn: sqlite3.Connection, memory_id: str) -> bool:
    """Remove an embedding from the vec table."""
    if not is_vec_available(conn):
        return False
    try:
        conn.execute("DELETE FROM memory_vec WHERE memory_id = ?", (memory_id,))
        return True
    except Exception:
        return False


def backfill_vec_table(
    conn: sqlite3.Connection,
    *,
    batch_size: int = 100,
) -> int:
    """Backfill the vec table from existing memory embeddings. Returns count."""
    if not is_vec_available(conn):
        return 0

    count = 0
    offset = 0
    while True:
        rows = conn.execute(
            """
            SELECT id, embedding FROM memory
            WHERE embedding IS NOT NULL
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        ).fetchall()
        if not rows:
            break
        for row in rows:
            if row[1]:
                upsert_embedding(conn, memory_id=row[0], embedding=row[1])
                count += 1
        offset += batch_size
    return count
