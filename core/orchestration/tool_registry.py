from __future__ import annotations

"""LLM tool-calling: registry, dispatch, and the gating loop.

DESIGN RATIONALE (2026-09-11 discussion with UK): UK explicitly
rejected hardcoded regex for routing natural-language requests like
"pending rules dikhao" or "yeh rule reject karo" to Brain's memory-
management methods -- "Jarvis khud apne dimag se samjhe, regex nahi."
That's correct: regex here would just be Claude pre-deciding intent
on JARVIS's behalf, not JARVIS understanding anything itself.

The actual fix is standard LLM tool/function calling (see Groq's
docs, console.groq.com/docs/tool-use/overview, verified 2026-09-11):
the model itself reads the message, decides whether a tool is
relevant, and if so which one and with what arguments -- using its
own language understanding, not a pattern JARVIS's author wrote by
hand.

Architecturally this is modeled on the cortex-basal ganglia loop
(cortex proposes candidate actions; basal ganglia GATES which one
actually executes, via Go/NoGo pathways -- see e.g. Baston &
Ursino 2015, "A Biologically Inspired Computational Model of Basal
Ganglia in Action Selection"): the LLM ("cortex") PROPOSES a tool
call, but nothing executes until dispatch_tool_call() below ("basal
ganglia") gates it -- specifically, verifying a MUTATING call's
knowledge_id actually refers to a real, currently-pending/active item
before touching any real state. This is a cheap, native, zero-extra-
LLM-call check, not a second model call -- same "native before
expensive" discipline as the rest of JARVIS.

Tools available:
  - The 6 Brain methods for self-authored-rule / standing-instruction
    management (previously CLI-only: /pending_rules, /confirm_rule,
    /reject_rule, /explain_rule, /instructions, /remove_instruction).
  - browser_search: Groq's built-in, server-side web search tool
    (verified 2026-09-11 against console.groq.com/docs/tool-use/
    built-in-tools/browser-search -- supported directly by
    openai/gpt-oss-120b, JARVIS's configured model; no separate API
    key or search service needed). This is the concrete fix for
    2026-09-11 roadmap Phase 4 (knowledge-gap verification / "H2O"
    case): JARVIS can now actually check a real source instead of
    only answering from the LLM's parametric memory.
"""

import json
from typing import Any, Dict, List, Optional

from ..runtime.log import log_event

READ_ONLY_TOOLS = {"list_pending_self_rules", "explain_self_rule", "list_standing_instructions", "list_contested_facts"}
MUTATING_TOOLS = {"confirm_self_rule", "reject_self_rule", "remove_standing_instruction", "resolve_contested_fact"}
# Distinct from MUTATING_TOOLS above: this doesn't touch an EXISTING
# item by knowledge_id, it creates a new one -- see save_verified_fact()
# in brain.py. UK's explicit ask (2026-09-11): searched/LLM-derived
# facts must NOT be persisted by default (fills the database with
# one-off lookups nobody asked to keep) -- only when UK explicitly
# says so ("search karke save karo", "yaad rakho"). The tool's own
# description below carries that restriction to the model; gating
# here just validates the fields are non-empty, not a knowledge_id.
WRITE_TOOLS = {"save_verified_fact"}
LOCAL_TOOL_NAMES = READ_ONLY_TOOLS | MUTATING_TOOLS | WRITE_TOOLS

MAX_TOOL_ITERATIONS = 3

# Appended to the system prompt only for tool-enabled turns (see
# run_tool_loop below) -- UK's explicit ask: browser_search use must
# be disclosed in the reply, but the source/URL only stated if UK
# actually asks for it, not dumped every time.
_SEARCH_TRANSPARENCY_INSTRUCTION = (
    "\n\nTOOL USE DISCLOSURE: If you use browser_search to answer, briefly say in your reply "
    "that you checked current/online information for this (so it's clear it wasn't just from "
    "memory) -- but do NOT list specific URLs, article titles, or source names unless UK "
    "explicitly asks where the information came from."
)


