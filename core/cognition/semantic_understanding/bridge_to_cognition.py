"""Bridge semantic understanding into Cognition without bypassing Brain/Router."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .context_model import ContextModel
from .entity_store import EntityStore
from .engine import SemanticUnderstandingEngine
from .learning_boundary import SemanticLearningBoundary
from .relation_store import RelationStore
from .semantic_retriever import SemanticRetriever


class SemanticUnderstanding:
    """Neuro-symbolic understanding facade at the Cognition boundary."""

    VERSION = "0.3.0"

    def __init__(self, *, parser: Optional[SemanticUnderstandingEngine] = None,
                 entity_store: Optional[EntityStore] = None,
                 relation_store: Optional[RelationStore] = None,
                 context_model: Optional[ContextModel] = None,
                 retriever: Optional[SemanticRetriever] = None,
                 semantic_memory: Optional[Any] = None,
                 learning_boundary: Optional[SemanticLearningBoundary] = None) -> None:
        self.parser = parser or SemanticUnderstandingEngine()
        self.entity_store = entity_store or EntityStore()
        self.relation_store = relation_store or RelationStore()
        self.context_model = context_model or ContextModel()
        self.retriever = retriever or SemanticRetriever(semantic_memory=semantic_memory)
        self.learning_boundary = learning_boundary or SemanticLearningBoundary()

    def understand(self, text: str, *, language: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None,
                   retrieve: bool = True, retrieval_limit: int = 8) -> Dict[str, Any]:
        native_semantic = self.parser.understand(text, context=context)
        resolution = self.learning_boundary.resolve(text, native_semantic, context=context)
        semantic = dict(resolution.get("semantic") or native_semantic)
        provenance = semantic.get("provenance") if isinstance(semantic.get("provenance"), dict) else {}
        semantic["provenance"] = {**provenance, "semantic_source": resolution.get("source", "native")}

        entities = []
        for entity in semantic.get("entities", []):
            if not isinstance(entity, dict) or not entity.get("text"):
                continue
            stored = self.entity_store.upsert(entity["text"], entity.get("type", "unknown"))
            enriched = dict(entity)
            enriched["entity_id"] = stored.entity_id
            entities.append(enriched)
        semantic["entities"] = entities
        context_state = self.context_model.update(semantic)
        evidence = (
            self.retriever.retrieve(semantic.get("normalized", text), limit=retrieval_limit)
            if retrieve else {"exact": [], "vector": [], "graph": []}
        )
        return {
            "version": self.VERSION,
            "semantic": semantic,
            "normalized": semantic.get("normalized", text),
            "entities": entities,
            "relations": list(semantic.get("relations") or []),
            "context": context_state,
            "evidence": evidence,
            "learning": {
                "source": resolution.get("source", "native"),
                "fallback_used": bool(resolution.get("fallback_used", False)),
                "candidate": resolution.get("candidate"),
            },
        }

    def learn_semantic_candidate(self, candidate_id: str, *, auto_accept: bool = False) -> Dict[str, Any]:
        return self.learning_boundary.learn(candidate_id, auto_accept=auto_accept)

    def accept_semantic_candidate(self, candidate_id: str) -> Dict[str, Any]:
        return self.learning_boundary.accept_candidate(candidate_id)

    def reject_semantic_candidate(self, candidate_id: str, reason: str = "") -> Dict[str, Any]:
        return self.learning_boundary.reject_candidate(candidate_id, reason)

    def promote_semantic_candidate(self, candidate_id: str) -> Dict[str, Any]:
        return self.learning_boundary.promote(candidate_id)

    def add_relation(self, subject: str, predicate: str, obj: Any, *,
                     confidence: float = 1.0,
                     provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Keep a transient candidate; trusted persistence belongs to learning."""
        relation = self.relation_store.add(subject, predicate, obj,
                                            confidence=confidence, provenance=provenance)
        return {"subject": relation.subject, "predicate": relation.predicate,
                "object": relation.object, "confidence": relation.confidence,
                "provenance": relation.provenance}
