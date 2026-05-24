"""Tests for context manager — model-aware budgets, tiered compaction."""

import asyncio

from gtm_os.config import LLMConfig
from gtm_os.engine.context_manager import (
    ContextManager,
    _count_tokens,
    _get_model_context_limit,
    _msg_text,
    estimate_tokens,
)


def test_model_context_limit_gpt4o():
    limit = _get_model_context_limit("openai/gpt-4o")
    assert limit == 128_000


def test_model_context_limit_claude():
    limit = _get_model_context_limit("anthropic/claude-3-5-sonnet-20241022")
    assert limit == 200_000


def test_model_context_limit_ollama():
    limit = _get_model_context_limit("ollama/llama3.1")
    assert limit == 8_192


def test_model_context_limit_unknown():
    limit = _get_model_context_limit("custom/unknown-model")
    assert limit == 32_000


def test_context_manager_auto_budget_openai():
    cfg = LLMConfig(model="openai/gpt-4o")
    cm = ContextManager(cfg)
    assert cm.max_context_tokens == int(128_000 * 0.80)


def test_context_manager_auto_budget_ollama():
    cfg = LLMConfig(model="ollama/llama3.1")
    cm = ContextManager(cfg)
    assert cm.max_context_tokens == int(8_192 * 0.80)
    assert cm._is_local_model is True


def test_context_manager_manual_override():
    cfg = LLMConfig(model="openai/gpt-4o")
    cm = ContextManager(cfg, max_context_tokens=5000)
    assert cm.max_context_tokens == 5000


def test_prune_no_op_when_under_budget():
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    cm = ContextManager(cfg, max_context_tokens=100_000)
    msgs = [{"role": "user", "content": "hello"}]
    result = cm.prune(msgs)
    assert result == msgs


def test_prune_truncates_large_tool():
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    cm = ContextManager(cfg, max_context_tokens=200)
    msgs = [
        {"role": "tool", "content": "x" * 5000, "name": "big"},
        {"role": "assistant", "content": "thinking about it"},
        {"role": "user", "content": "go on"},
        {"role": "assistant", "content": "more thought"},
        {"role": "user", "content": "latest"},
    ]
    result = cm.prune(msgs)
    tool_msg = next(m for m in result if m.get("role") == "tool")
    assert len(tool_msg["content"]) < 5000


def test_tiered_compact_tier1_truncates():
    cfg = LLMConfig(model="ollama/llama3.1")
    cm = ContextManager(cfg, max_context_tokens=50)
    msgs = [
        {"role": "tool", "content": "z" * 500},
        {"role": "assistant", "content": "thinking"},
        {"role": "tool", "content": "a" * 400},
        {"role": "user", "content": "recent"},
    ]
    result = cm._tiered_compact(msgs, tokens=5000, budget=500)
    # Tier 1+ compaction should reduce the tool content
    tool_msgs = [m for m in result if m.get("role") == "tool"]
    assert all(len(m["content"]) < 500 for m in tool_msgs)


def test_tiered_compact_tier2_drops_content():
    cfg = LLMConfig(model="ollama/llama3.1")
    cm = ContextManager(cfg, max_context_tokens=10)
    msgs = [
        {"role": "tool", "content": "z" * 500},
        {"role": "assistant", "content": "thinking", "tool_calls": [{"function": {"name": "foo"}}]},
        {"role": "user", "content": "recent"},
    ]
    result = cm._tiered_compact(msgs, tokens=10000, budget=10)
    tool_msg = next(m for m in result if m.get("role") == "tool")
    assert tool_msg["content"] == "[dropped]"


def test_count_tokens_basic():
    tokens = _count_tokens("hello world", "openai/gpt-4o-mini")
    assert tokens > 0


def test_count_tokens_empty():
    tokens = _count_tokens("", "openai/gpt-4o-mini")
    assert tokens == 0


def test_msg_text_extracts_content():
    msg = {"role": "user", "content": "hello"}
    assert "hello" in _msg_text(msg)


def test_msg_text_includes_tool_calls():
    msg = {"role": "assistant", "content": "ok", "tool_calls": [{"fn": "test"}]}
    text = _msg_text(msg)
    assert "test" in text


def test_estimate_tokens_multiple():
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    tokens = estimate_tokens(msgs, "openai/gpt-4o-mini")
    assert tokens > 0


def test_flush_to_memory_saves_long_messages():
    cfg = LLMConfig(model="openai/gpt-4o-mini", embedding_model="")
    cm = ContextManager(cfg)

    import os
    import tempfile

    from gtm_os.engine.memory import VectorMemory
    from gtm_os.engine.store import Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(os.path.join(tmp, "test.db"))
        memory = VectorMemory(store, cfg)
        msgs = [
            {
                "role": "assistant",
                "content": "This is a long assistant message that should be saved to memory because it contains meaningful content worth preserving for future reference.",
            },
            {"role": "user", "content": "short"},
        ]
        saved = asyncio.run(cm.flush_to_memory(msgs, memory))
        assert saved >= 1


def test_flush_to_memory_skips_short():
    cfg = LLMConfig(model="openai/gpt-4o-mini", embedding_model="")
    cm = ContextManager(cfg)

    import os
    import tempfile

    from gtm_os.engine.memory import VectorMemory
    from gtm_os.engine.store import Store

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(os.path.join(tmp, "test.db"))
        memory = VectorMemory(store, cfg)
        msgs = [
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "hello"},
        ]
        saved = asyncio.run(cm.flush_to_memory(msgs, memory))
        assert saved == 0
