from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AlertMessage:
    """Outbound alert payload placeholder."""

    category: str
    message: str
    symbol: str


class AlertsClient(Protocol):
    """Contract for alert delivery integrations."""

    def publish(self, alert: AlertMessage) -> None:
        """Deliver an alert to an external sink."""


class NullAlertsClient:
    """No-op alert transport for local development."""

    def publish(self, alert: AlertMessage) -> None:
        return None
