"""Local smoke tests for the JARVIS contract layer.

Run from repository root:
    python3 -m core.contracts.test_contracts
"""

from __future__ import annotations

from . import CONTRACTS, ContractError, validate_input, validate_output


def test_registry_is_complete() -> None:
    expected_layers = {
        "perception",
        "semantic_understanding",
        "cognition",
        "cognitive_router",
        "brain",
        "experience",
        "learning",
        "memory",
        "self_evaluation",
        "evolution",
    }
    actual_layers = {name.rsplit(".", 1)[0] for name in CONTRACTS}
    assert actual_layers == expected_layers, (actual_layers, expected_layers)
    for layer in expected_layers:
        assert f"{layer}.input" in CONTRACTS
        assert f"{layer}.output" in CONTRACTS


def test_representative_pipeline() -> None:
    perception = validate_output(
        "perception",
        {
            "normalized_input": "How do I stay motivated in my journey?",
            "language": "en",
            "confidence": 0.99,
            "basic_intent": "guidance",
            "entities": [],
            "metadata": {},
        },
    )
    semantic = validate_output(
        "semantic_understanding",
        {
            "normalized_text": perception["normalized_input"],
            "intent": {"name": "motivation_guidance"},
            "entities": [],
            "relations": [],
            "events": [],
            "references": [],
            "confidence": 0.91,
            "provenance": {"source": "native_semantic"},
            "inferences": [],
            "unknowns": [],
        },
    )
    cognition = validate_input(
        "cognition",
        {
            "semantic": semantic,
            "memory": {},
            "knowledge": {},
            "goals": [],
            "state": {},
            "capabilities": {},
            "experience": [],
        },
    )
    assert cognition["semantic"]["intent"]["name"] == "motivation_guidance"


def test_invalid_payload_is_rejected() -> None:
    try:
        validate_output("perception", {"normalized_input": "missing fields"})
    except ContractError:
        return
    raise AssertionError("invalid perception output was accepted")


def main() -> None:
    test_registry_is_complete()
    test_representative_pipeline()
    test_invalid_payload_is_rejected()
    print(f"PASS: {len(CONTRACTS)} JARVIS input/output contracts validated")
    print("PASS: perception -> semantic_understanding -> cognition wiring validated")
    print("PASS: invalid payload rejection validated")


if __name__ == "__main__":
    main()
