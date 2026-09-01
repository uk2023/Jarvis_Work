"""Semantic Understanding substrate for JARVIS.

This package is intentionally dependency-free and sits above the existing
memory/learning organs. It provides deterministic symbolic extraction and
context structures without making the LLM the owner of semantic memory.
"""

from .engine import SemanticUnderstandingEngine, SemanticFact

__all__ = ["SemanticUnderstandingEngine", "SemanticFact"]
