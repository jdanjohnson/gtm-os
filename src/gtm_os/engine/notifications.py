"""Notification system — fire alerts on key events.

Implements WS3C:
- In-app notifications via system messages
- Slack notifications via Composio (when configured)
- Email notifications via Composio (when configured)
- Fires on: approval needed, failure escalation, high-confidence learning,
  experiment complete, budget threshold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import Config
from .composio_tools import ComposioIntegration
from .store import Store

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    channel: str  # "in_app", "slack", "email"
    message: str
    experiment_id: str | None = None
    event_type: str = "info"  # "approval", "failure", "learning", "complete", "budget"


class NotificationService:
    """Multi-channel notification dispatch."""

    def __init__(
        self,
        *,
        config: Config,
        store: Store,
        composio: ComposioIntegration | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.composio = composio
        # Read notification config from config if available.
        self._slack_channel = getattr(config, "slack_channel", None)
        self._email = getattr(config, "notification_email", None)

    def notify(
        self,
        message: str,
        *,
        experiment_id: str | None = None,
        event_type: str = "info",
    ) -> list[Notification]:
        """Send notification via all configured channels."""
        sent: list[Notification] = []

        # Always save in-app notification as system message.
        self.store.add_message(
            role="system",
            content=f"[NOTIFICATION:{event_type.upper()}] {message}",
            experiment_id=experiment_id,
        )
        sent.append(Notification(
            channel="in_app", message=message,
            experiment_id=experiment_id, event_type=event_type,
        ))

        # Slack via Composio (best effort).
        if self.composio and self.composio.configured and self._slack_channel:
            try:
                # Use Composio's Slack integration if available.
                self.composio.execute_action(
                    "SLACK_SEND_MESSAGE",
                    params={"channel": self._slack_channel, "text": f"🔔 GTM-OS: {message}"},
                )
                sent.append(Notification(
                    channel="slack", message=message,
                    experiment_id=experiment_id, event_type=event_type,
                ))
            except Exception as exc:
                logger.debug("slack notification failed (non-fatal): %s", exc)

        # Email via Composio (best effort).
        if self.composio and self.composio.configured and self._email:
            try:
                self.composio.execute_action(
                    "GMAIL_SEND_EMAIL",
                    params={
                        "to": self._email,
                        "subject": f"GTM-OS: {event_type} — {message[:80]}",
                        "body": message,
                    },
                )
                sent.append(Notification(
                    channel="email", message=message,
                    experiment_id=experiment_id, event_type=event_type,
                ))
            except Exception as exc:
                logger.debug("email notification failed (non-fatal): %s", exc)

        return sent

    # Convenience methods for common events.

    def on_approval_needed(self, experiment_id: str, details: str) -> list[Notification]:
        return self.notify(
            f"Approval needed: {details}",
            experiment_id=experiment_id,
            event_type="approval",
        )

    def on_failure(self, experiment_id: str, error: str, failure_count: int) -> list[Notification]:
        return self.notify(
            f"Experiment failed ({failure_count} consecutive): {error}",
            experiment_id=experiment_id,
            event_type="failure",
        )

    def on_learning(self, experiment_id: str, learning: str) -> list[Notification]:
        return self.notify(
            f"High-confidence learning: {learning[:200]}",
            experiment_id=experiment_id,
            event_type="learning",
        )

    def on_complete(self, experiment_id: str, summary: str) -> list[Notification]:
        return self.notify(
            f"Experiment complete: {summary}",
            experiment_id=experiment_id,
            event_type="complete",
        )

    def on_budget_threshold(self, experiment_id: str, pct_used: float) -> list[Notification]:
        return self.notify(
            f"Budget alert: {pct_used:.0f}% of token budget used",
            experiment_id=experiment_id,
            event_type="budget",
        )

    def on_rule_created(self, experiment_id: str | None, rule_file: str) -> list[Notification]:
        return self.notify(
            f"New rule derived from learnings: {rule_file}",
            experiment_id=experiment_id,
            event_type="learning",
        )
