from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class SkillLearner:
    """
    Converts repeated, verified successful experiences into auditable
    skill proposals.

    SkillLearner is deliberately proposal-only. It never registers a
    capability and never creates executable code. SkillRegistry remains
    the only executable capability registry.

    The canonical ExperienceEngine shape is accepted directly, while the
    older flat test/fixture shape remains compatible:

        canonical:
            {"action": {...}, "outcome": {...}, "success": True,
             "context": {...}}

        legacy:
            {"action": "...", "status": "success", "detail": "..."}
    """

    VERSION = "0.2.0"

    def __init__(self, min_repetitions: int = 3, min_success_rate: float = 0.8):
        if min_repetitions < 1:
            raise ValueError("min_repetitions must be >= 1")
        if not 0.0 <= min_success_rate <= 1.0:
            raise ValueError("min_success_rate must be between 0 and 1")

        self.min_repetitions = min_repetitions
        self.min_success_rate = min_success_rate
        self._experiences: List[Dict[str, Any]] = []
        self._proposals: Dict[str, Dict[str, Any]] = {}

    # =============================================================
    # OBSERVE
    # =============================================================

    def observe(self, experience: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Record one canonical experience and return newly qualified proposals."""
        if not isinstance(experience, dict):
            raise TypeError("experience must be a dictionary")

        normalized = self._normalize_experience(experience)
        if normalized is None or not normalized["success"]:
            return []

        self._experiences.append(normalized)
        return self.propose(self._experiences)

    # =============================================================
    # PROPOSE
    # =============================================================

    def propose(self, experiences: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Generate proposals from successful, repeatable executable actions."""
        source = self._experiences if experiences is None else experiences
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for raw in source:
            normalized = self._normalize_experience(raw)
            if normalized is None or not normalized["success"]:
                continue
            action = normalized["action"]
            grouped.setdefault(action, []).append(normalized)

        proposals: List[Dict[str, Any]] = []
        for action, group in grouped.items():
            repetitions = len(group)
            if repetitions < self.min_repetitions:
                continue

            # The group contains verified successes only. Keep the
            # denominator explicit so mixed legacy/canonical input remains
            # safe if propose() is called directly with external fixtures.
            all_group = [
                self._normalize_experience(item)
                for item in source
                if self._normalize_experience(item) is not None
                and self._normalize_experience(item)["action"] == action
            ]
            all_group = [item for item in all_group if item is not None]
            success_rate = (
                sum(1 for item in all_group if item["success"]) / len(all_group)
                if all_group
                else 0.0
            )
            if success_rate < self.min_success_rate:
                continue

            name = self._skill_name(action)
            existing = self._proposals.get(name)
            proposal = {
                "name": name,
                "based_on_action": action,
                "repetitions": repetitions,
                "success_rate": round(success_rate, 2),
                "example_detail": group[-1].get("detail", ""),
                "goal": group[-1].get("goal", ""),
                "proposed_at": time.time(),
                "status": existing.get("status", "proposed") if existing else "proposed",
            }
            self._proposals[name] = proposal
            proposals.append(dict(proposal))

        return proposals

    # =============================================================
    # PROPOSAL GOVERNANCE
    # =============================================================

    def list_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        proposals = list(self._proposals.values())
        if status is not None:
            proposals = [p for p in proposals if p.get("status") == status]
        return [dict(p) for p in proposals]

    def approve(self, name: str) -> Dict[str, Any]:
        """Approve a proposal without registering or executing anything."""
        proposal = self._proposals.get(name)
        if proposal is None:
            raise KeyError(f"Unknown skill proposal: {name}")
        proposal["status"] = "approved"
        proposal["approved_at"] = time.time()
        return dict(proposal)

    def reject(self, name: str, reason: str = "") -> Dict[str, Any]:
        """Reject a proposal without mutating SkillRegistry."""
        proposal = self._proposals.get(name)
        if proposal is None:
            raise KeyError(f"Unknown skill proposal: {name}")
        proposal["status"] = "rejected"
        proposal["rejection_reason"] = reason
        proposal["rejected_at"] = time.time()
        return dict(proposal)

    # =============================================================
    # NORMALIZATION
    # =============================================================

    @classmethod
    def _normalize_experience(cls, experience: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = experience.get("action")
        outcome = experience.get("outcome") or {}
        context = experience.get("context") or {}

        # Chat responses are observations, not executable actions.
        if isinstance(action, dict):
            action_name = (
                action.get("skill")
                or action.get("name")
                or action.get("action")
            )
            if not action_name or "jarvis_response" in action:
                return None
            detail = action.get("detail", "")
        else:
            action_name = action
            detail = experience.get("detail", "")

        if not isinstance(action_name, str) or not action_name.strip():
            return None

        if isinstance(outcome, dict):
            explicit_success = outcome.get("success")
            status = outcome.get("status")
        else:
            explicit_success = None
            status = None

        if explicit_success is None and "success" in experience:
            explicit_success = experience.get("success")

        if explicit_success is None:
            status = str(experience.get("status", status) or "").lower()
            success = status in {"success", "completed", "done"}
        else:
            success = bool(explicit_success)

        if not detail and isinstance(outcome, dict):
            detail = outcome.get("detail", "")

        goal = context.get("goal", "") if isinstance(context, dict) else ""
        return {
            "action": action_name.strip(),
            "detail": str(detail or ""),
            "goal": str(goal or ""),
            "success": success,
        }

    @staticmethod
    def _skill_name(action: str) -> str:
        return "skill_" + "".join(
            c if c.isalnum() else "_" for c in action.lower()
        ).strip("_")

    def statistics(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "observed_experiences": len(self._experiences),
            "proposal_count": len(self._proposals),
            "proposed": len(self.list_proposals("proposed")),
            "approved": len(self.list_proposals("approved")),
            "rejected": len(self.list_proposals("rejected")),
            "min_repetitions": self.min_repetitions,
            "min_success_rate": self.min_success_rate,
        }
