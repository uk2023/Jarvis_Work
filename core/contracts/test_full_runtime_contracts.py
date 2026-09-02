"""End-to-end contract enforcement smoke test for the live blueprint runtime."""

from __future__ import annotations

import time
from typing import Any, Mapping, Optional

from ..orchestration.contract_enforced_brain import ContractEnforcedBlueprintBrain
from ..orchestration.cognitive_router import CognitiveDecision
from ..orchestration.perception import PerceptionEngine, PerceptionResult
from ..cognition.semantic_understanding import SemanticUnderstanding
from ..cognition.semantic_understanding.brain_adapter import SemanticBrainAdapter


class StubPerceptionProvider:
    name = "contract_runtime_stub"

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent={"name": "statement", "confidence": 0.95, "source": self.name},
            entities=[], language="en", confidence=0.95, uncertainty=0.05,
            source=self.name, reason="contract runtime test",
        )


class CapturingRouter:
    def __init__(self) -> None:
        self.last_input = None

    def decide(self, *, cognition_input=None, **kwargs):
        self.last_input = cognition_input
        confidence = float((cognition_input.get("semantic") or {}).get("confidence", 0.0))
        return CognitiveDecision("llm", confidence, "contract test", {"source": "test"}, True)


class StubLLM:
    def generate(self, system_prompt: str, user_input: str) -> str:
        return "contract runtime response"


class StubExperience:
    def process(self, **kwargs):
        return {"episode_id": "contract-episode", "experience": kwargs}


class StubLearning:
    def __init__(self) -> None:
        self.calls = 0
        self.last_result = None

    def learn(self, *, experience, auto_accept=True):
        self.calls += 1
        self.last_result = {
            "success": True,
            "experience": experience,
            "evaluation": {"success": True},
            "knowledge": None,
            "accepted": False,
        }
        return self.last_result


def test_full_runtime_contract_chain() -> None:
    router = CapturingRouter()
    learning = StubLearning()
    brain = ContractEnforcedBlueprintBrain(
        perception_engine=PerceptionEngine(providers=[StubPerceptionProvider()]),
        cognitive_router=router,
        llm_bridge=StubLLM(),
        experience_engine=StubExperience(),
        learning_coordinator=learning,
    )
    adapter = SemanticBrainAdapter(semantic=SemanticUnderstanding(semantic_memory=None))
    adapter.attach(brain)

    brain.start()
    try:
        response = brain.think_and_respond("I like Python")
        assert response == "contract runtime response"
        deadline = time.time() + 2.0
        while time.time() < deadline and brain._learning_queue.processed < 1:
            time.sleep(0.01)

        assert router.last_input is not None
        assert brain.last_cognition_output["cognitive_context"] == brain.last_cognition_input
        assert brain.last_router_input["cognitive_context"] == brain.last_cognition_input
        assert brain.last_router_output["route"] == "llm"
        assert brain.last_brain_input["cognitive_context"] == brain.last_cognition_input
        assert brain.last_brain_output["response"] == "contract runtime response"
        assert brain.last_experience_input["brain_result"] == brain.last_brain_output
        assert brain.last_experience_output["experience"]
        assert brain.last_learning_input["experience"] == brain.last_experience_output["experience"]
        assert brain.last_learning_output["learning_result"]
        assert brain.last_memory_input["learning_result"] == brain.last_learning_output["learning_result"]
        assert brain.last_memory_output["memory_context"] is not None
        assert brain._learning_queue.failed == 0
        assert learning.calls == 1
    finally:
        brain.stop()


def main() -> None:
    test_full_runtime_contract_chain()
    print("PASS: Cognition input/output contracts enforced")
    print("PASS: Cognitive Router input/output contracts enforced")
    print("PASS: Brain input/output contracts enforced")
    print("PASS: Experience input/output contracts enforced")
    print("PASS: Learning input/output contracts enforced")
    print("PASS: Memory input/output contracts enforced")
    print("PASS: full runtime contract chain completed")


if __name__ == "__main__":
    main()
