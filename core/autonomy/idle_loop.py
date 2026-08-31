from __future__ import annotations

import time
from typing import Any, Dict, List


class IdleLoop:
    """
    Autonomous maintenance loop, run periodically by Heartbeat when
    the organism has no active user interaction.

    Safety model:
      1. Curiosity proposes candidates; it never executes anything.
      2. Planner turns the selected goal into structured steps.
      3. Confirmation-required steps are surfaced as pending confirmation.
      4. Safe steps are handed to the Brain-owned executor.

    The executor is the Brain boundary. IdleLoop does not execute skills,
    create experiences, or write learning records itself.
    """

    def __init__(
        self,
        goal_manager=None,
        curiosity=None,
        planner=None,
        scheduler=None,
        state=None,
        event_bus=None,
        store=None,
        executor=None,
        max_actions_per_step: int = 1,
    ):
        self.goal_manager = goal_manager
        self.curiosity = curiosity
        self.planner = planner
        self.scheduler = scheduler
        self.state = state
        self.events = event_bus
        self.store = store
        self.executor = executor
        self.max_actions_per_step = max_actions_per_step
        self.pending_confirmations: List[Dict[str, Any]] = []

    def step(self) -> Dict[str, Any]:
        """Run exactly one idle cycle. Called by Heartbeat/Scheduler."""
        if self.scheduler is not None:
            for task in self.scheduler.due_tasks():
                self._run_task(task)

        if self.goal_manager is None or self.curiosity is None or self.planner is None:
            return self._noop("autonomy organs not fully attached")

        goals = self.goal_manager.pending()
        candidates = self.curiosity.candidates(state=self.state, goals=goals)

        for candidate in candidates:
            self.goal_manager.add(
                text=candidate["reason"],
                priority=candidate.get("priority", 0.5),
                origin="curiosity",
            )

        target = self.goal_manager.next_goal()
        if target is None:
            return self._noop("no pending goals")

        self.goal_manager.update_status(target["id"], "active")

        # A goal owns its plan and cursor so repeated idle cycles continue
        # from the next step instead of executing step 1 forever.
        plan = target.get("plan") or []
        step_index = int(target.get("step_index", 0))
        if not plan or step_index >= len(plan):
            plan = self.planner.plan(target)
            self.goal_manager.set_plan(target["id"], plan)
            target = self.goal_manager._find(target["id"]) or target
            step_index = int(target.get("step_index", 0))

        executed = []
        confirmations_needed = []

        for planned_step in plan[step_index : step_index + self.max_actions_per_step]:
            if planned_step.get("requires_confirmation"):
                confirmations_needed.append(planned_step)
                self.pending_confirmations.append(
                    {**planned_step, "goal_id": target["id"], "queued_at": time.time()}
                )
                continue

            outcome = self._run_step(target, planned_step)
            executed.append(outcome)

            if outcome.get("success") is True:
                self.goal_manager.advance_step(target["id"])
                self.goal_manager.add_progress(
                    target["id"], f"Executed: {planned_step.get('action')}"
                )
            else:
                # Failed work remains at the current cursor so a later cycle
                # can retry/recover instead of falsely completing the goal.
                self.goal_manager.add_progress(
                    target["id"], f"Failed: {planned_step.get('action')}"
                )

        refreshed = self.goal_manager._find(target["id"]) or target
        refreshed_index = int(refreshed.get("step_index", 0))
        if plan and refreshed_index >= len(plan):
            self.goal_manager.update_status(target["id"], "completed")
        elif confirmations_needed:
            self.goal_manager.add_progress(
                target["id"], "Awaiting explicit confirmation before continuing."
            )

        result = {
            "action": "IDLE_CYCLE",
            "goal": target["text"],
            "goal_id": target["id"],
            "step_index": refreshed_index,
            "executed": executed,
            "awaiting_confirmation": confirmations_needed,
        }
        self._publish("IDLE_CYCLE_COMPLETE", result)
        return result

    def _run_step(self, goal: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        if self.executor is None:
            return {"success": False, "status": "no_executor", "step": step}

        try:
            return self.executor(step, goal=goal)
        except TypeError as exc:
            # Compatibility with older executor callables that accept only
            # the step. The production Brain executor accepts the goal too.
            try:
                return self.executor(step)
            except Exception as fallback_exc:
                return {"success": False, "status": "error", "result": str(fallback_exc), "step": step}
        except Exception as exc:
            return {"success": False, "status": "error", "result": str(exc), "step": step}

    def _run_task(self, task: Dict[str, Any]) -> None:
        if self.executor is None:
            return
        try:
            self.executor(task)
        except Exception as exc:
            self._publish("IDLE_SCHEDULED_TASK_FAILED", {"task": task, "error": str(exc)})

    def _noop(self, reason: str) -> Dict[str, Any]:
        result = {"action": "NO_OP", "reason": reason}
        self._publish("IDLE_CYCLE_NOOP", result)
        return result

    def _publish(self, name: str, payload: Any) -> None:
        if self.events is None:
            return

        emit = getattr(self.events, "safe_emit", None) or getattr(self.events, "emit", None)
        if callable(emit):
            try:
                emit(name, payload, source="idle_loop")
            except TypeError:
                try:
                    emit(name, payload)
                except Exception:
                    pass
            except Exception:
                pass
