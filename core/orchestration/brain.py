from __future__ import annotations

import re
import time
from .cognitive_router import CognitiveRouter
from .perception import PerceptionEngine, LLMPerceptionProvider
from ..skills.skill_executor import SkillExecutor
from typing import Any, Dict, Optional

from ..learning.learning_queue import AsyncLearningQueue


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
        self.memory = memory_manager
        self.experience = experience_engine
        self.evaluator = self_evaluator
        self.knowledge_builder = knowledge_builder
        self.consolidator = memory_consolidator
        self.learning = learning_coordinator
        self.evolution = evolution_engine
        self.events = event_bus
        self.state = internal_state
        self.planner = planner
        self.goal_manager = goal_manager
        self.llm = llm_bridge
        self.cognitive_router = cognitive_router or CognitiveRouter()
        self.skill_registry = skill_registry
        self.skill_executor = (
            skill_executor if skill_executor is not None else
            (SkillExecutor(skill_registry) if skill_registry is not None else None)
        )
        self.perception = perception_engine or PerceptionEngine(state=self.state)
        if self.llm is not None:
            self.set_llm_bridge(self.llm)
        self.last_cognitive_decision = None
        self.last_perception = None
        self.last_brain_decision = None
        self.last_action_response = None
        self.auto_accept_knowledge = auto_accept_knowledge
        self.created_at = time.time()
        self.last_cycle_at = None
        self.cycle_count = 0
        self.last_result = None
        self.running = True
        self._learning_queue = AsyncLearningQueue(worker=self._run_learning_job)
        self.last_turn_trace = None
        self.total_turns = 0
        self.total_latency_seconds = 0.0
        self.total_tokens_estimate = 0
        self.typo_map = {
            "chahie": "chahiye", "chahia": "chahiye", "chaiye": "chahiye",
            "krde": "kar de", "krdo": "kar do", "kr": "kar", "krna": "karna",
            "nhi": "nahi", "mje": "mujhe", "mjhe": "mujhe", "mai": "main", "mein": "main",
            "yhi": "yahi", "yha": "yahan", "wha": "wahan", "smjha": "samjha",
            "smjhna": "samajhna", "bta": "bata", "btao": "batao", "thik": "theek", "thk": "theek",
            "acha": "accha", "achha": "accha", "rha": "raha", "rhi": "rahi", "rhe": "rahe",
            "kese": "kaise", "kse": "kaise", "tmhe": "tumhe", "tmhara": "tumhara", "tm": "tum",
            "dedo": "de do"
        }

    def _normalize_hinglish_typos(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"normalized": text, "corrections": []}
        tokens = re.findall(r"\w+|\W+", text)
        corrections, out_tokens = [], []
        for tok in tokens:
            key = tok.lower()
            if key in self.typo_map and self.typo_map[key] != key:
                corrections.append({"raw": tok, "corrected": self.typo_map[key]})
                out_tokens.append(self.typo_map[key])
            else:
                out_tokens.append(tok)
        return {"normalized": "".join(out_tokens), "corrections": corrections}

    def think_and_respond(self, user_input: str, identity_profile: Optional[Dict[str, Any]] = None, source: str = "cli") -> str:
        started = time.time()
        user_input = str(user_input or "").strip()
        self._emit("BRAIN_CYCLE_STARTED", {"source": source, "user_input": user_input})
        try:
            perception = self._perceive(user_input)
            route = self._route_cognition(user_input, perception)
        except Exception as exc:
            self.last_brain_decision = {"mode": "error", "status": "cognition_failed", "error": str(exc)}
            response = f"[Brain Error: {exc}]"
            self._record_action_response(mode="error", status="failed", response=response, error=str(exc))
            self._trace(user_input, response, {"mode": "error"}, {}, started, self.llm is not None)
            return response

        mode = str(route.get("mode", "llm")).lower()
        intent = perception.get("intent") or {}
        skill_name = (intent.get("skill") or intent.get("name")) if isinstance(intent, dict) else None

        if mode == "goal":
            result = self._register_and_plan_goal(perception.get("goal"))
            response = (f"Goal accepted and planned: {result.get('goal', {}).get('text', '')}"
                        if result.get("status") == "planned" else "Goal could not be planned.")
            self.last_brain_decision = {"mode": "goal", "status": result.get("status"), "goal": result.get("goal")}
            self._record_action_response(mode="goal", status=result.get("status", "failed"), response=response)
            self._trace(user_input, response, route, perception, started, self.llm is not None)
            return response

        if mode in {"tool", "native"}:
            if self.skill_executor is None or not skill_name:
                response = self._fallback(user_input)
                self.last_brain_decision = {"mode": "native", "status": "no_capability", "skill": skill_name}
                self._record_action_response(mode="native", status="failed", response=response, error="capability_not_available")
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response
            try:
                native_result = self.skill_executor.execute(skill_name, user_input=user_input)
                response = str(native_result)
                self.last_brain_decision = {"mode": "native", "status": "completed", "skill": skill_name, "action_result": response}
                self._record_action_response(mode="native", status="completed", response=response, action={"skill": skill_name})
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response
            except Exception as exc:
                response = f"[Brain Action Error: {exc}]"
                self.last_brain_decision = {"mode": "native", "status": "failed", "skill": skill_name, "error": str(exc)}
                self._record_action_response(mode="native", status="failed", response=response, error=str(exc))
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response

        if mode == "hybrid":
            if self.skill_executor is None or not skill_name:
                response = self._fallback(user_input)
                self.last_brain_decision = {"mode": "hybrid", "status": "no_native_capability", "skill": skill_name}
                self._record_action_response(mode="hybrid", status="failed", response=response, error="capability_not_available")
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response
            try:
                native_result = self.skill_executor.execute(skill_name, user_input=user_input)
                response = self._hybrid_synthesize(user_input, skill_name, native_result, source)
                self.last_brain_decision = {"mode": "hybrid", "status": "completed", "native_skill": skill_name, "native_result": str(native_result)}
                self._record_action_response(mode="hybrid", status="completed", response=response)
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response
            except Exception as exc:
                response = f"[Brain Hybrid Error: {exc}]"
                self.last_brain_decision = {"mode": "hybrid", "status": "failed", "skill": skill_name, "error": str(exc)}
                self._record_action_response(mode="hybrid", status="failed", response=response, error=str(exc))
                self._trace(user_input, response, route, perception, started, self.llm is not None)
                return response

        if self.llm is None:
            response = self._fallback(user_input)
            self.last_brain_decision = {"mode": mode, "status": "llm_unavailable"}
            self._record_action_response(mode=mode, status="degraded", response=response)
            self._trace(user_input, response, route, perception, started, False)
            return response

        retrieval_query = self._normalize_hinglish_typos(user_input)["normalized"]
        context = self.build_context(query=retrieval_query, recent_limit=3) if self.memory is not None else {}
        bot_name = "JARVIS"
        creator_name = "UK"
        if isinstance(identity_profile, dict):
            bot_name = identity_profile.get("name", bot_name)
            creator_name = identity_profile.get("creator", creator_name)
        system_prompt = (f"SYSTEM IDENTITY INSTRUCTIONS (STRICT):\n1. You are {bot_name}, a self-contained cognitive AI organism running locally.\n"
                         f"2. The user talking to you is {creator_name}, your developer and creator.\n3. NEVER swap roles or claim to be {creator_name}.\n"
                         f"4. Communicate naturally, precisely, and conversationally in Hinglish.\n5. Keep responses loyal, calm, and concise.\n"
                         f"6. Dont use emojis in response.\n7. Behave alike Marvel Iron Man's JARVIS: savage, funny, and useful.\n8. Always loyal to {creator_name}.")
        context_prompt = (f"=== RETRIEVED MEMORIES ===\n{context.get('recent_experiences', [])}\n\n=== SEMANTIC KNOWLEDGE ===\n"
                          f"{context.get('relevant_knowledge', [])}\n\n=== KNOWLEDGE GRAPH EDGES ===\n{context.get('graph_relations', [])}\n\n"
                          f"=== CURRENT USER MESSAGE ===\n{creator_name}: {user_input}\n\n{bot_name}:")
        try:
            generate = getattr(self.llm, "generate", None)
            if callable(generate):
                response = str(generate(system_prompt, context_prompt)).strip()
            else:
                generate_response = getattr(self.llm, "generate_response", None)
                if not callable(generate_response):
                    raise AttributeError("LLM bridge exposes neither generate() nor generate_response().")
                response = str(generate_response(system_prompt=system_prompt, user_input=context_prompt)).strip()
            if not response:
                response = "..."
            self.last_brain_decision = {"mode": "llm", "status": "completed"}
            self._record_action_response(mode="llm", status="completed", response=response)
            self._trace(user_input, response, route, perception, started, True)
            return response
        except Exception as exc:
            response = f"[Brain Thinking Error: {exc}]"
            self.last_brain_decision = {"mode": "llm", "status": "failed", "error": str(exc)}
            self._record_action_response(mode="llm", status="failed", response=response, error=str(exc))
            self._trace(user_input, response, route, perception, started, True)
            return response

    def _enqueue_learning(self, event_type, context, action, outcome, source, importance):
        job = {"event_type": event_type, "context": context, "action": action, "outcome": outcome,
               "source": source, "importance": importance, "build_knowledge": True,
               "auto_accept": self.auto_accept_knowledge}
        if self._learning_queue.is_alive():
            if not self._learning_queue.submit(job):
                self._run_learning_job(job)
        else:
            self._run_learning_job(job)

    def _run_learning_job(self, job: Dict[str, Any]):
        try:
            self.process_experience(event_type=job["event_type"], context=job["context"], action=job["action"], outcome=job["outcome"],
                                    source=job["source"], importance=job["importance"], build_knowledge=job["build_knowledge"], auto_accept=job["auto_accept"])
        except Exception as exc:
            print(f"[Brain Pipeline Warning] Could not process experience: {exc}")

    def process_experience(self, event_type, context=None, action=None, outcome=None, source=None, importance=0.5, build_knowledge=True, auto_accept=None):
        if self.experience is None:
            raise RuntimeError("ExperienceEngine is not connected.")
        if auto_accept is None:
            auto_accept = self.auto_accept_knowledge
        started_at = time.time()
        experience_result = self.experience.process(event_type=event_type, context=context or {}, action=action or {}, outcome=outcome or {}, source=source, importance=importance)
        if not isinstance(experience_result, dict):
            raise RuntimeError("ExperienceEngine returned an invalid result.")
        experience = experience_result.get("experience", {})
        learning_result = None
        if self.learning is not None and build_knowledge:
            learn_method = getattr(self.learning, "learn", None)
            if not callable(learn_method):
                raise RuntimeError("LearningCoordinator does not expose learn().")
            learning_result = learn_method(experience=experience, auto_accept=auto_accept)
        elif self.learning is None and build_knowledge:
            evaluation = self.evaluator.evaluate(experience) if self.evaluator is not None else None
            knowledge = self.knowledge_builder.build(experience=experience, evaluation=evaluation) if self.knowledge_builder is not None and evaluation is not None else None
            accepted = False
            if auto_accept and knowledge is not None and self.knowledge_builder is not None:
                knowledge_id = knowledge.get("id") if isinstance(knowledge, dict) else getattr(knowledge, "id", None)
                accept_method = getattr(self.knowledge_builder, "accept", None)
                if knowledge_id is not None and callable(accept_method):
                    try:
                        accept_method(knowledge_id)
                        accepted = True
                    except Exception as exc:
                        print(f"[Brain Pipeline Warning] Could not auto-accept knowledge: {exc}")
            learning_result = {"success": True, "experience": experience, "evaluation": evaluation, "knowledge": knowledge, "accepted": accepted, "duration": 0.0, "timestamp": time.time()}
        evaluation = learning_result.get("evaluation") if isinstance(learning_result, dict) else None
        knowledge = learning_result.get("knowledge") if isinstance(learning_result, dict) else None
        accepted = bool(learning_result.get("accepted", False)) if isinstance(learning_result, dict) else False
        result = {"type": "BRAIN_EXPERIENCE_CYCLE", "success": True, "experience": experience, "learning": learning_result,
                  "evaluation": evaluation, "knowledge": knowledge, "accepted": accepted,
                  "episode_id": experience_result.get("episode_id"), "duration": time.time() - started_at, "timestamp": time.time()}
        self._finish_cycle(result)
        self._emit("BRAIN_EXPERIENCE_PROCESSED", result)
        return result

    def learn(self, experience, auto_accept=None):
        if not isinstance(experience, dict):
            raise TypeError("experience must be a dictionary.")
        if self.learning is None:
            raise RuntimeError("LearningCoordinator is not connected.")
        if auto_accept is None:
            auto_accept = self.auto_accept_knowledge
        result = self.learning.learn(experience=experience, auto_accept=auto_accept)
        self._emit("BRAIN_LEARNING_COMPLETED", result)
        return result

    def evaluate(self, experience):
        if self.learning is not None:
            method = getattr(self.learning, "evaluate", None)
            if callable(method):
                return method(experience)
        if self.evaluator is None:
            raise RuntimeError("SelfEvaluator is not connected.")
        return self.evaluator.evaluate(experience)

    def build_knowledge(self, experience, evaluation=None):
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

    def accept_knowledge(self, knowledge_id):
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

    def reject_knowledge(self, knowledge_id, reason=""):
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

    def consolidate(self, limit=50):
        if self.consolidator is None:
            raise RuntimeError("MemoryConsolidator is not connected.")
        result = self.consolidator.consolidate(limit=limit)
        self._emit("BRAIN_MEMORY_CONSOLIDATED", result)
        return result

    def learn_and_consolidate(self, experience, auto_accept=None, consolidation_limit=50):
        learning_result = self.learn(experience=experience, auto_accept=auto_accept)
        consolidation_result = self.consolidate(limit=consolidation_limit) if self.consolidator is not None else None
        return {"learning": learning_result, "consolidation": consolidation_result, "timestamp": time.time()}

    def propose_evolution(self, evaluation, target, reason=None):
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        proposal = self.evolution.propose(evaluation=evaluation, target=target, reason=reason)
        self._emit("BRAIN_EVOLUTION_PROPOSED", proposal)
        return proposal

    def validate_evolution(self, proposal_id):
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        return self.evolution.validate(proposal_id)

    def approve_evolution(self, proposal_id):
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        return self.evolution.approve(proposal_id)

    def apply_evolution(self, proposal_id):
        if self.evolution is None:
            raise RuntimeError("EvolutionEngine is not connected.")
        return self.evolution.apply(proposal_id)

    def build_context(self, query=None, subject=None, recent_limit=5, knowledge_limit=10):
        if self.memory is None:
            return {"recent_experiences": [], "relevant_knowledge": [], "graph_relations": []}
        return self.memory.build_context(query=query, subject=subject, recent_limit=recent_limit, knowledge_limit=knowledge_limit)

    def plan(self, goal, context=None):
        if self.planner is None:
            raise RuntimeError("Planner is not connected.")
        method = getattr(self.planner, "plan", None)
        if not callable(method):
            raise RuntimeError("Connected planner does not expose plan().")
        return method(goal=goal, context=context or {})

    def create_goal(self, goal):
        if self.goal_manager is None:
            raise RuntimeError("GoalManager is not connected.")
        method = getattr(self.goal_manager, "create_goal", None)
        if not callable(method):
            raise RuntimeError("Connected GoalManager does not expose create_goal().")
        return method(goal)

    def status(self):
        learning_status = None
        if self.learning is not None and callable(getattr(self.learning, "status", None)):
            try:
                learning_status = self.learning.status()
            except Exception as exc:
                learning_status = {"error": str(exc)}
        consolidator_status = None
        if self.consolidator is not None and callable(getattr(self.consolidator, "status", None)):
            try:
                consolidator_status = self.consolidator.status()
            except Exception as exc:
                consolidator_status = {"error": str(exc)}
        return {"version": self.VERSION, "running": self.running, "created_at": self.created_at, "cycles": self.cycle_count,
                "last_cycle_at": self.last_cycle_at, "auto_accept_knowledge": self.auto_accept_knowledge,
                "total_turns": self.total_turns, "total_latency_seconds": self.total_latency_seconds,
                "avg_latency_ms": round((self.total_latency_seconds / self.total_turns) * 1000, 1) if self.total_turns else 0.0,
                "total_tokens_estimate": self.total_tokens_estimate,
                "organs": {"memory": self.memory is not None, "experience_engine": self.experience is not None,
                            "self_evaluator": self.evaluator is not None, "knowledge_builder": self.knowledge_builder is not None,
                            "memory_consolidator": self.consolidator is not None, "learning_coordinator": self.learning is not None,
                            "evolution_engine": self.evolution is not None, "planner": self.planner is not None,
                            "goal_manager": self.goal_manager is not None, "llm_bridge": self.llm is not None},
                "learning_status": learning_status, "consolidator_status": consolidator_status,
                "async_learning_queue": self._learning_queue.status()}

    def get_last_result(self):
        return self.last_result

    def start(self):
        self.running = True
        self._learning_queue.start()
        if self.learning is not None and callable(getattr(self.learning, "start", None)):
            self.learning.start()

    def stop(self):
        self.running = False
        self._learning_queue.stop(drain=True)
        if self.learning is not None and callable(getattr(self.learning, "stop", None)):
            self.learning.stop()

    def _finish_cycle(self, result):
        self.cycle_count += 1
        self.last_cycle_at = time.time()
        self.last_result = result

    def set_llm_bridge(self, llm_bridge):
        self.llm = llm_bridge
        if not hasattr(self, "perception") or self.perception is None:
            return
        self.perception.providers = [p for p in self.perception.providers if getattr(p, "name", None) != "llm"]
        if llm_bridge is not None:
            self.perception.add_provider(LLMPerceptionProvider(llm_bridge))

    def execute_autonomous_step(self, step, goal=None):
        started = time.time()
        step_data = dict(step or {})
        action_name = step_data.get("action")
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
            self._enqueue_learning("AUTONOMOUS_STEP", {"goal": goal or {}, "step": step_data}, {"skill": skill_name, "action": action_name}, result, "idle", 0.3)
            return result
        try:
            native_result = self.skill_executor.execute(skill_name, user_input=step_data.get("input", action_name))
            result = {"success": True, "status": "completed", "action": action_name, "skill": skill_name, "result": str(native_result), "duration": time.time() - started}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": "completed", "skill": skill_name, "action_result": str(native_result)}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_COMPLETED", result)
            self._enqueue_learning("AUTONOMOUS_STEP", {"goal": goal or {}, "step": step_data}, {"skill": skill_name, "action": action_name, "result": str(native_result)}, result, "idle", 0.5)
            self._emit("BRAIN_CYCLE_COMPLETED", {"source": "idle", "brain_decision": self.last_brain_decision, "action_response": result, "duration": time.time() - started})
            return result
        except Exception as exc:
            result = {"success": False, "status": "failed", "action": action_name, "skill": skill_name, "result": str(exc), "duration": time.time() - started}
            self.last_brain_decision = {"mode": "native", "source": "idle", "status": "failed", "skill": skill_name, "error": str(exc)}
            self.last_action_response = result
            self._emit("ACTION_RESPONSE_FAILED", result)
            self._enqueue_learning("AUTONOMOUS_STEP", {"goal": goal or {}, "step": step_data}, {"skill": skill_name, "action": action_name}, result, "idle", 0.5)
            return result

    def _perceive(self, user_input):
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        result = self.perception.perceive(user_input, context=context)
        payload = result.as_dict()
        self.last_perception = payload
        self._emit("PERCEPTION_COMPLETED", {"user_input": user_input, "perception": payload})
        return payload

    def _route_cognition(self, user_input, perception):
        context = self.build_context(query=user_input, recent_limit=3) if self.memory is not None else {}
        goals = []
        if self.goal_manager is not None:
            current_goal = getattr(self.goal_manager, "current_goal", None)
            if current_goal is not None:
                goals = [current_goal]
        decision = self.cognitive_router.decide(user_input=user_input, context=context,
                                                skills=getattr(self.skill_registry, "skills", None),
                                                identity=None, goals=goals, perception=perception)
        payload = decision.as_dict()
        self.last_cognitive_decision = payload
        if self.state is not None:
            try:
                self.state.update(last_route=decision.mode, confidence=decision.confidence, uncertainty=1.0 - decision.confidence)
            except Exception:
                pass
        self._emit("COGNITION_ROUTED", {"user_input": user_input, "decision": payload})
        return payload

    def _register_and_plan_goal(self, perceived_goal):
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
        plan = goal.get("plan") or []
        if not plan and self.planner is not None:
            plan = self.planner.plan(goal)
            self.goal_manager.set_plan(goal["id"], plan)
            goal = self.goal_manager._find(goal["id"]) or goal
        return {"status": "planned", "goal": goal, "plan": plan}

    def _hybrid_synthesize(self, user_input, skill_name, native_result, source):
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
                return str(generate_response(system_prompt=system_prompt, user_input=synthesis_input)).strip()
        except Exception:
            pass
        return str(native_result)

    def attach_skill_registry(self, skill_registry):
        self.skill_registry = skill_registry
        self.skill_executor = SkillExecutor(skill_registry) if skill_registry is not None else None

    def attach_skill_executor(self, skill_executor):
        self.skill_executor = skill_executor

    def _record_action_response(self, *, mode, status, response, action=None, error=None):
        record = {"mode": mode, "status": status, "response": str(response)}
        if action is not None:
            record["action"] = action
        if error is not None:
            record["error"] = error
        self.last_action_response = record
        self._emit("ACTION_RESPONSE_COMPLETED", record)
        return str(response)

    def _trace(self, user_input, response, route, perception, started, llm):
        self.last_turn_trace = {"source": "brain", "query": user_input, "response_preview": str(response)[:200],
                                "perception": perception, "cognitive_route": route, "brain_decision": self.last_brain_decision,
                                "action_response": self.last_action_response, "llm_available": llm,
                                "pipeline_success": True, "timings": {"total": time.time() - started}}
        self._emit("BRAIN_CYCLE_COMPLETED", {"trace": self.last_turn_trace})

    def _fallback(self, user_input):
        lower = (user_input or "").strip().lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        return "JARVIS received the input, but no language cognition provider is currently available. Core organism remains active."

    def _emit(self, event_name, payload=None):
        if self.events is None:
            return
        safe_emit = getattr(self.events, "safe_emit", None)
        if callable(safe_emit):
            safe_emit(event_name, payload, source="brain")
