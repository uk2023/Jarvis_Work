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
        return {
            "user_input": self.user_input,
            "normalized_text": self.normalized_text,
            "intent": self.intent,
            "entities": self.entities,
            "goal": self.goal,
            "requested_capability": self.requested_capability,
            "speech_act": self.speech_act,
            "language": self.language,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "source": self.source,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class PerceptionProvider(Protocol):
    """Provider that converts language into structured perception.

    Providers are replaceable. The Brain/Router never depends on an LLM
    implementation directly; an LLM is simply one possible provider.
    """

    name: str

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        ...


class LLMPerceptionProvider:
    """LLM-backed perception provider used while native cognition matures."""

    name = "llm"

    PROMPT = """Convert the user's message into ONE structured perception.
Return ONLY valid JSON with this shape:
{"intent":{"name":"...","confidence":0.0},"entities":{},"goal":null,"requested_capability":null,"speech_act":null,"language":"...","confidence":0.0,"reason":"..."}
Do not answer the user. Do not invent facts. If meaning is unclear, use an empty intent name and low confidence.
User message: {user_input}
Context: {context}
"""

    def __init__(self, llm_bridge: Any):
        self.llm = llm_bridge

    def perceive(self, user_input: str, context: Optional[Mapping[str, Any]] = None) -> PerceptionResult:
        raw = self.llm.generate_response(
            system_prompt=self.PROMPT,
            user_input=self.PROMPT.format(user_input=user_input, context=dict(context or {})),
            max_tokens=300,
            temperature=0.0,
        )
        cleaned = re.sub(r"^```(?:json)?|```$", "", str(raw).strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except Exception as exc:
            return PerceptionResult(
                user_input=user_input,
                normalized_text=user_input,
                source=self.name,
                reason=f"provider returned invalid JSON: {exc}",
            )

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
    """Provider-agnostic perception organ.

    Provider order is explicit. A provider failure never becomes an invented
    intent. The engine returns low-confidence perception so the Router can
    safely choose the LLM/clarification path.
    """

    VERSION = "0.1.0"

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
                if self.state is not None:
                    try:
                        self.state.update(last_perception=result.as_dict())
                    except Exception:
                        pass
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
        if self.state is not None:
            try:
                self.state.update(last_perception=result.as_dict())
            except Exception:
                pass
        return result
