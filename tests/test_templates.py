"""Tests for WS3D: experiment templates."""

from __future__ import annotations

import pytest

from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_save_template(store):
    tid = store.save_template(name="Cold outreach v1", description="Basic cold email")
    assert tid


def test_save_template_with_config(store):
    tid = store.save_template(
        name="LinkedIn drip",
        play_ids=["kol-crm"],
        config={"channel": "linkedin"},
        hypothesis_pattern="LinkedIn outreach yields 5% reply rate",
        token_budget=100_000,
    )
    assert tid


def test_get_template(store):
    tid = store.save_template(name="test template")
    tmpl = store.get_template(tid)
    assert tmpl is not None
    assert tmpl["name"] == "test template"


def test_get_template_not_found(store):
    assert store.get_template("nonexistent") is None


def test_list_templates_empty(store):
    assert store.list_templates() == []


def test_list_templates(store):
    store.save_template(name="T1")
    store.save_template(name="T2")
    templates = store.list_templates()
    assert len(templates) == 2


def test_template_preserves_play_ids(store):
    tid = store.save_template(name="T", play_ids=["b2b-saas-email", "kol-crm"])
    tmpl = store.get_template(tid)
    import json

    play_ids = json.loads(tmpl["play_ids"]) if isinstance(tmpl["play_ids"], str) else tmpl["play_ids"]
    assert play_ids == ["b2b-saas-email", "kol-crm"]


def test_save_template_from_experiment(store):
    exp = store.create_experiment(
        "Source experiment",
        hypothesis="Test hypothesis",
        play_ids=["kol-crm"],
        config={"channel": "email"},
    )
    tid = store.save_template(
        name="From experiment",
        play_ids=exp.play_ids,
        config=exp.config,
        hypothesis_pattern=exp.hypothesis,
        created_from=exp.id,
    )
    tmpl = store.get_template(tid)
    assert tmpl["created_from"] == exp.id
