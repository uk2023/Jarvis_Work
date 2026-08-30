from __future__ import annotations

import unittest

from core.autonomy.idle_executor import IdleExecutor
from core.orchestration.cognitive_router import CognitiveRouter
from core.orchestration.llm_optional_brain import LLMOptionalBrain
from core.orchestration.perception import PerceptionEngine, PerceptionResult, PerceptionProvider


class FixedProvider:
    name = "test-native"

    def __init__(self, result: PerceptionResult):
        self.result = result

    def perceive(self, user_input, context=None):
        return self.result


class FakeSkillRegistry:
    def __init__(self):
        self.skills = {}

    def get(self, name):
        return self.skills.get(name)


class BrainWiringContractTests(unittest.TestCase):
    def test_perception_result_contract(self):
        result = PerceptionResult(
            user_input="test input",
            normalized_text="test input",
            intent={"name": "test", "skill": "echo"},
            confidence=0.95,
            source="test-native",
        )
        engine = PerceptionEngine(providers=[FixedProvider(result)])
        observed = engine.perceive("test input")
        self.assertEqual(observed.user_input, "test input")
        self.assertEqual(observed.intent["name"], "test")
        self.assertGreaterEqual(observed.confidence, 0.8)

    def test_router_selects_native_tool_without_llm(self):
        router = CognitiveRouter()
        decision = router.decide(
            user_input="run echo",
            perception={
                "user_input": "run echo",
                "intent": {"name": "execute", "skill": "echo"},
                "confidence": 0.95,
                "source": "test-native",
            },
            skills={"echo": object()},
        )
        self.assertEqual(decision.mode, "tool")
        self.assertFalse(decision.llm_required)

    def test_router_refuses_unmatched_perception(self):
        router = CognitiveRouter()
        decision = router.decide(
            user_input="actual input",
            perception={
                "user_input": "different input",
                "intent": {"name": "execute"},
                "confidence": 0.99,
            },
            skills={"echo": object()},
        )
        self.assertEqual(decision.mode, "llm")
        self.assertTrue(decision.llm_required)

    def test_idle_executor_is_bounded(self):
        calls = []

        def echo(step):
            calls.append(step)
            return "ok"

        executor = IdleExecutor(capabilities={"echo": echo})
        result = executor.execute({"capability": "echo", "action": "echo"})
        self.assertTrue(result["success"])
        self.assertEqual(calls[0]["capability"], "echo")

        blocked = executor.execute({"capability": "echo", "requires_confirmation": True})
        self.assertFalse(blocked["success"])
        self.assertEqual(len(calls), 1)

        unknown = executor.execute({"capability": "not_registered"})
        self.assertFalse(unknown["success"])

    def test_optional_brain_can_operate_without_llm(self):
        brain = LLMOptionalBrain(
            cognitive_router=CognitiveRouter(),
            perception_engine=PerceptionEngine(),
            llm_bridge=None,
        )
        response = brain.think_and_respond("status")
        self.assertIn("LLM unavailable", response)
        self.assertEqual(brain.last_cognitive_decision["mode"], "llm")
        self.assertFalse(brain.last_turn_trace["llm_available"])


if __name__ == "__main__":
    unittest.main()
