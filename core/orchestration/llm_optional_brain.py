# -*- coding: utf-8 -*-
"""LLM-optional runtime adapter for JARVIS Brain.

CognitiveRouter is the first decision point in the live Brain pipeline. The
LLM is a fallback cognition service, not the owner of orchestration.
"""
from time import time
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain
from .cognitive_router import CognitiveRouter


class LLMOptionalBrain(BaseBrain):
    """Brain that remains alive when no LLM bridge is attached."""

    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+llm-optional-router"

    def __init__(self, *args, cognitive_router=None, skill_registry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = None
        self.last_cognitive_decision: Optional[Dict[str, Any]] = None

    def _get_structured_intent(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Read only a perception explicitly associated with this input.

        The router never invents intent. A stale perception from an earlier
        turn must never be allowed to authorize a new native action.
        """
        perception = getattr(self.state, "last_perception", None) if self.state is not None else None
        if not isinstance(perception, dict):
            return None

        source_input = perception.get("user_input") or perception.get("source_input")
        if source_input != user_input:
            return None

        intent = perception.get("intent")
        if isinstance(intent, dict):
            return intent
        return None

    def _route_cognition(self, user_input: str) -> Dict[str, Any]:
        """Run the router before any LLM call and persist its decision."""
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
            explicit_intent=self._get_structured_intent(user_input),
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

    def _record_route_trace(self, route: Dict[str, Any], llm_available: bool) -> None:
        """Add routing telemetry without fabricating cognitive results."""
        trace = dict(self.last_turn_trace or {})
        trace["cognitive_route"] = route
        trace["llm_available"] = llm_available
        self.last_turn_trace = trace

    def _fallback_cognitive_response(self, user_input: str, source: str = "cli") -> str:
        text = (user_input or "").strip()
        lower = text.lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        if lower in {"who are you", "what are you", "tum kaun ho", "aap kaun ho"}:
            return ("Main JARVIS ka core organism hoon. Natural-language reasoning service "
                    "abhi unavailable hai, lekin Brain, state, memory aur autonomous "
                    "subsystems active reh sakte hain.")
        if lower in {"what can you do", "tum kya kar sakte ho"}:
            return ("LLM ke bina main deterministic core operations, state, memory, "
                    "learning, goals aur autonomous coordination maintain kar sakta hoon. "
                    "Natural conversation ke liye LLM attach karna zaroori hai.")
        return ("JARVIS received your input, but the LLM cognitive service is currently "
                "offline. Core organism remains alive; natural-language reasoning is "
                "temporarily unavailable.")

    def think_and_respond(self, user_input: str,
                          identity_profile: Optional[Dict[str, Any]] = None,
                          source: str = "cli") -> str:
        """Route cognition first; invoke LLM only when the route requires it."""
        turn_start = time()
        route = self._route_cognition(user_input)

        mode = route.get("mode")
        intent = self._get_structured_intent(user_input) or {}

        # A native tool route is executable without language generation.
        if mode == "tool" and self.skill_registry is not None:
            skill_name = intent.get("skill") or intent.get("name")
            executor = getattr(self.skill_executor, "execute", None)
            if skill_name and callable(executor):
                try:
                    result = executor(skill_name, user_input=user_input)
                    response = str(result)
                    self._enqueue_learning(
                        event_type="USER_CHAT_TOOL",
                        context={"user_input": user_input, "cognitive_route": route},
                        action={"skill": skill_name, "result": response},
                        outcome={"status": "completed"},
                        source=source,
                        importance=0.7,
                    )
                    if self.state is not None:
                        try:
                            self.state.record_response(response)
                        except Exception:
                            pass
                    self.last_turn_trace = {
                        "source": source,
                        "query": user_input,
                        "response_preview": response[:200],
                        "cognitive_route": route,
                        "llm_available": getattr(self, "llm", None) is not None,
                        "pipeline_success": True,
                        "timings": {"total": time() - turn_start, "memory": 0.0, "llm": 0.0},
                    }
                    return response
                except Exception as exc:
                    # Do not silently execute a different action. If an LLM is
                    # available it may recover the interaction as a fallback.
                    route = dict(route)
                    route["native_execution_error"] = str(exc)
                    self.last_cognitive_decision = route

        if mode == "clarify":
            response = "I need clarification before I can safely continue."
            self.last_turn_trace = {
                "source": source,
                "query": user_input,
                "response_preview": response,
                "cognitive_route": route,
                "llm_available": getattr(self, "llm", None) is not None,
                "pipeline_success": True,
                "timings": {"total": time() - turn_start, "memory": 0.0, "llm": 0.0},
            }
            return response

        # A known route currently still needs a language renderer because the
        # organism has no deterministic natural-language renderer yet. Keep the
        # route visible instead of pretending that an LLM-free answer exists.
        if mode == "known" and getattr(self, "llm", None) is None:
            response = "JARVIS has supporting knowledge, but its native language renderer is not available yet."
            self.last_turn_trace = {
                "source": source,
                "query": user_input,
                "response_preview": response,
                "cognitive_route": route,
                "llm_available": False,
                "pipeline_success": True,
                "timings": {"total": time() - turn_start, "memory": 0.0, "llm": 0.0},
            }
            return response

        # The LLM branch is the fallback for language cognition. BaseBrain owns
        # the existing Memory -> Experience -> Learning -> Evaluation ->
        # Knowledge -> Consolidation pipeline, so this patch does not bypass it.
        if getattr(self, "llm", None) is not None:
            response = super().think_and_respond(
                user_input, identity_profile=identity_profile, source=source
            )
            self._record_route_trace(route, llm_available=True)
            return response

        # No LLM: organism remains alive and records the degraded interaction.
        try:
            if self.events is not None:
                self.events.emit("USER_INPUT", {"text": user_input}, source=source)
        except Exception:
            pass

        try:
            self._enqueue_learning(
                event_type="USER_INPUT_DEGRADED",
                context={"user_input": user_input, "cognitive_route": route},
                action={"mode": "llm_unavailable"},
                outcome={"status": "received_without_llm"},
                source=source,
                importance=0.2,
            )
        except Exception:
            pass

        try:
            queue = self.status().get("async_learning_queue", {}) if hasattr(self, "status") else {}
        except Exception:
            queue = {}

        response = self._fallback_cognitive_response(user_input, source=source)
        self.last_turn_trace = {
            "source": source,
            "query": user_input,
            "response_preview": response[:200],
            "memory": {},
            "vector_matches": [],
            "learning_queue": queue,
            "cognitive_route": route,
            "pipeline_success": True,
            "llm_available": False,
            "timings": {"memory": 0.0, "llm": 0.0, "total": time() - turn_start},
            "memory_signal": None,
            "typos_corrected": [],
        }
        return response


def install_llm_optional_brain() -> None:
    """Compatibility no-op; bootstrap explicitly imports the adapter."""
    return None
