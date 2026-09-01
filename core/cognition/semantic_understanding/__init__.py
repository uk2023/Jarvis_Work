"""Semantic Understanding substrate.

Provides a dependency-light neuro-symbolic foundation between Perception and
Cognition. It does not execute actions and does not write trusted long-term
memory by itself.
"""

from .bridge_to_cognition import SemanticUnderstanding

__all__ = ["SemanticUnderstanding"]
