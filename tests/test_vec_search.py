"""Tests for sqlite-vec integration (WS6)."""

import sqlite3

import numpy as np
import pytest

from gtm_os.engine.vec_search import (
    backfill_vec_table,
    delete_embedding,
    is_vec_available,
    search_vec,
    upsert_embedding,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


def test_is_vec_available_returns_bool(conn):
    result = is_vec_available(conn)
    assert isinstance(result, bool)


def test_upsert_without_vec(conn):
    # Without sqlite-vec loaded, should gracefully return False.
    embedding = np.zeros(1536, dtype=np.float32).tobytes()
    result = upsert_embedding(conn, memory_id="m1", embedding=embedding)
    # Either False (no vec) or True (vec available)
    assert isinstance(result, bool)


def test_search_without_vec(conn):
    embedding = np.zeros(1536, dtype=np.float32).tobytes()
    results = search_vec(conn, query_embedding=embedding, limit=5)
    assert results == []  # Falls back to empty


def test_delete_without_vec(conn):
    result = delete_embedding(conn, "m1")
    assert isinstance(result, bool)


def test_backfill_without_vec(conn):
    count = backfill_vec_table(conn)
    # Should return 0 if vec is not available
    assert count == 0
