import unittest

from core.learning.learning_coordinator import LearningCoordinator
from core.skills.skill_learner import SkillLearner
from core.skills.skill_registry import SkillRegistry


class FakeEvaluator:
    def evaluate(self, experience):
        return {"score": 1.0, "success": bool(experience.get("success", True))}


class SkillActivationIntegrationTests(unittest.TestCase):
    def _experience(self):
        return {
            "event_type": "TOOL_ACTION",
            "context": {"goal": "check status"},
            "action": {"skill": "check_status", "detail": "read status"},
            "outcome": {"status": "SUCCESS", "detail": "online"},
            "success": True,
        }

    def test_repeated_verified_experiences_generate_proposal(self):
        learner = SkillLearner(min_repetitions=3, min_success_rate=0.8)
        for _ in range(3):
            proposals = learner.observe(self._experience())
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["status"], "proposed")

    def test_only_approved_proposal_can_enter_registry(self):
        learner = SkillLearner(min_repetitions=1)
        registry = SkillRegistry()
        coordinator = LearningCoordinator(
            evaluator=FakeEvaluator(), skill_learner=learner, skill_registry=registry
        )
        coordinator.learn(self._experience())

        with self.assertRaises(PermissionError):
            coordinator.activate_skill_proposal("skill_check_status", lambda: "ok")
        self.assertFalse(registry.is_registered("skill_check_status"))

        coordinator.approve_skill_proposal("skill_check_status")
        result = coordinator.activate_skill_proposal("skill_check_status", lambda: "ok")

        self.assertEqual(result["status"], "registered")
        self.assertEqual(learner.list_proposals("registered")[0]["name"], "skill_check_status")
        self.assertTrue(registry.is_registered("skill_check_status"))
        self.assertEqual(registry.get("skill_check_status")(), "ok")

    def test_registry_rejects_unapproved_direct_registration(self):
        registry = SkillRegistry()
        proposal = {"name": "skill_ping", "status": "proposed"}
        with self.assertRaises(PermissionError):
            registry.register_approved(proposal, lambda: "pong")
        self.assertFalse(registry.is_registered("skill_ping"))

    def test_approval_alone_does_not_register(self):
        learner = SkillLearner(min_repetitions=1)
        registry = SkillRegistry()
        coordinator = LearningCoordinator(evaluator=FakeEvaluator(), skill_learner=learner, skill_registry=registry)
        coordinator.learn({"action": {"skill": "ping"}, "outcome": {"status": "SUCCESS"}, "success": True})
        coordinator.approve_skill_proposal("skill_ping")
        self.assertFalse(registry.is_registered("skill_ping"))
        self.assertEqual(learner.list_proposals("approved")[0]["name"], "skill_ping")


if __name__ == "__main__":
    unittest.main()
