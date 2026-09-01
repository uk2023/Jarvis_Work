from __future__ import annotations

from typing import Any, Dict


class RuntimeEvolutionAdapter:
    """
    First concrete Phase 4 evolution adapter.

    This adapter is intentionally narrow: it does not edit source code,
    import arbitrary modules, or accept executable instructions from a
    proposal. It records the approved runtime evolution as an organism
    event and returns a small, serializable handoff that the next cycle
    can observe through the evolution engine's last_execution state.
    """

    TARGET = "organism_runtime"
    VERSION = "0.1.0"

    def __init__(self, state=None):
        self.state = state

    def __call__(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(proposal, dict):
            raise TypeError("Evolution proposal must be a dictionary.")

        target = str(proposal.get("target") or "")
        if target != self.TARGET:
            raise PermissionError(
                f"RuntimeEvolutionAdapter only accepts target: {self.TARGET}"
            )

        proposal_id = str(proposal.get("id") or "")
        if not proposal_id:
            raise ValueError("Evolution proposal id is required.")

        handoff = {
            "adapter": self.__class__.__name__,
            "adapter_version": self.VERSION,
            "proposal_id": proposal_id,
            "target": self.TARGET,
            "next_cycle_ready": True,
        }

        if self.state is not None:
            record_event = getattr(self.state, "record_event", None)
            if callable(record_event):
                record_event(
                    "EVOLUTION_RUNTIME_APPLIED",
                    handoff,
                    source="runtime_evolution_adapter",
                )

        return handoff
