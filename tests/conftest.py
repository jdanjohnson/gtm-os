"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gtm_os.config import (
    BudgetConfig,
    Config,
    LLMConfig,
    SchedulerConfig,
    ServerConfig,
)
from gtm_os.engine.store import Store


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    return Config(
        project_root=tmp_path,
        primitives_dir=tmp_path / "primitives",
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "gtm-os.db",
        server=ServerConfig(),
        scheduler=SchedulerConfig(enabled=False),
        llm=LLMConfig(model="openai/gpt-4o-mini", embedding_model=""),
        budgets=BudgetConfig(),
        composio_api_key=None,
    )


@pytest.fixture()
def store(config: Config) -> Store:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    s = Store(config.db_path)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def primitives_tree(tmp_path: Path) -> Path:
    """Minimal in-memory primitives layout."""
    root = tmp_path / "primitives"
    (root / "brand" / "examples").mkdir(parents=True)
    (root / "agents").mkdir(parents=True)
    (root / "rules" / "phase-rules").mkdir(parents=True)
    (root / "rules" / "channel-rules").mkdir(parents=True)
    (root / "plays" / "demo").mkdir(parents=True)
    (root / "triggers").mkdir(parents=True)
    (root / "memory" / "learnings").mkdir(parents=True)

    (root / "brand" / "BRAND.md").write_text("# Brand\n\nWe sell joy.\n")
    (root / "brand" / "tone.yaml").write_text("voice: [direct, warm]\n")
    (root / "brand" / "examples" / "one.md").write_text("Example one\n")
    (root / "agents" / "orchestrator.md").write_text("# Orchestrator\n\nYou route work.\n")
    (root / "agents" / "researcher.md").write_text("# Researcher\n\nYou design.\n")
    (root / "rules" / "RULES.md").write_text("# Rules\n\nBe honest.\n")
    (root / "rules" / "phase-rules" / "design.md").write_text(
        "# design rules\n\nSearch memory first.\n"
    )
    (root / "rules" / "channel-rules" / "email.md").write_text(
        "# email rules\n\nNo HTML.\n"
    )
    (root / "plays" / "demo" / "PLAY.md").write_text(
        "---\nid: demo\nchannel: email\n---\n# Demo play\n\nSend an email.\n"
    )
    (root / "triggers" / "schedules.yaml").write_text(
        "templates:\n  daily:\n    cron_expr: '0 9 * * *'\n"
    )
    return root
