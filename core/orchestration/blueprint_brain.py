from __future__ import annotations

import time
from typing import Any, Dict, Optional

from ..contracts import validate_input
from .brain import Brain


class BlueprintBrain(Brain):
    """Blueprint-authoritative Brain runtime.

    Runtime order:
    Perception -> Semantic Understanding -> Cognition -> Cognitive Router ->
    Native/Hybrid/LLM execution -> Response -> Experience/Learning.

    The inherited Brain remains the compatibility organ. This class is the
    locked runtime entry point used by organism bootstrap.
    """

    VERSION = "1.1.0"

    def _build_cognition_input(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble canonical Cognition input from semantic output and context."""
        semantic = dict(perception.get("semantic_understanding") or {})
        if not semantic:
            raise RuntimeError("Semantic Understanding result is required before Cognition")
        context = self.build_context(query=semantic.get("normalized_text") or user_input, recent_limit=3)
        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]
        state = {}
        if self.state is not None:
            snapshot = getattr(self.state, "snapshot", None)
            if callable(snapshot):
                try:
                    state = dict(snapshot() or {})
                except Exception:
                    state = {}
        capabilities = {"skills": getattr(self.skill_registry, "skills", {})}
        cognition_input = validate_input("cognition", {
            "semantic": semantic,
            "memory": context,
            "knowledge": {"relevant_knowledge": context.get("relevant_knowledge", [])},
            "goals": goals,
            "state": state,
            "capabilities": capabilities,
            "experience": context.get("recent_experiences", []),
        })
        self.last_cognition_input = cognition_input
        return cognition_input

    def _route_cognition(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Run Cognition first; Router receives only canonical cognition.input."""
        cognition_input = self._build_cognition_input(user_input, perception)
        decision = self.cognitive_router.decide(user_input=user_input, cognition_input=cognition_input)
        payload = decision.as_dict()
        self.last_cognitive_decision = payload
        if self.state is not None:
            try:
                self.state.update(last_route=decision.mode, confidence=decision.confidence, uncertainty=1.0 - decision.confidence)
            except Exception:
                pass
        self._emit("COGNITION_ROUTED", {"user_input": user_input, "cognition_input": cognition_input, "decision": payload})
        return payload

    def think_and_respond(self, user_input: str,
                          identity_profile: Optional[Dict[str, Any]] = None,
                          source: str = "cli") -> str:
        started = time.time()
        user_input = str(user_input or "").strip()
        self._emit("BRAIN_CYCLE_STARTED", {"source": source, "user_input": user_input})
        perception = self._perceive(user_input)
        route = self._route_cognition(user_input, perception)
        cognition_input = self.last_cognition_input or {}
        semantic = cognition_input.get("semantic") or perception.get("semantic_understanding") or {}
        intent = semantic.get("intent") if isinstance(semantic.get("intent"), dict) else {}
        skill_name = intent.get("skill") or intent.get("name")
        perceived_goal = semantic.get("goal") or intent.get("goal") or perception.get("goal")

        if route.get("mode") == "goal":
            result = self._register_and_plan_goal(perceived_goal)
            response = "Goal accepted and planned." if result.get("status") == "planned" else "Goal could not be planned."
            status = result.get("status", "failed")
            decision = {"route": "goal", "status": status, "goal": result.get("goal"), "plan": result.get("plan", [])}
            self.last_brain_decision = decision
            self._record_action_response(mode="native", status=status, response=response, action=decision)
            self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
            self._trace(user_input, response, route, perception, started, False)
            return response

        mode = str(route.get("mode", "llm")).lower()
        if mode in {"tool", "native"}:
            if self.skill_executor is None or not skill_name:
                response = self._fallback(user_input)
                decision = {"route": "native", "status": "capability_unavailable", "skill": skill_name}
                self.last_brain_decision = decision
                self._record_action_response(mode="native", status="failed", response=response, action=decision, error="capability_not_available")
                self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                self._trace(user_input, response, route, perception, started, False)
                return response
            try:
                result = self.skill_executor.execute(skill_name, user_input=user_input)
                response = str(result)
                decision = {"route": "native", "status": "completed", "skill": skill_name, "result": response}
                self.last_brain_decision = decision
                self._record_action_response(mode="native", status="completed", response=response, action=decision)
                self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                self._trace(user_input, response, route, perception, started, False)
                return response
            except Exception as exc:
                response = f"[Native action failed: {exc}]"
                decision = {"route": "native", "status": "failed", "skill": skill_name, "error": str(exc)}
                self.last_brain_decision = decision
                self._record_action_response(mode="native", status="failed", response=response, action=decision, error=str(exc))
                self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                self._trace(user_input, response, route, perception, started, False)
                return response

        if mode == "hybrid":
            if self.skill_executor is None or not skill_name:
                mode = "llm"
            else:
                try:
                    native_result = self.skill_executor.execute(skill_name, user_input=user_input)
                    response = self._hybrid_synthesize(user_input, skill_name, native_result, source)
                    decision = {"route": "hybrid", "status": "completed", "skill": skill_name, "native_result": str(native_result)}
                    self.last_brain_decision = decision
                    self._record_action_response(mode="hybrid", status="completed", response=response, action=decision)
                    self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                    self._trace(user_input, response, route, perception, started, True)
                    return response
                except Exception as exc:
                    response = f"[Hybrid execution failed: {exc}]"
                    decision = {"route": "hybrid", "status": "failed", "skill": skill_name, "error": str(exc)}
                    self.last_brain_decision = decision
                    self._record_action_response(mode="hybrid", status="failed", response=response, action=decision, error=str(exc))
                    self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                    self._trace(user_input, response, route, perception, started, self.llm is not None)
                    return response

        if mode == "known":
            context = self.build_context(query=semantic.get("normalized_text", user_input), recent_limit=3)
            facts = context.get("relevant_knowledge", [])
            if facts:
                fact = facts[0] if isinstance(facts[0], dict) else {}
                response = self._format_fact(fact)
                decision = {"route": "native", "status": "completed", "source": "semantic_memory", "evidence": fact}
                self.last_brain_decision = decision
                self._record_action_response(mode="native", status="completed", response=response, action=decision)
                self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                self._trace(user_input, response, route, perception, started, False)
                return response
            mode = "llm"

        if mode == "llm":
            if self.llm is None:
                response = self._fallback(user_input)
                decision = {"route": "llm_fallback", "status": "provider_unavailable"}
                self.last_brain_decision = decision
                self._record_action_response(mode="llm", status="degraded", response=response, action=decision)
                self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
                self._trace(user_input, response, route, perception, started, False)
                return response
            context = self.build_context(query=semantic.get("normalized_text", user_input), recent_limit=3)
            prompt = ("Respond to the user using the supplied organism context. "
                      "The LLM is a fallback cognition capability only. Do not execute actions, "
                      "do not claim an action happened unless the action result is present, and "
                      "do not invent facts.")
            payload = f"Context: {context}\nUser: {user_input}"
            try:
                generate = getattr(self.llm, "generate", None)
                response = str(generate(prompt, payload) if callable(generate) else self.llm.generate_response(system_prompt=prompt, user_input=payload)).strip()
                response = response or "..."
                decision = {"route": "llm_fallback", "status": "completed"}
            except Exception as exc:
                response = f"[LLM fallback failed: {exc}]"
                decision = {"route": "llm_fallback", "status": "failed", "error": str(exc)}
            self.last_brain_decision = decision
            self._record_action_response(mode="llm", status=decision["status"], response=response, action=decision)
            self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
            self._trace(user_input, response, route, perception, started, True)
            return response

        response = self._fallback(user_input)
        decision = {"route": mode, "status": "unsupported_route"}
        self.last_brain_decision = decision
        self._record_action_response(mode=mode, status="failed", response=response, action=decision)
        self._learn_turn(user_input, perception, route, decision, self.last_action_response, source)
        self._trace(user_input, response, route, perception, started, self.llm is not None)
        return response

    def _format_fact(self, fact: Dict[str, Any]) -> str:
        subject = fact.get("subject")
        predicate = fact.get("predicate")
        value = fact.get("value")
        if subject and predicate and value is not None:
            return f"{subject} {predicate}: {value}"
        return str(fact.get("content") or fact)

    def _learn_turn(self, user_input: str, perception: Dict[str, Any], route: Dict[str, Any], decision: Dict[str, Any], action_response: Dict[str, Any], source: str) -> None:
        outcome = dict(action_response or {})
        outcome["success"] = outcome.get("status") in {"completed", "planned"}
        self._enqueue_learning(
            event_type="USER_INTERACTION",
            context={
                "user_input": user_input,
                "semantic": dict(self.last_cognition_input or {}).get("semantic", perception.get("semantic_understanding", {})),
                "perception": perception,
                "route": route,
            },
            action=decision,
            outcome=outcome,
            source=source,
            importance=0.5,
        )
