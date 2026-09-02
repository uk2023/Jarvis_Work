from __future__ import annotations

from typing import Any, Dict

from ..contracts import validate_input, validate_output
from .blueprint_brain import BlueprintBrain


class _ContractExperienceProxy:
    def __init__(self, target: Any, owner: "ContractEnforcedBlueprintBrain") -> None:
        self._target = target
        self._owner = owner

    def process(self, *, event_type: str, context=None, action=None, outcome=None, source: str = "unknown", importance: float = 0.5, **kwargs):
        context = dict(context or {})
        experience_input = validate_input("experience", {
            "user_input": str(context.get("user_input", "")),
            "semantic": dict(context.get("semantic") or {}),
            "routing": dict(context.get("routing") or context.get("route") or {}),
            "brain_result": dict(context.get("brain_result") or {}),
            "action_result": context.get("action_result"),
        })
        self._owner.last_experience_input = experience_input
        result = self._target.process(
            event_type=event_type,
            context=experience_input,
            action=action or {},
            outcome=outcome or {},
            source=source,
            importance=importance,
            **kwargs,
        )
        result_dict = dict(result or {}) if isinstance(result, dict) else {"result": result}
        experience_output = validate_output("experience", {
            "evaluation": dict(result_dict.get("evaluation") or {}),
            "experience": dict(result_dict.get("experience") or experience_input),
        })
        self._owner.last_experience_output = experience_output
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class _ContractLearningProxy:
    def __init__(self, target: Any, owner: "ContractEnforcedBlueprintBrain") -> None:
        self._target = target
        self._owner = owner

    def learn(self, *, experience, auto_accept=True, **kwargs):
        learning_input = validate_input("learning", {"experience": dict(experience or {})})
        self._owner.last_learning_input = learning_input
        result = self._target.learn(experience=learning_input["experience"], auto_accept=auto_accept, **kwargs)
        result_dict = dict(result or {}) if isinstance(result, dict) else {"result": result}
        knowledge = result_dict.get("knowledge")
        knowledge_updates = knowledge if isinstance(knowledge, list) else ([knowledge] if knowledge is not None else [])
        learning_output = validate_output("learning", {
            "learning_result": result_dict,
            "knowledge_updates": knowledge_updates,
        })
        self._owner.last_learning_output = learning_output
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class _ContractMemoryProxy:
    def __init__(self, target: Any, owner: "ContractEnforcedBlueprintBrain") -> None:
        self._target = target
        self._owner = owner

    def remember_knowledge(self, *args, **kwargs):
        learning_result = {"knowledge": dict(kwargs)}
        memory_input = validate_input("memory", {"learning_result": learning_result})
        self._owner.last_memory_input = memory_input
        result = self._target.remember_knowledge(*args, **kwargs)
        memory_context = result if isinstance(result, dict) else {"result": result}
        memory_output = validate_output("memory", {"memory_context": memory_context})
        self._owner.last_memory_output = memory_output
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class ContractEnforcedBlueprintBrain(BlueprintBrain):
    """BlueprintBrain with fail-closed runtime contract enforcement."""

    VERSION = "1.2.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_cognition_output = None
        self.last_router_input = None
        self.last_router_output = None
        self.last_brain_input = None
        self.last_brain_output = None
        self.last_experience_input = None
        self.last_experience_output = None
        self.last_learning_input = None
        self.last_learning_output = None
        self.last_memory_input = None
        self.last_memory_output = None
        if self.experience is not None and not isinstance(self.experience, _ContractExperienceProxy):
            self.experience = _ContractExperienceProxy(self.experience, self)
        if self.learning is not None and not isinstance(self.learning, _ContractLearningProxy):
            self.learning = _ContractLearningProxy(self.learning, self)
        if self.memory is not None and not isinstance(self.memory, _ContractMemoryProxy):
            self.memory = _ContractMemoryProxy(self.memory, self)

    def _build_cognition_input(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        cognition_input = super()._build_cognition_input(user_input, perception)
        self.last_cognition_output = validate_output("cognition", {
            "cognitive_context": cognition_input,
            "confidence": float((cognition_input.get("semantic") or {}).get("confidence", 0.0) or 0.0),
        })
        return cognition_input

    def _route_cognition(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        cognition_input = self._build_cognition_input(user_input, perception)
        router_input = validate_input("cognitive_router", {"cognitive_context": cognition_input})
        decision = self.cognitive_router.decide(
            user_input=user_input,
            cognition_input=router_input["cognitive_context"],
        )
        router_output = validate_output("cognitive_router", {
            "route": decision.mode,
            "confidence": decision.confidence,
            "fallback_allowed": decision.llm_required,
            "evidence": list((decision.evidence or {}).items()),
        })
        payload = decision.as_dict()
        payload.update({"route": router_output["route"], "fallback_allowed": router_output["fallback_allowed"]})
        self.last_router_input = router_input
        self.last_router_output = router_output
        self.last_cognitive_decision = payload
        self.last_brain_input = validate_input("brain", {
            "cognitive_context": cognition_input,
            "routing_decision": router_output,
        })
        return payload

    def _learn_turn(self, user_input: str, perception: Dict[str, Any], route: Dict[str, Any], decision: Dict[str, Any], action_response: Dict[str, Any], source: str) -> None:
        brain_output = validate_output("brain", {
            "decision": dict(decision),
            "action": action_response.get("action"),
            "response": action_response.get("response"),
        })
        self.last_brain_output = brain_output
        semantic = dict((self.last_cognition_input or {}).get("semantic") or perception.get("semantic_understanding") or {})
        experience_input = validate_input("experience", {
            "user_input": user_input,
            "semantic": semantic,
            "routing": dict(route),
            "brain_result": brain_output,
            "action_result": action_response.get("action"),
        })
        self.last_experience_input = experience_input
        outcome = dict(action_response or {})
        outcome["success"] = outcome.get("status") in {"completed", "planned"}
        self._enqueue_learning(
            event_type="USER_INTERACTION",
            context=experience_input,
            action=decision,
            outcome=outcome,
            source=source,
            importance=0.5,
        )

    def _run_learning_job(self, job: Dict[str, Any]) -> None:
        context = dict(job.get("context") or {})
        experience_input = validate_input("experience", {
            "user_input": str(context.get("user_input", "")),
            "semantic": dict(context.get("semantic") or {}),
            "routing": dict(context.get("routing") or context.get("route") or {}),
            "brain_result": dict(context.get("brain_result") or {}),
            "action_result": context.get("action_result"),
        })
        super()._run_learning_job({**job, "context": experience_input})
        learning_result = getattr(self.learning, "last_result", None) if self.learning is not None else None
        learning_result = dict(learning_result or {})
        experience_output = validate_output("experience", {
            "evaluation": dict(learning_result.get("evaluation") or {}),
            "experience": dict(learning_result.get("experience") or experience_input),
        })
        learning_input = validate_input("learning", {"experience": experience_output["experience"]})
        knowledge = learning_result.get("knowledge")
        knowledge_updates = knowledge if isinstance(knowledge, list) else ([knowledge] if knowledge is not None else [])
        learning_output = validate_output("learning", {
            "learning_result": learning_result,
            "knowledge_updates": knowledge_updates,
        })
        memory_input = validate_input("memory", {"learning_result": learning_output["learning_result"]})
        memory_context: Dict[str, Any] = {}
        memory = self.memory
        if memory is not None:
            status = getattr(memory, "status", None)
            if callable(status):
                try:
                    memory_context = dict(status() or {})
                except Exception:
                    memory_context = {}
        memory_output = validate_output("memory", {"memory_context": memory_context})
        self.last_experience_output = experience_output
        self.last_learning_input = learning_input
        self.last_learning_output = learning_output
        self.last_memory_input = memory_input
        self.last_memory_output = memory_output
