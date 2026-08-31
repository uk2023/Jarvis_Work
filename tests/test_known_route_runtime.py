from __future__ import annotations

import unittest

from core.orchestration.llm_optional_brain import LLMOptionalBrain
from core.orchestration.cognitive_router import CognitiveRouter
from core.orchestration.perception import PerceptionEngine, PerceptionResult


class MemoryWithEvidence:
    def build_context(
        self,
        query=None,
        subject=None,
        recent_limit=3,
        knowledge_limit=10,
    ):
        return {
            "recent_experiences": [{"id": 1, "text": "known fact"}],
            "relevant_knowledge": [],
            "graph_relations": [],
        }


class RecallProvider:
    name = "test"

    def __init__(self):
        self.calls = 0

    def perceive(self, user_input, context=None):
        self.calls += 1
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent={"name": "recall"},
            confidence=0.95,
            uncertainty=0.05,
            source=self.name,
        )


class RenderingLLM:
    def __init__(self):
        self.calls = 0

    def generate_response(self, **kwargs):
        self.calls += 1
        return "LLM rendered known-memory response"


class KnownRouteRuntimeTests(unittest.TestCase):
    def test_known_route_uses_llm_renderer_when_available(self):
        provider = RecallProvider()
        llm = RenderingLLM()
        brain = LLMOptionalBrain(
            memory_manager=MemoryWithEvidence(),
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
            llm_bridge=llm,
            perception_engine=PerceptionEngine(providers=[provider]),
            cognitive_router=CognitiveRouter(),
        )
        brain._enqueue_learning = lambda **kwargs: None

        response = brain.think_and_respond("what do you remember")

        self.assertEqual(response, "LLM rendered known-memory response")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(brain.last_cognitive_decision["mode"], "known")


if __name__ == "__main__":
    unittest.main()
