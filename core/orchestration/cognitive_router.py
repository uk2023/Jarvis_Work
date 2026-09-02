from __future__ import annotations

import json
import os
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
    """Evidence-driven route authority. It consumes Cognition output only."""

    VERSION = "0.6.0"

    def __init__(self, minimum_confidence: Optional[float] = None) -> None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(root, "config", "cognition.json")
        configured = None
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                configured = json.load(handle).get("routing", {}).get("minimum_confidence")
        except (OSError, ValueError, AttributeError):
            pass
        value = minimum_confidence if minimum_confidence is not None else configured
        if value is None:
            raise RuntimeError("Cognitive routing policy is not configured")
        self.minimum_confidence = max(0.0, min(1.0, float(value)))

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
        cognition_input: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        skills: Any = None,
        identity: Any = None,
        goals: Any = None,
        perception: Optional[Mapping[str, Any]] = None,
        explicit_intent: Optional[Mapping[str, Any]] = None,
    ) -> CognitiveDecision:
        """Choose execution from the canonical Cognition contract.

        ``cognition_input`` is the authoritative runtime path. The older
        perception/explicit_intent arguments remain compatibility inputs for
        non-blueprint callers and are not used when canonical Cognition data
        is supplied.
        """
        if cognition_input is not None:
            c = dict(cognition_input)
            semantic = dict(c.get("semantic") or {})
            intent = dict(semantic.get("intent") or {})
            memory_context = dict(c.get("memory") or {})
            knowledge_context = dict(c.get("knowledge") or {})
            state_context = dict(c.get("state") or {})
            capability_context = c.get("capabilities") or {}
            available_skills = capability_context.get("skills") if isinstance(capability_context, Mapping) else capability_context
            available_skills = available_skills or skills
            active_goals = c.get("goals") or goals
            perceived_goal = semantic.get("goal") or intent.get("goal")
            confidence = float(semantic.get("confidence", 0.0) or 0.0)
            normalized_text = semantic.get("normalized_text") or user_input
            evidence_source = "cognition"
            ctx = {**memory_context, **knowledge_context}
            if state_context:
                ctx["state"] = state_context
        else:
            p = dict(perception or {})
            intent = dict(p.get("intent") or explicit_intent or {})
            p_input = p.get("user_input") or p.get("source_input")
            input_matches = (p_input == user_input) if p_input is not None else explicit_intent is not None
            confidence = float(p.get("confidence", intent.get("confidence", 0.0)) or 0.0)
            if explicit_intent is not None and "confidence" not in p and "confidence" not in intent:
                confidence = 1.0
            confidence = max(0.0, min(1.0, confidence))
            ctx = dict(context or {})
            available_skills = skills
            active_goals = goals
            perceived_goal = p.get("goal")
            normalized_text = p.get("normalized_text") or user_input
            evidence_source = "compatibility"
            if not input_matches:
                confidence = 0.0

        confidence = max(0.0, min(1.0, confidence))
        memory_count = self._count(ctx.get("recent_experiences"))
        knowledge_count = self._count(ctx.get("relevant_knowledge"))
        graph_count = self._count(ctx.get("graph_relations"))
        skill_count = self._count(available_skills)
        goal_count = self._count(active_goals)
        requested_mode = str(intent.get("execution_mode") or intent.get("route") or "").strip().lower()
        evidence = {
            "memory_matches": memory_count,
            "knowledge_matches": knowledge_count,
            "graph_relations": graph_count,
            "available_skills": skill_count,
            "active_goals": goal_count,
            "structured_intent": bool(intent),
            "semantic_source": evidence_source,
            "semantic_confidence": confidence,
            "input_present": bool((normalized_text or "").strip()),
            "requested_execution_mode": requested_mode or None,
            "perceived_goal": perceived_goal,
        }
        usable = bool(intent) and confidence >= self.minimum_confidence
        if usable and intent.get("requires_confirmation") is True:
            return CognitiveDecision("clarify", confidence, "Cognition requires confirmation before action.", evidence, False)
        if usable and perceived_goal:
            return CognitiveDecision("goal", confidence, "Cognition identified an explicit user goal.", evidence, False)
        if usable and requested_mode == "hybrid":
            if skill_count and intent.get("skill"):
                return CognitiveDecision("hybrid", confidence, "Cognition selected hybrid execution with an available native capability.", evidence, True)
            return CognitiveDecision("llm", confidence, "Hybrid was requested but no usable native capability is available; using LLM fallback cognition.", evidence, True)
        if usable and skill_count:
            return CognitiveDecision("tool", confidence, "Cognition identified a usable organism capability.", evidence, False)
        if usable and (knowledge_count > 0 or memory_count > 0):
            return CognitiveDecision("known", confidence, "Cognition has sufficient stored organism evidence for a native answer.", evidence, False)
        return CognitiveDecision("llm", confidence, "Cognition has no sufficiently confident deterministic route; using LLM fallback cognition.", evidence, True)
