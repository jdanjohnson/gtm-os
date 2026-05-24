"""Tests for harness — parallel tool execution, options."""

import asyncio

from gtm_os.engine.harness import (
    HarnessOptions,
    _execute_tool,
    _execute_tools_parallel,
    _tool_calls_signature,
    _tools_to_openai_schema,
)
from gtm_os.types import Tool, ToolCall


def _make_tool(name: str, result=None, error=None) -> Tool:
    """Helper: create a Tool with an async execute function."""

    async def execute(**kwargs):
        if error:
            raise ValueError(error)
        return result or {"ok": True, **kwargs}

    return Tool(
        name=name,
        description=f"Tool {name}",
        parameters={"type": "object", "properties": {}},
        execute=execute,
    )


def test_harness_options_defaults():
    opts = HarnessOptions()
    assert opts.max_iterations == 20
    assert opts.parallel_tool_calls is True
    assert opts.stream is False


def test_tools_to_openai_schema():
    tool = _make_tool("test_tool")
    schema = _tools_to_openai_schema([tool])
    assert len(schema) == 1
    assert schema[0]["type"] == "function"
    assert schema[0]["function"]["name"] == "test_tool"


def test_execute_tool_success():
    tool = _make_tool("calc", result={"sum": 42})
    tc = ToolCall(id="tc1", name="calc", arguments={"x": 1})
    result = asyncio.run(_execute_tool(tc, {"calc": tool}))
    assert result.error is None
    assert result.result == {"sum": 42}


def test_execute_tool_unknown():
    tc = ToolCall(id="tc1", name="nonexistent", arguments={})
    result = asyncio.run(_execute_tool(tc, {}))
    assert result.error is not None
    assert "unknown tool" in result.error


def test_execute_tool_error():
    tool = _make_tool("bad", error="something broke")
    tc = ToolCall(id="tc1", name="bad", arguments={})
    result = asyncio.run(_execute_tool(tc, {"bad": tool}))
    assert result.error is not None
    assert "something broke" in result.error


def test_execute_tools_parallel():
    tool_a = _make_tool("a", result={"v": "A"})
    tool_b = _make_tool("b", result={"v": "B"})
    tools_by_name = {"a": tool_a, "b": tool_b}
    calls = [
        ToolCall(id="tc1", name="a", arguments={}),
        ToolCall(id="tc2", name="b", arguments={}),
    ]
    results = asyncio.run(_execute_tools_parallel(calls, tools_by_name))
    assert len(results) == 2
    assert results[0].name == "a"
    assert results[1].name == "b"
    assert results[0].error is None
    assert results[1].error is None


def test_execute_tools_parallel_mixed():
    tool_ok = _make_tool("ok_tool", result="fine")
    tool_bad = _make_tool("bad_tool", error="oops")
    tools_by_name = {"ok_tool": tool_ok, "bad_tool": tool_bad}
    calls = [
        ToolCall(id="tc1", name="ok_tool", arguments={}),
        ToolCall(id="tc2", name="bad_tool", arguments={}),
    ]
    results = asyncio.run(_execute_tools_parallel(calls, tools_by_name))
    assert results[0].error is None
    assert results[1].error is not None


def test_tool_calls_signature():
    calls = [
        ToolCall(id="tc1", name="search", arguments={"query": "test"}),
        ToolCall(id="tc2", name="get", arguments={"id": "123"}),
    ]
    sig = _tool_calls_signature(calls)
    assert "search" in sig
    assert "get" in sig
    assert "||" in sig
