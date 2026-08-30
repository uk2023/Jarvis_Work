from __future__ import annotations

"""Evidence-driven routing. The router never parses language or calls an LLM."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class CognitiveDecision:
    mode: str
    confidence: float
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    llm_required: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": self.evidence,
            "llm_required": self.llm_required,
        }


class CognitiveRouter:
    """Choose a safe execution/cognition route from structured evidence."""

    VERSION = "0.2.0"

    def __init__(self, minimum_confidence: float = 0.80) -> None:
        self.minimum_confidence = max(0.0, min(1.0, float(minimum_confidence)))

    @staticmethod
    def _count(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, Mapping):
            return len(value)
        if isinstance(value, (str, bytes)):
            return 1 if value else 0
        try:
            return len(value)
        except TypeError:
            return 1

    def decide(
        self,
        *,
        user_input: str,
        context: Optional[Mapping[str, Any]] = None,
        skills: Any = None,
        identity: Any = None,
        goals: Any = None,
        perception: Optional[Mapping[str, Any]] = None,
        explicit_intent: Optional[Mapping[str, Any]] = None,
    ) -> CognitiveDecision:
        """Route only from an input-matched structured perception.

        `explicit_intent` remains as a compatibility input. New callers should
        pass the complete PerceptionResult mapping through `perception`.
        """
        ctx = dict(context or {})
        p = dict(perception or {})
        intent = dict(p.get("intent") or explicit_intent or {})
        p_input = p.get("user_input") or p.get("source_input")
        input_matches = p_input == user_input if p_input is not None else False
        p_confidence = float(p.get("confidence", intent.get("confidence", 0.0)) or 0.0)
        p_confidence = max(0.0, min(1.0, p_confidence))

        memory_count = self._count(ctx.get("recent_experiences"))
        knowledge_count = self._count(ctx.get("relevant_knowledge"))
        graph_count = self._count(ctx.get("graph_relations"))
        skill_count = self._count(skills)
        goal_count = self._count(goals)

        evidence = {
            "memory_matches": memory_count,
            "knowledge_matches": knowledge_count,
            "graph_relations": graph_count,
            "available_skills": skill_count,
            "active_goals": goal_count,
            "structured_intent": bool(intent),
            "perception_source": p.get("source"),
            "perception_confidence": p_confidence,
            "perception_matches_input": input_matches,
            "input_present": bool((user_input or "").strip()),
        }

        usable_perception = bool(intent) and input_matches and p_confidence >= self.minimum_confidence

        if usable_perception and intent.get("requires_confirmation") is True:
            return CognitiveDecision("clarify", 0.95, "The structured intent requires confirmation before action.", evidence, False)

        if usable_perception and skill_count:
            confidence = min(0.99, max(p_confidence, 0.90))
            return CognitiveDecision("tool", confidence, "Perception identified a usable organism capability.", evidence, False)

        if usable_perception and (knowledge_count > 0 or memory_count > 0):
            confidence = min(0.95, max(p_confidence, 0.84))
            return CognitiveDecision("known", confidence, "Perception is supported by stored organism evidence.", evidence, False)

        return CognitiveDecision(
            "llm",
            0.0,
            "No sufficiently confident input-matched deterministic perception is available.",
            evidence,
            True,
        )
