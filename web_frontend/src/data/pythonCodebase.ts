import { PythonCodeFile } from '../types';

export const PYTHON_CODEBASE: PythonCodeFile[] = [
  {
    filename: 'brain.py',
    path: 'core/orchestration/brain.py',
    category: 'orchestration',
    description: 'Central Cognitive Orchestrator with Async Non-blocking Background Learning & Single-Turn Dual Signal Extraction.',
    code: `# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import time
import threading
import queue
from typing import Any, Dict, Optional, List


class Brain:
    """
    JARVIS COGNITIVE BRAIN ORCHESTRATOR (v2026.4 - Async Learning Edition)
    
    Architectural Optimizations:
    1. Synchronous ultra-fast response to User (<0.5s local / cloud).
    2. Non-blocking Asynchronous Background Learning Queue:
       USER -> RETRIEVE -> QWEN INFERENCE -> RETURN RESPONSE IMMEDIATELY
       └─> Async Background Thread: ExperienceEngine -> SelfEvaluator -> KnowledgeBuilder -> Acceptance -> DB
    3. Hinglish & Typo Normalizer (handles phonetics like "nan" -> "naam", "xhahta" -> "chahta").
    4. Auto-reconsolidation: Prevents duplicated memory triples and updates evidence/confidence in-place.
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

        self.auto_accept_knowledge = auto_accept_knowledge
        self.created_at = time.time()
        self.last_cycle_at: Optional[float] = None
        self.cycle_count = 0
        self.running = True

        # Async background learning queue & worker thread
        self._learning_queue: queue.Queue = queue.Queue(maxsize=100)
        self._start_background_learning_worker()

    def _start_background_learning_worker(self):
        def _worker():
            while self.running:
                try:
                    task = self._learning_queue.get(timeout=2.0)
                    if task is None:
                        break
                    
                    user_input, response_text, source = task
                    self._process_background_learning(user_input, response_text, source)
                    self._learning_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[Brain Background Worker Error] {e}")

        t = threading.Thread(target=_worker, name="JARVIS-BackgroundLearning", daemon=True)
        t.start()

    def think_and_respond(
        self,
        user_input: str,
        identity_profile: Optional[Dict[str, Any]] = None,
        source: str = "cli",
    ) -> str:
        """
        FAST SYNCHRONOUS PATH:
        1. Context Retrieval from FAISS & Knowledge Graph.
        2. Prompt Synthesis with Identity Instructions.
        3. Neural Inference (Qwen / Groq).
        4. Enqueue interaction to background learning thread for 0-latency response.
        """
        if self.llm is None:
            return "[Brain Error: LLM Bridge not connected.]"

        # 1. Retrieve relevant memory & graph nodes
        context = self.build_context(query=user_input, recent_limit=3, knowledge_limit=5)
        recent_memories = context.get("recent_experiences", [])
        relevant_knowledge = context.get("relevant_knowledge", [])
        graph_relations = context.get("graph_relations", [])

        bot_name = identity_profile.get("name", "JARVIS") if identity_profile else "JARVIS"
        creator_name = identity_profile.get("creator", "UK") if identity_profile else "UK"

        # 2. System Identity Prompt
        system_prompt = (
            f"SYSTEM IDENTITY INSTRUCTIONS (STRICT):\n"
            f"1. You are {bot_name}, a self-contained cognitive AI organism running locally.\n"
            f"2. The user talking to you is {creator_name}, your developer and creator.\n"
            f"3. NEVER swap roles or claim to be {creator_name}.\n"
            f"4. Communicate naturally, precisely, and conversationally in Hinglish.\n"
            f"5. Understand Hinglish slang and typos automatically.\n"
            f"6. Keep responses witty, sharp, loyal, and concise like Marvel JARVIS.\n"
            f"7. Always loyal to {creator_name}."
        )

        # 3. Context Payload
        context_prompt = (
            f"=== RETRIEVED MEMORIES ===\n{recent_memories if recent_memories else 'No previous memory match.'}\n\n"
            f"=== SEMANTIC KNOWLEDGE ===\n{relevant_knowledge if relevant_knowledge else 'No direct facts found.'}\n\n"
            f"=== KNOWLEDGE GRAPH EDGES ===\n{graph_relations if graph_relations else 'No graph nodes linked.'}\n\n"
            f"=== CURRENT USER MESSAGE ===\n{creator_name}: {user_input}\n\n"
            f"{bot_name}:"
        )

        try:
            response = self.llm.generate_response(
                system_prompt=system_prompt,
                user_input=context_prompt,
                max_tokens=512,
                temperature=0.7
            )
            cleaned_response = response.strip() if isinstance(response, str) else str(response)
        except Exception as exc:
            return f"[Brain Inference Error: {exc}]"

        # 4. Enqueue to Background Learning Queue (Non-blocking)
        try:
            self._learning_queue.put_nowait((user_input, cleaned_response, source))
        except queue.Full:
            print("[Brain Warning] Learning queue is full, dropping frame.")

        return cleaned_response

    def _process_background_learning(self, user_input: str, response_text: str, source: str):
        """Executed asynchronously in background thread to avoid user-facing latency."""
        outcome: Dict[str, Any] = {"status": "completed"}
        
        # Extract structured fact triple if present
        fact = self._extract_fact_fast(user_input, response_text)
        if fact:
            outcome.update(fact)

        try:
            self.process_experience(
                event_type="USER_CHAT",
                context={"user_input": user_input},
                action={"jarvis_response": response_text},
                outcome=outcome,
                source=source,
                importance=0.7 if fact else 0.4,
                build_knowledge=True,
                auto_accept=self.auto_accept_knowledge,
            )
        except Exception as e:
            print(f"[Brain Learning Pipeline Exception] {e}")

    _FACT_EXTRACTION_PROMPT = (
        "You are an expert fact extractor for personal cognitive AI. "
        "Extract ONE factual statement from the conversation turn if one exists. "
        "The user often speaks in Hinglish with minor spelling typos (e.g., 'nan' -> 'naam', 'psnd' -> 'pasand'). "
        "Correct typos automatically and extract clear subject, predicate, and value. "
        "Return ONLY a raw JSON object. If no new fact exists, return: {\"has_fact\": false}\n\n"
        "Examples:\n"
        "User: 'mera ex ka nan devyana h' -> {\"has_fact\": true, \"subject\": \"user_ex\", \"predicate\": \"name\", \"value\": \"Devyana\"}\n"
        "User: 'mujhe python coding psnd h' -> {\"has_fact\": true, \"subject\": \"user\", \"predicate\": \"favorite_language\", \"value\": \"Python\"}\n"
    )

    def _extract_fact_fast(self, user_input: str, jarvis_response: str) -> Optional[Dict[str, Any]]:
        if not self.llm:
            return None

        # Lightweight rule-based fast heuristic check before calling LLM
        intent_keywords = ["mera", "meri", "mujhe", "naam", "nan", "hobbies", "setup", "ex", "pass", "like", "favorite", "live", "rehta"]
        if not any(kw in user_input.lower() for kw in intent_keywords):
            return None

        try:
            raw = self.llm.generate_response(
                system_prompt=self._FACT_EXTRACTION_PROMPT,
                user_input=f"User: {user_input}\nAssistant: {jarvis_response}",
                max_tokens=150,
                temperature=0.0
            )
            cleaned = raw.strip().replace(chr(96)*3 + "json", "").replace(chr(96)*3, "").strip()
            data = json.loads(cleaned)
            
            if isinstance(data, dict) and data.get("has_fact"):
                sub = str(data.get("subject", "")).strip().lower()
                pred = str(data.get("predicate", "")).strip().lower()
                val = data.get("value")
                if sub and pred and val:
                    return {"subject": sub, "predicate": pred, "value": val}
        except Exception:
            pass
        return None

    def build_context(
        self,
        query: Optional[str] = None,
        subject: Optional[str] = None,
        recent_limit: int = 3,
        knowledge_limit: int = 5,
    ) -> Dict[str, Any]:
        if self.memory is None:
            return {"recent_experiences": [], "relevant_knowledge": [], "graph_relations": []}

        return self.memory.build_context(
            query=query,
            subject=subject,
            recent_limit=recent_limit,
            knowledge_limit=knowledge_limit,
        )

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
        if self.experience is None:
            raise RuntimeError("ExperienceEngine is not connected.")

        if auto_accept is None:
            auto_accept = self.auto_accept_knowledge

        # 1. Experience Engine Step
        exp_res = self.experience.process(
            event_type=event_type,
            context=context or {},
            action=action or {},
            outcome=outcome or {},
            source=source,
            importance=importance,
        )
        experience = exp_res.get("experience", {})

        # 2. Learning Coordinator Step
        learning_result = None
        if self.learning and build_knowledge:
            learning_result = self.learning.learn(experience=experience, auto_accept=auto_accept)
        elif self.knowledge_builder and build_knowledge:
            eval_res = self.evaluator.evaluate(experience) if self.evaluator else {}
            candidate = self.knowledge_builder.build(experience=experience, evaluation=eval_res)
            if auto_accept and candidate:
                self.knowledge_builder.accept(candidate["id"])

        self.cycle_count += 1
        self.last_cycle_at = time.time()
        return {"success": True, "experience": experience, "learning": learning_result}

    def stop(self):
        self.running = False
        try:
            self._learning_queue.put_nowait(None)
        except Exception:
            pass
`
  },
  {
    filename: 'semantic_memory.py',
    path: 'core/memory/semantic_memory.py',
    category: 'memory',
    description: 'FAISS Vector Database + ONNX Embedder + NetworkX Semantic Knowledge Graph with Typo-Tolerant Hybrid Search.',
    code: `# -*- coding: utf-8 -*-
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
    """Ultra-lightweight ONNX Embedder for ARM64 Android Termux (MiniLM-L6-v2 ~45MB)."""

    def __init__(
        self,
        model_path: str = "all-MiniLM-L6-v2.onnx",
        tokenizer_path: str = "tokenizer.json",
    ):
        self.vector_dim = 384
        if not os.path.exists(model_path) or not os.path.exists(tokenizer_path):
            print(f"[ONNXEmbedder] Warning: {model_path} or {tokenizer_path} missing. Run download.sh!")

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
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

        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        }

        outputs = self.session.run(None, inputs)
        embeddings = outputs[0]

        # Mean pooling with normalization
        mask_expanded = np.expand_dims(attention_mask, -1)
        sum_embeddings = np.sum(embeddings * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = sum_embeddings / sum_mask

        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        normalized = (pooled / np.clip(norms, a_min=1e-9, a_max=None)).astype(np.float32)
        return normalized[0] if is_single else normalized


@dataclass
class Knowledge:
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
    def from_dict(cls, data: Dict[str, Any]) -> Knowledge:
        tags = data.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        val = data.get("value")
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except Exception:
                pass
        return cls(
            knowledge_id=data["knowledge_id"],
            subject=data["subject"],
            predicate=data["predicate"],
            value=val,
            confidence=float(data.get("confidence", 0.5)),
            importance=float(data.get("importance", 0.5)),
            source=data.get("source"),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            evidence_count=int(data.get("evidence_count", 1)),
            tags=tags,
        )


class SemanticMemory:
    """Long-term Memory Store with FAISS Vector Index & NetworkX Knowledge Graph."""

    VERSION = "0.4.0"

    def __init__(
        self,
        db_path: str = "database/jarvis.db",
        faiss_index_path: str = "database/jarvis_faiss.index",
        max_knowledge: int = 10000,
        model_path: str = "all-MiniLM-L6-v2.onnx",
        tokenizer_path: str = "tokenizer.json",
    ):
        self.db_path = db_path
        self.faiss_index_path = faiss_index_path
        self.max_knowledge = max_knowledge
        self._lock = threading.RLock()

        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_sqlite_db()

        self.embedder = FastONNXEmbedder(model_path=model_path, tokenizer_path=tokenizer_path)
        self.vector_dim = self.embedder.get_sentence_embedding_dimension()

        self.faiss_index = faiss.IndexIDMap2(faiss.IndexFlatL2(self.vector_dim))
        self.id_to_faiss_idx: Dict[str, int] = {}
        self.faiss_idx_to_id: Dict[int, str] = {}
        self._next_faiss_id = 1
        self.graph = nx.DiGraph()

        self._hydrate_stores()

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=8.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_sqlite_db(self) -> None:
        with self._lock, self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    knowledge_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    importance REAL NOT NULL,
                    source TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    tags TEXT NOT NULL,
                    faiss_id INTEGER
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_subject ON knowledge(subject);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_pred ON knowledge(subject, predicate);")
            conn.commit()

    def _hydrate_stores(self) -> None:
        with self._lock, self._get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM knowledge")
            rows = [dict(r) for r in cursor.fetchall()]
            if not rows:
                return

            texts_to_embed = []
            faiss_ids = []

            for row in rows:
                item = Knowledge.from_dict(row)
                self._add_to_graph(item)
                fid = int(row["faiss_id"]) if row.get("faiss_id") is not None else len(self.id_to_faiss_idx) + 1
                self.id_to_faiss_idx[item.knowledge_id] = fid
                self.faiss_idx_to_id[fid] = item.knowledge_id
                texts_to_embed.append(f"{item.subject} {item.predicate} {str(item.value)}")
                faiss_ids.append(fid)

            if texts_to_embed:
                vectors = self.embedder.encode(texts_to_embed).astype(np.float32)
                self.faiss_index = faiss.IndexIDMap2(faiss.IndexFlatL2(self.vector_dim))
                self.faiss_index.add_with_ids(vectors, np.array(faiss_ids, dtype=np.int64))

    def remember(
        self,
        subject: str,
        predicate: str,
        value: Any,
        confidence: float = 0.8,
        importance: float = 0.7,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Knowledge:
        subject = self._normalize(subject)
        predicate = self._normalize(predicate)

        with self._lock:
            # 1. Check existing triple
            existing = self._find_by_trace(subject, predicate)
            if existing is not None:
                existing.evidence_count += 1
                existing.confidence = min(1.0, existing.confidence + 0.1)
                existing.importance = max(existing.importance, importance)
                existing.updated_at = time.time()
                existing.value = value
                
                faiss_id = self.id_to_faiss_idx.get(existing.knowledge_id)
                self._save_knowledge_to_db(existing, faiss_id=faiss_id)
                self._add_to_graph(existing)

                if faiss_id is not None:
                    text = f"{existing.subject} {existing.predicate} {str(existing.value)}"
                    vec = self.embedder.encode(text).astype(np.float32)
                    self.faiss_index.remove_ids(np.array([faiss_id], dtype=np.int64))
                    self.faiss_index.add_with_ids(np.array([vec]), np.array([faiss_id], dtype=np.int64))
                return existing

            # 2. Novel Fact Creation
            now = time.time()
            faiss_id = self._next_faiss_id
            self._next_faiss_id += 1

            k = Knowledge(
                knowledge_id=str(uuid.uuid4()),
                subject=subject,
                predicate=predicate,
                value=value,
                confidence=confidence,
                importance=importance,
                source=source,
                created_at=now,
                updated_at=now,
                tags=tags or [],
            )

            self._save_knowledge_to_db(k, faiss_id=faiss_id)
            self._add_to_graph(k)

            text = f"{k.subject} {k.predicate} {str(k.value)}"
            vec = self.embedder.encode(text).astype(np.float32)
            self.faiss_index.add_with_ids(np.array([vec]), np.array([faiss_id], dtype=np.int64))
            self.id_to_faiss_idx[k.knowledge_id] = faiss_id
            self.faiss_idx_to_id[faiss_id] = k.knowledge_id

            return k

    def hybrid_search(self, query: str, limit: int = 5, similarity_threshold: float = 0.55) -> List[Knowledge]:
        """Performs typo-tolerant vector similarity search with lexical fallback."""
        with self._lock:
            if self.faiss_index.ntotal == 0:
                return self.search(query, limit=limit)

            q_vec = self.embedder.encode(query).astype(np.float32)
            k_search = min(limit * 2, self.faiss_index.ntotal)
            distances, indices = self.faiss_index.search(np.array([q_vec]), k_search)

            results: List[Knowledge] = []
            for dist, idx in zip(distances[0], indices[0]):
                idx = int(idx)
                if idx != -1 and idx in self.faiss_idx_to_id:
                    cosine_sim = float(1.0 - (dist / 2.0))
                    if cosine_sim >= similarity_threshold:
                        k_item = self.get(self.faiss_idx_to_id[idx])
                        if k_item:
                            results.append(k_item)

            if len(results) < limit:
                lexical = self.search(query, limit=limit)
                seen = {r.knowledge_id for r in results}
                for item in lexical:
                    if item.knowledge_id not in seen:
                        results.append(item)
                        seen.add(item.knowledge_id)

            return results[:limit]

    def get_graph_relations(self, subject: str, max_limit: int = 5) -> List[Dict[str, Any]]:
        subject = self._normalize(subject)
        with self._lock:
            if subject not in self.graph:
                return []

            relations = []
            for neighbor in self.graph.successors(subject):
                data = self.graph.get_edge_data(subject, neighbor)
                relations.append({
                    "subject": subject,
                    "target": neighbor,
                    "predicate": data.get("predicate", "related_to")
                })
                if len(relations) >= max_limit:
                    break
            return relations

    def _add_to_graph(self, item: Knowledge) -> None:
        self.graph.add_node(item.subject, type="subject")
        if isinstance(item.value, str):
            val_norm = self._normalize(item.value)
            self.graph.add_node(val_norm, type="value")
            self.graph.add_edge(item.subject, val_norm, predicate=item.predicate)

    def _find_by_trace(self, subject: str, predicate: str) -> Optional[Knowledge]:
        with self._lock, self._get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM knowledge WHERE subject = ? AND predicate = ?", (subject, predicate))
            row = cursor.fetchone()
            return Knowledge.from_dict(dict(row)) if row else None

    def get(self, knowledge_id: str) -> Optional[Knowledge]:
        with self._lock, self._get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM knowledge WHERE knowledge_id = ?", (knowledge_id,))
            row = cursor.fetchone()
            return Knowledge.from_dict(dict(row)) if row else None

    def search(self, query: str, limit: int = 5) -> List[Knowledge]:
        q_norm = f"%{self._normalize(query)}%"
        sql = """
            SELECT * FROM knowledge
            WHERE subject LIKE ? OR predicate LIKE ? OR value LIKE ?
            ORDER BY importance DESC, confidence DESC
            LIMIT ?
        """
        with self._lock, self._get_db_connection() as conn:
            cursor = conn.execute(sql, (q_norm, q_norm, q_norm, limit))
            return [Knowledge.from_dict(dict(row)) for row in cursor.fetchall()]

    def _save_knowledge_to_db(self, k: Knowledge, faiss_id: Optional[int] = None) -> None:
        val_str = json.dumps(k.value) if not isinstance(k.value, str) else k.value
        tags_str = json.dumps(k.tags)
        with self._get_db_connection() as conn:
            conn.execute("""
                INSERT INTO knowledge (
                    knowledge_id, subject, predicate, value, confidence,
                    importance, source, created_at, updated_at, evidence_count, tags, faiss_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(knowledge_id) DO UPDATE SET
                    value=excluded.value,
                    confidence=excluded.confidence,
                    importance=excluded.importance,
                    updated_at=excluded.updated_at,
                    evidence_count=excluded.evidence_count,
                    faiss_id=excluded.faiss_id;
            """, (k.knowledge_id, k.subject, k.predicate, val_str, k.confidence, k.importance, k.source, k.created_at, k.updated_at, k.evidence_count, tags_str, faiss_id))
            conn.commit()

    @staticmethod
    def _normalize(val: Any) -> str:
        return str(val or "").strip().lower()
`
  },
  {
    filename: 'llm_bridge.py',
    path: 'core/orchestration/llm_bridge.py',
    category: 'orchestration',
    description: 'Hybrid Neural Bridge supporting offline Qwen2.5-3B / LlamaCpp with Cognitive Budgeter and Groq Cloud failover.',
    code: `# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import socket
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class CognitiveBudgeter:
    """Dynamic context pruner to prevent token overflow on local ARM64 RAM."""
    def __init__(self, max_context_tokens: int = 4096):
        self.max_context_tokens = max_context_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return int(len(text.split()) * 1.3) + 4

    def optimize_payload(self, system_prompt: str, user_input: str, max_tokens: int = 512) -> tuple[str, str]:
        budget = self.max_context_tokens - max_tokens - 128
        sys_tokens = self.estimate_tokens(system_prompt)
        usr_tokens = self.estimate_tokens(user_input)

        if (sys_tokens + usr_tokens) <= budget:
            return system_prompt, user_input

        lines = system_prompt.split("\\n")
        trimmed_lines = []
        current = usr_tokens
        for line in lines:
            cnt = self.estimate_tokens(line)
            if current + cnt <= budget:
                trimmed_lines.append(line)
                current += cnt
            else:
                break
        return "\\n".join(trimmed_lines), user_input


class LlamaCppEngine:
    """Local Offline Qwen2.5-3B / GGUF model runner (Optimized for Android 8GB RAM)."""
    def __init__(
        self,
        model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf",
        n_ctx: int = 4096,
        n_threads: int = 4,
    ):
        if Llama is None:
            raise ImportError("llama-cpp-python is not installed. Run pip install llama-cpp-python")

        model_path = os.path.join(os.path.dirname(__file__), "..", "..", "models", model_filename)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model {model_filename} not found in models/ folder!")

        print(f"[JARVIS LLM] Loading Offline Model {model_filename} (4-Threads, n_ctx={n_ctx})...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False,
        )
        self.budgeter = CognitiveBudgeter(max_context_tokens=n_ctx)

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        opt_sys, opt_usr = self.budgeter.optimize_payload(system_prompt, user_input, max_tokens)
        messages = [
            {"role": "system", "content": opt_sys},
            {"role": "user", "content": opt_usr},
        ]
        res = self.llm.create_chat_completion(messages=messages, temperature=temperature, max_tokens=max_tokens)
        return res["choices"][0]["message"]["content"].strip()


class GroqEngine:
    """Fast Cloud Bridge with Multi-Key Failover."""
    def __init__(self, api_keys: Optional[str] = None, model: str = "openai/gpt-oss-120b"):
        raw_keys = api_keys or os.getenv("GROQ_API_KEY") or ""
        self.api_keys = [k.strip() for k in raw_keys.replace(" ", "").split(",") if k.strip()]
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        self._current_idx = 0

    def generate(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        if not self.api_keys or requests is None:
            raise RuntimeError("No Groq API keys configured or requests missing.")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        total = len(self.api_keys)
        for _ in range(total):
            key = self.api_keys[self._current_idx]
            self._current_idx = (self._current_idx + 1) % total
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                continue
        raise RuntimeError("All Groq keys exhausted.")


class HybridLLMBridge:
    """Dynamic offline/online router."""
    def __init__(self, model_filename: str = "qwen2.5-3b-instruct-q4_k_m.gguf", n_ctx: int = 4096, n_threads: int = 4):
        self.model_filename = model_filename
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self._local: Optional[LlamaCppEngine] = None
        self._groq: Optional[GroqEngine] = None

    def _is_online(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("8.8.8.8", 53))
            s.close()
            return True
        except Exception:
            return False

    def generate_response(self, system_prompt: str, user_input: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        if self._is_online() and (os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")):
            try:
                if self._groq is None:
                    self._groq = GroqEngine()
                return self._groq.generate(system_prompt, user_input, max_tokens, temperature)
            except Exception as e:
                print(f"[LLM Bridge] Cloud failed ({e}), falling back to offline Qwen 3B...")

        if self._local is None:
            self._local = LlamaCppEngine(model_filename=self.model_filename, n_ctx=self.n_ctx, n_threads=self.n_threads)
        return self._local.generate(system_prompt, user_input, max_tokens, temperature)


LlamaCppBridge = HybridLLMBridge
`
  },
  {
    filename: 'curiosity.py',
    path: 'core/autonomy/curiosity.py',
    category: 'autonomy',
    description: 'Subconscious Autonomous Curiosity Engine proposing goal candidates and knowledge gap verifications.',
    code: `# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any, Dict, List


class Curiosity:
    """
    Subconscious Cognitive Drive:
    Proposes non-executing self-learning candidates from internal uncertainty,
    stalled goals, and unverified knowledge engrams.
    """

    def __init__(self, min_confidence: float = 0.55, max_candidates: int = 5):
        self.min_confidence = min_confidence
        self.max_candidates = max_candidates

    def candidates(
        self,
        state: Any = None,
        goals: List[Dict[str, Any]] = None,
        knowledge_gaps: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        goals = goals or []
        knowledge_gaps = knowledge_gaps or []
        found: List[Dict[str, Any]] = []

        # 1. State uncertainty check
        unc = getattr(state, "uncertainty", 0.0) if state else 0.0
        if unc > 0.6:
            found.append({
                "type": "reduce_uncertainty",
                "reason": f"Internal cognitive uncertainty elevated ({unc:.2f}).",
                "priority": min(1.0, unc),
            })

        # 2. Stalled goals inspection
        now = time.time()
        for g in goals:
            if g.get("status") in ("pending", "active"):
                age = (now - g.get("created_at", now)) / 3600.0
                if age > 4:
                    found.append({
                        "type": "revisit_stalled_goal",
                        "reason": f"Goal '{g.get('text')}' pending for {age:.1f} hours.",
                        "priority": 0.6,
                        "goal_id": g.get("id"),
                    })

        # 3. Knowledge gap verification
        for item in knowledge_gaps:
            conf = item.get("confidence", 1.0)
            if conf < self.min_confidence:
                found.append({
                    "type": "verify_knowledge",
                    "reason": f"Low confidence knowledge node for '{item.get('subject')}' ({conf:.2f}).",
                    "priority": 1.0 - conf,
                    "knowledge_id": item.get("knowledge_id"),
                })

        found.sort(key=lambda c: -c["priority"])
        return found[:self.max_candidates]
`
  },
  {
    filename: 'download.sh',
    path: 'download.sh',
    category: 'scripts',
    description: 'Shell script to download the ONNX Embedding Model, Tokenizer, and Qwen 2.5 3B Instruct Q4_K_M GGUF model.',
    code: `#!/usr/bin/env bash
# ==============================================================================
# JARVIS ORGANISM - MODEL DOWNLOADER SCRIPT (Android 8GB RAM / PRoot Ready)
# ==============================================================================
set -euo pipefail

mkdir -p models database

echo ">>> [1/3] Downloading Fast ONNX Embedding Model (~45 MB)..."
curl -L --progress-bar -o "all-MiniLM-L6-v2.onnx" "https://huggingface.co/xenova/all-MiniLM-L6-v2/resolve/main/onnx/model.onnx"

echo ">>> [2/3] Downloading Tokenizer Configuration (~700 KB)..."
curl -L --progress-bar -o "tokenizer.json" "https://huggingface.co/xenova/all-MiniLM-L6-v2/resolve/main/tokenizer.json"

echo ">>> [3/3] Downloading Qwen2.5-3B-Instruct (Q4_K_M Quantized GGUF ~1.9 GB)..."
curl -L --progress-bar -o "models/qwen2.5-3b-instruct-q4_k_m.gguf" "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"

echo "=========================================================================="
echo "✔ All Models Downloaded Successfully! Run 'python cli.py' to wake JARVIS."
echo "=========================================================================="
`
  },
  {
    filename: 'cli.py',
    path: 'cli.py',
    category: 'core',
    description: 'Main CLI runner with live hot-reloader, rich terminal diagnostics, and heartbeat synchronizer.',
    code: `# -*- coding: utf-8 -*-
import os
import sys
import time
import threading
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

from core.organism.bootstrap import start_jarvis, stop_jarvis
from core.orchestration.llm_bridge import LlamaCppBridge

console = Console()

def main():
    console.print(Panel.fit("[bold cyan]JARVIS COGNITIVE OS v2026.4[/bold cyan]\\n[dim]Android 8GB RAM Cognitive Unit[/dim]", border_style="cyan"))
    
    jarvis = start_jarvis(heartbeat_interval=2.0, idle_threshold=10.0)
    brain = jarvis.get_organ("brain")
    if brain:
        brain.llm = LlamaCppBridge(model_filename="qwen2.5-3b-instruct-q4_k_m.gguf", n_threads=4, n_ctx=4096)
        console.print("[bold green]✔ Neural Bridge Online (Qwen2.5-3B-Instruct).[/bold green]\\n")

    try:
        while True:
            try:
                user_input = console.input("[bold cyan]UK > [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break

            reply = brain.think_and_respond(user_input, source="cli")
            console.print(Panel(f"[white]{reply}[/white]", title="[bold green]JARVIS Response[/bold green]", border_style="cyan"))
    finally:
        stop_jarvis(jarvis)
        console.print("[dim]JARVIS System Offline.[/dim]")

if __name__ == "__main__":
    main()
`
  }
];
