"""Extended tests for store.py — checkpoints, messages, schedules."""

import pytest

from gtm_os.engine.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


@pytest.fixture
def experiment_id(store):
    exp = store.create_experiment(name="test", play_ids=[], config={}, token_budget=100000)
    return exp.id


# --- Checkpoint tests ---


def test_save_and_get_checkpoint(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    store.save_checkpoint(experiment_id, run.id, "step1", {"result": "done"})
    cp = store.get_checkpoint(run.id, "step1")
    assert cp is not None


def test_get_checkpoint_missing(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    cp = store.get_checkpoint(run.id, "nonexistent")
    assert cp is None


# --- Message tests ---


def test_add_and_list_messages(store, experiment_id):
    store.add_message(role="user", content="hello", experiment_id=experiment_id)
    store.add_message(role="assistant", content="world", experiment_id=experiment_id)
    msgs = store.list_messages(experiment_id=experiment_id, limit=10)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_list_messages_limit(store, experiment_id):
    for i in range(10):
        store.add_message(role="user", content=f"msg {i}", experiment_id=experiment_id)
    msgs = store.list_messages(experiment_id=experiment_id, limit=5)
    assert len(msgs) == 5


# --- Experiment tests ---


def test_create_experiment(store):
    exp = store.create_experiment(
        name="My Exp", play_ids=["play1"], config={"channel": "email"}, token_budget=50000
    )
    assert exp.name == "My Exp"
    assert exp.play_ids == ["play1"]
    assert exp.token_budget == 50000
    assert exp.phase == "design"


def test_list_experiments(store):
    store.create_experiment(name="A", play_ids=[], config={}, token_budget=1000)
    store.create_experiment(name="B", play_ids=[], config={}, token_budget=1000)
    exps = store.list_experiments(limit=10)
    assert len(exps) >= 2


def test_update_experiment(store):
    exp = store.create_experiment(name="Test", play_ids=[], config={}, token_budget=1000)
    updated = store.update_experiment(exp.id, phase="build")
    assert updated is not None
    assert updated.phase == "build"


def test_add_experiment_tokens(store):
    exp = store.create_experiment(name="Test", play_ids=[], config={}, token_budget=1000)
    store.add_experiment_tokens(exp.id, 150)
    updated = store.get_experiment(exp.id)
    assert updated is not None
    assert updated.tokens_used == 150
    store.add_experiment_tokens(exp.id, 50)
    updated = store.get_experiment(exp.id)
    assert updated.tokens_used == 200


# --- Run tests ---


def test_start_and_finish_run(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={"key": "val"})
    assert run.status == "running"
    store.finish_run(run.id, status="completed", output={"message": "done"})
    finished = store.get_run(run.id)
    assert finished is not None
    assert finished.status == "completed"


def test_list_runs(store, experiment_id):
    store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    store.start_run(experiment_id=experiment_id, phase="build", input_context={})
    runs = store.list_runs(experiment_id, limit=10)
    assert len(runs) == 2


def test_find_orphan_runs(store, experiment_id):
    run = store.start_run(experiment_id=experiment_id, phase="design", input_context={})
    # Manually set started_at to 2 hours ago.
    from datetime import UTC, datetime, timedelta

    old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat(timespec="seconds")
    with store._lock, store._conn:
        store._conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (old_time, run.id))
    orphans = store.find_orphan_runs(older_than_minutes=90)
    assert len(orphans) >= 1


# --- Schedule tests ---


def test_create_schedule(store, experiment_id):
    from datetime import UTC, datetime, timedelta

    from gtm_os.types import Schedule

    next_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    sched_obj = Schedule(
        id="sched-test-1",
        experiment_id=experiment_id,
        type="interval",
        cron_expr=None,
        interval_seconds=3600,
        next_run_at=next_run,
        enabled=True,
        max_cost=10.0,
    )
    sched = store.insert_schedule(sched_obj)
    assert sched.experiment_id == experiment_id
    assert sched.type == "interval"
    assert sched.enabled is True


def test_due_schedules(store, experiment_id):
    from datetime import UTC, datetime, timedelta

    from gtm_os.types import Schedule

    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat(timespec="seconds")
    sched_obj = Schedule(
        id="sched-due-1",
        experiment_id=experiment_id,
        type="interval",
        cron_expr=None,
        interval_seconds=60,
        next_run_at=past,
        enabled=True,
    )
    store.insert_schedule(sched_obj)
    due = store.due_schedules()
    assert len(due) >= 1


def test_update_schedule(store, experiment_id):
    from datetime import UTC, datetime, timedelta

    from gtm_os.types import Schedule

    next_run = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    sched_obj = Schedule(
        id="sched-upd-1",
        experiment_id=experiment_id,
        type="interval",
        cron_expr=None,
        interval_seconds=60,
        next_run_at=next_run,
        enabled=True,
    )
    sched = store.insert_schedule(sched_obj)
    updated = store.update_schedule(sched.id, enabled=False, consecutive_failures=3)
    assert updated is not None
    assert updated.enabled is False
    assert updated.consecutive_failures == 3


# --- Memory tests ---


def test_insert_and_get_memory(store):
    m = store.insert_memory(
        type="fact",
        content="test fact",
        source="test",
        experiment_id=None,
        confidence=0.7,
        embedding=None,
    )
    assert m.content == "test fact"
    fetched = store.get_memory(m.id)
    assert fetched is not None
    assert fetched.confidence == 0.7


def test_all_memory_rows(store):
    store.insert_memory(
        type="fact", content="f1", source=None, experiment_id=None, confidence=0.5, embedding=None
    )
    store.insert_memory(
        type="learning",
        content="l1",
        source=None,
        experiment_id=None,
        confidence=0.5,
        embedding=None,
    )
    all_rows = list(store.all_memory_rows())
    assert len(all_rows) == 2
    fact_rows = list(store.all_memory_rows(type_filter="fact"))
    assert len(fact_rows) == 1


def test_update_memory_confidence(store):
    m = store.insert_memory(
        type="fact", content="test", source=None, experiment_id=None, confidence=0.5, embedding=None
    )
    store.update_memory_confidence(m.id, confidence=0.9, reinforced_by=["exp1", "exp2"])
    updated = store.get_memory(m.id)
    assert updated is not None
    assert updated.confidence == 0.9
    assert updated.reinforced_by == ["exp1", "exp2"]
