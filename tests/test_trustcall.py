"""Tests for TrustCall-style JSON Patch system."""

from __future__ import annotations

import pytest

from gtm_os.engine.trustcall import (
    PatchError,
    PatchOp,
    apply_patch,
    apply_patches,
    build_extraction_tool,
    build_update_tool,
    parse_llm_patches,
)


def test_add_to_empty():
    doc: dict = {}
    apply_patch(doc, PatchOp(op="add", path="/name", value="Acme"))
    assert doc["name"] == "Acme"


def test_add_nested():
    doc: dict = {"icp": {}}
    apply_patch(doc, PatchOp(op="add", path="/icp/industry", value="SaaS"))
    assert doc["icp"]["industry"] == "SaaS"


def test_replace():
    doc = {"name": "Old"}
    apply_patch(doc, PatchOp(op="replace", path="/name", value="New"))
    assert doc["name"] == "New"


def test_replace_nonexistent_raises():
    doc: dict = {}
    with pytest.raises(PatchError, match="Key not found"):
        apply_patch(doc, PatchOp(op="replace", path="/missing", value="x"))


def test_remove():
    doc = {"a": 1, "b": 2}
    apply_patch(doc, PatchOp(op="remove", path="/a"))
    assert "a" not in doc
    assert doc["b"] == 2


def test_remove_nonexistent_raises():
    doc: dict = {}
    with pytest.raises(PatchError, match="Key not found"):
        apply_patch(doc, PatchOp(op="remove", path="/missing"))


def test_move():
    doc = {"src": {"val": 42}, "dst": {}}
    apply_patch(doc, PatchOp(op="move", path="/dst/val", from_path="/src/val"))
    assert doc["dst"]["val"] == 42
    assert "val" not in doc["src"]


def test_copy():
    doc = {"src": {"val": 42}, "dst": {}}
    apply_patch(doc, PatchOp(op="copy", path="/dst/val", from_path="/src/val"))
    assert doc["dst"]["val"] == 42
    assert doc["src"]["val"] == 42


def test_test_op_pass():
    doc = {"x": 5}
    apply_patch(doc, PatchOp(op="test", path="/x", value=5))


def test_test_op_fail():
    doc = {"x": 5}
    with pytest.raises(PatchError, match="Test failed"):
        apply_patch(doc, PatchOp(op="test", path="/x", value=10))


def test_array_add():
    doc = {"items": [1, 2, 3]}
    apply_patch(doc, PatchOp(op="add", path="/items/-", value=4))
    assert doc["items"] == [1, 2, 3, 4]


def test_array_insert():
    doc = {"items": ["a", "c"]}
    apply_patch(doc, PatchOp(op="add", path="/items/1", value="b"))
    assert doc["items"] == ["a", "b", "c"]


def test_array_replace():
    doc = {"items": ["a", "b", "c"]}
    apply_patch(doc, PatchOp(op="replace", path="/items/1", value="B"))
    assert doc["items"] == ["a", "B", "c"]


def test_array_remove():
    doc = {"items": ["a", "b", "c"]}
    apply_patch(doc, PatchOp(op="remove", path="/items/1"))
    assert doc["items"] == ["a", "c"]


def test_apply_patches_atomic_success():
    doc = {"a": 1}
    patches = [
        PatchOp(op="add", path="/b", value=2),
        PatchOp(op="replace", path="/a", value=10),
    ]
    result = apply_patches(doc, patches, atomic=True)
    assert result.success
    assert result.document == {"a": 10, "b": 2}
    assert len(result.applied) == 2
    # Original untouched.
    assert doc == {"a": 1}


def test_apply_patches_atomic_failure():
    doc = {"a": 1}
    patches = [
        PatchOp(op="add", path="/b", value=2),
        PatchOp(op="replace", path="/missing", value=99),
    ]
    result = apply_patches(doc, patches, atomic=True)
    assert not result.success
    assert result.document == {"a": 1}  # No changes applied.
    assert len(result.failed) == 1


def test_apply_patches_non_atomic():
    doc = {"a": 1}
    patches = [
        PatchOp(op="add", path="/b", value=2),
        PatchOp(op="replace", path="/missing", value=99),
        PatchOp(op="add", path="/c", value=3),
    ]
    result = apply_patches(doc, patches, atomic=False)
    assert not result.success
    assert result.document["b"] == 2
    assert result.document["c"] == 3
    assert len(result.applied) == 2
    assert len(result.failed) == 1


def test_parse_llm_patches():
    tool_input = {
        "patches": [
            {"op": "add", "path": "/name", "value": "Acme Corp"},
            {"op": "add", "path": "/icp/industry", "value": "SaaS"},
            {"op": "replace", "path": "/name", "value": "Acme Inc"},
        ]
    }
    ops = parse_llm_patches(tool_input)
    assert len(ops) == 3
    assert ops[0].op == "add"
    assert ops[0].path == "/name"
    assert ops[0].value == "Acme Corp"
    assert ops[2].op == "replace"


def test_build_extraction_tool_schema():
    schema = build_extraction_tool()
    assert schema["name"] == "structured_extract"
    assert "patches" in schema["input_schema"]["properties"]


def test_build_update_tool_schema():
    doc = {"name": "Acme", "icp": {"industry": "SaaS"}}
    schema = build_update_tool(doc)
    assert schema["name"] == "patch_document"
    assert "Current state" in schema["description"]
    assert "Acme" in schema["description"]


def test_escaped_pointer():
    """JSON Pointer RFC 6901: ~0 → ~, ~1 → /."""
    doc = {"a/b": {"c~d": 42}}
    apply_patch(doc, PatchOp(op="replace", path="/a~1b/c~0d", value=99))
    assert doc["a/b"]["c~d"] == 99


def test_unknown_op_raises():
    doc: dict = {}
    with pytest.raises(PatchError, match="Unknown op"):
        apply_patch(doc, PatchOp(op="invalid", path="/x"))


def test_invalid_pointer_raises():
    doc: dict = {}
    with pytest.raises(PatchError, match="must start with /"):
        apply_patch(doc, PatchOp(op="add", path="noslash", value=1))
