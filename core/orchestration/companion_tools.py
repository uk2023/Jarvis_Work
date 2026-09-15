from __future__ import annotations

"""Brain capabilities added 2026-09-13, kept in a mixin so brain.py
itself is not touched more than the one line that inherits it.

Four things UK asked for:

  1. RELATIONSHIP TOOLS -- so the tree can be built by talking
     ("Heramb mera dost hai"), not only through a Python API.

  2. MESSAGE DROP -- voicemail for someone, held until they verify.

  3. STANDING-INSTRUCTION AUDIT -- UK: "standing instruction silently
     hit ho jata hai, UI ya trace ya kahin bhi iska record nahi aata".
     Every firing is now recorded with a timestamp and reason, so
     there is an actual place to look. A scheduled action that runs
     invisibly is indistinguishable from one that never ran, which is
     exactly why this was hard to trust.

  4. SEARCH CONFIRMATION -- UK: JARVIS should decide when to go to the
     internet, and when it is unsure, ASK rather than either guessing
     or silently searching. Pairs with information_need.py: that
     decides WHERE an answer lives; this handles the borderline case
     where going out to the web is a judgement call.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..runtime.log import log_event

_AUDIT_DB = Path("data/instruction_audit.db")


def _audit_conn() -> sqlite3.Connection:
    _AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_AUDIT_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS instruction_firings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instruction_id TEXT,
            instruction_text TEXT,
            trigger_type TEXT,
            fired_at REAL NOT NULL,
            outcome TEXT,
            detail TEXT
        )
    """)
    return conn


def record_instruction_firing(instruction_id: str, instruction_text: str,
                              trigger_type: str, outcome: str,
                              detail: Optional[str] = None) -> None:
    """Called whenever a standing instruction actually fires. Silent
    failure here is acceptable (an audit write must never break the
    action it is recording) but it is logged, so a missing trail is
    itself visible."""
    try:
        with _audit_conn() as conn:
            conn.execute(
                "INSERT INTO instruction_firings (instruction_id, instruction_text, trigger_type,"
                " fired_at, outcome, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (instruction_id, instruction_text, trigger_type, time.time(), outcome, detail),
            )
            conn.commit()
        log_event("instructions", f"standing instruction fired: {instruction_text[:60]} -> {outcome}", level="info")
    except Exception as exc:
        log_event("instructions", f"could not record instruction firing (audit trail incomplete): {exc}", level="warning")


