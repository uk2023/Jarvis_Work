#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JARVIS Organism Monitor.

Run this in a SECOND terminal session (a second Termux session, a
tmux/screen pane, or a second SSH window) while `python3 cli.py` runs
in the first one. It shows JARVIS's live internal lifecycle -- exactly
what the plain chat CLI can't show you:

    * Current pipeline stage: IDLE / PERCEIVING / INDEXING / EXECUTING
    * Whether the last structured extraction had to fall back to its
      deterministic safe default (FALLBACK ACTIVE)
    * The recent workflow pipeline trace (stage transitions + timing)
    * Recent schema extraction attempts (primary/refined/safe_fallback)
    * The background learning queue (pending/processed/failed, and
      whether a learning job is actively running right now)
    * Recent internal warnings/errors that used to be bare print()
      calls corrupting the chat console

Design constraints, on purpose:

    * Zero third-party dependencies. Only the Python standard library
      (json, os, time, curses, argparse) is imported. No `rich`, no
      `textual` -- those are exactly what made the two previous
      monitor attempts unreliable on Termux/Android (textual is heavy
      to build there; rich's Live rendering across two independently-
      spawned terminals needs a GUI terminal emulator to auto-launch,
      which cli.py used to require and would hard-crash on Termux when
      none was found).
    * No terminal auto-spawn. You start this yourself, in whatever
      second session your platform actually gives you -- a second
      Termux tab, `tmux new-window`, `screen`, or SSH. That is the
      thing that is actually reliable everywhere.
    * Reads a single small JSON file (the IPC "jarvis_state.ipc" state
      bus written by core/runtime/state_bus.py). No sockets, no ports,
      no permissions beyond reading one file.

Usage:
    python3 monitor.py
    python3 monitor.py --state /custom/path/jarvis_state.ipc --interval 0.5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------
# Path resolution -- intentionally duplicated from core/runtime/
# state_bus.py rather than imported. monitor.py must stay importable
# and runnable even if the rest of the codebase (faiss/networkx/
# onnxruntime/tokenizers) isn't fully installed yet on this machine --
# it only ever needs to read one small JSON file.
# ---------------------------------------------------------------------

