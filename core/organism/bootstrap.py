from __future__ import annotations

from typing import Optional

from .jarvis_core import JarvisCore
from .internal_state import InternalState
from .event_bus import EventBus
from .heartbeat import Heartbeat
from .lifecycle import Lifecycle

from core.orchestration.brain import Brain

from ..memory.memory_manager import MemoryManager
from ..memory.memory_consolidator import (
    MemoryConsolidator,
)

from ..learning.experience_engine import (
    ExperienceEngine,
)
from ..learning.self_evaluator import (
    SelfEvaluator,
)
from ..learning.knowledge_builder import (
    KnowledgeBuilder,
)
from ..learning.learning_coordinator import (
    LearningCoordinator,
)
from ..learning.evolution_engine import (
    EvolutionEngine,
)

from ..autonomy.curiosity import Curiosity
from ..autonomy.goal_manager import GoalManager
from ..autonomy.planner import Planner
from ..autonomy.scheduler import Scheduler
from ..autonomy.idle_loop import IdleLoop

from ..skills.skill_registry import SkillRegistry
from ..skills.skill_executor import SkillExecutor
from ..skills.skill_learner import SkillLearner


# =============================================================
# CREATE JARVIS
# =============================================================

def create_jarvis(
    identity=None,
    personality=None,
    values=None,
    heartbeat_interval: float = 5.0,
    idle_threshold: float = 30.0,
) -> JarvisCore:
    """
    Construct the complete JARVIS organism.

    Dependency architecture:

        InternalState
              │
              ▼
          EventBus
              │
        ┌─────┴─────┐
        ▼           ▼
     Heartbeat    Memory
                    │
          ┌─────────┼───────────┐
          ▼         ▼           ▼
     Experience  Evaluator   Knowledge
       Engine                  Builder
          │         │           │
          └─────────┼───────────┘
                    ▼
          MemoryConsolidator
                    │
                    ▼
          LearningCoordinator
                    │
                    ▼
            EvolutionEngine
                    │
                    ▼
                  Brain
                    │
                    ▼
               JarvisCore
                    │
                    ▼
                Lifecycle
    """

    # =========================================================
    # 1. INTERNAL STATE
    # =========================================================

    state = InternalState()

    # =========================================================
    # 2. EVENT BUS
    # =========================================================

    events = EventBus(
        internal_state=state,
    )

    # =========================================================
    # 3. HEARTBEAT
    # =========================================================

    heartbeat = Heartbeat(
        event_bus=events,
        internal_state=state,
        interval=heartbeat_interval,
        idle_threshold=idle_threshold,
    )

    # =========================================================
    # 4. MEMORY
    # =========================================================

    memory = MemoryManager(
        event_bus=events,
    )

    # =========================================================
    # 5. EXPERIENCE ENGINE
    # =========================================================
    #
    # Converts raw completed experiences into structured
    # experiences and learning signals.
    #

    experience_engine = ExperienceEngine(
        memory_manager=memory,
        event_bus=events,
        internal_state=state,
    )

    # =========================================================
    # 6. SELF EVALUATOR
    # =========================================================
    #
    # Evaluates whether an experience was useful,
    # successful, reliable, etc.
    #

    evaluator = SelfEvaluator(
        memory_manager=memory,
        event_bus=events,
        internal_state=state,
    )

    # =========================================================
    # 7. KNOWLEDGE BUILDER
    # =========================================================
    #
    # Converts evaluated experiences into knowledge
    # candidates.
    #

    knowledge_builder = KnowledgeBuilder(
        event_bus=events,
        internal_state=state,
        memory_manager=memory,
    )

    # =========================================================
    # 8. MEMORY CONSOLIDATOR
    # =========================================================
    #
    # Converts important/repeated episodic experiences
    # into semantic knowledge.
    #

    consolidator = MemoryConsolidator(
        memory_manager=memory,
        event_bus=events,
    )

    # =========================================================
    # 9. LEARNING COORDINATOR
    # =========================================================
    #
    # Central learning orchestration layer.
    #
    # It does NOT replace the organs.
    #
    # It coordinates:
    #
    #     Experience
    #          ↓
    #     Evaluation
    #          ↓
    #     Knowledge
    #          ↓
    #     Acceptance
    #          ↓
    #     Consolidation
    #

    learning = LearningCoordinator(
        evaluator=evaluator,
        knowledge_builder=knowledge_builder,
        consolidator=consolidator,
        memory_manager=memory,
        event_bus=events,
        internal_state=state,
    )

    # =========================================================
    # 10. EVOLUTION ENGINE
    # =========================================================
    #
    # Evolution remains completely controlled.
    #
    #     Proposal
    #        ↓
    #     Validate
    #        ↓
    #      Approve
    #        ↓
    #       Apply
    #

    evolution = EvolutionEngine(
        event_bus=events,
        internal_state=state,
        memory_manager=memory,
    )

    # =========================================================
    # 10b. AUTONOMY (previously built but never wired in)
    # =========================================================
    #
    # curiosity.py / goal_manager.py / planner.py / scheduler.py /
    # idle_loop.py already existed as fully-implemented organs but
    # nothing ever imported or connected them — the organism had a
    # heartbeat but nothing used the idle time it detected. Wiring
    # them here is what lets JARVIS keep evolving/pulsating between
    # user prompts instead of only reacting to input:
    #
    #     Heartbeat (idle beat)
    #           |
    #           v
    #       IdleLoop.step()
    #      /      |        \
    # Curiosity  GoalManager  Planner/Scheduler
    #      \      |        /
    #     logged as an AUTONOMOUS_STEP episode -> memory
    #
    # Nothing here ever executes anything unsafe: IdleLoop has no
    # `executor` attached, so any step that isn't purely
    # "propose/plan/log" is surfaced as a pending confirmation
    # instead of being run.
    #

    goal_manager = GoalManager(store=memory.store)
    curiosity = Curiosity()
    scheduler = Scheduler()
    planner = Planner(llm_bridge=None)  # attached lazily once brain.llm exists

    idle_loop = IdleLoop(
        goal_manager=goal_manager,
        curiosity=curiosity,
        planner=planner,
        scheduler=scheduler,
        state=state,
        event_bus=events,
        store=memory.store,
        executor=None,
    )

    # =========================================================
    # 10c. SKILLS (also previously built but never wired in)
    # =========================================================
    #
    # SkillRegistry/SkillExecutor stay dormant until something is
    # explicitly registered (Brain, a future gatekeeper, etc.) —
    # that part is intentionally left as-is, no auto-execution.
    # SkillLearner is the one piece that benefits from being wired
    # to the idle pulse: it turns repeated successful
    # AUTONOMOUS_STEP episodes into skill *proposals*, which are
    # only ever added as goals (origin="skill_learner") for later
    # review — never auto-registered as an executable skill. That
    # keeps "controlled evolution" true for skills too, not just
    # for knowledge/evolution proposals.
    #

    skill_registry = SkillRegistry()
    skill_executor = SkillExecutor(skill_registry)
    skill_learner = SkillLearner()

    # =========================================================
    # 11. BRAIN
    # =========================================================
    #
    # Brain is the high-level orchestrator.
    #
    # Brain does NOT duplicate learning logic.
    #

    brain = Brain(
        memory_manager=memory,
        experience_engine=experience_engine,
        learning_coordinator=learning,
        self_evaluator=evaluator,
        knowledge_builder=knowledge_builder,
        memory_consolidator=consolidator,
        evolution_engine=evolution,
        planner=planner,
        goal_manager=goal_manager,
        event_bus=events,
        internal_state=state,
    )

    # =========================================================
    # 12. JARVIS CORE
    # =========================================================

    jarvis = JarvisCore(
        identity=identity,
        personality=personality,
        values=values,
        state=state,
        event_bus=events,
        heartbeat=heartbeat,
    )

