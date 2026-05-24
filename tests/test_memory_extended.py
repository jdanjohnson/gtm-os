"""Tests for extended memory features — entity, decay, dedup, batch embed."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from gtm_os.config import LLMConfig
from gtm_os.engine.memory import VectorMemory, _cosine, _keyword_score, _slugify
from gtm_os.engine.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "test.db"))


@pytest.fixture
def memory(store):
    cfg = LLMConfig(model="openai/gpt-4o-mini", embedding_model="")
    return VectorMemory(store, cfg)


def test_save_and_search_keyword(memory):
    asyncio.run(memory.save("Python is great for data science", type="fact"))
    asyncio.run(memory.save("JavaScript rules the frontend", type="fact"))
    results = asyncio.run(memory.search("Python data", limit=5))
    assert len(results) >= 1
    assert any("Python" in r.content for r in results)


def test_save_entity(memory):
    asyncio.run(
        memory.save_entity(
            "company",
            "acme-corp",
            {"name": "Acme Corp", "industry": "Tech", "size": "500+"},
            experiment_id="exp-1",
        )
    )
    entities = asyncio.run(memory.get_entity("company", "acme-corp"))
    assert len(entities) == 1
    assert "Acme Corp" in entities[0].content


def test_save_entity_multiple_facts(memory):
    asyncio.run(memory.save_entity("prospect", "john-doe", {"name": "John Doe", "title": "CTO"}))
    asyncio.run(
        memory.save_entity("prospect", "jane-smith", {"name": "Jane Smith", "title": "VP Eng"})
    )
    john = asyncio.run(memory.get_entity("prospect", "john-doe"))
    jane = asyncio.run(memory.get_entity("prospect", "jane-smith"))
    assert len(john) == 1
    assert len(jane) == 1


def test_apply_decay_no_old_memories(memory):
    asyncio.run(memory.save("recent memory", type="fact"))
    count = memory.apply_decay()
    assert count == 0  # Too recent to decay


def test_apply_decay_old_memories(memory, store):
    # Manually insert an old memory.
    old_date = (datetime.now(UTC) - timedelta(weeks=8)).isoformat(timespec="seconds")
    store.insert_memory(
        type="fact",
        content="old fact",
        source=None,
        experiment_id=None,
        confidence=0.5,
        embedding=None,
    )
    # Manually set created_at to old date.
    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE memory SET created_at = ? WHERE content = ?",
            (old_date, "old fact"),
        )
    count = memory.apply_decay()
    assert count >= 1


def test_write_corrections_to_rules_none_eligible(memory, tmp_path):
    asyncio.run(memory.save("low confidence learning", type="learning", confidence=0.3))
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    written = memory.write_corrections_to_rules(rules_dir)
    assert written == []


def test_write_corrections_to_rules_eligible(memory, store, tmp_path):
    store.insert_memory(
        type="learning",
        content="Always personalize the first line",
        source=None,
        experiment_id=None,
        confidence=0.9,
        embedding=None,
    )
    # Set reinforced_by to meet threshold.
    import json

    with store._lock, store._conn:
        store._conn.execute(
            "UPDATE memory SET reinforced_by = ? WHERE content LIKE '%personalize%'",
            (json.dumps(["exp1", "exp2", "exp3"]),),
        )
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    written = memory.write_corrections_to_rules(rules_dir)
    assert len(written) == 1
    assert written[0].exists()
    content = written[0].read_text()
    assert "personalize" in content


def test_replay_run_empty(memory, store):
    result = memory.replay_run("nonexistent-run")
    assert result == []


def test_keyword_score():
    score = _keyword_score("python machine learning", "python is used for machine learning and ai")
    assert score > 0.3


def test_keyword_score_no_overlap():
    score = _keyword_score("xyz abc", "completely different words here")
    assert score == 0.0


def test_cosine_identical():
    import numpy as np

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    assert abs(_cosine(a, b) - 1.0) < 0.001


def test_cosine_orthogonal():
    import numpy as np

    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert abs(_cosine(a, b)) < 0.001


def test_cosine_empty():
    import numpy as np

    a = np.array([])
    b = np.array([])
    assert _cosine(a, b) == 0.0


def test_slugify():
    assert _slugify("Hello World! Test") == "hello-world-test"
    assert _slugify("  spaces  ") == "spaces"
    assert _slugify("CamelCase") == "camelcase"


def test_search_with_type_filter(memory):
    asyncio.run(memory.save("a fact about testing", type="fact"))
    asyncio.run(memory.save("a learning about testing", type="learning"))
    facts = asyncio.run(memory.search("testing", type_filter="fact"))
    assert all(r.type == "fact" for r in facts)


def test_search_with_min_confidence(memory, store):
    store.insert_memory(
        type="fact",
        content="low conf",
        source=None,
        experiment_id=None,
        confidence=0.1,
        embedding=None,
    )
    store.insert_memory(
        type="fact",
        content="high conf",
        source=None,
        experiment_id=None,
        confidence=0.9,
        embedding=None,
    )
    results = asyncio.run(memory.search("conf", min_confidence=0.5))
    assert all(r.confidence >= 0.5 for r in results)
