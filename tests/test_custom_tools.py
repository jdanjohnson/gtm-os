
import pytest

from gtm_os.config import LLMConfig
from gtm_os.engine.composio_tools import ComposioIntegration
from gtm_os.engine.custom_tools import build_custom_tools
from gtm_os.engine.memory import VectorMemory
from gtm_os.engine.store import Store


@pytest.mark.asyncio
async def test_create_and_update_experiment(store: Store):
    memory = VectorMemory(store, LLMConfig(embedding_model=""))
    tools = build_custom_tools(store=store, memory=memory, play_ids=["demo"])
    by_name = {t.name: t for t in tools}

    create = by_name["create_experiment"]
    result = await create.execute(
        name="alpha", hypothesis="works", play_ids=["demo"], channel="email"
    )
    assert result["ok"]
    exp_id = result["experiment_id"]

    listed = await by_name["list_experiments"].execute()
    assert any(e["id"] == exp_id for e in listed["experiments"])

    transitioned = await by_name["transition_phase"].execute(
        experiment_id=exp_id, new_phase="build", reason="design done"
    )
    assert transitioned["ok"]
    assert transitioned["phase"] == "build"

    # memory_save round-trip
    saved = await by_name["memory_save"].execute(
        content="our segments respond to 'missed renewals' framing", type="learning"
    )
    assert saved["ok"]
    found = await by_name["memory_search"].execute(query="missed renewals")
    assert any("missed renewals" in r["content"] for r in found["results"])


@pytest.mark.asyncio
async def test_schedule_task(store: Store):
    memory = VectorMemory(store, LLMConfig(embedding_model=""))
    tools = build_custom_tools(store=store, memory=memory, play_ids=[])
    by_name = {t.name: t for t in tools}
    exp = store.create_experiment(name="sched")
    out = await by_name["schedule_task"].execute(
        experiment_id=exp.id, cron_expr="0 9 * * *"
    )
    assert out["ok"]
    assert out["schedule_id"]


@pytest.mark.asyncio
async def test_request_approval_pauses(store: Store):
    memory = VectorMemory(store, LLMConfig(embedding_model=""))
    tools = build_custom_tools(store=store, memory=memory, play_ids=[])
    by_name = {t.name: t for t in tools}
    exp = store.create_experiment(name="appr")
    out = await by_name["request_approval"].execute(
        experiment_id=exp.id, message="ok to send?"
    )
    assert out["phase"] == "paused"
    refreshed = store.get_experiment(exp.id)
    assert refreshed.phase == "paused"


@pytest.mark.asyncio
async def test_composio_not_configured_path():
    composio = ComposioIntegration(api_key=None)
    assert composio.configured is False
    results = await composio.discover_tools("send email")
    assert results and results[0].get("error") == "composio_not_configured"
    out = await composio.execute_action("GMAIL_SEND_EMAIL", {"to": "x"})
    assert out["ok"] is False
