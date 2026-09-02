"""Canonical, dependency-free input/output contracts for the JARVIS pipeline.

The contracts are transport-friendly dictionaries. They define boundaries
between layers without dictating how a layer implements its work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class ContractError(ValueError):
    """Raised when a payload violates a registered contract."""


@dataclass(frozen=True)
class LayerPayload:
    """Typed wrapper useful at integration boundaries."""

    layer: str
    data: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"layer": self.layer, "data": dict(self.data)}


# JSON-like schema notation. Field types are intentionally small and
# dependency-free: string, number, boolean, object, array, or any.
CONTRACTS: dict[str, dict[str, Any]] = {
    "perception.input": {"required": ("raw_input",), "fields": {"raw_input": "string"}},
    "perception.output": {
        "required": ("normalized_input", "language", "confidence"),
        "fields": {"normalized_input": "string", "language": "string", "confidence": "number", "basic_intent": "any", "entities": "array", "metadata": "object"},
    },
    "semantic_understanding.input": {
        "required": ("perception", "user_input"),
        "fields": {"perception": "object", "user_input": "string", "semantic_context": "object"},
    },
    "semantic_understanding.output": {
        "required": ("normalized_text", "intent", "entities", "relations", "events", "references", "confidence", "provenance"),
        "fields": {"normalized_text": "string", "intent": "any", "entities": "array", "relations": "array", "events": "array", "references": "array", "confidence": "number", "provenance": "object", "inferences": "array", "unknowns": "array"},
    },
    "cognition.input": {
        "required": ("semantic",),
        "fields": {"semantic": "object", "memory": "object", "knowledge": "object", "goals": "array", "state": "object", "capabilities": "object", "experience": "array"},
    },
    "cognition.output": {"required": ("cognitive_context",), "fields": {"cognitive_context": "object", "confidence": "number"}},
    "cognitive_router.input": {"required": ("cognitive_context",), "fields": {"cognitive_context": "object"}},
    "cognitive_router.output": {"required": ("route", "confidence", "fallback_allowed"), "fields": {"route": "string", "confidence": "number", "fallback_allowed": "boolean", "evidence": "array"}},
    "brain.input": {"required": ("cognitive_context", "routing_decision"), "fields": {"cognitive_context": "object", "routing_decision": "object"}},
    "brain.output": {"required": ("decision", "action", "response"), "fields": {"decision": "object", "action": "any", "response": "any"}},
    "experience.input": {
        "required": ("event_type", "context", "action", "outcome"),
        "fields": {"event_type": "string", "context": "object", "action": "object", "outcome": "object", "source": "any", "importance": "number"},
    },
    "experience.output": {"required": ("evaluation", "experience"), "fields": {"evaluation": "object", "experience": "object"}},
    "learning.input": {"required": ("experience",), "fields": {"experience": "object"}},
    "learning.output": {"required": ("learning_result",), "fields": {"learning_result": "object", "knowledge_updates": "array"}},
    "memory.input": {"required": ("learning_result",), "fields": {"learning_result": "object"}},
    "memory.output": {"required": ("memory_context",), "fields": {"memory_context": "object"}},
    "self_evaluation.input": {"required": ("experience",), "fields": {"experience": "object"}},
    "self_evaluation.output": {"required": ("evaluation",), "fields": {"evaluation": "object"}},
    "evolution.input": {"required": ("evolution_proposal",), "fields": {"evolution_proposal": "object"}},
    "evolution.output": {"required": ("updated_capabilities", "change_record"), "fields": {"updated_capabilities": "object", "change_record": "object"}},
}