<<<<<<< HEAD
    # =========================================================
    # 13. ATTACH ORGANS
    # =========================================================
=======
    def _on_heartbeat(event) -> None:
        payload = getattr(event, "payload", {}) or {}
        now = __import__("time").time()
        if now - last_monitor_run[0] >= monitor_cooldown:
            last_monitor_run[0] = now
            runtime_monitor.write_snapshot(jarvis=None, organs={
                "heartbeat": heartbeat,
                "llm_bridge": llm_bridge,
                "memory": memory,
                "learning": learning,
                "evaluator": evaluator,
                "knowledge_builder": knowledge_builder,
                "evolution": evolution,
                "idle_loop": idle_loop,
                "state": state,
                # UK explicitly asked to be able to SEE this happen
                # (monitor.py showed no idle-consolidation activity at
                # all before) -- exposed the same way every other organ
                # already is, via RuntimeMonitor._stats()'s generic
                # `.statistics()` lookup (aliased to .status() on
                # MemoryConsolidator).
                "consolidator": consolidator,
            })
        if payload.get("idle"):
            with idle_lock:
                if now - last_idle_run[0] >= idle_cooldown:
                    last_idle_run[0] = now
                    idle_loop.step()
                    # Background knowledge maintenance: before this, both
                    # LearningCoordinator.consolidate() and
                    # KnowledgeBuilder.accept_reliable() were fully
                    # implemented but never actually called by anything
                    # at runtime -- the organism would idle-cycle on
                    # goals/curiosity forever while accepted-but-pending
                    # knowledge candidates and consolidatable episodic
                    # memory just sat there unprocessed. Piggyback on the
                    # same idle tick (and its cooldown) used above so
                    # this runs "whenever JARVIS isn't busy talking to
                    # someone", each step independently guarded so one
                    # failing never blocks the other or the idle loop.
                    try:
                        learning.consolidate(limit=25)
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_CONSOLIDATION_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
                    try:
                        knowledge_builder.accept_reliable(minimum_confidence=0.75, limit=25)
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_KNOWLEDGE_ACCEPT_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
                    try:
                        # 2026-09-11 roadmap Phase 5 (previously dead
                        # code): SemanticEvolutionCycle/SemanticKnowledge
                        # Promotion were fully written but NEVER imported
                        # anywhere -- every LLM-fallback semantic
                        # interpretation sat in learning_boundary.py's
                        # in-memory candidates dict forever, never
                        # promoted into LearnedSemanticRegistry, so
                        # JARVIS kept re-asking the LLM for input
                        # patterns it had already successfully
                        # interpreted before. semantic_evolution_cycle
                        # is constructed lazily here (not at bootstrap
                        # top) so it always sees the SAME
                        # learning_boundary instance Brain actually
                        # wired up in _configure_semantic_fallback().
                        boundary = getattr(semantic_understanding, "learning_boundary", None)
                        if boundary is not None:
                            from core.cognition.semantic_understanding.evolution_cycle import SemanticEvolutionCycle
                            evolution_cycle = SemanticEvolutionCycle(boundary=boundary, learning_coordinator=learning)
                            promo_result = evolution_cycle.promote_ready_candidates(min_confidence=0.75, limit=10)
                            if promo_result.get("promoted"):
                                events.safe_emit(
                                    "IDLE_SEMANTIC_CANDIDATES_PROMOTED", promo_result, source="bootstrap"
                                ) if hasattr(events, "safe_emit") else None
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_SEMANTIC_PROMOTION_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
                    try:
                        # SELF-AUTHORED EXTRACTION PATTERNS (2026-09-12,
                        # UK's explicit "regex = hardcoding" objection):
                        # cluster boundary.candidates (real inputs where
                        # native symbolic parsing failed and the LLM had
                        # to step in -- see learning_boundary.py) by a
                        # cheap shared-shape heuristic (same first two
                        # words), and if 2+ genuinely similar failures
                        # exist, ask JARVIS's own pattern_synthesizer to
                        # propose+sandbox-test a new native pattern for
                        # that shape. Nothing here ever applies a
                        # pattern live -- see Brain.confirm_pattern();
                        # this only ever WRITES A PENDING PROPOSAL, same
                        # as self-authored behavioral rules.
                        boundary = getattr(semantic_understanding, "learning_boundary", None)
                        synthesizer = getattr(brain, "pattern_synthesizer", None)
                        if boundary is not None and synthesizer is not None:
                            from collections import defaultdict
                            clusters = defaultdict(list)
                            for candidate in boundary.candidates.values():
                                text = getattr(candidate, "input_text", "") or ""
                                words = text.strip().lower().split()
                                if len(words) >= 2:
                                    clusters[" ".join(words[:2])].append(text)
                            for shape, examples in clusters.items():
                                if len(examples) >= 2:
                                    proposal = synthesizer.propose_from_candidates(
                                        similar_examples=examples[:5],
                                        gap_description=f"native extraction repeatedly failed on inputs shaped like '{shape}...'",
                                    )
                                    if proposal:
                                        events.safe_emit(
                                            "IDLE_PATTERN_PROPOSED", proposal, source="bootstrap"
                                        ) if hasattr(events, "safe_emit") else None
                                    break  # one proposal per idle cycle -- stay cheap, stay reviewable at UK's pace
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_PATTERN_SYNTHESIS_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
                    try:
                        # UK's #5 recall/learning/memory proposal: mine
                        # the persistent trace log for repeated, safe,
                        # always-consistent small talk and promote it
                        # into a zero-LLM-call native template.
                        brain.native_response_learner.run_idle_cycle()
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_NATIVE_RESPONSE_LEARNING_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
                    try:
                        # UK's #3 recall/learning/memory proposal
                        # (spaced-repetition-inspired decay): personal
                        # facts nobody has recalled/reinforced in 14+
                        # days quietly weaken, mirroring the forgetting
                        # curve, instead of every fact sitting at equal
                        # permanent weight forever.
                        decayed_ids = memory.semantic.decay_unused(days_threshold=14.0, confidence_delta=0.02)
                        events.safe_emit(
                            "MEMORY_DECAY_COMPLETED",
                            {"decayed_count": len(decayed_ids), "timestamp": __import__("time").time()},
                            source="bootstrap",
                        ) if hasattr(events, "safe_emit") else None
                    except Exception as exc:
                        events.safe_emit(
                            "IDLE_MEMORY_DECAY_FAILED", {"error": str(exc)}, source="bootstrap"
                        ) if hasattr(events, "safe_emit") else None
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

    jarvis.attach_organ(
        "memory",
        memory,
    )

    jarvis.attach_organ(
        "experience_engine",
        experience_engine,
    )

    jarvis.attach_organ(
        "self_evaluator",
        evaluator,
    )

    jarvis.attach_organ(
        "knowledge_builder",
        knowledge_builder,
    )

    jarvis.attach_organ(
        "memory_consolidator",
        consolidator,
    )

    jarvis.attach_organ(
        "learning_coordinator",
        learning,
    )

    jarvis.attach_organ(
        "evolution",
        evolution,
    )

    jarvis.attach_organ(
        "brain",
        brain,
    )

    jarvis.attach_organ("goal_manager", goal_manager)
    jarvis.attach_organ("curiosity", curiosity)
    jarvis.attach_organ("scheduler", scheduler)
    jarvis.attach_organ("planner", planner)
    jarvis.attach_organ("idle_loop", idle_loop)
    jarvis.attach_organ("skill_registry", skill_registry)
    jarvis.attach_organ("skill_executor", skill_executor)
    jarvis.attach_organ("skill_learner", skill_learner)

    # =========================================================
    # 13b. PULSE -> AUTONOMY HOOK
    # =========================================================
    #
    # This is the literal "heartbeat makes the organism keep
    # evolving even when nobody is talking to it" wire. Heartbeat
    # already emits a HEARTBEAT event on every beat with an `idle`
    # flag (see heartbeat.py) — it just had no listener before.
    #

    _pulse_counter = {"idle_beats": 0}
    _SKILL_PROPOSAL_EVERY_N_IDLE_BEATS = 20  # keep this cheap and infrequent

    def _on_heartbeat_pulse(event) -> None:
        payload = getattr(event, "payload", None) or {}
        if not payload.get("idle"):
            return

        # Let the planner reason with whatever LLM is currently
        # attached to Brain (it may be connected after bootstrap
        # finishes, e.g. by cli.py), without hard-wiring model
        # loading into bootstrap itself.
        planner.llm_bridge = getattr(brain, "llm", None)

        try:
            idle_loop.step()
        except Exception as exc:
            print(f"[Autonomy] idle pulse failed: {exc}")

        _pulse_counter["idle_beats"] += 1
        if _pulse_counter["idle_beats"] % _SKILL_PROPOSAL_EVERY_N_IDLE_BEATS != 0:
            return

        try:
            recent = memory.store.load_episodes(limit=500)
            # SkillLearner expects flat {"action": str, "detail": str,
            # "status": str, "goal": str} records; idle_loop logs
            # episodes with the step nested under "action" and the
            # goal nested under "context", so reshape before proposing.
            autonomous = []
            for e in recent:
                if e.get("event_type") != "AUTONOMOUS_STEP":
                    continue
                step = e.get("action") or {}
                outcome = e.get("outcome") or {}
                context = e.get("context") or {}
                if not isinstance(step, dict) or not step.get("action"):
                    continue
                autonomous.append(
                    {
                        "action": step.get("action"),
                        "detail": step.get("detail", ""),
                        "status": outcome.get("status"),
                        "goal": context.get("goal"),
                    }
                )
            for proposal in skill_learner.propose(autonomous):
                goal_manager.add(
                    text=f"skill_proposal:{proposal['name']}",
                    priority=min(1.0, proposal.get("success_rate", 0.5)),
                    origin="skill_learner",
                )
        except Exception as exc:
            print(f"[Autonomy] skill proposal pass failed: {exc}")

    events.subscribe("HEARTBEAT", _on_heartbeat_pulse)

    # Autonomy organs are wired and listening; flip the switch so
    # InternalState (and anything inspecting it) reflects reality.
    enable_autonomy = getattr(state, "enable_autonomy", None)
    if callable(enable_autonomy):
        enable_autonomy()

    # =========================================================
    # 14. LIFECYCLE
    # =========================================================

    lifecycle = Lifecycle(
        jarvis=jarvis,
        internal_state=state,
        event_bus=events,
        heartbeat=heartbeat,
    )

    jarvis.lifecycle = lifecycle

    # =========================================================
    # 15. FINAL RUNTIME REFERENCES
    # =========================================================
    #
    # Optional direct references on JarvisCore.
    # Only assign them if the attributes already exist or
    # the project architecture allows dynamic attributes.
    #

    jarvis.brain = brain

    return jarvis


