"""Tests for experiment lifecycle — phase transitions, output chaining, directives."""

import pytest

from gtm_os.config import LLMConfig
from gtm_os.engine.experiment import (
    PHASE_AGENT,
    PHASE_ORDER,
    ExperimentRunner,
    _next_phase,
    _phase_directive,
    _prev_phase,
)
from gtm_os.engine.store import Store
from gtm_os.types import Experiment, Primitives


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


def test_phase_order():
    assert PHASE_ORDER == ["design", "build", "execute", "measure", "learn", "complete"]


def test_phase_agent_mapping():
    assert PHASE_AGENT["design"] == "researcher"
    assert PHASE_AGENT["build"] == "copywriter"
    assert PHASE_AGENT["execute"] == "operator"
    assert PHASE_AGENT["measure"] == "analyst"
    assert PHASE_AGENT["learn"] == "analyst"


def test_next_phase():
    assert _next_phase("design") == "build"
    assert _next_phase("build") == "execute"
    assert _next_phase("execute") == "measure"
    assert _next_phase("measure") == "learn"
    assert _next_phase("learn") == "complete"
    assert _next_phase("complete") is None
    assert _next_phase("unknown") is None


def test_prev_phase():
    assert _prev_phase("design") is None
    assert _prev_phase("build") == "design"
    assert _prev_phase("execute") == "build"
    assert _prev_phase("learn") == "measure"
    assert _prev_phase("unknown") is None


def test_phase_directive_design():
    exp = Experiment(id="e1", name="Test Exp", hypothesis="H1")
    directive = _phase_directive("design", exp)
    assert "design" in directive.lower() or "Design" in directive
    assert "Test Exp" in directive


def test_phase_directive_build():
    exp = Experiment(id="e1", name="Test Exp")
    directive = _phase_directive("build", exp)
    assert "build" in directive.lower() or "Build" in directive
    assert "request_approval" in directive


def test_phase_directive_learn():
    exp = Experiment(id="e1", name="Test Exp")
    directive = _phase_directive("learn", exp)
    assert "learn" in directive.lower()


def test_phase_directive_with_plays():
    exp = Experiment(id="e1", name="Test Exp", play_ids=["cold-email"])
    primitives = Primitives(plays={"cold-email": "Send personalized cold emails to prospects"})
    directive = _phase_directive("design", exp, primitives)
    assert "cold-email" in directive


def test_create_experiment(store):
    import tempfile
    from pathlib import Path

    from gtm_os.config import BudgetConfig, Config
    from gtm_os.engine.composio_tools import ComposioIntegration
    from gtm_os.engine.memory import VectorMemory

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(
            project_root=Path(tmp),
            primitives_dir=Path(tmp) / "primitives",
            data_dir=Path(tmp) / "data",
            db_path=Path(tmp) / "test.db",
            llm=LLMConfig(model="openai/gpt-4o-mini", embedding_model=""),
            budgets=BudgetConfig(default_experiment_token_budget=100_000),
        )
        (Path(tmp) / "primitives").mkdir()
        memory = VectorMemory(store, cfg.llm)
        composio = ComposioIntegration(api_key=None)
        runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
        exp = runner.create(name="My Test", hypothesis="Will it work?")
        assert exp.name == "My Test"
        assert exp.phase == "design"
        assert exp.token_budget == 100_000


def test_transition_phase(store):
    exp = store.create_experiment(name="Test", play_ids=[], config={}, token_budget=100000)
    import tempfile
    from pathlib import Path

    from gtm_os.config import Config
    from gtm_os.engine.composio_tools import ComposioIntegration
    from gtm_os.engine.memory import VectorMemory

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(
            project_root=Path(tmp),
            primitives_dir=Path(tmp) / "primitives",
            data_dir=Path(tmp) / "data",
            db_path=Path(tmp) / "test.db",
            llm=LLMConfig(model="openai/gpt-4o-mini", embedding_model=""),
        )
        (Path(tmp) / "primitives").mkdir()
        memory = VectorMemory(store, cfg.llm)
        composio = ComposioIntegration(api_key=None)
        runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
        updated = runner.transition_phase(exp.id, "build")
        assert updated is not None
        assert updated.phase == "build"


def test_transition_invalid_phase(store):
    exp = store.create_experiment(name="Test", play_ids=[], config={}, token_budget=100000)
    import tempfile
    from pathlib import Path

    from gtm_os.config import Config
    from gtm_os.engine.composio_tools import ComposioIntegration
    from gtm_os.engine.memory import VectorMemory

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(
            project_root=Path(tmp),
            primitives_dir=Path(tmp) / "primitives",
            data_dir=Path(tmp) / "data",
            db_path=Path(tmp) / "test.db",
            llm=LLMConfig(model="openai/gpt-4o-mini", embedding_model=""),
        )
        (Path(tmp) / "primitives").mkdir()
        memory = VectorMemory(store, cfg.llm)
        composio = ComposioIntegration(api_key=None)
        runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
        with pytest.raises(ValueError, match="unknown phase"):
            runner.transition_phase(exp.id, "invalid_phase")


def test_pause_resume(store):
    exp = store.create_experiment(name="Test", play_ids=[], config={}, token_budget=100000)
    import tempfile
    from pathlib import Path

    from gtm_os.config import Config
    from gtm_os.engine.composio_tools import ComposioIntegration
    from gtm_os.engine.memory import VectorMemory

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Config(
            project_root=Path(tmp),
            primitives_dir=Path(tmp) / "primitives",
            data_dir=Path(tmp) / "data",
            db_path=Path(tmp) / "test.db",
            llm=LLMConfig(model="openai/gpt-4o-mini", embedding_model=""),
        )
        (Path(tmp) / "primitives").mkdir()
        memory = VectorMemory(store, cfg.llm)
        composio = ComposioIntegration(api_key=None)
        runner = ExperimentRunner(config=cfg, store=store, memory=memory, composio=composio)
        paused = runner.pause(exp.id, reason="Testing pause")
        assert paused is not None
        assert paused.phase == "paused"

        resumed = runner.resume(exp.id, target_phase="build")
        assert resumed is not None
        assert resumed.phase == "build"
