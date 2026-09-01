"""Hybrid semantic retrieval facade.

The retriever prefers exact symbolic matches, then optional vector and graph
providers. Providers are injected so the module can connect to JARVIS's
existing SemanticMemory/FAISS/graph implementations without duplicating them.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional


class SemanticRetriever:
    VERSION = "0.1.0"

    def __init__(self, *, exact_provider: Optional[Callable[..., Iterable[Any]]] = None,
                 vector_provider: Optional[Callable[..., Iterable[Any]]] = None,
                 graph_provider: Optional[Callable[..., Iterable[Any]]] = None) -> None:
        self.exact_provider = exact_provider
        self.vector_provider = vector_provider
        self.graph_provider = graph_provider

    @staticmethod
    def _safe_call(provider: Optional[Callable[..., Iterable[Any]]], query: str, **kwargs: Any) -> List[Any]:
        if not callable(provider):
            return []
        try:
            result = provider(query, **kwargs)
            return list(result or [])
        except TypeError:
            return list(provider(query) or [])
        except Exception:
            return []

    def retrieve(self, query: str, *, limit: int = 8, **kwargs: Any) -> Dict[str, List[Any]]:
        exact = self._safe_call(self.exact_provider, query, limit=limit, **kwargs)
        vector = self._safe_call(self.vector_provider, query, limit=limit, **kwargs)
        graph = self._safe_call(self.graph_provider, query, limit=limit, **kwargs)
        return {"exact": exact[:limit], "vector": vector[:limit], "graph": graph[:limit]}
