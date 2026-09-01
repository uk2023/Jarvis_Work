from __future__ import annotations

import time
import unittest

from core.organism.bootstrap import create_jarvis


class BrainIdleWiringTests(unittest.TestCase):
    """Verify the runtime path Heartbeat -> EventBus -> IdleLoop -> Brain."""

    def test_heartbeat_idle_event_reaches_idle_loop(self):
        jarvis = create_jarvis(heartbeat_interval=0.5, idle_threshold=0.5)
        idle_loop = jarvis.get_organ("idle_loop")
        self.assertIsNotNone(idle_loop)
        self.assertIs(jarvis.idle_loop, idle_loop)
        self.assertIs(idle_loop.executor, jarvis.get_organ("brain").execute_autonomous_step)

        calls = []
        original_step = idle_loop.step

        def spy_step():
            calls.append(True)
            return {"action": "TEST_IDLE_CYCLE"}

        idle_loop.step = spy_step
        try:
            # Force the organism into the idle condition without waiting
            # for a background heartbeat thread.
            jarvis.state.last_activity_at = time.time() - 10.0
            jarvis.heartbeat.running = True
            payload = jarvis.heartbeat.beat()

            self.assertTrue(payload["idle"])
            self.assertEqual(calls, [True])

            heartbeat_events = jarvis.event_bus.get_history("HEARTBEAT")
            self.assertTrue(heartbeat_events)
            self.assertTrue(heartbeat_events[-1].payload["idle"])
            self.assertEqual(
                jarvis.event_bus.get_subscribers("HEARTBEAT")["HEARTBEAT"],
                1,
            )
        finally:
            idle_loop.step = original_step
            jarvis.heartbeat.running = False

    def test_idle_loop_is_brain_owned(self):
        jarvis = create_jarvis()
        idle_loop = jarvis.get_organ("idle_loop")
        brain = jarvis.get_organ("brain")

        self.assertIsNotNone(idle_loop)
        self.assertIsNotNone(brain)
        self.assertIs(idle_loop.executor, brain.execute_autonomous_step)
        self.assertIs(jarvis.get_organ("perception"), brain.perception_engine)
        self.assertIs(jarvis.get_organ("cognitive_router"), brain.cognitive_router)


if __name__ == "__main__":
    unittest.main(verbosity=2)
