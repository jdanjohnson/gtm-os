from pathlib import Path

from gtm_os.engine.context import assemble_context
from gtm_os.engine.loader import load_primitives, primitives_exist
from gtm_os.types import Experiment


def test_primitives_load(primitives_tree: Path):
    prim = load_primitives(primitives_tree)
    assert primitives_exist(primitives_tree)
    assert "orchestrator" in prim.agents
    assert "researcher" in prim.agents
    assert "demo" in prim.plays
    assert prim.brand.body.startswith("# Brand")
    assert prim.brand.tone.get("voice") == ["direct", "warm"]
    assert "design" in prim.rules.phase_rules
    assert "email" in prim.rules.channel_rules
    assert prim.triggers.schedules["templates"]["daily"]["cron_expr"] == "0 9 * * *"


def test_assemble_context_includes_play_and_rules(primitives_tree: Path):
    prim = load_primitives(primitives_tree)
    exp = Experiment(
        id="x",
        name="t",
        phase="design",
        play_ids=["demo"],
        config={"channel": "email"},
    )
    ctx = assemble_context(prim, agent_name="researcher", experiment=exp)
    assert "Researcher" in ctx
    assert "Brand" in ctx
    assert "Rules" in ctx
    assert "Demo play" in ctx
    assert "email rules" in ctx
    assert "Current experiment" in ctx
    assert "How to act" in ctx


def test_assemble_context_handles_missing_experiment(primitives_tree: Path):
    prim = load_primitives(primitives_tree)
    ctx = assemble_context(prim, agent_name="orchestrator")
    assert "Orchestrator" in ctx
    assert "Available plays" in ctx