def _resolve_default_path() -> str:
    env_path = os.environ.get("JARVIS_STATE_IPC")
    candidates = []
    if env_path:
        candidates.append(env_path)
    candidates.append(os.path.join(tempfile.gettempdir(), "jarvis_state.ipc"))
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(base_dir, "runtime", "jarvis_state.ipc"))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def read_snapshot(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


# ---------------------------------------------------------------------
# Pure rendering: snapshot -> list of (text, style) lines. Kept free of
# any curses calls so it can be tested/iterated on without a real
# terminal, and so the plain-text fallback (no curses available) can
# reuse exactly the same content.
# ---------------------------------------------------------------------

STAGE_STYLE = {
    "IDLE": "dim",
    "PERCEIVING": "stage",
    "INDEXING": "stage",
    "EXECUTING": "stage",
}


def _fmt_text(text: str, limit: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _ago(ts: Optional[float], now: float) -> str:
    if not ts:
        return "—"
    delta = max(0.0, now - float(ts))
    if delta < 1.0:
        return "just now"
    if delta < 60.0:
        return f"{delta:.1f}s ago"
    return f"{int(delta // 60)}m{int(delta % 60):02d}s ago"


def build_lines(snapshot: Optional[Dict[str, Any]], now: Optional[float] = None) -> List[Tuple[str, str]]:
    now = now if now is not None else time.time()
    lines: List[Tuple[str, str]] = []

    if not snapshot:
        lines.append(("Waiting for the JARVIS state publisher...", "warn"))
        lines.append(("", "normal"))
        lines.append(("Start JARVIS in another session with:  python3 cli.py", "dim"))
        return lines

    runtime_state = snapshot.get("runtime", "UNKNOWN")
    stage = snapshot.get("stage", "IDLE")
    fallback_active = bool(snapshot.get("fallback_active", False))
    updated_at = snapshot.get("updated_at")
    pid = snapshot.get("pid", "?")

    runtime_style = "ok" if runtime_state == "ONLINE" else "error"
    lines.append((f"JARVIS ORGANISM MONITOR   pid={pid}   runtime={runtime_state}   updated {_ago(updated_at, now)}", runtime_style))
    lines.append(("", "normal"))

    stage_style = STAGE_STYLE.get(stage, "stage")
    lines.append((f"  STAGE: {stage}", stage_style))
    if fallback_active:
        lines.append(("  ⚠ FALLBACK ACTIVE -- last extraction used the deterministic safe default", "warn"))
    lines.append(("", "normal"))

    # -- Workflow pipeline trace -----------------------------------
    lines.append(("WORKFLOW PIPELINE TRACE (most recent last)", "header"))
    trace = snapshot.get("pipeline_trace") or []
    if not trace:
        lines.append(("  (no turns processed yet)", "dim"))
    else:
        for event in trace[-8:]:
            prev = event.get("previous_stage", "?")
            cur = event.get("stage", "?")
            dur = event.get("duration_in_previous")
            dur_txt = f"{dur:.3f}s" if isinstance(dur, (int, float)) else "?"
            lines.append((f"  {prev:>10} -> {cur:<10}  ({dur_txt} in {prev})  {_ago(event.get('timestamp'), now)}", "normal"))
    lines.append(("", "normal"))

    # -- Recent schema extractions -----------------------------------
    lines.append(("RECENT SCHEMA EXTRACTIONS", "header"))
    extractions = snapshot.get("extractions") or []
    if not extractions:
        lines.append(("  (none yet)", "dim"))
    else:
        for ext in extractions[-6:]:
            schema = ext.get("schema", "?")
            stage_used = ext.get("stage_used", "?")
            fb = ext.get("fallback_active", False)
            style = "warn" if fb else "ok"
            attempts = ext.get("attempts") or []
            attempt_txt = " -> ".join(f"{a.get('stage')}:{'ok' if a.get('ok') else 'fail'}" for a in attempts)
            lines.append((f"  [{schema}] used={stage_used:<12} {attempt_txt}  {_ago(ext.get('timestamp'), now)}", style))
    lines.append(("", "normal"))

    # -- Background learning queue -----------------------------------
    lines.append(("BACKGROUND LEARNING QUEUE", "header"))
    learning = snapshot.get("learning") or {}
    active_txt = "RUNNING NOW" if learning.get("active") else "idle"
    alive_txt = "ALIVE" if learning.get("alive") else "STOPPED"
    lines.append((
        f"  worker={alive_txt:<7} {active_txt:<12}  pending={learning.get('pending', 0)}  "
        f"processed={learning.get('processed', 0)}  failed={learning.get('failed', 0)}  "
        f"dropped={learning.get('dropped', 0)}",
        "ok" if learning.get("alive") else "error",
    ))
    lines.append(("", "normal"))

    # -- Organism health -----------------------------------
    heartbeat = snapshot.get("heartbeat") or {}
    organs = snapshot.get("organs") or {}
    online = sum(1 for o in organs.values() if isinstance(o, dict) and o.get("attached"))
    total = len(organs)
    lines.append(("ORGANISM HEALTH", "header"))
    lines.append((
        f"  heartbeat={'ALIVE' if heartbeat.get('running') else 'STOPPED'} "
        f"beats={heartbeat.get('beats', 0)}  idle={heartbeat.get('idle', True)}   "
        f"llm_ready={snapshot.get('llm_ready', False)}   organs={online}/{total} online",
        "normal",
    ))
    lines.append(("", "normal"))

    # -- Idle-loop activity (what JARVIS actually does when not chatting) --
    # Previously the ONLY idle signal here was the bare True/False flag
    # above -- this section shows real idle-cycle results (curiosity ->
    # goal -> planner -> executor, see core/autonomy/idle_loop.py).
    idle_last = snapshot.get("idle_last") or {}
    idle_activity = snapshot.get("idle_activity") or []
    lines.append(("IDLE LOOP ACTIVITY", "header"))
    if not idle_activity:
        lines.append(("  No idle cycles recorded yet this session (runs every ~30s of inactivity).", "dim"))
    else:
        age = time.time() - idle_last.get("timestamp", time.time())
        if idle_last.get("event") == "IDLE_CYCLE_NOOP":
            lines.append((f"  Last cycle ({age:.0f}s ago): NO-OP -- {idle_last.get('reason', 'no pending goals')}", "dim"))
        else:
            lines.append((
                f"  Last cycle ({age:.0f}s ago): goal=\"{idle_last.get('goal', '?')}\" "
                f"step={idle_last.get('step_index', '?')} executed={idle_last.get('executed_count', 0)} "
                f"awaiting_confirmation={idle_last.get('awaiting_confirmation_count', 0)}",
                "normal",
            ))
        lines.append((f"  {len(idle_activity)} idle cycle(s) recorded this session.", "dim"))
    lines.append(("", "normal"))

    # -- Idle memory consolidation (episodic chat -> semantic facts) ---
    # UK explicitly asked to be able to see this happen. Previously
    # bootstrap.py called MemoryConsolidator.consolidate() every idle
    # tick but NOTHING surfaced the result anywhere -- not CLI, not
    # web, not here. See core/memory/memory_consolidator.py.
    consolidation = snapshot.get("memory_consolidation") or {}
    lines.append(("MEMORY CONSOLIDATION (episodic -> semantic, idle-time)", "header"))
    if not consolidation or not consolidation.get("run_count"):
        lines.append(("  Not run yet this session (piggybacks on the idle cycle above, same ~30s cooldown).", "dim"))
    else:
        last_result = consolidation.get("last_result") or {}
        age = time.time() - consolidation.get("last_run_at", time.time())
        lines.append((
            f"  run #{consolidation.get('run_count', 0)} ({age:.0f}s ago): "
            f"examined={last_result.get('examined', 0)}  candidates={last_result.get('candidates', 0)}  "
            f"promoted_to_semantic={last_result.get('consolidated', 0)}",
            "ok" if last_result.get("consolidated") else "normal",
        ))
        items = last_result.get("items") or []
        for item in items[:5]:
            lines.append((
                f"    + {item.get('subject', '?')} -- {item.get('predicate', '?')} -> {item.get('value', '?')}",
                "ok",
            ))
        preview = last_result.get("examined_preview") or []
        if preview and not items:
            shown = "; ".join(f'"{p}"' for p in preview[:3])
            lines.append((f"    (examined but nothing new extracted, e.g. {shown})", "dim"))
    lines.append(("", "normal"))

    # -- Native response learning (UK's #5: JARVIS learning to answer
    # itself, zero LLM cost, for safe repeated small talk only) -------
    nrl = snapshot.get("native_response_learning") or {}
    lines.append(("NATIVE RESPONSE LEARNING (zero-LLM-cost templates)", "header"))
    if not nrl or not nrl.get("run_count"):
        lines.append(("  Not run yet this session (piggybacks on the idle cycle, same ~30s cooldown).", "dim"))
    else:
        last = nrl.get("last_mine_result") or {}
        lines.append((
            f"  templates_learned={nrl.get('template_count', 0)}  total_hits_saved_from_LLM={nrl.get('total_hits', 0)}  "
            f"last_scan: candidates={last.get('candidates_found', 0)} newly_approved={last.get('approved', 0)}",
            "ok" if nrl.get("template_count") else "normal",
        ))
        patterns = last.get("patterns") or []
        for pattern in patterns[:5]:
            lines.append((f"    + learned: \"{pattern}\"", "ok"))
    lines.append(("", "normal"))

    # -- Procedural memory (UK's #2 proposal: the formal 3rd memory
    # type -- declarative=semantic, episodic=episodic, procedural=this)
    proc_mem = snapshot.get("procedural_memory") or {}
    lines.append(("PROCEDURAL MEMORY (3rd memory type: learned habits)", "header"))
    if not proc_mem:
        lines.append(("  Not available yet this session.", "dim"))
    else:
        by_kind = proc_mem.get("by_kind") or {}
        kind_txt = "  ".join(f"{k}={v}" for k, v in by_kind.items()) or "(none learned yet)"
        lines.append((
            f"  total_procedures={proc_mem.get('procedure_count', 0)}  total_hits={proc_mem.get('total_hits', 0)}  by_kind: {kind_txt}",
            "ok" if proc_mem.get("procedure_count") else "normal",
        ))
    lines.append(("", "normal"))

    # -- Personal idiolect/typo learning (UK's #1 proposal) ------------
    idiolect = snapshot.get("idiolect_status") or {}
    lines.append(("PERSONAL TYPO LEARNING (idiolect model)", "header"))
    if not idiolect:
        lines.append(("  Not available yet this session.", "dim"))
    else:
        lines.append((
            f"  learned_corrections={idiolect.get('learned_corrections_count', 0)}  "
            f"pending_pairs_being_tracked={idiolect.get('tracked_pending_pairs', 0)}  "
            f"promotion_threshold={idiolect.get('promotion_threshold', '?')} repeats",
            "normal",
        ))
        closest = idiolect.get("closest_to_learning") or []
        for entry in closest[:3]:
            lines.append((
                f"    \"{entry.get('original')}\" -> \"{entry.get('corrected')}\" "
                f"({entry.get('count')}/{idiolect.get('promotion_threshold', '?')} seen)",
                "dim",
            ))
    lines.append(("", "normal"))

    # -- Spaced-repetition memory decay (UK's #3 proposal) -------------
    decay = snapshot.get("memory_decay") or {}
    lines.append(("MEMORY DECAY (unused personal facts fade, like real memory)", "header"))
    if not decay:
        lines.append(("  Not run yet this session (piggybacks on the idle cycle, ~30s cooldown).", "dim"))
    else:
        age = time.time() - decay.get("timestamp", time.time())
        lines.append((f"  Last cycle ({age:.0f}s ago): {decay.get('decayed_count', 0)} unused fact(s) weakened slightly.", "normal"))
    lines.append(("", "normal"))

    # -- Metacognitive calibration (UK's #5 proposal) -------------------
    calibration = snapshot.get("calibration") or {}
    lines.append(("METACOGNITIVE CALIBRATION (how often confident == correct)", "header"))
    if not calibration or not calibration.get("available"):
        lines.append(("  Not available yet this session.", "dim"))
    elif not calibration.get("total_contradictions"):
        lines.append(("  No facts have been contradicted/corrected yet -- nothing to calibrate against.", "dim"))
    else:
        score = calibration.get("calibration_score")
        lines.append((
            f"  calibration_score={score} ({calibration.get('overconfident_contradictions', 0)}/"
            f"{calibration.get('total_contradictions', 0)} contradicted facts were stated at high confidence)",
            "ok" if isinstance(score, (int, float)) and score >= 0.7 else "normal",
        ))
    lines.append(("", "normal"))

    # -- Cognitive self-awareness (blueprint sections 43/48) ------------
    # This is the real answer to "kya JARVIS sach mein seekh raha hai /
    # reason kar raha hai" -- previously nothing here at all, because
    # none of DependencyMetrics/evolution/reasoning-trace data ever
    # reached the state bus, no matter how this display improved.
    dep = snapshot.get("dependency_metrics") or {}
    contradiction_rate = snapshot.get("contradiction_rate")
    lines.append(("COGNITIVE SELF-AWARENESS", "header"))
    if not dep:
        lines.append(("  (no turns processed yet this session)", "dim"))
    else:
        native_rate = dep.get("native_resolution_rate")
        fallback_rate = dep.get("llm_fallback_rate")
        retry_rate = dep.get("retry_value_rate")
        lines.append((
            f"  total_interactions={dep.get('total_interactions', 0)}   "
            f"native_resolution_rate={native_rate if native_rate is not None else '—'}   "
            f"llm_fallback_rate={fallback_rate if fallback_rate is not None else '—'}",
            "ok" if isinstance(native_rate, (int, float)) and native_rate >= 0.5 else "normal",
        ))
        lines.append((
            f"  direct_recall={dep.get('native_direct_recall_count', 0)}  "
            f"identity={dep.get('identity_answer_count', 0)}  "
            f"graph_multi_hop={dep.get('graph_multi_hop_count', 0)}  "
            f"slm_assisted={dep.get('slm_assisted_recall_count', 0)}  "
            f"retry_value_rate={retry_rate if retry_rate is not None else '—'}",
            "normal",
        ))
        if contradiction_rate is not None:
            lines.append((f"  contradiction_rate={contradiction_rate}  (fraction of stored facts with a corrected prior value)", "normal"))
    training_stats = snapshot.get("training_data_stats") or {}
    if training_stats.get("total_examples"):
        by_source = training_stats.get("by_source") or {}
        src_txt = "  ".join(f"{k}={v}" for k, v in by_source.items())
        lines.append((
            f"  training data collected: {training_stats.get('total_examples', 0)} examples ({src_txt}) -- "
            f"step 1 toward a future locally-trained model, see core/learning/training_data_collector.py",
            "dim",
        ))
    lines.append(("", "normal"))

    # -- Evolution & self-learning ---------------------------------------
    evolution = snapshot.get("evolution_summary") or {}
    reasoning = snapshot.get("latest_reasoning") or {}
    lines.append(("EVOLUTION & SELF-LEARNING", "header"))
    if not evolution and not reasoning:
        lines.append(("  (no evolution proposals or reasoning cycles yet this session)", "dim"))
    else:
        counts = evolution.get("counts") or {}
        counts_txt = "  ".join(f"{k}={v}" for k, v in counts.items()) or "none"
        lines.append((f"  proposals: total={evolution.get('total', 0)}  ({counts_txt})", "normal"))
        if evolution.get("latest_target"):
            lines.append((f"  latest: [{evolution.get('latest_status')}] target={evolution.get('latest_target')} -- {_fmt_text(evolution.get('latest_reason', ''), 80)}", "ok" if evolution.get("latest_status") == "APPLIED" else "normal"))
    lines.append(("", "normal"))

    # -- Full 11-question post-response reasoning trace -----------------
    # Previously only a computed 2-line conclusion was shown here
    # ("flagged for possible change" / "self-rule adopted"). This is
    # the actual Q&A a person can verify line by line -- every field
    # core/learning/post_response_reasoning.py computes, not a summary
    # of it.
    lines.append(("LATEST REASONING CYCLE (11 questions)", "header"))
    if not reasoning:
        lines.append(("  (no reasoning cycle completed yet this session)", "dim"))
    else:
        age = time.time() - reasoning.get("timestamp", time.time())
        lines.append((f"  ({age:.0f}s ago, mode={reasoning.get('mode', '—')})", "dim"))
        qa = [
            ("1. What did I do, and why?", reasoning.get("what_and_why")),
            ("2. What did I expect to happen?", reasoning.get("expected_outcome")),
            ("3. What actually happened?", reasoning.get("actual_outcome")),
            ("4. Why did expected/actual differ?", reasoning.get("outcome_gap_reason")),
            ("5. What did I learn or confirm?", reasoning.get("new_learning")),
            ("6. Capability check", reasoning.get("capability_check")),
            ("7. Strategy evidence", reasoning.get("strategy_evidence")),
            ("8. Should I change strategy?", f"{reasoning.get('should_change_strategy')} -- {reasoning.get('change_reason')}"),
            ("9. How reliable is this evidence?", reasoning.get("evidence_reliability")),
            ("10. What will I do differently?", reasoning.get("next_time_different")),
            ("11. Worth adopting into future behavior?", reasoning.get("adopt_as_learning")),
        ]
        for question, answer in qa:
            style = "ok" if question.startswith("11.") and reasoning.get("adopt_as_learning") else "normal"
            lines.append((f"  {question}", "dim"))
            lines.append((f"    -> {_fmt_text(str(answer), 100)}", style))
        llm_cost = reasoning.get("llm_cost") or {}
        if llm_cost.get("retry_used"):
            lines.append((f"  [LLM cost] retry used, {'paid off' if llm_cost.get('retry_paid_off') else 'did NOT pay off'}", "warn" if not llm_cost.get("retry_paid_off") else "ok"))
    lines.append(("", "normal"))

    # -- Self-authored rules awaiting UK's review -------------------------
    # The reasoning cycle above can conclude "worth adopting" (question
    # 11), but that conclusion alone doesn't mean it's LIVE -- it only
    # becomes a proposal sitting in a pending queue until UK reviews it
    # via /confirm_rule or /reject_rule (cli.py). Previously that queue
    # was invisible here even though the reasoning that filled it was
    # already shown above -- a person could see "adopted: True" and
    # reasonably assume it was already governing responses.
    pending_rules = snapshot.get("pending_self_rules") or []
    lines.append(("SELF-AUTHORED RULES -- AWAITING YOUR REVIEW", "header"))
    if not pending_rules:
        lines.append(("  (none pending -- nothing proposed, or everything already reviewed)", "dim"))
    else:
        lines.append((f"  {len(pending_rules)} pending -- review with /pending_rules, /confirm_rule <n>, /reject_rule <n> in cli.py", "warn"))
        for rule in pending_rules[:5]:
            src = rule.get("source_type", "unknown")
            lines.append((
                f"  [{src}] {_fmt_text(str(rule.get('rule', '')), 90)}  (confidence={rule.get('confidence')})",
                "normal",
            ))
    lines.append(("", "normal"))

    # -- Standing instructions (daily triggers) --------------------------
    standing = snapshot.get("standing_instructions") or []
    lines.append(("STANDING INSTRUCTIONS (daily triggers)", "header"))
    if not standing:
        lines.append(("  (none yet -- e.g. say \"roz subah good morning bolo\" to create one)", "dim"))
    else:
        for item in standing[:5]:
            lines.append((
                f"  [{item.get('trigger_time', '?')}] {_fmt_text(str(item.get('action_text', '')), 80)}  "
                f"(last fired: {item.get('last_fired_date') or 'never'})",
                "normal",
            ))
    lines.append(("", "normal"))

    # -- Most recent LLM tool-call trace (M2, 2026-09-11) -----------------
    # See core/orchestration/tool_registry.py -- the model itself
    # decides when to call list_pending_self_rules/confirm_self_rule/
    # browser_search/etc, no hardcoded routing. Shown here so that
    # decision is never a black box.
    tool_calls = snapshot.get("latest_tool_calls") or []
    lines.append(("LAST TURN'S TOOL CALLS (LLM-decided, not hardcoded)", "header"))
    if not tool_calls:
        lines.append(("  (no tool calls this session yet)", "dim"))
    else:
        for call in tool_calls[-5:]:
            if call.get("builtin_tool"):
                lines.append((f"  [browser_search] {_fmt_text(call.get('executed_tools_summary', ''), 90)}", "normal"))
            else:
                result = call.get("result") or {}
                failed = isinstance(result, dict) and result.get("error")
                lines.append((
                    f"  [{call.get('name')}] args={call.get('arguments')} -> "
                    f"{_fmt_text(str(result), 80)}",
                    "warn" if failed else "ok",
                ))
    lines.append(("", "normal"))

    # -- Contested facts (M6, 2026-09-11) ---------------------------------
    # See core/memory/semantic_memory.py's remember() -- a less-trusted
    # source tried to overwrite a more-trusted fact and was held back
    # instead of silently applied. Needs UK's review.
    contested = snapshot.get("contested_facts") or []
    lines.append(("CONTESTED FACTS -- AWAITING YOUR REVIEW", "header"))
    if not contested:
        lines.append(("  (none pending)", "dim"))
    else:
        for item in contested[:5]:
            lines.append((
                f"  {item.get('subject')}.{item.get('predicate')}: "
                f"current=[{item.get('current_source_type')}] {_fmt_text(str(item.get('current_value')), 40)}  vs  "
                f"proposed=[{item.get('proposed_source_type')}] {_fmt_text(str(item.get('proposed_value')), 40)}",
                "warn",
            ))
    lines.append(("", "normal"))

    # -- M8: LLM dependency telemetry --------------------------------
    # See SemanticLearningBoundary.stats() -- how much of semantic
    # understanding resolves WITHOUT an LLM call this session, and
    # whether the learned-native path is taking real share from LLM
    # fallback over time. Scoped, measurable slice of "JARVIS observe
    # kare aur LLM ko native replicate kare" -- not autonomous
    # replacement, just honest visibility into the ratio.
    dep_stats = snapshot.get("llm_dependency_stats") or {}
    lines.append(("LLM DEPENDENCY (semantic understanding, this session)", "header"))
    if not dep_stats.get("available"):
        lines.append(("  (not available yet)", "dim"))
    else:
        counts = dep_stats.get("counts") or {}
        rate = dep_stats.get("native_coverage_rate")
        rate_txt = f"{rate * 100:.1f}%" if rate is not None else "—"
        lines.append((
            f"  native={counts.get('native', 0)}  learned_native={counts.get('learned_native', 0)}  "
            f"llm_fallback={counts.get('llm_fallback', 0)}  -- native coverage: {rate_txt}",
            "ok" if (rate or 0) >= 0.5 else "normal",
        ))
        lines.append((f"  learned registry size: {dep_stats.get('learned_registry_size', 0)}  |  pending candidates: {dep_stats.get('pending_candidates', 0)}", "dim"))
    lines.append(("", "normal"))

    # -- Recent internal log lines -----------------------------------
    logs = snapshot.get("logs") or []
    if logs:
        lines.append(("RECENT INTERNAL LOG (warnings/errors that stay out of the chat console)", "header"))
        for entry in logs[-5:]:
            level = entry.get("level", "info")
            style = "error" if level == "error" else ("warn" if level == "warning" else "dim")
            lines.append((f"  [{level:<7}] {entry.get('tag', '?')}: {entry.get('message', '')}", style))

    return lines


# ---------------------------------------------------------------------
# curses front-end
# ---------------------------------------------------------------------

def _run_curses(path: str, interval: float) -> int:
    import curses

    def _main(stdscr) -> int:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(max(100, int(interval * 1000)))

        has_color = curses.has_colors()
        style_pairs = {}
        if has_color:
            curses.start_color()
            try:
                curses.use_default_colors()
                bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK
            palette = {
                "header": curses.COLOR_CYAN,
                "stage": curses.COLOR_GREEN,
                "ok": curses.COLOR_GREEN,
                "warn": curses.COLOR_YELLOW,
                "error": curses.COLOR_RED,
                "dim": curses.COLOR_WHITE,
                "normal": curses.COLOR_WHITE,
            }
            for idx, (name, color) in enumerate(palette.items(), start=1):
                try:
                    curses.init_pair(idx, color, bg)
                    style_pairs[name] = curses.color_pair(idx)
                except curses.error:
                    style_pairs[name] = 0

        scroll_offset = 0
        while True:
            snapshot = read_snapshot(path)
            lines = build_lines(snapshot)

            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()
            visible_rows = max(1, max_y - 1)
            # THE ACTUAL FIX (screenshot evidence, 2026-09-11): this
            # loop used to always render lines[0:max_y-1] and silently
            # DROP everything past that -- there was no scrolling at
            # all, so once the monitor had more sections than a phone
            # terminal's height (CONTESTED FACTS, LLM DEPENDENCY, the
            # log tail, etc. all got added over this session), they
            # were simply never visible, full stop, no matter how long
            # you waited or what keys you pressed. scroll_offset below
            # is genuinely new state, clamped every frame to stay
            # in-bounds even as line count changes frame to frame.
            max_offset = max(0, len(lines) - visible_rows)
            scroll_offset = max(0, min(scroll_offset, max_offset))
            visible = lines[scroll_offset: scroll_offset + visible_rows]
            for row, (text, style) in enumerate(visible):
                attr = style_pairs.get(style, 0)
                if style in ("header", "stage"):
                    attr |= curses.A_BOLD
                try:
                    stdscr.addnstr(row, 0, text, max(0, max_x - 1), attr)
                except curses.error:
                    pass  # terminal too small for this line -- skip, never crash

            scroll_hint = f"  [{scroll_offset + 1}-{min(scroll_offset + visible_rows, len(lines))}/{len(lines)}]" if len(lines) > visible_rows else ""
            footer = f" q: quit   \u2191/\u2193 PgUp/PgDn/Home/End: scroll{scroll_hint}   refresh: {interval:.1f}s "
            try:
                stdscr.addnstr(max_y - 1, 0, footer[: max_x - 1], max_x - 1, curses.A_REVERSE)
            except curses.error:
                pass
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (ord("q"), ord("Q")):
                return 0
            if ch == curses.KEY_RESIZE:
                continue
            elif ch in (curses.KEY_DOWN, ord("j")):
                scroll_offset += 1
            elif ch in (curses.KEY_UP, ord("k")):
                scroll_offset -= 1
            elif ch == curses.KEY_NPAGE:  # Page Down
                scroll_offset += max(1, visible_rows - 1)
            elif ch == curses.KEY_PPAGE:  # Page Up
                scroll_offset -= max(1, visible_rows - 1)
            elif ch == curses.KEY_HOME:
                scroll_offset = 0
            elif ch == curses.KEY_END:
                scroll_offset = max_offset
            # nodelay + timeout already paced this loop; nothing else to do.

    return curses.wrapper(_main)


# ---------------------------------------------------------------------
# Plain-text fallback (no curses / not a real TTY / any curses failure)
# ---------------------------------------------------------------------

def _run_plain(path: str, interval: float) -> int:
    print(f"[monitor.py] curses unavailable in this terminal -- falling back to a plain polling view.")
    print(f"[monitor.py] watching: {path}  (Ctrl+C to quit)\n")
    try:
        while True:
            snapshot = read_snapshot(path)
            lines = build_lines(snapshot)
            print("\033[2J\033[H", end="")  # clear screen, home cursor (ANSI; safe on Linux/Termux)
            for text, _style in lines:
                print(text)
            print(f"\n[refresh {interval:.1f}s | Ctrl+C to quit]")
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS organism live state monitor (run in a second terminal session).")
    parser.add_argument("--state", metavar="PATH", default=None, help="Path to the jarvis_state.ipc file (default: auto-detected).")
    parser.add_argument("--interval", type=float, default=0.5, help="Refresh interval in seconds (default: 0.5).")
    parser.add_argument("--plain", action="store_true", help="Force the plain-text fallback even if curses is available.")
    args = parser.parse_args()

    path = args.state or _resolve_default_path()
    interval = max(0.1, args.interval)

    if args.plain or not sys.stdout.isatty():
        return _run_plain(path, interval)

    try:
        return _run_curses(path, interval)
    except Exception as exc:  # noqa: BLE001 - curses can fail in many terminal-specific ways
        print(f"[monitor.py] curses UI failed ({exc}); falling back to plain text.")
        return _run_plain(path, interval)


if __name__ == "__main__":
    raise SystemExit(main())
