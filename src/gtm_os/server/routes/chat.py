"""Chat endpoint — SSE streamed agent responses."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ...engine.context import assemble_context
from ...engine.experiment import PHASE_AGENT
from ...engine.harness import HarnessOptions, stream_agent_events

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    experiment_id: str | None = None
    agent: str | None = None


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    gtm = request.app.state.gtm
    thread_id = body.thread_id or f"thread-{uuid.uuid4().hex[:12]}"
    experiment_id = body.experiment_id

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")

    # Persist the user message.
    gtm.store.add_message(
        role="user",
        content=body.message,
        thread_id=thread_id,
        experiment_id=experiment_id,
    )

    primitives = gtm.runner.load_primitives_cached()
    experiment = gtm.store.get_experiment(experiment_id) if experiment_id else None
    agent_name = body.agent or (
        PHASE_AGENT.get(experiment.phase, "orchestrator") if experiment else "orchestrator"
    )

    # Pull recent memories relevant to the user message.
    memories = await gtm.memory.search(body.message, limit=6)

    system_prompt = assemble_context(
        primitives,
        agent_name=agent_name,
        experiment=experiment,
        phase=experiment.phase if experiment else None,
        relevant_memories=memories,
    )

    # Rehydrate conversation history for this thread.
    history = gtm.store.list_messages(thread_id=thread_id)
    messages: list[dict[str, Any]] = []
    for m in history:
        if m["role"] in {"user", "assistant"}:
            messages.append({"role": m["role"], "content": m["content"]})

    if not messages or messages[-1]["content"] != body.message:
        messages.append({"role": "user", "content": body.message})

    tools = gtm.runner.build_tools(primitives)

    async def event_gen():
        # Tell the client the thread + agent.
        yield {
            "event": "meta",
            "data": json.dumps(
                {
                    "thread_id": thread_id,
                    "agent": agent_name,
                    "experiment_id": experiment_id,
                }
            ),
        }

        final_message_parts: list[str] = []
        try:
            async for evt in stream_agent_events(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                config=gtm.config.llm,
                options=HarnessOptions(max_iterations=12),
            ):
                etype = evt.get("type")
                if etype == "token":
                    final_message_parts.append(evt.get("text") or "")
                    yield {"event": "token", "data": json.dumps({"text": evt["text"]})}
                elif etype == "tool_call":
                    yield {
                        "event": "tool_call",
                        "data": json.dumps(
                            {"name": evt["name"], "arguments": evt.get("arguments", {})}
                        ),
                    }
                elif etype == "tool_result":
                    yield {
                        "event": "tool_result",
                        "data": json.dumps(
                            {
                                "name": evt["name"],
                                "ok": evt.get("ok", True),
                                "result": _truncate(evt.get("result"), 4000),
                            }
                        ),
                    }
                elif etype == "final":
                    text = evt.get("message") or "".join(final_message_parts)
                    gtm.store.add_message(
                        role="assistant",
                        content=text,
                        thread_id=thread_id,
                        experiment_id=experiment_id,
                    )
                    if experiment_id:
                        gtm.store.add_experiment_tokens(experiment_id, int(evt.get("tokens") or 0))
                    yield {
                        "event": "final",
                        "data": json.dumps(
                            {
                                "message": text,
                                "tokens": evt.get("tokens", 0),
                                "tool_calls": evt.get("tool_calls", []),
                            }
                        ),
                    }
        except Exception as exc:
            logger.exception("chat stream failed")
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(event_gen())


@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, request: Request) -> dict[str, Any]:
    gtm = request.app.state.gtm
    return {"thread_id": thread_id, "messages": gtm.store.list_messages(thread_id=thread_id)}


def _truncate(value: Any, max_chars: int) -> Any:
    s = json.dumps(value, default=str)
    if len(s) <= max_chars:
        return value
    return {"_truncated": True, "preview": s[:max_chars] + "…"}
