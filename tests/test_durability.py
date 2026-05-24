"""Tests for durability.py — checkpoint/replay."""

import asyncio

import pytest

from gtm_os.engine.durability import DurableContext, _make_serializable
from gtm_os.engine.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


@pytest.fixture
def experiment_id(store):
    exp = store.create_experiment(name="test-exp", play_ids=[], config={}, token_budget=100000)
    return exp.id


def test_durable_context_new_run(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    ctx = DurableContext(store, experiment_id, run.id)
    assert ctx.completed_steps == set()


def test_step_sync_executes_and_checkpoints(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    ctx = DurableContext(store, experiment_id, run.id)

    result = ctx.step_sync("load_data", lambda: {"key": "value"})
    assert result == {"key": "value"}
    assert "load_data" in ctx.completed_steps

    # Second call should return cached result.
    result2 = ctx.step_sync("load_data", lambda: {"different": "data"})
    assert result2 == {"key": "value"}


def test_step_async_executes_and_checkpoints(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    ctx = DurableContext(store, experiment_id, run.id)

    async def async_fn():
        return 42

    result = asyncio.run(ctx.step("compute", async_fn))
    assert result == 42
    assert "compute" in ctx.completed_steps


def test_checkpoint_survives_reload(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    ctx = DurableContext(store, experiment_id, run.id)
    ctx.step_sync("step1", lambda: "hello")
    ctx.step_sync("step2", lambda: [1, 2, 3])

    # Simulate restart: create new context with same run_id.
    ctx2 = DurableContext(store, experiment_id, run.id)
    assert "step1" in ctx2.completed_steps
    assert "step2" in ctx2.completed_steps
    assert ctx2.get_result("step1") == "hello"
    assert ctx2.get_result("step2") == [1, 2, 3]


def test_make_serializable():
    assert _make_serializable(None) is None
    assert _make_serializable(42) == 42
    assert _make_serializable("hello") == "hello"
    assert _make_serializable([1, "two", 3.0]) == [1, "two", 3.0]
    assert _make_serializable({"a": 1}) == {"a": 1}


def test_make_serializable_nested():
    data = {"outer": {"inner": [1, 2, {"deep": True}]}}
    result = _make_serializable(data)
    assert result == {"outer": {"inner": [1, 2, {"deep": True}]}}


def test_multiple_steps_order(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    ctx = DurableContext(store, experiment_id, run.id)

    ctx.step_sync("a", lambda: "first")
    ctx.step_sync("b", lambda: "second")
    ctx.step_sync("c", lambda: "third")

    assert ctx.completed_steps == {"a", "b", "c"}
    assert ctx.get_result("a") == "first"
    assert ctx.get_result("b") == "second"
    assert ctx.get_result("c") == "third"
