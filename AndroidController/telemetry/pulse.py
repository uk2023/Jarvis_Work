"""Step/state event monitor for AndroidController.

The event schema is designed so a future JARVIS frontend can visualize
observe -> plan -> act -> verify execution without using JARVIS monitor.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass
class PulseEvent:
    type: str
    status: str
    message: str = ""
    step: int | None = None
    action: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time)


class Pulse:
    """In-memory event publisher; transport/persistence will be added later."""

    def __init__(self):
        self.events: list[PulseEvent] = []

    def emit(self, event: PulseEvent) -> PulseEvent:
        self.events.append(event)
        return event
