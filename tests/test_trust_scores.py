"""Tests for WS8C: trust scores / progressive autonomy."""

from __future__ import annotations

import pytest

from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_get_trust_score_nonexistent(store):
    assert store.get_trust_score("email") is None


def test_upsert_trust_score_creates(store):
    result = store.upsert_trust_score("email", score_delta=0.1, ran=True, succeeded=True)
    assert result is not None
    assert result["experiment_type"] == "email"
    assert abs(result["score"] - 0.1) < 0.001
    assert result["experiments_run"] == 1
    assert result["experiments_succeeded"] == 1


def test_upsert_trust_score_updates(store):
    store.upsert_trust_score("email", score_delta=0.5, ran=True, succeeded=True)
    result = store.upsert_trust_score("email", score_delta=0.1, ran=True, succeeded=True)
    assert abs(result["score"] - 0.6) < 0.001
    assert result["experiments_run"] == 2
    assert result["experiments_succeeded"] == 2


def test_trust_score_clamped_at_1(store):
    store.upsert_trust_score("email", score_delta=0.9)
    result = store.upsert_trust_score("email", score_delta=0.5)
    assert result["score"] <= 1.0


def test_trust_score_clamped_at_0(store):
    store.upsert_trust_score("email", score_delta=0.1)
    result = store.upsert_trust_score("email", score_delta=-0.5)
    assert result["score"] >= 0.0


def test_trust_score_negative_delta(store):
    store.upsert_trust_score("linkedin", score_delta=0.5, ran=True, succeeded=True)
    result = store.upsert_trust_score("linkedin", score_delta=-0.1, ran=True, succeeded=False)
    assert abs(result["score"] - 0.4) < 0.001
    assert result["experiments_run"] == 2
    assert result["experiments_succeeded"] == 1


def test_list_trust_scores(store):
    store.upsert_trust_score("email", score_delta=0.8)
    store.upsert_trust_score("linkedin", score_delta=0.3)
    scores = store.list_trust_scores()
    assert len(scores) == 2
    # Ordered by score DESC.
    assert scores[0]["experiment_type"] == "email"


def test_list_trust_scores_empty(store):
    assert store.list_trust_scores() == []
