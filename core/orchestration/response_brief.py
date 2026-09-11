from __future__ import annotations

"""Structured response brief -- the actual fix for "it feels LLM based".

Before this module: the LLM route built its system prompt out of raw
`str(dict)` dumps of retrieved Knowledge objects (literally
`{'knowledge_id': 'k5', 'subject': 'user', ...}` text) plus a fixed
persona paragraph, and asked the model to just... figure out what to
say. There was no channel for the user's own stated rules to reach
it, and nothing stopping the model from treating unrelated chat
history as equally authoritative as confirmed facts.

This inverts that: Brain's native/symbolic layers (perception, memory
retrieval, the rule store) do the understanding and assemble a small,
strictly-typed JSON schema -- "here is what's true, here is what the
user asked, here are the rules you must follow". The LLM's only job
is to phrase ONE reply from that schema. It is explicitly told not to
introduce facts that aren't in the schema.

Two functions matter to callers:
    build_response_brief(...) -> dict          always used when the
                                                 LLM route runs
    try_direct_recall_answer(...) -> str|None   a conservative, native
                                                 fast path: for a
                                                 narrow class of "what
                                                 is my X" questions
                                                 with an exact stored
                                                 fact, answer WITHOUT
                                                 calling the LLM at
                                                 all. This is the
                                                 concrete "every API
                                                 call has a cost, don't
                                                 spend one you don't
                                                 need" behaviour -- not
                                                 a slogan, an actual
                                                 skip.
"""

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------
# Native identity fast path (zero LLM calls -- "who are you"/"who am I")
# ---------------------------------------------------------------------

_IDENTITY_PATTERNS = [
    re.compile(r"\btum\s+kaun\s+ho\b", re.I),
    re.compile(r"\bapp?\s+kaun\s+ho\b", re.I),
    re.compile(r"\bwho\s+are\s+you\b", re.I),
    re.compile(r"\bapna\s+naam\s+batao\b", re.I),
    re.compile(r"\bwhat(?:'s| is)\s+your\s+name\b", re.I),
]
_SELF_ASK_PATTERNS = [
    re.compile(r"\bmai[n]?\s+kaun\s+h(?:u|oon)\b", re.I),
    re.compile(r"\bwho\s+am\s+i\b", re.I),
]
# "Why do you exist" -- distinct from "who are you". Previously
# unhandled entirely: JARVIS could say its NAME but never its PURPOSE
# unless the LLM happened to guess one fresh each time (inconsistent,
# and not grounded in Identity.PURPOSE which already existed as real
# structured data, just never surfaced through this fast path).
_PURPOSE_ASK_PATTERNS = [
    re.compile(r"\btum\s+kyu?n\s+ho\b", re.I),
    re.compile(r"\btumhara\s+(?:maksad|purpose|uddeshya)\s+kya\s+hai\b", re.I),
    re.compile(r"\bwhy\s+(?:do\s+you\s+exist|are\s+you\s+here)\b", re.I),
    re.compile(r"\bwhat(?:'s| is)\s+your\s+purpose\b", re.I),
]


def try_identity_answer(user_input: str, identity_system: Any, speaker_name: Optional[str] = None) -> Optional[str]:
    """Answer identity questions from JARVIS's own structured identity
    state (core/identity/jarvis_identity.py) instead of letting the LLM
    guess its own persona fresh each time. Zero LLM calls when it fires.
    """
    if identity_system is None:
        return None
    text = (user_input or "").strip()
    if not text or len(text) > 60:
        return None

    describe = getattr(identity_system, "describe_self_structured", None)
    if not callable(describe):
        return None

    if any(p.search(text) for p in _IDENTITY_PATTERNS):
        info = describe(speaker_name=speaker_name)
        return f"Main {info['i_am']} hoon -- {info['my_designation']}. Mere creator {info['my_creator']} hain."
    if any(p.search(text) for p in _SELF_ASK_PATTERNS):
        info = describe(speaker_name=speaker_name)
        return f"Aap {info['who_you_are']}."
    if any(p.search(text) for p in _PURPOSE_ASK_PATTERNS):
        info = describe(speaker_name=speaker_name)
        purpose = info.get("my_purpose")
        if purpose:
            return f"Mera purpose hai: {purpose}"
    return None


