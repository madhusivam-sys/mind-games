from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class BrokerIntent:
    """Placeholder broker intent for a future execution boundary."""

    symbol: str
    action: str
    quantity: int


class BrokerClient(Protocol):
    """Execution boundary kept out of the MVP runtime path."""

    def submit(self, intent: BrokerIntent) -> str:
        """Return a broker acknowledgement identifier."""


class NullBrokerClient:
    """No-op broker client to make the boundary explicit."""

    def submit(self, intent: BrokerIntent) -> str:
        raise NotImplementedError("Execution is intentionally out of scope for Bazaar Mind Games.")
