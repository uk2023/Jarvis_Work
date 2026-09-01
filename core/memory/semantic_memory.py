from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

import faiss
import networkx as nx
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class FastONNXEmbedder:
    """Lightweight CPU-only embedder using ONNX Runtime for ARM64 / Termux."""

    def __init__(self, model_path: str = "all-MiniLM-L6-v2.onnx", tokenizer_path: str = "tokenizer.json"):
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.vector_dim = 384
        if not os.path.exists(model_path) or not os.path.exists(tokenizer_path):
            print(f"[ONNXEmbedder] Warning: {model_path} or {tokenizer_path} not found!")
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_padding(length=128, pad_id=0, pad_token="[PAD]")
        self.tokenizer.enable_truncation(max_length=128)

    def get_sentence_embedding_dimension(self) -> int:
        return self.vector_dim

    def encode(self, sentences: Union[str, List[str]], show_progress_bar: bool = False) -> np.ndarray:
        is_single = isinstance(sentences, str)
        text_list = [sentences] if is_single else sentences
        encoded_batch = [self.tokenizer.encode(t) for t in text_list]
        input_ids = np.array([e.ids for e in encoded_batch], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded_batch], dtype=np.int64)
        token_type_ids = np.array([e.type_ids for e in encoded_batch], dtype=np.int64)
        inputs = {"input_ids": input_ids, "attention_mask": attention_mask, "token_type_ids": token_type_ids}
        outputs = self.session.run(None, inputs)
        embeddings = outputs[0]
        mask_expanded = np.expand_dims(attention_mask, -1)
        sum_embeddings = np.sum(embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = sum_embeddings / sum_mask
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        normalized = (pooled / np.clip(norms, a_min=1e-9, a_max=None)).astype(np.float32)
        return normalized[0] if is_single else normalized


@dataclass
class Knowledge:
    """A single piece of semantic knowledge in JARVIS's long-term memory."""
    knowledge_id: str
    subject: str
    predicate: str
    value: Any
    confidence: float = 0.5
    importance: float = 0.5
    source: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0
    evidence_count: int = 1
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Knowledge":
        tags = data.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except json.JSONDecodeError:
                tags = []
        value = data.get("value")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls(
            knowledge_id=data["knowledge_id"], subject=data["subject"], predicate=data["predicate"], value=value,
            confidence=float(data.get("confidence", 0.5)), importance=float(data.get("importance", 0.5)),
            source=data.get("source"), created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())), evidence_count=int(data.get("evidence_count", 1)), tags=tags,
        )


