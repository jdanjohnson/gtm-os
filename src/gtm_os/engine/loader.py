"""Load all primitives from disk into typed structures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..types import BrandConfig, Primitives, RulesConfig, TriggersConfig


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _read_yaml(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if not text.strip():
        return {}
    try:
        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        return {}


def load_primitives(base_path: str | Path = "primitives") -> Primitives:
    """Walk a primitives directory and return everything as a typed `Primitives`."""
    base = Path(base_path)
    prim = Primitives(base_path=str(base))

    # Brand
    brand_dir = base / "brand"
    prim.brand = BrandConfig(
        body=_read_text(brand_dir / "BRAND.md"),
        tone=_read_yaml(brand_dir / "tone.yaml"),
        examples=[
            f.read_text(encoding="utf-8")
            for f in sorted((brand_dir / "examples").glob("*.md"))
            if f.is_file()
        ]
        if (brand_dir / "examples").exists()
        else [],
    )

    # Agents
    agents_dir = base / "agents"
    if agents_dir.exists():
        prim.agents = {
            f.stem: _read_text(f) for f in sorted(agents_dir.glob("*.md")) if f.is_file()
        }

    # Rules
    rules_dir = base / "rules"
    rules = RulesConfig(global_rules=_read_text(rules_dir / "RULES.md"))
    phase_rules_dir = rules_dir / "phase-rules"
    if phase_rules_dir.exists():
        rules.phase_rules = {
            f.stem: _read_text(f) for f in sorted(phase_rules_dir.glob("*.md")) if f.is_file()
        }
    channel_rules_dir = rules_dir / "channel-rules"
    if channel_rules_dir.exists():
        rules.channel_rules = {
            f.stem: _read_text(f) for f in sorted(channel_rules_dir.glob("*.md")) if f.is_file()
        }
    prim.rules = rules

    # Plays — every subdirectory that contains a PLAY.md is a play
    plays_dir = base / "plays"
    if plays_dir.exists():
        for sub in sorted(plays_dir.iterdir()):
            if sub.is_dir():
                play_file = sub / "PLAY.md"
                if play_file.exists():
                    prim.plays[sub.name] = _read_text(play_file)
            elif sub.is_file() and sub.suffix == ".md":
                prim.plays[sub.stem] = _read_text(sub)

    # Memory (file-based supplementary memory)
    memory_dir = base / "memory"
    if memory_dir.exists():
        for f in sorted(memory_dir.rglob("*.md")):
            if f.is_file():
                prim.memory_files.append(_read_text(f))

    # Triggers
    triggers_dir = base / "triggers"
    prim.triggers = TriggersConfig(
        schedules=_read_yaml(triggers_dir / "schedules.yaml"),
        on_phase_change=_read_yaml(triggers_dir / "on-phase-change.yaml"),
    )

    return prim


def parse_play_frontmatter(play_content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a PLAY.md file (WS3E)."""
    if not play_content.startswith("---"):
        return {}
    end = play_content.find("---", 3)
    if end < 0:
        return {}
    fm_text = play_content[3:end].strip()
    try:
        loaded = yaml.safe_load(fm_text)
        return loaded if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        return {}


def get_play_tools_needed(base_path: str | Path) -> dict[str, list[str]]:
    """Return {play_id: [tool_use_cases]} from play frontmatter (WS3E)."""
    base = Path(base_path)
    plays_dir = base / "plays"
    result: dict[str, list[str]] = {}
    if not plays_dir.exists():
        return result
    for sub in sorted(plays_dir.iterdir()):
        if not sub.is_dir():
            continue
        play_file = sub / "PLAY.md"
        if not play_file.exists():
            continue
        fm = parse_play_frontmatter(_read_text(play_file))
        tools = fm.get("tools_needed", [])
        if tools:
            use_cases = []
            for t in tools:
                if isinstance(t, dict):
                    use_cases.append(str(t.get("use_case", t)))
                else:
                    use_cases.append(str(t))
            result[sub.name] = use_cases
    return result


def primitives_exist(base_path: str | Path) -> bool:
    base = Path(base_path)
    return (base / "agents").exists() or (base / "brand").exists()
