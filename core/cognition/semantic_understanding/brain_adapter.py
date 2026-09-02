from __future__ import annotations

from types import MethodType
from typing import Any, Optional

from .bridge_to_cognition import SemanticUnderstanding
from .engine import SemanticUnderstandingEngine


class SemanticBrainAdapter:
    """Attach neuro-symbolic understanding to Brain without changing its lifecycle.

    Brain remains the orchestrator. The adapter enriches its existing memory
    context and leaves routing, action, learning, and evolution boundaries intact.
    """

    VERSION = "0.2.0"

    def __init__(self, engine: Optional[SemanticUnderstandingEngine] = None,
                 semantic: Optional[SemanticUnderstanding] = None):
        self.engine = engine or SemanticUnderstandingEngine()
        self.semantic = semantic

    def attach(self, brain: Any) -> Any:
        if getattr(brain, "_semantic_understanding_attached", False):
            return brain
        if self.semantic is None:
            memory_manager = getattr(brain, "memory", None)
            semantic_memory = getattr(memory_manager, "semantic", None)
            self.semantic = SemanticUnderstanding(semantic_memory=semantic_memory)
        brain.semantic_understanding = self
        self._wrap_build_context(brain)
        brain._semantic_understanding_attached = True
        return brain

    def _wrap_build_context(self, brain: Any) -> None:
        original = brain.build_context
        symbolic_engine = self.engine
        semantic = self.semantic

        def build_context_with_semantics(this, query=None, subject=None,
                                         recent_limit=5, knowledge_limit=10):
            context = original(query=query, subject=subject,
                               recent_limit=recent_limit, knowledge_limit=knowledge_limit)
            text = str(query or "")
            if not text or semantic is None:
                return context

            integrated = semantic.understand(
                text, context=context, retrieve=True, retrieval_limit=knowledge_limit
            )
            legacy = symbolic_engine.understand(text, context=context)
            candidates = legacy.get("fact_candidates") or []
            integrated["fact_candidates"] = candidates
            integrated["legacy_semantic"] = legacy
            context["semantic_understanding"] = integrated

            if candidates:
                existing = list(context.get("relevant_knowledge") or [])
                existing.append({"semantic_fact_candidates": candidates})
                context["relevant_knowledge"] = existing

            evidence = integrated.get("evidence") or {}
            if evidence.get("graph"):
                existing_graph = list(context.get("graph_relations") or [])
                seen = {repr(item) for item in existing_graph}
                for relation in evidence["graph"]:
                    if repr(relation) not in seen:
                        existing_graph.append(relation)
                        seen.add(repr(relation))
                context["graph_relations"] = existing_graph
            return context

        brain.build_context = MethodType(build_context_with_semantics, brain)
