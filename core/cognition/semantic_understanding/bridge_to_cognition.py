"""Bridge semantic understanding into Cognition without bypassing Brain/Router."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .context_model import ContextModel
from .entity_store import EntityStore
from .engine import SemanticUnderstandingEngine
from .relation_store import RelationStore
from .semantic_retriever import SemanticRetriever


class SemanticUnderstanding:
    """Neuro-symbolic understanding facade at the Cognition boundary.

    Persistent facts, FAISS vectors, and the NetworkX graph remain owned by
    SemanticMemory. This class only parses, contextualizes, resolves transient
    entities, and returns retrieval evidence.
    """

    VERSION = "0.2.0"

    def __init__(self, *, parser: Optional[SemanticUnderstandingEngine] = None,
                 entity_store: Optional[EntityStore] = None,
                 relation_store: Optional[RelationStore] = None,
                 context_model: Optional[ContextModel] = None,
                 retriever: Optional[SemanticRetriever] = None,
                 semantic_memory: Optional[Any] = None) -> None:
        self.parser = parser or SemanticUnderstandingEngine()
        self.entity_store = entity_store or EntityStore()
        self.relation_store = relation_store or RelationStore()
        self.context_model = context_model or ContextModel()
        self.retriever = retriever or SemanticRetriever(semantic_memory=semantic_memory)

    def understand(self, text: str, *, language: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None,
                   retrieve: bool = True, retrieval_limit: int = 8) -> Dict[str, Any]:
        semantic = self.parser.understand(text, context=context)
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
        relations = list(semantic.get("relations") or [])
        return {
            "version": self.VERSION,
            "semantic": semantic,
            "normalized": semantic.get("normalized", text),
            "entities": entities,
            "relations": relations,
            "context": context_state,
            "evidence": evidence,
        }

    def add_relation(self, subject: str, predicate: str, obj: Any, *,
                     confidence: float = 1.0,
                     provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Keep a transient candidate; trusted persistence belongs to learning."""
        relation = self.relation_store.add(subject, predicate, obj,
                                            confidence=confidence, provenance=provenance)
        return {"subject": relation.subject, "predicate": relation.predicate,
                "object": relation.object, "confidence": relation.confidence,
                "provenance": relation.provenance}
