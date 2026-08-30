from __future__ import annotations

import unittest

from core.autonomy.idle_executor import IdleExecutor
from core.orchestration.cognitive_router import CognitiveRouter
from core.orchestration.perception import PerceptionEngine, PerceptionResult, PerceptionProvider
from core.orchestration.llm_optional_brain import LLMOptionalBrain
from core.organism.bootstrap import create_jarvis
from core.skills.skill_registry import SkillRegistry


class StubProvider:
    name = "stub"

    def perceive(self, user_input, context=None):
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent={"name": "test_capability", "skill": "test_capability"},
            requested_capability="test_capability",
            confidence=0.95,
            uncertainty=0.05,
            source=self.name,
        )


class BrainWiringContractTests(unittest.TestCase):
    def test_perception_contract(self):
        engine = PerceptionEngine(providers=[StubProvider()])
        result = engine.perceive("run test")
        self.assertIsInstance(result, PerceptionResult)
        self.assertEqual(result.source, "stub")
        self.assertEqual(result.user_input, "run test")
        self.assertGreaterEqual(result.confidence, 0.95)

    def test_router_requires_input_matched_high_confidence_perception(self):
        router = CognitiveRouter(minimum_confidence=0.80)
        decision = router.decide(
            user_input="run test",
            skills={"test_capability": lambda step: "ok"},
            perception={
                "user_input": "different input",
                "intent": {"name": "test_capability", "skill": "test_capability"},
                "confidence": 0.99,
                "source": "stub",
            },
        )
        self.assertEqual(decision.mode, "llm")
        self.assertTrue(decision.llm_required)

    def test_idle_executor_is_bounded(self):
        called = []
        executor = IdleExecutor({"test_capability": lambda step: called.append(step) or "ok"})

        result = executor.execute({"capability": "test_capability", "action": "test"})
        self.assertTrue(result["success"])
        self.assertEqual(len(called), 1)

        confirmation = executor.execute({"capability": "test_capability", "requires_confirmation": True})
        self.assertFalse(confirmation["success"])
        self.assertEqual(confirmation["result"], "confirmation_required")
        self.assertEqual(len(called), 1)

        unknown = executor.execute({"capability": "not_registered"})
        self.assertFalse(unknown["success"])
        self.assertIn("capability_not_registered", unknown["result"])

    def test_bootstrap_wires_organs(self):
        jarvis = create_jarvis(heartbeat_interval=60.0, idle_threshold=3600.0)
        self.assertIsNotNone(jarvis.organs["brain"])
        self.assertIsInstance(jarvis.organs["perception"], PerceptionEngine)
        self.assertIsInstance(jarvis.organs["cognitive_router"], CognitiveRouter)
        self.assertIsInstance(jarvis.organs["idle_executor"], IdleExecutor)
        self.assertIs(jarvis.organs["idle_executor"].capabilities, jarvis.organs["skill_registry"].skills)

    def test_llm_optional_brain_degrades_without_llm(self):
        registry = SkillRegistry()
        brain = LLMOptionalBrain(
            memory_manager=None,
            experience_engine=None,
            self_evaluator=None,
            knowledge_builder=None,
            memory_consolidator=None,
            learning_coordinator=None,
            evolution_engine=None,
            planner=None,
            goal_manager=None,
            event_bus=None,
            internal_state=None,
            llm_bridge=None,
            skill_registry=registry,
        )
        response = brain.think_and_respond("hello")
        self.assertIn("LLM", response)
        self.assertIsNotNone(brain.last_perception)
        self.assertIsNotNone(brain.last_cognitive_decision)
        self.assertEqual(brain.last_cognitive_decision["mode"], "llm")


if __name__ == "__main__":
    unittest.main()