def build_tool_schemas() -> List[Dict[str, Any]]:
    """OpenAI-format function-calling schemas (verified against Groq's
    tool-use docs, 2026-09-11) plus Groq's built-in browser_search.
    Descriptions explicitly tell the model NOT to guess a knowledge_id
    -- it must call the matching list_* tool first and read the real
    id back, since dispatch_tool_call() below will reject a fabricated
    one anyway (cheaper for everyone if the model doesn't try)."""
    id_note = (
        " Results are returned in the same order shown to UK elsewhere "
        "(e.g. cli.py's #0, #1, #2...), so if UK refers to an item by "
        "number, that number is this array's index."
    )
    return [
        {"type": "function", "function": {
            "name": "list_pending_self_rules",
            "description": (
                "List self-authored rules JARVIS has proposed about its own behavior that are "
                "awaiting UK's review (confirm or reject). Use when UK asks to see pending rules "
                "(e.g. 'pending rules dikhao', 'kya rule pending hai')." + id_note
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        {"type": "function", "function": {
            "name": "explain_self_rule",
            "description": (
                "Explain WHY a specific self-authored rule was proposed -- the actual supporting "
                "reasoning evidence, not just the rule text. Use when UK asks 'why did you make "
                "this rule' / 'yeh rule kyun banaya'. Call list_pending_self_rules first if you "
                "don't already have the real knowledge_id -- never guess one."
            ),
            "parameters": {"type": "object", "properties": {
                "knowledge_id": {"type": "string", "description": "The rule's knowledge_id, from list_pending_self_rules."}
            }, "required": ["knowledge_id"]},
        }},
        {"type": "function", "function": {
            "name": "confirm_self_rule",
            "description": (
                "Confirm a pending self-authored rule so it starts influencing JARVIS's future "
                "responses. Only call when UK has clearly approved a SPECIFIC rule. Call "
                "list_pending_self_rules first if you don't already have the real knowledge_id "
                "-- never guess one."
            ),
            "parameters": {"type": "object", "properties": {
                "knowledge_id": {"type": "string", "description": "The rule's knowledge_id to confirm."}
            }, "required": ["knowledge_id"]},
        }},
        {"type": "function", "function": {
            "name": "reject_self_rule",
            "description": (
                "Reject a pending self-authored rule. JARVIS will remember the rejection and "
                "won't re-propose the identical rule later. Only call when UK has clearly "
                "declined a SPECIFIC rule. Call list_pending_self_rules first if you don't "
                "already have the real knowledge_id -- never guess one."
            ),
            "parameters": {"type": "object", "properties": {
                "knowledge_id": {"type": "string", "description": "The rule's knowledge_id to reject."}
            }, "required": ["knowledge_id"]},
        }},
        {"type": "function", "function": {
            "name": "list_standing_instructions",
            "description": (
                "List active daily standing instructions (time-triggered actions UK asked JARVIS "
                "to do every day, e.g. 'roz subah good morning bolo') and their trigger times."
                + id_note
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        {"type": "function", "function": {
            "name": "remove_standing_instruction",
            "description": (
                "Delete a standing instruction outright. Only call when UK has clearly asked to "
                "remove a SPECIFIC instruction. Call list_standing_instructions first if you "
                "don't already have the real knowledge_id -- never guess one."
            ),
            "parameters": {"type": "object", "properties": {
                "knowledge_id": {"type": "string", "description": "The instruction's knowledge_id to remove."}
            }, "required": ["knowledge_id"]},
        }},
        {"type": "function", "function": {
            "name": "save_verified_fact",
            "description": (
                "Persist a fact to JARVIS's long-term memory. ONLY call this when UK EXPLICITLY "
                "asks to save/remember/store a specific fact -- e.g. 'search karke save kar do', "
                "'yaad rakhna ki...', 'memory mein daal do'. Do NOT call this just because you "
                "looked something up with browser_search -- most searches are for answering the "
                "immediate question only and must NOT be persisted, or memory fills with one-off "
                "lookups nobody asked to keep. If UK did not explicitly ask you to save/remember "
                "it, do not call this tool, even if the answer came from a search."
            ),
            "parameters": {"type": "object", "properties": {
                "subject": {"type": "string", "description": "What/who the fact is about, e.g. 'magnesium'."},
                "predicate": {"type": "string", "description": "The attribute/relationship, e.g. 'atomic_number'."},
                "value": {"type": "string", "description": "The fact's value, e.g. '12'."},
            }, "required": ["subject", "predicate", "value"]},
        }},
        {"type": "function", "function": {
            "name": "list_contested_facts",
            "description": (
                "List facts where a less-trusted source (e.g. an unverified guess) tried to "
                "overwrite a more-trusted one and was held back instead of silently applied. "
                "Use when UK asks about contradictions/contested facts/'conflicting info'."
            ) + id_note,
            "parameters": {"type": "object", "properties": {}, "required": []},
        }},
        {"type": "function", "function": {
            "name": "resolve_contested_fact",
            "description": (
                "Resolve a contested fact: either accept the newly-proposed value (replacing the "
                "current one) or keep the current value and dismiss the proposal. Only call when "
                "UK has clearly decided which one is right. Call list_contested_facts first if you "
                "don't already have the real knowledge_id -- never guess one."
            ),
            "parameters": {"type": "object", "properties": {
                "knowledge_id": {"type": "string", "description": "The contested fact's knowledge_id."},
                "accept_new_value": {"type": "boolean", "description": "True to accept the proposed new value, false to keep the current one."},
            }, "required": ["knowledge_id", "accept_new_value"]},
        }},
        # Groq built-in, server-side web search -- see module docstring.
        # No local dispatch needed: Groq executes this itself and
        # returns the synthesized, cited answer directly in
        # message.content (see run_tool_loop()'s handling below).
        {"type": "browser_search"},
    ]


def dispatch_tool_call(brain: Any, name: str, args: Dict[str, Any], search_used_this_turn: bool = False) -> Dict[str, Any]:
    """THE GATE (see module docstring). Validates before executing;
    never trusts the model's arguments blindly for a mutating/write call."""
    if name not in LOCAL_TOOL_NAMES:
        return {"error": f"unknown or non-local tool: {name}"}
    method = getattr(brain, name, None)
    if not callable(method):
        return {"error": f"tool '{name}' is not available on this Brain instance"}

    if name in MUTATING_TOOLS:
        knowledge_id = args.get("knowledge_id")
        if not knowledge_id:
            return {"error": "knowledge_id is required"}
        if name in ("confirm_self_rule", "reject_self_rule"):
            valid_ids = {r.get("knowledge_id") for r in brain.list_pending_self_rules()}
        elif name == "resolve_contested_fact":
            valid_ids = {r.get("knowledge_id") for r in brain.list_contested_facts()}
        else:  # remove_standing_instruction
            valid_ids = {r.get("knowledge_id") for r in brain.list_standing_instructions()}
        if knowledge_id not in valid_ids:
            return {
                "error": (
                    f"knowledge_id '{knowledge_id}' does not match any current item. "
                    "Call the matching list_* tool first to get real ids -- do not guess."
                )
            }

    if name in WRITE_TOOLS:
        subject, predicate, value = args.get("subject"), args.get("predicate"), args.get("value")
        if not subject or not predicate or value in (None, ""):
            return {"error": "subject, predicate and value are all required"}
        if any(len(str(v)) > 300 for v in (subject, predicate, value)):
            return {"error": "subject/predicate/value must each be under 300 characters"}
        # source_type honesty (see core/memory/semantic_memory.py's
        # provenance system): "verified" only if browser_search
        # actually ran earlier THIS turn -- if the model is saving
        # something from its own parametric memory on request, that's
        # still unverified, just now durable instead of ephemeral.
        args = {**args, "source_type": "verified" if search_used_this_turn else "llm_unverified"}

    try:
        return method(**args) if args else method()
    except Exception as exc:
        log_event("tool_registry", f"tool '{name}' execution failed: {exc}", level="warning")
        return {"error": str(exc)}


def run_tool_loop(brain: Any, system_prompt: str, user_message: str,
                   max_iterations: int = MAX_TOOL_ITERATIONS) -> Optional[str]:
    """Runs the propose -> gate -> execute -> re-evaluate loop until the
    model returns a final answer (no more tool_calls) or iterations run
    out. Returns None if tool-calling isn't usable this turn at all
    (caller -- see Brain's response-generation block -- must fall back
    to the existing plain generate() path unchanged); returns None
    (not a stub string) if the loop exhausts its iterations without a
    final answer too, for the same reason.

    IMPORTANT (openai/gpt-oss-120b doesn't support parallel tool use,
    verified against Groq's docs 2026-09-11): a compound instruction
    like "X search karo aur save karo" cannot be one tool call that
    does both -- browser_search (built-in, resolves fully server-side
    in a single completion) has to be followed by a SEPARATE local
    save_verified_fact call in a LATER iteration, once the model has
    seen the search result. So a built-in tool firing does NOT end
    the loop here the way a genuinely final answer does -- the model
    gets one more turn to decide if a local follow-up action is still
    needed, nudged by a synthetic system message rather than assumed
    silently either way.

    The full tool-call trace is recorded on brain.last_tool_call_trace
    (bounded, most-recent-turn only) so monitor.py / a future API
    endpoint can show exactly which tools fired and why -- UK's
    explicit ask that autonomous actions stay traceable, not a black
    box."""
    llm = getattr(brain, "llm", None)
    if llm is None or not hasattr(llm, "generate_with_tools"):
        return None

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt + _SEARCH_TRANSPARENCY_INSTRUCTION},
        {"role": "user", "content": user_message},
    ]
    tools = build_tool_schemas()
    trace: List[Dict[str, Any]] = []
    search_used_this_turn = False

    for iteration in range(max(1, max_iterations)):
        message = llm.generate_with_tools(messages=messages, tools=tools, tool_choice="auto", reasoning_effort="low")
        if message is None:
            brain.last_tool_call_trace = trace
            return None

        tool_calls = message.get("tool_calls") or []
        executed = message.get("executed_tools")

        if tool_calls:
            messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": tool_calls})
            for call in tool_calls:
                fn = call.get("function", {}) or {}
                name = fn.get("name")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = dispatch_tool_call(brain, name, args, search_used_this_turn=search_used_this_turn)
                trace.append({"name": name, "arguments": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
            continue

        if executed:
            # Built-in tool (browser_search) resolved server-side.
            # STRUCTURED capture (2026-09-11, UK's explicit ask): keep
            # the actual title/url/content/score records JARVIS itself
            # can inspect and reason about later -- not just a
            # truncated str() blob of whatever Groq returned. This is
            # what "JARVIS ko pata rahe usne kya paya" means in
            # practice: the search_results live in Brain's own trace
            # (see list_tool_call_trace/monitor.py/CLI's /tool_trace),
            # independent of whatever prose the LLM chose to write in
            # its reply. The reply text itself still comes from the
            # model's message.content this pass (Groq's browser_search
            # already does real synthesis+citation in one call) --
            # routing that through a SECOND constrained brief-style
            # pass (matching response_brief.py's "LLM only phrases,
            # never invents" pattern) is the natural next step, not
            # done this pass.
            search_used_this_turn = True
            structured_results = []
            try:
                for tool_exec in (executed if isinstance(executed, list) else [executed]):
                    if isinstance(tool_exec, dict):
                        results = tool_exec.get("search_results") or {}
                        for item in (results.get("results") or []) if isinstance(results, dict) else []:
                            structured_results.append({
                                "title": item.get("title"), "url": item.get("url"),
                                "content": item.get("content"), "score": item.get("score"),
                            })
            except Exception:
                structured_results = []
            trace.append({
                "builtin_tool": True,
                "executed_tools_summary": str(executed)[:500],
                "search_results": structured_results,
            })
            if iteration < max_iterations - 1:
                messages.append({"role": "assistant", "content": message.get("content")})
                messages.append({
                    "role": "system",
                    "content": (
                        "If the original request also explicitly asked you to save/remember this "
                        "fact, call save_verified_fact now with the right subject/predicate/value. "
                        "Otherwise, just repeat your answer above as the final response -- do not "
                        "search again."
                    ),
                })
                continue
            # Out of iterations to safely follow up -- return what we have.
            brain.last_tool_call_trace = trace
            content = message.get("content")
            return str(content).strip() if content else None

        # Genuinely final: no tool call, no built-in tool fired.
        content = message.get("content")
        brain.last_tool_call_trace = trace
        return str(content).strip() if content else None

    brain.last_tool_call_trace = trace
    return None
