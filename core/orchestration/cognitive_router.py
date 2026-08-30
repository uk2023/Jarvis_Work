from __future__ import annotations

"""
Evidence-driven cognitive routing for JARVIS.

The router deliberately does NOT understand natural language and does NOT
call an LLM. Its job is to answer one narrower orchestration question:

    "Does the organism already have enough usable evidence/capability to
     continue without external language cognition?"

This is the first layer of the long-term architecture in which the LLM is
an optional cognition/voice service rather than the owner of the Brain.

Important design rule:
    No keyword/query hardcoding lives here.

The router consumes structured evidence produced by JARVIS organs. As those
organs become better, the LLM dependency can decrease naturally without
rewriting this router.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional


@dataclass(frozen=True)
class CognitiveDecision:
    """Immutable decision returned to Brain."""

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
    """
    Routes a turn according to organism evidence.

    Supported modes:
        known   -> organism has enough evidence for a deterministic path
        tool    -> a registered capability should handle the turn
        clarify -> evidence conflicts or is insufficient for safe action
        llm     -> language cognition is genuinely required

    The router never generates a response. Brain remains responsible for
    orchestration and execution.
    """

    VERSION = "0.1.0"

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

    @staticmethod
    def _has_callable(value: Any, names: Iterable[str]) -> bool:
        return any(callable(getattr(value, name, None)) for name in names)

    def decide(
        self,
        *,
        user_input: str,
        context: Optional[Mapping[str, Any]] = None,
        skills: Any = None,
        identity: Any = None,
        goals: Any = None,
        explicit_intent: Optional[Mapping[str, Any]] = None,
    ) -> CognitiveDecision:
        """Return an evidence-based routing decision.

        `explicit_intent` is intentionally optional. When a future
        perception/intent organ supplies structured meaning, this router can
        consume it without changing its public contract.
        """
        ctx = dict(context or {})
        intent = dict(explicit_intent or {})

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
            "input_present": bool((user_input or "").strip()),
        }

        # A structured intent plus a registered capability is the strongest
        # current signal that the organism can execute without asking the LLM
        # to interpret the request again.
        if intent and skill_count:
            confidence = 0.90
            return CognitiveDecision(
                mode="tool",
                confidence=confidence,
                reason="Structured intent and an available organism capability are present.",
                evidence=evidence,
                llm_required=False,
            )

        # A strong direct knowledge/memory hit can support a deterministic
        # retrieval path. We deliberately require multiple evidence signals;
        # one fuzzy memory result must not silently become 'truth'.
        if intent and (knowledge_count > 0 or memory_count > 0) and graph_count >= 0:
            confidence = 0.84 if knowledge_count > 0 else 0.81
            return CognitiveDecision(
                mode="known",
                confidence=confidence,
                reason="Structured meaning is available and the organism has supporting stored evidence.",
                evidence=evidence,
                llm_required=False,
            )

        # Conflicting/empty evidence should not trigger an autonomous action.
        # Brain may ask the LLM to interpret the language or ask the user for
        # clarification depending on the eventual intent/evaluator layer.
        if intent.get("requires_confirmation") is True:
            return CognitiveDecision(
                mode="clarify",
                confidence=0.95,
                reason="The structured intent explicitly requires confirmation before action.",
                evidence=evidence,
                llm_required=False,
            )

        return CognitiveDecision(
            mode="llm",
            confidence=0.0,
            reason="Current organism evidence is insufficient for a safe deterministic route.",
            evidence=evidence,
            llm_required=True,
        )
