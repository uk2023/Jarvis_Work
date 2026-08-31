import unittest
from unittest.mock import patch

from core.organism.bootstrap import JarvisBootstrap


class BootstrapRealRuntimeSmokeTests(unittest.TestCase):
    """Verify real Bootstrap assembly reaches a real Brain with controlled IO."""

    def test_bootstrap_assembles_real_organism_without_evolution_wiring(self):
        bootstrap = JarvisBootstrap()

        with patch.object(bootstrap, "_start_idle_executor", lambda: None):
            core = bootstrap.start()

        self.assertIsNotNone(core)
        self.assertIs(core.organs["brain"], bootstrap.brain)
        self.assertIs(core.organs["perception"], bootstrap.perception)
        self.assertIs(core.organs["router"], bootstrap.cognitive_router)
        self.assertIs(core.organs["skills"], bootstrap.skill_registry)
        self.assertIsNotNone(core.organs["context"])

        # Evolution remains intentionally outside the runtime cognition path.
        self.assertNotIn("evolution", core.organs)

        # Real Brain dependencies are the same live instances assembled by Bootstrap.
        self.assertIs(bootstrap.brain.perception_engine, bootstrap.perception)
        self.assertIs(bootstrap.brain.cognitive_router, bootstrap.cognitive_router)
        self.assertIs(bootstrap.brain.skill_registry, bootstrap.skill_registry)

    def test_real_brain_path_with_controlled_perception_and_llm(self):
        bootstrap = JarvisBootstrap()

        with patch.object(bootstrap, "_start_idle_executor", lambda: None):
            core = bootstrap.start()

        brain = core.organs["brain"]

        class ControlledPerception:
            def perceive(self, user_input, context=None):
                from core.orchestration.perception import PerceptionResult
                return PerceptionResult(
                    user_input=user_input,
                    normalized_text=user_input,
                    intent={"name": "conversation", "confidence": 0.99},
                    language="en",
                    confidence=0.99,
                    uncertainty=0.01,
                    source="bootstrap-smoke",
                    reason="controlled runtime smoke input",
                )

        class ControlledLLM:
            def generate_combined(self, system_prompt, user_input):
                return {"response": "bootstrap smoke response", "memory_signal": None}

        original_perception = brain.perception_engine
        original_llm = brain.llm_bridge
        brain.perception_engine = ControlledPerception()
        brain.llm_bridge = ControlledLLM()
        try:
            response = brain.think_and_respond("hello jarvis", source="bootstrap-smoke")
        finally:
            brain.perception_engine = original_perception
            brain.llm_bridge = original_llm

        self.assertEqual(response, "bootstrap smoke response")
        self.assertEqual(brain.last_perception["source"], "bootstrap-smoke")
        self.assertEqual(brain.last_cognitive_decision["mode"], "llm")
        self.assertTrue(brain.last_turn_trace["pipeline_success"])


if __name__ == "__main__":
    unittest.main()
