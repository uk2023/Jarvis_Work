# -*- coding: utf-8 -*-
"""LLM-optional runtime adapter for JARVIS Brain."""
from typing import Any, Dict, Optional

from .brain import Brain as BaseBrain


class LLMOptionalBrain(BaseBrain):
    """Brain that remains alive when no LLM bridge is attached."""

    VERSION = getattr(BaseBrain, "VERSION", "unknown") + "+llm-optional"

    def _fallback_cognitive_response(self, user_input: str, source: str = "cli") -> str:
        text = (user_input or "").strip()
        lower = text.lower()
        if lower in {"status", "health", "ping"}:
            return "JARVIS Core ONLINE. LLM unavailable; operating in degraded cognitive mode."
        if lower in {"who are you", "what are you", "tum kaun ho", "aap kaun ho"}:
            return ("Main JARVIS ka core organism hoon. Natural-language reasoning service "
                    "abhi unavailable hai, lekin Brain, state, memory aur autonomous "
                    "subsystems active reh sakte hain.")
        if lower in {"what can you do", "tum kya kar sakte ho"}:
            return ("LLM ke bina main deterministic core operations, state, memory, "
                    "learning, goals aur autonomous coordination maintain kar sakta hoon. "
                    "Natural conversation ke liye LLM attach karna zaroori hai.")
        return ("JARVIS received your input, but the LLM cognitive service is currently "
                "offline. Core organism remains alive; natural-language reasoning is "
                "temporarily unavailable.")

    def think_and_respond(self, user_input: str,
                          identity_profile: Optional[Dict[str, Any]] = None,
                          source: str = "cli") -> str:
        """Use normal Brain intelligence when LLM exists; otherwise stay alive."""
        if getattr(self, "llm", None) is not None:
            return super().think_and_respond(
                user_input, identity_profile=identity_profile, source=source
            )

        # Current EventBus API is emit(), not publish().
        try:
            if self.events is not None:
                self.events.emit("USER_INPUT", {"text": user_input}, source=source)
        except Exception:
            pass

        # Record the interaction without inventing an LLM-derived fact.
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

        try:
            queue = self.status().get("async_learning_queue", {}) if hasattr(self, "status") else {}
        except Exception:
            queue = {}

        self.last_turn_trace = {
            "source": source,
            "memory": {},
            "vector_matches": [],
            "learning_queue": queue,
            "pipeline_success": True,
            "llm_available": False,
            "timings": {"memory": 0.0, "llm": 0.0, "total": 0.0},
            "memory_signal": None,
            "typos_corrected": [],
        }
        return self._fallback_cognitive_response(user_input, source=source)


def install_llm_optional_brain() -> None:
    """Compatibility no-op; bootstrap should explicitly import the adapter."""
    return None
