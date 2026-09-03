from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol

from ..contracts import validate_output


@dataclass(frozen=True)
class PerceptionResult:
    """Stable machine-readable meaning passed from perception to Brain/router."""
    user_input: str
    normalized_text: str
    intent: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    goal: Optional[Any] = None
    requested_capability: Optional[str] = None
    speech_act: Optional[str] = None
    language: Optional[str] = None
    confidence: float = 0.0
    uncertainty: float = 1.0
    source: str = "unknown"
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    def as_contract_payload(self) -> Dict[str, Any]:
        """Return the canonical Perception output contract."""
        entities = self.entities
        if isinstance(entities, dict):
            entities = [entities] if entities else []
        elif not isinstance(entities, list):
            entities = []

        return validate_output(
            "perception",
            {
                "normalized_input": self.normalized_text,
                "language": self.language or "unknown",
                "confidence": float(self.confidence),
                "basic_intent": self.intent,
                "entities": entities,
                "metadata": {
                    "source": self.source,
                    "uncertainty": float(self.uncertainty),
                    "goal": self.goal,
                    "requested_capability": self.requested_capability,
                    "speech_act": self.speech_act,
                    "reason": self.reason,
                },
            },
        )


class PerceptionProvider(Protocol):
    """Replaceable provider; LLM is only one possible implementation."""
    name: str

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        ...


class NativePerceptionProvider:
    """Deterministic Level-0 perception (blueprint section 4: LEVEL 0 —
    deterministic normalization, tried before any LLM/SLM escalation).

    Handles a small set of unambiguous conversational patterns (greetings,
    status checks, thanks, farewells) without any LLM call. Returns None
    for anything it doesn't confidently recognize, so PerceptionEngine
    falls through to the next provider (LLM) -- this is a genuine
    escalation cascade, not a replacement for LLM perception.
    """
    name = "native"

    _PATTERNS: tuple = (
        ("greeting", re.compile(r"^(hi|hello|hey|hlo|yo|namaste|namaskar)\b", re.I)),
        ("status_check", re.compile(r"^(status|health|ping|are you (online|there|up)|you there)\b", re.I)),
        ("thanks", re.compile(r"^(thanks|thank you|shukriya|dhanyavad)\b", re.I)),
        ("farewell", re.compile(r"^(bye|goodbye|see you|tata|good night)\b", re.I)),
    )

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> Optional[PerceptionResult]:
        normalized = (user_input or "").strip()
        if not normalized:
            return None
        for intent_name, pattern in self._PATTERNS:
            if pattern.match(normalized):
                return PerceptionResult(
                    user_input=user_input,
                    normalized_text=normalized,
                    intent={"name": intent_name, "confidence": 0.95},
                    language="unknown",
                    confidence=0.95,
                    uncertainty=0.05,
                    source=self.name,
                    reason=f"Matched deterministic pattern: {intent_name}",
                )
        return None


class LLMPerceptionProvider:
    """Temporary LLM-backed perception provider while native cognition matures."""
    name = "llm"

    SYSTEM_PROMPT = (
        "Convert a user's message into one structured perception. "
        "Return ONLY valid JSON. Never answer the user and never invent facts. "
        "Use an empty intent name and low confidence when meaning is unclear. "
        "Required keys: intent, entities, goal, requested_capability, "
        "speech_act, language, confidence, reason."
    )

    # Retrieval-based context bound (blueprint Phase 4): perception runs
    # on every single turn, so an unbounded context dict here means every
    # message -- including a bare "hello" -- pays for the full memory/
    # knowledge/graph payload. Cap item count and per-item length before
    # the dict is ever stringified into the prompt, rather than relying
    # solely on the downstream token budgeter (whose word-count estimate
    # can diverge from the real byte size of dense/structured content).
    _CONTEXT_MAX_ITEMS = 3
    _CONTEXT_MAX_ITEM_CHARS = 150

    def __init__(self, llm_bridge: Any):
        self.llm = llm_bridge

    @classmethod
    def _bounded_context(cls, context: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        if not context:
            return {}
        bounded: Dict[str, Any] = {}
        for key, value in dict(context).items():
            if isinstance(value, (list, tuple)):
                items = []
                for item in list(value)[: cls._CONTEXT_MAX_ITEMS]:
                    text = str(item)
                    if len(text) > cls._CONTEXT_MAX_ITEM_CHARS:
                        text = text[: cls._CONTEXT_MAX_ITEM_CHARS] + "…"
                    items.append(text)
                bounded[key] = items
            else:
                text = str(value)
                if len(text) > cls._CONTEXT_MAX_ITEM_CHARS:
                    text = text[: cls._CONTEXT_MAX_ITEM_CHARS] + "…"
                bounded[key] = text
        return bounded

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        prompt = (
            f"User message: {user_input}\n"
            f"Context: {self._bounded_context(context)}\n"
            'JSON shape: {"intent":{"name":"...","confidence":0.0},'
            '"entities":{},"goal":null,"requested_capability":null,'
            '"speech_act":null,"language":"...","confidence":0.0,"reason":"..."}'
        )
        raw = self.llm.generate_response(
            system_prompt=self.SYSTEM_PROMPT,
            user_input=prompt,
            max_tokens=300,
            temperature=0.0,
        )
        cleaned = re.sub(r"^```(?:json)?|```$", "", str(raw).strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except Exception as exc:
            return PerceptionResult(user_input, user_input, source=self.name, reason=f"invalid provider JSON: {exc}")

        intent = data.get("intent") if isinstance(data.get("intent"), dict) else {}
        confidence = float(data.get("confidence", intent.get("confidence", 0.0)) or 0.0)
        confidence = max(0.0, min(1.0, confidence))
        return PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            intent=intent,
            entities=data.get("entities") if isinstance(data.get("entities"), dict) else {},
            goal=data.get("goal"),
            requested_capability=data.get("requested_capability"),
            speech_act=data.get("speech_act"),
            language=data.get("language"),
            confidence=confidence,
            uncertainty=1.0 - confidence,
            source=self.name,
            reason=str(data.get("reason", "LLM structured perception")),
        )


class PerceptionEngine:
    """Provider-agnostic perception organ with explicit provider ordering."""
    VERSION = "0.3.0"

    def __init__(self, providers=None, state=None):
        self.providers = list(providers or [])
        self.state = state
        self.last_result: Optional[PerceptionResult] = None
        self.last_contract: Optional[Dict[str, Any]] = None

    def add_provider(self, provider: PerceptionProvider) -> None:
        self.providers.append(provider)

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        for provider in self.providers:
            try:
                result = provider.perceive(user_input, context=context)
                if not isinstance(result, PerceptionResult):
                    continue
                self.last_contract = result.as_contract_payload()
                self.last_result = result
                self._publish_state(result)
                return result
            except Exception:
                continue

        result = PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            language="unknown",
            source="none",
            reason="No perception provider produced a result.",
        )
        self.last_contract = result.as_contract_payload()
        self.last_result = result
        self._publish_state(result)
        return result

    def _publish_state(self, result: PerceptionResult) -> None:
        if self.state is None:
            return
        try:
            self.state.update(last_perception=result.as_dict())
        except Exception:
            pass
