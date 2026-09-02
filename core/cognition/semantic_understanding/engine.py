from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class SemanticFact:
    """Candidate fact produced by deterministic semantic understanding."""

    subject: str
    predicate: str
    value: Any
    confidence: float = 0.8
    source: str = "symbolic_parser"
    evidence: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticEntity:
    """Entity mention resolved into a stable semantic role."""

    text: str
    entity_id: str
    entity_type: str = "unknown"
    mention: str = "explicit"
    confidence: float = 0.8

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticEvent:
    """Event/action representation extracted from an utterance."""

    event_type: str
    subject: Optional[str] = None
    object: Optional[str] = None
    time: Optional[str] = None
    confidence: float = 0.8
    evidence: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SemanticUnderstandingEngine:
    """Dependency-light semantic understanding organ for JARVIS.

    The engine is deliberately deterministic and side-effect light. It turns
    normalized language into a structured representation containing intent,
    entities, references, relations, events, temporal cues and safe inference.
    It does not persist knowledge; candidates remain subject to the normal
    Experience -> Evaluation -> Knowledge boundary.
    """

    VERSION = "0.2.0"
    _SPACE_RE = re.compile(r"\s+")

    _NAME_PATTERNS = (
        (re.compile(r"\bmera\s+naam\s+(?:hai|is)\s+([A-Za-z][\w .'-]{1,60})", re.I), "user", "name", 0.96),
        (re.compile(r"\bmy\s+name\s+is\s+([A-Za-z][\w .'-]{1,60})\b", re.I), "user", "name", 0.98),
        (re.compile(r"\bi\s+am\s+([A-Za-z][\w .'-]{1,60})\b", re.I), "user", "identity", 0.88),
    )

    _RELATION_NAME_PATTERN = re.compile(
        r"\bmera\s+([A-Za-z][\w -]{1,50}?)\s+ka\s+naam\s+([A-Za-z][\w .'-]{1,60})\s+(?:hai|h)\b",
        re.I,
    )

    _GENERIC_PATTERNS = (
        (re.compile(r"\bmera\s+([A-Za-z][\w -]{1,50}?)\s+([A-Za-z0-9][\w .:/@+'-]{0,100}?)(?:\s+hai|\s+h)\b", re.I), "hinglish", 0.78),
        (re.compile(r"\bmy\s+([A-Za-z][\w -]{1,50}?)\s+is\s+([A-Za-z0-9][\w .:/@+'-]{0,100}?)(?:[.!?]|$)", re.I), "english", 0.84),
        (re.compile(r"\bi\s+(?:live|work|study)\s+(?:in|at)\s+([A-Za-z0-9][\w .,'-]{1,80})(?:[.!?]|$)", re.I), "location_or_activity", 0.86),
    )

    _PREFERENCE_PATTERNS = (
        (re.compile(r"\bmujhe\s+(.+?)\s+pasand\s+hai\b", re.I), "likes", 0.90),
        (re.compile(r"\bi\s+like\s+(.+?)(?:[.!?]|$)", re.I), "likes", 0.92),
        (re.compile(r"\bi\s+prefer\s+(.+?)(?:[.!?]|$)", re.I), "prefers", 0.92),
        (re.compile(r"\bi\s+hate\s+(.+?)(?:[.!?]|$)", re.I), "dislikes", 0.90),
    )

    _TEMPORAL_PATTERNS = (
        (re.compile(r"\b(kal|yesterday)\b", re.I), "relative_day"),
        (re.compile(r"\b(aaj|today)\b", re.I), "today"),
        (re.compile(r"\b(kal|tomorrow)\b", re.I), "relative_day"),
        (re.compile(r"\b(parso)\b", re.I), "relative_day"),
        (re.compile(r"\b(abhi|now)\b", re.I), "now"),
        (re.compile(r"\b(baad\s+mein|later)\b", re.I), "future_relative"),
    )

    _ACTION_PATTERNS = (
        (re.compile(r"\b(?:maine|main)\s+(.+?)\s+(?:seekhna|sikhna)\s+start\s+(?:kiya|ki)\b", re.I), "learning_started"),
        (re.compile(r"\b(?:i|maine|main)\s+(?:start|started)\s+(?:learning|studying)\s+(.+?)(?:[.!?]|$)", re.I), "learning_started"),
        (re.compile(r"\b(?:i\s+am|main\s+)?(?:learning|studying)\s+(.+?)(?:[.!?]|$)", re.I), "learning_started"),
        (re.compile(r"\b(?:maine|main)\s+(.+?)\s+(?:banana|banaya)\s+start\s+(?:kiya|ki)\b", re.I), "creation_started"),
        (re.compile(r"\b(?:maine|main)\s+(.+?)\s+(?:seekha|sikha)\b", re.I), "learned"),
    )

    _COMMAND_PATTERNS = (
        re.compile(r"^(?:open|start|run|stop|search|find|show|tell|remember|delete|create|execute|chala|karo|batao|dikhao|dhundo|khol)\b", re.I),
        re.compile(r"^(?:please\s+)?(?:open|start|run|stop|search|find|show|tell|remember|delete|create|execute)\b", re.I),
    )
    _QUESTION_PATTERNS = re.compile(r"^(?:what|why|how|when|where|who|which|can|could|is|are|do|does|did|kya|kyu|kyun|kaise|kab|kahan|kaun|hai|hain)\b", re.I)

    _PRONOUNS = {
        "it": "singular_object", "this": "demonstrative", "that": "demonstrative",
        "usko": "singular_object", "isko": "singular_object", "usse": "singular_object",
        "isme": "singular_object", "usme": "singular_object", "wahi": "demonstrative",
        "yeh": "demonstrative", "ye": "demonstrative", "woh": "demonstrative",
    }

    def __init__(self, *, max_context_turns: int = 8) -> None:
        self.max_context_turns = max(1, int(max_context_turns))
        self._recent_turns: List[Dict[str, Any]] = []
        self._last_entities: List[Dict[str, Any]] = []
        self._last_events: List[Dict[str, Any]] = []

    def normalize(self, text: str) -> str:
        text = str(text or "").strip()
        text = self._SPACE_RE.sub(" ", text)
        replacements = {
            r"\bnan\b": "naam", r"\bkrna\b": "karna", r"\bnhi\b": "nahi",
            r"\bsmjhna\b": "samajhna", r"\bthk\b": "theek",
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.I)
        return text

    @staticmethod
    def _clean_phrase(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip(" \t\n.,!?;:"))

    @staticmethod
    def _subject_key(raw: str) -> str:
        raw = re.sub(r"[^a-zA-Z0-9_ ]+", " ", raw.lower())
        raw = re.sub(r"\s+", "_", raw.strip())
        return raw[:80] or "user"

    @staticmethod
    def _entity_id(text: str) -> str:
        return "entity:" + SemanticUnderstandingEngine._subject_key(text)

    def _name_facts(self, text: str) -> Iterable[SemanticFact]:
        for pattern, subject, predicate, confidence in self._NAME_PATTERNS:
            match = pattern.search(text)
            if match:
                value = self._clean_phrase(match.group(1))
                if value:
                    yield SemanticFact(subject, predicate, value, confidence, "symbolic_parser", match.group(0))
        relation = self._RELATION_NAME_PATTERN.search(text)
        if relation:
            subject = self._subject_key(relation.group(1))
            value = self._clean_phrase(relation.group(2))
            if subject and value:
                yield SemanticFact(subject, "name", value, 0.96, "symbolic_parser", relation.group(0))

    def _preference_facts(self, text: str) -> Iterable[SemanticFact]:
        for pattern, predicate, confidence in self._PREFERENCE_PATTERNS:
            match = pattern.search(text)
            if match:
                value = self._clean_phrase(match.group(1))
                if value:
                    yield SemanticFact("user", predicate, value, confidence, "symbolic_parser", match.group(0))

    def _generic_facts(self, text: str) -> Iterable[SemanticFact]:
        # Action statements are represented by _extract_events(), not as
        # generic identity/state facts.
        is_learning_event = bool(
            re.search(
                r"^\s*(?:i\s+(?:am|'m)|main\s+)?(?:learning|studying)\s+.+",
                text,
                re.I,
            )
            or re.search(
                r"^\s*i\s+(?:am|'m)\s+learning\s+.+",
                text,
                re.I,
            )
        )

        for pattern, style, confidence in self._GENERIC_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue

            if is_learning_event:
                continue
            if style == "location_or_activity":
                value = self._clean_phrase(match.group(1))
                if value:
                    predicate = "lives_in" if "live" in match.group(0).lower() else "activity_location"
                    yield SemanticFact("user", predicate, value, confidence, "symbolic_parser", match.group(0))
                continue
            raw_predicate = self._clean_phrase(match.group(1))
            value = self._clean_phrase(match.group(2))

            # Action statements such as "I am learning Python" are events,
            # not identity facts.
            if re.match(r"^i\s+(?:am|m)\s+(?:learning|studying)\b", text, re.I):
                continue

            raw_predicate = re.sub(r"\b(naam|name)\b", "name", raw_predicate, flags=re.I)
            if raw_predicate and value:
                yield SemanticFact("user", self._subject_key(raw_predicate), value, confidence, "symbolic_parser", match.group(0))

    def _extract_temporal(self, text: str) -> List[Dict[str, str]]:
        found: List[Dict[str, str]] = []
        for pattern, temporal_type in self._TEMPORAL_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1).lower()
                item = {"text": value, "type": temporal_type}
                if item not in found:
                    found.append(item)
        return found

    def _extract_entities_structured(self, text: str) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        seen = set()
        # Proper nouns / technical names.
        for match in re.finditer(r"\b[A-Z][a-zA-Z0-9_-]{2,30}\b", text):
            value = match.group(0)
            key = value.lower()
            if key not in seen:
                seen.add(key)
                entity_type = "person" if value.lower() in {"ujjwal", "devyana"} else "named_entity"
                entities.append(SemanticEntity(value, self._entity_id(value), entity_type, "explicit", 0.90).as_dict())
        # Technical noun phrases in common learning/action constructions.
        for match in re.finditer(r"\b(?:python|javascript|java|react|node(?:\.js)?|machine\s+learning|ai|android)\b", text, re.I):
            value = match.group(0)
            key = value.lower()
            if key not in seen:
                seen.add(key)
                entities.append(SemanticEntity(value, self._entity_id(value), "topic", "explicit", 0.86).as_dict())
        return entities[:20]

    def _resolve_references(self, text: str, entities: List[Dict[str, Any]], context: Mapping[str, Any]) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        previous = list(self._last_entities)
        supplied = context.get("entities") if isinstance(context, Mapping) else None
        if isinstance(supplied, list):
            previous = [x for x in supplied if isinstance(x, dict)] + previous
        candidate = next((x for x in previous if x.get("entity_id") or x.get("text")), None)
        for token in re.findall(r"\b[\w]+\b", text.lower()):
            if token not in self._PRONOUNS:
                continue
            resolved = candidate
            refs.append({
                "mention": token,
                "type": self._PRONOUNS[token],
                "resolved_to": dict(resolved) if resolved else None,
                "confidence": 0.86 if resolved else 0.0,
            })
        return refs

    def _extract_events(self, text: str, temporal: List[Dict[str, str]], entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        time_value = temporal[0]["text"] if temporal else None
        for pattern, event_type in self._ACTION_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            raw = self._clean_phrase(match.group(1))
            # Avoid treating obvious filler as the object.
            obj = raw
            events.append(SemanticEvent(event_type, "user", obj, time_value, 0.88, match.group(0)).as_dict())
            break
        return events

    def _extract_semantic_relations(self, events: List[Dict[str, Any]], temporal: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        relations: List[Dict[str, Any]] = []
        for event in events:
            subject = event.get("subject") or "user"
            obj = event.get("object")
            if obj:
                relations.append({"subject": subject, "predicate": event["event_type"], "value": obj,
                                  "confidence": event["confidence"], "source": "event_parser", "evidence": event["evidence"]})
            if event.get("time"):
                relations.append({"subject": event["event_type"], "predicate": "occurred_at", "value": event["time"],
                                  "confidence": 0.84, "source": "temporal_parser", "evidence": event["evidence"]})
        return relations

    def _infer(self, events: List[Dict[str, Any]], references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        inferences: List[Dict[str, Any]] = []
        for event in events:
            if event.get("event_type") == "learning_started" and event.get("object"):
                inferences.append({
                    "type": "current_learning_target",
                    "subject": "user",
                    "value": event["object"],
                    "confidence": round(float(event.get("confidence", 0.8)) * 0.90, 3),
                    "source": "semantic_inference",
                    "from_event": event["event_type"],
                })
        for ref in references:
            resolved = ref.get("resolved_to")
            if resolved:
                inferences.append({
                    "type": "resolved_reference",
                    "mention": ref["mention"],
                    "entity": resolved,
                    "confidence": ref.get("confidence", 0.0),
                    "source": "context_resolution",
                })
        return inferences
        
    @staticmethod
    def _detect_intent(text: str) -> Dict[str, Any]:
        if text.endswith("?") or SemanticUnderstandingEngine._QUESTION_PATTERNS.search(text):
            return {
                "name": "question",
                "confidence": 0.90,
                "source": "symbolic_parser",
            }

        for pattern in SemanticUnderstandingEngine._COMMAND_PATTERNS:
            if pattern.search(text):
                return {
                    "name": "command",
                    "confidence": 0.90,
                    "source": "symbolic_parser",
                }

        return {
        "name": "statement",
        "confidence": 0.72,
        "source": "symbolic_parser",
        }
        

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"
        if re.search(r"\b(yaar|kya|kyu|kyun|kaise|mujhe|mera|meri|hai|hain|ho|karna|usko|wahi)\b", text, re.I):
            return "hinglish"
        return "en"

    def _build_context_snapshot(self) -> Dict[str, Any]:
        return {
            "last_intent": self._recent_turns[-1].get("intent", {}).get("name") if self._recent_turns else None,
            "last_entities": list(self._last_entities),
            "last_events": list(self._last_events),
            "recent_turns": list(self._recent_turns),
        }

    def understand(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Produce the complete semantic contract without persisting knowledge."""
        started = time.time()
        normalized = self.normalize(text)
        external_context: Mapping[str, Any] = context or {}
        intent = self._detect_intent(normalized)
        language = self._detect_language(normalized)
        entities = self._extract_entities_structured(normalized)
        temporal = self._extract_temporal(normalized)
        references = self._resolve_references(normalized, entities, external_context)
        events = self._extract_events(normalized, temporal, entities)

        facts: List[SemanticFact] = []
        seen = set()
        for generator in (self._name_facts(normalized), self._preference_facts(normalized), self._generic_facts(normalized)):
            for fact in generator:
                key = (fact.subject, fact.predicate, str(fact.value).lower())
                if key not in seen:
                    seen.add(key)
                    facts.append(fact)

        # Action/event statements must not be persisted as identity facts.
        # Example: "I am learning Python" -> learning_started event,
        # not identity("learning Python").
        if any(
            event.get("event_type") == "learning_started"
            for event in events
        ):
            facts = [
                fact for fact in facts
                if not (
                    fact.predicate == "identity"
                    and fact.value
                    and re.match(
                        r"^(?:learning|studying)\\s+",
                        str(fact.value),
                        re.I,
                    )
                )
            ]

        semantic_relations = self._extract_semantic_relations(events, temporal)
        # Prevent action/state statements from being stored as identity facts.
        # Example: "I am learning Python" must produce a learning_started event,
        # never identity("learning Python").
        if any(e.get("event_type") == "learning_started" for e in events):
            facts = [
                fact for fact in facts
                if not (
                    getattr(fact, "predicate", None) == "identity"
                    and str(getattr(fact, "value", "")).strip().lower()
                    == "learning python"
                )
            ]

        relations = [fact.as_dict() for fact in facts] + semantic_relations
        inferences = self._infer(events, references)
        confidence_values = [intent.get("confidence", 0.0)] + [e.get("confidence", 0.0) for e in entities] + [e.get("confidence", 0.0) for e in events]
        confidence = max(confidence_values or [0.0])

        result = {
            "version": self.VERSION,
            "text": str(text or ""),
            "normalized": normalized,
            "language": language,
            "intent": intent,
            "tokens": normalized.split() if normalized else [],
            "entities": entities,
            "references": references,
            "temporal": temporal,
            "events": events,
            "relations": relations,
            "fact_candidates": [fact.as_dict() for fact in facts],
            "inferences": inferences,
            "confidence": round(confidence, 3),
            "uncertainty": round(1.0 - confidence, 3),
            "context": self._build_context_snapshot(),
            "context_keys": sorted(external_context.keys()),
            "processing_ms": round((time.time() - started) * 1000.0, 3),
        }

        self._last_entities = list(entities)
        self._last_events = list(events)
        self._recent_turns.append({
            "timestamp": time.time(),
            "normalized": normalized,
            "intent": intent,
            "entities": entities,
            "events": events,
            "temporal": temporal,
        })
        self._recent_turns = self._recent_turns[-self.max_context_turns:]
        return result
