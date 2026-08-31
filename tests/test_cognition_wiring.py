from __future__ import annotations

import unittest

from core.orchestration.cognition_wiring import CognitionWiring
from core.orchestration.cognitive_router import CognitiveRouter
from core.orchestration.llm_optional_brain import LLMOptionalBrain
from core.orchestration.perception import PerceptionEngine, PerceptionResult
from core.skills.skill_registry import SkillRegistry


class Provider:
    name = "test"

    def __init__(self, intent=None, confidence=0.95):
        self.intent = intent or {}
        self.confidence = confidence
        self.calls = 0

    def perceive(self, user_input, context=None):
        self.calls += 1
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent=self.intent,
            confidence=self.confidence,
            uncertainty=1.0 - self.confidence,
            source=self.name,
        )


class ExplodingLLM:
    def generate_response(self, **kwargs):
        raise AssertionError("LLM must not be called on a native tool route")


class CognitionWiringRuntimeTests(unittest.TestCase):
    def test_one_input_produces_one_perception_and_one_route(self):
        provider = Provider(intent={"name": "recall"})
        wiring = CognitionWiring(
            perception=PerceptionEngine(providers=[provider]),
            router=CognitiveRouter(),
        )

        result = wiring.run("what do you remember")

        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.perception.user_input, "what do you remember")
        self.assertEqual(result.decision.mode, "llm")
        self.assertEqual(result.context["recent_experiences"], [])

    def test_native_skill_route_is_selected_without_llm(self):
        provider = Provider(
            intent={"name": "example", "skill": "example"},
        )
        registry = SkillRegistry()
        registry.skills["example"] = lambda **kwargs: "ok"

        brain = LLMOptionalBrain(
            llm_bridge=ExplodingLLM(),
            perception_engine=PerceptionEngine(providers=[provider]),
            cognitive_router=CognitiveRouter(),
            skill_registry=registry,
        )

        response = brain.think_and_respond("run example")

        self.assertEqual(response, "ok")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(brain.last_cognitive_decision["mode"], "tool")
        self.assertEqual(brain.last_perception["user_input"], "run example")

    def test_clarification_route_stops_before_llm(self):
        provider = Provider(
            intent={"name": "dangerous_action", "requires_confirmation": True},
        )
        brain = LLMOptionalBrain(
            llm_bridge=ExplodingLLM(),
            perception_engine=PerceptionEngine(providers=[provider]),
            cognitive_router=CognitiveRouter(),
        )

        response = brain.think_and_respond("do the pending action")

        self.assertEqual(response, "I need clarification before I can safely continue.")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(brain.last_cognitive_decision["mode"], "clarify")


if __name__ == "__main__":
    unittest.main()
