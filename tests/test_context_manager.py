
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
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    cm = ContextManager(cfg)
    msgs = [
        {"role": "tool", "content": "z" * 500, "name": "deep"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "deep"}}], "content": "thinking"},
    ]
    t1 = cm.tiered_compact(msgs, tier=1)
    assert "…" in t1[0]["content"]
    t3 = cm.tiered_compact(msgs, tier=3)
    assert t3[1]["content"].startswith("[called:")


def test_estimate_tokens_smoke():
    cfg = LLMConfig(model="openai/gpt-4o-mini")
    n = estimate_tokens([{"role": "user", "content": "hi there"}], cfg.model)
    assert n > 0
