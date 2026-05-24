"""Agent persona evolution — track per-agent metrics, evolve personas.

Implements WS8G:
- Track per-agent performance metrics
- After N runs, analyze patterns and propose persona modifications
- Store persona modifications as versioned diffs
- Allow rollback to previous versions
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .store import Store

logger = logging.getLogger(__name__)

# How many runs before we analyze and potentially modify a persona.
ANALYSIS_INTERVAL = 10


@dataclass
class AgentMetrics:
    agent_name: str
    total_runs: int = 0
    avg_tokens_per_run: float = 0.0
    quality_scores: list[float] = field(default_factory=list)
    human_edit_count: int = 0
    doom_loop_count: int = 0
    success_rate: float = 0.0


@dataclass
class PersonaVersion:
    version: int
    agent_name: str
    content: str
    modification: str
    confidence: float
    created_at: str = ""


def get_agent_metrics(store: Store, agent_name: str) -> AgentMetrics:
    """Compute performance metrics for a specific agent."""
    metrics = AgentMetrics(agent_name=agent_name)

    # Gather runs where this agent was active.
    all_exps = store.list_experiments(limit=500)
    agent_runs = []
    for exp in all_exps:
        runs = store.list_runs(exp.id, limit=100)
        for run in runs:
            ctx = run.input_context or {}
            if ctx.get("agent") == agent_name:
                agent_runs.append(run)

    metrics.total_runs = len(agent_runs)
    if not agent_runs:
        return metrics

    total_tokens = sum(r.tokens_used for r in agent_runs)
    metrics.avg_tokens_per_run = total_tokens / len(agent_runs) if agent_runs else 0

    successes = sum(1 for r in agent_runs if r.status == "completed")
    metrics.success_rate = successes / len(agent_runs) if agent_runs else 0

    doom_loops = sum(1 for r in agent_runs if r.error == "doom_loop")
    metrics.doom_loop_count = doom_loops

    return metrics


def list_persona_versions(agents_dir: Path, agent_name: str) -> list[PersonaVersion]:
    """List all versions of an agent persona."""
    versions_dir = agents_dir / f".{agent_name}-versions"
    if not versions_dir.exists():
        return []

    versions: list[PersonaVersion] = []
    for vf in sorted(versions_dir.glob("v*.md")):
        try:
            ver_num = int(vf.stem[1:])
        except ValueError:
            continue
        meta_file = vf.with_suffix(".json")
        meta: dict[str, Any] = {}
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
        versions.append(PersonaVersion(
            version=ver_num,
            agent_name=agent_name,
            content=vf.read_text(),
            modification=meta.get("modification", ""),
            confidence=float(meta.get("confidence", 0)),
            created_at=meta.get("created_at", ""),
        ))
    return versions


def save_persona_version(
    agents_dir: Path,
    agent_name: str,
    *,
    modification: str,
    confidence: float = 0.8,
) -> PersonaVersion | None:
    """Save current persona as a version, then apply modification."""
    persona_file = agents_dir / f"{agent_name}.md"
    if not persona_file.exists():
        return None

    current_content = persona_file.read_text()

    # Create versions directory.
    versions_dir = agents_dir / f".{agent_name}-versions"
    versions_dir.mkdir(exist_ok=True)

    # Determine next version number.
    existing = list_persona_versions(agents_dir, agent_name)
    next_ver = max((v.version for v in existing), default=0) + 1

    # Save current as version.
    ver_file = versions_dir / f"v{next_ver}.md"
    ver_file.write_text(current_content)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    meta_file = versions_dir / f"v{next_ver}.json"
    meta_file.write_text(json.dumps({
        "modification": modification,
        "confidence": confidence,
        "created_at": now,
    }))

    # Apply modification by appending to persona.
    modified = current_content.rstrip() + f"\n\n## Auto-derived (v{next_ver + 1})\n\n{modification}\n"
    persona_file.write_text(modified)

    logger.info("persona %s evolved to v%d: %s", agent_name, next_ver + 1, modification[:80])

    return PersonaVersion(
        version=next_ver,
        agent_name=agent_name,
        content=current_content,
        modification=modification,
        confidence=confidence,
        created_at=now,
    )


def rollback_persona(agents_dir: Path, agent_name: str, target_version: int) -> bool:
    """Rollback persona to a specific version."""
    versions = list_persona_versions(agents_dir, agent_name)
    target = next((v for v in versions if v.version == target_version), None)
    if not target:
        return False

    persona_file = agents_dir / f"{agent_name}.md"
    persona_file.write_text(target.content)
    logger.info("persona %s rolled back to v%d", agent_name, target_version)
    return True
