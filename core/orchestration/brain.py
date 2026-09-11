from __future__ import annotations

import json
import re
import time
import hashlib
from .cognitive_router import CognitiveRouter
from .perception import PerceptionEngine, LLMPerceptionProvider
from .response_brief import build_response_brief, try_direct_recall_answer, try_identity_answer, check_response_grounding, check_action_claim_grounding, get_self_authored_rules
from ..cognition.user_rules import UserRuleStore
from ..autonomy.standing_instructions import StandingInstructionStore
from ..learning.outcome_feedback import detect_correction
from ..cognition.native_reasoner import NativeReasoner
from ..learning.native_response_learning import NativeResponseLearner
from ..contracts import validate_input, validate_output, ContractError
from ..learning.post_response_reasoning import build_reasoning_trace
from ..learning.dependency_metrics import DependencyMetrics, contradiction_rate
from ..learning.fallback_pattern_detector import FallbackPatternDetector
from ..learning.category_word_learner import CategoryWordLearner
from ..skills.skill_executor import SkillExecutor
from typing import Any, Dict, Optional

from ..learning.learning_queue import AsyncLearningQueue
from ..runtime.log import log_event
from ..runtime.chat_log import log_chat_turn


class Brain:
    """
    Central orchestration organ of JARVIS.

    Brain coordinates major cognitive organs.

    Brain is NOT:
        - the LLM
        - the memory database
        - the learning engine itself
        - the evaluator
        - the knowledge builder
        - the evolution engine
        - an unrestricted executor

    Authoritative semantic architecture:

        User Input
          ↓
        Perception
          ↓
        Semantic Understanding
          ↓
        Structured Semantic Result
          ↓
        Cognition
          ↓
        Response
          ↓
        Experience / Learning

    Evolution remains controlled:

        Proposal
            ↓
        Validate
            ↓
        Approve
            ↓
        Apply

    Brain only orchestrates these operations.

    Semantic understanding is authoritative for semantic interpretation.
    Brain orchestrates Perception → Semantic Understanding → Cognition →
    Response → Experience / Learning and does not perform a second semantic
    extraction pass through the LLM.
    """

    VERSION = "0.6.0"

    def __init__(
        self,
        memory_manager=None,
        experience_engine=None,
        self_evaluator=None,
        knowledge_builder=None,
        memory_consolidator=None,
        learning_coordinator=None,
        evolution_engine=None,
        event_bus=None,
        internal_state=None,
        planner=None,
        goal_manager=None,
        llm_bridge=None,
        cognitive_router=None,
        perception_engine=None,
        skill_registry=None,
        skill_executor=None,
        auto_accept_knowledge: bool = True,
    ):
        # =========================================================
        # CORE ORGANS
        # =========================================================

        self.memory = memory_manager
        # Native, zero-LLM-cost rule capture -- see core/cognition/user_rules.py.
        # getattr(...) because self.memory can be a bare MemoryManager
        # (has .semantic) OR None (standalone/test Brain instances);
        # UserRuleStore already no-ops cleanly when semantic_memory is None.
        self._user_rules = UserRuleStore(getattr(self.memory, "semantic", None))
        # Standing (triggered) instructions -- distinct from the
        # behavioral rules above. See core/autonomy/
        # standing_instructions.py's module docstring: captures "do X
        # when Y happens" (today: daily time triggers), e.g. UK's
        # "roz subah good morning bolo". Public (no leading underscore,
        # unlike _user_rules) because idle_loop needs read access to
        # due_now()/mark_fired() from outside Brain -- see bootstrap.py.
        self.standing_instructions = StandingInstructionStore(getattr(self.memory, "semantic", None))
        # UK's #5: learns to answer repeated, safe, non-fact-dependent
        # small talk without an LLM call -- see core/learning/
        # native_response_learning.py's module docstring for the full
        # safety design (why it's restricted to a narrow intent
        # allowlist, never fact questions).
        self.native_response_learner = NativeResponseLearner(event_bus=event_bus)
        # UK's #2 recall/learning/memory proposal: the formal
        # procedural-memory organ (see core/memory/procedural_memory.py)
        # that native_response_learner now delegates its storage to --
        # exposed directly on Brain too so introspection/monitor.py can
        # show it as its own memory type, not just a sub-detail of one
        # feature.
        self.procedural_memory = self.native_response_learner.procedural_memory
        # Unified native (zero-LLM-cost) resolver chain (blueprint
        # section 27) -- see core/cognition/native_reasoner.py.
        # identity_system is often attached AFTER Brain construction
        # (bootstrap.py wiring order), so it's refreshed on the
        # instance right before each use rather than fixed here.
        self._native_reasoner = NativeReasoner(memory_manager=self.memory, brain=self, native_response_learner=self.native_response_learner)
        # Bound after construction via bootstrap.py (JarvisIdentity needs
        # this Brain instance to read live capabilities, so it can't be
        # constructed before Brain exists). None-safe everywhere it's read.
        self.identity_system: Optional[Any] = None
        # Post-response reasoning history (see process_experience below
        # and core/learning/post_response_reasoning.py) -- bounded so it
        # can't grow unboundedly over a long session.
        self.last_reasoning_traces: list = []
        # Most recent turn's LLM tool-call trace (see
        # core/orchestration/tool_registry.py's run_tool_loop()) --
        # which tools the model proposed, the gated result of each,
        # for traceability the same way last_reasoning_traces already is.
        self.last_tool_call_trace: list = []
        # OUTCOME FEEDBACK part 1/2 -- see the capture site right
        # after build_response_brief() and the correction-detection
        # site near the top of the turn-processing method.
        self.last_turn_fact_ids: list = []
        # NEW: real, retained history of WHY each layer produced what it
        # produced this turn -- not just a transient CLI display line.
        # Every layer (perception, semantic understanding) now reports
        # a structured validation: did it succeed, and if not, exactly
        # why (which mechanism was tried, what specifically failed).
        # This is what makes "why didn't you extract X" answerable from
        # real retained data via the self-awareness fast path, instead
        # of only ever being visible for the ONE turn it happened on,
        # in the CLI, then discarded.
        self.last_layer_validations: list = []
        # UK's explicit ask: no protection existed against a message
        # trying to hide malicious "instructions" for JARVIS. Retained
        # history (like last_layer_validations) so flagged inputs can
        # genuinely be reviewed later, not lost after one turn.
        self.safety_check_history: list = []
        # LLM Dependency Metrics (blueprint section 43) -- one shared
        # counter set for the whole Brain lifetime, updated at the same
        # single chokepoint background learning uses.
        self.dependency_metrics = DependencyMetrics()
        # Evolution-of-LLM-fallbacks detector (blueprint section 48) --
        # see core/learning/fallback_pattern_detector.py.
        self.fallback_pattern_detector = FallbackPatternDetector()
        # WIRED THIS SESSION (was built earlier but never connected --
        # a real, confirmed gap UK caught: overnight idle-learning had
        # almost nothing to work with because fallback_pattern_detector
        # only tracks ONE narrow failure shape (recall-miss questions),
        # while category_word_learner tracks something far more common:
        # every time the LLM successfully extracts a favourite_<category>
        # fact that native regex's indicator-word set didn't already
        # know, THAT word is a genuine, real vocabulary-expansion
        # candidate -- happening on ordinary STATEMENTS, not just the
        # narrow recall-question case.
        try:
            from ..cognition.semantic_understanding.engine import SemanticUnderstandingEngine
            known_words = set(SemanticUnderstandingEngine._CATEGORY_INDICATOR_WORDS)
        except Exception:
            known_words = set()
        self.category_word_learner = CategoryWordLearner(known_indicator_words=known_words, min_occurrences=2)
        # Per-turn memoization for build_context(). _perceive(),
        # _build_cognition_input() and the LLM-fallback route each call
        # build_context() with essentially the same query text once per
        # turn -- that's 3 separate FAISS similarity searches + ONNX
        # embedding computations for one user message, which is real,
        # avoidable latency (each is real compute, not free). Cache is
        # cleared at the top of every think_and_respond() call.
        self._context_cache: dict = {}
        self.experience = experience_engine
        self.evaluator = self_evaluator
        self.knowledge_builder = knowledge_builder
        self.consolidator = memory_consolidator
        self.learning = learning_coordinator
        self.evolution = evolution_engine

        # =========================================================
        # SYSTEM SERVICES
        # =========================================================

        self.events = event_bus
        self.state = internal_state
        self.planner = planner
        self.goal_manager = goal_manager
        self.llm = llm_bridge

        # =========================================================
        # COGNITION / PERCEPTION / SKILLS
        # =========================================================

        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = (
            skill_executor
            if skill_executor is not None
            else (
                SkillExecutor(skill_registry)
                if skill_registry is not None
                else None
            )
        )
        self.perception = perception_engine or PerceptionEngine(state=self.state)

        if self.llm is not None:
            self.set_llm_bridge(self.llm)

        self.last_cognitive_decision: Optional[Dict[str, Any]] = None
        self.last_perception: Optional[Dict[str, Any]] = None
        self.last_context: Optional[Dict[str, Any]] = None
        self.last_brain_decision: Optional[Dict[str, Any]] = None
        self.last_action_response: Optional[Dict[str, Any]] = None
        # Set at the top of every think_and_respond() call; read back by
        # _record_action_response() so the centralized background-
        # learning hand-off (see _record_action_response below) has the
        # live user_input without having to thread it through every one
        # of the ~10 return points in think_and_respond().
        self._last_user_input: str = ""

        # =========================================================
        # LEARNING POLICY
        # =========================================================
        # Whether experiences that pass through process_experience()
        # get their resulting knowledge candidate auto-accepted into
        # persistent memory. This is what actually makes JARVIS learn
        # instead of just logging episodes. Set to False if you want
        # a manual review step (accept_knowledge / reject_knowledge).
        self.auto_accept_knowledge = auto_accept_knowledge

        # =========================================================
        # RUNTIME
        # =========================================================

        self.created_at = time.time()
        self.last_cycle_at: Optional[float] = None
        self.cycle_count = 0
        self.last_result: Optional[Dict[str, Any]] = None
        self.running = True

        # =========================================================
        # ASYNC LEARNING QUEUE
        # =========================================================
        # Response synchronous, learning asynchronous + ordered queue.
        # think_and_respond() returns to the user as soon as the LLM
        # reply is ready; the full Experience -> Learning -> Evaluate
        # -> KnowledgeBuilder -> DB pipeline runs in the background,
        # one job at a time, in the exact order turns happened. See
        # core/learning/learning_queue.py for the full rationale.
        self._learning_queue = AsyncLearningQueue(worker=self._run_learning_job)

        # =========================================================
        # LIVE TELEMETRY (for CLI trace + web /api endpoints)
        # =========================================================
        # Real, cumulative counters updated every turn -- no simulated
        # numbers. `last_turn_trace` is the single source of truth
        # both cli.py and the web backend read from after a turn.
        self.last_turn_trace: Optional[Dict[str, Any]] = None
        self.total_turns = 0
        self.total_latency_seconds = 0.0
        self.total_tokens_estimate = 0

        # =========================================================
        # HINGLISH TYPO NORMALIZATION (retrieval-time only)
        # =========================================================
        # A small, expandable dictionary of common Hinglish/typo forms
        # UK actually types (see project chat history) -> their clean
        # form. This is applied ONLY to the copy of the text used for
        # memory retrieval (so "confident retrieval hone chahiye rules
        # for typos" is real, not aspirational) -- the original
        # user_input is still what gets stored/shown, unmodified.
        self.typo_map: Dict[str, str] = {
            "chahie": "chahiye", "chahia": "chahiye", "chaiye": "chahiye",
            "krde": "kar de", "krdo": "kar do", "kr": "kar", "krna": "karna",
            "hoga": "hoga", "hona": "hona", "nhi": "nahi", "nahi": "nahi",
            "mje": "mujhe", "mjhe": "mujhe", "mai": "main", "mein": "main",
            "yhi": "yahi", "yha": "yahan", "wha": "wahan",
            "smjha": "samjha", "smjhna": "samjhna",
            "bta": "bata", "btao": "batao", "bta do": "bata do",
            "thik": "theek", "thk": "theek",
            "acha": "accha", "achha": "accha",
            "rha": "raha", "rhi": "rahi", "rhe": "rahe",
            "kese": "kaise", "kse": "kaise",
            "tmhe": "tumhe", "tmhara": "tumhara", "tm": "tum",
            "dedo": "de do", "dena": "dena",
            # Added from real observed transcript failures -- each of
            # these directly caused an extraction-cascade failure
            # ("Extraction cascade exhausted...", confidence=0.00)
            # before being caught here.
            "hye": "hey", "nam": "naam",
            "onnly": "only", "gielfriend": "girlfriend", "girlfrien": "girlfriend",
            "nahu": "nahi", "crator": "creator",
            "tunhe": "tumhe", "tunhara": "tumhara", "tunhari": "tumhari",
            "muje": "mujhe", "mujje": "mujhe",
            "insoect": "inspect",
        }

    def _normalize_hinglish_typos(self, text: str) -> Dict[str, Any]:
        """
        Whole-word substitution against self.typo_map. Returns the
        normalized text plus the list of corrections actually made,
        so the trace/UI can show real typo-correction data instead of
        nothing (the web frontend has a dedicated slot for this --
        CognitiveTrace.typosCorrected -- that was never populated).
        """
        if not text:
            return {"normalized": text, "corrections": []}

        tokens = re.findall(r"\w+|\W+", text)
        corrections = []
        out_tokens = []
        for tok in tokens:
            key = tok.lower()
            if key in self.typo_map and self.typo_map[key] != key:
                corrected = self.typo_map[key]
                corrections.append({"raw": tok, "corrected": corrected})
                out_tokens.append(corrected)
            else:
                out_tokens.append(tok)

        return {"normalized": "".join(out_tokens), "corrections": corrections}

    # =============================================================
    # THINK AND RESPOND (LLM + IDENTITY + MEMORY + PIPELINE)
    # =============================================================
    
    def think_and_respond(
        self,
        user_input: str,
        identity_profile: Optional[Dict[str, Any]] = None,
        source: str = "cli",
    ) -> str:
        """
        Canonical Brain entry point.

        Flow:
            User Input
              -> Perception
              -> Cognitive Router
              -> Goal / Native / Hybrid / LLM
              -> Brain Decision
              -> Action Response
              -> Trace

        The router is the authority for choosing the cognition route.
        LLM is optional and is only required for routes that actually
        need language cognition/synthesis.
        """
        started = time.time()
        user_input = str(user_input or "").strip()
        self._last_user_input = user_input
        # Fresh per-turn: see build_context() docstring note above.
        self._context_cache = {}

        # THE ACTUAL FIX (UK's explicit ask: "good morning bolo" jaisi
        # baat ek RULE hai, fact nahi, aur JARVIS ko yaad rakhna chahiye"):
        # this used to run ONLY inside the LLM route further below, so a
        # standing instruction like "hamesha subah good morning bolo"
        # was captured ONLY on turns the router happened to send to the
        # LLM -- a clear imperative like that is exactly the kind of
        # message the router is likely to classify as a goal/native
        # instruction instead, meaning the rule was silently never
        # captured at all. Rule capture is a handful of zero-cost regex
        # checks against the user's own words (see core/cognition/
        # user_rules.py) -- it must run on EVERY turn, before routing
        # decides anything, not just the ones that end up needing the LLM.
        try:
            self._user_rules.capture_from_message(user_input)
        except Exception:
            pass
        try:
            self.standing_instructions.capture_from_message(user_input)
        except Exception:
            pass
        # OUTCOME FEEDBACK, part 2/2 (2026-09-11 roadmap Phase 6): if
        # THIS message reads as UK correcting the PREVIOUS answer, the
        # facts that answer was built from (captured last turn -- see
        # the capture site right after build_response_brief() below)
        # get weakened. Real negative evidence, not internal
        # self-corroboration. Deliberately checked BEFORE
        # last_turn_fact_ids gets overwritten by this turn's own
        # brief-building further down.
        try:
            if detect_correction(user_input) and self.last_turn_fact_ids:
                semantic = getattr(self.memory, "semantic", None)
                if semantic is not None and hasattr(semantic, "weaken"):
                    weakened = []
                    for kid in self.last_turn_fact_ids:
                        try:
                            semantic.weaken(kid, confidence_delta=0.15)
                            weakened.append(kid)
                        except Exception:
                            continue
                    if weakened:
                        log_event("brain", f"negative outcome feedback: weakened {len(weakened)} fact(s) used in the previous answer after UK's correction", level="info")
                        self._emit("OUTCOME_FEEDBACK_NEGATIVE", {"weakened_knowledge_ids": weakened})
        except Exception:
            pass

        self._emit(
            "BRAIN_CYCLE_STARTED",
            {
                "source": source,
                "user_input": user_input,
            },
        )

        # ---------------------------------------------------------
        # 0. NATIVE DIRECT-ANSWER FAST PATH (before ANY LLM call)
        # ---------------------------------------------------------
        # This is what actually makes "every API call has a cost" real
        # instead of a design statement. Without this, a simple recall
        # question like "mera favourite color kya hai" still spent 3
        # LLM calls before ever reaching the LLM route's own fast path
        # below: perception's extraction cascade tries up to 2 (primary
        # + refined), then semantic understanding's own LLM fallback
        # tries a 3rd when native symbolic parsing is uncertain -- all
        # BEFORE routing even decides whether an LLM is needed at all.
        # Checking here, first, means a fact JARVIS already has costs
        # zero API calls end to end, not just zero for the final
        # response-generation step.
        try:
            early_context = self.build_context(query=user_input, recent_limit=0, knowledge_limit=6) if hasattr(self, "build_context") else {}
        except Exception:
            early_context = {}
        speaker_name = identity_profile.get("creator") if isinstance(identity_profile, dict) else None
        self._native_reasoner.identity = getattr(self, "identity_system", None)
        self._native_reasoner.llm_bridge = self.llm
        try:
            native_answer = self._native_reasoner.try_answer(user_input, early_context, speaker_name=speaker_name)
        except Exception:
            native_answer = None
        direct_answer = native_answer.text if native_answer is not None else None
        answered_by = native_answer.resolver if native_answer is not None else None
        if direct_answer is not None:
            self.last_perception = {
                "user_input": user_input, "normalized_text": user_input,
                "source": answered_by, "confidence": 1.0, "uncertainty": 0.0,
                "reason": "answered directly from stored knowledge; perception/LLM skipped entirely",
            }
            self.last_cognitive_decision = {"mode": "llm", "confidence": 1.0, "reason": f"native fast path: {answered_by}"}
            self.last_brain_decision = {"mode": "llm", "status": "completed", "answered_by": answered_by}
            response = self._record_action_response(
                mode="llm", status="completed", response=direct_answer,
                action={"answered_by": answered_by},
            )
            self._trace(user_input, response, self.last_cognitive_decision, self.last_perception, started, False)
            return response

        # ---------------------------------------------------------
        # 1. PERCEPTION
        # ---------------------------------------------------------
        try:
            perception = self._perceive(user_input)
        except Exception as exc:
            self.last_brain_decision = {
                "mode": "error",
                "status": "perception_failed",
                "error": str(exc),
            }
            response = f"[Brain Perception Error: {exc}]"
            self._record_action_response(
                mode="error",
                status="failed",
                response=response,
                error=str(exc),
            )
            self._trace(
                user_input,
                response,
                {"mode": "error", "status": "perception_failed"},
                {},
                started,
                self.llm is not None,
            )
            return response

        # ---------------------------------------------------------
        # 2. COGNITIVE ROUTING
        # ---------------------------------------------------------
        try:
            route = self._route_cognition(user_input, perception)
        except Exception as exc:
            self.last_brain_decision = {
                "mode": "error",
                "status": "routing_failed",
                "error": str(exc),
            }
            response = f"[Brain Routing Error: {exc}]"
            self._record_action_response(
                mode="error",
                status="failed",
                response=response,
                error=str(exc),
            )
            self._trace(
                user_input,
                response,
                {"mode": "error", "status": "routing_failed"},
                perception,
                started,
                self.llm is not None,
            )
            return response

        mode = str(route.get("mode", "llm")).lower()
        intent = perception.get("intent") or {}
        skill_name = (
            intent.get("skill")
            or intent.get("name")
            if isinstance(intent, dict)
            else None
        )

        # ---------------------------------------------------------
        # 3. GOAL ROUTE
        # ---------------------------------------------------------
        if mode == "goal":
            perceived_goal = perception.get("goal")

            result = self._register_and_plan_goal(perceived_goal)

            if result.get("status") != "planned":
                response = "Goal could not be planned."
                self.last_brain_decision = {
                    "mode": "goal",
                    "status": result.get("status", "failed"),
                    "goal": perceived_goal,
                }
                self._record_action_response(
                    mode="goal",
                    status="failed",
                    response=response,
                    action={"goal": perceived_goal},
                )
            else:
                goal = result.get("goal") or {}
                plan = result.get("plan") or []

                response = (
                    f"Goal accepted and planned: {goal.get('text', '')}"
                    if goal.get("text")
                    else "Goal accepted and planned."
                )

                self.last_brain_decision = {
                    "mode": "goal",
                    "status": "planned",
                    "goal": goal,
                    "plan": plan,
                }

                self._record_action_response(
                    mode="goal",
                    status="planned",
                    response=response,
                    action={
                        "goal": goal,
                        "plan": plan,
                    },
                )

            self._trace(
                user_input,
                response,
                route,
                perception,
                started,
                self.llm is not None,
            )
            return response

        # ---------------------------------------------------------
        # 4. NATIVE / TOOL ROUTE
        # ---------------------------------------------------------
        if mode in {"tool", "native"}:
            if self.skill_executor is None or not skill_name:
                response = self._fallback(user_input)

                self.last_brain_decision = {
                    "mode": "native",
                    "status": "no_capability",
                    "skill": skill_name,
                }

                self._record_action_response(
                    mode="native",
                    status="failed",
                    response=response,
                    action={"skill": skill_name},
                    error="capability_not_available",
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

            try:
                native_result = self.skill_executor.execute(
                    skill_name,
                    user_input=user_input,
                )

                response = str(native_result)

                self.last_brain_decision = {
                    "mode": "native",
                    "status": "completed",
                    "skill": skill_name,
                    "action_result": response,
                }

                self._record_action_response(
                    mode="native",
                    status="completed",
                    response=response,
                    action={"skill": skill_name},
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

            except Exception as exc:
                response = f"[Brain Action Error: {exc}]"

                self.last_brain_decision = {
                    "mode": "native",
                    "status": "failed",
                    "skill": skill_name,
                    "error": str(exc),
                }

                self._record_action_response(
                    mode="native",
                    status="failed",
                    response=response,
                    action={"skill": skill_name},
                    error=str(exc),
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

        # ---------------------------------------------------------
        # 5. HYBRID ROUTE
        # ---------------------------------------------------------
        if mode == "hybrid":
            if self.skill_executor is None or not skill_name:
                response = self._fallback(user_input)

                self.last_brain_decision = {
                    "mode": "hybrid",
                    "status": "no_native_capability",
                    "skill": skill_name,
                }

                self._record_action_response(
                    mode="hybrid",
                    status="failed",
                    response=response,
                    action={"skill": skill_name},
                    error="capability_not_available",
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

            try:
                native_result = self.skill_executor.execute(
                    skill_name,
                    user_input=user_input,
                )

                synthesized = self._hybrid_synthesize(
                    user_input=user_input,
                    skill_name=skill_name,
                    native_result=native_result,
                    source=source,
                )

                response = str(synthesized)

                self.last_brain_decision = {
                    "mode": "hybrid",
                    "status": "completed",
                    "native_skill": skill_name,
                    "native_result": str(native_result),
                }

                self._record_action_response(
                    mode="hybrid",
                    status="completed",
                    response=response,
                    action={
                        "skill": skill_name,
                        "native_result": str(native_result),
                    },
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

            except Exception as exc:
                response = f"[Brain Hybrid Error: {exc}]"

                self.last_brain_decision = {
                    "mode": "hybrid",
                    "status": "failed",
                    "skill": skill_name,
                    "error": str(exc),
                }

                self._record_action_response(
                    mode="hybrid",
                    status="failed",
                    response=response,
                    action={"skill": skill_name},
                    error=str(exc),
                )

                self._trace(
                    user_input,
                    response,
                    route,
                    perception,
                    started,
                    self.llm is not None,
                )
                return response

        # ---------------------------------------------------------
        # 6. LLM / KNOWN / OTHER LANGUAGE ROUTE
        # ---------------------------------------------------------
        if self.llm is None:
            response = self._fallback(user_input)

            self.last_brain_decision = {
                "mode": mode,
                "status": "llm_unavailable",
            }

            self._record_action_response(
                mode=mode,
                status="degraded",
                response=response,
            )

            self._trace(
                user_input,
                response,
                route,
                perception,
                started,
                False,
            )
            return response

        # Reuse the existing LLM + memory implementation, but do not
        # recursively call think_and_respond(). The LLM bridge is the
        # language cognition provider for this route.
        typo_result = self._normalize_hinglish_typos(user_input)
        retrieval_query = typo_result["normalized"]

        context = (
            self.build_context(query=retrieval_query, recent_limit=3)
            if hasattr(self, "build_context")
            else {}
        )

        # Rule capture now runs unconditionally near the top of
        # think_and_respond() (before routing), so every route -- not
        # just this LLM one -- captures standing instructions. Only the
        # read side is needed here.
        active_rules = []
        try:
            active_rules = self._user_rules.get_active_rules()
        except Exception:
            pass

        bot_name = "JARVIS"
        creator_name = "UK"

        if isinstance(identity_profile, dict):
            bot_name = identity_profile.get("name", bot_name)
            creator_name = identity_profile.get("creator", creator_name)

        # THE ACTUAL FIX (UK's explicit ask: "Brain ko pata hona chahiye
        # wo kaun hai, sirf identity route nahi"): previously
        # self.identity_system (JarvisIdentity -- purpose, invariants,
        # the REAL learned owner name/addressing-preference, live
        # capabilities) was only ever wired into the narrow native
        # "identity question" fast path (see _native_reasoner.identity
        # above). Every OTHER route -- including this LLM route, which
        # handles the majority of turns -- never read it at all, so the
        # model only ever saw the two bare hardcoded strings
        # "JARVIS"/"UK" cli.py passes on every single call, with no
        # purpose, no real learned name, no capability list. This block
        # pulls the SAME structured identity data the identity fast path
        # already uses and folds it into every LLM call, not just
        # identity-shaped questions.
        identity_block = None
        identity_system = getattr(self, "identity_system", None)
        if identity_system is not None:
            try:
                inv = identity_system.invariants()
                owner = identity_system.owner_profile()
                current = identity_system.current_self()
                bot_name = inv.get("name", bot_name)
                if owner.get("known"):
                    creator_name = owner["display_name"]
                identity_block = {
                    "i_am": inv.get("name"),
                    "designation": inv.get("designation"),
                    "role": inv.get("role"),
                    "purpose": inv.get("purpose"),
                    "created_by": inv.get("creator"),
                    "talking_to": owner.get("display_name") or inv.get("creator"),
                    "talking_to_is_creator": True,
                    "live_capabilities": current.get("capabilities", [])[:12],
                    # UK's explicit ask: JARVIS previously had no idea
                    # whether a turn arrived from the CLI terminal or the
                    # web browser chat -- `source` was passed all the way
                    # down to think_and_respond() but only ever used for
                    # event/learning metadata, never told to the model or
                    # made answerable. Real, cheap, already-available.
                    "channel": source,
                }
            except Exception:
                identity_block = None

        # Native direct-answer fast path: a narrow class of "what is my
        # X" recall questions with an exact stored fact can be answered
        # without spending an LLM call at all. This is the concrete
        # "every API call has a cost" behaviour -- an actual skip, not
        # a policy statement. Anything even slightly ambiguous falls
        # through to the LLM route below unchanged.
        # Second chance at the native fast path: the early check above
        # (step 0) used the raw, non-typo-corrected user_input and a
        # narrower context. This one runs against the typo-normalized
        # retrieval query and the fuller LLM-route context, so a fact
        # that only surfaces after typo correction still gets answered
        # for free instead of falling through to a real LLM call.
        direct_answer = try_direct_recall_answer(user_input, context)
        if direct_answer is not None:
            self.last_brain_decision = {
                "mode": "llm",
                "status": "completed",
                "answered_by": "native_direct_recall",
            }
            response = direct_answer
            self._record_action_response(
                mode="llm",
                status="completed",
                response=response,
                action={"answered_by": "native_direct_recall"},
            )
            self._trace(user_input, response, route, perception, started, True)
            return response

        # Structured response brief (see response_brief.py): Brain's own
        # native reasoning (perception, retrieval, rules) assembles a
        # small, strictly-typed schema of what's actually true and what
        # the user asked. The LLM's only job is to phrase ONE reply from
        # it -- it does not get raw dict dumps of memory objects and it
        # is explicitly told not to invent facts outside the schema.
        self_authored_rules = []
        try:
            self_authored_rules = get_self_authored_rules(self.memory)
        except Exception:
            pass
        brief = build_response_brief(
            user_input=user_input,
            perception=perception,
            context=context,
            active_rules=active_rules,
            self_authored_rules=self_authored_rules,
            bot_name=bot_name,
            creator_name=creator_name,
        )

        # OUTCOME FEEDBACK, part 1/2 (2026-09-11 roadmap Phase 6):
        # snapshot which real stored facts were actually surfaced to
        # the LLM THIS turn, so that if UK corrects JARVIS on the
        # VERY NEXT turn ("galat hai", "wrong", ...), Brain knows
        # exactly which facts to weaken -- see the correction-
        # detection block near the top of this method (searches for
        # detect_correction(user_input) against self.last_turn_fact_ids,
        # which still holds THIS turn's ids until the line below runs
        # again next turn). Deliberately captured here (after the
        # brief that will actually reach the LLM is built), not
        # earlier from build_context()'s raw retrieval, so this only
        # reflects facts that were genuinely part of what the LLM saw.
        try:
            self.last_turn_fact_ids = [
                kid for kid in (
                    getattr(item, "knowledge_id", None) if not isinstance(item, dict) else item.get("knowledge_id")
                    for item in (context.get("relevant_knowledge") or [])
                ) if kid
            ]
        except Exception:
            self.last_turn_fact_ids = []

        # Response Data Contract (blueprint section 13 / Rule 08): the
        # brief must itself be well-formed BEFORE it's allowed to reach
        # the LLM -- this is what turns "response_brief.py builds a
        # nice-looking dict" into an actually-enforced organ boundary,
        # matching the same contract-first discipline every other layer
        # transition already has (see core/contracts/schemas.py
        # "response.input"/"response.output").
        try:
            brief = validate_input("response", brief)
        except ContractError as exc:
            log_event("brain", f"response brief failed its own contract, using it anyway (degraded): {exc}", level="warning")

        system_prompt = (
            f"You are {bot_name}, a self-contained cognitive AI organism. "
            f"The user is {creator_name}, your developer and creator -- never "
            f"swap roles or claim to be {creator_name}. You will be given a "
            f"structured JSON brief below describing this turn. Follow its "
            f"instructions_for_llm exactly.\n\n"
            + (f"YOUR IDENTITY (who you are, real and current, not a persona to improvise):\n"
               f"{json.dumps(identity_block, ensure_ascii=False)}\n\n" if identity_block else "")
            + f"BRIEF:\n{json.dumps(brief, ensure_ascii=False)}"
        )

        # The current user message must NEVER be lost to context-budget
        # truncation. CognitiveBudgeter trims each side of the payload
        # by *dropping the tail*, so anything that must survive has to
        # live in its own short, isolated blob rather than at the end
        # of a long, unbounded memory dump. The live question therefore
        # stays here, separate from the brief above.
        context_prompt = f"{creator_name}: {user_input}\n\n{bot_name}:"

        try:
            # TOOL-CALLING (M2, 2026-09-11): tried BEFORE the plain
            # generate() path below. See core/orchestration/
            # tool_registry.py's module docstring for the full design
            # rationale (cortex-basal-ganglia gating, why this replaced
            # a regex-routing proposal UK explicitly rejected). Returns
            # None (falls through unchanged to plain generate()) when
            # tool-calling isn't usable this turn (offline, no tool
            # was actually needed and the model preferred plain text,
            # or the loop failed) -- this is purely additive, nothing
            # below this block changes.
            tool_response = None
            try:
                from .tool_registry import run_tool_loop
                # Reset BEFORE attempting -- run_tool_loop() only ever
                # sets this on paths that actually reach its internal
                # loop; if generate_with_tools isn't available at all
                # (offline, no Groq key) it returns None immediately
                # without touching this, which would otherwise leave
                # a PREVIOUS turn's trace looking like it happened this
                # turn in cli.py's "4c. TOOL CALLS" panel / monitor.py.
                self.last_tool_call_trace = []
                tool_response = run_tool_loop(self, system_prompt=system_prompt, user_message=user_input)
            except Exception as exc:
                log_event("brain", f"tool-calling loop failed, falling back to plain generation: {exc}", level="warning")
                tool_response = None

            if tool_response:
                response = tool_response
            else:
                generate = getattr(self.llm, "generate", None)

                if callable(generate):
                    response = str(
                        generate(
                            system_prompt,
                            context_prompt,
                        )
                    ).strip()
                else:
                    generate_response = getattr(
                        self.llm,
                        "generate_response",
                        None,
                    )

                    if not callable(generate_response):
                        raise AttributeError(
                            "LLM bridge exposes neither generate() nor "
                            "generate_response()."
                        )

                    response = str(
                        generate_response(
                            system_prompt=system_prompt,
                            user_input=context_prompt,
                            level="response_generation",
                        )
                    ).strip()

            if not response:
                response = "..."

            # response.output side of the Response Data Contract: the
            # LLM's output returns to JARVIS and is not automatically
            # trusted (Rule 09). check_response_grounding() (see
            # response_brief.py) is a real, conservative check -- it
            # flags proper-noun/number tokens in the reply that don't
            # appear anywhere in the brief's own legitimate sources, so
            # the most flagrant class of fabrication (an invented name,
            # place, or figure) is caught. It only ever WARNS: a false
            # positive here would silently corrupt real replies, which
            # would be worse than an occasional missed hallucination.
            grounding = check_response_grounding(
                response, brief,
                relations_extracted_this_turn=len((perception.get("semantic_understanding") or {}).get("relations") or []) if isinstance(perception, dict) else None,
            )
            # Detection-side safety net for false action claims (see
            # check_action_claim_grounding's docstring) -- unlike the
            # general grounding check above, this one is narrow and
            # confident enough to safely SUBSTITUTE the response, not
            # just flag it. action_executed is hardcoded False here:
            # reaching this branch at all already means routing found
            # no native/skill capability for this turn (this is the
            # "no executable native capability was selected" path --
            # see the ROUTING trace line) -- so no real action ran.
            action_correction = check_action_claim_grounding(response, action_executed=False)
            if action_correction:
                log_event(
                    "brain",
                    "response claimed a delete/update/verify action that never executed -- substituted an honest reply",
                    level="warning",
                )
                response = action_correction
                grounding = check_response_grounding(response, brief, relations_extracted_this_turn=0)
            try:
                validate_output("response", {
                    "text": response,
                    "stayed_within_brief": grounding.stayed_within_brief,
                    "flagged_unsupported": grounding.flagged_unsupported,
                })
            except ContractError as exc:
                log_event("brain", f"response.output contract violation: {exc}", level="warning")
            if not grounding.stayed_within_brief:
                log_event(
                    "brain",
                    f"response may contain unsupported content not present in the brief: {grounding.flagged_unsupported}",
                    level="warning",
                )

            self.last_brain_decision = {
                "mode": "llm",
                "status": "completed",
                "stayed_within_brief": grounding.stayed_within_brief,
            }

            self._record_action_response(
                mode="llm",
                status="completed",
                response=response,
            )

            self._trace(
                user_input,
                response,
                route,
                perception,
                started,
                True,
            )
            return response

        except Exception as exc:
            response = f"[Brain Thinking Error: {exc}]"

            self.last_brain_decision = {
                "mode": "llm",
                "status": "failed",
                "error": str(exc),
            }

            self._record_action_response(
                mode="llm",
                status="failed",
                response=response,
                error=str(exc),
            )

            self._trace(
                user_input,
                response,
                route,
                perception,
                started,
                True,
            )
            return response

    # =============================================================
    # ASYNC LEARNING HAND-OFF
    # =============================================================

    def _enqueue_learning(
        self,
        event_type: str,
        context: Dict[str, Any],
        action: Dict[str, Any],
        outcome: Dict[str, Any],
        source: Optional[str],
        importance: float,
    ) -> None:
        """
        Push one completed turn onto the ordered background learning
        queue. If the queue isn't running for any reason (e.g. start()
        was never called), falls back to the old synchronous path so a
        turn is never silently dropped -- it just costs latency instead,
        exactly like before this change.
        """
        job = {
            "event_type": event_type,
            "context": context,
            "action": action,
            "outcome": outcome,
            "source": source,
            "importance": importance,
            "build_knowledge": True,
            "auto_accept": self.auto_accept_knowledge,
        }

        if self._learning_queue.is_alive():
            if not self._learning_queue.submit(job):
                log_event("brain", "learning queue rejected job (full); running inline as fallback.", level="warning")
                self._run_learning_job(job)
        else:
            # Queue never started (e.g. Brain used standalone/tests) —
            # keep behaviour correct by falling back to synchronous.
            self._run_learning_job(job)

    def _run_learning_job(self, job: Dict[str, Any]) -> None:
        """Executed on the background learning-queue thread (or inline
        as a fallback). Never lets a learning failure reach the user."""
        self._set_learning_active(True)
        try:
            self.process_experience(
                event_type=job["event_type"],
                context=job["context"],
                action=job["action"],
                outcome=job["outcome"],
                source=job["source"],
                importance=job["importance"],
                build_knowledge=job["build_knowledge"],
                auto_accept=job["auto_accept"],
            )
        except Exception as exp_err:
            log_event("brain", f"could not process experience: {exp_err}", level="error")
        finally:
            self._set_learning_active(False)

    def _set_learning_active(self, active: bool) -> None:
        """Best-effort mirror of live learning-worker activity into the
        state bus, so monitor.py can show LEARNING as distinct from the
        synchronous IDLE/PERCEIVING/INDEXING/EXECUTING turn pipeline --
        the background worker legitimately overlaps with the next turn."""
        try:
            from ..runtime.state_bus import get_state_bus

            bus = get_state_bus(create=False)
            if bus is not None:
                bus.update_learning(status=self._learning_queue.status(), active=active)
        except Exception:
            pass

    # =============================================================
    # PROCESS EXPERIENCE
    # =============================================================

    def process_experience(
        self,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None,
        outcome: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        importance: float = 0.5,
        build_knowledge: bool = True,
        auto_accept: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Process one completed experience.

        Flow:
            Brain -> ExperienceEngine -> LearningCoordinator ->
            SelfEvaluator -> KnowledgeBuilder -> acceptance

        `auto_accept` defaults to self.auto_accept_knowledge when not
        explicitly passed, so the "built but never persisted" bug
        can't silently recur.
        """
        if self.experience is None:
            raise RuntimeError("ExperienceEngine is not connected.")

        if auto_accept is None:
            auto_accept = self.auto_accept_knowledge

        started_at = time.time()

        # =========================================================
        # 1. EXPERIENCE ENGINE
        # =========================================================
        experience_result = self.experience.process(
            event_type=event_type,
            context=context or {},
            action=action or {},
            outcome=outcome or {},
            source=source,
            importance=importance,
        )

        if not isinstance(experience_result, dict):
            raise RuntimeError("ExperienceEngine returned an invalid result.")

        experience = experience_result.get("experience", {})

        # =========================================================
        # 2. LEARNING COORDINATOR (preferred path)
        # =========================================================
        learning_result = None

        if self.learning is not None and build_knowledge:
            learn_method = getattr(self.learning, "learn", None)
            if not callable(learn_method):
                raise RuntimeError("LearningCoordinator does not expose learn().")

            learning_result = learn_method(
                experience=experience,
                auto_accept=auto_accept,
            )

        # =========================================================
        # 3. COMPATIBILITY FALLBACK (no LearningCoordinator connected)
        # =========================================================
        elif self.learning is None and build_knowledge:
            evaluation = None
            if self.evaluator is not None:
                evaluation = self.evaluator.evaluate(experience)

            knowledge = None
            if self.knowledge_builder is not None and evaluation is not None:
                knowledge = self.knowledge_builder.build(
                    experience=experience,
                    evaluation=evaluation,
                )

            accepted = False
            # THIS is the part that was previously missing: without
            # it, `knowledge` was created but never written to the
            # persistent knowledge table.
            if (
                auto_accept
                and knowledge is not None
                and self.knowledge_builder is not None
            ):
                knowledge_id = (
                    knowledge.get("id")
                    if isinstance(knowledge, dict)
                    else getattr(knowledge, "id", None)
                )
                accept_method = getattr(self.knowledge_builder, "accept", None)
                if knowledge_id is not None and callable(accept_method):
                    try:
                        accept_method(knowledge_id)
                        accepted = True
                    except Exception as accept_err:
                        log_event("brain", f"could not auto-accept knowledge: {accept_err}", level="warning")

            learning_result = {
                "success": True,
                "experience": experience,
                "evaluation": evaluation,
                "knowledge": knowledge,
                "accepted": accepted,
                "duration": 0.0,
                "timestamp": time.time(),
            }

        # =========================================================
        # 4. BUILD RESULT
        # =========================================================
        evaluation = None
        knowledge = None
        accepted = False

        if isinstance(learning_result, dict):
            evaluation = learning_result.get("evaluation")
            knowledge = learning_result.get("knowledge")
            accepted = bool(learning_result.get("accepted", False))

        result = {
            "type": "BRAIN_EXPERIENCE_CYCLE",
            "success": True,
            "experience": experience,
            "learning": learning_result,
            "evaluation": evaluation,
            "knowledge": knowledge,
            "accepted": accepted,
            "episode_id": experience_result.get("episode_id"),
            "duration": time.time() - started_at,
            "timestamp": time.time(),
        }

        # OUTCOME FEEDBACK positive side (2026-09-11 roadmap Phase 6):
        # when SelfEvaluator judges the WHOLE turn a success, lightly
        # reinforce the facts that were actually surfaced to the LLM
        # for it (self.last_turn_fact_ids, captured right after
        # build_response_brief()). Distinct from NativeReasoner's
        # existing reinforcement (which fires immediately on a
        # successful NATIVE direct-recall hit, a different code path)
        # -- this is the LLM-answered-turn half that never existed
        # before: those facts previously got zero feedback regardless
        # of whether the turn actually went well.
        try:
            if isinstance(evaluation, dict) and evaluation.get("success") and self.last_turn_fact_ids:
                semantic = getattr(self.memory, "semantic", None)
                if semantic is not None and hasattr(semantic, "reinforce"):
                    for kid in self.last_turn_fact_ids:
                        try:
                            semantic.reinforce(kid, confidence_delta=0.02)
                        except Exception:
                            continue
        except Exception:
            pass

        # ---------------------------------------------------------
        # POST-RESPONSE REASONING (response -> reasoning -> experience
        # -> learning): the structured 11-question self-reflection
        # cycle, built natively from the evaluation/experience data
        # already computed above -- zero extra LLM calls per turn.
        # See core/learning/post_response_reasoning.py.
        try:
            reasoning_trace = build_reasoning_trace(experience, evaluation, accepted, recent_traces=self.last_reasoning_traces)
            result["reasoning"] = reasoning_trace.as_dict()
            self.last_reasoning_traces.append(result["reasoning"])
            if len(self.last_reasoning_traces) > 50:
                self.last_reasoning_traces = self.last_reasoning_traces[-50:]
            # THE ACTUAL FEEDBACK LOOP: when the reasoning cycle decides
            # this recommendation is genuinely worth adopting (repeated,
            # not a one-off), JARVIS writes a SELF-authored rule into
            # memory -- distinct from UserRuleStore's user-stated rules
            # -- so future turns' response briefs are actually
            # influenced by what JARVIS itself has learned, not just a
            # judgment that gets logged and forgotten.
            # THE ACTUAL FEEDBACK LOOP (UK's explicit ask: JARVIS may
            # author its own rules from repeated evidence, exactly like
            # a real organism would -- but MUST NOT apply one until UK
            # has verified it. Previously this wrote straight to memory
            # and get_self_authored_rules() read it back on the very
            # next turn with zero human confirmation in between -- a
            # self-proposed rule was silently already governing
            # responses before anyone ever saw it. Stored the same way,
            # just tagged "pending_confirmation" instead of live --
            # see get_self_authored_rules() (only reads "confirmed"
            # ones) and Brain.confirm_self_rule()/reject_self_rule()/
            # list_pending_self_rules() below, reachable via cli.py's
            # /pending_rules, /confirm_rule, /reject_rule.
            if reasoning_trace.adopt_as_learning:
                try:
                    semantic = getattr(self.memory, "semantic", None)
                    if semantic is not None and hasattr(semantic, "remember"):
                        # UNIQUE PREDICATE (fix for a real collision bug
                        # found 2026-09-11: predicate was previously just
                        # f"learned_behavior_{mode}" -- shared by EVERY
                        # distinct proposal under the same mode, so a
                        # second, different next_time_different text
                        # would silently overwrite the first one's row,
                        # including union-merging its tags (a rejected
                        # row could end up tagged BOTH "rejected" and
                        # "pending_confirmation" at once). Hashing the
                        # actual recommendation text into the predicate
                        # gives each distinct proposal its own row;
                        # re-proposing the IDENTICAL text still correctly
                        # reinforces the same row via remember()'s normal
                        # update path.
                        rule_key = hashlib.sha1(
                            reasoning_trace.next_time_different.strip().lower().encode("utf-8")
                        ).hexdigest()[:10]
                        predicate = f"learned_behavior_{reasoning_trace.mode}_{rule_key}"

                        # REJECTION MEMORY (UK's explicit ask: "reject
                        # kiya to dubara wahi rule na banaye"). Previously
                        # reject_self_rule() hard-deleted the row, so
                        # nothing remembered a rejection ever happened --
                        # the identical recommendation would just get
                        # re-proposed the next time the pattern repeated
                        # 3x, forcing UK to reject the same thing forever.
                        # reject_self_rule() now tombstones instead of
                        # deleting (tags=["rejected"], see below) -- check
                        # for that tombstone BEFORE writing a new proposal.
                        already_rejected = False
                        try:
                            existing_rows = semantic.find(subject="jarvis_self_rule", predicate=predicate) or []
                            already_rejected = any("rejected" in (getattr(r, "tags", None) or []) for r in existing_rows)
                        except Exception:
                            already_rejected = False

                        if already_rejected:
                            log_event("brain", f"self-authored rule SUPPRESSED (previously rejected by UK, not re-proposing): {reasoning_trace.next_time_different}", level="info")
                        else:
                            rule_knowledge = semantic.remember(
                                subject="jarvis_self_rule",
                                predicate=predicate,
                                value=reasoning_trace.next_time_different,
                                confidence=0.75,
                                importance=0.6,
                                source="self_reasoning",
                                tags=["self_authored", "pending_confirmation"],
                                namespace="SYSTEM",
                                # JARVIS's own inferred conclusion, nothing
                                # external checked it yet -- must read as
                                # unverified until UK reviews it via
                                # /confirm_rule (see confirm_self_rule()
                                # below, which upgrades this to
                                # "user_stated" on confirmation).
                                source_type="llm_unverified",
                            )
                            # EVIDENCE/TRACEABILITY (UK's explicit ask:
                            # "clarify kare ki kyun banaya, kya reason
                            # tha"). Previously only the terse conclusion
                            # (next_time_different) was persisted -- the
                            # supporting Q&A (what_and_why/strategy_
                            # evidence/evidence_reliability/change_reason)
                            # lived only in the ephemeral trace log and
                            # was gone on restart. Stored as a companion
                            # record under the SAME memory store, linked
                            # by the rule's own knowledge_id as the
                            # predicate -- no new schema needed, and
                            # explain_self_rule() below reads it back.
                            try:
                                semantic.remember(
                                    subject="jarvis_self_rule_evidence",
                                    predicate=rule_knowledge.knowledge_id,
                                    value=json.dumps({
                                        "what_and_why": reasoning_trace.what_and_why,
                                        "outcome_gap_reason": reasoning_trace.outcome_gap_reason,
                                        "strategy_evidence": reasoning_trace.strategy_evidence,
                                        "change_reason": reasoning_trace.change_reason,
                                        "evidence_reliability": reasoning_trace.evidence_reliability,
                                        "repeated_occurrences": "3+ matching turns in the last 20 (see adopt_as_learning threshold)",
                                    }, ensure_ascii=False),
                                    confidence=0.75,
                                    importance=0.6,
                                    source="self_reasoning",
                                    tags=["self_rule_evidence"],
                                    namespace="SYSTEM",
                                    source_type="llm_unverified",
                                )
                            except Exception as exc:
                                log_event("brain", f"could not write self-rule evidence record: {exc}", level="warning")
                            log_event("brain", f"self-authored rule PROPOSED, awaiting UK's confirmation (/pending_rules): {reasoning_trace.next_time_different}", level="info")
                except Exception as exc:
                    log_event("brain", f"could not write self-authored rule: {exc}", level="warning")
            # Aggregate LLM cost-awareness (see DependencyMetrics.
            # record_retry_cost) -- this is what turns "was that retry
            # worth it" from a per-turn guess into a measurable,
            # growing answer JARVIS can actually consult.
            llm_cost = reasoning_trace.llm_cost or {}
            if llm_cost.get("retry_used"):
                self.dependency_metrics.record_retry_cost(
                    retry_used=True, retry_paid_off=bool(llm_cost.get("retry_paid_off")),
                )
                self._check_retry_value_evolution()
        except Exception as exc:
            log_event("brain", f"post-response reasoning failed: {exc}", level="warning")

        self._finish_cycle(result)
        self._emit("BRAIN_EXPERIENCE_PROCESSED", result)

        return result

    # =============================================================
    # LEARN
    # =============================================================

    def learn(self, experience: Dict[str, Any], auto_accept: Optional[bool] = None) -> Dict[str, Any]:
        """Direct learning entry point for an already-structured experience."""
        if not isinstance(experience, dict):
            raise TypeError("experience must be a dictionary.")

        if self.learning is None:
            raise RuntimeError("LearningCoordinator is not connected.")

        method = getattr(self.learning, "learn", None)
        if not callable(method):
            raise RuntimeError("LearningCoordinator does not expose learn().")

        if auto_accept is None:
            auto_accept = self.auto_accept_knowledge

        result = method(experience=experience, auto_accept=auto_accept)
        self._emit("BRAIN_LEARNING_COMPLETED", result)
        return result

    # =============================================================
    # EVALUATE
    # =============================================================

    def evaluate(self, experience: Dict[str, Any]) -> Dict[str, Any]:
        if self.learning is not None:
            method = getattr(self.learning, "evaluate", None)
            if callable(method):
                return method(experience)

        if self.evaluator is None:
            raise RuntimeError("SelfEvaluator is not connected.")

        return self.evaluator.evaluate(experience)

    # =============================================================
    # BUILD KNOWLEDGE
    # =============================================================

    def build_knowledge(
        self,
        experience: Dict[str, Any],
        evaluation: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if self.learning is not None:
            method = getattr(self.learning, "build_knowledge", None)
            if callable(method):
                return method(experience=experience, evaluation=evaluation)

        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")

        if evaluation is None:
            if self.evaluator is None:
                raise RuntimeError("SelfEvaluator is not connected.")
            evaluation = self.evaluator.evaluate(experience)

        return self.knowledge_builder.build(experience=experience, evaluation=evaluation)

    # =============================================================
    # ACCEPT / REJECT KNOWLEDGE
    # =============================================================

    def accept_knowledge(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        if self.learning is not None:
            method = getattr(self.learning, "accept_knowledge", None)
            if callable(method):
                result = method(knowledge_id)
                self._emit("BRAIN_KNOWLEDGE_ACCEPTED", result)
                return result

        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")

        result = self.knowledge_builder.accept(knowledge_id)
        self._emit("BRAIN_KNOWLEDGE_ACCEPTED", result)
        return result

    def reject_knowledge(self, knowledge_id: str, reason: str = "") -> Optional[Dict[str, Any]]:
        if self.learning is not None:
            method = getattr(self.learning, "reject_knowledge", None)
            if callable(method):
                result = method(knowledge_id=knowledge_id, reason=reason)
                self._emit("BRAIN_KNOWLEDGE_REJECTED", result)
                return result

        if self.knowledge_builder is None:
            raise RuntimeError("KnowledgeBuilder is not connected.")

        result = self.knowledge_builder.reject(knowledge_id=knowledge_id, reason=reason)
        self._emit("BRAIN_KNOWLEDGE_REJECTED", result)
        return result

    # =============================================================
    # SELF-AUTHORED RULES -- propose (automatic, see the post-response
    # reasoning block above) / confirm / reject (UK only). A self-
    # authored rule never reaches get_self_authored_rules() (and
    # therefore never influences a response) until confirm_self_rule()
    # has been called on it -- see response_brief.py's
    # get_self_authored_rules() docstring for why.
    # =============================================================

    def list_pending_self_rules(self) -> List[Dict[str, Any]]:
        """Self-authored rules JARVIS has proposed but UK has not yet
        reviewed. Read-only."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "find"):
            return []
        try:
            items = semantic.find(subject="jarvis_self_rule") or []
        except Exception:
            return []
        pending = [
            item for item in items
            if "pending_confirmation" in (getattr(item, "tags", None) or [])
            and "confirmed" not in (getattr(item, "tags", None) or [])
            and "rejected" not in (getattr(item, "tags", None) or [])
        ]
        pending.sort(key=lambda i: getattr(i, "created_at", 0), reverse=True)
        return [
            {
                "knowledge_id": getattr(item, "knowledge_id", None),
                "rule": getattr(item, "value", None),
                "predicate": getattr(item, "predicate", None),
                "confidence": getattr(item, "confidence", None),
                "created_at": getattr(item, "created_at", None),
                "source_type": getattr(item, "source_type", "unknown"),
            }
            for item in pending
        ]

    def confirm_self_rule(self, knowledge_id: str) -> Dict[str, Any]:
        """UK verifies a self-authored rule -- ONLY after this does it
        start influencing responses (get_self_authored_rules() starts
        returning it). remember() merges tags rather than replacing
        them (see SemanticMemory.remember()), so the old
        "pending_confirmation" tag harmlessly lingers alongside the new
        "confirmed" one -- both list_pending_self_rules() and
        get_self_authored_rules() key off "confirmed" being present,
        not "pending_confirmation" being absent."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "get"):
            return {"status": "error", "message": "Semantic memory not connected."}
        item = semantic.get(knowledge_id)
        if item is None or getattr(item, "subject", None) != "jarvis_self_rule":
            return {"status": "not_found", "knowledge_id": knowledge_id}
        try:
            semantic.remember(
                subject=item.subject, predicate=item.predicate, value=item.value,
                confidence=item.confidence, importance=item.importance,
                source=item.source, tags=["confirmed"], namespace=item.namespace,
                # UK personally reviewed and approved this -- that IS a
                # human verification step, so this is exactly the
                # "llm_unverified -> confirmed" upgrade path the
                # provenance system is for. remember()'s merge logic
                # (same value, source_type rank comparison) makes this
                # an upgrade only, never a downgrade.
                source_type="user_stated",
            )
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        self._emit("BRAIN_SELF_RULE_CONFIRMED", {"knowledge_id": knowledge_id, "rule": item.value})
        return {"status": "confirmed", "knowledge_id": knowledge_id, "rule": item.value}

    def reject_self_rule(self, knowledge_id: str) -> Dict[str, Any]:
        """UK declines a self-authored rule. FIX (2026-09-11, UK's
        explicit ask): previously this hard-deleted the row via
        semantic.forget(), which meant nothing remembered the
        rejection ever happened -- the identical recommendation would
        simply get re-proposed the next time its trigger pattern
        repeated 3x, forcing UK to reject the same thing over and
        over. Now the row is TOMBSTONED instead: tags are replaced
        (not merged -- see SemanticMemory.set_tags(), since remember()
        always unions and would leave a stale "pending_confirmation"
        tag sitting next to "rejected" forever) with ["self_authored",
        "rejected"], and the adopt_as_learning block above checks for
        exactly this tombstone before writing a new proposal with the
        same predicate, so a rejected rule stays rejected."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "get"):
            return {"status": "error", "message": "Semantic memory not connected."}
        item = semantic.get(knowledge_id)
        if item is None or getattr(item, "subject", None) != "jarvis_self_rule":
            return {"status": "not_found", "knowledge_id": knowledge_id}
        try:
            if hasattr(semantic, "set_tags"):
                semantic.set_tags(knowledge_id, ["self_authored", "rejected"])
            else:
                # Older SemanticMemory without set_tags -- fall back to
                # the old hard-delete rather than error out, but this
                # means the rejection won't be remembered.
                semantic.forget(knowledge_id)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        result = {"status": "rejected", "knowledge_id": knowledge_id, "rule": item.value}
        self._emit("BRAIN_SELF_RULE_REJECTED", result)
        return result

    def explain_self_rule(self, knowledge_id: str) -> Dict[str, Any]:
        """UK asks "yeh rule kyun banaya" -- reconstructs the actual
        justification (what_and_why / strategy_evidence / evidence_
        reliability / change_reason) from the linked evidence record
        written alongside the rule proposal, instead of only being
        able to show the terse final recommendation text. See the
        adopt_as_learning block above for where this evidence record
        is written (subject="jarvis_self_rule_evidence", predicate=
        this rule's own knowledge_id)."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "get"):
            return {"status": "error", "message": "Semantic memory not connected."}
        item = semantic.get(knowledge_id)
        if item is None or getattr(item, "subject", None) != "jarvis_self_rule":
            return {"status": "not_found", "knowledge_id": knowledge_id}
        evidence: Dict[str, Any] = {}
        try:
            evidence_rows = semantic.find(subject="jarvis_self_rule_evidence", predicate=knowledge_id) or []
            if evidence_rows:
                raw = evidence_rows[0].value
                if isinstance(raw, dict):
                    evidence = raw
                elif isinstance(raw, str):
                    try:
                        evidence = json.loads(raw)
                    except Exception:
                        evidence = {"raw": raw}
        except Exception:
            evidence = {}
        tags = getattr(item, "tags", None) or []
        status = "confirmed" if "confirmed" in tags else ("rejected" if "rejected" in tags else "pending")
        return {
            "knowledge_id": knowledge_id,
            "rule": item.value,
            "status": status,
            "confidence": item.confidence,
            "source_type": getattr(item, "source_type", "unknown"),
            "created_at": item.created_at,
            "evidence": evidence or {"note": "no linked evidence record found (rule may predate the evidence-tracking fix)"},
        }

    def list_standing_instructions(self) -> List[Dict[str, Any]]:
        """All active daily standing instructions (see core/autonomy/
        standing_instructions.py). Read-only."""
        try:
            return self.standing_instructions.list_active()
        except Exception:
            return []

    def remove_standing_instruction(self, knowledge_id: str) -> Dict[str, Any]:
        """UK deletes a standing instruction outright (unlike a
        self-authored rule, there's nothing to "reject then remember
        the rejection" here -- UK stated this one directly, so
        removing it is just removing it)."""
        try:
            removed = self.standing_instructions.remove(knowledge_id)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        result = {"status": "removed" if removed else "not_found", "knowledge_id": knowledge_id}
        self._emit("STANDING_INSTRUCTION_REMOVED", result)
        return result

    def save_verified_fact(self, subject: str, predicate: str, value: str, source_type: str = "llm_unverified") -> Dict[str, Any]:
        """Persist a fact the LLM looked up (or already knew) into
        long-term semantic memory. See core/orchestration/
        tool_registry.py's save_verified_fact tool -- deliberately
        NOT called automatically after every browser_search. UK's
        explicit ask (2026-09-11): most searched facts are for
        answering the immediate question only and must stay
        conversational/ephemeral (already captured in episodic memory
        as part of the normal per-turn experience record -- see
        ExperienceEngine -- which is temporary/session-scoped context,
        not a durable fact store). This method only runs when UK
        explicitly asked to save/remember something, so semantic
        memory doesn't fill with one-off lookups nobody asked to keep."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "remember"):
            return {"status": "error", "message": "Semantic memory not connected."}
        resolved_source_type = source_type if source_type in ("verified", "llm_unverified") else "llm_unverified"
        try:
            knowledge = semantic.remember(
                subject=subject, predicate=predicate, value=value,
                confidence=0.85, importance=0.6,
                source="llm_explicit_save",
                tags=["llm_saved_on_request"],
                namespace="WORLD",
                source_type=resolved_source_type,
            )
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        result = {
            "status": "saved", "knowledge_id": knowledge.knowledge_id,
            "subject": subject, "predicate": predicate, "value": value,
            "source_type": knowledge.source_type,
        }
        self._emit("BRAIN_FACT_SAVED_ON_REQUEST", result)
        return result

    def list_contested_facts(self) -> List[Dict[str, Any]]:
        """Facts where a less-trusted source tried to overwrite a
        more-trusted one and was held back (see SemanticMemory.
        remember()'s M6 contradiction-resolution branch). Read-only."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "list_contested_facts"):
            return []
        try:
            items = semantic.list_contested_facts()
        except Exception:
            return []
        out = []
        for item in items:
            contested = [h for h in (getattr(item, "history", None) or []) if isinstance(h, dict) and h.get("contested_candidate")]
            latest = contested[-1] if contested else {}
            out.append({
                "knowledge_id": getattr(item, "knowledge_id", None),
                "subject": getattr(item, "subject", None),
                "predicate": getattr(item, "predicate", None),
                "current_value": getattr(item, "value", None),
                "current_source_type": getattr(item, "source_type", "unknown"),
                "proposed_value": latest.get("proposed_value"),
                "proposed_source_type": latest.get("proposed_source_type"),
            })
        return out

    def resolve_contested_fact(self, knowledge_id: str, accept_new_value: bool) -> Dict[str, Any]:
        """UK's decision on a contested fact -- see list_contested_facts()."""
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        if semantic is None or not hasattr(semantic, "resolve_contested_fact"):
            return {"status": "error", "message": "Semantic memory not connected."}
        try:
            item = semantic.resolve_contested_fact(knowledge_id, accept_new_value=accept_new_value)
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
        if item is None:
            return {"status": "not_found", "knowledge_id": knowledge_id}
        result = {"status": "resolved", "knowledge_id": knowledge_id, "accepted_new_value": accept_new_value, "current_value": item.value}
        self._emit("BRAIN_CONTESTED_FACT_RESOLVED", result)
        return result

    def get_llm_dependency_stats(self) -> Dict[str, Any]:
        """M8 (2026-09-11, scoped): how much of semantic understanding
        is currently resolved WITHOUT an LLM call this session, and
        whether the learned-native path is taking real share from LLM
        fallback over time. See SemanticLearningBoundary.stats() for
        the full design note on why this is a measurable-telemetry
        slice, not a new autonomous-replacement subsystem."""
        boundary = getattr(self.semantic_understanding, "learning_boundary", None)
        if boundary is None or not hasattr(boundary, "stats"):
            return {"available": False}
        try:
            stats = boundary.stats()
            stats["available"] = True
            return stats
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    # =============================================================
    # CONSOLIDATE
    # =============================================================

    def consolidate(self, limit: int = 50) -> Dict[str, Any]:
        if self.consolidator is None:
            raise RuntimeError("MemoryConsolidator is not connected.")

        result = self.consolidator.consolidate(limit=limit)
        self._emit("BRAIN_MEMORY_CONSOLIDATED", result)
        return result

    def learn_and_consolidate(
        self,
        experience: Dict[str, Any],
        auto_accept: Optional[bool] = None,
        consolidation_limit: int = 50,
    ) -> Dict[str, Any]:
        learning_result = self.learn(experience=experience, auto_accept=auto_accept)

        consolidation_result = None
        if self.consolidator is not None:
            consolidation_result = self.consolidate(limit=consolidation_limit)

        return {
            "learning": learning_result,
            "consolidation": consolidation_result,
            "timestamp": time.time(),
        }

    # =============================================================
    # EVOLUTION
    # =============================================================

    def propose_evolution(self, evaluation: Dict[str, Any], target: str, reason: Optional[str] = None) -> Dict[str, Any]:
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        proposal = self.evolution.propose(evaluation=evaluation, target=target, reason=reason)
        self._emit("BRAIN_EVOLUTION_PROPOSED", proposal)
        return proposal

    def validate_evolution(self, proposal_id: str) -> Dict[str, Any]:
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        return self.evolution.validate(proposal_id)

    def approve_evolution(self, proposal_id: str) -> Dict[str, Any]:
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        return self.evolution.approve(proposal_id)

    def apply_evolution(self, proposal_id: str) -> Dict[str, Any]:
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        result = self.evolution.apply(proposal_id)
        # This is the ONE place a proposal becomes a real, applied change
        # -- so it's the correct place to grow JARVIS's own HISTORY
        # (see core/identity/jarvis_identity.py). Best-effort: identity
        # tracking must never block an evolution apply from succeeding.
        identity_system = getattr(self, "identity_system", None)
        if identity_system is not None:
            try:
                identity_system.record_adaptation(
                    description=f"Applied evolution proposal {proposal_id}",
                    evidence={"proposal_id": proposal_id, "result": result},
                )
            except Exception:
                pass
        return result

    # =============================================================
    # MEMORY CONTEXT (FAISS + Knowledge Graph retrieval)
    # =============================================================

    def build_context(
        self,
        query: Optional[str] = None,
        subject: Optional[str] = None,
        recent_limit: int = 5,
        knowledge_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Retrieve memory context for reasoning from MemoryManager.
        Brain intentionally does not know HOW retrieval works (FAISS
        similarity search, graph traversal, etc.) — that all lives in
        MemoryManager so it can be upgraded independently.
        """
        if self.memory is None:
            empty_context = {
                "recent_experiences": [],
                "relevant_knowledge": [],
                "graph_relations": [],
            }
            self.last_context = empty_context
            return empty_context

        cache_key = (query, subject, recent_limit, knowledge_limit)
        cached = self._context_cache.get(cache_key)
        if cached is not None:
            return cached

        # Only the real cache-miss path does actual FAISS/graph work, so
        # this is the genuine INDEXING stage of the pipeline -- a cache
        # hit is free and shouldn't flicker the monitor's lifecycle state.
        self._emit("CONTEXT_RETRIEVAL_STARTED", {"query": query, "subject": subject})
        result = self.memory.build_context(
            query=query,
            subject=subject,
            recent_limit=recent_limit,
            knowledge_limit=knowledge_limit,
        )
        self._context_cache[cache_key] = result
        self.last_context = result
        self._emit("CONTEXT_RETRIEVAL_COMPLETED", {
            "query": query,
            "recent_experiences": len(result.get("recent_experiences") or []),
            "relevant_knowledge": len(result.get("relevant_knowledge") or []),
            "graph_relations": len(result.get("graph_relations") or []),
        })
        return result

    # =============================================================
    # PLAN / GOALS
    # =============================================================

    def plan(self, goal: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        if self.planner is None:
            raise RuntimeError("Planner is not connected.")
        method = getattr(self.planner, "plan", None)
        if not callable(method):
            raise RuntimeError("Connected planner does not expose plan().")
        return method(goal=goal, context=context or {})

    def create_goal(self, goal: Any) -> Any:
        if self.goal_manager is None:
            raise RuntimeError("GoalManager is not connected.")
        method = getattr(self.goal_manager, "create_goal", None)
        if not callable(method):
            raise RuntimeError("Connected GoalManager does not expose create_goal().")
        return method(goal)

    # =============================================================
    # STATUS
    # =============================================================

    def status(self) -> Dict[str, Any]:
        learning_status = None
        if self.learning is not None:
            method = getattr(self.learning, "status", None)
            if callable(method):
                try:
                    learning_status = method()
                except Exception as exc:
                    learning_status = {"error": str(exc)}

        consolidator_status = None
        if self.consolidator is not None:
            method = getattr(self.consolidator, "status", None)
            if callable(method):
                try:
                    consolidator_status = method()
                except Exception as exc:
                    consolidator_status = {"error": str(exc)}

        return {
            "version": self.VERSION,
            "running": self.running,
            "created_at": self.created_at,
            "cycles": self.cycle_count,
            "last_cycle_at": self.last_cycle_at,
            "auto_accept_knowledge": self.auto_accept_knowledge,
            "total_turns": self.total_turns,
            "total_latency_seconds": self.total_latency_seconds,
            "avg_latency_ms": round(
                (self.total_latency_seconds / self.total_turns) * 1000, 1
            ) if self.total_turns else 0.0,
            "total_tokens_estimate": self.total_tokens_estimate,
            "organs": {
                "memory": self.memory is not None,
                "experience_engine": self.experience is not None,
                "self_evaluator": self.evaluator is not None,
                "knowledge_builder": self.knowledge_builder is not None,
                "memory_consolidator": self.consolidator is not None,
                "learning_coordinator": self.learning is not None,
                "evolution_engine": self.evolution is not None,
                "planner": self.planner is not None,
                "goal_manager": self.goal_manager is not None,
                "llm_bridge": self.llm is not None,
            },
            "learning_status": learning_status,
            "consolidator_status": consolidator_status,
            "async_learning_queue": self._learning_queue.status(),
            # LLM Dependency Metrics (blueprint section 43) -- the
            # measurable answer to "is JARVIS actually needing the LLM
            # less over time", not a description of intent.
            "dependency_metrics": self.dependency_metrics.as_dict(),
            "contradiction_rate": contradiction_rate(self.memory),
        }

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        return self.last_result

    # =============================================================
    # START / STOP
    # =============================================================

    def start(self) -> None:
        self.running = True
        self._learning_queue.start()
        if self.learning is not None:
            method = getattr(self.learning, "start", None)
            if callable(method):
                method()

    def stop(self) -> None:
        self.running = False
        # Drain=True: finish learning whatever is already queued before
        # shutting the worker down, so a clean stop never loses a fact
        # that was already accepted from the user.
        self._learning_queue.stop(drain=True)
        if self.learning is not None:
            method = getattr(self.learning, "stop", None)
            if callable(method):
                method()

    # =============================================================
    # INTERNAL HELPERS
    # =============================================================

    def _finish_cycle(self, result: Dict[str, Any]) -> None:
        self.cycle_count += 1
        self.last_cycle_at = time.time()
        self.last_result = result

    def set_llm_bridge(self, llm_bridge: Any) -> None:
        self.llm = llm_bridge

        if not hasattr(self, "perception") or self.perception is None:
            return

        self.perception.providers = [
            provider
            for provider in self.perception.providers
            if getattr(provider, "name", None) != "llm"
        ]

        if llm_bridge is not None:
            self.perception.add_provider(
                LLMPerceptionProvider(llm_bridge)
            )

    def execute_autonomous_step(self, step: Dict[str, Any], goal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute one planner-approved step through the Brain boundary."""
        started = time.time()
        step_data = dict(step or {})
        action_name = step_data.get("action")
        # THE ACTUAL FIX (UK's explicit ask: idle time should genuinely
        # hunt for facts and resolve its own uncertainty, not sit empty)
        # -- these two actions come from Planner's verify_knowledge plan
        # (core/autonomy/planner.py), now genuinely reachable since
        # idle_loop.py's _find_knowledge_gaps() feeds Curiosity real
        # low-confidence facts. No skill is registered under either
        # name (nothing is registered in skill_registry in this build),
        # so falling through to the generic skill_executor path below
        # would always fail with "no_capability" -- handled natively
        # here instead, directly against real semantic memory.
        if action_name in ("search_supporting_evidence", "update_confidence"):
            return self._execute_verify_knowledge_step(action_name, step_data, goal, started)
        if action_name == "standing_instruction_fire":
            return self._execute_standing_instruction(step_data, started)
        skill_name = step_data.get("capability") or step_data.get("skill") or action_name
        self._emit("BRAIN_CYCLE_STARTED", {"source": "idle", "goal": goal or {}, "step": step_data})
        if step_data.get("requires_confirmation") is True:
            result = {"success": False, "status": "blocked_pending_confirmation", "action": action_name, "result": "confirmation_required"}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": result["status"], "action": action_name}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_COMPLETED", result)
            return result
        if self.skill_executor is None or not skill_name:
            result = {"success": False, "status": "no_capability", "action": action_name, "result": f"capability_not_available: {skill_name}"}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": result["status"], "action": action_name}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_FAILED", result)
            self._enqueue_learning(event_type="AUTONOMOUS_STEP", context={"goal": goal or {}, "step": step_data}, action={"skill": skill_name, "action": action_name}, outcome=result, source="idle", importance=0.3)
            return result
        try:
            native_result = self.skill_executor.execute(skill_name, user_input=step_data.get("input", action_name))
            result = {"success": True, "status": "completed", "action": action_name, "skill": skill_name, "result": str(native_result), "duration": time.time() - started}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": "completed", "skill": skill_name, "action_result": str(native_result)}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_COMPLETED", result)
            self._enqueue_learning(event_type="AUTONOMOUS_STEP", context={"goal": goal or {}, "step": step_data}, action={"skill": skill_name, "action": action_name, "result": str(native_result)}, outcome=result, source="idle", importance=0.5)
            self._emit("BRAIN_CYCLE_COMPLETED", {"source": "idle", "brain_decision": self.last_brain_decision, "action_response": result, "duration": time.time() - started})
            return result
        except Exception as exc:
            result = {"success": False, "status": "failed", "action": action_name, "skill": skill_name, "result": str(exc), "duration": time.time() - started}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": "failed", "skill": skill_name, "error": str(exc)}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_FAILED", result)
            self._enqueue_learning(event_type="AUTONOMOUS_STEP", context={"goal": goal or {}, "step": step_data}, action={"skill": skill_name, "action": action_name}, outcome=result, source="idle", importance=0.5)
            return result

    def _execute_standing_instruction(self, step_data: Dict[str, Any], started: float) -> Dict[str, Any]:
        """Fires a due standing instruction (see core/autonomy/
        standing_instructions.py + idle_loop.py's step(), which pushes
        due items here via Scheduler.schedule()->due_tasks(), the fix
        for Scheduler.schedule() previously having no producer at all).
        Speaks via Termux:API TTS when available (core/runtime/voice.py);
        always also emits an event so the web frontend/CLI can show it
        even headless/without TTS. mark_fired() only runs AFTER this
        attempt, so a crash mid-fire correctly retries next idle tick
        instead of being silently marked done."""
        knowledge_id = step_data.get("knowledge_id")
        action_text = str(step_data.get("action_text") or "")
        spoken = False
        try:
            from ..runtime import voice
            if voice.voice_available():
                spoken = bool(voice.speak(action_text))
        except Exception:
            spoken = False
        result = {
            "success": True, "status": "completed", "action": "standing_instruction_fire",
            "result": f"fired: {action_text}", "spoken": spoken, "duration": time.time() - started,
        }
        self.last_brain_decision = {"mode": "native", "source": "idle", "status": "completed", "action": "standing_instruction_fire", "action_result": action_text}
        self.last_action_response = result
        self._emit("STANDING_INSTRUCTION_FIRED", {"knowledge_id": knowledge_id, "action_text": action_text, "spoken": spoken})
        self._emit("ACTION_RESPONSE_COMPLETED", result)
        try:
            self.standing_instructions.mark_fired(knowledge_id)
        except Exception:
            pass
        return result

    def _execute_verify_knowledge_step(self, action_name: str, step_data: Dict[str, Any], goal: Optional[Dict[str, Any]], started: float) -> Dict[str, Any]:
        """Native handler for verify_knowledge idle goals: re-check a
        real low-confidence fact against everything else stored about
        the same subject, and nudge its confidence honestly --
        bounded, reversible, and never inventing or deleting the fact
        itself. subject is parsed from the goal's own text because
        GoalManager.add() only persists text/priority/origin (no
        arbitrary metadata field), and that text is produced by
        Curiosity.candidates()'s exact "Knowledge about 'X' has low
        confidence (...)" format -- see core/autonomy/curiosity.py.
        """
        semantic = getattr(self.memory, "semantic", None) if self.memory is not None else None
        goal_text = str((goal or {}).get("text") or "")
        subject_match = re.search(r"Knowledge about '(.+?)' has low confidence", goal_text)
        subject = subject_match.group(1) if subject_match else None

        if semantic is None or not subject or not hasattr(semantic, "find_by_subject"):
            result = {
                "success": False, "status": "no_capability", "action": action_name,
                "result": "semantic memory unavailable or subject unresolved from goal text",
                "duration": time.time() - started,
            }
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": result["status"], "action": action_name}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_FAILED", result)
            return result

        try:
            related = semantic.find_by_subject(subject) or []
        except Exception:
            related = []
        corroborating = [r for r in related if isinstance(getattr(r, "confidence", None), (int, float)) and getattr(r, "confidence") >= 0.6]

        if action_name == "search_supporting_evidence":
            outcome_text = f"subject='{subject}': {len(related)} related fact(s) on file, {len(corroborating)} already at confidence>=0.6"
            result = {
                "success": True, "status": "completed", "action": action_name, "result": outcome_text,
                "related_count": len(related), "corroborating_count": len(corroborating), "duration": time.time() - started,
            }
        else:  # update_confidence
            adjusted = 0
            for item in related:
                kid = getattr(item, "knowledge_id", None)
                confidence = getattr(item, "confidence", None)
                if not kid or not isinstance(confidence, (int, float)) or confidence >= 0.6:
                    continue
                try:
                    if corroborating:
                        semantic.reinforce(kid, confidence_delta=0.05)
                    else:
                        semantic.weaken(kid, confidence_delta=0.02)
                    adjusted += 1
                except Exception:
                    continue
            direction = "reinforced (corroborated by other facts on the same subject)" if corroborating else "weakened further (still unconfirmed after this check)"
            outcome_text = f"subject='{subject}': {adjusted} low-confidence fact(s) {direction}"
            result = {
                "success": True, "status": "completed", "action": action_name, "result": outcome_text,
                "adjusted_count": adjusted, "duration": time.time() - started,
            }

        self.last_brain_decision = {"mode": "native", "source": "idle", "status": "completed", "action": action_name, "action_result": result["result"]}
        self.last_action_response = result
        self._emit("ACTION_RESPONSE_COMPLETED", result)
        self._enqueue_learning(
            event_type="AUTONOMOUS_STEP", context={"goal": goal or {}, "step": step_data},
            action={"action": action_name, "subject": subject}, outcome=result, source="idle", importance=0.4,
        )
        return result

    def _perceive(self, user_input: str) -> Dict[str, Any]:
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        result = self.perception.perceive(user_input, context=context)
        payload = result.as_dict()
        self.last_perception = payload
        self._emit("PERCEPTION_COMPLETED", {"user_input": user_input, "perception": payload})
        return payload

    def _route_cognition(self, user_input: str, perception: Dict[str, Any]) -> Dict[str, Any]:
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]
        decision = self.cognitive_router.decide(user_input=user_input, context=context, skills=getattr(self.skill_registry, "skills", None), identity=None, goals=goals, perception=perception)
        payload = decision.as_dict()
        self.last_cognitive_decision = payload
        if self.state is not None:
            try:
                self.state.update(last_route=decision.mode, confidence=decision.confidence, uncertainty=1.0 - decision.confidence)
            except Exception:
                pass
        self._emit("COGNITION_ROUTED", {"user_input": user_input, "decision": payload})
        return payload

    def _register_and_plan_goal(self, perceived_goal: Any) -> Dict[str, Any]:
        """Persist a user goal and plan it; execution remains Brain/idle-owned."""
        if self.goal_manager is None:
            return {"status": "goal_manager_unavailable", "goal": perceived_goal}
        if isinstance(perceived_goal, dict):
            text = str(perceived_goal.get("text") or perceived_goal.get("description") or "").strip()
            priority = float(perceived_goal.get("priority", 0.7) or 0.7)
        else:
            text = str(perceived_goal or "").strip()
            priority = 0.7
        if not text:
            return {"status": "invalid_goal", "goal": perceived_goal}
        existing = next((g for g in self.goal_manager.pending() if str(g.get("text", "")).strip().lower() == text.lower()), None)
        goal = existing or self.goal_manager.add(text=text, priority=priority, origin="user")
        self.goal_manager.update_status(goal["id"], "active")
        planner = getattr(self, "planner", None)
        plan = goal.get("plan") or []
        if not plan and planner is not None:
            plan = planner.plan(goal)
            self.goal_manager.set_plan(goal["id"], plan)
            goal = self.goal_manager._find(goal["id"]) or goal
        return {"status": "planned", "goal": goal, "plan": plan}

    def _hybrid_synthesize(self, user_input: str, skill_name: str, native_result: Any, source: str) -> str:
        if self.llm is None:
            return str(native_result)

        system_prompt = "You are JARVIS's response synthesizer. A native organism skill has already executed successfully. Do not invent actions or claim to execute anything. Return a concise user-facing response based only on the native result."
        synthesis_input = f"User request: {user_input}\nNative skill: {skill_name}\nNative result: {native_result}"
        try:
            generate = getattr(self.llm, "generate", None)
            if callable(generate):
                return str(generate(system_prompt, synthesis_input)).strip()
            generate_response = getattr(self.llm, "generate_response", None)
            if callable(generate_response):
                return str(generate_response(system_prompt=system_prompt, user_input=synthesis_input, level="response_generation")).strip()
        except Exception as exc:
            self.last_brain_decision = {"mode": "hybrid", "status": "native_success_llm_synthesis_failed", "error": str(exc)}
        return str(native_result)

    def attach_skill_registry(self, skill_registry: Any) -> None:
        """Attach or replace the skill registry and its executor."""
        self.skill_registry = skill_registry
        self.skill_executor = (
            SkillExecutor(skill_registry)
            if skill_registry is not None
            else None
        )

    def attach_skill_executor(self, skill_executor: Any) -> None:
        self.skill_executor = skill_executor

    def _record_action_response(self, *, mode: str, status: str, response: Any, action: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> str:
        response_text = str(response)
        record: Dict[str, Any] = {"mode": mode, "status": status, "response": response_text}
        if action is not None:
            record["action"] = action
        if error is not None:
            record["error"] = error
        self.last_action_response = record
        self._emit("ACTION_RESPONSE_COMPLETED", record)

        # Clean, readable chat transcript (separate from the internal
        # debug log) -- every turn passes through this single
        # chokepoint regardless of route (goal/native/hybrid/llm), so
        # this is the correct place to log it once, consistently.
        try:
            log_chat_turn(self._last_user_input, response_text)
        except Exception:
            pass

        try:
            self.dependency_metrics.record_turn(
                mode=mode, status=status,
                answered_by=(action or {}).get("answered_by") if isinstance(action, dict) else None,
            )
        except Exception:
            pass

        # Evolution-of-LLM-fallbacks detection (blueprint section 48):
        # only meaningful for turns that genuinely reached the LLM
        # (mode == "llm" and not one of the native fast paths above --
        # those already answered_by something and are excluded by the
        # "not action" check, since native fast paths pass action=None
        # or a dict without this specific shape).
        answered_by = (action or {}).get("answered_by") if isinstance(action, dict) else None
        if mode == "llm" and answered_by not in ("native_direct_recall", "identity", "graph_multi_hop", "slm_assisted_recall"):
            try:
                from .response_brief import detect_recall_miss
                pattern_key = detect_recall_miss(self._last_user_input, {})
                if pattern_key:
                    self.fallback_pattern_detector.record(
                        pattern_key=pattern_key, success=(status == "completed"), user_input=self._last_user_input,
                    )
                    self._check_fallback_promotion_candidates()
            except Exception:
                pass

        # ---------------------------------------------------------------
        # BACKGROUND LEARNING HAND-OFF (post-response context ingestion)
        # ---------------------------------------------------------------
        # This is the single chokepoint every conversational route (goal,
        # native, hybrid, llm) passes through on its way to returning a
        # reply, so it is the correct place to trigger background
        # learning -- previously _enqueue_learning() was only ever
        # called from the autonomous idle loop, so a normal chat turn
        # never fed the learning pipeline at all. mode == "error" is
        # excluded: a perception/routing crash has no structured
        # context worth persisting into semantic memory.
        if mode != "error":
            try:
                perception = self.last_perception or {}
                self._enqueue_learning(
                    event_type="USER_CHAT",
                    context={
                        "user_input": self._last_user_input,
                        "perception": perception,
                        # KnowledgeBuilder reads context["semantic"]["relations"]
                        # to turn ordinary chat turns ("remember X") into durable
                        # knowledge-graph facts -- keep this key even for the
                        # base Brain, where perception won't carry a semantic
                        # understanding block yet (it will just be {}).
                        "semantic": perception.get("semantic_understanding") or {},
                        "cognition": getattr(self, "last_cognition_input", None) or {},
                    },
                    action=action or {"mode": mode},
                    outcome={"response": response_text, "status": status, "error": error},
                    source="chat",
                    importance=0.6 if status in ("completed", "planned") else 0.3,
                )
            except Exception as exc:
                # Learning hand-off must never break the response that
                # has already been produced for the user.
                log_event("brain", f"background learning hand-off failed: {exc}", level="warning")

            # -----------------------------------------------------------
            # PERSISTENT TRACE LOG (UK's #4)
            # -----------------------------------------------------------
            # _enqueue_learning above feeds semantic-fact extraction, but
            # its context dict is scoped to what KnowledgeBuilder needs --
            # it does NOT carry the grounding-check verdict, LLM budget
            # spend, or the raw response text long-term (episodic memory
            # keeps its own copy, but self.last_turn_trace above gets
            # overwritten every single turn). This is the durable, full-
            # fidelity record: one JSON line per turn, forever (subject to
            # retention), that #5's native-response-learning miner and any
            # future introspection command both read from.
            try:
                from ..runtime.trace_log import get_trace_log

                decision = self.last_brain_decision or {}
                budget = self.llm.budget_status() if getattr(self, "llm", None) is not None and hasattr(self.llm, "budget_status") else {}
                get_trace_log().write({
                    "timestamp": time.time(),
                    "user_input": self._last_user_input,
                    "response": response_text,
                    "mode": mode,
                    "status": status,
                    "error": error,
                    "perception": perception,
                    "brain_decision": decision,
                    "stayed_within_brief": decision.get("stayed_within_brief"),
                    "flagged_unsupported": decision.get("flagged_unsupported"),
                    "llm_budget": budget,
                })
            except Exception as exc:
                log_event("brain", f"trace log write failed: {exc}", level="warning")

        return response_text

    _retry_value_evolution_proposed = False

    def _check_retry_value_evolution(self) -> None:
        """The other half of "JARVIS ko apne LLM-call kharche ki value
        khud pata honi chahiye": not just measuring retry_value_rate
        (DependencyMetrics), but actually ACTING on it when the number
        is bad enough, via the same governed evolution-proposal
        mechanism as _check_fallback_promotion_candidates below --
        never auto-applied, always requires separate approval (Rule 19).

        Deliberately conservative thresholds: at least 5 retries spent
        before drawing any conclusion (one or two bad retries prove
        nothing), and a paid-off rate below 30% before proposing
        anything -- retries that pay off even half the time are still
        worth their cost given how cheap the alternative (silently
        losing the data) is.
        """
        if self.evolution is None or self._retry_value_evolution_proposed:
            return
        used = self.dependency_metrics.llm_retry_used_count
        rate = self.dependency_metrics.retry_value_rate()
        if used < 5 or rate is None or rate >= 0.3:
            return
        try:
            self.propose_evolution(
                evaluation={
                    "score": rate,
                    "errors": [],
                    "evolution_target": "llm_retry_policy",
                    "evolution_reason": (
                        f"LLM reinforced-retry stages (perception's and/or semantic "
                        f"understanding's) have been spent {used} times and only paid "
                        f"off {rate*100:.0f}% of the time. Candidate: reconsider whether "
                        f"the retry is worth its extra API call for this deployment/model, "
                        f"or investigate why retries are failing so often (e.g. a model "
                        f"that consistently can't follow the reinforced JSON instruction)."
                    ),
                },
                target="llm_retry_policy",
                reason=f"Retry value rate {rate:.2f} across {used} spent retries is below the 0.3 worth-keeping threshold",
            )
            self._retry_value_evolution_proposed = True
            log_event("brain", f"proposed evolution: low retry value rate ({rate:.2f} across {used} retries)", level="info")
        except Exception as exc:
            log_event("brain", f"could not propose retry-value evolution: {exc}", level="warning")

    def _check_fallback_promotion_candidates(self) -> None:
        """Promote a recall-miss pattern into a governed evolution
        proposal once it's crossed the reliability threshold. This
        NEVER writes code or a resolver directly -- propose_evolution()
        creates an inspectable PROPOSED record via the existing
        ControlledEvolutionEngine; approval/apply remain a separate,
        explicit governed step (Rule 19), completely untouched here."""
        if self.evolution is None:
            return
        for candidate in self.fallback_pattern_detector.promotion_candidates():
            pattern_key = candidate["pattern_key"]
            try:
                self.propose_evolution(
                    evaluation={
                        "score": candidate["success_rate"],
                        "errors": [],
                        "evolution_target": "memory_retrieval",
                        "evolution_reason": (
                            f"Recall coverage gap: '{pattern_key}' was asked "
                            f"{candidate['occurrences']} times (all via LLM fallback, "
                            f"{candidate['success_rate']*100:.0f}% successful). The question "
                            f"shape matched native recall exactly but the predicate word "
                            f"wasn't in the recognized map -- candidate: add '{pattern_key}' "
                            f"as a recognized predicate alias in "
                            f"core/orchestration/response_brief.py's _ASK_WORD_TO_PREDICATE."
                        ),
                    },
                    target="memory_retrieval",
                    reason=f"Repeated LLM fallback for a native-recall-shaped question: '{pattern_key}'",
                )
                self.fallback_pattern_detector.mark_proposed(pattern_key)
                log_event("brain", f"proposed evolution for recall coverage gap: {pattern_key}", level="info")
            except Exception as exc:
                log_event("brain", f"could not propose evolution for '{pattern_key}': {exc}", level="warning")

    def _trace(self, user_input: str, response: str, route: Dict[str, Any], perception: Dict[str, Any], started: float, llm: bool) -> None:
        self.last_turn_trace = {"source": "brain", "query": user_input, "response_preview": response[:200], "perception": perception, "cognitive_route": route, "brain_decision": self.last_brain_decision, "action_response": self.last_action_response, "llm_available": llm, "pipeline_success": True, "timings": {"total": time.time() - started}}
        self._emit("BRAIN_CYCLE_COMPLETED", {"trace": self.last_turn_trace})

    # Retrieval-based context bound for the LLM fallback route (blueprint
    # Phase 4: never dump full memory/knowledge/graph state into an LLM
    # prompt). Caps item count and per-item length *before* the string
    # ever reaches CognitiveBudgeter, so the hard 4096-token guard is a
    # backstop rather than the only thing standing between this and an
    # unbounded prompt.
    _CONTEXT_MAX_ITEMS = 5
    _CONTEXT_MAX_ITEM_CHARS = 200

    @classmethod
    def _bounded_context_items(cls, items: Any) -> list:
        if not items:
            return []
        try:
            sequence = list(items)
        except TypeError:
            return []
        bounded = []
        for item in sequence[: cls._CONTEXT_MAX_ITEMS]:
            text = str(item)
            if len(text) > cls._CONTEXT_MAX_ITEM_CHARS:
                text = text[: cls._CONTEXT_MAX_ITEM_CHARS] + "…"
            bounded.append(text)
        return bounded

    @classmethod
    def _bounded_context_block(cls, context: Dict[str, Any]) -> str:
        # Epistemic-boundary fix: the old labels ("RETRIEVED MEMORIES" /
        # "SEMANTIC KNOWLEDGE") gave a raw chat-log excerpt and an actual
        # confirmed database fact equal rhetorical weight. A weak model
        # reading both sections back-to-back has no signal telling it
        # "only the second one is something you're allowed to claim you
        # remember" -- so it answers factual questions straight out of
        # the conversation transcript even when KnowledgeBuilder never
        # actually stored that fact (visible in production as: JARVIS
        # answers correctly, but /memory_inspect shows nothing saved).
        # Relabeling alone doesn't fix extraction, but it stops the model
        # from *asserting* unsaved chat history as saved, confirmed fact.
        experiences = cls._bounded_context_items(context.get("recent_experiences"))
        knowledge = cls._bounded_context_items(context.get("relevant_knowledge"))
        graph = cls._bounded_context_items(context.get("graph_relations"))
        return (
            f"=== PAST CONVERSATION EXCERPTS (context only -- NOT confirmed saved facts, max {cls._CONTEXT_MAX_ITEMS}) ===\\n"
            f"{experiences}\\n\\n"
            f"=== CONFIRMED KNOWLEDGE (verified facts actually saved in JARVIS's permanent store, max {cls._CONTEXT_MAX_ITEMS}) ===\\n"
            f"{knowledge}\\n\\n"
            f"=== KNOWLEDGE GRAPH EDGES (verified relations, max {cls._CONTEXT_MAX_ITEMS}) ===\\n"
            f"{graph}\\n\\n"
            f"=== MEMORY RULE (STRICT) ===\\n"
            f"Only treat something as a fact you 'remember' or have 'saved' if it "
            f"appears in CONFIRMED KNOWLEDGE or KNOWLEDGE GRAPH EDGES above. If a "
            f"detail only appears in PAST CONVERSATION EXCERPTS, you may refer to it "
            f"conversationally, but you must NOT claim it is remembered/saved -- say "
            f"it hasn't been confirmed/stored yet if the user asks directly."
        )

    def _fallback(self, user_input: str) -> str:
        lower = (user_input or "").strip().lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        return "JARVIS received the input, but no language cognition provider is currently available. Core organism remains active."

    def _emit(self, event_name: str, payload: Any = None) -> None:
        if self.events is None:
            return
        safe_emit = getattr(self.events, "safe_emit", None)
        if callable(safe_emit):
            safe_emit(event_name, payload, source="brain")
