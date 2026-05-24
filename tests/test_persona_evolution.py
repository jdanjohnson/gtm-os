"""Tests for WS8G: agent persona evolution."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gtm_os.engine.persona_evolution import (
    AgentMetrics,
    get_agent_metrics,
    list_persona_versions,
    rollback_persona,
    save_persona_version,
)
from gtm_os.engine.store import Store


@pytest.fixture
def store():
    return Store(":memory:")


def test_agent_metrics_defaults():
    m = AgentMetrics(agent_name="researcher")
    assert m.total_runs == 0
    assert m.avg_tokens_per_run == 0.0
    assert m.success_rate == 0.0


def test_get_agent_metrics_no_runs(store):
    metrics = get_agent_metrics(store, "researcher")
    assert metrics.total_runs == 0


def test_list_persona_versions_no_dir():
    with tempfile.TemporaryDirectory() as td:
        versions = list_persona_versions(Path(td), "researcher")
        assert versions == []


def test_save_and_list_versions():
    with tempfile.TemporaryDirectory() as td:
        agents_dir = Path(td)
        persona_file = agents_dir / "researcher.md"
        persona_file.write_text("# Researcher\nOriginal content")

        v = save_persona_version(
            agents_dir, "researcher",
            modification="Use shorter sentences based on 15 experiments",
            confidence=0.85,
        )
        assert v is not None
        assert v.version == 1
        assert v.agent_name == "researcher"

        # Original should be saved as version.
        versions = list_persona_versions(agents_dir, "researcher")
        assert len(versions) == 1
        assert "Original content" in versions[0].content

        # Persona file should have modification appended.
        updated = persona_file.read_text()
        assert "Auto-derived" in updated
        assert "shorter sentences" in updated


def test_save_multiple_versions():
    with tempfile.TemporaryDirectory() as td:
        agents_dir = Path(td)
        persona_file = agents_dir / "copywriter.md"
        persona_file.write_text("# Copywriter\nV1")

        save_persona_version(agents_dir, "copywriter", modification="Mod 1")
        save_persona_version(agents_dir, "copywriter", modification="Mod 2")

        versions = list_persona_versions(agents_dir, "copywriter")
        assert len(versions) == 2


def test_rollback_persona():
    with tempfile.TemporaryDirectory() as td:
        agents_dir = Path(td)
        persona_file = agents_dir / "analyst.md"
        persona_file.write_text("# Analyst\nOriginal")

        save_persona_version(agents_dir, "analyst", modification="Bad change")

        # Rollback to v1.
        assert rollback_persona(agents_dir, "analyst", 1) is True
        content = persona_file.read_text()
        assert "Original" in content
        assert "Bad change" not in content


def test_rollback_nonexistent():
    with tempfile.TemporaryDirectory() as td:
        assert rollback_persona(Path(td), "nope", 1) is False


def test_save_persona_nonexistent_file():
    with tempfile.TemporaryDirectory() as td:
        result = save_persona_version(Path(td), "nope", modification="test")
        assert result is None
