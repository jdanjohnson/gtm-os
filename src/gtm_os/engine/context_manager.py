"""3-layer context management — pruning, memory flush, compaction.

Implements WS2D:
- Tiered compaction for local models (Ollama): 3-tier system from Forge
  - Tier 1 (light): truncate old tool results to 200 chars
  - Tier 2 (medium): drop tool results entirely, preserve reasoning
  - Tier 3 (aggressive): drop reasoning, keep tool call skeleton only
- Model-aware token budgets: different max context per model
- Token budget tracking per experiment (integrates with experiment's token_budget)

Inspired by TrustClaw's ContextManager pattern and Forge's TieredCompact.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import LLMConfig
from .memory import VectorMemory

logger = logging.getLogger(__name__)

# Model-aware max context tokens.
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "openai/gpt-4o": 128_000,
    "openai/gpt-4o-mini": 128_000,
    "openai/gpt-4-turbo": 128_000,
    "anthropic/claude-3-5-sonnet-20241022": 200_000,
    "anthropic/claude-3-haiku-20240307": 200_000,
    "anthropic/claude-3-opus-20240229": 200_000,
    "ollama/llama3.1": 8_192,
    "ollama/llama3": 8_192,
    "ollama/mistral": 8_192,
    "ollama/mixtral": 32_768,
    "ollama/codellama": 16_384,
}

DEFAULT_CONTEXT_LIMIT = 32_000


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
    except Exception:
        return max(1, len(text) // 4)


def _msg_text(msg: dict[str, Any]) -> str:
    parts: list[str] = [str(msg.get("content") or "")]
    for tc in msg.get("tool_calls") or []:
        parts.append(str(tc))
    return "\n".join(parts)


def estimate_tokens(messages: list[dict], model: str) -> int:
    return sum(_count_tokens(_msg_text(m), model) for m in messages)


def _get_model_context_limit(model: str) -> int:
    """Resolve the context window size for a given model."""
    if model in MODEL_CONTEXT_LIMITS:
        return MODEL_CONTEXT_LIMITS[model]
    for prefix, limit in MODEL_CONTEXT_LIMITS.items():
        if model.startswith(prefix.rsplit("/", 1)[0] + "/"):
            return limit
    return DEFAULT_CONTEXT_LIMIT


class ContextManager:
    """Three-layer context management for long-running agent sessions.

    Model-aware: automatically adjusts budget based on the model being used.
    Supports tiered compaction for resource-constrained models (Ollama).
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        *,
        max_context_tokens: int | None = None,
        soft_trim_ratio: float = 0.30,
        hard_clear_ratio: float = 0.50,
    ) -> None:
        self.llm_config = llm_config
        # WS2D: Model-aware context budget.
        if max_context_tokens is not None:
            self.max_context_tokens = max_context_tokens
        else:
            model_limit = _get_model_context_limit(llm_config.model)
            # Use 80% of model limit to leave room for system prompt + response.
            self.max_context_tokens = int(model_limit * 0.80)
        self.soft_trim_ratio = soft_trim_ratio
        self.hard_clear_ratio = hard_clear_ratio
        self._is_local_model = llm_config.model.startswith("ollama/")

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
        keep_recent = max(2, min(4, len(out) // 2))

        # WS2D: For local models, use tiered compaction.
        if self._is_local_model:
            return self._tiered_compact(out, tokens, budget)

        for m in out[:-keep_recent] if keep_recent < len(out) else []:
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

        drop_before = max(0, len(out) - max(4, keep_recent + 2))
        cleaned: list[dict] = []
        for i, m in enumerate(out):
            if m.get("role") == "tool" and i < drop_before:
                m["content"] = "[tool result dropped to free context]"
            cleaned.append(m)
        return cleaned

    def _tiered_compact(self, messages: list[dict], tokens: int, budget: int) -> list[dict]:
        """WS2D: Three-tier compaction for local/small-context models."""
        keep_recent = max(2, min(4, len(messages) // 2))

        # Tier 1 (light): truncate old tool results to 200 chars.
        for m in messages[:-keep_recent] if keep_recent < len(messages) else []:
            if m.get("role") == "tool":
                content = str(m.get("content") or "")
                if len(content) > 200:
                    m["content"] = content[:200] + "…"

        tokens = estimate_tokens(messages, self.llm_config.model)
        if tokens <= budget:
            return messages

        # Tier 2 (medium): drop tool results entirely, preserve reasoning.
        for m in messages[:-keep_recent] if keep_recent < len(messages) else []:
            if m.get("role") == "tool":
                m["content"] = "[dropped]"

        tokens = estimate_tokens(messages, self.llm_config.model)
        if tokens <= budget:
            return messages

        # Tier 3 (aggressive): drop reasoning, keep tool call skeleton only.
        compacted: list[dict] = []
        for i, m in enumerate(messages):
            if i >= len(messages) - keep_recent:
                compacted.append(m)
                continue
            if m.get("role") == "assistant":
                tool_calls = m.get("tool_calls")
                if tool_calls:
                    compacted.append(
                        {"role": "assistant", "content": None, "tool_calls": tool_calls}
                    )
                # Drop content-only assistant messages in tier 3.
                continue
            if m.get("role") == "tool":
                compacted.append(
                    {"role": "tool", "tool_call_id": m.get("tool_call_id"), "content": "[dropped]"}
                )
                continue
            compacted.append(m)
        return compacted

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
            convo = "\n".join(f"[{m.get('role')}] {(m.get('content') or '')[:1000]}" for m in head)
            resp = await litellm.acompletion(
                model=self.llm_config.model,
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": convo},
                ],
                max_tokens=800,
                temperature=0.2,
            )
            summary_text = resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("compaction LLM call failed: %s", exc)
            summary_text = "\n".join(
                f"- [{m.get('role')}] {(m.get('content') or '')[:150]}" for m in head[:6]
            )

        summary_msg: dict[str, Any] = {
            "role": "system",
            "content": f"[Conversation history summary]\n{summary_text}",
        }
        return [summary_msg, *tail]
