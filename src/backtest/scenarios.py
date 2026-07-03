from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScenarioConfig:
    target_multiple: float = 1.5
    stop_multiple: float = 1.0
