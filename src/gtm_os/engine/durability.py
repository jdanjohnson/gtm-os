"""Durable execution — checkpoint/replay for experiment ticks.

Wraps each major step in run_tick() with a ctx.step(name, fn) pattern.
On crash/restart: reload from last checkpoint, skip completed steps.

Reference: Centaur workflow_engine.py WorkflowContext.step(name, fn)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .store import Store

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DurableContext:
    """Checkpoint-aware execution context for a single run."""

    def __init__(self, store: Store, experiment_id: str, run_id: str) -> None:
        self.store = store
        self.experiment_id = experiment_id
        self.run_id = run_id
        self._completed_steps: set[str] = set()
        self._results: dict[str, Any] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        """Load previously completed steps from checkpoint table."""

        # Query checkpoints for this run_id
        with self.store._lock:
            rows = self.store._conn.execute(
                "SELECT step_name, result FROM checkpoints WHERE run_id = ?",
                (self.run_id,),
            ).fetchall()
        for row in rows:
            self._completed_steps.add(row["step_name"])
            import json

            try:
                self._results[row["step_name"]] = json.loads(row["result"])
            except (json.JSONDecodeError, TypeError):
                self._results[row["step_name"]] = row["result"]

    @property
    def completed_steps(self) -> set[str]:
        return self._completed_steps

    def get_result(self, step_name: str) -> Any | None:
        return self._results.get(step_name)

    async def step(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute step with checkpoint. If already completed, return cached result."""
        if name in self._completed_steps:
            logger.debug("step '%s' already checkpointed, skipping", name)
            return self._results[name]

        result = await fn()

        # Serialize result for checkpoint storage
        serializable = _make_serializable(result)
        self.store.save_checkpoint(self.experiment_id, self.run_id, name, serializable)
        self._completed_steps.add(name)
        self._results[name] = serializable
        return result

    def step_sync(self, name: str, fn: Callable[[], T]) -> T:
        """Synchronous variant for steps that don't need async."""
        if name in self._completed_steps:
            logger.debug("step '%s' already checkpointed, skipping", name)
            return self._results[name]

        result = fn()

        serializable = _make_serializable(result)
        self.store.save_checkpoint(self.experiment_id, self.run_id, name, serializable)
        self._completed_steps.add(name)
        self._results[name] = serializable
        return result


def _make_serializable(value: Any) -> Any:
    """Best-effort conversion to JSON-serializable form."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_make_serializable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _make_serializable(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        import dataclasses

        return _make_serializable(dataclasses.asdict(value))
    return str(value)
