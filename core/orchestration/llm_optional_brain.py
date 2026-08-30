# -*- coding: utf-8 -*-
"""LLM-optional Brain adapter.

Perception now precedes routing. The LLM is injected as a replaceable
PerceptionProvider and remains a fallback cognition/response service.
"""
from time import time
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain
from .cognitive_router import CognitiveRouter
from .perception import PerceptionEngine, LLMPerceptionProvider
from ..skills.skill_executor import SkillExecutor


class LLMOptionalBrain(BaseBrain):
    """Brain whose language cognition can be replaced without changing Brain."""

    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+perception-router"

    def __init__(self, *args, cognitive_router=None, perception_engine=None,
                 skill_registry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None
        self.perception = perception_engine or PerceptionEngine(state=self.state)
        if self.llm is not None and not self.perception.providers:
            self.perception.add_provider(LLMPerceptionProvider(self.llm))
        self.last_cognitive_decision: Optional[Dict[str, Any]] = None
        self.last_perception: Optional[Dict[str, Any]] = None

    def _perceive(self, user_input: str) -> Dict[str, Any]:
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        result = self.perception.perceive(user_input, context=context)
        payload = result.as_dict()
        self.last_perception = payload
        return payload

    def _route_cognition(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]

        decision = self.cognitive_router.decide(
            user_input=user_input,
            context=context,
            skills=getattr(self.skill_registry, "skills", None),
            identity=None,
            goals=goals,
            perception=perception,
        )
        payload = decision.as_dict()
        self.last_cognitive_decision = payload
        if self.state is not None:
            try:
                self.state.update(
                    last_route=decision.mode,
                    confidence=decision.confidence,
                    uncertainty=1.0 - decision.confidence,
                )
            except Exception:
                pass
        return payload

    def _trace(self, user_input: str, response: str, route: Dict[str, Any],
               perception: Dict[str, Any], started: float, llm: bool) -> None:
        self.last_turn_trace = {
            "source": "brain",
            "query": user_input,
            "response_preview": response[:200],
            "perception": perception,
            "cognitive_route": route,
            "llm_available": llm,
            "pipeline_success": True,
            "timings": {"total": time() - started, "memory": 0.0, "llm": 0.0},
        }

    def _fallback(self, user_input: str) -> str:
        lower = (user_input or "").strip().lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        if lower in {"who are you", "what are you", "tum kaun ho", "aap kaun ho"}:
            return "Main JARVIS ka core organism hoon. Brain, state, memory, learning aur autonomous subsystems active hain; natural-language cognition abhi unavailable hai."
        return "JARVIS received the input, but no language cognition provider is currently available. Core organism remains active."

    def think_and_respond(self, user_input: str,
                          identity_profile: Optional[Dict[str, Any]] = None,
                          source: str = "cli") -> str:
        started = time()
        perception = self._perceive(user_input)
        route = self._route_cognition(user_input, perception)
        mode = route.get("mode")
        intent = perception.get("intent") or {}

        if mode == "tool" and self.skill_executor is not None:
            skill_name = intent.get("skill") or intent.get("name")
            if skill_name:
                try:
                    response = str(self.skill_executor.execute(skill_name, user_input=user_input))
                    self._enqueue_learning(
                        event_type="USER_CHAT_TOOL",
                        context={"user_input": user_input, "perception": perception, "cognitive_route": route},
                        action={"skill": skill_name, "result": response},
                        outcome={"status": "completed"}, source=source, importance=0.7,
                    )
                    self._trace(user_input, response, route, perception, started, self.llm is not None)
                    return response
                except Exception as exc:
                    route = dict(route)
                    route["native_execution_error"] = str(exc)
                    self.last_cognitive_decision = route

        if mode == "clarify":
            response = "I need clarification before I can safely continue."
            self._trace(user_input, response, route, perception, started, self.llm is not None)
            return response

        # LLM is reached only after perception + routing determine that
        # deterministic organism evidence is currently insufficient.
        if mode == "llm" and self.llm is not None:
            response = super().think_and_respond(user_input, identity_profile=identity_profile, source=source)
            self._trace(user_input, response, route, perception, started, True)
            return response

        if mode == "known" and self.llm is None:
            response = "JARVIS has supporting knowledge, but no native language renderer is available yet."
            self._trace(user_input, response, route, perception, started, False)
            return response

        response = self._fallback(user_input)
        try:
            self._enqueue_learning(
                event_type="USER_INPUT_DEGRADED",
                context={"user_input": user_input, "perception": perception, "cognitive_route": route},
                action={"mode": "llm_unavailable"},
                outcome={"status": "received_without_llm"}, source=source, importance=0.2,
            )
        except Exception:
            pass
        self._trace(user_input, response, route, perception, started, False)
        return response


def install_llm_optional_brain() -> None:
    return None
