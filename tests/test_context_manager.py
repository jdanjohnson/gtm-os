from gtm_os.config import LLMConfig
from gtm_os.engine.context_manager import ContextManager, estimate_tokens


def test_prune_trims_large_tool_results():
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    cm = ContextManager(cfg, max_context_tokens=500)
    msgs = [
        {"role": "system", "content": "stay frosty"},
        {"role": "user", "content": "go"},
        {"role": "tool", "name": "x", "content": "x" * 8000},
        {"role": "assistant", "content": "ack"},
        {"role": "tool", "name": "y", "content": "y" * 200},
        {"role": "assistant", "content": "done"},
    ]
    pruned = cm.prune(msgs)
    assert len(pruned) == len(msgs)
    # the large tool result should have been truncated
    pruned_tool = next(m for m in pruned if m["role"] == "tool" and m.get("name") == "x")
    assert "[truncated for context]" in pruned_tool["content"]


def test_tiered_compact():
    cfg = LLMConfig(model="ollama/llama3.1")
    cm = ContextManager(cfg, max_context_tokens=50)
    msgs = [
        {"role": "tool", "content": "z" * 500, "name": "deep"},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "deep"}}],
            "content": "thinking",
        },
        {"role": "user", "content": "recent message"},
    ]
    result = cm._tiered_compact(msgs, tokens=10000, budget=50)
    # Tier 1+ compaction should have truncated or dropped the tool content
    tool_msg = next((m for m in result if m.get("role") == "tool"), None)
    assert tool_msg is not None
    assert len(tool_msg["content"]) < 500


def test_estimate_tokens_smoke():
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    n = estimate_tokens([{"role": "user", "content": "hi there"}], cfg.model)
    assert n > 0