# "Why did you do that / what have you learned / what was missing /
# what changed" -- genuine introspection questions. Before this,
# asking JARVIS about its own reasoning had nowhere real to go: the
# question fell through to the LLM route, which had NO access to
# brain.last_reasoning_traces / dependency_metrics / evolution.proposals
# and could only guess a plausible-sounding answer from training data --
# meaning JARVIS could not actually explain itself even though the real
# data existed the entire time, just unreachable from conversation. This
# answers directly from that real data, zero LLM cost, same as the
# identity/direct-recall fast paths above.
_SELF_AWARENESS_PATTERNS = [
    re.compile(r"\btum(?:ne)?\s+(?:yeh\s+|woh\s+)?kyu?n\s+kiy?a\b", re.I),
    re.compile(r"\bkya\s+seekh[aiy]", re.I),
    re.compile(r"\bkya\s+kam[i]\s+thi\b", re.I),
    re.compile(r"\bkya\s+update\s+hua\b", re.I),
    re.compile(r"\bkyu[n]?\s+hua\s+(?:tha|abhi)?\s*\??$", re.I),
    re.compile(r"\bwhy\s+did\s+you\s+do\s+(?:that|this)\b", re.I),
    re.compile(r"\bwhat\s+(?:have\s+you\s+)?learn(?:ed|t)\b", re.I),
    re.compile(r"\bwhat.{0,20}(?:was\s+)?missing\b", re.I),
    re.compile(r"\bwhat.{0,15}update", re.I),
    # "Why didn't you store/extract X" -- answered from
    # last_layer_validations (the real, retained per-turn record of
    # WHY each layer produced what it produced), not a guess.
    re.compile(r"\bkyu[n]?\s+nahi\s+(?:store|save|extract|nikal|banaya|bana)", re.I),
    re.compile(r"\bwhy\s+(?:didn'?t|did\s+not)\s+you\s+(?:store|save|extract)", re.I),
    # "Good morning / raat ko kya hua" -- overnight idle-learning report.
    # Deliberately NOT matching a bare "good morning" here -- that's
    # already claimed by the ordinary native greeting path earlier in
    # the pipeline, and would never reach this far. Only the clearer,
    # unambiguous phrasing that specifically asks about the overnight/
    # idle period is handled here.
    re.compile(r"\b(?:raat|overnight|absence)\s+(?:ko|mein|me)?\s*kya\s+(?:hua|kiya|seekha)\b", re.I),
    re.compile(r"\bidle\s+mein\s+kya\s+(?:hua|kiya)\b", re.I),
    # "How long have you been running" -- session uptime vs total
    # cumulative runtime vs age-since-birth are three different real
    # numbers (see JarvisIdentity.runtime_info()), not one guess.
    re.compile(r"\bkitn[ei]\s+der\s+se\s+(?:chal|chalu|running)", re.I),
    re.compile(r"\bruntime\s+(?:batao|kya\s+hai)\b", re.I),
    re.compile(r"\bhow\s+long\s+(?:have\s+you\s+been\s+)?(?:running|up)\b", re.I),
]


