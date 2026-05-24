"""TrustCall-style JSON Patch system for reliable structured extraction.

Instead of asking an LLM to generate or modify large JSON objects (which is
unreliable), we ask the LLM to emit incremental JSON Patch (RFC 6902)
operations. This way the LLM only specifies what changed, not the entire
object.

Use cases in GTM-OS:
- Parsing prospect data into typed schemas without data loss
- Updating nested experiment configs without accidentally deleting fields
- Safely patching stored memory / learnings
- Extracting structured campaign metrics from unstructured LLM output

The module provides:
1. JSON Patch operations (add, remove, replace, move, copy, test)
2. Tool schemas that can be given to the LLM so it emits patches as tool calls
3. Helpers to parse LLM tool_use output into patch operations
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class PatchError(Exception):
    """Raised when a JSON Patch operation fails."""


@dataclass
class PatchOp:
    """A single RFC 6902 JSON Patch operation."""

    op: str  # add | remove | replace | move | copy | test
    path: str  # JSON Pointer (e.g. "/icp/industry")
    value: Any = None  # required for add, replace, test
    from_path: str | None = None  # required for move, copy

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"op": self.op, "path": self.path}
        if self.op in ("add", "replace", "test"):
            d["value"] = self.value
        if self.op in ("move", "copy") and self.from_path:
            d["from"] = self.from_path
        return d


@dataclass
class PatchResult:
    """Result of applying a batch of patches."""

    success: bool
    document: dict[str, Any]
    applied: list[PatchOp] = field(default_factory=list)
    failed: list[tuple[PatchOp, str]] = field(default_factory=list)


def _resolve_pointer(doc: dict[str, Any], pointer: str) -> tuple[Any, str]:
    """Resolve a JSON Pointer to (parent_container, final_key).

    Raises PatchError if the path is invalid or an intermediate doesn't exist.
    """
    if not pointer.startswith("/"):
        raise PatchError(f"JSON Pointer must start with /: {pointer}")

    parts = pointer[1:].split("/")
    # Unescape ~1 → / and ~0 → ~ per RFC 6901.
    parts = [p.replace("~1", "/").replace("~0", "~") for p in parts]

    current: Any = doc
    for i, part in enumerate(parts[:-1]):
        if isinstance(current, dict):
            if part not in current:
                raise PatchError(f"Path not found: /{'/'.join(parts[:i + 1])}")
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
            except ValueError as exc:
                raise PatchError(f"Expected array index, got: {part}") from exc
            if idx < 0 or idx >= len(current):
                raise PatchError(f"Array index out of range: {idx}")
            current = current[idx]
        else:
            raise PatchError(f"Cannot traverse into {type(current).__name__} at /{'/'.join(parts[:i + 1])}")

    return current, parts[-1]


def apply_patch(document: dict[str, Any], patch: PatchOp) -> None:
    """Apply a single patch operation (mutates document in place)."""
    if patch.op == "add":
        parent, key = _resolve_pointer(document, patch.path)
        if isinstance(parent, dict):
            parent[key] = patch.value
        elif isinstance(parent, list):
            if key == "-":
                parent.append(patch.value)
            else:
                try:
                    idx = int(key)
                except ValueError as exc:
                    raise PatchError(f"Expected array index or '-', got: {key}") from exc
                parent.insert(idx, patch.value)
        else:
            raise PatchError(f"Cannot add to {type(parent).__name__}")

    elif patch.op == "remove":
        parent, key = _resolve_pointer(document, patch.path)
        if isinstance(parent, dict):
            if key not in parent:
                raise PatchError(f"Key not found for remove: {patch.path}")
            del parent[key]
        elif isinstance(parent, list):
            try:
                idx = int(key)
            except ValueError as exc:
                raise PatchError(f"Expected array index, got: {key}") from exc
            if idx < 0 or idx >= len(parent):
                raise PatchError(f"Array index out of range: {idx}")
            parent.pop(idx)
        else:
            raise PatchError(f"Cannot remove from {type(parent).__name__}")

    elif patch.op == "replace":
        parent, key = _resolve_pointer(document, patch.path)
        if isinstance(parent, dict):
            if key not in parent:
                raise PatchError(f"Key not found for replace: {patch.path}")
            parent[key] = patch.value
        elif isinstance(parent, list):
            try:
                idx = int(key)
            except ValueError as exc:
                raise PatchError(f"Expected array index, got: {key}") from exc
            if idx < 0 or idx >= len(parent):
                raise PatchError(f"Array index out of range: {idx}")
            parent[idx] = patch.value
        else:
            raise PatchError(f"Cannot replace in {type(parent).__name__}")

    elif patch.op == "move":
        if not patch.from_path:
            raise PatchError("move requires 'from' path")
        # Remove from source.
        src_parent, src_key = _resolve_pointer(document, patch.from_path)
        if isinstance(src_parent, dict):
            value = src_parent.pop(src_key)
        elif isinstance(src_parent, list):
            value = src_parent.pop(int(src_key))
        else:
            raise PatchError(f"Cannot move from {type(src_parent).__name__}")
        # Add to destination.
        apply_patch(document, PatchOp(op="add", path=patch.path, value=value))

    elif patch.op == "copy":
        if not patch.from_path:
            raise PatchError("copy requires 'from' path")
        src_parent, src_key = _resolve_pointer(document, patch.from_path)
        if isinstance(src_parent, dict):
            value = copy.deepcopy(src_parent[src_key])
        elif isinstance(src_parent, list):
            value = copy.deepcopy(src_parent[int(src_key)])
        else:
            raise PatchError(f"Cannot copy from {type(src_parent).__name__}")
        apply_patch(document, PatchOp(op="add", path=patch.path, value=value))

    elif patch.op == "test":
        parent, key = _resolve_pointer(document, patch.path)
        if isinstance(parent, dict):
            actual = parent.get(key)
        elif isinstance(parent, list):
            actual = parent[int(key)]
        else:
            raise PatchError(f"Cannot test on {type(parent).__name__}")
        if actual != patch.value:
            raise PatchError(
                f"Test failed at {patch.path}: expected {patch.value!r}, got {actual!r}"
            )
    else:
        raise PatchError(f"Unknown op: {patch.op}")


def apply_patches(
    document: dict[str, Any],
    patches: list[PatchOp],
    *,
    atomic: bool = True,
) -> PatchResult:
    """Apply a list of patches to a document.

    If atomic=True (default), all patches succeed or none do.
    If atomic=False, applies as many as possible and reports failures.
    """
    if atomic:
        doc_copy = copy.deepcopy(document)
        applied: list[PatchOp] = []
        for patch in patches:
            try:
                apply_patch(doc_copy, patch)
                applied.append(patch)
            except PatchError as e:
                return PatchResult(
                    success=False,
                    document=document,
                    applied=applied,
                    failed=[(patch, str(e))],
                )
        return PatchResult(success=True, document=doc_copy, applied=applied)
    else:
        doc_copy = copy.deepcopy(document)
        applied_ops: list[PatchOp] = []
        failed_ops: list[tuple[PatchOp, str]] = []
        for patch in patches:
            try:
                apply_patch(doc_copy, patch)
                applied_ops.append(patch)
            except PatchError as e:
                failed_ops.append((patch, str(e)))
        return PatchResult(
            success=len(failed_ops) == 0,
            document=doc_copy,
            applied=applied_ops,
            failed=failed_ops,
        )


# ---------- LLM tool integration ----------


def build_extraction_tool() -> dict[str, Any]:
    """Return an Anthropic tool_use schema for structured extraction.

    The LLM uses this tool to extract data into a target schema by
    emitting JSON Patch operations against an empty document.
    """
    return {
        "name": "structured_extract",
        "description": (
            "Extract structured data by emitting JSON Patch operations. "
            "Each operation sets a field in the output document. "
            "Use 'add' to set new fields, 'replace' to update existing ones."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patches": {
                    "type": "array",
                    "description": "List of JSON Patch (RFC 6902) operations",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["add", "remove", "replace", "move", "copy", "test"],
                            },
                            "path": {
                                "type": "string",
                                "description": "JSON Pointer path (e.g. /name, /icp/industry)",
                            },
                            "value": {
                                "description": "Value for add/replace/test operations",
                            },
                            "from": {
                                "type": "string",
                                "description": "Source path for move/copy operations",
                            },
                        },
                        "required": ["op", "path"],
                    },
                },
            },
            "required": ["patches"],
        },
    }


def build_update_tool(current_doc: dict[str, Any]) -> dict[str, Any]:
    """Return a tool schema for updating an existing document.

    Includes the current document state in the description so the LLM
    knows what it's patching.
    """
    import json

    doc_preview = json.dumps(current_doc, indent=2, default=str)[:2000]
    return {
        "name": "patch_document",
        "description": (
            f"Update the document by emitting JSON Patch operations. "
            f"Current state:\n```json\n{doc_preview}\n```\n"
            "Use 'replace' to change existing fields, 'add' for new fields, "
            "'remove' to delete fields."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patches": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["add", "remove", "replace", "move", "copy", "test"],
                            },
                            "path": {"type": "string"},
                            "value": {},
                            "from": {"type": "string"},
                        },
                        "required": ["op", "path"],
                    },
                },
            },
            "required": ["patches"],
        },
    }


def parse_llm_patches(tool_input: dict[str, Any]) -> list[PatchOp]:
    """Parse patches from an LLM's tool_use output.

    Expects the tool_input to have a "patches" key containing a list of
    patch operation dicts.
    """
    raw_patches = tool_input.get("patches", [])
    ops: list[PatchOp] = []
    for raw in raw_patches:
        ops.append(
            PatchOp(
                op=raw["op"],
                path=raw["path"],
                value=raw.get("value"),
                from_path=raw.get("from"),
            )
        )
    return ops
