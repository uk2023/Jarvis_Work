from __future__ import annotations

from typing import Optional

from .jarvis_core import JarvisCore
from .internal_state import InternalState
from .event_bus import EventBus
from .heartbeat import Heartbeat
from .lifecycle import Lifecycle
from core.orchestration.brain import Brain
from core.orchestration.llm_bridge import HybridLLMBridge
from core.orchestration.cognitive_router import CognitiveRouter
from core.orchestration.perception import PerceptionEngine
from ..memory.memory_manager import MemoryManager
from ..memory.memory_consolidator import MemoryConsolidator
from ..learning.experience_engine import ExperienceEngine
from ..learning.self_evaluator import SelfEvaluator
from ..learning.knowledge_builder import KnowledgeBuilder
from ..learning.learning_coordinator import LearningCoordinator
from ..learning.controlled_evolution import ControlledEvolutionEngine
from ..learning.runtime_evolution_adapter import RuntimeEvolutionAdapter
from ..autonomy.curiosity import Curiosity
from ..autonomy.goal_manager import GoalManager
from ..autonomy.planner import Planner
from ..autonomy.scheduler import Scheduler
from ..autonomy.idle_loop import IdleLoop
from ..skills.skill_registry import SkillRegistry
from ..skills.skill_executor import SkillExecutor
from ..skills.skill_learner import SkillLearner


def create_jarvis(identity=None, personality=None, values=None,
                  heartbeat_interval: float = 5.0,
                  idle_threshold: float = 30.0) -> JarvisCore:
    state = InternalState()
    events = EventBus(internal_state=state)
    heartbeat = Heartbeat(event_bus=events, internal_state=state,
                          interval=heartbeat_interval, idle_threshold=idle_threshold)
    memory = MemoryManager(event_bus=events)
    experience_engine = ExperienceEngine(memory_manager=memory, event_bus=events, internal_state=state)
    evaluator = SelfEvaluator(memory_manager=memory, event_bus=events, internal_state=state)
    knowledge_builder = KnowledgeBuilder(event_bus=events, internal_state=state, memory_manager=memory)
    consolidator = MemoryConsolidator(memory_manager=memory, event_bus=events)
    skill_learner = SkillLearner()
    skill_registry = SkillRegistry()
    learning = LearningCoordinator(
        evaluator=evaluator,
        knowledge_builder=knowledge_builder,
        consolidator=consolidator,
        memory_manager=memory,
        event_bus=events,
        internal_state=state,
        skill_learner=skill_learner,
        skill_registry=skill_registry,
    )
    evolution = ControlledEvolutionEngine(
        event_bus=events,
        internal_state=state,
        memory_manager=memory,
    )

    # Phase 4-6: one narrow, allowlisted runtime adapter.
    # It can only materialize validated/approved runtime profile changes;
    # it cannot edit source code or import executable proposal content.
    runtime_evolution_adapter = RuntimeEvolutionAdapter(
        event_bus=events,
        memory_manager=memory,
    )
    evolution.register_adapter(
        RuntimeEvolutionAdapter.TARGET,
        runtime_evolution_adapter,
    )

    goal_manager = GoalManager(store=memory.store)
    curiosity = Curiosity()
    scheduler = Scheduler()
    llm_bridge = HybridLLMBridge()
    planner = Planner(llm_bridge=llm_bridge)
    skill_executor = SkillExecutor(skill_registry)
    cognitive_router = CognitiveRouter()
    perception = PerceptionEngine(state=state)
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
        cognitive_router=cognitive_router,
        perception_engine=perception,
        skill_registry=skill_registry,
        skill_executor=skill_executor,
        llm_bridge=llm_bridge,
    )
    idle_loop = IdleLoop(
        goal_manager=goal_manager,
        curiosity=curiosity,
        planner=planner,
        scheduler=scheduler,
        state=state,
        event_bus=events,
        store=memory.store,
        executor=brain.execute_autonomous_step,
    )

    def _on_heartbeat(event) -> None:
        payload = getattr(event, "payload", {}) or {}
        if payload.get("idle"):
            idle_loop.step()

    events.subscribe("HEARTBEAT", _on_heartbeat)

    organs = {
        "memory": memory, "experience": experience_engine, "evaluator": evaluator,
        "knowledge_builder": knowledge_builder, "consolidator": consolidator,
        "learning": learning, "evolution": evolution, "curiosity": curiosity,
        "goal_manager": goal_manager, "planner": planner, "scheduler": scheduler,
        "idle_loop": idle_loop,
        "skill_registry": skill_registry, "skill_executor": skill_executor,
        "skill_learner": skill_learner, "perception": perception,
        "cognitive_router": cognitive_router, "brain": brain,
        "llm_bridge": llm_bridge,
        "runtime_evolution_adapter": runtime_evolution_adapter,
    }
    jarvis = JarvisCore(identity=identity, personality=personality, values=values,
                        state=state, event_bus=events, heartbeat=heartbeat, organs=organs)
    jarvis.idle_loop = idle_loop
    return jarvis


def start_jarvis(identity=None, personality=None, values=None,
                 heartbeat_interval: float = 5.0,
                 idle_threshold: float = 30.0) -> JarvisCore:
    jarvis = create_jarvis(identity=identity, personality=personality, values=values,
                           heartbeat_interval=heartbeat_interval, idle_threshold=idle_threshold)
    lifecycle = Lifecycle(jarvis, internal_state=jarvis.state,
                          event_bus=jarvis.event_bus, heartbeat=jarvis.heartbeat)
    jarvis.lifecycle = lifecycle
    lifecycle.start()
    jarvis.start()
    return jarvis


def stop_jarvis(jarvis: Optional[JarvisCore]) -> None:
    if jarvis is None:
        return
    try:
        lifecycle = getattr(jarvis, "lifecycle", None)
        if lifecycle is None:
            lifecycle = Lifecycle(jarvis, internal_state=jarvis.state,
                                  event_bus=jarvis.event_bus, heartbeat=jarvis.heartbeat)
        lifecycle.stop()
    except Exception:
        try:
            if hasattr(jarvis, "heartbeat") and jarvis.heartbeat is not None:
                jarvis.heartbeat.stop()
        except Exception:
            pass
        try:
            if hasattr(jarvis, "stop"):
                jarvis.stop()
        except Exception:
            pass
