from __future__ import annotations

from types import MethodType
from typing import Any, Optional

from ...contracts import validate_input, validate_output
from .bridge_to_cognition import SemanticUnderstanding
from .engine import SemanticUnderstandingEngine


class SemanticBrainAdapter:
    """Make Semantic Understanding the authoritative Brain runtime boundary.

    The adapter preserves Brain's existing orchestration API while enforcing
    the canonical contracts at Perception -> Semantic Understanding ->
    Cognition. It does not persist knowledge and it does not replace the
    Cognitive Router.
    """

    VERSION = "0.3.0"

    def __init__(
        self,
        engine: Optional[SemanticUnderstandingEngine] = None,
        semantic: Optional[SemanticUnderstanding] = None,
    ):
        self.engine = engine or SemanticUnderstandingEngine()
        self.semantic = semantic

    @staticmethod
    def _perception_contract(payload: dict[str, Any]) -> dict[str, Any]:
        entities = payload.get("entities", [])
        if isinstance(entities, dict):
            entities = [entities] if entities else []
        elif not isinstance(entities, list):
            entities = []
        return validate_output(
            "perception",
            {
                "normalized_input": str(
                    payload.get("normalized_text", payload.get("user_input", ""))
                ),
                "language": str(payload.get("language") or "unknown"),
                "confidence": float(payload.get("confidence", 0.0) or 0.0),
                "basic_intent": payload.get("intent", {}),
                "entities": entities,
                "metadata": {
                    "source": payload.get("source", "unknown"),
                    "uncertainty": payload.get("uncertainty", 1.0),
                    "reason": payload.get("reason", ""),
                },
            },
        )

    @staticmethod
    def _semantic_contract(
        integrated: dict[str, Any], perception: dict[str, Any]
    ) -> dict[str, Any]:
        semantic = integrated.get("semantic") or {}
        intent = semantic.get("intent", {})
        return validate_output(
            "semantic_understanding",
            {
                "normalized_text": str(
                    semantic.get("normalized", perception.get("normalized_text", ""))
                ),
                "intent": intent,
                "entities": list(semantic.get("entities") or []),
                "relations": list(
                    integrated.get("relations") or semantic.get("relations") or []
                ),
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
            },
        )

    def attach(self, brain: Any) -> Any:
        if getattr(brain, "_semantic_understanding_attached", False):
            return brain
        if self.semantic is None:
            memory_manager = getattr(brain, "memory", None)
            semantic_memory = getattr(memory_manager, "semantic", None)
            self.semantic = SemanticUnderstanding(semantic_memory=semantic_memory)

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

            semantic_input = validate_input(
                "semantic_understanding",
                {
                    "perception": perception_contract,
                    "user_input": user_input,
                    "semantic_context": perception.get("context", {})
                    if isinstance(perception, dict)
                    else {},
                },
            )

            integrated = semantic.understand(
                semantic_input["user_input"],
                context=semantic_input.get("semantic_context") or {},
                retrieve=True,
            )
            semantic_contract = self._semantic_contract(integrated, perception)

            cognition_input = validate_input(
                "cognition",
                {
                    "semantic": semantic_contract,
                    "memory": {},
                    "knowledge": {},
                    "goals": [],
                    "state": {},
                    "capabilities": {},
                    "experience": [],
                },
            )

            enriched = dict(perception)
            enriched["semantic_understanding"] = semantic_contract
            enriched["cognition_input"] = cognition_input
            enriched["semantic_evidence"] = integrated.get("evidence", {})
            enriched["semantic_fact_candidates"] = (
                integrated.get("semantic", {}).get("fact_candidates", [])
                if isinstance(integrated.get("semantic"), dict)
                else []
            )
            this.last_contracts = {
                "perception.output": perception_contract,
                "semantic_understanding.input": semantic_input,
                "semantic_understanding.output": semantic_contract,
                "cognition.input": cognition_input,
            }
            this.last_semantic_understanding = semantic_contract
            this.last_cognition_input = cognition_input
            return enriched

        brain._perceive = MethodType(perceive_with_semantics, brain)
