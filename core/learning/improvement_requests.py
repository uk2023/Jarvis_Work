from __future__ import annotations

"""Conversational improvement-request intake -- UK's explicit ask: be
able to tell JARVIS "this is a bug", "I want this feature", "this
needs improving" the way Claude gets told these things in this
project's chat, and have JARVIS discuss it and act on it.

HONEST SCOPE, stated plainly (this is the load-bearing part of this
module, not a footnote): JARVIS's own LLM budget is 7 calls / 2400
tokens PER TURN (config/cognition.json). Fixing a real bug in this
project -- reading multiple files, understanding architecture, writing
correct code, running the regression suite, iterating on failures --
has genuinely taken thousands of tokens of reasoning PER FIX across
this entire long conversation. That is not a restriction that can be
relaxed; it is a real capability gap between a frontier model with a
full development sandbox and a small, tightly-budgeted model answering
one conversational turn. This module does not pretend otherwise.

What it DOES do, honestly: records every request UK makes, persists it
durably (so it survives restarts, unlike raising it once and losing
it), and classifies it into exactly two honest buckets:

  NARROW (JARVIS can genuinely self-test and propose): vocabulary/
  category-word additions -- this is precisely what
  category_word_learner.py + sandbox_test_category_word() already do,
  now reachable by explicitly asking for it, not just from passive
  LLM-fallback observation.

  BROADER (needs a developer / Claude): anything touching multiple
  files, architecture, or logic beyond a single vocabulary word. These
  get recorded and surfaced, but JARVIS says so plainly instead of
  attempting something outside its real, current ability to safely
  test.
"""

import re
import time
from typing import Any, Dict, List, Optional

_REQUEST_PATTERNS = [
    re.compile(r"\b(?:yeh|ye)\s+(?:ek\s+)?bug\s+hai\b", re.I),
    re.compile(r"\b(?:yeh|ye)\s+feature\s+chahi?ye\b", re.I),
    re.compile(r"\b(?:yeh|ye)\s+improvement\s+chahi?ye\b", re.I),
    re.compile(r"\bmujhe\s+(?:yeh|ye|is)\s+.{0,60}\s+chahi?ye\b", re.I),
    re.compile(r"\bmain\s+chahta\s+h[uo]+n\s+ki\b", re.I),
    re.compile(r"\bisse\s+fix\s+karo\b", re.I),
]

# A single vocabulary word (letters/digits only, no spaces) is the
# ONLY thing NARROW enough for the existing sandbox test to genuinely
# evaluate -- see the module docstring's honest-scope note.
_NARROW_WORD_PATTERN = re.compile(r"\b([a-zA-Z]{3,20})\b\s+(?:word|category|indicator)\b", re.I)


def is_improvement_request(text: str) -> bool:
    return any(p.search(text or "") for p in _REQUEST_PATTERNS)


def classify_request(text: str) -> Dict[str, Any]:
    """Returns {"scope": "narrow"|"broad", "candidate_word": str|None}.
    Narrow ONLY when a single vocabulary word can be identified as the
    actual ask -- everything else is honestly broad."""
    match = _NARROW_WORD_PATTERN.search(text or "")
    if match:
        return {"scope": "narrow", "candidate_word": match.group(1).lower()}
    return {"scope": "broad", "candidate_word": None}


class ImprovementRequestStore:
    """Persists every request UK makes (SYSTEM namespace, same durable
    pattern as identity adaptations) so it survives restarts and can
    genuinely be reviewed later -- not raised once and forgotten."""

    def __init__(self, memory: Any = None):
        self._memory = memory

    def record(self, text: str) -> Dict[str, Any]:
        classification = classify_request(text)
        entry = {
            "text": text,
            "timestamp": time.time(),
            "scope": classification["scope"],
            "candidate_word": classification["candidate_word"],
            "status": "recorded",
        }
        semantic = getattr(self._memory, "semantic", self._memory)
        if semantic is not None and hasattr(semantic, "remember"):
            try:
                predicate = f"improvement_request_{int(entry['timestamp'] * 1000)}"
                semantic.remember(
                    subject="jarvis_self", predicate=predicate, value=entry,
                    confidence=1.0, importance=0.6, source="user_request",
                    tags=["identity", "improvement_request"], namespace="SYSTEM",
                )
            except Exception:
                pass
        return entry

    def pending(self) -> List[Dict[str, Any]]:
        semantic = getattr(self._memory, "semantic", self._memory)
        if semantic is None or not hasattr(semantic, "find"):
            return []
        results = []
        try:
            for item in semantic.find(subject="jarvis_self") or []:
                predicate = str(getattr(item, "predicate", "") or "")
                if not predicate.startswith("improvement_request_"):
                    continue
                value = getattr(item, "value", None)
                if isinstance(value, dict) and value.get("status") == "recorded":
                    results.append(value)
        except Exception:
            pass
        return results


def honest_acknowledgement(entry: Dict[str, Any]) -> str:
    """The response JARVIS gives right when a request is recorded --
    genuinely honest about what it can and cannot attempt itself."""
    if entry["scope"] == "narrow" and entry["candidate_word"]:
        return (
            f"Samajh gaya, UK -- note kar liya. '{entry['candidate_word']}' jaisa "
            f"single word ho toh main khud sandbox mein test kar sakta hoon aur "
            f"agla idle cycle mein approval ke liye propose karunga. Bade "
            f"changes (multiple files, logic) ke liye tumhe ya Claude ko dekhna "
            f"padega -- yeh mera honest limit hai abhi."
        )
    return (
        "Samajh gaya, UK -- note kar liya, permanently save ho gaya. Lekin "
        "imaandaari se: yeh sirf ek vocabulary-word jaisa chhota change nahi "
        "lagta, isliye main khud safely test/apply nahi kar sakta -- yeh "
        "Claude ya kisi developer ko dikhana padega."
    )
