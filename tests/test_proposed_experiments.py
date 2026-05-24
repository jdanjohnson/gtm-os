"""Tests for WS8D: proposed experiments queue."""

from __future__ import annotations

import pytest

from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_propose_experiment(store):
    pid = store.propose_experiment(
        name="Follow-up cold email",
        hypothesis="Shorter subject lines increase open rate",
        rationale="Learning from exp-1 showed 60-char subjects underperformed",
    )
    assert pid


def test_propose_with_play_ids(store):
    pid = store.propose_experiment(
        name="LinkedIn test",
        play_ids=["kol-crm"],
        rationale="Try different channel",
        source_experiment_id="exp-1",
    )
    assert pid


def test_list_proposed_empty(store):
    assert store.list_proposed_experiments() == []


def test_list_proposed_returns_saved(store):
    store.propose_experiment(name="P1", rationale="R1")
    store.propose_experiment(name="P2", rationale="R2")
    props = store.list_proposed_experiments()
    assert len(props) == 2


def test_list_proposed_filter_by_status(store):
    pid1 = store.propose_experiment(name="P1", rationale="R1")
    store.propose_experiment(name="P2", rationale="R2")
    store.update_proposed_experiment(pid1, "approved")
    pending = store.list_proposed_experiments(status="pending")
    assert len(pending) == 1
    assert pending[0]["name"] == "P2"


def test_update_proposed_status(store):
    pid = store.propose_experiment(name="P1", rationale="R1")
    store.update_proposed_experiment(pid, "rejected")
    props = store.list_proposed_experiments(status="rejected")
    assert len(props) == 1
    assert props[0]["status"] == "rejected"


def test_proposed_default_status_is_pending(store):
    store.propose_experiment(name="P1", rationale="R1")
    props = store.list_proposed_experiments()
    assert props[0]["status"] == "pending"


def test_proposed_play_ids_serialized(store):
    store.propose_experiment(name="P1", play_ids=["a", "b"], rationale="R1")
    props = store.list_proposed_experiments()
    assert props[0]["play_ids"] == ["a", "b"]
