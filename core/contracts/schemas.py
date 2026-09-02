"""Canonical, dependency-free input/output contracts for the JARVIS pipeline.

The contracts are deliberately transport-friendly dictionaries. They define the
boundary between layers without dictating how a layer implements its work.

Design rule:
    implementation may evolve; the boundary contract stays stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class ContractError(ValueError):
    """Raised when a layer input/output violates its contract."""


@dataclass(frozen=True)
class LayerPayload:
    """Small typed wrapper useful at integration boundaries."""

    layer: str
    data: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"layer": self.layer, "data": dict(self.data)}


# JSON-like schema notation kept intentionally simple so no third-party
# validation package is required. A field value is one of:
#   "string", "number", "boolean", "object", "array", "any"
# and required fields are listed separately.
CONTRACTS: dict[str, dict[str, Any]] = {
    "perception.input": {
        "required": ("raw_input",),
        "fields": {"raw_input": "string"},
    },
    "perception.output": {
        "required": ("normalized_input", "language", "confidence"),
        "fields": {
            "normalized_input": "string",
            "language": "string",
            "confidence": "number",
            "basic_intent": "any",
            "entities": "array",
            "metadata": "object",
        },
    },
    "semantic_understanding.input": {
        "required": ("perception", "user_input"),
        "fields": {
            "perception": "object",
            "user_input": "string",
            "semantic_context": "object",
        },
    },
    "semantic_understanding.output": {
        "required": (
            "normalized_text",
            "intent",
            "entities",
            "relations",
            "events",
            "references",
            "confidence",
            "provenance",
        ),
        "fields": {
            "normalized_text": "string",
            "intent": "any",
            "entities": "array",
            "relations": "array",
            "events": "array",
            "references": "array",
            "confidence": "number",
            "provenance": "object",
            "inferences": "array",
            "unknowns": "array",
        },
    },
    "cognition.input": {
        "required": ("semantic",),
        "fields": {
            "semantic": "object",
            "memory": "object",
            "knowledge": "object",
            "goals": "array",
            "state": "object",
            "capabilities": "object",
            "experience": "array",
        },
    },
    "cognition.output": {
        "required": ("cognitive_context",),
        "fields": {"cognitive_context": "object", "confidence": "number"},
    },
    "cognitive_router.input": {
        "required": ("cognitive_context",),
        "fields": {"cognitive_context": "object"},
    },
    "cognitive_router.output": {
        "required": ("route", "confidence", "fallback_allowed"),
        "fields": {
            "route": "string",
            "confidence": "number",
            "fallback_allowed": "boolean",
            "evidence": "array",
        },
    },
    "brain.input": {
        "required": ("cognitive_context", "routing_decision"),
        "fields": {
            "cognitive_context": "object",
            "routing_decision": "object",
        },
    },
    "brain.output": {
        "required": ("decision", "action", "response"),
        "fields": {
            "decision": "object",
            "action": "any",
            "response": "any",
        },
    },
    "experience.input": {
        "required": ("user_input", "brain_result"),
        "fields": {
            "user_input": "string",
            "semantic": "object",
            "routing": "object",
            "brain_result": "object",
            "action_result": "any",
        },
    },
    "experience.output": {
        "required": ("evaluation", "experience"),
        "fields": {"evaluation": "object", "experience": "object"},
    },
    "learning.input": {
        "required": ("experience",),
        "fields": {"experience": "object"},
    },
    "learning.output": {
        "required": ("learning_result",),
        "fields": {"learning_result": "object", "knowledge_updates": "array"},
    },
    "memory.input": {
        "required": ("learning_result",),
        "fields": {"learning_result": "object"},
    },
    "memory.output": {
        "required": ("memory_context",),
        "fields": {"memory_context": "object"},
    },
    "self_evaluation.input": {
        "required": ("experience", "learning_result"),
        "fields": {"experience": "object", "learning_result": "object"},
    },
    "self_evaluation.output": {
        "required": ("evaluation", "evolution_proposal"),
        "fields": {"evaluation": "object", "evolution_proposal": "object"},
    },
    "evolution.input": {
        "required": ("evolution_proposal",),
        "fields": {"evolution_proposal": "object"},
    },
    "evolution.output": {
        "required": ("updated_capabilities", "change_record"),
        "fields": {"updated_capabilities": "object", "change_record": "object"},
    },
}


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "any":
        return True
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, (list, tuple))
    return False


def validate(schema_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a payload and return a shallow normalized dictionary."""
    if schema_name not in CONTRACTS:
        raise ContractError(f"Unknown contract: {schema_name}")
    if not isinstance(payload, Mapping):
        raise ContractError(f"{schema_name}: payload must be an object")

    schema = CONTRACTS[schema_name]
    missing = [key for key in schema["required"] if key not in payload]
    if missing:
        raise ContractError(f"{schema_name}: missing required fields: {', '.join(missing)}")

    for key, expected in schema["fields"].items():
        if key in payload and not _matches_type(payload[key], expected):
            actual = type(payload[key]).__name__
            raise ContractError(
                f"{schema_name}: field '{key}' must be {expected}, got {actual}"
            )

    return dict(payload)


def validate_input(layer: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return validate(f"{layer}.input", payload)


def validate_output(layer: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return validate(f"{layer}.output", payload)
