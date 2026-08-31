import unittest

from core.learning.learning_coordinator import LearningCoordinator
from core.skills.skill_learner import SkillLearner


class FakeEvaluator:
    def evaluate(self, experience):
        return {"score": 1.0, "success": bool(experience.get("success", True))}


class SkillLearningIntegrationTests(unittest.TestCase):
    def test_skill_learner_accepts_canonical_experience_and_proposes_after_repetition(self):
        learner = SkillLearner(min_repetitions=3, min_success_rate=0.8)
        experience = {
            "event_type": "TOOL_ACTION",
            "context": {"goal": "check status"},
            "action": {"skill": "check_status", "detail": "read status"},
            "outcome": {"status": "COMPLETED", "detail": "online"},
            "success": True,
        }

        self.assertEqual(learner.observe(experience), [])
        self.assertEqual(learner.observe(experience), [])
        proposals = learner.observe(experience)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["name"], "skill_check_status")
        self.assertEqual(proposals[0]["repetitions"], 3)
        self.assertEqual(proposals[0]["status"], "proposed")

    def test_chat_response_is_not_treated_as_a_learned_skill(self):
        learner = SkillLearner(min_repetitions=1)
        experience = {
            "action": {"jarvis_response": "hello"},
            "outcome": {"status": "COMPLETED"},
            "success": True,
        }
        self.assertEqual(learner.observe(experience), [])
        self.assertEqual(learner.statistics()["observed_experiences"], 0)

    def test_learning_coordinator_wires_skill_learner_without_registry_mutation(self):
        learner = SkillLearner(min_repetitions=1)
        coordinator = LearningCoordinator(
            evaluator=FakeEvaluator(),
            skill_learner=learner,
        )
        experience = {
            "event_type": "TOOL_ACTION",
            "context": {},
            "action": {"skill": "ping"},
            "outcome": {"status": "SUCCESS"},
            "success": True,
        }

        result = coordinator.learn(experience)

        self.assertTrue(result["success"])
        self.assertEqual(result["skill_proposals"][0]["name"], "skill_ping")
        self.assertEqual(coordinator.skill_observation_count, 1)
        self.assertEqual(coordinator.skill_proposal_count, 1)

    def test_skill_proposal_approval_does_not_execute_or_register_skill(self):
        learner = SkillLearner(min_repetitions=1)
        coordinator = LearningCoordinator(evaluator=FakeEvaluator(), skill_learner=learner)
        experience = {
            "event_type": "TOOL_ACTION",
            "context": {},
            "action": {"skill": "ping"},
            "outcome": {"status": "SUCCESS"},
            "success": True,
        }
        coordinator.learn(experience)

        approved = coordinator.approve_skill_proposal("skill_ping")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(learner.list_proposals("approved")[0]["name"], "skill_ping")


if __name__ == "__main__":
    unittest.main()
