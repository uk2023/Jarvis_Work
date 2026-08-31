from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .episodic_memory import EpisodicMemory, Episode
from .semantic_memory import SemanticMemory, Knowledge

from database.sqlite_store import SQLiteStore


class MemoryManager:
    """
    Unified persistent memory coordinator of the JARVIS organism.

    Memory layers:

        EpisodicMemory
            ↓
        SemanticMemory
            ↓
        SQLiteStore
            ↓
        database/jarvis.db

    MemoryManager provides the stable interface used by:
        Brain
        Learning
        Autonomy
        Skills

    It does NOT decide what should be learned.

    SemanticMemory owns the FAISS index and NetworkX graph.
    MemoryManager only coordinates those memory organs.
    """

    VERSION = "0.2.2"

    def __init__(
        self,
        episodic: Optional[EpisodicMemory] = None,
        semantic: Optional[SemanticMemory] = None,
        event_bus=None,
        store: Optional[SQLiteStore] = None,
    ):
        self.episodic = episodic if episodic is not None else EpisodicMemory()
        self.semantic = semantic if semantic is not None else SemanticMemory()
        self.events = event_bus
        self.store = store if store is not None else SQLiteStore("database/jarvis.db")
        self.created_at = time.time()
        self.updated_at = self.created_at
        self._restore_from_database()

    def _restore_from_database(self) -> None:
        """Load persistent episodic memory; SemanticMemory hydrates itself."""
        try:
            episodic_data = self.store.load_episodes()
            if episodic_data:
                self.episodic.restore({"episodes": episodic_data})
        except Exception as exc:
            print(f"[MemoryManager Restore Error] {exc}")

    def remember_experience(
        self,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
        action: Optional[Dict[str, Any]] = None,
        outcome: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        confidence: float = 1.0,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Episode:
        episode = self.episodic.remember(
            event_type=event_type,
            context=context,
            action=action,
            outcome=outcome,
            importance=importance,
            confidence=confidence,
            source=source,
            tags=tags,
        )
        self.store.save_episode(episode.to_dict())
        self.updated_at = time.time()
        self._emit(
            "MEMORY_CREATED",
            {
                "memory_type": "EPISODIC",
                "episode_id": episode.episode_id,
                "event_type": episode.event_type,
            },
        )
        return episode

    def remember_knowledge(
        self,
        subject: str,
        predicate: str,
        value: Any,
        confidence: float = 0.5,
        importance: float = 0.5,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Knowledge:
        knowledge = self.semantic.remember(
            subject=subject,
            predicate=predicate,
            value=value,
            confidence=confidence,
            importance=importance,
            source=source,
            tags=tags,
        )
        self.updated_at = time.time()
        self._emit(
            "KNOWLEDGE_UPDATED",
            {
                "memory_type": "SEMANTIC",
                "knowledge_id": knowledge.knowledge_id,
                "subject": knowledge.subject,
                "predicate": knowledge.predicate,
            },
        )
        return knowledge

    def recent_experiences(self, limit: int = 20) -> List[Episode]:
        return self.episodic.recent(limit=limit)

    def important_experiences(self, threshold: float = 0.7, limit: int = 20) -> List[Episode]:
        return self.episodic.important(threshold=threshold, limit=limit)

    def find_experiences(
        self,
        event_type: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> List[Episode]:
        if event_type:
            return self.episodic.find_by_event(event_type=event_type, limit=limit)
        if tag:
            return self.episodic.find_by_tag(tag=tag, limit=limit)
        return self.episodic.recent(limit=limit)

    def get_knowledge(
        self,
        subject: str,
        predicate: Optional[str] = None,
        value: Any = None,
    ) -> List[Knowledge]:
        return self.semantic.find(subject=subject, predicate=predicate, value=value)

    def knowledge_about(self, subject: str, limit: int = 50) -> List[Knowledge]:
        """Return all semantic knowledge for one subject."""
        return self.semantic.find(subject=subject)[: max(0, int(limit))]

    def get_graph_relations(self, subject: str) -> List[Dict[str, Any]]:
        """Return NetworkX graph relations owned by SemanticMemory."""
        if hasattr(self.semantic, "get_graph_relations"):
            return self.semantic.get_graph_relations(subject)
        return []

    def search_knowledge(self, query: str, limit: int = 20) -> List[Knowledge]:
        return self.semantic.hybrid_search(query=query, limit=limit)

    def list_all_knowledge(self, limit: int = 500) -> List[Knowledge]:
        return self.semantic.list_all(limit=limit)

    def forget_knowledge(self, knowledge_id: str) -> bool:
        return self.semantic.forget(knowledge_id)

    def search_memory_by_tag(self, tag: str, limit: int = 20) -> Dict[str, List[Any]]:
        """Search both episodic and semantic memory by tag."""
        knowledge = []
        find_by_tag = getattr(self.semantic, "find_by_tag", None)
        if callable(find_by_tag):
            knowledge = find_by_tag(tag=tag, limit=limit)
        else:
            # SemanticMemory currently persists tags in SQLite; keep the
            # coordinator compatible without requiring a second semantic API.
            for item in self.semantic.list_all(limit=max(limit, 1) * 10):
                if tag in (item.tags or []):
                    knowledge.append(item)
                    if len(knowledge) >= limit:
                        break
        return {
            "episodes": self.episodic.find_by_tag(tag=tag, limit=limit),
            "knowledge": knowledge,
        }

    def build_context(
        self,
        query: Optional[str] = None,
        subject: Optional[str] = None,
        recent_limit: int = 5,
        knowledge_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Build Brain memory context from episodic memory, semantic/FAISS
        retrieval, and graph relations.

        Subject lookup deliberately uses SemanticMemory.find(), which is
        the canonical subject/predicate lookup API. There is no hidden
        find_by_subject dependency.
        """
        recent = self.episodic.recent(limit=recent_limit)
        context: Dict[str, Any] = {
            "recent_experiences": [episode.to_dict() for episode in recent],
            "relevant_knowledge": [],
            "graph_relations": [],
        }
        graph_relations: List[Dict[str, Any]] = []

        if subject:
            knowledge = self.semantic.find(subject=subject)[: max(0, int(knowledge_limit))]
            graph_relations.extend(self.get_graph_relations(subject))
        elif query:
            knowledge = self.semantic.hybrid_search(query=query, limit=knowledge_limit)
            seen_subjects = set()
            for item in knowledge:
                item_subject = getattr(item, "subject", None)
                if item_subject and item_subject not in seen_subjects:
                    seen_subjects.add(item_subject)
                    graph_relations.extend(self.get_graph_relations(item_subject))
        else:
            knowledge = []

        context["relevant_knowledge"] = [item.to_dict() for item in knowledge]
        context["graph_relations"] = graph_relations
        return context

    def statistics(self) -> Dict[str, Any]:
        try:
            database_stats = self.store.statistics()
        except Exception as exc:
            database_stats = {"error": str(exc)}
        return {
            "version": self.VERSION,
            "runtime": {
                "episodic": self.episodic.count,
                "semantic": self.semantic.count,
            },
            "persistent": database_stats,
            "updated_at": self.updated_at,
        }

    def snapshot(
        self,
        episode_limit: Optional[int] = None,
        knowledge_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "episodic": self.episodic.snapshot(limit=episode_limit),
            "semantic": self.semantic.snapshot(limit=knowledge_limit),
            "database": self.store.statistics(),
        }

    def restore(self, snapshot: Dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            return
        episodic_snapshot = snapshot.get("episodic")
        semantic_snapshot = snapshot.get("semantic")
        if isinstance(episodic_snapshot, dict):
            self.episodic.restore(episodic_snapshot)
        if isinstance(semantic_snapshot, dict):
            self.semantic.restore(semantic_snapshot)
        self.updated_at = time.time()

    def clear_all(self) -> None:
        self.episodic.clear()
        self.semantic.clear()
        for episode in self.store.load_episodes():
            self.store.delete_episode(episode["episode_id"])
        self.updated_at = time.time()
        self._emit("MEMORY_CLEARED", {"timestamp": self.updated_at})

    def close(self) -> None:
        if self.store is not None:
            self.store.close()

    def _emit(self, event_name: str, payload: Any = None) -> None:
        if self.events is None:
            return
        safe_emit = getattr(self.events, "safe_emit", None)
        if callable(safe_emit):
            safe_emit(event_name, payload, source="memory_manager")
