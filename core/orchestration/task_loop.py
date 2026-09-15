from __future__ import annotations

"""ONE LOOP: THINK, ACT, VERIFY, CONCLUDE.

UK (2026-09-14): "extended thinking step turn multi turn sab ek hi
ho... Claude ki tarah think karke, beech mein jitne turns lena, aur
task end tak complete karna."

He is right that these were three things pretending to be one feature:

    thinking.py     reasoned in stages and then answered
    step_goals.py   planned steps and executed them
    codebox.py      iterated on code until it ran

Each was reachable separately, none knew about the others, and none of
them finished a task -- thinking stopped at an answer, step_goals
stopped at a plan-with-outputs. So "calculator bana do" produced either
prose about a calculator or a list of steps describing one, never a
calculator that ran.

THE LOOP
========
    UNDERSTAND  what is being asked, what is assumed, what "done" means
    PLAN        concrete steps, typed (code / write / verify / system)
    EXECUTE     each step; code steps ACTUALLY RUN in the sandbox
    VERIFY      check the result against the done-criteria from step 1
    CONCLUDE    what was built, what works, what did not

Every stage is emitted as an event, so the same run drives the CLI
panel and the frontend ThinkingSteps panel. One implementation, two
surfaces -- the previous split is how they drifted apart.

WHAT STOPS IT RUNNING AWAY
==========================
A loop that calls an LLM per step can burn a turn's budget in seconds
and, on a phone, take the process down with it. So:

  * the budget is checked BEFORE each step, not after;
  * MAX_STEPS is a hard cap, not a suggestion;
  * a failed verify retries ONCE, then reports honestly rather than
    looping on a problem it is not solving.

Stopping early with partial work and saying so is better than an
elegant loop that never terminates. UK has seen "Thought for 26.7s"
followed by a crash; that must not be reachable from here.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

from ..runtime.log import log_event

MAX_STEPS = 100     # absolute ceiling -- effort_levels.py's per-level caps sit under this
MIN_BUDGET_TO_CONTINUE = 2
MAX_VERIFY_RETRIES = 1

KIND_CODE = "code"
KIND_WRITE = "write"
KIND_VERIFY = "verify"
KIND_SYSTEM = "system"
_KINDS = {KIND_CODE, KIND_WRITE, KIND_VERIFY, KIND_SYSTEM}


@dataclass
class TaskStep:
    index: int
    kind: str
    description: str
    output: str = ""
    ok: bool = True
    executed: bool = False
    held: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index, "kind": self.kind, "description": self.description,
            "output": self.output[:2500], "ok": self.ok, "executed": self.executed,
            "held": self.held, "detail": self.detail,
            "duration_ms": round(self.duration_ms, 1),
        }


def _parse_json_list(raw: str) -> Optional[List[Dict[str, Any]]]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.I | re.M)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else None
    except Exception:
        return None


class TaskLoop:
    """Runs one task from request to finished result."""

    def __init__(self, generate: Callable, *, brain: Any = None,
                 role: str = "user", is_verified: bool = False,
                 effort: str = "medium"):
        self.generate = generate
        self.brain = brain
        self.role = (role or "user").lower()
        self.is_verified = bool(is_verified)
        self.steps: List[TaskStep] = []

        # EFFORT (2026-09-14, UK's 5-level spec). One dial drives both
        # this loop's step cap/retries AND thinking.py's stage count --
        # see core/orchestration/effort_levels.py for why they must move
        # together rather than being two settings a person has to
        # remember to align.
        from .effort_levels import profile_for
        self.effort = profile_for(effort)

    # ------------------------------------------------------------ budget
    def _remaining_calls(self) -> int:
        try:
            return int(self.brain.llm.budget_status().get("remaining_calls", 0))
        except Exception:
            return MIN_BUDGET_TO_CONTINUE + 1      # unknown: allow, cap still applies

    def _call(self, system: str, user: str, max_tokens: int = 900) -> str:
        return str(self.generate(
            system_prompt=system, user_input=user,
            max_tokens=max_tokens, level="response_generation",
        )).strip()

    # ------------------------------------------------------------- stages
    def _understand(self, task: str) -> Dict[str, Any]:
        try:
            raw = self._call(
                "You are JARVIS, about to carry out a task for UK. Return ONLY JSON: "
                '{"goal": "...", "assumptions": ["..."], "done_when": ["..."]}. '
                "done_when must be CHECKABLE conditions, not restatements of the goal.",
                f"Task: {task}",
                500,
            )
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.M)
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # Fall back to the task itself rather than inventing criteria.
        return {"goal": task, "assumptions": [], "done_when": []}

    def _plan(self, task: str, understanding: Dict[str, Any], max_steps: int) -> List[Dict[str, str]]:
        """THE INTENT-DECOMPOSITION ENGINE (UK, 2026-09-14: "ensure ki
        har step nikaalne ke liye ek engine hona chahiye jo intent ko
        steps mein break kare, phir code sandboxing complete kare").

        This is that engine. It takes the raw task text and the
        understanding extracted in _understand() (goal + done-criteria)
        and turns it into a TYPED step sequence -- code/write/verify/
        system -- BEFORE anything runs. Nothing in stream() executes a
        step that did not come out of this decomposition; in
        particular, KIND_CODE steps below are handed to
        _run_code_step(), which calls brain.run_coding_task() --
        JARVIS's own sandboxed coding tool (core/skills/codebox.py),
        the same one it already has LLM-tool permission to use on its
        own. So the pipeline is exactly: intent -> decompose (here) ->
        sandboxed execution (_run_code_step) -> verify (_run_verify_step).
        """
        raw = self._call(
            "Plan how to COMPLETE this task -- not how to describe it. Return ONLY a JSON array, "
            f"max {max_steps} items: "
            '[{"kind": "code"|"write"|"verify"|"system", "description": "..."}]. '
            "Use 'code' for anything that must actually run. Include at least one 'verify' step "
            "that checks the done_when conditions. Do not include steps that only explain.",
            f"Task: {task}\n\nUnderstanding: {json.dumps(understanding, ensure_ascii=False)}",
            700,
        )
        parsed = _parse_json_list(raw) or []
        steps: List[Dict[str, str]] = []
        for item in parsed[:max_steps]:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", KIND_WRITE)).lower().strip()
            desc = str(item.get("description", "")).strip()
            if desc:
                steps.append({"kind": kind if kind in _KINDS else KIND_WRITE, "description": desc})
        if not steps:
            steps = [{"kind": KIND_WRITE, "description": task}]
        if not any(s["kind"] == KIND_VERIFY for s in steps) and len(steps) < max_steps:
            steps.append({"kind": KIND_VERIFY, "description": "Check the result against done_when."})
        return steps

    def _run_code_step(self, task: str, step: TaskStep, context: str) -> None:
        """Code steps ACTUALLY RUN. This is the difference between
        completing a task and describing one."""
        if self.brain is None or not hasattr(self.brain, "run_coding_task"):
            step.ok = False
            step.output = "Coding sandbox available nahi hai is turn mein."
            return
        try:
            result = self.brain.run_coding_task(
                task=f"{task}\n\nThis step: {step.description}\n\nSo far:\n{context}",
                max_steps=3,
            )
            step.executed = True
            step.ok = bool(result.get("solved"))
            step.output = result.get("summary", "") or "(koi output nahi)"
            step.detail = {"attempts": result.get("attempts"), "session": result.get("session_id")}
        except Exception as exc:
            step.ok = False
            step.output = f"Code step fail hua: {exc}"

    def _run_system_step(self, step: TaskStep) -> None:
        """System steps are re-checked HERE, at execution -- a plan can
        drift into system work after it was approved."""
        from .step_goals import KIND_SYSTEM as _unused  # noqa: F401  (keeps the concepts linked)
        from ..skills.sandbox_policy import can_run_system_task
        allowed, why = can_run_system_task(self.role, self.is_verified)
        step.held = True
        step.executed = False
        step.ok = allowed
        step.output = (
            f"System-level step: {step.description}\n"
            + ("Aap authorised ho, par bina aapke explicit 'haan' ke main ise nahi chalaunga."
               if allowed else f"Refused: {why}")
        )

    def _run_write_step(self, task: str, step: TaskStep, context: str) -> None:
        try:
            step.output = self._call(
                f"You are JARVIS completing a task for UK, step {step.index}. Produce ONLY this "
                "step's actual output -- the thing itself, not a description of it. No preamble, "
                "no restating the plan.",
                f"Task: {task}\n\nSteps so far:\n{context or '(none)'}\n\n"
                f"This step: {step.description}\n\nDo it now.",
                1400,
            )
            step.executed = True
            step.ok = bool(step.output)
        except Exception as exc:
            step.ok = False
            step.output = f"Step fail hua: {exc}"

    def _run_verify_step(self, understanding: Dict[str, Any], step: TaskStep,
                         context: str) -> None:
        """Check the work against the criteria set in UNDERSTAND.

        Deliberately asked as a yes/no with reasons, so a vague "looks
        good" cannot pass for verification.
        """
        done_when = understanding.get("done_when") or []
        try:
            raw = self._call(
                "You are checking whether a task is genuinely complete. Return ONLY JSON: "
                '{"complete": true|false, "failures": ["..."]}. '
                "Be strict: if a condition cannot be confirmed from the work shown, it is NOT met. "
                "Do not mark complete just because the work looks reasonable.",
                f"Conditions:\n{json.dumps(done_when, ensure_ascii=False)}\n\nWork done:\n{context}",
                500,
            )
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.M)
            data = json.loads(cleaned)
            complete = bool(data.get("complete"))
            failures = data.get("failures") or []
            step.executed = True
            step.ok = complete
            step.detail = {"failures": failures}
            step.output = ("Sab conditions poori hui." if complete
                           else "Yeh reh gaya: " + "; ".join(str(f) for f in failures[:5]))
        except Exception as exc:
            step.executed = True
            step.ok = False
            step.output = f"Verify nahi kar paya: {exc}"

    # --------------------------------------------------------------- run
    def stream(self, task: str, *, max_steps: int = 6) -> Generator[Dict[str, Any], None, None]:
        """Yields events as the task progresses. Same events drive the
        CLI panel and the frontend ThinkingSteps panel."""
        started = time.time()
        # max_steps argument is now a ceiling ON TOP of the effort
        # profile's own cap, not the sole source of truth -- "low"
        # effort must stay small even if a caller passes max_steps=8.
        max_steps = max(1, min(int(max_steps), MAX_STEPS, self.effort.max_task_steps))

        yield {"type": "effort", "level": self.effort.name, "label": self.effort.label,
              "max_steps": max_steps, "verify_retries": self.effort.verify_retries,
              "step_visibility": self.effort.step_visibility}

        yield {"type": "stage_start", "stage": "understand"}
        understanding = self._understand(task)
        yield {"type": "stage", "stage": "understand",
               "content": (f"Goal: {understanding.get('goal', task)}\n"
                           + (f"Done when: {'; '.join(understanding.get('done_when') or []) }"
                              if understanding.get("done_when") else "Done-criteria clear nahi the.")),
               "ok": True}

        if self._remaining_calls() < max(MIN_BUDGET_TO_CONTINUE, self.effort.min_budget_calls):
            yield {"type": "aborted", "reason": "Budget khatam -- plan banane se pehle hi ruk gaya."}
            return

        yield {"type": "stage_start", "stage": "plan"}
        plan = self._plan(task, understanding, max_steps)
        yield {"type": "stage", "stage": "plan",
               "content": "\n".join(f"{i}. [{s['kind']}] {s['description']}"
                                    for i, s in enumerate(plan, 1)),
               "ok": True, "detail": {"steps": len(plan)}}

        context_lines: List[str] = []
        verify_retries = 0
        index = 0

        while index < len(plan):
            planned = plan[index]
            index += 1

            if self._remaining_calls() < MIN_BUDGET_TO_CONTINUE:
                yield {"type": "aborted",
                       "reason": f"Budget khatam -- {index - 1}/{len(plan)} step ke baad ruka."}
                break

            step = TaskStep(index=index, kind=planned["kind"], description=planned["description"])
            yield {"type": "stage_start", "stage": step.kind, "index": index,
                   "description": step.description}

            t0 = time.time()
            context = "\n\n".join(context_lines[-4:])
            if step.kind == KIND_CODE:
                self._run_code_step(task, step, context)
            elif step.kind == KIND_SYSTEM:
                self._run_system_step(step)
            elif step.kind == KIND_VERIFY:
                self._run_verify_step(understanding, step, context)
            else:
                self._run_write_step(task, step, context)
            step.duration_ms = (time.time() - t0) * 1000

            self.steps.append(step)
            context_lines.append(f"[step {index} {step.kind}] {step.description}\n{step.output}")
            # step_visibility: "collapsed" turns still stream the raw
            # event (the frontend decides how much to render), but the
            # content is truncated hard here so a "low" effort run never
            # pays the token cost of a full step transcript it will not
            # show.
            emitted = step.as_dict()
            if self.effort.step_visibility == "collapsed":
                emitted["content"] = ""
                emitted["output"] = emitted["output"][:80]
            yield {"type": "stage", "stage": step.kind, **emitted}

            # Verify retry count comes from the EFFORT PROFILE now, not
            # a fixed module constant -- "low" gets zero retries, "deep"
            # gets two, per UK's hierarchy.
            if step.kind == KIND_VERIFY and not step.ok and verify_retries < self.effort.verify_retries:
                verify_retries += 1
                failures = (step.detail or {}).get("failures") or []
                plan.insert(index, {
                    "kind": KIND_CODE if any(s["kind"] == KIND_CODE for s in plan) else KIND_WRITE,
                    "description": ("Fix what verification flagged: "
                                    + "; ".join(str(f) for f in failures[:3])),
                })
                plan.insert(index + 1, {"kind": KIND_VERIFY,
                                        "description": "Re-check the done_when conditions."})
                yield {"type": "retry", "reason": step.output}

        done = sum(1 for s in self.steps if s.ok and s.executed)
        held = [s for s in self.steps if s.held]
        verified = [s for s in self.steps if s.kind == KIND_VERIFY]
        complete = bool(verified) and verified[-1].ok and not held

        conclusion = self._conclude(task, complete, held)
        yield {
            "type": "done",
            "result": {
                "task": task,
                "complete": complete,
                "steps": [s.as_dict() for s in self.steps],
                "completed_steps": done,
                "total_steps": len(self.steps),
                "awaiting_confirmation": [s.as_dict() for s in held],
                "conclusion": conclusion,
                "duration_ms": round((time.time() - started) * 1000, 1),
            },
        }

    def _conclude(self, task: str, complete: bool, held: List[TaskStep]) -> str:
        """The summary UK asked for: what was done, what works, what did
        not. Built from the real step record, not generated freely --
        a written conclusion could otherwise claim success the steps do
        not support."""
        parts = []
        code_steps = [s for s in self.steps if s.kind == KIND_CODE]
        failed = [s for s in self.steps if not s.ok and not s.held]

        parts.append(
            f"{sum(1 for s in self.steps if s.ok and s.executed)}/{len(self.steps)} step poore hue."
        )
        if code_steps:
            ran = sum(1 for s in code_steps if s.ok)
            parts.append(f"{ran}/{len(code_steps)} code step sach mein chale.")
        if held:
            parts.append(f"{len(held)} system step aapki confirmation ka intezaar kar rahe hain.")
        if failed:
            parts.append("Yeh fail hue: " + "; ".join(f"step {s.index} ({s.kind})" for s in failed[:3]) + ".")
        parts.append("Task poora hua." if complete
                     else "Task poora NAHI hua -- upar dekho kahan ruka.")
        return " ".join(parts)

    def run(self, task: str, *, max_steps: int = 6) -> Dict[str, Any]:
        """Non-streaming wrapper for the CLI and plain callers."""
        final: Dict[str, Any] = {}
        for event in self.stream(task, max_steps=max_steps):
            if event["type"] == "done":
                final = event["result"]
            elif event["type"] == "aborted":
                final.setdefault("aborted", event["reason"])
        return final or {"complete": False, "conclusion": "Kuch chala hi nahi."}


def wants_task_loop(text: str) -> bool:
    """Does this turn want a task carried out, rather than answered?

    Structural check, no LLM call -- deciding whether to spend calls
    must not itself cost one.
    """
    lowered = (text or "").lower()
    build_markers = ("bana do", "banao", "bna do", "bnao", "build", "implement", "create",
                     "likh ke do", "likhkar do", "fix karo", "theek karo", "setup karo",
                     "step by step", "step turn", "poora", "complete karo")
    return any(m in lowered for m in build_markers)
