"""Integration tests for the Perception -> Semantic Understanding -> Cognition boundary.

Run from repository root:
    python3 -m core.contracts.test_pipeline_integration
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..orchestration.brain import Brain
from ..orchestration.perception import PerceptionEngine, PerceptionResult
from ..cognition.semantic_understanding import SemanticUnderstanding
from ..cognition.semantic_understanding.brain_adapter import SemanticBrainAdapter
from . import validate_input, validate_output


class StubPerceptionProvider:
    """Deterministic provider used to exercise the real runtime wiring."""

    name = "integration_stub"

    def perceive(
        self,
        user_input: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> PerceptionResult:
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent={"name": "statement", "confidence": 0.95, "source": self.name},
            entities=[{"text": "Python", "type": "topic", "confidence": 0.9}],
            language="en",
            confidence=0.95,
            uncertainty=0.05,
            source=self.name,
            reason="deterministic integration provider",
        )


def test_runtime_pipeline_contracts() -> None:
    perception = PerceptionEngine(providers=[StubPerceptionProvider()])
    brain = Brain(perception_engine=perception)
    semantic = SemanticUnderstanding(semantic_memory=None)
    adapter = SemanticBrainAdapter(semantic=semantic)
    adapter.attach(brain)

    result = brain._perceive("I like Python")

    perception_contract = validate_output(
        "perception", adapter.last_contracts["perception.output"]
    )
    semantic_input = validate_input(
        "semantic_understanding", adapter.last_contracts["semantic_understanding.input"]
    )
    semantic_contract = validate_output(
        "semantic_understanding", adapter.last_contracts["semantic_understanding.output"]
    )
    cognition_input = validate_input(
        "cognition", adapter.last_contracts["cognition.input"]
    )

    assert result["semantic_understanding"] == semantic_contract
    assert result["cognition_input"] == cognition_input
    assert semantic_input["perception"] == perception_contract
    assert semantic_contract["normalized_text"] == "I like Python"
    assert semantic_contract["intent"]["name"] == "statement"
    assert any(
        relation.get("predicate") == "likes"
        and relation.get("value") == "Python"
        for relation in semantic_contract["relations"]
        if isinstance(relation, dict)
    )


def test_semantic_layer_is_authoritative_and_not_legacy_double_parsed() -> None:
    perception = PerceptionEngine(providers=[StubPerceptionProvider()])
    brain = Brain(perception_engine=perception)
    semantic = SemanticUnderstanding(semantic_memory=None)
    adapter = SemanticBrainAdapter(semantic=semantic)
    adapter.attach(brain)

    first = brain._perceive("I am learning Python")
    second = brain._perceive("I am learning Python")

    assert first["semantic_understanding"]["events"]
    assert first["semantic_understanding"]["events"][0]["event_type"] == "learning_started"
    assert second["semantic_understanding"]["events"]
    assert "legacy_semantic" not in first["semantic_understanding"]
    assert "legacy_semantic" not in second["semantic_understanding"]
    assert "cognition_input" in first


def main() -> None:
    test_runtime_pipeline_contracts()
    test_semantic_layer_is_authoritative_and_not_legacy_double_parsed()
    print("PASS: runtime Perception -> Semantic Understanding -> Cognition integration")
    print("PASS: all three runtime boundaries validated against canonical contracts")
    print("PASS: legacy double-parsing path is absent from the authoritative semantic payload")


if __name__ == "__main__":
    main()