# =============================================================
# START JARVIS
# =============================================================

def start_jarvis(
    identity=None,
    personality=None,
    values=None,
    heartbeat_interval: float = 5.0,
    idle_threshold: float = 30.0,
) -> JarvisCore:
    """
    Create and start JARVIS.
    """

    jarvis = create_jarvis(
        identity=identity,
        personality=personality,
        values=values,
        heartbeat_interval=heartbeat_interval,
        idle_threshold=idle_threshold,
    )

    lifecycle = getattr(
        jarvis,
        "lifecycle",
        None,
    )

    if lifecycle is None:
        raise RuntimeError(
            "JARVIS lifecycle is not connected."
        )

    success = lifecycle.start()

    if not success:
        raise RuntimeError(
            "JARVIS failed to start."
        )

    jarvis.running = True

    return jarvis


# =============================================================
# STOP JARVIS
# =============================================================

def stop_jarvis(
    jarvis: Optional[JarvisCore],
) -> None:
    """
    Safely stop JARVIS.

    Shutdown order:

        Lifecycle
            ↓
        Heartbeat
            ↓
        Memory
            ↓
        EventBus
    """

    if jarvis is None:
        return

    # =========================================================
    # 1. LIFECYCLE
    # =========================================================

    lifecycle = getattr(
        jarvis,
        "lifecycle",
        None,
    )

    if lifecycle is not None:

        stop_method = getattr(
            lifecycle,
            "stop",
            None,
        )

        if callable(stop_method):

            stop_method()

    # =========================================================
    # 2. BRAIN
    # =========================================================

    brain = getattr(
        jarvis,
        "brain",
        None,
    )

    if brain is not None:

        stop_method = getattr(
            brain,
            "stop",
            None,
        )

        if callable(stop_method):

            stop_method()

    # =========================================================
    # 3. LEARNING COORDINATOR
    # =========================================================

    learning = None

    try:

        learning = jarvis.get_organ(
            "learning_coordinator"
        )

    except Exception:
        learning = None

    if learning is not None:

        stop_method = getattr(
            learning,
            "stop",
            None,
        )

        if callable(stop_method):

            stop_method()

    # =========================================================
    # 4. MEMORY
    # =========================================================

    memory = None

    try:

        memory = jarvis.get_organ(
            "memory"
        )

    except Exception:
        memory = None

    if memory is not None:

        close_method = getattr(
            memory,
            "close",
            None,
        )

        if callable(close_method):

            close_method()

    # =========================================================
    # 5. EVENT BUS
    # =========================================================

    events = getattr(
        jarvis,
        "events",
        None,
    )

    if events is not None:

        stop_method = getattr(
            events,
            "stop",
            None,
        )

        if callable(stop_method):

            stop_method()

    # =========================================================
    # 6. FINAL STATE
    # =========================================================

    jarvis.running = False