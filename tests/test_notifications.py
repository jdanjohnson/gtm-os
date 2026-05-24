"""Tests for WS3C: notification system."""

from __future__ import annotations

import pytest

from gtm_os.engine.notifications import NotificationService
from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def config():
    from gtm_os.config import load_config

    return load_config()


@pytest.fixture
def service(config, store):
    return NotificationService(config=config, store=store)


def test_notify_saves_in_app(service, store):
    sent = service.notify("Test alert", experiment_id="e1", event_type="info")
    assert len(sent) >= 1
    assert sent[0].channel == "in_app"

    msgs = store.list_messages(experiment_id="e1")
    assert any("[NOTIFICATION:INFO]" in m["content"] for m in msgs)


def test_on_approval_needed(service, store):
    exp = store.create_experiment("test")
    sent = service.on_approval_needed(exp.id, "Review cold emails before sending")
    assert any(n.event_type == "approval" for n in sent)


def test_on_failure(service, store):
    exp = store.create_experiment("test")
    sent = service.on_failure(exp.id, "LLM timeout", 3)
    assert any(n.event_type == "failure" for n in sent)
    assert any("3 consecutive" in n.message for n in sent)


def test_on_learning(service, store):
    exp = store.create_experiment("test")
    sent = service.on_learning(exp.id, "Short subject lines work better")
    assert any(n.event_type == "learning" for n in sent)


def test_on_complete(service, store):
    exp = store.create_experiment("test")
    sent = service.on_complete(exp.id, "12% reply rate achieved")
    assert any(n.event_type == "complete" for n in sent)


def test_on_budget_threshold(service, store):
    exp = store.create_experiment("test")
    sent = service.on_budget_threshold(exp.id, 85.0)
    assert any("85%" in n.message for n in sent)


def test_on_rule_created(service):
    sent = service.on_rule_created(None, "derived/short-subjects.md")
    assert any(n.event_type == "learning" for n in sent)


def test_notify_without_composio(service):
    """When Composio isn't configured, only in_app notifications are sent."""
    sent = service.notify("Hello")
    channels = [n.channel for n in sent]
    assert "in_app" in channels
    assert "slack" not in channels
    assert "email" not in channels
