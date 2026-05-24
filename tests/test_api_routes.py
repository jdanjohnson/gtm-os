"""Tests for new API routes: metrics, templates, trust, simulation, feedback."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gtm_os.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def experiment_id(client):
    resp = client.post("/api/experiments", json={"name": "test-exp", "hypothesis": "Test"})
    return resp.json()["experiment"]["id"]


# ---------- Metrics routes ----------

def test_save_metric_route(client, experiment_id):
    resp = client.post(
        f"/api/experiments/{experiment_id}/metrics",
        json={"metric_name": "reply_rate", "metric_value": 0.12},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"]


def test_list_metrics_route(client, experiment_id):
    client.post(
        f"/api/experiments/{experiment_id}/metrics",
        json={"metric_name": "reply_rate", "metric_value": 0.12},
    )
    resp = client.get(f"/api/experiments/{experiment_id}/metrics")
    assert resp.status_code == 200
    assert len(resp.json()["metrics"]) == 1


def test_metric_summary_route(client, experiment_id):
    client.post(
        f"/api/experiments/{experiment_id}/metrics",
        json={"metric_name": "ctr", "metric_value": 0.03},
    )
    resp = client.get(f"/api/experiments/{experiment_id}/metrics/summary")
    assert resp.status_code == 200
    assert "metrics" in resp.json()


# ---------- Templates routes ----------

def test_save_template_route(client):
    resp = client.post("/api/templates", json={"name": "Cold outreach v1"})
    assert resp.status_code == 200
    assert resp.json()["ok"]


def test_list_templates_route(client):
    client.post("/api/templates", json={"name": "T1"})
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    assert len(resp.json()["templates"]) >= 1


def test_get_template_route(client):
    r = client.post("/api/templates", json={"name": "T1"})
    tid = r.json()["template_id"]
    resp = client.get(f"/api/templates/{tid}")
    assert resp.status_code == 200
    assert resp.json()["template"]["name"] == "T1"


def test_get_template_not_found(client):
    resp = client.get("/api/templates/nonexistent")
    assert resp.status_code == 404


def test_create_from_template_route(client):
    r = client.post("/api/templates", json={"name": "T1", "play_ids": ["kol-crm"]})
    tid = r.json()["template_id"]
    resp = client.post(f"/api/templates/{tid}/create-experiment", json={"name": "From template"})
    assert resp.status_code == 200
    assert resp.json()["ok"]
    assert resp.json()["experiment_id"]


# ---------- Trust scores routes ----------

def test_list_trust_scores_route(client):
    resp = client.get("/api/trust-scores")
    assert resp.status_code == 200
    assert "trust_scores" in resp.json()


def test_get_trust_score_route(client):
    resp = client.get("/api/trust-scores/email")
    assert resp.status_code == 200
    assert resp.json()["trust_score"]["score"] == 0.0


# ---------- Proposed experiments routes ----------

def test_list_proposed_route(client):
    resp = client.get("/api/proposed-experiments")
    assert resp.status_code == 200
    assert "proposals" in resp.json()


# ---------- Simulation route ----------

def test_simulate_route(client, experiment_id):
    resp = client.post(f"/api/experiments/{experiment_id}/simulate")
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_simulate_not_found(client):
    resp = client.post("/api/experiments/nonexistent/simulate")
    assert resp.status_code == 404


# ---------- Health check still works ----------

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"]
