from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SemanticFact:
    """A candidate semantic triple produced without an LLM call."""

    subject: str
    predicate: str
    value: Any
    confidence: float = 0.8
    source: str = "symbolic_parser"
    evidence: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SemanticUnderstandingEngine:
    """Small neuro-symbolic bootstrap layer for JARVIS.

    The current implementation deliberately uses deterministic symbolic
    rules. It is a substrate, not a replacement for the locked cognitive
    architecture. Later neural encoders/entity-linkers can be plugged into
    the same `understand()` contract without changing Brain boundaries.
    """

    VERSION = "0.1.0"

    _SPACE_RE = re.compile(r"\s+")
    _NAME_PATTERNS = (
        (re.compile(r"\b(?:mera|my)\s+naam\s+(?:hai|is)\s+([A-Za-z][\w .'-]{1,60})", re.I), "user", "name", 0.96),
        (re.compile(r"\bmy\s+name\s+is\s+([A-Za-z][\w .'-]{1,60})\b", re.I), "user", "name", 0.98),
        (re.compile(r"\bi\s+am\s+([A-Za-z][\w .'-]{1,60})\b", re.I), "user", "identity", 0.88),
    )

    _GENERIC_PATTERNS = (
        (re.compile(r"\bmera\s+([A-Za-z][\w -]{1,50}?)\s+(?:hai|h)\s+([A-Za-z0-9][\w .:/@+'-]{0,100})", re.I), "hinglish", 0.78),
        (re.compile(r"\bmy\s+([A-Za-z][\w -]{1,50}?)\s+is\s+([A-Za-z0-9][\w .:/@+'-]{0,100})", re.I), "english", 0.84),
        (re.compile(r"\bi\s+(?:live|work|study)\s+(?:in|at)\s+([A-Za-z0-9][\w .,'-]{1,80})", re.I), "location_or_activity", 0.86),
    )

    _PREFERENCE_PATTERNS = (
        (re.compile(r"\bmujhe\s+(.+?)\s+pasand\s+hai\b", re.I), "likes", 0.90),
        (re.compile(r"\bi\s+like\s+(.+?)(?:[.!?]|$)", re.I), "likes", 0.92),
        (re.compile(r"\bi\s+prefer\s+(.+?)(?:[.!?]|$)", re.I), "prefers", 0.92),
        (re.compile(r"\bi\s+hate\s+(.+?)(?:[.!?]|$)", re.I), "dislikes", 0.90),
    )

    _STOP_VALUE = re.compile(r"(?:\s+(?:hai|h|is|and|aur)\s*)$", re.I)

    def normalize(self, text: str) -> str:
        text = str(text or "").strip()
        text = self._SPACE_RE.sub(" ", text)
        replacements = {
            "\bnan\b": "naam",
            "\bkrna\b": "karna",
            "\bnhi\b": "nahi",
            "\bsmjhna\b": "samajhna",
            "\bthk\b": "theek",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.I)
        return text

    @staticmethod
    def _clean_phrase(value: str) -> str:
        value = str(value or "").strip(" \t\n.,!?;:")
        value = re.sub(r"\s+", " ", value)
        return value

    @staticmethod
    def _subject_key(raw: str) -> str:
        raw = re.sub(r"[^a-zA-Z0-9_ ]+", " ", raw.lower())
        raw = re.sub(r"\s+", "_", raw.strip())
        return raw[:80] or "user"

    def _name_facts(self, text: str) -> Iterable[SemanticFact]:
        for pattern, subject, predicate, confidence in self._NAME_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            value = self._clean_phrase(match.group(1))
            if value:
                yield SemanticFact(subject, predicate, value, confidence, "symbolic_parser", match.group(0))

    def _preference_facts(self, text: str) -> Iterable[SemanticFact]:
        for pattern, predicate, confidence in self._PREFERENCE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            value = self._clean_phrase(match.group(1))
            if value:
                yield SemanticFact("user", predicate, value, confidence, "symbolic_parser", match.group(0))

    def _generic_facts(self, text: str) -> Iterable[SemanticFact]:
        for pattern, style, confidence in self._GENERIC_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            if style == "location_or_activity":
                value = self._clean_phrase(match.group(1))
                if value:
                    predicate = "lives_in" if "live" in match.group(0).lower() else "activity_location"
                    yield SemanticFact("user", predicate, value, confidence, "symbolic_parser", match.group(0))
                continue
            raw_predicate = self._clean_phrase(match.group(1))
            value = self._clean_phrase(match.group(2))
            raw_predicate = re.sub(r"\b(naam|name)\b", "name", raw_predicate, flags=re.I)
            if raw_predicate and value:
                yield SemanticFact("user", self._subject_key(raw_predicate), value, confidence, "symbolic_parser", match.group(0))

    def understand(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return structured meaning suitable for Cognition/Retrieval.

        No persistence occurs here. Facts remain candidates until the normal
        Experience -> SelfEvaluator -> KnowledgeBuilder boundary accepts them.
        """
        normalized = self.normalize(text)
        facts: List[SemanticFact] = []
        seen = set()

        for fact in (*self._name_facts(normalized), *self._preference_facts(normalized), *self._generic_facts(normalized)):
            key = (fact.subject, fact.predicate, str(fact.value).lower())
            if key not in seen:
                seen.add(key)
                facts.append(fact)

        entities = self._extract_entities(normalized)
        relations = [fact.as_dict() for fact in facts]
        return {
            "version": self.VERSION,
            "normalized": normalized,
            "entities": entities,
            "relations": relations,
            "fact_candidates": relations,
            "confidence": max((f.confidence for f in facts), default=0.0),
            "context_keys": sorted((context or {}).keys()),
        }

    @staticmethod
    def _extract_entities(text: str) -> List[str]:
        entities: List[str] = []
        for match in re.findall(r"\b[A-Z][a-zA-Z0-9_-]{2,30}\b", text):
            if match not in entities:
                entities.append(match)
        return entities[:20]
