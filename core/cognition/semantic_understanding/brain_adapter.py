from __future__ import annotations

import json
import re
from types import MethodType
from typing import Any, Optional

from ...contracts import validate_input, validate_output
from .bridge_to_cognition import SemanticUnderstanding
from .engine import SemanticUnderstandingEngine


class SemanticBrainAdapter:
    """Authoritative Perception -> Semantic Understanding -> Cognition boundary.

    M3.1 additionally binds the existing Brain LLM and LearningCoordinator to
    Semantic Understanding as fallback/intake services. The LLM only proposes
    a semantic candidate; it never writes trusted knowledge directly.
    """

    VERSION = "0.4.0"

    _FALLBACK_SYSTEM_PROMPT = (
        "You are JARVIS semantic understanding fallback.\n"
        "Interpret the user's input and return ONLY a JSON object.\n"
        "Do not answer conversationally. Do not invent external facts.\n"
        "Use this exact top-level shape:\n"
        '{"semantic":{"normalized":"...","intent":{},"entities":[],'
        '"relations":[],"events":[],"references":[],"confidence":0.0,'
        '"provenance":{"source":"llm_fallback"},"inferences":[],"unknowns":[]}}\n'
        "confidence must be between 0 and 1. unknowns must list unresolved semantic parts."
    )

    def __init__(self, engine: Optional[SemanticUnderstandingEngine] = None,
                 semantic: Optional[SemanticUnderstanding] = None):
        self.engine = engine or SemanticUnderstandingEngine()
        self.semantic = semantic
        self.last_contracts: dict[str, dict[str, Any]] = {}
        self.last_semantic_understanding: Optional[dict[str, Any]] = None
        self.last_cognition_input: Optional[dict[str, Any]] = None
        self.last_fallback_error: Optional[str] = None

    @staticmethod
    def _perception_contract(payload: dict[str, Any]) -> dict[str, Any]:
        entities = payload.get("entities", [])
        if isinstance(entities, dict):
            entities = [entities] if entities else []
        elif not isinstance(entities, list):
            entities = []
        return validate_output("perception", {
            "normalized_input": str(payload.get("normalized_text", payload.get("user_input", ""))),
            "language": str(payload.get("language") or "unknown"),
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "basic_intent": payload.get("intent", {}),
            "entities": entities,
            "metadata": {
                "source": payload.get("source", "unknown"),
                "uncertainty": payload.get("uncertainty", 1.0),
                "reason": payload.get("reason", ""),
            },
        })

    @staticmethod
    def _semantic_contract(integrated: dict[str, Any], perception: dict[str, Any]) -> dict[str, Any]:
        semantic = integrated.get("semantic") or {}
        intent = semantic.get("intent", {})
        return validate_output("semantic_understanding", {
            "normalized_text": str(semantic.get("normalized", perception.get("normalized_text", ""))),
            "intent": intent,
            "entities": list(semantic.get("entities") or []),
            "relations": list(integrated.get("relations") or semantic.get("relations") or []),
            "events": list(semantic.get("events") or []),
            "references": list(semantic.get("references") or []),
            "confidence": float(semantic.get("confidence", 0.0) or 0.0),
            "provenance": {
                "source": "semantic_understanding",
                "version": integrated.get("version"),
                "parser_source": intent.get("source") if isinstance(intent, dict) else None,
            },
            "inferences": list(semantic.get("inferences") or []),
            "unknowns": list(semantic.get("unknowns") or []),
        })

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any]:
        text = str(raw or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("LLM semantic fallback did not return JSON")
            value = json.loads(text[start:end + 1])
        if not isinstance(value, dict):
            raise TypeError("LLM semantic fallback JSON must be an object")
        return value

    def _llm_semantic_fallback(self, request: dict[str, Any]) -> dict[str, Any]:
        """Call the existing Brain LLM bridge and convert its answer to a candidate."""
        self.last_fallback_error = None
        llm = getattr(request.get("brain"), "llm", None)
        if llm is None:
            raise RuntimeError("Brain LLM bridge is not connected")
        raw = llm.generate_response(
            system_prompt=self._FALLBACK_SYSTEM_PROMPT,
            user_input=str(request.get("text", "")),
            max_tokens=512,
            temperature=0.1,
        )
        payload = self._extract_json_object(raw)
        semantic = payload.get("semantic", payload)
        if not isinstance(semantic, dict) or not semantic:
            raise ValueError("LLM semantic fallback returned no semantic object")
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

    def attach(self, brain: Any) -> Any:
        if getattr(brain, "_semantic_understanding_attached", False):
            return brain
        if self.semantic is None:
            memory_manager = getattr(brain, "memory", None)
            semantic_memory = getattr(memory_manager, "semantic", None)
            self.semantic = SemanticUnderstanding(semantic_memory=semantic_memory)
        boundary = self.semantic.learning_boundary
        boundary.llm_fallback = lambda request: self._llm_semantic_fallback({**request, "brain": brain})
        boundary.learning = getattr(brain, "learning_coordinator", None)
        brain.semantic_understanding = self
        self._wrap_perception(brain)
        brain._semantic_understanding_attached = True
        return brain

    def _wrap_perception(self, brain: Any) -> None:
        original = brain._perceive
        semantic = self.semantic

        def perceive_with_semantics(this, user_input: str):
            perception = original(user_input)
            perception_contract = self._perception_contract(perception)
            semantic_input = validate_input("semantic_understanding", {
                "perception": perception_contract,
                "user_input": user_input,
                "semantic_context": perception.get("context", {}) if isinstance(perception, dict) else {},
            })
            integrated = semantic.understand(
                semantic_input["user_input"],
                context=semantic_input.get("semantic_context") or {},
                retrieve=True,
            )
            semantic_contract = self._semantic_contract(integrated, perception)
            cognition_input = validate_input("cognition", {
                "semantic": semantic_contract,
                "memory": {},
                "knowledge": {},
                "goals": [],
                "state": {},
                "capabilities": {},
                "experience": [],
            })

            enriched = dict(perception)
            enriched["semantic_understanding"] = semantic_contract
            enriched["cognition_input"] = cognition_input
            enriched["semantic_evidence"] = integrated.get("evidence", {})
            enriched["semantic_learning"] = integrated.get("learning", {})
            enriched["semantic_fact_candidates"] = (
                integrated.get("semantic", {}).get("fact_candidates", [])
                if isinstance(integrated.get("semantic"), dict) else []
            )
            self.last_contracts = {
                "perception.output": perception_contract,
                "semantic_understanding.input": semantic_input,
                "semantic_understanding.output": semantic_contract,
                "cognition.input": cognition_input,
            }
            self.last_semantic_understanding = semantic_contract
            self.last_cognition_input = cognition_input
            return enriched

        brain._perceive = MethodType(perceive_with_semantics, brain)
