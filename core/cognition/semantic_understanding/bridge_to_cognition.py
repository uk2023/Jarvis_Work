"""Bridge Semantic Understanding into Cognition without bypassing the Router."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .context_model import ContextModel
from .entity_store import EntityStore
from .parser import SemanticParser
from .relation_store import RelationStore
from .semantic_retriever import SemanticRetriever


class SemanticUnderstanding:
    """Unified semantic substrate exposed to the Cognition layer.

    This component understands and structures input; it does not execute
    actions, make final decisions, write trusted knowledge, or activate skills.
    """

    VERSION = "0.1.0"

    def __init__(self, *, parser: Optional[SemanticParser] = None,
                 entity_store: Optional[EntityStore] = None,
                 relation_store: Optional[RelationStore] = None,
                 context_model: Optional[ContextModel] = None,
                 retriever: Optional[SemanticRetriever] = None) -> None:
        self.parser = parser or SemanticParser()
        self.entity_store = entity_store or EntityStore()
        self.relation_store = relation_store or RelationStore()
        self.context_model = context_model or ContextModel()
        self.retriever = retriever or SemanticRetriever()

    def understand(self, text: str, *, language: Optional[str] = None,
                   retrieve: bool = True, retrieval_limit: int = 8) -> Dict[str, Any]:
        semantic = self.parser.parse(text, language=language)
        for entity in semantic.get("entities", []):
            stored = self.entity_store.upsert(entity["text"], entity.get("type", "unknown"))
            entity["entity_id"] = stored.entity_id
        context = self.context_model.update(semantic)
        evidence = self.retriever.retrieve(semantic.get("normalized", text), limit=retrieval_limit) if retrieve else {"exact": [], "vector": [], "graph": []}
        return {
            "semantic": semantic,
            "entities": semantic.get("entities", []),
            "context": context,
            "evidence": evidence,
            "relations": [],
        }

    def add_relation(self, subject: str, predicate: str, obj: Any, *, confidence: float = 1.0, provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        relation = self.relation_store.add(subject, predicate, obj, confidence=confidence, provenance=provenance)
        return {"subject": relation.subject, "predicate": relation.predicate, "object": relation.object, "confidence": relation.confidence, "provenance": relation.provenance}