def get_instruction_firings(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        with _audit_conn() as conn:
            rows = conn.execute(
                "SELECT instruction_id, instruction_text, trigger_type, fired_at, outcome, detail"
                " FROM instruction_firings ORDER BY fired_at DESC LIMIT ?", (max(1, int(limit)),)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# Going to the web is worth confirming when the question is answerable
# EITHER from the model's own knowledge or from a live source, and the
# two could disagree. A settled historical fact needs no search; a
# stock price needs no confirmation (it simply cannot be answered
# without one). The interesting middle is where asking is cheapest.
_SETTLED_MARKERS = ("history", "itihas", "kab bana", "who invented", "kisne banaya",
                    "definition", "matlab kya", "kya hota hai", "explain", "samjhao")
_MUST_SEARCH_MARKERS = ("price", "rate", "bhav", "stock", "nifty", "sensex", "weather",
                        "mausam", "score", "news", "khabar", "aaj ka", "today's",
                        # DEVANAGARI (added 2026-09-15, from UK's own chat log): the
                        # checks above only matched Latin-script text, so "निफ़्टी"
                        # typed in Devanagari missed EVERY rule here -- including
                        # decide_information_need()'s own world_live classification,
                        # which also came back as the generic "language" source for
                        # the same input. Until that deeper NLU gap is fixed for
                        # Devanagari generally, this list at least catches the
                        # highest-frequency terms UK actually hit.
                        "निफ़्टी", "निफ्टी", "सेंसेक्स", "मौसम", "भाव", "स्टॉक", "खबर")

# Turns about JARVIS itself, UK, or the people around him are never a
# web question -- checked BEFORE the generic fallthrough below, or
# "kis baare mein baat kar rahe the" and "UJJWAL kaun hai" (both
# already-known facts) end up offering a web search anyway, which is
# exactly what UK's log showed on 29 of 144 turns.
_PERSONAL_MARKERS = ("tum", "tumhe", "tumhara", "tumhari", "mujhe", "mera", "meri", "mere",
                     "aap", "aapka", "apna", "yaad", "jante", "janta", "jaanta", "naam",
                     "creator", "kaun ho", "who are you", "kis baare mein", "kya baat",
                     "kar rahe the", "kaise ho", "how are you")

# The confirm branch is for turns that GENUINELY smell time-sensitive --
# not the catch-all for anything uncertain. UK's log showed "2*2=?" and
# "how are you" both ending in "web se check karun?" because the old
# default sent every unmatched turn here.
_MAYBE_STALE_MARKERS = ("kaunsa behtar", "compare", " vs ", "latest", "naya", "new",
                        "price", "kitne ka", "release", "version")


def should_confirm_search(user_input: str, information_need: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Decide: search outright, ask first, or don't search.

    Returns {"action": "search"|"confirm"|"no_search", "reason": str}.
    """
    text = (user_input or "").lower()
    need = (information_need or {}).get("source")

    if any(m in text for m in _MUST_SEARCH_MARKERS) or need == "world_live":
        return {"action": "search",
                "reason": "Yeh live data hai -- iska jawab bina source ke dena guess hoga, isliye seedha search."}

    if any(m in text for m in _SETTLED_MARKERS):
        return {"action": "no_search",
                "reason": "Yeh settled/conceptual sawaal hai -- ismein search se kuch nahi badlega."}

    # Explicit instruction always wins over JARVIS's own judgement.
    if any(m in text for m in ("search karo", "internet", "web se", "dekh kar batao", "google")):
        return {"action": "search", "reason": "UK ne khud search karne ko kaha."}

    if need in ("semantic", "episodic", "rules", "self_state", "procedural"):
        return {"action": "no_search",
                "reason": f"Iska jawab {need} memory ka hai, internet ka nahi."}

    # PERSONAL/SELF-REFERENTIAL -- checked before the fallthrough. UK's
    # log: "UJJWAL kaun hai?" (already answered), "kis baare mein baat
    # kar rahe the?", "how are you jarvis" all offered a web search
    # despite being about JARVIS, UK, or their own conversation -- none
    # of which a web search can answer.
    if any(m in text for m in _PERSONAL_MARKERS):
        return {"action": "no_search",
                "reason": "Yeh hamare baare mein hai -- iska jawab memory mein hai, web pe nahi."}

    # DEFAULT IS NO_SEARCH, NOT CONFIRM (fixed 2026-09-15 -- this exact
    # fix was made once earlier and lost when the working tree was
    # reverted; UK's fresh chat log showed the regression directly: 29
    # of 144 turns ended in an unprompted "web se check karun?",
    # including on "2*2 = ?" and "how are you jarvis"). Confirming is
    # now reserved for turns that actually smell time-sensitive;
    # everything else gets a plain answer with no search offer at all.
    if any(m in text for m in _MAYBE_STALE_MARKERS):
        return {"action": "confirm",
                "reason": "Time-sensitive ho sakta hai -- ek line mein poochna theek hai."}

    return {"action": "no_search",
            "reason": "Isme kuch live nahi hai -- jo pata hai wahi seedha bolo."}


class CompanionToolsMixin:
    """Mixed into Brain. Every method here is dispatchable as a tool."""

    # ---------------------------------------------------- relationships
    def add_relationship(self, person: str, relation: str, notes: Optional[str] = None) -> Dict[str, Any]:
        from ..identity.relationships import add_relationship as _add, who_is
        if not (person or "").strip() or not (relation or "").strip():
            return {"error": "person and relation are both required"}
        existing = who_is(person)
        rel_id = _add(person=person, relation=relation, notes=notes)
        return {
            "success": True, "id": rel_id, "person": person.strip(), "relation": relation.strip().lower(),
            "note": (f"Pehle se '{existing['relation']}' recorded tha -- ab yeh bhi jud gaya."
                     if existing else "Naya relation record ho gaya."),
        }

    def get_relationship_tree(self) -> Dict[str, Any]:
        from ..identity.relationships import get_relationship_tree as _tree, known_people_count
        return {"tree": _tree(), "stats": known_people_count()}

    def leave_message_for(self, person: str, message: str) -> Dict[str, Any]:
        from ..identity.relationships import leave_message, who_is
        if not (person or "").strip() or not (message or "").strip():
            return {"error": "person and message are both required"}
        msg_id = leave_message(from_username="uk", for_person=person, message=message)
        known = who_is(person)
        return {
            "success": True, "id": msg_id, "for": person.strip(),
            "delivery": (
                "Unke sign in karke verify hone par pahuncha dunga."
                if known and known.get("linked_username")
                else "Abhi unka account link nahi hai -- jab woh signup karke verify honge, tab milega."
            ),
        }

    # --------------------------------------------- coding + evolution
    def run_coding_task(self, task: str, max_steps: int = 4) -> Dict[str, Any]:
        """The ONLY multi-step path in JARVIS -- see skills/codebox.py."""
        from ..skills.codebox import run_coding_session
        if not (task or "").strip():
            return {"error": "task is required"}
        try:
            return run_coding_session(
                self.llm.generate_response,
                task=task,
                system_prompt="You are JARVIS, writing code for UK.",
                max_steps=max_steps,
            )
        except Exception as exc:
            return {"error": f"coding session failed: {exc}", "solved": False}

    def propose_self_feature(self, feature_name: str, code: str,
                             rationale: str, confidence: float = 0.5) -> Dict[str, Any]:
        from ..evolution.self_evolution import propose_feature
        if not (feature_name or "").strip() or not (code or "").strip():
            return {"error": "feature_name and code are both required"}
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except Exception:
            confidence = 0.5
        return propose_feature(feature_name, code, rationale or "", confidence)

    def list_self_proposals(self) -> Dict[str, Any]:
        from ..evolution.self_evolution import evolution_status, list_proposals
        status = evolution_status()
        return {
            "status": status,
            "proposals": [
                {k: p.get(k) for k in ("id", "feature_name", "status", "confidence",
                                       "rationale", "approval_reasons", "created_at")}
                for p in list_proposals(limit=20)
            ],
        }

    def decide_self_proposal(self, proposal_id: str, approve: bool) -> Dict[str, Any]:
        """Deliberately NOT exposed as an LLM tool -- approving its own
        proposals is the one decision JARVIS must never make. Callable
        from the CLI/UI by UK only."""
        from ..evolution.self_evolution import decide_proposal
        return decide_proposal(proposal_id, approve=approve, decided_by="UK")

    # ------------------------------------------------------ step goals
    def run_goal_stepwise(self, goal: str, role: str = "user",
                          is_verified: bool = False, max_steps: int = 6) -> Dict[str, Any]:
        """Multi-step goal execution -- owner/co-owner only. Not exposed
        as an LLM tool: UK asks for it explicitly, so the CLI/UI calls
        this rather than letting the model start a multi-call run on its
        own judgement."""
        from .step_goals import run_goal_steps
        if not (goal or "").strip():
            return {"error": "goal is required"}
        return run_goal_steps(
            self.llm.generate_response, goal=goal, role=role,
            is_verified=is_verified, max_steps=max_steps, brain=self,
        )




    def sandbox_overview(self) -> Dict[str, Any]:
        from ..skills.sandbox_policy import sandbox_overview as _overview
        return _overview()

    def run_self_diagnostics(self) -> Dict[str, Any]:
        """Read-only -- JARVIS reports what it finds, never auto-fixes
        during a normal conversation. Applying a remedy is a deliberate
        owner/co-owner action (CLI's /diagnose fix, or the HTTP
        POST /diagnose/fix route), never something a chat turn triggers
        on its own."""
        from ..runtime.diagnostics import run_diagnostics
        return run_diagnostics(auto_fix=False)

    def list_my_uploads(self) -> Dict[str, Any]:
        """Only the current speaker's uploads -- scoped by their own
        sandbox, so there is no path to another user's files."""
        from ..skills.upload_guard import list_uploads
        speaker = getattr(self, "current_speaker", None) or {}
        return {"uploads": list_uploads(role=speaker.get("role", "user"),
                                        username=speaker.get("username"))}

    # --------------------------------------------- standing instructions
    def get_instruction_firings(self, limit: int = 20) -> Dict[str, Any]:
        firings = get_instruction_firings(limit)
        return {
            "firings": firings,
            "count": len(firings),
            "note": ("Abhi tak koi standing instruction fire nahi hui (ya audit trail shuru hone se "
                     "pehle hui thi)." if not firings else None),
        }
