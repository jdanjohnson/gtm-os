"""3-layer context management — pruning, memory flush, compaction.

Inspired by TrustClaw's ContextManager pattern. Token counts are approximate (1 token ~= 4
characters) when tiktoken isn't available, but exact-when-possible.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import LLMConfig
from .memory import VectorMemory

logger = logging.getLogger(__name__)


def _count_tokens(text: str, model: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model.split("/", 1)[-1])
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:  # pragma: no cover — tiktoken is a hard dep but be safe
        return max(1, len(text) // 4)


def _msg_text(msg: dict[str, Any]) -> str:
    parts: list[str] = [str(msg.get("content") or "")]
    for tc in msg.get("tool_calls") or []:
        parts.append(str(tc))
    return "\n".join(parts)


def estimate_tokens(messages: list[dict], model: str) -> int:
    return sum(_count_tokens(_msg_text(m), model) for m in messages)


class ContextManager:
    """Three-layer context management for long-running agent sessions."""

    def __init__(
        self,
        llm_config: LLMConfig,
        *,
        max_context_tokens: int = 32_000,
        soft_trim_ratio: float = 0.30,
        hard_clear_ratio: float = 0.50,
    ) -> None:
        self.llm_config = llm_config
        self.max_context_tokens = max_context_tokens
        self.soft_trim_ratio = soft_trim_ratio
        self.hard_clear_ratio = hard_clear_ratio

    # Layer 1 — pruning
    def prune(self, messages: list[dict]) -> list[dict]:
        """Trim large tool results without dropping system / recent turns."""
        if not messages:
            return messages
        budget = self.max_context_tokens
        soft = int(budget * (1 - self.soft_trim_ratio))
        hard = int(budget * (1 - self.hard_clear_ratio))
        tokens = estimate_tokens(messages, self.llm_config.model)
        if tokens <= soft:
            return messages

        out = [dict(m) for m in messages]
        for m in out[:-4]:
            if m.get("role") != "tool":
                continue
            content = m.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            if len(content) > 1500:
                m["content"] = content[:1200] + "\n…[truncated for context]"

        tokens = estimate_tokens(out, self.llm_config.model)
        if tokens <= hard:
            return out

        cleaned: list[dict] = []
        for i, m in enumerate(out):
            if (
                m.get("role") == "tool"
                and i < len(out) - 6
            ):
                m["content"] = "[tool result dropped to free context]"
            cleaned.append(m)
        return cleaned

    # Layer 2 — memory flush
    async def flush_to_memory(
        self,
        messages: list[dict],
        memory: VectorMemory,
        *,
        experiment_id: str | None = None,
    ) -> int:
        """Extract salient assistant statements into long-term memory before we compact."""
        saved = 0
        for m in messages:
            if m.get("role") != "assistant":
                continue
            content = (m.get("content") or "").strip()
            if not content or len(content) < 80:
                continue
            await memory.save(
                content,
                type="learning",
                source="context-flush",
                experiment_id=experiment_id,
                confidence=0.45,
            )
            saved += 1
            if saved >= 5:
                break
        return saved

    # Layer 3 — compaction
    async def compact(self, messages: list[dict]) -> list[dict]:
        """LLM-driven summarization of the older half of the conversation."""
        if len(messages) <= 8:
            return messages

        keep_tail = 4
        head, tail = messages[:-keep_tail], messages[-keep_tail:]
        if estimate_tokens(head, self.llm_config.model) < 1000:
            return messages

        try:
            import litellm

            summary_prompt = (
                "Summarize the following conversation as compact, neutral notes that another "
                "agent could pick up. Preserve: facts, decisions, prospect data, hypotheses, "
                "open tasks. Drop pleasantries."
            )
            convo = "\n".join(
                f"[{m.get('role')}] {(m.get('content') or '')[:1000]}" for m in head
            )
            resp = await litellm.acompletion(
                model=self.llm_config.model,
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": convo},
                ],
                api_key=self.llm_config.api_key,
                temperature=0.2,
                max_tokens=800,
                timeout=self.llm_config.request_timeout_seconds,
            )
            summary = resp.choices[0].message.content
        except Exception as exc:
            logger.warning("compaction failed: %s", exc)
            summary = (
                "[compaction unavailable — earlier conversation preserved verbatim was "
                f"~{estimate_tokens(head, self.llm_config.model)} tokens]"
            )

        return [
            {"role": "system", "content": f"[Conversation summary]\n{summary}"},
            *tail,
        ]

    def tiered_compact(self, messages: list[dict], tier: int) -> list[dict]:
        """Forge-style tiered compaction for local / small-context models."""
        out: list[dict] = []
        for m in messages:
            mm = dict(m)
            if tier >= 1 and mm.get("role") == "tool":
                content = mm.get("content") or ""
                if isinstance(content, str) and len(content) > 200:
                    mm["content"] = content[:200] + "…"
            if tier >= 2 and mm.get("role") == "tool":
                mm["content"] = "[tool result dropped]"
            if tier >= 3 and mm.get("role") == "assistant":
                tcs = mm.get("tool_calls") or []
                mm["content"] = ""
                if tcs:
                    skeleton = ", ".join(
                        (tc.get("function", {}) or {}).get("name", "tool") for tc in tcs
                    )
                    mm["content"] = f"[called: {skeleton}]"
            out.append(mm)
        return out
