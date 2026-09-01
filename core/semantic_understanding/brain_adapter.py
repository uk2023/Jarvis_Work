from __future__ import annotations

from types import MethodType
from typing import Any, Dict, Optional

from .engine import SemanticUnderstandingEngine


class SemanticBrainAdapter:
    """Attach semantic understanding to the existing Brain without rewriting it.

    This is intentionally an integration seam. The locked Brain lifecycle stays
    intact; semantic parsing enriches retrieval and supplies fact candidates to
    the existing Experience -> LearningCoordinator -> KnowledgeBuilder path.
    """

    VERSION = "0.1.0"

    def __init__(self, engine: Optional[SemanticUnderstandingEngine] = None):
        self.engine = engine or SemanticUnderstandingEngine()

    def attach(self, brain: Any) -> Any:
        if getattr(brain, "_semantic_understanding_attached", False):
            return brain

        brain.semantic_understanding = self
        self._wrap_build_context(brain)
        self._wrap_think_and_respond(brain)
        brain._semantic_understanding_attached = True
        return brain

    def _wrap_build_context(self, brain: Any) -> None:
        original = brain.build_context
        engine = self.engine

        def build_context_with_semantics(this, query=None, subject=None, recent_limit=5, knowledge_limit=10):
            context = original(query=query, subject=subject, recent_limit=recent_limit, knowledge_limit=knowledge_limit)
            semantic = engine.understand(query or "", context=context)
            context["semantic_understanding"] = semantic
            candidates = semantic.get("fact_candidates") or []
            if candidates:
                existing = list(context.get("relevant_knowledge") or [])
                existing.append({"semantic_fact_candidates": candidates})
                context["relevant_knowledge"] = existing
            return context

        brain.build_context = MethodType(build_context_with_semantics, brain)

    def _wrap_think_and_respond(self, brain: Any) -> None:
        original = brain.think_and_respond
        engine = self.engine

        def think_with_semantics(this, user_input, identity_profile=None, source="cli"):
            response = original(user_input, identity_profile=identity_profile, source=source)
            semantic = engine.understand(user_input)

            outcome: Dict[str, Any] = {
                "value": response,
                "semantic_understanding": semantic,
            }
            candidates = semantic.get("fact_candidates") or []
            if candidates:
                strongest = max(candidates, key=lambda item: float(item.get("confidence", 0.0)))
                outcome.update({
                    "subject": strongest["subject"],
                    "predicate": strongest["predicate"],
                    "value": strongest["value"],
                    "semantic_fact_candidates": candidates,
                })

            try:
                brain._enqueue_learning(
                    event_type="USER_CHAT",
                    context={
                        "user_input": str(user_input or ""),
                        "semantic_understanding": semantic,
                    },
                    action={"jarvis_response": response},
                    outcome=outcome,
                    source=source,
                    importance=0.6 if candidates else 0.2,
                )
            except Exception as exc:
                print(f"[SemanticUnderstanding] learning handoff warning: {exc}")

            return response

        brain.think_and_respond = MethodType(think_with_semantics, brain)
