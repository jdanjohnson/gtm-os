"""Load and query the gallery of playbooks, workflows, skills, and tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

GalleryKind = str  # "playbook" | "workflow" | "skill" | "tool"

_KINDS = ("playbooks", "workflows", "skills", "tools")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, FileNotFoundError):
        return {}


class GalleryItem:
    """Single gallery entry (playbook, workflow, skill, or tool)."""

    __slots__ = ("category", "data", "description", "id", "kind", "name", "path", "tags")

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self.kind: str = data.get("kind", "unknown")
        self.id: str = data.get("id", path.stem)
        self.name: str = data.get("name", self.id)
        self.description: str = data.get("description", "")
        self.category: str = data.get("category", "")
        self.tags: list[str] = data.get("tags", [])
        self.data = data
        self.path = path

    def to_summary(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
        }

    def to_full(self) -> dict[str, Any]:
        return self.data


class Gallery:
    """In-memory index of gallery YAML files."""

    def __init__(self, gallery_dir: str | Path = "gallery") -> None:
        self._dir = Path(gallery_dir)
        self._items: dict[str, dict[str, GalleryItem]] = {
            "playbook": {},
            "workflow": {},
            "skill": {},
            "tool": {},
        }
        self._load()

    def _load(self) -> None:
        kind_map = {
            "playbooks": "playbook",
            "workflows": "workflow",
            "skills": "skill",
            "tools": "tool",
        }
        for dir_name, kind in kind_map.items():
            sub = self._dir / dir_name
            if not sub.exists():
                continue
            for f in sorted(sub.glob("*.yaml")):
                data = _load_yaml(f)
                if not data:
                    continue
                item = GalleryItem(data, f)
                self._items[kind][item.id] = item

    def list_all(self, kind: str | None = None, category: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        kinds = [kind] if kind and kind in self._items else list(self._items.keys())
        for k in kinds:
            for item in self._items[k].values():
                if category and item.category != category:
                    continue
                if tag and tag not in item.tags:
                    continue
                results.append(item.to_summary())
        return results

    def get(self, kind: str, item_id: str) -> dict[str, Any] | None:
        item = self._items.get(kind, {}).get(item_id)
        return item.to_full() if item else None

    def search(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        tokens = query_lower.split()
        results: list[tuple[int, dict[str, Any]]] = []
        for kind_items in self._items.values():
            for item in kind_items.values():
                score = 0
                text = f"{item.name} {item.description} {' '.join(item.tags)} {item.category}".lower()
                for token in tokens:
                    if token in text:
                        score += 1
                if score > 0:
                    results.append((score, item.to_summary()))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results]

    @property
    def stats(self) -> dict[str, int]:
        return {kind: len(items) for kind, items in self._items.items()}
