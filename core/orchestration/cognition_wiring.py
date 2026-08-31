from __future__ import annotations

"""Canonical perception -> cognition routing adapter used by Brain runtime paths."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .cognitive_router import CognitiveDecision, CognitiveRouter
from .perception import PerceptionEngine, PerceptionResult


@dataclass(frozen=True)
class CognitionPass:
    """One deterministic cognition pass: perceive once, then route that result."""

    perception: PerceptionResult
    decision: CognitiveDecision
    context: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "perception": self.perception.as_dict(),
            "cognitive_route": self.decision.as_dict(),
            "context": self.context,
        }


class CognitionWiring:
    """Own the canonical Perception -> CognitiveRouter contract.

    This adapter deliberately contains no LLM call and no skill execution.
    It only prepares the evidence contract and asks CognitiveRouter for a
    decision. Execution remains the responsibility of the Brain/Executor.
    """

    VERSION = "0.1.0"

    def __init__(
        self,
        *,
        perception: PerceptionEngine,
        router: CognitiveRouter,
        memory: Any = None,
        goal_manager: Any = None,
        skill_registry: Any = None,
        state: Any = None,
    ) -> None:
        self.perception = perception
        self.router = router
        self.memory = memory
        self.goal_manager = goal_manager
        self.skill_registry = skill_registry
        self.state = state
        self.last_pass: Optional[CognitionPass] = None

    def run(self, user_input: str) -> CognitionPass:
        """Run exactly one perception + routing pass for the current input."""
        context = self._build_context(user_input)
        perception = self.perception.perceive(user_input, context=context)

        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]

        skills = getattr(self.skill_registry, "skills", None)
        decision = self.router.decide(
            user_input=user_input,
            context=context,
            skills=skills,
            identity=None,
            goals=goals,
            perception=perception.as_dict(),
        )

        result = CognitionPass(
            perception=perception,
            decision=decision,
            context=context,
        )
        self.last_pass = result
        self._publish_state(result)
        return result

    def _build_context(self, user_input: str) -> Dict[str, Any]:
        if self.memory is None:
            return {
                "recent_experiences": [],
                "relevant_knowledge": [],
                "graph_relations": [],
            }
        try:
            return dict(self.memory.build_context(query=user_input, recent_limit=3))
        except Exception:
            # Cognition must remain available if retrieval is temporarily down.
            return {
                "recent_experiences": [],
                "relevant_knowledge": [],
                "graph_relations": [],
            }

    def _publish_state(self, result: CognitionPass) -> None:
        if self.state is None:
            return
        try:
            self.state.update(
                last_perception=result.perception.as_dict(),
                last_route=result.decision.mode,
                confidence=result.decision.confidence,
                uncertainty=1.0 - result.decision.confidence,
            )
        except Exception:
            pass
