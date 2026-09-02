"""M3.3 full semantic evolution cycle orchestration."""

from __future__ import annotations

from typing import Any, Dict

from .knowledge_promotion import SemanticKnowledgePromotion
from .learning_boundary import SemanticLearningBoundary


class SemanticEvolutionCycle:
    """Coordinate fallback -> learning -> acceptance -> promotion -> reuse.

    The cycle deliberately delegates trusted knowledge creation to the existing
    learning stack and delegates future matching to LearnedSemanticRegistry.
    """

    VERSION = "0.1.0"

    def __init__(self, boundary: SemanticLearningBoundary, learning_coordinator: Any):
        self.boundary = boundary
        self.promotion = SemanticKnowledgePromotion(boundary, learning_coordinator)

    def accept_and_promote(self, candidate_id: str) -> Dict[str, Any]:
        return self.promotion.accept_and_promote(candidate_id)

    def reject(self, candidate_id: str, reason: str = "") -> Dict[str, Any]:
        return self.promotion.reject(candidate_id, reason=reason)

    def reuse(self, text: str) -> Dict[str, Any] | None:
        """Return a learned-native semantic interpretation, if one exists."""
        return self.boundary.apply_learned_capability(text)

    def cycle(self, text: str, native_result: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a new input through native/learned/fallback resolution."""
        return self.boundary.resolve(text, native_result)
