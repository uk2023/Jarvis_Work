from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


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


class PerceptionProvider(Protocol):
    """Replaceable provider; LLM is only one possible implementation."""
    name: str

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        ...


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

    def __init__(self, llm_bridge: Any):
        self.llm = llm_bridge

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        prompt = (
            f"User message: {user_input}\n"
            f"Context: {dict(context or {})}\n"
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
    VERSION = "0.2.0"

    def __init__(self, providers=None, state=None):
        self.providers = list(providers or [])
        self.state = state
        self.last_result: Optional[PerceptionResult] = None

    def add_provider(self, provider: PerceptionProvider) -> None:
        self.providers.append(provider)

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        for provider in self.providers:
            try:
                result = provider.perceive(user_input, context=context)
                if not isinstance(result, PerceptionResult):
                    continue
                self.last_result = result
                self._publish_state(result)
                return result
            except Exception:
                continue

        result = PerceptionResult(
            user_input=user_input,
            normalized_text=user_input,
            source="none",
            reason="No perception provider produced a result.",
        )
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
