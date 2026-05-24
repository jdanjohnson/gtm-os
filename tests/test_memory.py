import pytest

from gtm_os.config import LLMConfig
from gtm_os.engine.memory import VectorMemory
from gtm_os.engine.store import Store


@pytest.mark.asyncio
async def test_memory_keyword_fallback(store: Store):
    # No embedding_model configured → keyword fallback path.
    memory = VectorMemory(store, LLMConfig(embedding_model=""))

    await memory.save("apollo people search worked well for VPs", type="learning")
    await memory.save("hubspot integration was flaky on weekends", type="fact")
    await memory.save("the customer prefers cold calls over emails", type="preference")

    results = await memory.search("apollo people")
    assert results
    assert any("apollo" in r.content.lower() for r in results)
    # similarity scores are computed
    assert all(r.similarity is not None for r in results)


@pytest.mark.asyncio
async def test_memory_reinforce(store: Store):
    memory = VectorMemory(store, LLMConfig(embedding_model=""))
    m = await memory.save(
        "subject lines with dollar amounts get higher reply rates", type="learning", confidence=0.5
    )
    reinforced = await memory.reinforce(m.id, experiment_id="exp-1")
    assert reinforced is not None
    assert reinforced.confidence > 0.5
    assert "exp-1" in reinforced.reinforced_by
