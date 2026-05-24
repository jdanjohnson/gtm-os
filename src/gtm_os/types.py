"""Shared dataclasses and typed structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["user", "assistant", "system", "tool"]
ExperimentPhase = Literal[
    "design",
    "build",
    "execute",
    "measure",
    "learn",
    "complete",
    "paused",
]
MemoryType = Literal["fact", "learning", "preference", "rule"]


@dataclass
class BrandConfig:
    """Brand voice + tone + examples loaded from primitives/brand/."""

    body: str = ""
    tone: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)


@dataclass
class RulesConfig:
    """Rules loaded from primitives/rules/."""

    global_rules: str = ""
    phase_rules: dict[str, str] = field(default_factory=dict)
    channel_rules: dict[str, str] = field(default_factory=dict)


@dataclass
class TriggersConfig:
    """Triggers loaded from primitives/triggers/."""

    schedules: dict[str, Any] = field(default_factory=dict)
    on_phase_change: dict[str, Any] = field(default_factory=dict)


@dataclass
class Primitives:
    """All primitives loaded from disk."""

    brand: BrandConfig = field(default_factory=BrandConfig)
    agents: dict[str, str] = field(default_factory=dict)
    rules: RulesConfig = field(default_factory=RulesConfig)
    plays: dict[str, str] = field(default_factory=dict)
    memory_files: list[str] = field(default_factory=list)
    triggers: TriggersConfig = field(default_factory=TriggersConfig)
    base_path: str = ""


@dataclass
class Experiment:
    id: str
    name: str
    description: str | None = None
    hypothesis: str | None = None
    phase: ExperimentPhase = "design"
    play_ids: list[str] = field(default_factory=list)
    current_agent: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    schedule_id: str | None = None
    token_budget: int = 200_000
    tokens_used: int = 0
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Run:
    id: str
    experiment_id: str
    phase: str
    status: str = "pending"
    input_context: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    tools_used: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None


@dataclass
class Memory:
    id: str
    type: MemoryType
    content: str
    source: str | None = None
    experiment_id: str | None = None
    confidence: float = 0.5
    reinforced_by: list[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    similarity: float | None = None


@dataclass
class Schedule:
    id: str
    experiment_id: str | None
    type: str
    cron_expr: str | None
    interval_seconds: int | None
    next_run_at: str
    last_run_at: str | None = None
    enabled: bool = True
    consecutive_failures: int = 0
    max_cost: float | None = None
    cost_spent: float = 0.0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Tool:
    """Tool callable by an agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Any  # async callable


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    result: Any
    error: str | None = None


@dataclass
class AgentMessage:
    """One message in an agent's conversation."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class AgentResult:
    """Outcome of a single run of the agent loop."""

    message: AgentMessage
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    iterations: int = 0
    tokens_used: int = 0
    finished: bool = True
    error: str | None = None
