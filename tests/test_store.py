from datetime import UTC, datetime, timedelta

from gtm_os.engine.store import Store, _new_id
from gtm_os.types import Schedule


def test_experiment_crud(store: Store):
    exp = store.create_experiment(
        name="alpha",
        hypothesis="testing",
        play_ids=["demo"],
        config={"channel": "email"},
        token_budget=10_000,
    )
    assert exp.id
    assert exp.phase == "design"
    assert exp.play_ids == ["demo"]
    assert exp.config == {"channel": "email"}

    fetched = store.get_experiment(exp.id)
    assert fetched is not None
    assert fetched.name == "alpha"

    listed = store.list_experiments()
    assert len(listed) == 1

    updated = store.update_experiment(exp.id, phase="build", play_ids=["other"])
    assert updated is not None
    assert updated.phase == "build"
    assert updated.play_ids == ["other"]


def test_runs_and_tokens(store: Store):
    exp = store.create_experiment(name="run-exp")
    run = store.start_run(exp.id, "design", {"agent": "researcher"})
    assert run.status == "running"
    store.finish_run(run.id, status="completed", output={"message": "done"}, tokens_used=123)
    store.add_experiment_tokens(exp.id, 123)
    reloaded = store.get_experiment(exp.id)
    assert reloaded.tokens_used == 123
    runs = store.list_runs(exp.id)
    assert len(runs) == 1
    assert runs[0].status == "completed"


def test_memory_insert_and_list(store: Store):
    m = store.insert_memory(
        type="fact",
        content="hello",
        source="test",
        experiment_id=None,
        confidence=0.42,
        embedding=None,
    )
    assert m.confidence == 0.42

    listed = store.list_memories()
    assert any(x.id == m.id for x in listed)


def test_schedule_insert_due(store: Store):
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat(timespec="seconds")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    sched_past = Schedule(
        id=_new_id(),
        experiment_id=None,
        type="tick",
        cron_expr=None,
        interval_seconds=60,
        next_run_at=past,
    )
    sched_future = Schedule(
        id=_new_id(),
        experiment_id=None,
        type="tick",
        cron_expr=None,
        interval_seconds=60,
        next_run_at=future,
    )
    store.insert_schedule(sched_past)
    store.insert_schedule(sched_future)
    due = store.due_schedules()
    assert any(s.id == sched_past.id for s in due)
    assert not any(s.id == sched_future.id for s in due)


def test_checkpoints(store: Store):
    exp = store.create_experiment(name="cp")
    run = store.start_run(exp.id, "design", {})
    store.save_checkpoint(exp.id, run.id, "step-a", {"hello": 1})
    store.save_checkpoint(exp.id, run.id, "step-a", {"hello": 2})  # upsert
    assert store.get_checkpoint(run.id, "step-a") == {"hello": 2}
    assert store.get_checkpoint(run.id, "missing") is None