def try_self_awareness_answer(user_input: str, brain: Any) -> Optional[str]:
    """Zero-LLM-cost introspection: answers "why did you do that", "what
    have you learned", "what was missing", "what changed" from JARVIS's
    OWN real reasoning history (last_reasoning_traces), dependency
    metrics, and evolution proposals -- not a guess."""
    text = (user_input or "").strip()
    if not text or len(text) > 100:
        return None
    if not any(p.search(text) for p in _SELF_AWARENESS_PATTERNS):
        return None
    if brain is None:
        return None

    # "Why didn't you store/extract X" -- answered directly from the
    # REAL, retained record of the last time a layer failed to
    # produce a relation, not a guess.
    if re.search(r"\bkyu[n]?\s+nahi\s+(?:store|save|extract|nikal|banaya|bana)", text, re.I) or \
       re.search(r"\bwhy\s+(?:didn'?t|did\s+not)\s+you\s+(?:store|save|extract)", text, re.I):
        validations = getattr(brain, "last_layer_validations", None) or []
        for v in reversed(validations):
            if isinstance(v, dict) and not v.get("succeeded"):
                return f"Pichhli baar jo store nahi hui: \"{v.get('reason', 'reason not recorded')}\" (layer: {v.get('layer', 'unknown')})"
        return "Abhi tak koi record nahi hai kisi extraction ke fail hone ka is session mein."

    # "Good morning / raat ko kya hua" -- UK's explicit overnight-report
    # ask. Answered from idle_loop's REAL accumulated log
    # (core/autonomy/idle_loop.py's overnight_log), never a fabricated
    # "I learned a lot!" -- if idle time found nothing worth promoting,
    # that is exactly what gets said.
    if re.search(r"\b(?:raat|overnight|absence)\s+(?:ko|mein|me)?\s*kya\s+(?:hua|kiya|seekha)\b", text, re.I) or \
       re.search(r"\bidle\s+mein\s+kya\s+(?:hua|kiya)\b", text, re.I):
        idle_loop = getattr(brain, "idle_loop", None)
        get_report = getattr(idle_loop, "get_overnight_report", None) if idle_loop is not None else None
        if callable(get_report):
            report = get_report(since=time.time() - 12 * 3600)  # last 12 hours
            if report["cycles_reviewed"] == 0:
                return "Raat ko idle time mein koi naya pattern nahi mila jo promote karne layak ho -- sab kuch normal raha."
            lines = [f"Raat ko {report['cycles_reviewed']} baar review kiya, {report['total_findings']} cheezein mili:"]
            for entry in report["entries"][-5:]:
                for finding in entry.get("findings", []):
                    lines.append(f"- {finding}")
            return " ".join(lines) if len(lines) > 1 else lines[0]
        return None

    # "Kitni der se chal rahe ho / runtime batao" -- three genuinely
    # different, real numbers from JarvisIdentity.runtime_info(), not
    # one conflated guess.
    if re.search(r"\bkitn[ei]\s+der\s+se\s+(?:chal|chalu|running)", text, re.I) or \
       re.search(r"\bruntime\s+(?:batao|kya\s+hai)\b", text, re.I) or \
       re.search(r"\bhow\s+long\s+(?:have\s+you\s+been\s+)?(?:running|up)\b", text, re.I):
        identity = getattr(brain, "identity_system", None)
        get_runtime_info = getattr(identity, "runtime_info", None) if identity is not None else None
        if callable(get_runtime_info):
            info = get_runtime_info()

            def _fmt_duration(seconds: float) -> str:
                seconds = int(seconds)
                days, rem = divmod(seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, _ = divmod(rem, 60)
                parts = []
                if days:
                    parts.append(f"{days} din")
                if hours:
                    parts.append(f"{hours} ghante")
                if minutes or not parts:
                    parts.append(f"{minutes} minute")
                return " ".join(parts)

            return (
                f"Is session mein {_fmt_duration(info['session_uptime_seconds'])} se chal raha hoon. "
                f"Total mila ke ab tak {_fmt_duration(info['cumulative_runtime_seconds'])} genuinely active raha hoon. "
                f"Bane hue {_fmt_duration(info['age_seconds'])} ho gaye hain."
            )
        return None

    traces = getattr(brain, "last_reasoning_traces", None) or []
    latest = traces[-1] if traces and isinstance(traces[-1], dict) else {}

    dep: Dict[str, Any] = {}
    status_fn = getattr(brain, "status", None)
    if callable(status_fn):
        try:
            dep = dict(status_fn()).get("dependency_metrics", {}) or {}
        except Exception:
            dep = {}

    evolution = getattr(brain, "evolution", None)
    proposals = getattr(evolution, "proposals", None) if evolution is not None else None
    latest_proposal = None
    if isinstance(proposals, dict) and proposals:
        try:
            latest_proposal = max(
                (p for p in proposals.values() if isinstance(p, dict)),
                key=lambda p: p.get("created_at", 0),
                default=None,
            )
        except Exception:
            latest_proposal = None

    parts = []
    if latest:
        why = latest.get("what_and_why") or "kuch specific record nahi hua is turn ke liye"
        parts.append(f"Pichhle turn mein: {why}")
        if latest.get("adopt_as_learning"):
            parts.append(f"Maine yeh seekha aur adopt kiya: \"{latest.get('next_time_different', '')}\"")
        elif latest.get("should_change_strategy"):
            gap = latest.get("outcome_gap_reason") or "expected aur actual outcome mein farak tha"
            parts.append(f"Ek gap notice hua tha ({gap}) -- flagged hai, lekin abhi adopt karne layak evidence nahi hai.")
        else:
            parts.append("Koi strategy change flag nahi hui -- jo approach use hui woh theek chali.")
    else:
        parts.append("Abhi tak is session mein koi reasoning cycle complete nahi hua hai.")

    if dep:
        total = dep.get("total_interactions", 0)
        native_rate = dep.get("native_resolution_rate")
        if total:
            parts.append(f"Ab tak {total} interactions mein native resolution rate {native_rate} hai.")

    if latest_proposal:
        parts.append(
            f"Sabse recent evolution proposal: [{latest_proposal.get('status')}] "
            f"target={latest_proposal.get('target')} -- {latest_proposal.get('reason', '')}"
        )

    return " ".join(parts) if parts else None


# Common Hinglish/Hindi words that get capitalized mid-sentence in
# ordinary casual typing/generation -- transliterated Hindi has no
# strict capitalization convention, so words like "Aur" (and), "Kuch"
# (some), "Naam" (name) routinely appear capitalized in the MIDDLE of
# a sentence, not just at its start. A real, observed failure: the
# proper-noun heuristic below flagged exactly these as "invented"
# because they weren't sentence-initial and weren't in the brief's own
# vocabulary -- but they're ordinary grammatical/functional words, not
# entities the LLM fabricated. This list is intentionally the most
# common ~80 such words, not an attempt at full Hindi vocabulary
# coverage -- it eliminates the large majority of false positives
# without trying to solve general transliterated-Hindi capitalization.
_COMMON_HINGLISH_WORDS = {
    "aur", "ya", "lekin", "kyunki", "kyuki", "toh", "bhi", "hi", "wahi", "yahi",
    "kuch", "sab", "sabhi", "acha", "achha", "achi", "theek", "thik",
    "naam", "baat", "kaam", "waqt", "din", "raat", "ghar", "log", "cheez", "chiz",
    "kya", "kaun", "kaha", "kahan", "kab", "kyun", "kyu", "kaise", "kitna", "kitni",
    "mera", "meri", "mere", "tera", "teri", "tere", "uska", "uski", "uske",
    "hamara", "hamari", "aapka", "aapki", "aapke", "aapko", "tumhara", "tumhari",
    "aap", "tum", "hum", "woh", "yeh", "ye", "wo", "unhe", "unko", "unka", "unki",
    "unke", "unhone", "isse", "usse", "isko", "usko", "iska", "iski", "inhe",
    "tumko", "tumhe", "mujhko", "hamein", "humein",
    "hai", "hoga", "hogi", "tha", "thi", "the", "raha", "rahi", "rahe",
    "kar", "karo", "karna", "kiya", "kijiye", "bol", "bolo", "bolna", "bataya",
    "dekh", "dekho", "dekhna", "samajh", "samjha", "samjho", "chahiye", "chaiye",
    "abhi", "phir", "fir", "ab", "tab", "jab", "agar", "warna", "matlab",
    "bahut", "bohot", "zyada", "thoda", "sirf", "bas", "only", "onnly",
    "please", "sorry", "thanks", "welcome", "okay", "haan", "nahi", "nahin",
}


def check_response_grounding(response_text: str, brief: Dict[str, Any], relations_extracted_this_turn: Optional[int] = None) -> "GroundingCheck":
    """DURING-response check (not the post-response reasoning cycle --
    see core/learning/post_response_reasoning.py for that): does the
    LLM's reply look like it stayed inside what the brief actually gave
    it? This is the real implementation behind response.output's
    "stayed_within_brief" field, which was previously a hardcoded
    True/[] placeholder.

    Honest limitation: full semantic hallucination-detection (deciding
    whether a sentence's MEANING is supported by known_facts) is a hard
    open problem this does not claim to solve. What this DOES check,
    conservatively: every proper-noun-like token and every standalone
    number in the response must appear somewhere in the brief's own
    legitimate sources (known_facts, known_relations, the user's own
    message, or recent_context) -- catching the most flagrant class of
    fabrication (an invented name, place, or figure) without pretending
    to verify subtler claims. False negatives are expected and
    acceptable; a false positive (blocking a genuinely grounded reply)
    would be worse, so this only ever WARNS (flags), never blocks.
    """
    vocabulary_parts = [
        brief.get("user_message", ""),
        brief.get("persona", {}).get("name", "") if isinstance(brief.get("persona"), dict) else "",
        brief.get("persona", {}).get("creator", "") if isinstance(brief.get("persona"), dict) else "",
        " ".join(brief.get("known_facts") or []),
        " ".join(brief.get("known_relations") or []),
        " ".join(brief.get("recent_context") or []),
        " ".join(brief.get("user_rules") or []),
    ]
    vocabulary = set(re.findall(r"[A-Za-z][A-Za-z']+|\d+", " ".join(vocabulary_parts).lower()))
    # Numeric substring tolerance: a fact stored as "1788707956.448458"
    # yields vocabulary tokens {"1788707956", "448458"} via the \d+
    # split above. The LLM is free to re-render that same fact with
    # different precision/rounding (e.g. "1788707956.4" or just the
    # integer part) -- that is not fabrication, it's reformatting a
    # real fact, and byte-exact matching was flagging it anyway. Treat
    # a candidate number as grounded if it is a numeric PREFIX of (or
    # is prefixed by) any vocabulary number, not just an exact match.
    vocabulary_numbers = [tok for tok in vocabulary if tok.isdigit()]

    # Derived-duration exemption: "943.13 seconds", "4926 seconds",
    # "X ghante/minute" are arithmetic JARVIS performed on a known
    # timestamp fact (now - creation_timestamp), not an invented
    # entity. A real observed failure was exactly this: true elapsed-
    # time numbers got flagged because the SUBTRACTION RESULT is never
    # literally present in the brief, only its inputs are. This is the
    # narrow, low-risk class of numeric "hallucination" that is
    # actually always safe: it's a name/place/price fabrication this
    # check exists to catch, not a correctly-computed duration.
    _duration_word = re.compile(
        r"\b\d[\d.]*\s*(?:second|seconds|sec|secs|ghante?|ghanta|minute|minutes|din|days?)\b", re.I
    )
    _duration_numbers_raw = set(re.findall(r"\b\d+(?:\.\d+)?\b", " ".join(m.group(0) for m in _duration_word.finditer(response_text))))
    # Candidate tokens are matched via \b\d{2,}\b on the RAW response
    # text, which stops at the decimal point ("943.13" -> "943" and
    # "13" as two SEPARATE candidates, since "." is a non-word
    # boundary) -- but duration_numbers above kept the full decimal
    # string ("943.13") as one piece, so neither half ever matched it
    # exactly. Real bug, found via UK's "943.13 seconds" case still
    # getting flagged post-fix: also add each dot-separated part so
    # both halves of a decimal duration are recognized individually.
    duration_numbers = set(_duration_numbers_raw)
    for _num in _duration_numbers_raw:
        duration_numbers.update(part for part in _num.split(".") if part)

    candidates = set(re.findall(r"\b[A-Z][a-zA-Z']{2,}\b|\b\d{2,}\b", response_text))
    # Sentence-initial capitals are not proper nouns -- don't flag the
    # first word of each sentence just for being capitalized.
    # Sentence-initial capitals are not proper nouns -- don't flag the
    # first word of each sentence just for being capitalized.
    # BUG FIX (real production false-positive, found via UK's logs):
    # this used to collect m.group(0) -- the WHOLE match including the
    # leading ". "/"! "/"? " (or start-of-string) -- into sentence_starts,
    # e.g. ". Aage" instead of just "Aage". candidates below only ever
    # contains the bare word ("Aage"), so the two sets could NEVER
    # intersect -- meaning the sentence-start exemption has silently
    # done nothing this whole time, and EVERY capitalized word that
    # opens the second (or third, ...) sentence of a multi-sentence
    # reply was getting flagged as "unsupported", regardless of how
    # innocuous the sentence was. This is almost certainly the single
    # biggest source of the FLAGGED warnings UK kept seeing on
    # completely ordinary responses. Now correctly captures group(1),
    # the bare word only.
    sentence_starts = set(m.group(1) for m in re.finditer(r"(?:^|[.!?]\s+)([A-Z][a-zA-Z']{2,})", response_text))

    def _numeric_match(token: str) -> bool:
        if not token.isdigit():
            return False
        if token in duration_numbers:
            return True
        return any(token.startswith(vocab_num) or vocab_num.startswith(token) for vocab_num in vocabulary_numbers)

    flagged = sorted(
        token for token in candidates
        if token not in sentence_starts
        and token.lower() not in vocabulary
        and token.lower() not in _COMMON_HINGLISH_WORDS
        and not _numeric_match(token)
    )

    # Refusal-hallucination check: a real observed failure was the LLM
    # inventing a justification for refusing an explicit user request
    # ("system rule says affirmative stays as 'bs UK'. I can't change
    # it.") when no such protective rule existed anywhere in the brief
    # -- the LLM fabricated a POLICY, not a fact, so the proper-noun/
    # number check above never catches this class of hallucination.
    # This is the concrete meaning of "LLM should strictly read the
    # schema and respond, never decide policy on its own": if the
    # response claims something is locked/protected/unchangeable, that
    # claim must be traceable to something actually in user_rules --
    # otherwise the LLM invented the refusal itself.
    refusal_pattern = re.compile(
        r"\b(?:can'?t|cannot|nahi\s+(?:badal|change)|not\s+allowed|system\s+rule|"
        r"rule\s+(?:ke\s+hisaab\s+se|says)|protected|locked|stays\s+as)\b", re.I,
    )
    unsupported_refusal = False
    if refusal_pattern.search(response_text):
        protective_language = re.compile(r"\b(?:never|hamesha|lock|protect|don'?t\s+(?:let|change)|keep\s+as|cannot\s+be\s+changed)\b", re.I)
        rules_text = " ".join(brief.get("user_rules") or [])
        if not protective_language.search(rules_text):
            unsupported_refusal = True
            flagged = flagged + ["[unsupported refusal: no protective rule found in brief]"]

    # False-confirmation-of-action check: a real, observed, trust-
    # breaking failure was the LLM telling the user "Akanksha ka naam
    # database mein hamesha ke liye store kar diya" when semantic
    # understanding had extracted ZERO relations that turn -- nothing
    # was actually stored, the LLM simply said what the user wanted to
    # hear. This is the mirror image of the refusal-hallucination check
    # above: instead of inventing a reason to REFUSE, this invents a
    # claim that an action SUCCEEDED. Only checked when the caller
    # actually knows how many relations this turn extracted (passing
    # None skips this check entirely rather than guessing).
    unsupported_confirmation = False
    if relations_extracted_this_turn is not None and relations_extracted_this_turn == 0:
        storage_claim = re.search(r"\b(?:stor(?:e|ed|ing)|sav(?:e|ed|ing)|not(?:e|ed|ing)|record(?:ed)?|likh)\w*\b", response_text, re.I)
        completion_word = re.search(r"\b(?:kar\s+diy\w*|kiya|kar\s+liy\w*|kar\s+lunga|done|hamesha\s+ke\s+liye)\b", response_text, re.I)
        if storage_claim and completion_word:
            unsupported_confirmation = True
            flagged = flagged + ["[unsupported confirmation: claims something was stored, but nothing was extracted this turn]"]

    # MECHANICAL addressing-rule enforcement -- not just an LLM prompt
    # instruction ("obey user_rules exactly") but an actual post-hoc
    # check, the same discipline as the other checks above. The most
    # concrete, checkable rule type observed throughout this project:
    # "Always call me X". If that rule is active AND the user's OTHER
    # known name differs from X, and the reply used the OTHER name
    # while never using X at all, that is a genuine, mechanically
    # detectable rule violation -- not a guess about phrasing style.
    rule_violation = False
    preferred_address = None
    for rule in brief.get("user_rules") or []:
        match = re.search(r"\balways\s+([A-Za-z][\w]{1,30})\b", str(rule), re.I)
        if match:
            preferred_address = match.group(1)
            break
    if preferred_address:
        real_name = None
        for fact in brief.get("known_facts") or []:
            name_match = re.match(r"^user\s+(?:full_)?name:\s*(.+)$", str(fact).strip(), re.I)
            if name_match:
                real_name = name_match.group(1).strip()
                break
        if real_name and real_name.lower() != preferred_address.lower():
            used_real_name = re.search(rf"\b{re.escape(real_name)}\b", response_text, re.I)
            used_preferred = re.search(rf"\b{re.escape(preferred_address)}\b", response_text, re.I)
            if used_real_name and not used_preferred:
                rule_violation = True
                flagged = flagged + [f"[rule violation: must always address as '{preferred_address}', but response used '{real_name}' instead]"]

    return GroundingCheck(stayed_within_brief=(len(flagged) == 0 and not unsupported_refusal and not unsupported_confirmation and not rule_violation), flagged_unsupported=flagged)


# Real production evidence (UK's overnight logs, 2026-09-08): the LLM
# repeatedly said things like "Resume READY entry hata di gayi hai,
# maine verify kiya" for a semantic-memory delete that NO code path
# actually performs -- JARVIS has zero chat-invokable forget/update
# skill (SemanticMemory.forget() exists but nothing calls it from a
# conversation turn). The system prompt itself was previously telling
# the LLM to "comply and confirm" such requests (fixed above in
# build_response_brief's instructions_for_llm), but a prompt
# instruction alone isn't a guarantee -- this is the detection-side
# safety net. Narrower and more confident than the general grounding
# check above (which only warns, on purpose, to avoid false-
# positiving a real reply): this only fires when NO action executed
# this turn at all, which is a hard, unambiguous fact, not a judgment
# call -- so unlike the general check, this one is safe to actually
# correct the response rather than just flag it.
_ACTION_CLAIM_PATTERNS = re.compile(
    r"\b(?:hata\s*di\s*gayi|hata\s*diy?a|delete\s*kar\s*(?:diy?a|liy?a)|"
    r"remove\s*kar\s*(?:diy?a|liy?a)|update\s*(?:ho\s*gaya|kar\s*(?:diy?a|liy?a))|"
    r"record\s*update|verify\s*kiy?a|save\s*kar\s*(?:diy?a|liy?a)|"
    r"note\s*le\s*liy?a|recording\s*start\s*ho\s*gayi)\b", re.I,
)


def check_action_claim_grounding(response_text: str, action_executed: bool) -> Optional[str]:
    """Returns a corrected, honest response if `response_text` claims
    a state-changing action happened while `action_executed` is
    False -- otherwise returns None (nothing to correct)."""
    if action_executed:
        return None
    text = str(response_text or "")
    if not _ACTION_CLAIM_PATTERNS.search(text):
        return None
    return (
        "Mujhe abhi delete/update/verify jaisa koi actual action perform karne ki "
        "capability nahi hai, isliye main yeh claim nahi karunga ki maine wo kar diya -- "
        "kyunki maine nahi kiya. Yeh feature abhi build nahi hua hai."
    )


@dataclass
class GroundingCheck:
    stayed_within_brief: bool
    flagged_unsupported: list


def detect_recall_miss(user_input: str, context: Dict[str, Any]) -> Optional[str]:
    """Companion to try_direct_recall_answer(), used for Evolution-of-
    LLM-fallbacks detection (blueprint section 48), NOT for answering.

    Returns the "asked_about" phrase ONLY for the specific case that
    matters for that detector: the recall PATTERN matched (this really
    is a "what is my X" question) but the predicate word isn't in
    _ASK_WORD_TO_PREDICATE, so no native answer was possible even
    though the question shape was exactly the kind native recall
    handles. That is a genuine, measurable "native coverage gap" --
    distinct from a pattern match that failed because no fact was
    stored (nothing to evolve there; that's just missing data, not a
    missing capability).
    """
    text = (user_input or "").strip()
    if not text or len(text) > 80:
        return None
    asked_about = None
    for pattern in _RECALL_PATTERNS:
        match = pattern.search(text)
        if match:
            asked_about = match.group(1).strip(" ?.!").lower()
            break
    if not asked_about:
        return None
    for word in _ASK_WORD_TO_PREDICATE:
        if word in asked_about:
            return None  # recognized -- not a coverage gap
    return asked_about


def _fact_line(item: Any) -> Optional[str]:
    """One Knowledge item -> one clean "subject predicate: value" line,
    instead of a raw dict repr. Accepts either a Knowledge-like object
    (attribute access) or its .to_dict() form (both appear across the
    codebase depending on call site).

    Namespace-labeled (blueprint section 38's non-negotiable rule: "a
    document-derived statement is evidence, not automatically: USER
    believes X"). Without this, a DOCUMENT-namespace fact and a
    PERSONAL-namespace fact were indistinguishable once formatted --
    the LLM had no signal telling it "the manual says X" apart from
    "you told me X". Only non-PERSONAL namespaces are labeled, so the
    common case (a fact the user stated directly) stays exactly as
    concise as before.
    """
    get = (lambda k: getattr(item, k, None)) if not isinstance(item, dict) else item.get
    subject = get("subject")
    predicate = get("predicate")
    value = get("value")
    if not subject or not predicate:
        return None
    predicate_readable = str(predicate).replace("_", " ")
    namespace = get("namespace") or "PERSONAL"
    if namespace and namespace != "PERSONAL":
        return f"[{namespace}] {subject} {predicate_readable}: {value}"
    return f"{subject} {predicate_readable}: {value}"


def _relation_line(item: Dict[str, Any]) -> Optional[str]:
    subject = item.get("subject")
    predicate = item.get("predicate")
    target = item.get("target")
    if not subject or not target:
        return None
    return f"{subject} -> {predicate or 'related_to'} -> {target}"


def _recap_line(item: Dict[str, Any]) -> Optional[str]:
    ctx = item.get("context") if isinstance(item, dict) else None
    if not isinstance(ctx, dict):
        return None
    user_said = ctx.get("user_input")
    if not user_said:
        return None
    return f"user previously said: {user_said}"


def get_self_authored_rules(memory: Any, limit: int = 10) -> List[str]:
    """JARVIS's own self-authored operating rules (see Brain's
    post-response reasoning: when the same recommendation repeats
    across enough turns, adopt_as_learning fires and a candidate rule
    gets written under subject="jarvis_self_rule"). Kept separate from
    UserRuleStore's user-stated rules -- these are what JARVIS itself
    has learned, not what the user told it.

    ONLY tags containing "confirmed" are returned here -- UK's explicit
    ask: a self-authored rule must be verified by her before it's
    allowed to influence responses. A freshly proposed rule is tagged
    "pending_confirmation" (see Brain._record_action_response's
    post-response reasoning block) and stays invisible to this function
    -- and therefore to every response brief -- until Brain.
    confirm_self_rule() marks it "confirmed". See cli.py's
    /pending_rules, /confirm_rule, /reject_rule.
    """
    semantic = getattr(memory, "semantic", memory)
    if semantic is None or not hasattr(semantic, "find"):
        return []
    try:
        items = semantic.find(subject="jarvis_self_rule")
    except Exception:
        return []
    items = [item for item in items if "confirmed" in (getattr(item, "tags", None) or [])]
    items = sorted(items, key=lambda k: getattr(k, "updated_at", 0), reverse=True)[:limit]
    return [str(getattr(item, "value", "")) for item in items if getattr(item, "value", None)]


def build_response_brief(
    *,
    user_input: str,
    perception: Dict[str, Any],
    context: Dict[str, Any],
    active_rules: List[str],
    self_authored_rules: Optional[List[str]] = None,
    bot_name: str = "JARVIS",
    creator_name: str = "UK",
    max_facts: int = 6,
    max_relations: int = 4,
    max_recap: int = 3,
) -> Dict[str, Any]:
    intent = perception.get("intent") if isinstance(perception.get("intent"), dict) else {}
    facts = [line for line in (_fact_line(i) for i in (context.get("relevant_knowledge") or [])[:max_facts]) if line]
    relations = [line for line in (_relation_line(i) for i in (context.get("graph_relations") or [])[:max_relations]) if line]
    recap = [line for line in (_recap_line(i) for i in (context.get("recent_experiences") or [])[:max_recap]) if line]

    # RESPONSE LANGUAGE SHOULD MATCH THE INPUT'S LANGUAGE (UK's explicit
    # ask), not be hardcoded to one style regardless of what was typed.
    # perception already detects this (perception["language"]) -- this
    # was previously computed and then never used for anything, so
    # "Hinglish" got hardcoded into every persona style unconditionally
    # even on a turn typed in plain English.
    detected_language = str(perception.get("language", "") or "").strip().lower()
    if detected_language == "en":
        style = "Natural English, concise, no emojis, loyal but a bit savage -- Iron Man's JARVIS tone"
    else:
        # "unknown"/"hi"/anything else defaults to Hinglish, since that
        # is genuinely the overwhelmingly common case in this project's
        # real usage -- but this is now a language-aware DEFAULT, not
        # an unconditional override of what the user actually typed in.
        style = "Hinglish, concise, no emojis, loyal but a bit savage -- Iron Man's JARVIS tone"

    return {
        "persona": {
            "name": bot_name,
            "creator": creator_name,
            "style": style,
        },
        "user_message": user_input,
        "detected_intent": {
            "name": intent.get("name") or "unknown",
            "confidence": round(float(intent.get("confidence", 0.0) or 0.0), 2),
        },
        "known_facts": facts,
        "known_relations": relations,
        "user_rules": list(active_rules),
        "jarvis_self_rules": list(self_authored_rules or []),
        "recent_context": recap,
        "instructions_for_llm": (
            "You are JARVIS's VOCAL CHORDS, not its brain. JARVIS's own "
            "cognition has already decided what happened and what matters -- "
            "everything you need is in known_facts/known_relations/user_rules "
            "above. Your only job is to give that decision a natural voice. "
            "Write ONE natural reply using ONLY the facts and relations listed "
            "above -- never invent a fact that isn't there, and never add your "
            "own interpretation, feeling, or judgment about the user that "
            "isn't already present in the data above. Obey every item in "
            "user_rules exactly, with no exceptions, even if it conflicts with "
            "your default style. jarvis_self_rules are behaviors JARVIS itself "
            "has learned from repeated past turns (not from the user) -- weigh "
            "these as strong defaults, but user_rules always win if they conflict. "
            "THE 'DON'T INVENT' RULE ABOVE APPLIES ONLY TO PERSONAL/PROJECT "
            "FACTS -- claims about UK himself, his life, his preferences, or "
            "this specific JARVIS project/codebase. It does NOT apply to "
            "general world knowledge (chemistry, geography, history, science, "
            "how things work, etc.) -- answer those normally from what you "
            "already know, the same way any knowledgeable assistant would, "
            "even though they aren't listed in known_facts (they wouldn't be -- "
            "known_facts only tracks things specifically learned about UK or "
            "this project, not general facts about the world). If a browser_search "
            "tool is available and the question needs current/real-time "
            "information you're unsure of, use it -- don't just say you don't "
            "know when you could check. Reserve 'I don't know that yet' "
            "specifically for personal/project facts that are genuinely absent "
            "from known_facts, not for ordinary questions about the world. "
            "Facts prefixed with a namespace "
            "tag like [DOCUMENT] came from an ingested document, not from the "
            "user directly -- phrase these as 'according to the document' or "
            "similar, never as something the user personally told you. "
            "Your job is strictly to turn the data above into natural language "
            "-- you do not decide policy. This specific reply-phrasing step "
            "does not itself execute actions -- but JARVIS DOES have real "
            "tools (available via tool-calling on turns where they're offered) "
            "to confirm/reject a proposed self-authored rule, resolve a "
            "contested fact, remove a standing instruction, and save a "
            "verified fact -- these are NOT hypothetical or 'not implemented'. "
            "If the user asks for one of these and no action result is present "
            "in known_facts/known_relations above, it means the action wasn't "
            "taken THIS turn (e.g. this phrasing step ran without tool access) "
            "-- say so honestly and suggest they try again or use the specific "
            "command, but NEVER claim outright that the capability doesn't "
            "exist when it does. NEVER say 'kar diya'/'update ho gaya'/"
            "'verify kiya'/'record se hata diya' or any other claim that a "
            "change happened when no result confirming it is present above --"
            " confirming a change that never happened is a lie, and JARVIS "
            "never lies about its own actions, even to be agreeable. Equally, "
            "never invent a justification for refusing (e.g. claiming 'system "
            "rule says X is locked') unless that protection is actually listed "
            "in user_rules."
        ),
    }


# ---------------------------------------------------------------------
# Native direct-answer fast path (zero LLM calls when it fires)
# ---------------------------------------------------------------------

_RECALL_PATTERNS = [
    re.compile(r"\bmer[ai]\s+(.+?)\s+(?:kya\s+hai|kya\??|batao)\b", re.I),
    re.compile(r"\bwhat(?:'s| is)\s+my\s+(.+?)\s*\??\s*$", re.I),
]

# Same spirit as SemanticMemory._PREDICATE_ALIASES: map the noun the
# user actually asked with onto the predicate word facts are stored
# under, so "mera favourite color" matches a fact stored under
# predicate "favourite" (the value already says "color black").
_ASK_WORD_TO_PREDICATE = {
    "favourite": "favourite", "favorite": "favourite", "fav": "favourite",
    "naam": "name", "name": "name",
    "hobby": "hobby", "hobbies": "hobby", "shauk": "hobby",
    "editor": "prefers_editor",
}


# Third-party relationship words -- when "asked_about" contains one of
# these, the question is about SOMEONE ELSE's property, not the
# user's own. A real, severe bug this fixes directly: "meri girlfriend
# ka naam batao?" was answered using whatever fact had predicate="name"
# in memory REGARDLESS OF SUBJECT -- since the user's OWN name was
# usually the only "name"-predicate fact stored, the answer came back
# as the user's own name instead of the girlfriend's, every time.
_THIRD_PARTY_SUBJECT_WORDS = {
    "girlfriend", "boyfriend", "wife", "husband", "friend", "dost",
    "mom", "mummy", "maa", "dad", "papa", "pita", "sister", "behen",
    "brother", "bhai", "colleague", "boss", "teacher", "gf", "bf",
}


def try_direct_recall_answer(user_input: str, context: Dict[str, Any], on_hit: Optional[Any] = None) -> Optional[str]:
    """Deliberately narrow: only fires for a simple "what is my X"
    phrasing with an exact predicate match against an already-retrieved
    fact. Anything even slightly ambiguous falls through to the LLM
    route unchanged -- this must never guess wrong to save a call.

    `on_hit`, if given, is called with the matched knowledge item right
    before returning -- this is the hook NativeReasoner uses to
    reinforce a fact's confidence when it's actually recalled (the
    testing-effect-inspired spaced-repetition feature: SemanticMemory
    already had .reinforce()/.weaken() methods, built but never called
    from anywhere -- this is the real call site). Optional and
    exception-safe so it can never turn a successful recall into a
    failed one."""
    text = (user_input or "").strip()
    if not text or len(text) > 80:
        return None

    asked_about = None
    for pattern in _RECALL_PATTERNS:
        match = pattern.search(text)
        if match:
            asked_about = match.group(1).strip(" ?.!").lower()
            break
    if not asked_about:
        return None

    predicate_guess = None
    for word, predicate in _ASK_WORD_TO_PREDICATE.items():
        if word in asked_about:
            predicate_guess = predicate
            break
    if predicate_guess is None:
        return None

    # Whose property is actually being asked about -- "user" (the
    # default, "meri/mera X") unless a third-party word appears in the
    # asked phrase itself ("meri GIRLFRIEND ka naam"), in which case
    # the fact must be looked up under THAT subject, never silently
    # substituted with the user's own matching-predicate fact.
    subject_guess = "user"
    for word in _THIRD_PARTY_SUBJECT_WORDS:
        if word in asked_about:
            subject_guess = word
            break

    for item in context.get("relevant_knowledge") or []:
        get = (lambda k: getattr(item, k, None)) if not isinstance(item, dict) else item.get
        predicate = str(get("predicate") or "").lower()
        subject = str(get("subject") or "").lower()
        if predicate == predicate_guess and subject == subject_guess:
            value = get("value")
            if value:
                value_text = str(value).strip()
                # Avoid "favourite color color black" when the stored
                # value already repeats the noun the user asked with --
                # strip that leading repeated word before phrasing.
                asked_last_word = asked_about.split()[-1] if asked_about.split() else asked_about
                if value_text.lower().startswith(asked_last_word.lower() + " "):
                    value_text = value_text[len(asked_last_word):].strip()
                if on_hit is not None:
                    try:
                        on_hit(item)
                    except Exception:
                        pass
                return f"Aapka {asked_about} {value_text} hai."
    return None
