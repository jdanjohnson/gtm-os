"""Tests for WS3A: multi-agent orchestrator."""

from __future__ import annotations

import pytest

from gtm_os.engine.orchestrator import PHASE_AGENTS, HandoffState, Orchestrator


@pytest.fixture
def store():
    from gtm_os.engine.store import Store

    return Store(":memory:")


@pytest.fixture
def memory(store):
    from gtm_os.config import LLMConfig
    from gtm_os.engine.memory import VectorMemory

    return VectorMemory(store, LLMConfig(model="openai/gpt-4o", api_key="test"))


@pytest.fixture
def config():
    from gtm_os.config import load_config

    return load_config()


@pytest.fixture
def orchestrator(config, store, memory):
    return Orchestrator(config=config, store=store, memory=memory)


def test_phase_agents_coverage():
    """All experiment phases have agent assignments."""
    expected_phases = {"design", "build", "execute", "measure", "learn", "complete", "paused"}
    assert expected_phases == set(PHASE_AGENTS.keys())


def test_phase_agents_are_lists():
    for phase, agents in PHASE_AGENTS.items():
        assert isinstance(agents, list), f"Phase {phase} agents should be a list"
        assert len(agents) > 0, f"Phase {phase} should have at least one agent"


def test_handoff_state_defaults():
    hs = HandoffState(phase="build")
    assert hs.phase == "build"
    assert hs.agents_run == []
    assert hs.agent_outputs == {}
    assert hs.total_tokens == 0
    assert hs.last_error is None


def test_orchestrator_init(orchestrator):
    assert orchestrator.config is not None
    assert orchestrator.store is not None
    assert orchestrator.memory is not None


def test_build_phase_has_researcher_and_copywriter():
    assert PHASE_AGENTS["build"] == ["researcher", "copywriter"]


def test_execute_phase_uses_operator():
    assert PHASE_AGENTS["execute"] == ["operator"]


def test_measure_phase_uses_analyst():
    assert PHASE_AGENTS["measure"] == ["analyst"]
