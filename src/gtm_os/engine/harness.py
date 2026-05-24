"""Thin LLM harness — tool loop, streaming, provider switching via litellm.

This is intentionally small. The principle (per the PRD): no heavyweight framework.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..config import LLMConfig
from ..types import AgentMessage, AgentResult, Tool, ToolCall, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class HarnessOptions:
    max_iterations: int = 20
    temperature: float | None = None
    stream: bool = False
    extra_stop_strings: list[str] | None = None


def _tools_to_openai_schema(tools: list[Tool]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _normalize_tool_calls(raw_calls: Any) -> list[ToolCall]:
    if not raw_calls:
        return []
    out: list[ToolCall] = []
    for tc in raw_calls:
        # litellm returns objects; convert to plain dicts.
        if not isinstance(tc, dict):
            tc_dict = getattr(tc, "model_dump", None)
            tc = tc_dict() if callable(tc_dict) else dict(tc)  # type: ignore[assignment]
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name") or "unknown"
        args_raw = fn.get("arguments") or tc.get("arguments") or "{}"
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw) if args_raw.strip() else {}
            except json.JSONDecodeError:
                args = {"_raw": args_raw}
        else:
            args = args_raw or {}
        out.append(
            ToolCall(id=str(tc.get("id") or f"tc_{int(time.time()*1000)}"), name=name, arguments=args)
        )
    return out


async def llm_call(
    *,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[Tool] | None,
    config: LLMConfig,
    temperature: float | None = None,
    stream: bool = False,
) -> tuple[AgentMessage, int]:
    """One LLM call. Returns (assistant message with tool_calls, tokens_used)."""
    import litellm

    full_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}] + list(
        messages
    )
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": full_messages,
        "temperature": float(temperature if temperature is not None else config.temperature),
        "max_tokens": config.max_tokens,
        "timeout": config.request_timeout_seconds,
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if tools:
        kwargs["tools"] = _tools_to_openai_schema(tools)
        kwargs["tool_choice"] = "auto"

    if stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        return await _llm_stream(**kwargs)

    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    msg = choice.message
    tool_calls = _normalize_tool_calls(getattr(msg, "tool_calls", None) or [])
    tokens = 0
    usage = getattr(response, "usage", None)
    if usage is not None:
        tokens = int(getattr(usage, "total_tokens", 0) or 0)
    return (
        AgentMessage(role="assistant", content=msg.content or "", tool_calls=tool_calls),
        tokens,
    )


async def _llm_stream(**kwargs: Any) -> tuple[AgentMessage, int]:
    """Internal: consume a litellm stream and assemble the final message + tokens."""
    import litellm

    content_parts: list[str] = []
    tool_call_acc: dict[int, dict[str, Any]] = {}
    tokens = 0
    async for chunk in await litellm.acompletion(**kwargs):
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            usage = getattr(chunk, "usage", None)
            if usage:
                tokens = int(getattr(usage, "total_tokens", 0) or 0)
            continue
        delta = choices[0].delta if hasattr(choices[0], "delta") else choices[0].get("delta", {})
        if delta is None:
            continue
        d_content = getattr(delta, "content", None) if not isinstance(delta, dict) else delta.get(
            "content"
        )
        if d_content:
            content_parts.append(str(d_content))
        d_calls = (
            getattr(delta, "tool_calls", None)
            if not isinstance(delta, dict)
            else delta.get("tool_calls")
        ) or []
        for tc in d_calls:
            idx = getattr(tc, "index", None) if not isinstance(tc, dict) else tc.get("index", 0)
            acc = tool_call_acc.setdefault(int(idx or 0), {"function": {"arguments": ""}})
            tc_id = getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id")
            if tc_id:
                acc["id"] = tc_id
            fn = (
                getattr(tc, "function", None)
                if not isinstance(tc, dict)
                else tc.get("function")
            )
            if fn is None:
                continue
            name = getattr(fn, "name", None) if not isinstance(fn, dict) else fn.get("name")
            if name:
                acc["function"]["name"] = name
            args = (
                getattr(fn, "arguments", None)
                if not isinstance(fn, dict)
                else fn.get("arguments")
            )
            if args:
                acc["function"]["arguments"] += args

    final = AgentMessage(
        role="assistant",
        content="".join(content_parts),
        tool_calls=_normalize_tool_calls(list(tool_call_acc.values())),
    )
    return final, tokens


async def stream_llm_tokens(
    *,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[Tool] | None,
    config: LLMConfig,
    on_token: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[AgentMessage, int]:
    """Like `llm_call(stream=True)` but invokes `on_token` per content delta."""
    import litellm

    full_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}] + list(
        messages
    )
    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": full_messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout": config.request_timeout_seconds,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if tools:
        kwargs["tools"] = _tools_to_openai_schema(tools)
        kwargs["tool_choice"] = "auto"

    content_parts: list[str] = []
    tool_call_acc: dict[int, dict[str, Any]] = {}
    tokens = 0

    async for chunk in await litellm.acompletion(**kwargs):
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            usage = getattr(chunk, "usage", None)
            if usage:
                tokens = int(getattr(usage, "total_tokens", 0) or 0)
            continue
        delta = choices[0].delta if hasattr(choices[0], "delta") else choices[0].get("delta", {})
        if delta is None:
            continue
        d_content = (
            getattr(delta, "content", None)
            if not isinstance(delta, dict)
            else delta.get("content")
        )
        if d_content:
            content_parts.append(str(d_content))
            if on_token is not None:
                await on_token(str(d_content))
        d_calls = (
            getattr(delta, "tool_calls", None)
            if not isinstance(delta, dict)
            else delta.get("tool_calls")
        ) or []
        for tc in d_calls:
            idx = getattr(tc, "index", None) if not isinstance(tc, dict) else tc.get("index", 0)
            acc = tool_call_acc.setdefault(int(idx or 0), {"function": {"arguments": ""}})
            tc_id = getattr(tc, "id", None) if not isinstance(tc, dict) else tc.get("id")
            if tc_id:
                acc["id"] = tc_id
            fn = (
                getattr(tc, "function", None)
                if not isinstance(tc, dict)
                else tc.get("function")
            )
            if fn is None:
                continue
            name = getattr(fn, "name", None) if not isinstance(fn, dict) else fn.get("name")
            if name:
                acc["function"]["name"] = name
            args = (
                getattr(fn, "arguments", None)
                if not isinstance(fn, dict)
                else fn.get("arguments")
            )
            if args:
                acc["function"]["arguments"] += args

    final = AgentMessage(
        role="assistant",
        content="".join(content_parts),
        tool_calls=_normalize_tool_calls(list(tool_call_acc.values())),
    )
    return final, tokens


async def _execute_tool(
    tool_call: ToolCall, tools_by_name: dict[str, Tool]
) -> ToolResult:
    tool = tools_by_name.get(tool_call.name)
    if not tool:
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            result=None,
            error=f"unknown tool: {tool_call.name}",
        )
    try:
        result = await tool.execute(**(tool_call.arguments or {}))
        return ToolResult(tool_call_id=tool_call.id, name=tool_call.name, result=result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool %s failed", tool_call.name)
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            result=None,
            error=f"{type(exc).__name__}: {exc}",
        )


def _tool_calls_signature(calls: list[ToolCall]) -> str:
    return "||".join(f"{c.name}:{json.dumps(c.arguments, sort_keys=True)}" for c in calls)


async def run_agent(
    *,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[Tool],
    config: LLMConfig,
    options: HarnessOptions | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> AgentResult:
    """Core agent loop.

    Loops up to `max_iterations` times:
      1. call the LLM
      2. if it returned tool calls — run them, append results, loop
      3. otherwise — return the final message
    """
    opts = options or HarnessOptions()
    tools_by_name = {t.name: t for t in tools}
    convo: list[dict[str, Any]] = list(messages)
    total_tokens = 0
    last_signature: str | None = None
    repeat_count = 0
    all_calls: list[ToolCall] = []
    all_results: list[ToolResult] = []

    for iteration in range(opts.max_iterations):
        assistant_msg, tokens = await llm_call(
            system_prompt=system_prompt,
            messages=convo,
            tools=tools,
            config=config,
            temperature=opts.temperature,
        )
        total_tokens += tokens

        if on_event:
            await on_event({"type": "assistant_message", "message": assistant_msg.content})

        if not assistant_msg.tool_calls:
            return AgentResult(
                message=assistant_msg,
                tool_calls=all_calls,
                tool_results=all_results,
                iterations=iteration + 1,
                tokens_used=total_tokens,
                finished=True,
            )

        # Doom-loop detection.
        sig = _tool_calls_signature(assistant_msg.tool_calls)
        if sig == last_signature:
            repeat_count += 1
        else:
            repeat_count = 0
        last_signature = sig
        if repeat_count >= 2:
            return AgentResult(
                message=AgentMessage(
                    role="assistant",
                    content=(
                        assistant_msg.content
                        or "[Doom-loop: stopping after repeated identical tool calls.]"
                    ),
                ),
                tool_calls=all_calls,
                tool_results=all_results,
                iterations=iteration + 1,
                tokens_used=total_tokens,
                finished=False,
                error="doom_loop",
            )

        # Append assistant message that requested the tools.
        convo.append(
            {
                "role": "assistant",
                "content": assistant_msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in assistant_msg.tool_calls
                ],
            }
        )

        for tc in assistant_msg.tool_calls:
            if on_event:
                await on_event({"type": "tool_call", "name": tc.name, "arguments": tc.arguments})
            tool_result = await _execute_tool(tc, tools_by_name)
            all_calls.append(tc)
            all_results.append(tool_result)
            if on_event:
                await on_event(
                    {
                        "type": "tool_result",
                        "name": tc.name,
                        "ok": tool_result.error is None,
                        "result": tool_result.result if tool_result.error is None else tool_result.error,
                    }
                )
            convo.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": (
                        json.dumps(tool_result.result, default=str)
                        if tool_result.error is None
                        else json.dumps({"error": tool_result.error})
                    ),
                }
            )

    # Out of iterations.
    return AgentResult(
        message=AgentMessage(role="assistant", content="[max iterations reached]"),
        tool_calls=all_calls,
        tool_results=all_results,
        iterations=opts.max_iterations,
        tokens_used=total_tokens,
        finished=False,
        error="max_iterations",
    )


async def stream_agent_events(
    *,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[Tool],
    config: LLMConfig,
    options: HarnessOptions | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """SSE-friendly version: yields events as the agent runs.

    Events: {"type": "token", "text": "..."}, {"type": "tool_call", ...},
    {"type": "tool_result", ...}, {"type": "final", "message": "...", "tokens": N}.
    """
    opts = options or HarnessOptions()
    tools_by_name = {t.name: t for t in tools}
    convo: list[dict[str, Any]] = list(messages)
    total_tokens = 0
    all_calls: list[ToolCall] = []
    all_results: list[ToolResult] = []

    for iteration in range(opts.max_iterations):
        async def _on_token(t: str, *, _buf: list[str] = []) -> None:
            _buf.append(t)

        tokens_buffer: list[str] = []

        async def _emit(t: str) -> None:
            tokens_buffer.append(t)

        # We can't yield from a callback, so we do streaming + collect tokens.
        # Implementation: stream once, yield tokens as we go via an inline queue.
        import asyncio

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def _producer() -> AgentMessage:
            async def cb(t: str) -> None:
                await queue.put({"type": "token", "text": t})

            msg, tokens = await stream_llm_tokens(
                system_prompt=system_prompt,
                messages=convo,
                tools=tools,
                config=config,
                on_token=cb,
            )
            await queue.put({"__done__": True, "msg": msg, "tokens": tokens})
            return msg

        producer = asyncio.create_task(_producer())

        final_msg: AgentMessage | None = None
        tokens_this_call = 0
        while True:
            evt = await queue.get()
            if evt.get("__done__"):
                final_msg = evt["msg"]
                tokens_this_call = evt["tokens"]
                break
            yield evt
        await producer  # surface any errors

        assert final_msg is not None
        total_tokens += tokens_this_call

        if not final_msg.tool_calls:
            yield {
                "type": "final",
                "message": final_msg.content,
                "tokens": total_tokens,
                "tool_calls": [
                    {"name": tc.name, "arguments": tc.arguments} for tc in all_calls
                ],
            }
            return

        convo.append(
            {
                "role": "assistant",
                "content": final_msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in final_msg.tool_calls
                ],
            }
        )

        for tc in final_msg.tool_calls:
            yield {"type": "tool_call", "name": tc.name, "arguments": tc.arguments}
            result = await _execute_tool(tc, tools_by_name)
            all_calls.append(tc)
            all_results.append(result)
            yield {
                "type": "tool_result",
                "name": tc.name,
                "ok": result.error is None,
                "result": result.result if result.error is None else result.error,
            }
            convo.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": (
                        json.dumps(result.result, default=str)
                        if result.error is None
                        else json.dumps({"error": result.error})
                    ),
                }
            )

    yield {"type": "final", "message": "[max iterations reached]", "tokens": total_tokens}
