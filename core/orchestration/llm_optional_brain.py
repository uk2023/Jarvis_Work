# -*- coding: utf-8 -*-
"""LLM-optional Brain adapter: perception -> routing -> action/LLM."""
from time import time
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain
from .cognitive_router import CognitiveRouter
from .perception import PerceptionEngine, LLMPerceptionProvider
from ..skills.skill_executor import SkillExecutor


class LLMOptionalBrain(BaseBrain):
    """Brain whose language cognition is a replaceable perception provider."""
    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+perception-router"

    def __init__(self, *args, cognitive_router=None, perception_engine=None, skill_registry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None
        self.perception = perception_engine or PerceptionEngine(state=self.state)
        if self.llm is not None:
            self.set_llm_bridge(self.llm)
        self.last_cognitive_decision: Optional[Dict[str, Any]] = None
        self.last_perception: Optional[Dict[str, Any]] = None
        self.last_brain_decision: Optional[Dict[str, Any]] = None
        self.last_action_response: Optional[Dict[str, Any]] = None

    def _emit(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """Publish lifecycle telemetry without coupling Brain to consumers."""
        if self.events is None:
            return
        try:
            self.events.safe_emit(name, payload or {}, source="brain")
        except Exception:
            pass

    def set_llm_bridge(self, llm_bridge: Any) -> None:
        self.llm = llm_bridge
        self.perception.providers = [p for p in self.perception.providers if getattr(p, "name", None) != "llm"]
        if llm_bridge is not None:
            self.perception.add_provider(LLMPerceptionProvider(llm_bridge))

    def attach_skill_registry(self, skill_registry: Any) -> None:
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None

    def _perceive(self, user_input: str) -> Dict[str, Any]:
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        result = self.perception.perceive(user_input, context=context)
        payload = result.as_dict()
        self.last_perception = payload
        self._emit("PERCEPTION_COMPLETED", {"user_input": user_input, "perception": payload})
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
                self.state.update(last_route=decision.mode, confidence=decision.confidence, uncertainty=1.0 - decision.confidence)
            except Exception:
                pass
        self._emit("COGNITION_ROUTED", {"user_input": user_input, "decision": payload})
        return payload

    def _record_action_response(self, *, mode: str, status: str, response: Any, action: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> str:
        """Commit the Brain decision into one explicit action/response contract."""
        response_text = str(response)
        record: Dict[str, Any] = {"mode": mode, "status": status, "response": response_text}
        if action is not None:
            record["action"] = action
        if error is not None:
            record["error"] = error
        self.last_action_response = record
        self._emit("ACTION_RESPONSE_COMPLETED", record)
        return response_text

    def _trace(self, user_input: str, response: str, route: Dict[str, Any], perception: Dict[str, Any], started: float, llm: bool) -> None:
        self.last_turn_trace = {
            "source": "brain",
            "query": user_input,
            "response_preview": response[:200],
            "perception": perception,
            "cognitive_route": route,
            "brain_decision": self.last_brain_decision,
            "action_response": self.last_action_response,
            "llm_available": llm,
            "pipeline_success": True,
            "timings": {"total": time() - started, "memory": 0.0, "llm": 0.0},
        }
        self._emit("BRAIN_CYCLE_COMPLETED", {"trace": self.last_turn_trace})

    def _fallback(self, user_input: str) -> str:
        lower = (user_input or "").strip().lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        return "JARVIS received the input, but no language cognition provider is currently available. Core organism remains active."

    def _hybrid_synthesize(self, user_input: str, skill_name: str, native_result: Any, source: str) -> str:
        """Native capability executes first; LLM only interprets the result."""
        if self.llm is None:
            return str(native_result)
        system_prompt = (
            "You are JARVIS's response synthesizer. A native organism skill has already "
            "executed successfully. Do not invent actions or claim to execute anything. "
            "Return a concise user-facing response based only on the native result."
        )
        synthesis_input = f"User request: {user_input}\nNative skill: {skill_name}\nNative result: {native_result}"
        try:
            generate_combined = getattr(self.llm, "generate_combined", None)
            if callable(generate_combined):
                combined = generate_combined(system_prompt=system_prompt, user_input=synthesis_input)
                if isinstance(combined, dict) and combined.get("response"):
                    return str(combined["response"])
            generate = getattr(self.llm, "generate", None)
            if callable(generate):
                return str(generate(system_prompt, synthesis_input)).strip()
        except Exception as exc:
            self.last_brain_decision = {"mode": "hybrid", "status": "native_success_llm_synthesis_failed", "error": str(exc)}
        return str(native_result)

    def think_and_respond(self, user_input: str, identity_profile: Optional[Dict[str, Any]] = None, source: str = "cli") -> str:
        started = time()
        self._emit("BRAIN_CYCLE_STARTED", {"user_input": user_input, "source": source})
        perception = self._perceive(user_input)
        route = self._route_cognition(user_input, perception)
        mode = route.get("mode")
        intent = perception.get("intent") or {}

        if mode == "tool" and self.skill_executor is not None:
            skill_name = intent.get("skill") or intent.get("name")
            if skill_name:
                try:
                    response = self.skill_executor.execute(skill_name, user_input=user_input)
                    self.last_brain_decision = {"mode": "native", "status": "executed", "skill": skill_name, "action_result": str(response)}
                    response = self._record_action_response(mode="native", status="completed", response=response, action={"skill": skill_name, "result": str(response)})
                    self._enqueue_learning(event_type="USER_CHAT_TOOL", context={"user_input": user_input, "perception": perception, "cognitive_route": route}, action={"skill": skill_name, "result": response}, outcome={"status": "completed"}, source=source, importance=0.7)
                    self._trace(user_input, response, route, perception, started, self.llm is not None)
                    return response
                except Exception as exc:
                    route = dict(route)
                    route["native_execution_error"] = str(exc)
                    self.last_cognitive_decision = route
                    self._emit("ACTION_RESPONSE_FAILED", {"mode": "native", "error": str(exc), "user_input": user_input})

        if mode == "hybrid" and self.skill_executor is not None:
            skill_name = intent.get("skill") or intent.get("name")
            if skill_name:
                try:
                    native_result = self.skill_executor.execute(skill_name, user_input=user_input)
                    response = self._hybrid_synthesize(user_input, skill_name, native_result, source)
                    self.last_brain_decision = {"mode": "hybrid", "status": "completed", "native_skill": skill_name, "native_result": str(native_result), "response": response}
                    response = self._record_action_response(mode="hybrid", status="completed", response=response, action={"skill": skill_name, "result": str(native_result), "mode": "hybrid"})
                    self._enqueue_learning(event_type="USER_CHAT_HYBRID", context={"user_input": user_input, "perception": perception, "cognitive_route": route}, action={"skill": skill_name, "result": str(native_result), "mode": "hybrid"}, outcome={"status": "completed", "response": response}, source=source, importance=0.8)
                    self._trace(user_input, response, route, perception, started, self.llm is not None)
                    return response
                except Exception as exc:
                    self.last_brain_decision = {"mode": "hybrid", "status": "native_execution_failed", "error": str(exc)}
                    route = dict(route)
                    route["native_execution_error"] = str(exc)
                    self._emit("ACTION_RESPONSE_FAILED", {"mode": "hybrid", "error": str(exc), "user_input": user_input})

        if mode == "clarify":
            response = self._record_action_response(mode="clarify", status="blocked_pending_confirmation", response="I need clarification before I can safely continue.")
            self.last_brain_decision = {"mode": "clarify", "status": "blocked_pending_confirmation"}
            self._trace(user_input, response, route, perception, started, self.llm is not None)
            return response

        if mode == "llm" and self.llm is not None:
            response = super().think_and_respond(user_input, identity_profile=identity_profile, source=source)
            self.last_brain_decision = {"mode": "llm", "status": "completed"}
            response = self._record_action_response(mode="llm", status="completed", response=response)
            self._trace(user_input, response, route, perception, started, True)
            return response

        if mode == "known" and self.llm is None:
            response = self._record_action_response(mode="known", status="knowledge_only", response="JARVIS has supporting knowledge, but no native language renderer is available yet.")
            self.last_brain_decision = {"mode": "known", "status": "knowledge_only"}
            self._trace(user_input, response, route, perception, started, False)
            return response

        response = self._fallback(user_input)
        try:
            self._enqueue_learning(event_type="USER_INPUT_DEGRADED", context={"user_input": user_input, "perception": perception, "cognitive_route": route}, action={"mode": "llm_unavailable"}, outcome={"status": "received_without_llm"}, source=source, importance=0.2)
        except Exception:
            pass
        self.last_brain_decision = {"mode": "fallback", "status": "degraded"}
        response = self._record_action_response(mode="fallback", status="degraded", response=response)
        self._trace(user_input, response, route, perception, started, False)
        return response


def install_llm_optional_brain() -> None:
    return None
