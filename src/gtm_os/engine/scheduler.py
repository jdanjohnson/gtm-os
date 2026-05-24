"""Scheduler daemon — polls SQLite for due schedules and runs experiment ticks.

Pattern adapted from PraisonAI's AgentScheduler and Background Agents' SchedulerDO:
- Background thread + asyncio event loop.
- Auto-pause schedule after `max_consecutive_failures`.
- Recovery sweep for orphaned runs (started > 90 min ago, still 'running').
- Optional `max_cost` per schedule.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from croniter import croniter

from ..config import Config
from .experiment import ExperimentRunner
from .store import Store


logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _next_run_at(*, cron_expr: str | None, interval_seconds: int | None) -> str:
    if cron_expr:
        return (
            croniter(cron_expr, _now_utc()).get_next(datetime).astimezone(timezone.utc).isoformat(timespec="seconds")
        )
    seconds = int(interval_seconds or 3600)
    return (_now_utc() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


class Scheduler:
    """Polling scheduler. Run in a background thread with its own event loop."""

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
            except Exception:  # noqa: BLE001
                logger.exception("scheduler tick failed")
            # Sleep responsively.
            for _ in range(max(1, interval)):
                if self._stop.is_set():
                    break
                await asyncio.sleep(1)
        logger.info("scheduler stopped")

    async def _tick(self) -> None:
        # Recovery sweep at most every 15 min.
        if (
            self._recovery_swept_at is None
            or (_now_utc() - self._recovery_swept_at) > timedelta(minutes=15)
        ):
            for orphan in self.store.find_orphan_runs(older_than_minutes=90):
                self.store.finish_run(orphan.id, status="failed", error="orphaned")
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

            if sched.max_cost is not None and sched.cost_spent >= sched.max_cost:
                self.store.update_schedule(sched.id, enabled=False)
                logger.info("schedule %s disabled (cost cap reached)", sched.id)
                continue

            if not sched.experiment_id:
                continue

            outcome = await self.runner.run_tick(sched.experiment_id)
            if outcome.ok:
                self.store.update_schedule(sched.id, consecutive_failures=0)
            else:
                fails = (sched.consecutive_failures or 0) + 1
                fields = {"consecutive_failures": fails}
                if fails >= self.config.scheduler.max_consecutive_failures:
                    fields["enabled"] = False
                    logger.warning(
                        "schedule %s disabled after %d consecutive failures",
                        sched.id,
                        fails,
                    )
                self.store.update_schedule(sched.id, **fields)
