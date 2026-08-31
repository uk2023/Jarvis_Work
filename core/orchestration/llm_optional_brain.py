from __future__ import annotations

"""LLM-optional Brain adapter: perception -> routing -> action/LLM."""
from time import time
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain
from .cognitive_router import CognitiveRouter
from .cognition_wiring import CognitionWiring
from .perception import PerceptionEngine, LLMPerceptionProvider
from ..skills.skill_executor import SkillExecutor


class LLMOptionalBrain(BaseBrain):
    """Brain whose language cognition is a replaceable perception provider."""

    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+perception-router"

    def __init__(self, *args, cognitive_router=None, perception_engine=None,
                 skill_registry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None
        self.perception = perception_engine or PerceptionEngine(state=self.state)
        self.cognition = CognitionWiring(
            perception=self.perception,
            router=self.cognitive_router,
            memory=self.memory,
            goal_manager=self.goal_manager,
            skill_registry=self.skill_registry,
            state=self.state,
        )
        if self.llm is not None:
            self.set_llm_bridge(self.llm)
        self.last_cognitive_decision: Optional[Dict[str, Any]] = None
        self.last_perception: Optional[Dict[str, Any]] = None

    def set_llm_bridge(self, llm_bridge: Any) -> None:
        """Attach/detach the LLM without changing Brain or Router contracts."""
        self.llm = llm_bridge
        self.perception.providers = [p for p in self.perception.providers if getattr(p, "name", None) != "llm"]
        if llm_bridge is not None:
            self.perception.add_provider(LLMPerceptionProvider(llm_bridge))

    def attach_skill_registry(self, skill_registry: Any) -> None:
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None
        self.cognition.skill_registry = skill_registry

    def _run_cognition(self, user_input: str) -> Dict[str, Any]:
        """Canonical single-pass Perception -> CognitiveRouter wiring."""
        result = self.cognition.run(user_input)
        perception = result.perception.as_dict()
        route = result.decision.as_dict()
        self.last_perception = perception
        self.last_cognitive_decision = route
        return route

    def _perceive(self, user_input: str) -> Dict[str, Any]:
        """Compatibility accessor; does not perform a second cognition pass."""
        if self.cognition.last_pass is None or self.cognition.last_pass.perception.user_input != user_input:
            self._run_cognition(user_input)
        return self.last_perception or {}

    def _route_cognition(self, user_input: str, perception: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compatibility accessor; reuses the current pass for the same input."""
        if self.cognition.last_pass is None or self.cognition.last_pass.perception.user_input != user_input:
            return self._run_cognition(user_input)
        route = self.cognition.last_pass.decision.as_dict()
        self.last_cognitive_decision = route
        return route

    def _trace(self, user_input: str, response: str, route: Dict[str, Any],
               perception: Dict[str, Any], started: float, llm: bool) -> None:
        self.last_turn_trace = {
            "source": "brain", "query": user_input, "response_preview": response[:200],
            "perception": perception, "cognitive_route": route, "llm_available": llm,
            "pipeline_success": True,
            "timings": {"total": time() - started, "memory": 0.0, "llm": 0.0},
        }

    def _fallback(self, user_input: str) -> str:
        lower = (user_input or "").strip().lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        return "JARVIS received the input, but no LLM language cognition provider is currently available. Core organism remains active."

    def think_and_respond(self, user_input: str,
                          identity_profile: Optional[Dict[str, Any]] = None,
                          source: str = "cli") -> str:
        started = time()
        route = self._run_cognition(user_input)
        perception = self.last_perception or {}
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
