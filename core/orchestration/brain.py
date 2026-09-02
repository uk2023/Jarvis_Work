from __future__ import annotations

import re
import time
from .cognitive_router import CognitiveRouter
from .perception import PerceptionEngine, LLMPerceptionProvider
from ..skills.skill_executor import SkillExecutor
from typing import Any, Dict, Optional

from ..learning.learning_queue import AsyncLearningQueue


class Brain:
    """
    Central orchestration organ of JARVIS.

    Brain coordinates major cognitive organs and keeps LLM, memory,
    evaluation, learning, evolution and execution as separate boundaries.
    """

    VERSION = "0.6.0"

    def __init__(self, memory_manager=None, experience_engine=None,
                 self_evaluator=None, knowledge_builder=None,
                 memory_consolidator=None, learning_coordinator=None,
                 evolution_engine=None, event_bus=None, internal_state=None,
                 planner=None, goal_manager=None, llm_bridge=None,
                 cognitive_router=None, perception_engine=None,
                 skill_registry=None, skill_executor=None,
                 auto_accept_knowledge: bool = True):
        self.memory = memory_manager
        self.experience = experience_engine
        self.evaluator = self_evaluator
        self.knowledge_builder = knowledge_builder
        self.consolidator = memory_consolidator
        self.learning = learning_coordinator
        self.evolution = evolution_engine
        self.events = event_bus
        self.state = internal_state
        self.planner = planner
        self.goal_manager = goal_manager
        self.llm = llm_bridge
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = skill_executor or (SkillExecutor(skill_registry) if skill_registry else None)
        self.perception = perception_engine or PerceptionEngine(state=self.state)
        self.auto_accept_knowledge = auto_accept_knowledge
        self.created_at = time.time()
        self.last_cycle_at = None
        self.cycle_count = 0
        self.last_result = None
        self.running = True
        self._learning_queue = AsyncLearningQueue(worker=self._run_learning_job)
        self.last_turn_trace = None
        self.total_turns = 0
        self.total_latency_seconds = 0.0
        self.total_tokens_estimate = 0
        self.typo_map: Dict[str, str] = {}

    def learning_cycle_stages(self):
        return ("experience", "evaluation", "eligibility", "learning", "validation", "adoption")

    def record_learning_cycle(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise TypeError("learning cycle result must be a dictionary")
        self.last_result = dict(result)
        self.last_cycle_at = time.time()
        return self.last_result

    def _run_learning_job(self, *args, **kwargs):
        """Compatibility boundary for the asynchronous learner."""
        return None
