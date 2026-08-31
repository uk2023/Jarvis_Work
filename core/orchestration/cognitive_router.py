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
        return {"mode": self.mode, "confidence": self.confidence, "reason": self.reason, "evidence": self.evidence, "llm_required": self.llm_required}

class CognitiveRouter:
    """Choose a safe execution/cognition route from structured evidence."""
    VERSION = "0.3.0"
    def __init__(self, minimum_confidence: float = 0.80) -> None:
        self.minimum_confidence = max(0.0, min(1.0, float(minimum_confidence)))
    @staticmethod
    def _count(value: Any) -> int:
        if value is None: return 0
        if isinstance(value, Mapping): return len(value)
        if isinstance(value, (str, bytes)): return 1 if value else 0
        try: return len(value)
        except TypeError: return 1
    def decide(self, *, user_input: str, context: Optional[Mapping[str, Any]] = None, skills: Any = None, identity: Any = None, goals: Any = None, perception: Optional[Mapping[str, Any]] = None, explicit_intent: Optional[Mapping[str, Any]] = None) -> CognitiveDecision:
        """Route only from structured, input-matched perception.

        Hybrid is explicit: perception must request execution_mode=hybrid.
        The router never invents hybrid merely because skills and memory exist.
        """
        ctx = dict(context or {})
        p = dict(perception or {})
        using_compat_intent = not p and explicit_intent is not None
        intent = dict(p.get("intent") or explicit_intent or {})
        p_input = p.get("user_input") or p.get("source_input")
        input_matches = (p_input == user_input) if p_input is not None else using_compat_intent
        p_confidence = float(p.get("confidence", intent.get("confidence", 0.0)) or 0.0)
        if using_compat_intent and "confidence" not in p and "confidence" not in intent: p_confidence = 1.0
        p_confidence = max(0.0, min(1.0, p_confidence))
        memory_count = self._count(ctx.get("recent_experiences"))
        knowledge_count = self._count(ctx.get("relevant_knowledge"))
        graph_count = self._count(ctx.get("graph_relations"))
        skill_count = self._count(skills)
        goal_count = self._count(goals)
        requested_mode = str(intent.get("execution_mode") or intent.get("route") or "").strip().lower()
        evidence = {"memory_matches": memory_count, "knowledge_matches": knowledge_count, "graph_relations": graph_count, "available_skills": skill_count, "active_goals": goal_count, "structured_intent": bool(intent), "perception_source": p.get("source") if p else "explicit_intent", "perception_confidence": p_confidence, "perception_matches_input": input_matches, "input_present": bool((user_input or "").strip()), "requested_execution_mode": requested_mode or None}
        usable = bool(intent) and input_matches and p_confidence >= self.minimum_confidence
        if usable and intent.get("requires_confirmation") is True:
            return CognitiveDecision("clarify", 0.95, "The structured intent requires confirmation before action.", evidence, False)
        if usable and requested_mode == "hybrid":
            if skill_count and intent.get("skill"):
                return CognitiveDecision("hybrid", min(0.99, max(p_confidence, 0.90)), "Perception explicitly requested native capability execution with LLM synthesis.", evidence, True)
            return CognitiveDecision("llm", p_confidence, "Hybrid was requested but no usable native skill was identified; falling back to LLM cognition.", evidence, True)
        if usable and skill_count:
            return CognitiveDecision("tool", min(0.99, max(p_confidence, 0.90)), "Perception identified a usable organism capability.", evidence, False)
        if usable and (knowledge_count > 0 or memory_count > 0):
            return CognitiveDecision("known", min(0.95, max(p_confidence, 0.84)), "Perception is supported by stored organism evidence.", evidence, False)
        return CognitiveDecision("llm", 0.0, "No sufficiently confident input-matched deterministic perception is available.", evidence, True)
