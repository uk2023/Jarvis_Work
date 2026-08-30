from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol


@dataclass
class PerceptionResult:
    raw_input: str
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    goal: Optional[Any] = None
    confidence: float = 0.0
    uncertainty: Optional[str] = None
    source: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class PerceptionProvider(Protocol):
    def perceive(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> PerceptionResult:
        ...


class PerceptionEngine:
    def __init__(self, provider: Optional[PerceptionProvider] = None):
        self.provider = provider

    def set_provider(self, provider: Optional[PerceptionProvider]) -> None:
        self.provider = provider

    def perceive(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> PerceptionResult:
        if not isinstance(user_input, str):
            raise TypeError("user_input must be a string")
        if not user_input.strip():
            return PerceptionResult(raw_input=user_input, uncertainty="empty_input", source="native")
        if self.provider is None:
            return PerceptionResult(raw_input=user_input, uncertainty="no_perception_provider", source="native")
        result = self.provider.perceive(user_input, context or {})
        if not isinstance(result, PerceptionResult):
            raise TypeError("PerceptionProvider must return PerceptionResult")
        return result
