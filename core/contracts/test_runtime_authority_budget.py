"""Runtime regression checks for Router authority, LLM budget and live validation trace."""

from __future__ import annotations

from typing import Any

from ..contracts.validator import begin_validation_trace, get_validation_trace, validate_input
from ..orchestration.cognitive_router import CognitiveRouter
from ..orchestration.llm_bridge import CognitiveBudgetExceeded, HybridLLMBridge


class _FakeLocal:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        self.calls += 1
        return f"reply-{self.calls}"


def _cognition(memory_count: int = 3, knowledge_count: int = 0) -> dict[str, Any]:
    return {
        "semantic": {
            "normalized_text": "hello Jarvis",
            "intent": {"name": "statement", "confidence": 0.9},
            "entities": [], "relations": [], "events": [], "references": [],
            "confidence": 0.9, "provenance": {"source": "native"},
            "inferences": [], "unknowns": [],
        },
        "memory": {"recent_experiences": [{} for _ in range(memory_count)]},
        "knowledge": {"relevant_knowledge": [{} for _ in range(knowledge_count)]},
        "goals": [], "state": {}, "capabilities": {"skills": {}}, "experience": [],
    }


def test_router_does_not_emit_unexecutable_known_route() -> None:
    router = CognitiveRouter(minimum_confidence=0.6)
    decision = router.decide(user_input="hello Jarvis", cognition_input=_cognition(memory_count=3))
    assert decision.mode == "llm"
    assert decision.llm_required is True


def test_validator_records_real_runtime_events() -> None:
    begin_validation_trace()
    validate_input("cognition", _cognition())
    events = get_validation_trace()
    assert events
    assert events[-1]["schema"] == "cognition.input"
    assert events[-1]["status"] == "PASS"


def test_llm_budget_is_hard_per_turn() -> None:
    bridge = HybridLLMBridge(force_mode="offline")
    fake = _FakeLocal()
    bridge._get_local = lambda: fake
    bridge.begin_turn_budget()
    assert bridge.generate_response("system", "one", max_tokens=512) == "reply-1"
    try:
        bridge.generate_response("system", "two", max_tokens=512)
    except CognitiveBudgetExceeded:
        pass
    else:
        raise AssertionError("second 512-token request must exceed the 768-token turn budget")
    assert fake.calls == 1


def main() -> None:
    test_router_does_not_emit_unexecutable_known_route()
    test_validator_records_real_runtime_events()
    test_llm_budget_is_hard_per_turn()
    print("PASS: Router emits only executable runtime routes")
    print("PASS: central validator records real boundary validation events")
    print("PASS: LLM call/output budget is enforced per turn")
    print("PASS: Router authority + LLM budget regression checks completed")


if __name__ == "__main__":
    main()
