from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class LearningCoordinator:
    """Central orchestration organ for controlled learning and skill proposals."""

    VERSION = "0.3.0"

    def __init__(
        self,
        evaluator=None,
        knowledge_builder=None,
        consolidator=None,
        memory_manager=None,
        event_bus=None,
        internal_state=None,
        skill_learner=None,
    ):
        self.evaluator = evaluator
        self.knowledge_builder = knowledge_builder
        self.consolidator = consolidator
        self.memory = memory_manager
        self.skill_learner = skill_learner
        self.events = event_bus
        self.state = internal_state

        self.learning_count = 0
        self.evaluation_count = 0
        self.knowledge_build_count = 0
        self.knowledge_accept_count = 0
        self.knowledge_reject_count = 0
        self.consolidation_count = 0
        self.skill_observation_count = 0
        self.skill_proposal_count = 0
        self.last_learning_at: Optional[float] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.running = True

    def learn(self, experience: Dict[str, Any], auto_accept: bool = False) -> Dict[str, Any]:
        if not self.running:
            raise RuntimeError("LearningCoordinator is stopped.")
        if not isinstance(experience, dict):
            raise TypeError("experience must be a dictionary")

        started_at = time.time()
        result: Dict[str, Any] = {
            "type": "LEARNING_CYCLE",
            "success": False,
            "experience": experience,
            "evaluation": None,
            "knowledge": None,
            "accepted": False,
            "skill_proposals": [],
            "duration": 0.0,
            "timestamp": None,
        }

        if self.evaluator is None:
            raise RuntimeError("SelfEvaluator is not connected.")

        evaluation = self.evaluator.evaluate(experience)
        result["evaluation"] = evaluation
        self.evaluation_count += 1

        if self.knowledge_builder is not None:
            candidate = self.knowledge_builder.build(experience=experience, evaluation=evaluation)
            result["knowledge"] = candidate
            if candidate is not None:
                self.knowledge_build_count += 1
                if auto_accept:
                    accepted = self.accept_knowledge(candidate["id"])
                    result["accepted"] = accepted.get("status") == "ACCEPTED"

        # Skill learning is deliberately separate from knowledge learning.
        # It observes only the canonical experience and produces proposals;
        # it never registers executable code in SkillRegistry.
        if self.skill_learner is not None:
            observe = getattr(self.skill_learner, "observe", None)
            if callable(observe):
                proposals = observe(experience)
                self.skill_observation_count += 1
                result["skill_proposals"] = proposals
                self.skill_proposal_count = len(
                    getattr(self.skill_learner, "list_proposals", lambda: [])()
                )
                if proposals:
                    self._emit("SKILL_PROPOSALS_GENERATED", {"proposals": proposals})

        self.learning_count += 1
        self.last_learning_at = time.time()
        result["success"] = True
        result["duration"] = time.time() - started_at
        result["timestamp"] = self.last_learning_at
        self.last_result = result
        self._emit("LEARNING_COMPLETED", result)
        return result

    def evaluate(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        if not self.running:
            raise RuntimeError("LearningCoordinator is stopped.")
        if self.evaluator is None:
            raise RuntimeError("SelfEvaluator is not connected.")
        result = self.evaluator.evaluate(experience)
        self.evaluation_count += 1
        self._emit("LEARNING_EVALUATION_COMPLETED", result)
        return result

    def build_knowledge(self, experience: Dict[str, Any], evaluation: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")
        if evaluation is None:
            evaluation = self.evaluate(experience)
        candidate = self.knowledge_builder.build(experience=experience, evaluation=evaluation)
        if candidate is not None:
            self.knowledge_build_count += 1
            self._emit("LEARNING_KNOWLEDGE_BUILT", candidate)
        return candidate

    def accept_knowledge(self, knowledge_id: str) -> Dict[str, Any]:
        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")
        candidate = self.knowledge_builder.accept(knowledge_id)
        if candidate.get("status") == "ACCEPTED":
            self.knowledge_accept_count += 1
            self._emit("LEARNING_KNOWLEDGE_ACCEPTED", candidate)
        return candidate

    def reject_knowledge(self, knowledge_id: str, reason: str = "") -> Dict[str, Any]:
        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")
        candidate = self.knowledge_builder.reject(knowledge_id=knowledge_id, reason=reason)
        self.knowledge_reject_count += 1
        self._emit("LEARNING_KNOWLEDGE_REJECTED", candidate)
        return candidate

    def list_skill_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.skill_learner is None:
            return []
        method = getattr(self.skill_learner, "list_proposals", None)
        return method(status=status) if callable(method) else []

    def approve_skill_proposal(self, name: str) -> Dict[str, Any]:
        if self.skill_learner is None:
            raise RuntimeError("SkillLearner is not connected.")
        method = getattr(self.skill_learner, "approve", None)
        if not callable(method):
            raise RuntimeError("SkillLearner does not expose approve().")
        result = method(name)
        self._emit("SKILL_PROPOSAL_APPROVED", result)
        return result

    def reject_skill_proposal(self, name: str, reason: str = "") -> Dict[str, Any]:
        if self.skill_learner is None:
            raise RuntimeError("SkillLearner is not connected.")
        method = getattr(self.skill_learner, "reject", None)
        if not callable(method):
            raise RuntimeError("SkillLearner does not expose reject().")
        result = method(name, reason=reason)
        self._emit("SKILL_PROPOSAL_REJECTED", result)
        return result

    def consolidate(self, limit: int = 50) -> Dict[str, Any]:
        if self.consolidator is None:
            raise RuntimeError("MemoryConsolidator is not connected.")
        result = self.consolidator.consolidate(limit=limit)
        self.consolidation_count += 1
        self._emit("LEARNING_CONSOLIDATION_COMPLETED", result)
        return result

    def learn_and_consolidate(self, experience: Dict[str, Any], auto_accept: bool = False, consolidation_limit: int = 50) -> Dict[str, Any]:
        learning = self.learn(experience=experience, auto_accept=auto_accept)
        consolidation = self.consolidate(limit=consolidation_limit)
        return {"learning": learning, "consolidation": consolidation, "timestamp": time.time()}

    def get_candidate(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        if self.knowledge_builder is None:
            return None
        getter = getattr(self.knowledge_builder, "get", None)
        return getter(knowledge_id) if callable(getter) else None

    def list_candidates(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if self.knowledge_builder is None:
            return []
        method = getattr(self.knowledge_builder, "list_knowledge", None)
        return method(status=status, limit=limit) if callable(method) else []

    def status(self) -> Dict[str, Any]:
        def safe_status(obj, method_name):
            if obj is None:
                return {}
            method = getattr(obj, method_name, None)
            if not callable(method):
                return {}
            try:
                return method()
            except Exception as exc:
                return {"error": str(exc)}

        return {
            "version": self.VERSION,
            "running": self.running,
            "learning_count": self.learning_count,
            "evaluation_count": self.evaluation_count,
            "knowledge_build_count": self.knowledge_build_count,
            "knowledge_accept_count": self.knowledge_accept_count,
            "knowledge_reject_count": self.knowledge_reject_count,
            "consolidation_count": self.consolidation_count,
            "skill_observation_count": self.skill_observation_count,
            "skill_proposal_count": self.skill_proposal_count,
            "last_learning_at": self.last_learning_at,
            "evaluator": safe_status(self.evaluator, "statistics"),
            "knowledge_builder": safe_status(self.knowledge_builder, "statistics"),
            "consolidator": safe_status(self.consolidator, "status"),
            "skill_learner": safe_status(self.skill_learner, "statistics"),
        }

    def reset_statistics(self) -> None:
        self.learning_count = 0
        self.evaluation_count = 0
        self.knowledge_build_count = 0
        self.knowledge_accept_count = 0
        self.knowledge_reject_count = 0
        self.consolidation_count = 0
        self.skill_observation_count = 0
        self.skill_proposal_count = 0
        self.last_learning_at = None
        self.last_result = None

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def _emit(self, event_name: str, payload: Any = None) -> None:
        if self.events is None:
            return
        safe_emit = getattr(self.events, "safe_emit", None)
        if callable(safe_emit):
            safe_emit(event_name, payload, source="learning_coordinator")
