"""Scheduler daemon — polls SQLite for due schedules and runs experiment ticks.

Implements WS2A:
- Exponential backoff on retry (1min → 2min → 4min → max 30min)
- Per-run cost estimation (tokens x model price)
- cost_spent updated after each run, auto-pause when max_cost reached
- Escalation stages: (1) retry with different prompt, (2) notify, (3) pause
- Recovery sweep for orphaned runs and zombied schedules
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime, timedelta

from croniter import croniter

from ..config import Config
from .experiment import ExperimentRunner, RunOutcome
from .store import Store

logger = logging.getLogger(__name__)

# Cost per 1K tokens (approximate) — used for budget tracking.
MODEL_COST_PER_1K: dict[str, float] = {
    "openai/gpt-4o-mini": 0.00015,
    "openai/gpt-4o": 0.005,
    "anthropic/claude-3-5-sonnet-20241022": 0.003,
    "anthropic/claude-3-haiku-20240307": 0.00025,
    "ollama/": 0.0,
}

# Backoff schedule: attempt → delay in seconds.
BACKOFF_DELAYS = [60, 120, 240, 480, 960, 1800]  # max 30 min


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _next_run_at(*, cron_expr: str | None, interval_seconds: int | None) -> str:
    if cron_expr:
        return (
            croniter(cron_expr, _now_utc())
            .get_next(datetime)
            .astimezone(UTC)
            .isoformat(timespec="seconds")
        )
    seconds = int(interval_seconds or 3600)
    return (_now_utc() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _backoff_delay(failure_count: int) -> int:
    """Exponential backoff with ceiling."""
    idx = min(failure_count, len(BACKOFF_DELAYS) - 1)
    return BACKOFF_DELAYS[idx]


def _estimate_cost(tokens: int, model: str) -> float:
    """Estimate cost of a run based on token count and model."""
    for prefix, cost in MODEL_COST_PER_1K.items():
        if model.startswith(prefix):
            return (tokens / 1000.0) * cost
    return (tokens / 1000.0) * 0.001  # default conservative estimate


class Scheduler:
    """Polling scheduler with retry, escalation, and cost tracking."""

    def __init__(
        self,
        *,
        config: Config,
        store: Store,
        runner: ExperimentRunner,
    ) -> None:
        self.config = config
        self.store = store
        self.runner = runner
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._recovery_swept_at: datetime | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_thread, name="gtm-os-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._poll_loop())
        finally:
            self._loop.close()

    async def _poll_loop(self) -> None:
        interval = self.config.scheduler.poll_interval_seconds
        logger.info("scheduler started (poll every %ss)", interval)
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("scheduler tick failed")
            for _ in range(max(1, interval)):
                if self._stop.is_set():
                    break
                await asyncio.sleep(1)
        logger.info("scheduler stopped")

    async def _tick(self) -> None:
        # Recovery sweep at most every 15 min — includes zombied schedules.
        if self._recovery_swept_at is None or (_now_utc() - self._recovery_swept_at) > timedelta(
            minutes=15
        ):
            self._recovery_sweep()
            self._recovery_swept_at = _now_utc()

        due = self.store.due_schedules()
        if not due:
            return
        for sched in due:
            # Claim it by moving next_run_at forward immediately.
            new_next = _next_run_at(
                cron_expr=sched.cron_expr, interval_seconds=sched.interval_seconds
            )
            self.store.update_schedule(
                sched.id,
                next_run_at=new_next,
                last_run_at=_now_utc().isoformat(timespec="seconds"),
            )

            # Cost cap check.
            if sched.max_cost is not None and sched.cost_spent >= sched.max_cost:
                self.store.update_schedule(sched.id, enabled=False)
                logger.info(
                    "schedule %s disabled (cost cap reached: $%.4f)", sched.id, sched.cost_spent
                )
                continue

            if not sched.experiment_id:
                continue

            outcome = await self.runner.run_tick(sched.experiment_id)

            # Update cost tracking.
            if outcome.tokens_used > 0:
                run_cost = _estimate_cost(outcome.tokens_used, self.config.llm.model)
                new_cost_spent = sched.cost_spent + run_cost
                self.store.update_schedule(sched.id, cost_spent=new_cost_spent)

                # Check if we just exceeded cost cap.
                if sched.max_cost is not None and new_cost_spent >= sched.max_cost:
                    self.store.update_schedule(sched.id, enabled=False)
                    logger.info(
                        "schedule %s disabled mid-run (cost cap $%.4f reached)",
                        sched.id,
                        sched.max_cost,
                    )

            if outcome.ok:
                self.store.update_schedule(sched.id, consecutive_failures=0)
            else:
                fails = (sched.consecutive_failures or 0) + 1
                self._handle_failure(sched.id, fails, outcome)

    def _handle_failure(self, schedule_id: str, failure_count: int, outcome: RunOutcome) -> None:
        """Escalation stages on failure (WS2A)."""
        max_failures = self.config.scheduler.max_consecutive_failures

        if failure_count >= max_failures:
            # Stage 3: Disable after max consecutive failures.
            self.store.update_schedule(
                schedule_id, consecutive_failures=failure_count, enabled=False
            )
            logger.warning(
                "schedule %s disabled after %d consecutive failures (escalation stage 3)",
                schedule_id,
                failure_count,
            )
            # Notify via memory/message if experiment is available.
            sched = self.store.get_schedule(schedule_id)
            if sched and sched.experiment_id:
                self.store.add_message(
                    role="system",
                    content=(
                        f"[ESCALATION] Schedule {schedule_id} disabled after {failure_count} "
                        f"failures. Last error: {outcome.error or 'unknown'}. "
                        "Manual intervention required."
                    ),
                    experiment_id=sched.experiment_id,
                )
        elif failure_count == max_failures - 1:
            # Stage 2: Notify but keep running.
            self.store.update_schedule(schedule_id, consecutive_failures=failure_count)
            sched = self.store.get_schedule(schedule_id)
            if sched and sched.experiment_id:
                self.store.add_message(
                    role="system",
                    content=(
                        f"[WARNING] Schedule {schedule_id} has failed {failure_count} times. "
                        f"One more failure will disable it. Last error: {outcome.error or 'unknown'}"
                    ),
                    experiment_id=sched.experiment_id,
                )
            logger.warning(
                "schedule %s at escalation stage 2 (%d failures)",
                schedule_id,
                failure_count,
            )
        else:
            # Stage 1: Retry with backoff.
            delay = _backoff_delay(failure_count)
            backoff_next = (_now_utc() + timedelta(seconds=delay)).isoformat(timespec="seconds")
            self.store.update_schedule(
                schedule_id, consecutive_failures=failure_count, next_run_at=backoff_next
            )
            logger.info(
                "schedule %s: retry #%d with %ds backoff",
                schedule_id,
                failure_count,
                delay,
            )

    def _recovery_sweep(self) -> None:
        """Recover orphaned runs and zombied schedules."""
        # Orphaned runs (running > 90 min).
        for orphan in self.store.find_orphan_runs(older_than_minutes=90):
            self.store.finish_run(orphan.id, status="failed", error="orphaned")
            logger.info("recovered orphaned run %s", orphan.id)

        # Zombied schedules: enabled but next_run_at is way in the past (>24h).
        all_enabled = self.store.list_schedules(only_enabled=True)
        cutoff = (_now_utc() - timedelta(hours=24)).isoformat(timespec="seconds")
        for sched in all_enabled:
            if sched.next_run_at < cutoff:
                # Reset next_run_at to now to un-zombie.
                new_next = _next_run_at(
                    cron_expr=sched.cron_expr, interval_seconds=sched.interval_seconds
                )
                self.store.update_schedule(sched.id, next_run_at=new_next)
                logger.info("recovered zombied schedule %s", sched.id)
