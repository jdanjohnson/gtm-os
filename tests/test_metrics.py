"""Tests for WS3B: structured metrics."""

from __future__ import annotations

import pytest

from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def experiment_id(store):
    exp = store.create_experiment("test-metrics")
    return exp.id


def test_save_metric(store, experiment_id):
    mid = store.save_metric(
        experiment_id=experiment_id,
        metric_name="reply_rate",
        metric_value=0.12,
    )
    assert mid


def test_save_metric_with_variant(store, experiment_id):
    mid = store.save_metric(
        experiment_id=experiment_id,
        metric_name="open_rate",
        metric_value=0.45,
        variant="A",
    )
    assert mid


def test_list_metrics_empty(store, experiment_id):
    metrics = store.list_metrics(experiment_id)
    assert metrics == []


def test_list_metrics_returns_saved(store, experiment_id):
    store.save_metric(experiment_id=experiment_id, metric_name="reply_rate", metric_value=0.12)
    store.save_metric(experiment_id=experiment_id, metric_name="open_rate", metric_value=0.45)
    metrics = store.list_metrics(experiment_id)
    assert len(metrics) == 2


def test_list_metrics_filter_by_name(store, experiment_id):
    store.save_metric(experiment_id=experiment_id, metric_name="reply_rate", metric_value=0.12)
    store.save_metric(experiment_id=experiment_id, metric_name="open_rate", metric_value=0.45)
    metrics = store.list_metrics(experiment_id, metric_name="reply_rate")
    assert len(metrics) == 1
    assert metrics[0]["metric_name"] == "reply_rate"


def test_list_metrics_filter_by_variant(store, experiment_id):
    store.save_metric(experiment_id=experiment_id, metric_name="ctr", metric_value=0.03, variant="A")
    store.save_metric(experiment_id=experiment_id, metric_name="ctr", metric_value=0.05, variant="B")
    metrics = store.list_metrics(experiment_id, variant="A")
    assert len(metrics) == 1
    assert metrics[0]["variant"] == "A"


def test_metric_summary(store, experiment_id):
    store.save_metric(experiment_id=experiment_id, metric_name="reply_rate", metric_value=0.1)
    store.save_metric(experiment_id=experiment_id, metric_name="reply_rate", metric_value=0.2)
    store.save_metric(experiment_id=experiment_id, metric_name="reply_rate", metric_value=0.3)
    summary = store.get_metric_summary(experiment_id)
    assert summary["experiment_id"] == experiment_id
    assert len(summary["metrics"]) >= 1
    m = summary["metrics"][0]
    assert m["metric_name"] == "reply_rate"
    assert m["count"] == 3
    assert abs(m["avg_value"] - 0.2) < 0.001


def test_metric_summary_with_variants(store, experiment_id):
    store.save_metric(experiment_id=experiment_id, metric_name="ctr", metric_value=0.03, variant="A")
    store.save_metric(experiment_id=experiment_id, metric_name="ctr", metric_value=0.05, variant="B")
    summary = store.get_metric_summary(experiment_id)
    assert len(summary["metrics"]) == 2


def test_metric_summary_empty(store, experiment_id):
    summary = store.get_metric_summary(experiment_id)
    assert summary["metrics"] == []
