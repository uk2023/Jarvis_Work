from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Optional

from ..contracts import validate_input, validate_output
from ..cognition.semantic_understanding import SemanticUnderstanding
from .brain import Brain


class BlueprintBrain(Brain):
    """The actual runtime Brain; contracts are enforced at live boundaries.

    This replaces the old ContractEnforcedBlueprintBrain proxy. The Brain
    itself owns the Perception -> Semantic Understanding -> Cognition ->
    Router -> Response -> Experience/Learning orchestration boundary.
    """

    VERSION = "1.2.0"

    _SEMANTIC_FALLBACK_PROMPT = (
        "You are JARVIS semantic understanding fallback. Return ONLY JSON. "
        "Do not answer the user and do not invent external facts. "
        'Shape: {"semantic":{"normalized":"...","intent":{},"entities":[],'
        '"relations":[],"events":[],"references":[],"confidence":0.0,'
        '"provenance":{"source":"llm_fallback"},"inferences":[],"unknowns":[]}}'
    )

    def __init__(self, *args, semantic_understanding: Optional[SemanticUnderstanding] = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.semantic_understanding = semantic_understanding or SemanticUnderstanding(
            semantic_memory=getattr(self.memory, "semantic", None)
        )
        self.last_contracts: Dict[str, Dict[str, Any]] = {}
        self.last_cognition_output = None
        self.last_router_input = None
        self.last_router_output = None
        self.last_brain_input = None
        self.last_brain_output = None
        self.last_experience_input = None
        self.last_experience_output = None
        self.last_learning_input = None
        self.last_learning_output = None
        self.last_memory_input = None
        self.last_memory_output = None
        self.last_self_evaluation_input = None
        self.last_self_evaluation_output = None
        self._configure_semantic_fallback()

    def _configure_semantic_fallback(self) -> None:
        boundary = getattr(self.semantic_understanding, "learning_boundary", None)
        if boundary is None:
            return
        boundary.learning = self.learning
        if self.llm is None:
            return

        def fallback(request: Dict[str, Any]) -> Mapping[str, Any]:
            raw = self.llm.generate_response(
                system_prompt=self._SEMANTIC_FALLBACK_PROMPT,
                user_input=str(request.get("text", "")),
                max_tokens=512,
                temperature=0.1,
            )
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw).strip(), flags=re.I | re.S).strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                start, end = text.find("{"), text.rfind("}")
                if start < 0 or end <= start:
                    raise ValueError("LLM semantic fallback did not return JSON")
                payload = json.loads(text[start:end + 1])
            if not isinstance(payload, dict):
                raise TypeError("LLM semantic fallback JSON must be an object")
            semantic = payload.get("semantic", payload)
            if not isinstance(semantic, dict):
                raise TypeError("LLM semantic fallback semantic field must be an object")
            semantic.setdefault("normalized", request.get("text", ""))
            semantic.setdefault("intent", {})
            semantic.setdefault("entities", [])
            semantic.setdefault("relations", [])
            semantic.setdefault("events", [])
            semantic.setdefault("references", [])
            semantic.setdefault("confidence", 0.0)
            semantic.setdefault("provenance", {"source": "llm_fallback"})
            semantic.setdefault("inferences", [])
            semantic.setdefault("unknowns", [])
            return {"semantic": semantic}

        boundary.llm_fallback = fallback

    def _perceive(self, user_input: str) -> Dict[str, Any]:
        perception_input = validate_input("perception", {"raw_input": str(user_input)})
        context = self.build_context(query=perception_input["raw_input"], recent_limit=3) if self.memory is not None else {}
        result = self.perception.perceive(perception_input["raw_input"], context=context)
        perception_output = validate_output("perception", result.as_contract_payload())
        semantic_input = validate_input("semantic_understanding", {
            "perception": perception_output,
            "user_input": perception_input["raw_input"],
            "semantic_context": context,
        })
        integrated = self.semantic_understanding.understand(
            semantic_input["perception"]["normalized_input"],
            context=semantic_input["semantic_context"],
            retrieve=True,
        )
        semantic = dict(integrated.get("semantic") or {})
        intent = semantic.get("intent") if isinstance(semantic.get("intent"), dict) else {}
        semantic_output = validate_output("semantic_understanding", {
            "normalized_text": str(semantic.get("normalized", perception_output["normalized_input"])),
            "intent": intent,
            "entities": list(semantic.get("entities") or []),
            "relations": list(integrated.get("relations") or semantic.get("relations") or []),
            "events": list(semantic.get("events") or []),
            "references": list(semantic.get("references") or []),
            "confidence": float(semantic.get("confidence", 0.0) or 0.0),
            "provenance": dict(semantic.get("provenance") or {"source": "native"}),
            "inferences": list(semantic.get("inferences") or []),
            "unknowns": list(semantic.get("unknowns") or []),
        })
        enriched = result.as_dict()
        semantic_intent = semantic_output["intent"] if isinstance(semantic_output["intent"], dict) else {}
        enriched.update({
            "normalized_text": semantic_output["normalized_text"],
            "intent": semantic_intent,
            "entities": semantic_output["entities"],
            "goal": semantic.get("goal") or semantic_intent.get("goal"),
            "language": perception_output["language"],
            "confidence": semantic_output["confidence"],
            "uncertainty": 1.0 - semantic_output["confidence"],
            "semantic_understanding": semantic_output,
            "semantic_evidence": integrated.get("evidence", {}),
            "semantic_learning": integrated.get("learning", {}),
        })
        self.last_perception = enriched
        self.last_contracts.update({
            "perception.input": perception_input,
            "perception.output": perception_output,
            "semantic_understanding.input": semantic_input,
            "semantic_understanding.output": semantic_output,
        })
        return enriched

    def _build_cognition_input(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        semantic = dict(perception.get("semantic_understanding") or {})
        if not semantic:
            raise RuntimeError("Semantic Understanding result is required before Cognition")
        context = self.build_context(query=semantic.get("normalized_text") or user_input, recent_limit=3)
        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]
        state = {}
        if self.state is not None:
            snapshot = getattr(self.state, "snapshot", None)
            if callable(snapshot):
                try:
                    state = dict(snapshot() or {})
                except Exception:
                    state = {}
        cognition_input = validate_input("cognition", {
            "semantic": semantic,
            "memory": context,
            "knowledge": {"relevant_knowledge": context.get("relevant_knowledge", [])},
            "goals": goals,
            "state": state,
            "capabilities": {"skills": getattr(self.skill_registry, "skills", {})},
            "experience": context.get("recent_experiences", []),
        })
        self.last_cognition_input = cognition_input
        self.last_cognition_output = validate_output("cognition", {
            "cognitive_context": cognition_input,
            "confidence": float(semantic.get("confidence", 0.0) or 0.0),
        })
        self.last_contracts["cognition.input"] = cognition_input
        self.last_contracts["cognition.output"] = self.last_cognition_output
        return cognition_input

    def _route_cognition(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        cognition_input = self._build_cognition_input(user_input, perception)
        router_input = validate_input("cognitive_router", {"cognitive_context": cognition_input})
        decision = self.cognitive_router.decide(user_input=user_input, cognition_input=router_input["cognitive_context"])
        router_output = validate_output("cognitive_router", {
            "route": decision.mode,
            "confidence": decision.confidence,
            "fallback_allowed": decision.llm_required,
            "evidence": list((decision.evidence or {}).items()),
        })
        payload = decision.as_dict()
        payload.update({"route": router_output["route"], "fallback_allowed": router_output["fallback_allowed"]})
        self.last_router_input = router_input
        self.last_router_output = router_output
        self.last_cognitive_decision = payload
        self.last_brain_input = validate_input("brain", {
            "cognitive_context": cognition_input,
            "routing_decision": router_output,
        })
        self.last_contracts.update({
            "cognitive_router.input": router_input,
            "cognitive_router.output": router_output,
            "brain.input": self.last_brain_input,
        })
        return payload

    def _enqueue_learning(self, event_type: str, context: Dict[str, Any], action: Dict[str, Any], outcome: Dict[str, Any], source: Optional[str], importance: float) -> None:
        self.last_brain_output = validate_output("brain", {
            "decision": dict(self.last_brain_decision or action or {}),
            "action": outcome.get("action") if isinstance(outcome, dict) else None,
            "response": outcome.get("response") if isinstance(outcome, dict) else None,
        })
        self.last_contracts["brain.output"] = self.last_brain_output
        super()._enqueue_learning(event_type, context, action, outcome, source, importance)

    def process_experience(self, event_type: str, context: Optional[Dict[str, Any]] = None,
                           action: Optional[Dict[str, Any]] = None, outcome: Optional[Dict[str, Any]] = None,
                           source: Optional[str] = None, importance: float = 0.5,
                           build_knowledge: bool = True, auto_accept: Optional[bool] = None) -> Dict[str, Any]:
        experience_input = validate_input("experience", {
            "event_type": str(event_type), "context": dict(context or {}),
            "action": dict(action or {}), "outcome": dict(outcome or {}),
            "source": str(source or "unknown"), "importance": float(importance),
        })
        self.last_experience_input = experience_input
        self.last_contracts["experience.input"] = experience_input
        result = super().process_experience(
            event_type=experience_input["event_type"], context=experience_input["context"],
            action=experience_input["action"], outcome=experience_input["outcome"],
            source=experience_input["source"], importance=experience_input["importance"],
            build_knowledge=build_knowledge, auto_accept=auto_accept,
        )
        learning_result = result.get("learning") if isinstance(result, dict) else {}
        experience_payload = result.get("experience") if isinstance(result, dict) else {}
        evaluation = learning_result.get("evaluation") if isinstance(learning_result, dict) else {}
        self.last_experience_output = validate_output("experience", {
            "evaluation": dict(evaluation or {}),
            "experience": dict(experience_payload or {}),
        })
        self.last_contracts["experience.output"] = self.last_experience_output
        if isinstance(learning_result, dict):
            self.last_learning_input = validate_input("learning", {"experience": dict(experience_payload or {})})
            knowledge = learning_result.get("knowledge")
            updates = knowledge if isinstance(knowledge, list) else ([knowledge] if knowledge is not None else [])
            self.last_learning_output = validate_output("learning", {
                "learning_result": learning_result, "knowledge_updates": updates,
            })
            self.last_contracts["learning.input"] = self.last_learning_input
            self.last_contracts["learning.output"] = self.last_learning_output
            if isinstance(evaluation, dict):
                self.last_self_evaluation_input = validate_input("self_evaluation", {"experience": dict(experience_payload or {})})
                self.last_self_evaluation_output = validate_output("self_evaluation", {"evaluation": evaluation})
                self.last_contracts["self_evaluation.input"] = self.last_self_evaluation_input
                self.last_contracts["self_evaluation.output"] = self.last_self_evaluation_output
            self.last_memory_input = validate_input("memory", {"learning_result": learning_result})
            memory_context = {}
            if self.memory is not None:
                stats = getattr(self.memory, "statistics", None)
                if callable(stats):
                    try:
                        memory_context = dict(stats() or {})
                    except Exception:
                        memory_context = {}
            self.last_memory_output = validate_output("memory", {"memory_context": memory_context})
            self.last_contracts["memory.input"] = self.last_memory_input
            self.last_contracts["memory.output"] = self.last_memory_output
        return result

    def learn(self, experience: Dict[str, Any], auto_accept: Optional[bool] = None) -> Dict[str, Any]:
        learning_input = validate_input("learning", {"experience": dict(experience)})
        result = super().learn(learning_input["experience"], auto_accept=auto_accept)
        knowledge = result.get("knowledge") if isinstance(result, dict) else None
        updates = knowledge if isinstance(knowledge, list) else ([knowledge] if knowledge is not None else [])
        self.last_learning_input = learning_input
        self.last_learning_output = validate_output("learning", {"learning_result": dict(result or {}), "knowledge_updates": updates})
        self.last_contracts["learning.input"] = learning_input
        self.last_contracts["learning.output"] = self.last_learning_output
        return result

    def evaluate(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        self_eval_input = validate_input("self_evaluation", {"experience": dict(experience)})
        result = super().evaluate(self_eval_input["experience"])
        self.last_self_evaluation_input = self_eval_input
        self.last_self_evaluation_output = validate_output("self_evaluation", {"evaluation": dict(result or {})})
        self.last_contracts["self_evaluation.input"] = self_eval_input
        self.last_contracts["self_evaluation.output"] = self.last_self_evaluation_output
        return result
