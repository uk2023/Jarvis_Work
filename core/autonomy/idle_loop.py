from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class IdleLoop:
    """
    Autonomous maintenance loop, run periodically by Heartbeat when
    the organism has no active user interaction.

    Safety model (unchanged from the original design intent):
      1. Curiosity proposes *candidates* (never executes anything).
      2. Planner turns the top candidate/goal into steps.
      3. Any step with requires_confirmation=True is NOT executed here
         — it is surfaced as a pending confirmation for the user.
      4. Steps that are safe to run are handed to the provided
         `executor` callback, and the outcome is logged as an episode.

    This class contains no model-loading and no direct file/network
    access itself — it only coordinates already-attached organs.
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

        # ---------------------------------------------------------
        # 0) Run anything the Scheduler says is due first.
        # ---------------------------------------------------------
        if self.scheduler is not None:
            for task in self.scheduler.due_tasks():
                self._run_task(task)

        # ---------------------------------------------------------
        # 1) Nothing to do if no goal_manager/curiosity attached yet.
        # ---------------------------------------------------------
        if self.goal_manager is None or self.curiosity is None or self.planner is None:
            return self._noop("autonomy organs not fully attached")

        goals = self.goal_manager.pending()

        candidates = self.curiosity.candidates(state=self.state, goals=goals)

        # Curiosity-sourced candidates become goals the first time
        # they're seen, so progress on them is tracked consistently.
        for candidate in candidates:
            self.goal_manager.add(
                text=candidate["reason"],
                priority=candidate.get("priority", 0.5),
                origin="curiosity",
            )

        target = self.goal_manager.next_goal()

        if target is None:
            return self._background_maintenance("no pending goals")

    def _background_maintenance(self, reason: str) -> Dict[str, Any]:
        """IDLE MUST NEVER SIT EMPTY (2026-09-13, UK: "idle me kabhi
        khali nahi baithega JARVIS ab").

        Previously a cycle with no pending goal returned a no-op and the
        organism did literally nothing until the next user message --
        which is why the monitor showed zero learning, zero
        consolidation, zero pattern work for hours at a stretch.

        There is always real maintenance available, so the cycle now
        works through a fixed backlog in priority order. Each task is
        cheap, bounded, and independently guarded: one failing task must
        not stop the rest, because a single bad consolidation should not
        silently disable all background work (exactly the failure mode
        that made this look broken).

        Deliberately NO LLM calls here -- idle work runs on the organism's
        own machinery, so a background cycle can never quietly eat the
        token budget UK is saving for conversation.
        """
        performed: List[Dict[str, Any]] = []

        def _try(label: str, fn) -> None:
            try:
                outcome = fn()
                performed.append({"task": label, "ok": True, "result": outcome})
            except Exception as exc:
                performed.append({"task": label, "ok": False, "error": str(exc)})

        brain = getattr(self, "brain", None)
        memory = getattr(brain, "memory", None) if brain is not None else None

        # 1. Episodic -> semantic consolidation. Now that chat turns are
        #    actually persisted as episodes, this has real material.
        consolidator = getattr(brain, "consolidator", None) if brain is not None else None
        if consolidator is not None and hasattr(consolidator, "consolidate"):
            _try("memory_consolidation", lambda: consolidator.consolidate(limit=50))

        # 2. Re-verify low-confidence knowledge gaps found this cycle.
        _try("knowledge_gap_scan", lambda: {"gaps": len(self._find_knowledge_gaps())})

        # 3. Learning-pattern review (time-gated internally).
        _try("learning_pattern_review", self._review_learning_patterns)

        # 4. Procedural memory: promote repeated habits.
        procedural = getattr(brain, "procedural_memory", None) if brain is not None else None
        if procedural is not None and hasattr(procedural, "promote_candidates"):
            _try("procedural_promotion", procedural.promote_candidates)

        # 5. Pattern synthesis: propose extraction patterns from misses.
        synthesis = getattr(brain, "pattern_synthesis", None) if brain is not None else None
        if synthesis is not None and hasattr(synthesis, "scan"):
            _try("pattern_synthesis", synthesis.scan)

        # 6. Memory decay: let unused personal facts fade, like real memory.
        if memory is not None and hasattr(memory, "decay_unused"):
            _try("memory_decay", memory.decay_unused)

        result = {
            "action": "IDLE_MAINTENANCE",
            "reason": reason,
            "tasks_run": len(performed),
            "tasks_succeeded": sum(1 for p in performed if p["ok"]),
            "performed": performed,
        }
        self._publish("IDLE_MAINTENANCE_COMPLETE", result)
        return result

        self.goal_manager.update_status(target["id"], "active")

        steps = self.planner.plan(target)

        executed = []
        confirmations_needed = []

        for step in steps[: self.max_actions_per_step]:
            if step.get("requires_confirmation"):
                confirmations_needed.append(step)
                self.pending_confirmations.append(
                    {**step, "goal_id": target["id"], "queued_at": time.time()}
                )
                continue

            outcome = self._run_step(target, step)
            executed.append(outcome)

        if executed and not confirmations_needed:
            self.goal_manager.add_progress(
                target["id"], f"Executed: {[s['action'] for s in executed]}"
            )

        if not steps:
            self.goal_manager.update_status(target["id"], "completed")

        result = {
            "action": "IDLE_CYCLE",
            "goal": target["text"],
            "executed": executed,
            "awaiting_confirmation": confirmations_needed,
        }

        self._publish("IDLE_CYCLE_COMPLETE", result)
        return result

    # =============================================================
    # INTERNAL
    # =============================================================

    def _run_step(self, goal: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        outcome = {"step": step, "status": "skipped", "result": None}

        if self.executor is None:
            outcome["status"] = "no_executor"
            return outcome

        try:
            result = self.executor(step)
            outcome["status"] = "success"
            outcome["result"] = result
        except Exception as exc:
            outcome["status"] = "error"
            outcome["result"] = str(exc)

        self._log_episode(goal, step, outcome)
        return outcome

    def _run_task(self, task: Dict[str, Any]) -> None:
        if self.executor is None:
            return
<<<<<<< HEAD

=======
        is_instruction = task.get("action") == "standing_instruction_fire"
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
        try:
            self.executor(task)
            # SILENT-FIRING FIX (2026-09-13, UK: "standing instruction
            # silently hit ho jata hai, UI ya trace ya kahin bhi iska
            # record nahi aata"). A scheduled action that runs with no
            # trace is indistinguishable from one that never ran, so
            # there was no way to tell a working scheduler from a dead
            # one. Every firing is now recorded with a timestamp and
            # outcome, readable via Brain.get_instruction_firings() and
            # therefore surfaceable in CLI/monitor/UI.
            if is_instruction:
                from ..orchestration.companion_tools import record_instruction_firing
                record_instruction_firing(
                    instruction_id=str(task.get("knowledge_id") or ""),
                    instruction_text=str(task.get("action_text") or ""),
                    trigger_type="scheduled",
                    outcome="fired",
                )
        except Exception as exc:
<<<<<<< HEAD
            print(f"[IdleLoop] Scheduled task failed: {exc}")

    def _log_episode(
        self,
        goal: Dict[str, Any],
        step: Dict[str, Any],
        outcome: Dict[str, Any],
    ) -> None:
        if self.store is None:
            return

        try:
            self.store.save_episode(
                {
                    "episode_id": f"idle-{time.time()}",
                    "timestamp": time.time(),
                    "event_type": "AUTONOMOUS_STEP",
                    "context": {"goal": goal.get("text")},
                    "action": step,
                    "outcome": outcome,
                    "importance": 0.3,
                    "confidence": 1.0 if outcome["status"] == "success" else 0.4,
                    "source": "idle_loop",
                }
            )
        except Exception as exc:
            print(f"[IdleLoop] Failed to log episode: {exc}")
=======
            if is_instruction:
                try:
                    from ..orchestration.companion_tools import record_instruction_firing
                    record_instruction_firing(
                        instruction_id=str(task.get("knowledge_id") or ""),
                        instruction_text=str(task.get("action_text") or ""),
                        trigger_type="scheduled",
                        outcome="failed",
                        detail=str(exc),
                    )
                except Exception:
                    pass
            self._publish("IDLE_SCHEDULED_TASK_FAILED", {"task": task, "error": str(exc)})
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

    def _noop(self, reason: str) -> Dict[str, Any]:
        result = {"action": "NO_OP", "reason": reason}
        self._publish("IDLE_CYCLE_NOOP", result)
        return result

    def _publish(self, name: str, payload: Any) -> None:
        if self.events is None:
            return

        emit = getattr(self.events, "emit", None)

        if callable(emit):
            try:
                emit(name, payload)
            except Exception as exc:
                print(f"[IdleLoop EventBus Error] {name}: {exc}")
