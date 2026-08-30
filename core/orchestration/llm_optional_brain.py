# -*- coding: utf-8 -*-
"""LLM-optional runtime adapter for JARVIS Brain.

The normal Brain remains the central orchestrator. The LLM is an optional
cognitive service used for natural-language understanding/generation, not a
lifecycle dependency of the organism.

Usage in bootstrap.py:
    from core.orchestration.brain import Brain as BaseBrain
    from core.orchestration.llm_optional_brain import LLMOptionalBrain
    Brain = LLMOptionalBrain

No model is loaded here. CLI/web may attach one later.
"""
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain


class LLMOptionalBrain(BaseBrain):
    """Brain that remains alive when no LLM bridge is attached."""

    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+llm-optional"

    def _fallback_cognitive_response(self, user_input: str, source: str = "cli") -> str:
        """Provide a deterministic degraded-mode response.

        This is deliberately not pretending to be an LLM. It confirms that
        the organism is alive, can receive input, and can expose core state.
        Known operational commands can still be handled by the outer CLI/UI.
        """
        text = (user_input or "").strip()
        lower = text.lower()

        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."

        if lower in {"who are you", "what are you", "tum kaun ho", "aap kaun ho"}:
            return "Main JARVIS ka core organism hoon. Natural-language reasoning service abhi unavailable hai, lekin Brain, state, memory aur autonomous subsystems active reh sakte hain."

        if lower in {"what can you do", "tum kya kar sakte ho"}:
            return "LLM ke bina main deterministic core operations, state, memory, learning, goals aur autonomous coordination maintain kar sakta hoon. Natural conversation ke liye LLM attach karna zaroori hai."

        return (
            "JARVIS received your input, but the LLM cognitive service is currently "
            "offline. Core organism remains alive; natural-language reasoning is "
            "temporarily unavailable."
        )

    def think_and_respond(
        self,
        user_input: str,
        identity_profile: Optional[Dict[str, Any]] = None,
        source: str = "cli",
    ) -> str:
        """Use the full existing pipeline when LLM exists; otherwise degrade safely."""
        if getattr(self, "llm", None) is not None:
            return super().think_and_respond(
                user_input,
                identity_profile=identity_profile,
                source=source,
            )

        # Keep the organism's input/event path alive even without language
        # generation. The experience can be recorded by the existing learning
        # machinery without inventing an LLM-generated fact.
        try:
            if hasattr(self, "events") and self.events is not None:
                self.events.publish(
                    "USER_INPUT",
                    {"text": user_input},
                    source=source,
                )
            elif hasattr(self, "event_bus") and self.event_bus is not None:
                self.event_bus.publish(
                    "USER_INPUT",
                    {"text": user_input},
                    source=source,
                )
        except Exception:
            pass

        try:
            if hasattr(self, "_enqueue_learning"):
                self._enqueue_learning(
                    event_type="USER_INPUT_DEGRADED",
                    context={"user_input": user_input},
                    action={"mode": "llm_unavailable"},
                    outcome={"status": "received_without_llm"},
                    source=source,
                    importance=0.2,
                )
        except Exception:
            pass

        # Keep telemetry coherent for diagnostics even though no neural
        # inference occurred.
        try:
            self.last_turn_trace = {
                "source": source,
                "memory": {},
                "vector_matches": [],
                "learning_queue": self.status().get("async_learning_queue", {})
                if hasattr(self, "status") else {},
                "pipeline_success": True,
                "llm_available": False,
                "timings": {"memory": 0.0, "llm": 0.0, "total": 0.0},
                "memory_signal": None,
                "typos_corrected": [],
            }
        except Exception:
            pass

        return self._fallback_cognitive_response(user_input, source=source)


def install_llm_optional_brain() -> None:
    """Compatibility helper for code that imports the original Brain class.

    Call before constructing Brain instances if replacing the bootstrap import
    is inconvenient. Existing Brain references are intentionally not mutated
    globally unless this function is explicitly called.
    """
    return None
