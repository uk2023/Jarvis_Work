"""Controlled self-evolution boundary for Semantic Understanding."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

LLMFallback = Callable[[Dict[str, Any]], Mapping[str, Any]]


def _tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[\w]+", str(text or "").lower()) if len(w) > 1)


@dataclass
class SemanticLearningCandidate:
    candidate_id: str
    input_text: str
    semantic: Dict[str, Any]
    source: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    status: str = "CANDIDATE"
    created_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.candidate_id,
            "type": "SEMANTIC_LEARNING_CANDIDATE",
            "input_text": self.input_text,
            "semantic": dict(self.semantic),
            "source": self.source,
            "confidence": self.confidence,
            "evidence": dict(self.evidence),
            "status": self.status,
            "created_at": self.created_at,
        }


class LearnedSemanticRegistry:
    """Promoted semantic capabilities matched from learned data, not regex rules."""

    VERSION = "0.2.0"

    def __init__(self, *, minimum_similarity: float = 0.78) -> None:
        self.minimum_similarity = max(0.0, min(1.0, float(minimum_similarity)))
        self._entries: List[Dict[str, Any]] = []

    @staticmethod
    def _similarity(left: Iterable[str], right: Iterable[str]) -> float:
        a, b = set(left), set(right)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def promote(self, candidate: SemanticLearningCandidate | Mapping[str, Any]) -> Dict[str, Any]:
        data = candidate.as_dict() if isinstance(candidate, SemanticLearningCandidate) else dict(candidate)
        if data.get("status") != "ACCEPTED":
            raise ValueError("Only an ACCEPTED candidate may be promoted")
        semantic = data.get("semantic")
        if not isinstance(semantic, dict):
            raise ValueError("candidate semantic payload must be an object")
        entry = {
            "id": data.get("id") or f"learned:{uuid.uuid4().hex}",
            "signature": sorted(_tokens(data.get("input_text", ""))),
            "semantic": semantic,
            "confidence": float(data.get("confidence", 0.0)),
            "source": data.get("source", "unknown"),
            "created_at": data.get("created_at", time.time()),
        }
        self._entries = [e for e in self._entries if e["id"] != entry["id"]]
        self._entries.append(entry)
        return dict(entry)

    def match(self, text: str) -> Optional[Dict[str, Any]]:
        query = _tokens(text)
        best, best_score = None, 0.0
        for entry in self._entries:
            score = self._similarity(query, entry.get("signature", []))
            if score >= self.minimum_similarity and score > best_score:
                best, best_score = dict(entry), score
                best["similarity"] = score
        return best

    def entries(self) -> List[Dict[str, Any]]:
        return [dict(entry) for entry in self._entries]


class SemanticLearningBoundary:
    """Gate unknown semantic cases through fallback, evaluation and promotion."""

    VERSION = "0.2.0"

    def __init__(self, *, llm_fallback: Optional[LLMFallback] = None,
                 learning_coordinator: Optional[Any] = None,
                 registry: Optional[LearnedSemanticRegistry] = None,
                 native_confidence_threshold: float = 0.72) -> None:
        self.llm_fallback = llm_fallback
        self.learning = learning_coordinator
        self.registry = registry or LearnedSemanticRegistry()
        self.native_confidence_threshold = max(0.0, min(1.0, float(native_confidence_threshold)))
        self.candidates: Dict[str, SemanticLearningCandidate] = {}

    @staticmethod
    def _confidence(result: Mapping[str, Any]) -> float:
        try:
            return max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        except (TypeError, ValueError):
            return 0.0

    def needs_fallback(self, result: Mapping[str, Any]) -> bool:
        unknowns = result.get("unknowns")
        return bool(unknowns) or self._confidence(result) < self.native_confidence_threshold

    def apply_learned_capability(self, text: str) -> Optional[Dict[str, Any]]:
        match = self.registry.match(text)
        if match is None:
            return None
        semantic = dict(match.get("semantic") or {})
        provenance = semantic.get("provenance") if isinstance(semantic.get("provenance"), dict) else {}
        semantic["provenance"] = {
            **provenance,
            "source": "learned_native",
            "registry_version": self.registry.VERSION,
            "similarity": match.get("similarity", 0.0),
            "learned_from": match.get("source"),
        }
        return semantic

    def resolve(self, text: str, native_result: Mapping[str, Any], *,
                context: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        # Existing native understanding remains authoritative when confident.
        if not self.needs_fallback(native_result):
            return {"semantic": dict(native_result), "source": "native", "fallback_used": False, "candidate": None}

        # Learned capability is preferred to asking the LLM again.
        learned = self.apply_learned_capability(text)
        if learned is not None:
            return {"semantic": learned, "source": "learned_native", "fallback_used": False, "candidate": None}

        if self.llm_fallback is None:
            return {"semantic": dict(native_result), "source": "native", "fallback_used": False, "candidate": None}

        request = {
            "text": str(text),
            "native_semantic": dict(native_result),
            "context": dict(context or {}),
            "instruction": "Return only structured semantic meaning; do not invent external facts.",
        }
        raw = self.llm_fallback(request)
        if not isinstance(raw, Mapping):
            raise TypeError("LLM fallback must return a structured mapping")
        semantic = dict(raw.get("semantic", raw))
        if not semantic:
            raise ValueError("LLM fallback returned an empty semantic result")
        candidate = SemanticLearningCandidate(
            candidate_id=f"semantic:{uuid.uuid4().hex}",
            input_text=str(text), semantic=semantic, source="llm_fallback",
            confidence=self._confidence(semantic),
            evidence={"native": dict(native_result), "fallback_request": request},
        )
        self.candidates[candidate.candidate_id] = candidate
        return {"semantic": semantic, "source": "llm_fallback", "fallback_used": True,
                "candidate": candidate.as_dict()}

    def learn(self, candidate_id: str, *, auto_accept: bool = False) -> Dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown semantic learning candidate: {candidate_id}")
        if self.learning is None:
            return {"candidate": candidate.as_dict(), "learning": {"success": True, "accepted": False}}
        experience = {
            "event_type": "SEMANTIC_FALLBACK_INTERPRETATION",
            "context": {"semantic": candidate.semantic, "source": candidate.source},
            "action": {"subject": "semantic_understanding", "predicate": "interpreted"},
            "outcome": {"success": True, "score": candidate.confidence,
                        "subject": "semantic_understanding", "predicate": "interprets",
                        "value": candidate.semantic},
            "semantic_candidate": candidate.as_dict(),
        }
        return {"candidate": candidate.as_dict(),
                "learning": self.learning.learn(experience, auto_accept=auto_accept)}

    def accept_candidate(self, candidate_id: str) -> Dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown semantic learning candidate: {candidate_id}")
        if candidate.status != "CANDIDATE":
            raise ValueError("Only a CANDIDATE may be accepted")
        candidate.status = "ACCEPTED"
        return candidate.as_dict()

    def reject_candidate(self, candidate_id: str, reason: str = "") -> Dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown semantic learning candidate: {candidate_id}")
        if candidate.status != "CANDIDATE":
            raise ValueError("Only a CANDIDATE may be rejected")
        candidate.status = "REJECTED"
        payload = candidate.as_dict()
        payload["rejection_reason"] = str(reason)
        return payload

    def promote(self, candidate_id: str) -> Dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise KeyError(f"Unknown semantic learning candidate: {candidate_id}")
        if candidate.status != "ACCEPTED":
            raise ValueError("Candidate must be explicitly accepted before promotion")
        return self.registry.promote(candidate)
