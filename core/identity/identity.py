from __future__ import annotations

from copy import deepcopy
from time import time
from typing import Any, Dict, Optional


class Identity:
    """Layered identity state for the JARVIS organism.

    Layer 1 (core): stable organism invariants.
    Layer 2 (adaptive): mutable self-model derived from validated runtime state.
    Layer 3 (autobiographical): durable identity-relevant history supplied by
    the organism's memory/evolution boundaries.

    Core identity is intentionally stable. Adaptive and autobiographical state
    may evolve, but this class does not grant either layer authority to bypass
    learning, validation, approval, or evolution boundaries.
    """

    # Stable identity invariants; these are identity constants, not learned
    # application intelligence.
    NAME = "JARVIS"
    VERSION = "0.3.0"
    DESIGNATION = "Modular Cognitive Organism"
    CREATOR = "UK"
    PURPOSE = (
        "To evolve autonomously, learn from experiences, "
        "and assist intelligently while maintaining internal consistency."
    )

    def __init__(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        adaptive_state: Optional[Dict[str, Any]] = None,
        autobiographical_history: Optional[list] = None,
    ):
        self.metadata = deepcopy(metadata or {})
        self.adaptive_state: Dict[str, Any] = deepcopy(adaptive_state or {})
        self.autobiographical_history = list(autobiographical_history or [])

    def get_core(self) -> Dict[str, Any]:
        """Return stable identity invariants."""
        return {
            "name": self.NAME,
            "version": self.VERSION,
            "designation": self.DESIGNATION,
            "creator": self.CREATOR,
            "purpose": self.PURPOSE,
        }

    def update_adaptive(self, **changes: Any) -> Dict[str, Any]:
        """Update the mutable self-model from an authorized caller."""
        self.adaptive_state.update(changes)
        return deepcopy(self.adaptive_state)

    def record_autobiographical_event(
        self,
        event_type: str,
        evidence: Any = None,
        source: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Record identity-relevant history without declaring it learned truth."""
        if not event_type:
            raise ValueError("event_type cannot be empty.")
        event = {
            "event_type": event_type,
            "evidence": evidence,
            "source": source,
            "timestamp": time() if timestamp is None else timestamp,
        }
        self.autobiographical_history.append(event)
        return deepcopy(event)

    def set_metadata(self, key: str, value: Any) -> None:
        if not key:
            raise ValueError("metadata key cannot be empty.")
        self.metadata[key] = value

    def get_profile(self) -> Dict[str, Any]:
        """Return the complete three-layer identity profile."""
        return {
            "core": self.get_core(),
            "adaptive": deepcopy(self.adaptive_state),
            "autobiographical": deepcopy(self.autobiographical_history),
            "metadata": deepcopy(self.metadata),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Serializable identity snapshot for organism state/status."""
        return self.get_profile()
