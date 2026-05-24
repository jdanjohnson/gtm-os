"""Adaptive plays — auto-fork plays based on accumulated learnings.

Implements WS8F:
- Detect when a learning contradicts current play content
- Fork the play with the learned modification
- Add frontmatter: parent, forked_from_learning, segment
- Track play lineage for review
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ..types import Memory
from .store import Store

logger = logging.getLogger(__name__)


def check_and_fork_plays(
    *,
    plays_dir: Path,
    learnings: list[Memory],
    store: Store,
) -> list[str]:
    """Check if any high-confidence learnings should fork a play.

    Returns list of forked play paths.
    """
    forked: list[str] = []

    for learning in learnings:
        if learning.confidence < 0.75:
            continue
        if learning.type not in ("learning", "rule"):
            continue

        # Check if learning references a specific play.
        play_ref = _extract_play_reference(learning.content)
        if not play_ref:
            continue

        # Check if the referenced play exists.
        play_path = plays_dir / play_ref / "PLAY.md"
        if not play_path.exists():
            continue

        play_content = play_path.read_text()

        # Check if learning contradicts or modifies play content.
        segment = _extract_segment(learning.content)
        if not segment:
            continue

        # Create fork.
        fork_name = f"{play_ref}-{_slugify(segment)}"
        fork_dir = plays_dir / fork_name
        if fork_dir.exists():
            continue  # Already forked.

        fork_dir.mkdir(parents=True, exist_ok=True)
        fork_path = fork_dir / "PLAY.md"

        # Build forked play with frontmatter.
        frontmatter = (
            f"---\n"
            f"id: {fork_name}\n"
            f"parent: {play_ref}\n"
            f"forked_from_learning: {learning.id}\n"
            f"segment: {segment}\n"
            f"---\n\n"
        )

        # Append the learning as a modification note.
        modification = (
            f"\n\n## Modification (auto-derived)\n\n"
            f"> {learning.content}\n\n"
            f"This play variant was automatically created based on a high-confidence "
            f"learning (confidence: {learning.confidence:.2f}) from "
            f"experiment {learning.experiment_id or 'unknown'}.\n"
        )

        fork_path.write_text(frontmatter + play_content + modification)
        forked.append(str(fork_path))
        logger.info(
            "forked play %s → %s based on learning %s",
            play_ref, fork_name, learning.id,
        )

    return forked


def _extract_play_reference(content: str) -> str | None:
    """Extract play ID from learning content."""
    patterns = [
        r"play:\s*['\"]?([\w-]+)['\"]?",
        r"(b2b-[\w-]+)",
        r"(local-[\w-]+)",
        r"(kol-crm)\b",
        r"\b(seo)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip("'\"").lower()
    return None


def _extract_segment(content: str) -> str | None:
    """Extract target segment from learning content."""
    patterns = [
        r"for\s+(\w[\w\s]{2,20}?)(?:\s*,|\s*\.|$)",
        r"targeting\s+(\w[\w\s]{2,20}?)(?:\s*,|\s*\.|$)",
        r"(technical|enterprise|startup|smb|mid-market)\s+buyers?",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
    return None


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:30]


def list_play_variants(plays_dir: Path) -> list[dict[str, Any]]:
    """List all plays with their variant lineage."""
    plays: list[dict[str, Any]] = []
    for play_dir in sorted(plays_dir.iterdir()):
        if not play_dir.is_dir():
            continue
        play_md = play_dir / "PLAY.md"
        if not play_md.exists():
            continue

        content = play_md.read_text()
        meta: dict[str, Any] = {"id": play_dir.name, "path": str(play_md)}

        # Parse frontmatter.
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                fm = content[3:end].strip()
                for line in fm.splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        meta[key.strip()] = val.strip()

        plays.append(meta)

    return plays