class SemanticMemory:
    """Long-term knowledge store of JARVIS (Android PRoot Optimized)."""
    VERSION = "0.3.6"

    def __init__(self, db_path: str = "database/jarvis.db", faiss_index_path: str = "database/jarvis_faiss.index",
                 max_knowledge: int = 10000, model_path: str = "all-MiniLM-L6-v2.onnx", tokenizer_path: str = "tokenizer.json"):
        self.db_path = db_path
        self.faiss_index_path = faiss_index_path
        self.max_knowledge = max(1, int(max_knowledge))
        self._lock = threading.RLock()
        self._init_sqlite_db()
        print("[SemanticMemory] Loading ONNX Fast Embedder & FAISS Vector Store...")
        self.embedder = FastONNXEmbedder(model_path=model_path, tokenizer_path=tokenizer_path)
        self.vector_dim = self.embedder.get_sentence_embedding_dimension()
        self.faiss_index = faiss.IndexIDMap2(faiss.IndexFlatL2(self.vector_dim))
        self.id_to_faiss_idx: Dict[str, int] = {}
        self.faiss_idx_to_id: Dict[int, str] = {}
        self._next_faiss_id = 1
        self.graph = nx.DiGraph()
        self._hydrate_stores()
        self.created_at = time.time()
        self.updated_at = self.created_at

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite_db(self) -> None:
        with self._lock, self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    knowledge_id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, value TEXT NOT NULL,
                    confidence REAL NOT NULL, importance REAL NOT NULL, source TEXT, created_at REAL NOT NULL,
                    updated_at REAL NOT NULL, evidence_count INTEGER NOT NULL, tags TEXT NOT NULL, faiss_id INTEGER
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_subject ON knowledge(subject);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_predicate ON knowledge(predicate);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_pred ON knowledge(subject, predicate);")
            try:
                conn.execute("SELECT faiss_id FROM knowledge LIMIT 1;")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE knowledge ADD COLUMN faiss_id INTEGER;")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_faiss_id ON knowledge(faiss_id) WHERE faiss_id IS NOT NULL;")
            conn.commit()

    def _hydrate_stores(self) -> None:
        with self._lock, self._get_db_connection() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM knowledge").fetchall()]
            if not rows:
                return
            max_existing = max((int(r["faiss_id"]) for r in rows if r.get("faiss_id") is not None), default=0)
            next_id = max_existing + 1
            rows_needing_id = [r for r in rows if r.get("faiss_id") is None]
            for row in rows_needing_id:
                row["faiss_id"] = next_id
                next_id += 1
                conn.execute("UPDATE knowledge SET faiss_id = ? WHERE knowledge_id = ?", (row["faiss_id"], row["knowledge_id"]))
            if rows_needing_id:
                conn.commit()
            self._next_faiss_id = next_id
            texts_to_embed, faiss_ids = [], []
            for row in rows:
                item = Knowledge.from_dict(row)
                self._add_to_graph(item)
                faiss_id = int(row["faiss_id"])
                self.id_to_faiss_idx[item.knowledge_id] = faiss_id
                self.faiss_idx_to_id[faiss_id] = item.knowledge_id
                texts_to_embed.append(f"{item.subject} {item.predicate} {str(item.value)}")
                faiss_ids.append(faiss_id)
            loaded_ok = False
            if os.path.exists(self.faiss_index_path):
                try:
                    candidate = faiss.read_index(self.faiss_index_path)
                    if candidate.ntotal == len(faiss_ids):
                        self.faiss_index = candidate
                        loaded_ok = True
                except Exception:
                    loaded_ok = False
            if not loaded_ok and texts_to_embed:
                self._rebuild_faiss_batch(texts_to_embed, faiss_ids)

    def _rebuild_faiss_batch(self, texts: List[str], ids: List[int]) -> None:
        vectors = self.embedder.encode(texts, show_progress_bar=False).astype(np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(ids) or vectors.shape[1] != self.vector_dim:
            vectors = np.asarray(vectors, dtype=np.float32).reshape(len(ids), self.vector_dim)
        self.faiss_index = faiss.IndexIDMap2(faiss.IndexFlatL2(self.vector_dim))
        self.faiss_index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))
        self._save_faiss_to_disk()

    def _faiss_single_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize one embedding to FAISS's required (1, dimension) shape."""
        array = np.asarray(vector, dtype=np.float32)
        if array.size != self.vector_dim:
            raise ValueError(f"Embedding dimension mismatch: expected {self.vector_dim} values, got shape {array.shape}.")
        return array.reshape(1, self.vector_dim)

    def remember(self, subject: str, predicate: str, value: Any, confidence: float = 0.5, importance: float = 0.5,
                 source: Optional[str] = None, tags: Optional[List[str]] = None) -> Knowledge:
        subject, predicate = self._normalize(subject), self._normalize(predicate)
        if not subject or not predicate:
            raise ValueError("subject and predicate cannot be empty.")
        with self._lock:
            existing = self._find_by_trace(subject, predicate)
            if existing is not None:
                old_val_norm = self._normalize(existing.value)
                new_val_norm = self._normalize(value)
                value_changed = old_val_norm != new_val_norm
                existing.evidence_count += 1
                existing.confidence = self._merge_confidence(existing.confidence, confidence)
                existing.importance = max(existing.importance, self._clamp(importance))
                existing.updated_at = time.time()
                existing.value = value
                if source:
                    existing.source = source
                if tags:
                    existing.tags = list(set(existing.tags + (tags or [])))
                existing_faiss_id = self.id_to_faiss_idx.get(existing.knowledge_id)
                self._save_knowledge_to_db(existing, faiss_id=existing_faiss_id)
                if value_changed:
                    if self.graph.has_edge(existing.subject, old_val_norm):
                        self.graph.remove_edge(existing.subject, old_val_norm)
                    self._add_to_graph(existing)
                    if existing_faiss_id is not None:
                        text_to_embed = f"{existing.subject} {existing.predicate} {str(existing.value)}"
                        vector = self.embedder.encode(text_to_embed).astype(np.float32)
                        self.faiss_index.remove_ids(np.asarray([existing_faiss_id], dtype=np.int64))
                        self.faiss_index.add_with_ids(self._faiss_single_vector(vector), np.asarray([existing_faiss_id], dtype=np.int64))
                self.updated_at = existing.updated_at
                self._save_faiss_to_disk()
                return existing
            now = time.time()
            knowledge = Knowledge(
                knowledge_id=str(uuid.uuid4()), subject=subject, predicate=predicate, value=value,
                confidence=self._clamp(confidence), importance=self._clamp(importance), source=source,
                created_at=now, updated_at=now, evidence_count=1, tags=list(tags or []),
            )
            faiss_id = self._next_faiss_id
            self._next_faiss_id += 1
            self._save_knowledge_to_db(knowledge, faiss_id=faiss_id)
            self._add_to_graph(knowledge)
            text_to_embed = f"{knowledge.subject} {knowledge.predicate} {str(knowledge.value)}"
            vector = self.embedder.encode(text_to_embed).astype(np.float32)
            self.faiss_index.add_with_ids(self._faiss_single_vector(vector), np.asarray([faiss_id], dtype=np.int64))
            self.id_to_faiss_idx[knowledge.knowledge_id] = faiss_id
            self.faiss_idx_to_id[faiss_id] = knowledge.knowledge_id
            self.updated_at = now
            self._prune()
            self._save_faiss_to_disk()
            return knowledge

    def forget(self, knowledge_id: str) -> bool:
        with self._lock:
            item = self.get(knowledge_id)
            if not item:
                return False
            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM knowledge WHERE knowledge_id = ?", (knowledge_id,))
                conn.commit()
            val_norm = self._normalize(item.value)
            if self.graph.has_edge(item.subject, val_norm):
                self.graph.remove_edge(item.subject, val_norm)
            if knowledge_id in self.id_to_faiss_idx:
                faiss_id = self.id_to_faiss_idx.pop(knowledge_id)
                self.faiss_idx_to_id.pop(faiss_id, None)
                self.faiss_index.remove_ids(np.asarray([faiss_id], dtype=np.int64))
            self.updated_at = time.time()
            self._save_faiss_to_disk()
            return True

    def list_all(self, limit: int = 500) -> List["Knowledge"]:
        with self._lock, self._get_db_connection() as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM knowledge ORDER BY updated_at DESC LIMIT ?", (max(1, int(limit)),)).fetchall()]
        return [Knowledge.from_dict(row) for row in rows]

    def semantic_search(self, query: str, similarity_threshold: float = 0.70, max_candidate_cap: int = 20,
                        top_k: Optional[int] = None) -> List[Knowledge]:
        """Retrieve semantically similar knowledge using the single FAISS index."""
        if top_k is not None:
            max_candidate_cap = max(1, int(top_k))
        with self._lock:
            if self.faiss_index.ntotal == 0:
                return []
            query_vector = self.embedder.encode(query).astype(np.float32)
            k_search = min(max_candidate_cap, self.faiss_index.ntotal)
            distances, indices = self.faiss_index.search(self._faiss_single_vector(query_vector), k_search)
            active_facts = []
            for dist, idx in zip(distances[0], indices[0]):
                idx = int(idx)
                if idx != -1 and idx in self.faiss_idx_to_id:
                    cosine_sim = float(1.0 - (dist / 2.0))
                    if cosine_sim >= similarity_threshold:
                        item = self.get(self.faiss_idx_to_id[idx])
                        if item:
                            active_facts.append(item)
            return active_facts

    def hybrid_search(self, query: str, limit: int = 5, similarity_threshold: float = 0.70, lexical_fallback_limit: int = 5) -> List[Knowledge]:
        semantic_results = self.semantic_search(query, similarity_threshold=similarity_threshold, top_k=limit)
        if len(semantic_results) >= limit:
            return semantic_results[:limit]
        seen_ids = {item.knowledge_id for item in semantic_results}
        lexical_results: List[Knowledge] = []
        for item in self.search(query, limit=lexical_fallback_limit):
            if item.knowledge_id not in seen_ids:
                lexical_results.append(item)
                seen_ids.add(item.knowledge_id)
            if len(semantic_results) + len(lexical_results) >= limit:
                break
        return (semantic_results + lexical_results)[:limit]

    def get_trimmed_context(self, query: str, subject: Optional[str] = None, similarity_threshold: float = 0.70) -> str:
        facts = self.semantic_search(query, similarity_threshold=similarity_threshold)
        if not facts and not subject:
            return ""
        context_lines = [f"Fact: {f.subject} {f.predicate} {f.value}" for f in facts]
        if subject:
            graph_limit = max(3, len(facts) * 2)
            for r in self.get_graph_relations(subject, max_limit=graph_limit):
                context_lines.append(f"Relation: {r['subject']} -> {r['predicate']} -> {r['target']}")
        return "\n".join(context_lines)

    def get_graph_relations(self, subject: str, max_limit: int = 5) -> List[Dict[str, Any]]:
        subject = self._normalize(subject)
        with self._lock:
            if subject not in self.graph:
                return []
            relations = []
            for neighbor in self.graph.successors(subject):
                edge_data = self.graph.get_edge_data(subject, neighbor)
                relations.append({"subject": subject, "target": neighbor, "predicate": edge_data.get("predicate", "related_to")})
                if len(relations) >= max_limit:
                    break
            return relations

    def find(self, subject: str, predicate: Optional[str] = None, value: Any = None) -> List[Knowledge]:
        subject = self._normalize(subject)
        query = "SELECT * FROM knowledge WHERE subject = ?"
        params: List[Any] = [subject]
        if predicate is not None:
            query += " AND predicate = ?"
            params.append(self._normalize(predicate))
        if value is not None:
            query += " AND value = ?"
            params.append(json.dumps(value) if not isinstance(value, str) else value)
        with self._lock, self._get_db_connection() as conn:
            return [Knowledge.from_dict(dict(row)) for row in conn.execute(query, params).fetchall()]

    def find_by_subject(self, subject: str, limit: Optional[int] = None) -> List[Knowledge]:
        results = self.find(subject=subject)
        return results if limit is None else results[:max(0, int(limit))]

    def find_by_predicate(self, predicate: str, limit: Optional[int] = None) -> List[Knowledge]:
        predicate = self._normalize(predicate)
        with self._lock, self._get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM knowledge WHERE predicate = ? ORDER BY updated_at DESC", (predicate,)).fetchall()
        results = [Knowledge.from_dict(dict(row)) for row in rows]
        return results if limit is None else results[:max(0, int(limit))]

    def find_by_tag(self, tag: str, limit: Optional[int] = None) -> List[Knowledge]:
        target = self._normalize(tag)
        with self._lock, self._get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM knowledge ORDER BY updated_at DESC").fetchall()
        results = []
        for row in rows:
            item = Knowledge.from_dict(dict(row))
            if any(self._normalize(t) == target for t in item.tags):
                results.append(item)
                if limit is not None and len(results) >= max(0, int(limit)):
                    break
        return results

    def search(self, query: str, limit: int = 20) -> List[Knowledge]:
        query_norm = f"%{self._normalize(query)}%"
        sql = """
            SELECT * FROM knowledge
            WHERE subject LIKE ? OR predicate LIKE ? OR value LIKE ? OR tags LIKE ?
            ORDER BY importance DESC, confidence DESC, updated_at DESC
            LIMIT ?
        """
        with self._lock, self._get_db_connection() as conn:
            return [Knowledge.from_dict(dict(row)) for row in conn.execute(sql, (query_norm, query_norm, query_norm, query_norm, limit)).fetchall()]

    def get(self, knowledge_id: str) -> Optional[Knowledge]:
        with self._lock, self._get_db_connection() as conn:
            row = conn.execute("SELECT * FROM knowledge WHERE knowledge_id = ?", (knowledge_id,)).fetchone()
            return Knowledge.from_dict(dict(row)) if row else None

    def update_confidence(self, knowledge_id: str, confidence: float) -> Optional[Knowledge]:
        with self._lock:
            item = self.get(knowledge_id)
            if item is None:
                return None
            item.confidence = self._clamp(confidence)
            item.updated_at = time.time()
            self._save_knowledge_to_db(item, faiss_id=self.id_to_faiss_idx.get(knowledge_id))
            self.updated_at = item.updated_at
            return item

    def reinforce(self, knowledge_id: str, confidence_delta: float = 0.1) -> Optional[Knowledge]:
        item = self.get(knowledge_id)
        if item is None:
            return None
        return self.update_confidence(knowledge_id, item.confidence + float(confidence_delta))

    def weaken(self, knowledge_id: str, confidence_delta: float = 0.1) -> Optional[Knowledge]:
        item = self.get(knowledge_id)
        if item is None:
            return None
        return self.update_confidence(knowledge_id, item.confidence - float(confidence_delta))

    def snapshot(self, limit: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            query = "SELECT * FROM knowledge ORDER BY updated_at ASC"
            params = []
            if limit is not None:
                query += " LIMIT ?"
                params.append(max(0, int(limit)))
            with self._get_db_connection() as conn:
                rows = conn.execute(query, params).fetchall()
            return {"version": self.VERSION, "count": self.count, "max_knowledge": self.max_knowledge,
                    "created_at": self.created_at, "updated_at": self.updated_at,
                    "knowledge": [Knowledge.from_dict(dict(row)).to_dict() for row in rows]}

    def restore(self, snapshot: Dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            return
        raw_knowledge = snapshot.get("knowledge", [])
        if not isinstance(raw_knowledge, list):
            return
        for data in raw_knowledge:
            if not isinstance(data, dict):
                continue
            try:
                knowledge = Knowledge.from_dict(data)
                if self.get(knowledge.knowledge_id) is None:
                    self.remember(subject=knowledge.subject, predicate=knowledge.predicate, value=knowledge.value,
                                  confidence=knowledge.confidence, importance=knowledge.importance, source=knowledge.source, tags=knowledge.tags)
            except Exception as exc:
                print(f"[SemanticMemory] Restore warning: {exc}")
        self.updated_at = time.time()
        self._save_faiss_to_disk()

    @property
    def count(self) -> int:
        with self._lock, self._get_db_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]

    def clear(self) -> None:
        with self._lock:
            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM knowledge")
                conn.commit()
            self.graph.clear()
            self.faiss_index = faiss.IndexIDMap2(faiss.IndexFlatL2(self.vector_dim))
            self.id_to_faiss_idx.clear()
            self.faiss_idx_to_id.clear()
            self._next_faiss_id = 1
            if os.path.exists(self.faiss_index_path):
                try:
                    os.remove(self.faiss_index_path)
                except OSError:
                    pass
            self.updated_at = time.time()

    def _prune(self) -> None:
        current_count = self.count
        if current_count <= self.max_knowledge:
            return
        excess = current_count - self.max_knowledge
        with self._lock, self._get_db_connection() as conn:
            rows = conn.execute("""
                SELECT knowledge_id FROM knowledge
                ORDER BY importance ASC, confidence ASC, updated_at ASC
                LIMIT ?
            """, (excess,)).fetchall()
            to_remove = [row["knowledge_id"] for row in rows]
        for k_id in to_remove:
            self.forget(k_id)

    def _save_knowledge_to_db(self, knowledge: Knowledge, faiss_id: Optional[int] = None) -> None:
        val_str = json.dumps(knowledge.value) if not isinstance(knowledge.value, str) else knowledge.value
        tags_str = json.dumps(knowledge.tags)
        with self._get_db_connection() as conn:
            conn.execute("""
                INSERT INTO knowledge (
                    knowledge_id, subject, predicate, value, confidence, importance, source,
                    created_at, updated_at, evidence_count, tags, faiss_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(knowledge_id) DO UPDATE SET
                    value=excluded.value, confidence=excluded.confidence, importance=excluded.importance,
                    source=excluded.source, updated_at=excluded.updated_at, evidence_count=excluded.evidence_count,
                    tags=excluded.tags, faiss_id=excluded.faiss_id;
            """, (knowledge.knowledge_id, knowledge.subject, knowledge.predicate, val_str, knowledge.confidence,
                  knowledge.importance, knowledge.source, knowledge.created_at, knowledge.updated_at,
                  knowledge.evidence_count, tags_str, faiss_id))
            conn.commit()

    def _add_to_graph(self, item: Knowledge) -> None:
        self.graph.add_node(item.subject, type="subject")
        if isinstance(item.value, str):
            val_str = self._normalize(item.value)
            self.graph.add_node(val_str, type="value")
            self.graph.add_edge(item.subject, val_str, predicate=item.predicate)

    def _save_faiss_to_disk(self) -> None:
        try:
            faiss.write_index(self.faiss_index, self.faiss_index_path)
        except Exception as e:
            print(f"[SemanticMemory] Error saving FAISS index to disk: {e}")

    def _find_by_trace(self, subject: str, predicate: str) -> Optional[Knowledge]:
        items = self.find(subject, predicate)
        return items[0] if items else None

    def _find_exact(self, subject: str, predicate: str, value: Any) -> Optional[Knowledge]:
        items = self.find(subject, predicate)
        for item in items:
            if item.value == value:
                return item
        return None

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _merge_confidence(old: float, new: float) -> float:
        old = max(0.0, min(1.0, old))
        new = max(0.0, min(1.0, new))
        return old + ((new - old) * 0.25)
