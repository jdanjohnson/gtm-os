"""Tests for WS8E: simulation / dry-run mode."""

from __future__ import annotations

import pytest

from gtm_os.engine.simulation import SimulationResult, predict_outcomes
from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_predict_outcomes_no_experiment(store):
    result = predict_outcomes(store, "nonexistent")
    assert "not found" in result.message.lower()


def test_predict_outcomes_no_similar(store):
    exp = store.create_experiment("Test exp")
    result = predict_outcomes(store, exp.id)
    assert result.similar_experiments_found == 0
    assert "no comparable" in result.message.lower()


def test_predict_outcomes_with_similar(store):
    # Create a completed experiment with metrics.
    past = store.create_experiment(
        "Past exp", play_ids=["kol-crm"], config={"channel": "email"}
    )
    store.update_experiment(past.id, phase="complete")
    store.save_metric(experiment_id=past.id, metric_name="reply_rate", metric_value=0.12)
    store.save_metric(experiment_id=past.id, metric_name="reply_rate", metric_value=0.15)

    # Create current experiment with same play.
    current = store.create_experiment(
        "Current exp", play_ids=["kol-crm"], config={"channel": "email"}
    )

    result = predict_outcomes(store, current.id)
    assert result.similar_experiments_found >= 1
    assert len(result.predictions) >= 1
    assert result.predictions[0].name == "reply_rate"
    assert result.predictions[0].predicted_value > 0


def test_predict_outcomes_confidence_interval(store):
    past = store.create_experiment("Past", play_ids=["kol-crm"], config={"channel": "email"})
    store.update_experiment(past.id, phase="complete")
    store.save_metric(experiment_id=past.id, metric_name="ctr", metric_value=0.03)
    store.save_metric(experiment_id=past.id, metric_name="ctr", metric_value=0.05)
    store.save_metric(experiment_id=past.id, metric_name="ctr", metric_value=0.04)

    current = store.create_experiment("Curr", play_ids=["kol-crm"], config={"channel": "email"})
    result = predict_outcomes(store, current.id)
    pred = next((p for p in result.predictions if p.name == "ctr"), None)
    assert pred is not None
    assert pred.confidence_interval_low <= pred.predicted_value
    assert pred.predicted_value <= pred.confidence_interval_high


def test_simulation_result_defaults():
    sr = SimulationResult(experiment_id="test")
    assert sr.predictions == []
    assert sr.estimated_token_cost == 0
    assert sr.similar_experiments_found == 0
