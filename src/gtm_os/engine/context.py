"""Assemble primitives + experiment state into a system prompt."""

from __future__ import annotations

from collections.abc import Iterable

from ..types import Experiment, Memory, Primitives


def assemble_context(
    primitives: Primitives,
    *,
    agent_name: str = "orchestrator",
    experiment: Experiment | None = None,
    phase: str | None = None,
    relevant_memories: Iterable[Memory] | None = None,
    extra_sections: list[tuple[str, str]] | None = None,
) -> str:
    """Compile the system prompt for one agent call.

    Order (top-down — most important / most stable first):
      1. Agent persona
      2. Brand voice
      3. Global rules
      4. Phase-specific rules
      5. Channel-specific rules (if experiment has a channel)
      6. Current play(s)
      7. Memories (semantic search results)
      8. Experiment state
      9. Tooling note (placeholder — actual tools are passed separately)
    """
    sections: list[str] = []

    # 1. Agent persona
    agent_body = primitives.agents.get(agent_name) or primitives.agents.get("orchestrator", "")
    if agent_body:
        sections.append(_section(f"Agent: {agent_name}", agent_body))

    # 2. Brand
    if primitives.brand.body:
        brand_block = primitives.brand.body
        if primitives.brand.tone:
            brand_block += "\n\n## Tone\n" + _yaml_to_bullets(primitives.brand.tone)
        if primitives.brand.examples:
            brand_block += "\n\n## Example copy\n\n" + "\n\n---\n\n".join(
                primitives.brand.examples[:3]
            )
        sections.append(_section("Brand", brand_block))

    # 3. Global rules
    if primitives.rules.global_rules:
        sections.append(_section("Global Rules", primitives.rules.global_rules))

    # 4. Phase rules
    phase_val = phase or (experiment.phase if experiment else None)
    if phase_val and phase_val in primitives.rules.phase_rules:
        sections.append(
            _section(f"Rules for phase: {phase_val}", primitives.rules.phase_rules[phase_val])
        )

    # 5. Channel rules
    channel = None
    if experiment and isinstance(experiment.config, dict):
        channel = experiment.config.get("channel")
    if channel and channel in primitives.rules.channel_rules:
        sections.append(
            _section(f"Channel rules: {channel}", primitives.rules.channel_rules[channel])
        )

    # 6. Plays
    if experiment and experiment.play_ids:
        for pid in experiment.play_ids:
            play = primitives.plays.get(pid)
            if play:
                sections.append(_section(f"Play: {pid}", play))
    elif primitives.plays:
        # Surface play catalog so the orchestrator knows what's available.
        lines: list[str] = []
        for pid in sorted(primitives.plays.keys()):
            meta = primitives.play_meta.get(pid)
            if meta and meta.description:
                lines.append(f"- **{meta.name}** (`{pid}`, {meta.kind}): {meta.description}")
            else:
                lines.append(f"- `{pid}`")
        listing = "\n".join(lines)
        sections.append(_section("Available plays (use list_plays/get_play tools for details)", listing))

    # 7. Memories
    mem_list = list(relevant_memories or [])
    if mem_list:
        body = "\n\n".join(
            f"- ({m.type}, confidence={m.confidence:.2f}) {m.content}"
            + (f" [from exp {m.experiment_id}]" if m.experiment_id else "")
            for m in mem_list
        )
        sections.append(_section("Relevant memories", body))

    # 8. Experiment state
    if experiment:
        state = (
            f"id: {experiment.id}\n"
            f"name: {experiment.name}\n"
            f"phase: {experiment.phase}\n"
            f"hypothesis: {experiment.hypothesis or '(none yet)'}\n"
            f"plays: {', '.join(experiment.play_ids) or '(none)'}\n"
            f"config: {experiment.config}\n"
            f"tokens used: {experiment.tokens_used} / {experiment.token_budget}"
        )
        sections.append(_section("Current experiment", state))

    # 9. Extra
    if extra_sections:
        for title, body in extra_sections:
            sections.append(_section(title, body))

    sections.append(
        _section(
            "How to act",
            (
                "You are part of an autonomous GTM operating system.\n"
                "- Stay strictly in the voice defined by Brand.\n"
                "- Follow Rules without exception. If a rule blocks an action, surface it.\n"
                "- BIAS TOWARD ACTION. Build the tools and assets you need yourself.\n"
                "  Use available tools to take real action: create experiments,\n"
                "  save memories, schedule next runs, draft copy, build prospect lists.\n"
                "- Composio and Pipedream integrations are available as optional accelerators\n"
                "  for connecting to external services (Gmail, Apollo, Slack, etc.).\n"
                "  Use them when they help, but do not depend on them — work with what you have.\n"
                "- Before the execute phase, always ask for human approval.\n"
                "- Keep responses focused. Prefer concrete next steps over generic prose.\n"
            ),
        )
    )

    return "\n\n".join(sections).strip() + "\n"


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    if not body:
        return ""
    return f"# {title}\n\n{body}"


def _yaml_to_bullets(data: dict, depth: int = 0) -> str:
    out: list[str] = []
    indent = "  " * depth
    for k, v in data.items():
        if isinstance(v, dict):
            out.append(f"{indent}- **{k}**:")
            out.append(_yaml_to_bullets(v, depth + 1))
        elif isinstance(v, list):
            out.append(f"{indent}- **{k}**: " + ", ".join(str(x) for x in v))
        else:
            out.append(f"{indent}- **{k}**: {v}")
    return "\n".join(out)
