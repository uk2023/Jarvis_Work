# -*- coding: utf-8 -*-
<<<<<<< HEAD
=======
"""JARVIS terminal/runtime control interface.

The CLI is intentionally a runtime control surface, not a second cognition
engine. While idle it continuously monitors the organism's real lifecycle and
organ health. When a query arrives, the active Brain produces the single
cognitive turn and deep_inspector.py renders that exact turn data.
"""

# MEMORY LIMITS FIRST (2026-09-14). Must run before onnxruntime is
# imported anywhere in the process -- ORT reads OMP_NUM_THREADS etc. at
# import time, and by the time core/memory/*.py imports it, it is too
# late. This is the actual fix for the crash UK's resource samples
# showed: RSS jumping from 172MB to 1897MB in under 15 seconds with
# 789MB free on the device. See core/runtime/memory_limits.py for the
# full account.
try:
    from core.runtime.memory_limits import apply_process_limits
    apply_process_limits()
except Exception:
    pass

>>>>>>> 90fbd2a (Save local project changes before branch checkout)
import os
import sys
import time
import warnings
import threading
import traceback
import importlib
import hashlib

# --- System & Environment Setup ---
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
warnings.filterwarnings("ignore")

# Dynamic Root Path: Termux/Android ke dynamic directory ko automatically detect karega
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from core.organism.bootstrap import start_jarvis, stop_jarvis
from core.orchestration.llm_bridge import LlamaCppBridge
from core.organism.organ_descriptions import describe_organ

console = Console()

# --- Global State & Threading Synchronization ---
web_event_broadcaster = None
model_lock = threading.Lock()
<<<<<<< HEAD
_global_jarvis_instance = None  # Global reference for dynamic engine resolver
=======
_global_jarvis_instance = None
_frontend_process = None
_cli_monitor = None

CLI_COMMANDS = {
    "/help": "Show available JARVIS CLI commands",
    "/about": "Show JARVIS runtime and architecture information",
    "/memory_inspect": "Inspect live semantic memory, FAISS/search and graph state",
    "/trace_inspect": "Inspect the latest exact cognitive trace",
    "/tool_trace": "Show the last turn's LLM tool calls (list_pending_self_rules, browser_search, etc.) -- which tools the model decided to use and what each returned",
    "/runtime_inspect": "Inspect live runtime, heartbeat, queues and metrics",
    "/organ_inspect": "Inspect all attached organism organs and their state",
    "/organ_introspect": "Evidence-backed 10-question introspection for perception/semantic-understanding/brain -- never a bare 'working correctly'",
    "/login": "Identify yourself to view restricted traces: /login <username> (password prompt). /logout to drop it. Starting JARVIS never needs this.",
    "/trace": "View identity-tagged traces: /trace (yours) | /trace all | /trace user <name> | /trace role <role> | /trace session <id> | /trace req <id> | /trace who",
    "/diagnose": "JARVIS diagnoses itself: what's wrong, why, and the fix. /diagnose fix applies every safe auto-remedy; /diagnose fix <name> applies just one.",
    "/owner": "Owner/co-owner account management: /owner status | /owner set <username> | /owner cowner <username> | /owner remove <username> | /owner passwd",
    "/think": "Extended thinking: /think off | auto | on (auto = JARVIS khud decide karega)",
    "/codebox": "Open a live coding session in your own sandbox (separate from chat)",
    "/pending_rules": "List self-authored rules JARVIS has proposed but you haven't confirmed yet",
    "/confirm_rule <n>": "Confirm pending self-authored rule #n (from /pending_rules) -- only then does it start influencing responses",
    "/reject_rule <n>": "Reject pending self-authored rule #n -- remembered as rejected, so the identical rule won't be re-proposed later",
    "/explain_rule <n>": "Show WHY JARVIS proposed pending self-authored rule #n -- the actual reasoning evidence, not just the final rule text",
    "/instructions": "List active daily standing instructions (e.g. \"roz subah good morning bolo\") and their next trigger time",
    "/remove_instruction <n>": "Delete standing instruction #n (from /instructions) outright",
    "/contested_facts": "List facts where a less-trusted source tried to overwrite a more-trusted one and was held back for your review",
    "/resolve_contested <n> <accept|keep>": "Resolve contested fact #n (from /contested_facts) -- accept applies the proposed new value, keep discards it",
    "/llm_dependency": "Show how much of semantic understanding is resolved natively vs via LLM this session",
    "/grounding_violations": "Show recurring categories of response-vs-brief mismatches this session",
    "/pending_patterns": "List extraction patterns JARVIS wrote and sandbox-tested itself, awaiting your review",
    "/confirm_pattern <n>": "Approve pattern #n (from /pending_patterns) -- only then does it run live",
    "/reject_pattern <n>": "Decline pattern #n -- remembered as rejected, won't be re-proposed identically",
    "/remote": "Start a public ngrok tunnel so JARVIS is reachable from outside your local network",
    "/remote_stop": "Stop the ngrok tunnel started by /remote",
    "/self_evolution": "Show what JARVIS has adopted on its own (rules + patterns) without waiting for your approval",
    "/voice": "Toggle text-to-speech for JARVIS's replies. /voice list shows installed voices/engines, /voice set <name> picks one (requires Termux:API app + `pkg install termux-api`)",
    "/listen": "Speak your message instead of typing it -- captures one utterance, transcribes it, and sends it exactly like typed text (requires Termux:API app + `pkg install termux-api`)",
    "/voice_pitch": "Shortcut for /voice pitch <n>",
    "/voice_rate": "Shortcut for /voice rate <n>",
    "/verbose": "Toggle the additional full raw per-layer contract/schema trace (organized workflow panel always shows)",
    "/ingest_document <path>": "Ingest a text file into Document Knowledge (namespace-tagged, never treated as a personal fact)",
}

# Off by default: the full deep_inspector trace (raw contract payloads,
# per-layer validation status) used to render unconditionally after
# EVERY message, which is exactly what made "output bahut crowded lagta
# hai" -- both this dump and the OrganismCLIMonitor background thread
# were writing into the same console on top of the chat itself. Full
# detail is still one command away (/trace_inspect, or toggle this on),
# and it's always available live in a second session via `python3
# monitor.py` without touching this console at all.
_verbose_trace = os.getenv("JARVIS_CLI_VERBOSE", "").strip().lower() in {"1", "true", "yes", "on"}
_voice_enabled = False

>>>>>>> 90fbd2a (Save local project changes before branch checkout)

def print_banner():
    banner = Panel.fit(
        "[bold cyan]JARVIS COGNITIVE OS[/bold cyan] [dim text-gray]v2026.1[/dim text-gray]\n"
        "[dim white]Real-time Subsystem Metrics & Neural Diagnostics Control Unit[/dim white]",
        border_style="cyan",
        subtitle="[dim]UK ARCHITECTURE WORKSPACE[/dim]"
    )
    console.print(banner)

def render_organ_matrix(jarvis):
    table = Table(
        title="SYSTEM SUBSYSTEM & ORGAN DIAGNOSTICS MATRIX",
        border_style="blue",
        header_style="bold cyan",
        title_style="bold white"
    )
    table.add_column("Organ Designation", style="bold white", width=22)
    table.add_column("Class Type", style="dim white", width=20)
    table.add_column("State", justify="center", width=12)
    table.add_column("Operational Role & Diagnostics", style="dim")

    organs_status = jarvis.get_organ_status() if hasattr(jarvis, "get_organ_status") else {}

    # NOTE: this table used to only recognise 9 hardcoded organ names.
    # bootstrap.py now attaches the autonomy + skills organs too
    # (goal_manager, curiosity, scheduler, planner, idle_loop,
    # skill_registry, skill_executor, skill_learner) — they were still
    # being looped over and printed before, just always labelled
    # "Auxiliary Operational Organ" with no real diagnostics. Role
    # text + live diagnostics now come from
    # core/organism/organ_descriptions.py, shared with the web
    # backend's /api/organism/state so both surfaces agree.
    for name, info in organs_status.items():
        is_attached = info.get("attached", False)
        status_text = "[bold green]ONLINE[/bold green]" if is_attached else "[bold red]OFFLINE[/bold red]"
        table.add_row(name, info.get("type", "Subsystem"), status_text, describe_organ(jarvis, name, info))

    hb_status = jarvis.heartbeat.status() if hasattr(jarvis, "heartbeat") and jarvis.heartbeat else {}
    hb_text = "[bold green]ACTIVE[/bold green]" if hb_status.get("running") else "[bold red]STOPPED[/bold red]"
    hb_metrics = f"Beat Pulses: {hb_status.get('beat_count', 0)} | Idle State: {hb_status.get('is_idle', False)}"
    table.add_row("heartbeat_daemon", "Background Thread", hb_text, hb_metrics)

    # The async learning queue lives inside Brain, not in
    # jarvis.organs, so get_organ_status() never surfaces it. Without
    # this row the entire "response sync, learning async" pipeline was
    # invisible in diagnostics — you could not tell whether learning
    # was keeping up, stalled, or silently failing in the background.
    brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
    if brain is not None and hasattr(brain, "status"):
        try:
            queue_status = brain.status().get("async_learning_queue", {})
        except Exception:
            queue_status = {}
        q_alive = queue_status.get("alive", False)
        q_text = "[bold green]ACTIVE[/bold green]" if q_alive else "[bold red]STOPPED[/bold red]"
        q_metrics = (
            f"Pending: {queue_status.get('pending', 0)} | "
            f"Processed: {queue_status.get('processed', 0)} | "
            f"Failed: {queue_status.get('failed', 0)} | "
            f"Dropped: {queue_status.get('dropped', 0)}"
        )
        table.add_row("async_learning_queue", "Background Thread", q_text, q_metrics)

    # "llm" is likewise never a registered organ -- it's just
    # brain.llm, assigned after start_jarvis() returns (see main()
    # below). That meant this diagnostics table had NO row at all for
    # whether the model was actually connected/working, which is the
    # single most important thing to see when "model se communicate
    # nahi ho raha". Sourced from the real is_ready/last_error added
    # to HybridLLMBridge, not just "attribute is not None".
    llm_bridge = getattr(brain, "llm", None) if brain is not None else None
    if llm_bridge is not None:
        is_ready = getattr(llm_bridge, "is_ready", False)
        last_error = getattr(llm_bridge, "last_error", None)
        model_name = getattr(llm_bridge, "_model_filename", "unknown.gguf")
        if is_ready:
            llm_text = "[bold green]ONLINE[/bold green]"
            llm_metrics = f"Qwen offline bridge | model={model_name} | verified loaded"
        elif last_error:
            llm_text = "[bold red]FAILED[/bold red]"
            llm_metrics = f"model={model_name} | error: {last_error}"
        else:
            llm_text = "[bold yellow]UNVERIFIED[/bold yellow]"
            llm_metrics = f"model={model_name} | not yet loaded (no message sent, or verify_offline_ready() not called)"
        table.add_row("llm", "HybridLLMBridge", llm_text, llm_metrics)
    else:
        table.add_row("llm", "HybridLLMBridge", "[bold red]DISCONNECTED[/bold red]", "brain.llm is None -- never connected")

    console.print(table)

def render_cognition_trace(trace: dict, source: str = "cli"):
    """
    Renders directly from Brain.last_turn_trace -- the single real
    record of what happened this turn (see think_and_respond()).
    No separate retrieval/timing is done here anymore; this used to
    call build_context() a SECOND time just to build the trace, which
    meant every turn paid for FAISS/DB retrieval twice.
    """
    if not trace:
        console.print(Panel("[dim]No trace data available for this turn.[/dim]", border_style="dim"))
        return

    timings = trace.get("timings", {})
    total_time = timings.get("total", 0.0)
    tree = Tree(f"[bold cyan]COGNITIVE EXECUTION TRACE[/bold cyan] [dim](Source: {source.upper()} | Latency: {total_time:.3f}s)[/dim]")

    tree.add(f"[bold yellow]Event Ingestion:[/bold yellow] USER_INPUT via '{source}' interface")

    typos = trace.get("typos_corrected", [])
    if typos:
        typo_str = ", ".join(f"{t['raw']}→{t['corrected']}" for t in typos[:6])
        tree.add(f"[bold yellow]Typo Normalization:[/bold yellow] {typo_str}")

    mem = trace.get("memory", {})
    mem_branch = tree.add(f"[bold blue]Memory Subsystem Search[/bold blue] [dim]({timings.get('memory', 0.0):.3f}s)[/dim]:")

    if mem.get("recent_experiences"):
        mem_branch.add(f"[bold green]FAISS Vector Index:[/bold green] Retrieved {mem['recent_experiences']} matching frames")
    else:
        mem_branch.add("[bold yellow]FAISS Vector Index:[/bold yellow] 0 direct vector matches")

    vector_matches = trace.get("vector_matches", [])
    if vector_matches:
        top = vector_matches[0]
        mem_branch.add(f"Top Match: [dim]{top.get('subject')} -> {top.get('predicate')} -> {top.get('value')} (sim {top.get('similarity')})[/dim]")

    if mem.get("relevant_knowledge") or mem.get("graph_relations"):
        mem_branch.add(f"[bold green]NetworkX Knowledge Graph:[/bold green] Injected {mem.get('relevant_knowledge', 0)} facts, {mem.get('graph_relations', 0)} structural relations")
    else:
        mem_branch.add("[bold dim]Knowledge Graph:[/bold dim] No explicit graph links detected")

    # Learning is now asynchronous (see core/learning/learning_queue.py),
    # so this turn's experience is NOT "logged & validated" by the time
    # we get here — it was only just handed to the background queue.
    # Claiming it was already validated (the old behaviour) was actively
    # misleading, since the real work happens after this trace prints.
    pipe_branch = tree.add("[bold magenta]Learning Pipeline (async):[/bold magenta]")
    if trace.get("pipeline_success"):
        qs = trace.get("learning_queue", {})
        signal = trace.get("memory_signal")
        signal_str = "no fact detected this turn" if not signal else f"candidate fact: {signal.get('subject')}={signal.get('value')}"
        pipe_branch.add(
            f"[bold green]Queued[/bold green] for background learning ({signal_str}) "
            f"(queue pending={qs.get('pending', '?')}, "
            f"processed so far={qs.get('processed', '?')}, "
            f"failed={qs.get('failed', '?')})"
        )
    else:
        pipe_branch.add("[bold red]Pipeline State:[/bold red] Processing incomplete or bypassed")

    llm_time = timings.get("llm", 0.0)
    tree.add(f"[bold green]Neural Inference (Qwen, single combined call):[/bold green] Context synthesized -> response + memory_signal [dim]({llm_time:.2f}s)[/dim]")

<<<<<<< HEAD
    console.print(Panel(tree, border_style="dim", title="[bold white]Diagnostics[/bold white]", subtitle="[dim]Trace ID: TRC-LIVE[/dim]"))
=======
def render_runtime_inspection(jarvis):
    table = Table(title="JARVIS RUNTIME INSPECTION", border_style="green", header_style="bold green")
    table.add_column("Runtime Signal", style="bold white", width=30)
    table.add_column("Live State", style="cyan")
    state = getattr(jarvis, "state", None)
    state_data = {}
    if state is not None:
        try:
            state_data = state.to_dict() if hasattr(state, "to_dict") else getattr(state, "__dict__", {})
        except Exception:
            state_data = {}
    hb = _safe_dict(jarvis.heartbeat.status() if getattr(jarvis, "heartbeat", None) else {})
    table.add_row("Runtime", "ONLINE")
    table.add_row("Lifecycle", str(state_data.get("lifecycle", state_data.get("lifecycle_state", "ACTIVE"))))
    table.add_row("Heartbeat", f"{'ALIVE' if hb.get('running', False) else 'STOPPED'} | beats={hb.get('beat_count', 0)}")
    table.add_row("Idle", str(hb.get("is_idle", False)))
    table.add_row("Last activity", str(state_data.get("last_activity_at", "unknown")))
    table.add_row("Current mode", str(state_data.get("mode", "UNKNOWN")))
    brain = _brain(jarvis)
    if brain is not None and hasattr(brain, "status"):
        try:
            bs = _safe_dict(brain.status())
            q = _safe_dict(bs.get("async_learning_queue", {}))
            table.add_row("Learning queue", f"alive={q.get('alive', False)} pending={q.get('pending', 0)} processed={q.get('processed', 0)} failed={q.get('failed', 0)}")
        except Exception as exc:
            table.add_row("Brain status", f"ERROR: {exc}")
    console.print(table)


def render_about():
    console.print(Panel(
        "[bold cyan]JARVIS COGNITIVE OS v2026.1[/bold cyan]\n\n"
        "[white]Runtime control surface for the UK modular cognitive organism.[/white]\n"
        "Architecture: Perception → Cognition/Memory → Cognitive Router → Brain → Action/Response → Experience/Evaluation → Learning/Knowledge → Self-Evaluation → Evolution.\n\n"
        "CLI inspection commands are diagnostic controls and do not enter the normal cognitive pipeline.",
        title="ABOUT JARVIS",
        border_style="cyan",
    ))


def handle_cli_command(jarvis, user_input: str) -> bool:
    """Handle a slash command without entering the cognitive pipeline."""
    command = user_input.strip().lower().split(None, 1)[0] if user_input.strip() else ""
    if not command.startswith("/"):
        return False
    if command == "/help":
        print_cli_commands()
    elif command == "/about":
        render_about()
    elif command == "/memory_inspect":
        render_memory_inspection(jarvis)
    elif command == "/trace_inspect":
        render_trace_inspection(jarvis)
    elif command == "/tool_trace":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        trace = getattr(brain, "last_tool_call_trace", None) if brain is not None else None
        if not trace:
            console.print("[dim]No LLM tool calls recorded yet this session (see core/orchestration/tool_registry.py).[/dim]")
        else:
            tree = Tree("[bold]Last turn's tool calls (LLM-decided, not hardcoded)[/bold]")
            for call in trace:
                if call.get("builtin_tool"):
                    tree.add(f"[cyan]browser_search[/cyan] (server-side): {_fmt(call.get('executed_tools_summary', ''), limit=150)}")
                else:
                    result = call.get("result") or {}
                    style = "red" if isinstance(result, dict) and result.get("error") else "green"
                    branch = tree.add(f"[{style}]{call.get('name')}[/{style}]  args={call.get('arguments')}")
                    branch.add(f"-> {_fmt(str(result), limit=200)}")
            console.print(Panel(tree, border_style="cyan"))
    elif command == "/runtime_inspect":
        render_runtime_inspection(jarvis)
    elif command == "/organ_inspect":
        render_organ_matrix(jarvis)
    elif command == "/voice":
        global _voice_enabled
        from core.runtime.voice import voice_available, list_voices, set_voice, get_voice_config
        arg = user_input[len("/voice"):].strip()
        if not voice_available():
            console.print(
                "[bold yellow]Voice unavailable:[/bold yellow] termux-tts-speak not found. "
                "Install the Termux:API app (F-Droid/Play Store) AND run [bold]pkg install termux-api[/bold] in Termux, then try again."
            )
        elif arg == "list":
            voices = list_voices()
            if not voices:
                console.print("[bold yellow]No voices reported.[/bold yellow] termux-tts-engines returned nothing -- try /voice on/off instead, or check Termux:API is fully set up.")
            else:
                console.print(f"[bold cyan]{len(voices)} voice(s)/engine(s) found on this device:[/bold cyan]")
                for i, v in enumerate(voices):
                    console.print(f"  [{i}] engine={v.get('name', '?')}  " + "  ".join(f"{k}={val}" for k, val in v.items() if k not in ('name',)))
                console.print("[dim]Use /voice set <engine_name> to pick one -- if the default sounds robotic, another installed engine may sound more natural.[/dim]")
        elif arg.startswith("set "):
            engine_name = arg[len("set "):].strip()
            set_voice(engine=engine_name)
            console.print(f"[bold cyan]Voice engine set to:[/bold cyan] {engine_name}  (current config: {get_voice_config()})")
        elif arg.startswith("pitch "):
            try:
                set_voice(pitch=float(arg[len("pitch "):].strip()))
                console.print(f"[bold cyan]Voice pitch set.[/bold cyan]  (current config: {get_voice_config()})")
            except ValueError:
                console.print("[bold yellow]Usage:[/bold yellow] /voice pitch <number, e.g. 1.35>")
        elif arg.startswith("rate "):
            try:
                set_voice(rate=float(arg[len("rate "):].strip()))
                console.print(f"[bold cyan]Voice rate set.[/bold cyan]  (current config: {get_voice_config()})")
            except ValueError:
                console.print("[bold yellow]Usage:[/bold yellow] /voice rate <number, e.g. 1.15>")
        elif arg.startswith("lang "):
            set_voice(lang=arg[len("lang "):].strip())
            console.print(f"[bold cyan]Voice language set.[/bold cyan]  (current config: {get_voice_config()})")
        elif arg in ("", "toggle"):
            _voice_enabled = not _voice_enabled
            console.print(f"[bold cyan]Voice replies:[/bold cyan] {'ON -- JARVIS will speak each reply aloud' if _voice_enabled else 'OFF'}")
        else:
            console.print("[bold yellow]Usage:[/bold yellow] /voice (toggle) | /voice list | /voice set <engine_name> | /voice pitch <n> | /voice rate <n> | /voice lang <locale, e.g. hi-IN>")
    elif command == "/voice_pitch":
        from core.runtime.voice import set_voice, get_voice_config
        val = user_input[len("/voice_pitch"):].strip()
        try:
            set_voice(pitch=float(val))
            console.print(f"[bold cyan]Voice pitch set.[/bold cyan]  (current config: {get_voice_config()})")
        except ValueError:
            console.print("[bold yellow]Usage:[/bold yellow] /voice_pitch <number, e.g. 0.55>")
    elif command == "/voice_rate":
        from core.runtime.voice import set_voice, get_voice_config
        val = user_input[len("/voice_rate"):].strip()
        try:
            set_voice(rate=float(val))
            console.print(f"[bold cyan]Voice rate set.[/bold cyan]  (current config: {get_voice_config()})")
        except ValueError:
            console.print("[bold yellow]Usage:[/bold yellow] /voice_rate <number, e.g. 1.1>")
    elif command == "/listen":
        from core.runtime.voice import speech_input_available, listen
        if not speech_input_available():
            console.print(
                "[bold yellow]Voice input unavailable:[/bold yellow] termux-speech-to-text not found. "
                "Install the Termux:API app (F-Droid/Play Store) AND run [bold]pkg install termux-api[/bold] in Termux, then try again."
            )
        else:
            console.print("[dim]Listening... speak now.[/dim]")
            heard = listen()
            if not heard:
                console.print("[bold yellow]Didn't catch that.[/bold yellow] Nothing transcribed -- try again or type instead.")
            else:
                console.print(f"[dim]Heard:[/dim] \"{heard}\"")
                execute_cognitive_query(jarvis, heard, source="cli")
    elif command == "/organ_introspect":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None:
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            from core.orchestration.organ_introspection import introspect_all
            report = introspect_all(brain)
            for organ_name, answers in report.items():
                tree = Tree(f"[bold cyan]{organ_name.upper()}[/bold cyan]")
                for question, answer in answers.items():
                    label = question.replace("_", " ").upper()
                    tree.add(f"[bold]{label}?[/bold]  {_fmt(str(answer), limit=100)}")
                console.print(Panel(tree, border_style="cyan"))
    elif command.startswith("/login"):
        # Proving identity to READ traces -- separate from starting the
        # process, which needs no identity at all.
        import getpass as _gp
        from core.identity import user_store as _us
        parts = user_input.split()
        if len(parts) < 2:
            return "Use: /login <username>"
        _u = _us.verify_login(parts[1].strip(), _gp.getpass("  password: "))
        if not _u:
            # Same message either way -- no account enumeration.
            return "Username ya password galat hai."
        globals()["_CLI_VIEWER"] = {
            "username": _u.username, "role": _u.role, "is_verified": True,
            "channel": "cli", "session_id": f"cli_{_u.username}",
        }
        return (f"Logged in as {_u.username} ({_u.role}). "
                "/trace ab aapka apna trace dikhayega; /trace all se baaki jo allowed hai.")

    elif command == "/logout":
        globals()["_CLI_VIEWER"] = {"role": "guest", "is_verified": False,
                                    "username": None, "channel": "cli", "session_id": "cli"}
        return "Logged out. Trace view ab guest level pe hai (yani kuch nahi)."

    elif command.startswith("/trace"):
        from core.runtime.identity_trace import view as _tview, active_overview as _tactive
        viewer = globals().get("_CLI_VIEWER") or {"role": "guest"}
        parts = user_input.split()
        sub = parts[1].lower() if len(parts) > 1 else "mine"
        arg = parts[2] if len(parts) > 2 else None

        if sub == "who":
            res = _tactive(viewer)
            if not res.get("allowed"):
                return "Trace dekhne ke liye /login karo."
            if not res["users"]:
                return "Pichhle 30 min mein koi active nahi."
            out = [f"Active (last {res['window_minutes']}m):"]
            for u in res["users"]:
                out.append(f"  {u['username']:<12} {u['role']:<9} {u['channel']:<5}"
                           f" turns={u['turns']:<4} {u['last_seen']}")
            return "\n".join(out)

        scope_map = {"mine": "mine", "all": "all", "user": "user",
                     "role": "role", "session": "session", "req": "request"}
        scope = scope_map.get(sub, "mine")
        res = _tview(viewer, scope=scope, username=arg if scope == "user" else None,
                     role=arg if scope == "role" else None,
                     session_id=arg if scope == "session" else None,
                     request_id=arg if scope == "request" else None, limit=15)
        if not res.get("allowed"):
            return res.get("reason", "Trace dekhne ke liye /login karo.")
        if not res["entries"]:
            return (f"Is scope ({scope}) mein aapke liye koi trace nahi. "
                    "Agar dusron ka dekhna hai toh owner/co-owner chahiye.")
        out = [f"TRACE  scope={scope}  viewer={res['viewer']['username'] or 'guest'}"
               f" ({res['viewer']['role']})  {res['count']} entries"]
        for e in res["entries"]:
            out.append(f"  [{e['timestamp']}] {e['username']}/{e['role']} via {e['channel']}"
                       f"  {e['request_id']}  {int(e['duration_ms'] or 0)}ms")
            out.append(f"      > {(e['user_input'] or '')[:70]}")
            out.append(f"      < {(e['response'] or '')[:70]}")
        if res.get("note"):
            out.append(f"  ({res['note']})")
        return "\n".join(out)

    elif command.startswith("/diagnose"):
        from core.runtime.diagnostics import run_diagnostics, apply_remedy, STATUS_OK

        parts = user_input.split()
        # /diagnose fix           -> apply every AUTO remedy
        # /diagnose fix <name>    -> apply one specific AUTO remedy
        # /diagnose               -> report only, no changes
        if len(parts) >= 2 and parts[1] == "fix":
            viewer = globals().get("_CLI_VIEWER") or {"role": "guest"}
            role = (viewer.get("role") or "guest").lower()
            if role not in ("owner", "co_owner"):
                return ("Fix apply karna sirf owner/co-owner kar sakte hain -- "
                        "report abhi bhi /diagnose se dekh sakte ho.")
            if len(parts) >= 3:
                result = apply_remedy(parts[2])
                return (f"'{parts[2]}': {'FIXED' if result['ok'] else 'NAHI HUA'}\n"
                        f"  {result.get('outcome') or result.get('reason')}")
            report = run_diagnostics(auto_fix=True)
            out = [f"Diagnose + auto-fix: {report['total']} check, "
                   f"{len(report['auto_fixes_applied'])} fix apply hui."]
            for applied in report["auto_fixes_applied"]:
                out.append(f"  {applied['name']}: {applied['outcome']}")
            return "\n".join(out)

        report = run_diagnostics()
        out = [f"DIAGNOSTIC  {report['ok']} ok  {report['warnings']} warning  "
               f"{report['critical']} critical"]
        for r in report["results"]:
            if r["status"] == STATUS_OK:
                continue
            tag = "CRITICAL" if r["status"] == "critical" else "WARNING"
            out.append(f"\n[{tag}] {r['name']}")
            out.append(f"  {r['detail']}")
            if r["remedy_kind"] == "auto":
                out.append(f"  FIX (auto): {r['remedy_description']}")
                out.append(f"  -> /diagnose fix {r['name']}")
            elif r["remedy_kind"] == "guided":
                out.append(f"  FIX (manual): {r['remedy_description']}")
            else:
                out.append("  Yeh naya hai -- iska fix abhi JARVIS ko nahi pata.")
        if report["ok"] == report["total"]:
            out.append("Sab theek hai.")
        return "\n".join(out)

    elif command.startswith("/owner"):
        # Owner and co-owner are managed from the device, never over
        # HTTP. Anything that could mint an owner remotely would be the
        # most valuable target in the system.
        import getpass as _getpass
        from core.identity import user_store as _us

        parts = user_input.split()
        sub = parts[1].lower() if len(parts) > 1 else "status"
        target = parts[2].strip().lower() if len(parts) > 2 else None

        _us._init_schema()

        def _rows():
            with _us._connect() as c:
                return c.execute("SELECT username, role, display_name FROM users ORDER BY role, username").fetchall()

        if sub == "status":
            rows = _rows()
            if not rows:
                return ("Koi account nahi hai.\n"
                        "Owner banane ke liye:  python3 setup_owner.py\n"
                        "Ya yahin se:           /owner set uk")
            out = [f"{len(rows)} account:"]
            for r in rows:
                out.append(f"  {r['username']:<18} {r['role']}")
            if not any(r["role"] == "owner" for r in rows):
                out.append("\nOwner account NAHI hai -- /owner set <username> se banao.")
            return "\n".join(out)

        if sub in ("set", "passwd"):
            # 'set' creates/replaces the owner; 'passwd' resets the
            # existing one's password.
            with _us._connect() as c:
                existing = c.execute("SELECT username FROM users WHERE role='owner'").fetchone()
            if sub == "passwd":
                if not existing:
                    return "Koi owner hai hi nahi. Pehle /owner set <username>."
                target = existing["username"]
            if not target:
                return "Username chahiye:  /owner set <username>"
            if existing and sub == "set" and existing["username"] != target:
                return (f"Owner pehle se hai: '{existing['username']}'. Ek hi owner ho sakta hai.\n"
                        f"Password badalna ho toh: /owner passwd")

            pw = _getpass.getpass("  Naya password: ")
            if len(pw) < 8:
                return "Password kam se kam 8 characters ka hona chahiye. Kuch nahi badla."
            if pw != _getpass.getpass("  Dobara: "):
                return "Dono match nahi kiye. Kuch nahi badla."

            import secrets as _secrets, time as _time
            # verify_login() lowercases before its lookup, so the stored
            # row must be lowercase or login silently never matches.
            uname = target.strip().lower()
            salt = _secrets.token_bytes(16)
            with _us._connect() as c:
                if c.execute("SELECT 1 FROM users WHERE username=?", (uname,)).fetchone():
                    c.execute("UPDATE users SET password_hash=?, salt=?, role='owner' WHERE username=?",
                              (_us._hash_password(pw, salt), salt.hex(), uname))
                else:
                    c.execute("INSERT INTO users (username, password_hash, salt, role, created_at, display_name)"
                              " VALUES (?,?,?,'owner',?,?)",
                              (uname, _us._hash_password(pw, salt), salt.hex(), _time.time(), target))
                c.commit()
            return f"Owner '{uname}' ready hai. Web UI pe /owner se login karo."

        if sub == "cowner":
            if not target:
                return "Username chahiye:  /owner cowner <username>"
            with _us._connect() as c:
                row = c.execute("SELECT role FROM users WHERE username=?", (target,)).fetchone()
                if not row:
                    return f"'{target}' naam ka account nahi hai. Pehle usse signup karne do."
                if row["role"] == "owner":
                    return "Owner ka role badla nahi ja sakta."
                c.execute("UPDATE users SET role='co_owner' WHERE username=?", (target,))
                c.commit()
            return (f"'{target}' ab co-owner hai. Woh /owner se login karega.\n"
                    "Note: co-owner roles grant NAHI kar sakta -- taaki koi aapko "
                    "aapke hi system se bahar na kar sake.")

        if sub == "remove":
            if not target:
                return "Username chahiye:  /owner remove <username>"
            with _us._connect() as c:
                row = c.execute("SELECT role FROM users WHERE username=?", (target,)).fetchone()
                if not row:
                    return f"'{target}' naam ka account nahi hai."
                if row["role"] == "owner":
                    # The one rule that makes the rest safe.
                    return ("Owner ko koi remove nahi kar sakta -- aap bhi nahi. "
                            "Yeh jaan-boojh kar hai.")
                c.execute("DELETE FROM users WHERE username=?", (target,))
                c.commit()
            return f"'{target}' ka account delete ho gaya."

        return ("Use: /owner status | /owner set <username> | /owner cowner <username> | "
                "/owner remove <username> | /owner passwd")

    elif command.startswith("/think"):
        # Extended thinking toggle. Mirrors the frontend button so the
        # setting means the same thing in both places.
        parts = command.split()
        if len(parts) < 2 or parts[1] not in {"off", "auto", "on"}:
            current = globals().get("THINKING_MODE", "auto")
            return f"Extended thinking abhi '{current}' hai. Badalna ho: /think off | auto | on"
        globals()["THINKING_MODE"] = parts[1]
        explain = {
            "off": "Har turn normal chat -- koi extra reasoning nahi.",
            "auto": "Main khud decide karunga kis turn pe sochna hai. Simple baat pe nahi sochunga.",
            "on": "Har turn soch kar jawab dunga (zyada tokens lagenge).",
        }[parts[1]]
        return f"Extended thinking: {parts[1]}. {explain}"

    elif command.startswith("/codebox"):
        # A live coding session, deliberately separate from chat. Chat
        # keeps its copy-pasteable code blocks; this is where code runs.
        try:
            from core.skills.codebox import CodeBox
            box = CodeBox(role="owner", session_id="cli")
            files = box.list_files()
            return (
                f"CodeBox session: {box.session.workdir}\n"
                f"Files: {', '.join(files) if files else '(khali)'}\n"
                "Code likhne ke liye seedha bolo -- main likhunga, chalaunga, error aaye toh theek karunga.\n"
                "Yeh sandbox aapka apna hai; core ko yahan se kuch nahi hota."
            )
        except Exception as exc:
            return f"CodeBox shuru nahi ho paya: {exc}"

    elif command == "/pending_rules":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "list_pending_self_rules"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            pending = brain.list_pending_self_rules()
            if not pending:
                console.print("[dim]No self-authored rules awaiting confirmation.[/dim]")
            else:
                table = Table(title="SELF-AUTHORED RULES -- AWAITING YOUR CONFIRMATION", border_style="yellow", header_style="bold yellow")
                table.add_column("#", style="bold white", width=4)
                table.add_column("Proposed Rule", style="white")
                table.add_column("Confidence", justify="center", width=10)
                table.add_column("Knowledge ID", style="dim", width=36)
                for i, item in enumerate(pending):
                    table.add_row(str(i), str(item.get("rule")), f"{item.get('confidence', 0):.2f}", str(item.get("knowledge_id")))
                console.print(table)
                console.print("[dim]Use /confirm_rule <n> or /reject_rule <n> to review each one.[/dim]")
    elif command == "/confirm_rule":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/confirm_rule"):].strip()
        if brain is None or not hasattr(brain, "confirm_self_rule"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /confirm_rule <n>  (see /pending_rules for the list)")
        else:
            pending = brain.list_pending_self_rules()
            idx = int(arg)
            if idx < 0 or idx >= len(pending):
                console.print(f"[bold red]No pending rule #{idx}.[/bold red] Run /pending_rules first.")
            else:
                result = brain.confirm_self_rule(pending[idx]["knowledge_id"])
                if result.get("status") == "confirmed":
                    console.print(f"[bold green]Confirmed:[/bold green] \"{result.get('rule')}\" -- this will now influence responses.")
                else:
                    console.print(f"[bold red]Could not confirm:[/bold red] {result}")
    elif command == "/reject_rule":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/reject_rule"):].strip()
        if brain is None or not hasattr(brain, "reject_self_rule"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /reject_rule <n>  (see /pending_rules for the list)")
        else:
            pending = brain.list_pending_self_rules()
            idx = int(arg)
            if idx < 0 or idx >= len(pending):
                console.print(f"[bold red]No pending rule #{idx}.[/bold red] Run /pending_rules first.")
            else:
                result = brain.reject_self_rule(pending[idx]["knowledge_id"])
                console.print("[bold yellow]Rejected.[/bold yellow] JARVIS will remember this and won't re-propose the identical rule again." if result.get("status") == "rejected" else f"[bold red]{result}[/bold red]")
    elif command == "/explain_rule":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/explain_rule"):].strip()
        if brain is None or not hasattr(brain, "explain_self_rule"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /explain_rule <n>  (see /pending_rules for the list)")
        else:
            pending = brain.list_pending_self_rules()
            idx = int(arg)
            if idx < 0 or idx >= len(pending):
                console.print(f"[bold red]No pending rule #{idx}.[/bold red] Run /pending_rules first.")
            else:
                explanation = brain.explain_self_rule(pending[idx]["knowledge_id"])
                if explanation.get("status") == "not_found":
                    console.print(f"[bold red]{explanation}[/bold red]")
                else:
                    tree = Tree(f"[bold]{explanation.get('rule')}[/bold]")
                    tree.add(f"status: {explanation.get('status')}  |  confidence: {explanation.get('confidence'):.2f}  |  source_type: {explanation.get('source_type')}")
                    evidence = explanation.get("evidence") or {}
                    for key, value in evidence.items():
                        tree.add(f"[bold]{key.replace('_', ' ')}:[/bold] {_fmt(str(value), limit=140)}")
                    console.print(Panel(tree, title="WHY THIS RULE WAS PROPOSED", border_style="cyan"))
    elif command == "/instructions":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "list_standing_instructions"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            items = brain.list_standing_instructions()
            if not items:
                console.print("[dim]No standing instructions yet. Say something like \"roz subah good morning bolo\" to create one.[/dim]")
            else:
                table = Table(title="STANDING INSTRUCTIONS (daily triggers)", border_style="cyan", header_style="bold cyan")
                table.add_column("#", style="bold white", width=4)
                table.add_column("Trigger Time", width=12)
                table.add_column("Action", style="white")
                table.add_column("Last Fired", width=12)
                table.add_column("Knowledge ID", style="dim", width=36)
                for i, item in enumerate(items):
                    table.add_row(str(i), str(item.get("trigger_time")), str(item.get("action_text")),
                                  str(item.get("last_fired_date") or "never"), str(item.get("knowledge_id")))
                console.print(table)
                console.print("[dim]Use /remove_instruction <n> to delete one.[/dim]")
    elif command == "/remove_instruction":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/remove_instruction"):].strip()
        if brain is None or not hasattr(brain, "remove_standing_instruction"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /remove_instruction <n>  (see /instructions for the list)")
        else:
            items = brain.list_standing_instructions()
            idx = int(arg)
            if idx < 0 or idx >= len(items):
                console.print(f"[bold red]No instruction #{idx}.[/bold red] Run /instructions first.")
            else:
                result = brain.remove_standing_instruction(items[idx]["knowledge_id"])
                console.print("[bold yellow]Removed.[/bold yellow]" if result.get("status") == "removed" else f"[bold red]{result}[/bold red]")
    elif command == "/contested_facts":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "list_contested_facts"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            items = brain.list_contested_facts()
            if not items:
                console.print("[dim]No contested facts pending review.[/dim]")
            else:
                table = Table(title="CONTESTED FACTS -- AWAITING YOUR REVIEW", border_style="yellow", header_style="bold yellow")
                table.add_column("#", style="bold white", width=4)
                table.add_column("Subject.Predicate", style="white")
                table.add_column("Current", style="green")
                table.add_column("Proposed", style="yellow")
                table.add_column("Knowledge ID", style="dim", width=36)
                for i, item in enumerate(items):
                    table.add_row(
                        str(i), f"{item.get('subject')}.{item.get('predicate')}",
                        f"[{item.get('current_source_type')}] {item.get('current_value')}",
                        f"[{item.get('proposed_source_type')}] {item.get('proposed_value')}",
                        str(item.get("knowledge_id")),
                    )
                console.print(table)
                console.print("[dim]Use /resolve_contested <n> accept|keep to review each one.[/dim]")
    elif command == "/resolve_contested":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/resolve_contested"):].strip()
        parts = arg.split()
        if brain is None or not hasattr(brain, "resolve_contested_fact"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif len(parts) != 2 or not parts[0].isdigit() or parts[1].lower() not in ("accept", "keep"):
            console.print("[bold yellow]Usage:[/bold yellow] /resolve_contested <n> accept|keep  (see /contested_facts for the list)")
        else:
            items = brain.list_contested_facts()
            idx = int(parts[0])
            if idx < 0 or idx >= len(items):
                console.print(f"[bold red]No contested fact #{idx}.[/bold red] Run /contested_facts first.")
            else:
                accept = parts[1].lower() == "accept"
                result = brain.resolve_contested_fact(items[idx]["knowledge_id"], accept_new_value=accept)
                if result.get("status") == "resolved":
                    console.print(f"[bold green]Resolved.[/bold green] Current value: {result.get('current_value')}")
                else:
                    console.print(f"[bold red]{result}[/bold red]")
    elif command == "/llm_dependency":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "get_llm_dependency_stats"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            stats = brain.get_llm_dependency_stats()
            if not stats.get("available"):
                console.print("[dim]Not available yet.[/dim]")
            else:
                counts = stats.get("counts") or {}
                rate = stats.get("native_coverage_rate")
                table = Table(title="LLM DEPENDENCY (semantic understanding, this session)", border_style="cyan", header_style="bold cyan")
                table.add_column("Metric")
                table.add_column("Value")
                table.add_row("native", str(counts.get("native", 0)))
                table.add_row("learned_native", str(counts.get("learned_native", 0)))
                table.add_row("llm_fallback", str(counts.get("llm_fallback", 0)))
                table.add_row("native coverage rate", f"{rate * 100:.1f}%" if rate is not None else "—")
                table.add_row("learned registry size", str(stats.get("learned_registry_size", 0)))
                table.add_row("pending candidates", str(stats.get("pending_candidates", 0)))
                console.print(table)
    elif command == "/grounding_violations":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "get_grounding_violation_patterns"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            patterns = brain.get_grounding_violation_patterns()
            if not patterns.get("total_violations"):
                console.print("[dim]No grounding violations recorded this session.[/dim]")
            else:
                console.print(f"[bold yellow]Total violations: {patterns.get('total_violations')}[/bold yellow]")
                table = Table(title="RECURRING VIOLATION CATEGORIES", border_style="yellow", header_style="bold yellow")
                table.add_column("Category")
                table.add_column("Count")
                for p in patterns.get("patterns") or []:
                    table.add_row(str(p.get("category")), str(p.get("count")))
                console.print(table)
    elif command == "/pending_patterns":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "list_pending_patterns"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            items = brain.list_pending_patterns()
            if not items:
                console.print("[dim]No self-authored patterns pending review.[/dim]")
            else:
                for i, item in enumerate(items):
                    tree = Tree(f"[bold]#{i}[/bold] target: {item.get('target_predicate')}")
                    tree.add(f"regex: [cyan]{item.get('regex')}[/cyan]")
                    tree.add(f"gap: {item.get('gap_description')}")
                    tree.add(f"examples: {item.get('example_inputs')}")
                    console.print(Panel(tree, border_style="cyan"))
                console.print("[dim]Use /confirm_pattern <n> or /reject_pattern <n>.[/dim]")
    elif command == "/confirm_pattern":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/confirm_pattern"):].strip()
        if brain is None or not hasattr(brain, "confirm_pattern"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /confirm_pattern <n>  (see /pending_patterns)")
        else:
            items = brain.list_pending_patterns()
            idx = int(arg)
            if idx < 0 or idx >= len(items):
                console.print(f"[bold red]No pending pattern #{idx}.[/bold red] Run /pending_patterns first.")
            else:
                result = brain.confirm_pattern(items[idx]["knowledge_id"])
                console.print("[bold green]Confirmed.[/bold green] This pattern now runs live." if result.get("status") == "confirmed" else f"[bold red]{result}[/bold red]")
    elif command == "/reject_pattern":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        arg = user_input[len("/reject_pattern"):].strip()
        if brain is None or not hasattr(brain, "reject_pattern"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        elif not arg.isdigit():
            console.print("[bold yellow]Usage:[/bold yellow] /reject_pattern <n>  (see /pending_patterns)")
        else:
            items = brain.list_pending_patterns()
            idx = int(arg)
            if idx < 0 or idx >= len(items):
                console.print(f"[bold red]No pending pattern #{idx}.[/bold red] Run /pending_patterns first.")
            else:
                result = brain.reject_pattern(items[idx]["knowledge_id"])
                console.print("[bold yellow]Rejected.[/bold yellow]" if result.get("status") == "rejected" else f"[bold red]{result}[/bold red]")
    elif command == "/remote":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "start_remote_access"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            console.print("[dim]Starting ngrok tunnel...[/dim]")
            result = brain.start_remote_access()
            if result.get("status") in ("started", "already_running"):
                console.print(f"[bold green]JARVIS is reachable at:[/bold green] {result.get('public_url')}")
                console.print("[dim]Local access unaffected: http://localhost:5173, http://localhost:8000[/dim]")
            else:
                console.print(f"[bold red]{result.get('message')}[/bold red]")
    elif command == "/remote_stop":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None or not hasattr(brain, "stop_remote_access"):
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            result = brain.stop_remote_access()
            console.print("[bold yellow]Tunnel stopped.[/bold yellow]" if result.get("status") == "stopped" else f"[dim]{result}[/dim]")
    elif command == "/self_evolution":
        brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
        if brain is None:
            console.print("[bold red]No brain organ attached.[/bold red]")
        else:
            rules = brain.get_recent_auto_adopted_rules() if hasattr(brain, "get_recent_auto_adopted_rules") else []
            patterns = brain.get_recent_auto_promotions() if hasattr(brain, "get_recent_auto_promotions") else []
            if not rules and not patterns:
                console.print("[dim]Nothing has self-adopted yet. JARVIS adopts a behavioral rule only after "
                              "8 independent reasoning cycles reach the same conclusion, and an extraction "
                              "pattern after 6 consistent real matches.[/dim]")
            for r in rules:
                console.print(Panel(
                    f"[bold]RULE (self-adopted)[/bold]\n{r.get('rule')}\n\n"
                    f"[dim]independent proposals: {r.get('independent_proposals')} -- undo with /reject_rule[/dim]",
                    border_style="magenta"))
            for p in patterns:
                console.print(Panel(
                    f"[bold]PATTERN (self-adopted)[/bold]\n{p.get('regex')}\n\n"
                    f"[dim]{p.get('message')}[/dim]", border_style="cyan"))
    elif command == "/verbose":
        global _verbose_trace
        _verbose_trace = not _verbose_trace
        state_txt = "ON -- the full raw per-layer contract trace will render below every reply's workflow panel" if _verbose_trace else "OFF -- the organized workflow panel still shows every stage; use /trace_inspect for the full raw contract payloads on demand"
        console.print(f"[bold cyan]Verbose trace:[/bold cyan] {state_txt}")
    elif command == "/ingest_document":
        path = user_input[len("/ingest_document"):].strip()
        if not path:
            console.print("[bold yellow]Usage:[/bold yellow] /ingest_document <path-to-text-file>")
        else:
            try:
                from core.memory.document_ingestion import ingest_document
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
                memory = getattr(brain, "memory", None) if brain is not None else None
                if memory is None:
                    console.print("[bold red]No memory organ attached -- cannot ingest.[/bold red]")
                else:
                    summary = ingest_document(memory, text, doc_id=path.split("/")[-1])
                    console.print(
                        f"[bold green]Ingested[/bold green] {path}: "
                        f"{summary['chunks_stored']} excerpts stored, {summary['facts_extracted']} facts extracted "
                        f"[dim](all tagged namespace=DOCUMENT -- never treated as something you personally told JARVIS)[/dim]"
                    )
            except FileNotFoundError:
                console.print(f"[bold red]File not found:[/bold red] {path}")
            except Exception as exc:
                console.print(f"[bold red]Ingestion failed:[/bold red] {exc}")
    else:
        console.print(f"[bold red]Unknown JARVIS command:[/bold red] {command}\n[dim]Use /help for available commands.[/dim]")
    return True
>>>>>>> 90fbd2a (Save local project changes before branch checkout)


def start_silent_heartbeat_sync(jarvis):
    def _sync_loop():
        while True:
            try:
                time.sleep(3.0)
                if web_event_broadcaster and callable(web_event_broadcaster):
                    hb = jarvis.heartbeat.status() if hasattr(jarvis, "heartbeat") and jarvis.heartbeat else {}
                    beats = hb.get("beat_count", 0)
                    is_idle = hb.get("is_idle", True)

                    brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
                    queue_status = {}
                    if brain is not None and hasattr(brain, "status"):
                        try:
                            queue_status = brain.status().get("async_learning_queue", {})
                        except Exception:
                            queue_status = {}

                    goal_manager = jarvis.get_organ("goal_manager") if hasattr(jarvis, "get_organ") else None
                    goals_snapshot = {}
                    if goal_manager is not None and hasattr(goal_manager, "snapshot"):
                        try:
                            goals_snapshot = goal_manager.snapshot()
                        except Exception:
                            goals_snapshot = {}

                    web_event_broadcaster({
                        "type": "pulse",
                        "wave": "SYS_UPTIME",
                        "beats": beats,
                        "state": "Idle Scanning" if is_idle else "Active Processing",
                        # These two were missing before -- the web UI had
                        # no visibility into the async learning queue or
                        # the autonomy/goal layer, only the raw beat count.
                        "learning_queue": queue_status,
                        "goals": goals_snapshot,
                    })
            except Exception:
                pass

    t = threading.Thread(target=_sync_loop, daemon=True)
    t.start()

def execute_cognitive_query(jarvis, user_input: str, source: str = "cli") -> str:
    with model_lock:
        brain = jarvis.get_organ("brain")
        start_total = time.time()

        now = time.time()
        if hasattr(jarvis, "state") and jarvis.state:
            if hasattr(jarvis.state, "update"):
                jarvis.state.update(last_activity_at=now)
            else:
                setattr(jarvis.state, "last_activity_at", now)

        jarvis.receive_event("USER_INPUT", {"text": user_input}, source=source)

        reply = "[System Error: Core Cognitive Engine Offline]"
        pipeline_success = False
        error_stack = None

        if brain:
            console.print(f"\n[bold cyan][{source.upper()} INGESTION] Processing query through Pipeline...[/bold cyan]")

            identity_profile = {
                "name": "JARVIS",
                "creator": "UK",
                "nature": "Modular Cognitive Organism",
                "instruction": "Respond accurately in Hinglish directly as JARVIS. User is UK, your creator."
            }

            # NOTE: think_and_respond() does its OWN retrieval + timing
            # internally now and stores the full result on
            # brain.last_turn_trace. Previously this function called
            # build_context() here a SECOND time (duplicate FAISS/DB
            # work every turn) purely to build a trace, then rebuilt a
            # second, less detailed trace afterwards. Both are gone —
            # this is now the only place retrieval happens per turn.
            try:
                reply = brain.think_and_respond(user_input, identity_profile=identity_profile, source=source)
                pipeline_success = True

            except Exception as err:
                reply = f"[Brain Processing Fault: {err}]"
                error_stack = traceback.format_exc()

        total_duration = time.time() - start_total
        trace = getattr(brain, "last_turn_trace", None) if brain is not None else None

        render_cognition_trace(trace, source=source)

        if error_stack:
            console.print(Panel(f"[bold red]RUNTIME EXCEPTION DETECTED ({source.upper()}):[/bold red]\n{error_stack}", border_style="red", title="[bold red]System Error Fault[/bold red]"))
        else:
            console.print(Panel(f"[white]{reply}[/white]", title=f"[bold green]JARVIS Output ({source.upper()})[/bold green]", border_style="cyan"))

        if web_event_broadcaster and callable(web_event_broadcaster):
            try:
                web_event_broadcaster({
                    "type": "cli_stream",
                    "text": f"[{source.upper()}] Query: {user_input} -> Responded ({total_duration:.2f}s)",
                    "tag": "INFO"
                })
            except Exception as b_err:
                console.print(f"[dim red]Web broadcast sync error: {b_err}[/dim red]")

        return reply

# --- Dynamic Resolver Global Entry Point for Web Dashboard ---
def process_query(user_input: str, source: str = "web") -> str:
    global _global_jarvis_instance
    if _global_jarvis_instance:
        return execute_cognitive_query(_global_jarvis_instance, user_input, source=source)
    return "⚠️ Engine Not Initialized in CLI Process."

def start_web_server_thread(jarvis):
    global web_event_broadcaster
    try:
        import main as app_module

        if hasattr(app_module, "set_shared_organism"):
            app_module.set_shared_organism(jarvis)
        else:
            app_module.jarvis = jarvis

        if hasattr(app_module, "attach_console"):
            app_module.attach_console(console)

        if hasattr(app_module, "broadcast_to_clients"):
            web_event_broadcaster = app_module.broadcast_to_clients

        if hasattr(app_module, "start_server_in_thread"):
            app_module.start_server_in_thread()
            console.print("[bold green]Web Engine Server Thread Successfully Started.[/bold green]")

    except Exception as e:
        console.print(Panel(f"[bold red]Web Server Initialization Exception:[/bold red]\n{traceback.format_exc()}", border_style="red"))

# --- Dynamic Instance Live-Patching Engine ---
def patch_organ_instances(jarvis, reloaded_mod):
    patched_organs = []
    classes_in_mod = {
        name: obj for name, obj in reloaded_mod.__dict__.items() 
        if isinstance(obj, type)
    }
    
    if not classes_in_mod or not hasattr(jarvis, "organs"):
        return patched_organs

    organs_dict = jarvis.organs if isinstance(jarvis.organs, dict) else {}
    for organ_name, organ_instance in organs_dict.items():
        if organ_instance is None:
            continue
        
        curr_class_name = organ_instance.__class__.__name__
        if curr_class_name in classes_in_mod:
            new_class = classes_in_mod[curr_class_name]
            try:
                organ_instance.__class__ = new_class
                if hasattr(organ_instance, "__on_reload__") and callable(organ_instance.__on_reload__):
                    organ_instance.__on_reload__()
                patched_organs.append(f"{organ_name} -> {curr_class_name}")
            except Exception as patch_err:
                console.print(f"[dim red]Failed to patch instance {organ_name}: {patch_err}[/dim red]")

    return patched_organs

def get_file_fingerprint(filepath):
    try:
        stat = os.stat(filepath)
        with open(filepath, "rb") as f:
            content_hash = hashlib.md5(f.read()).hexdigest()
        return f"{stat.st_size}_{content_hash}"
    except Exception:
        return None

def start_live_module_watcher(jarvis):
    def _watch_loop():
        def scan_files():
            fingerprints = {}
            for root, _, files in os.walk(BASE_DIR):
                for file in files:
                    if file.endswith(".py") and not file.startswith("."):
                        filepath = os.path.realpath(os.path.join(root, file))
                        fp = get_file_fingerprint(filepath)
                        if fp:
                            fingerprints[filepath] = fp
            return fingerprints

        try:
            last_state = scan_files()
            console.print(f"[bold green]✔ Live File Watcher Active[/bold green] [dim](Tracking {len(last_state)} files in {BASE_DIR})[/dim]\n")
        except Exception as init_err:
            console.print(f"[bold red]Watcher Init Failed:[/bold red] {init_err}")
            return

        while True:
            try:
                time.sleep(1.0)
                current_state = scan_files()

                changed_files = []
                new_files = []

                for path, fp in current_state.items():
                    if path not in last_state:
                        new_files.append(path)
                    elif last_state[path] != fp:
                        changed_files.append(path)

                if changed_files or new_files:
                    last_state = current_state
                    timestamp_str = time.strftime("%H:%M:%S")

                    for filepath in new_files:
                        rel_path = os.path.relpath(filepath, BASE_DIR)
                        console.print("\n")
                        console.print(Panel(
                            f"[bold cyan]🆕 NEW FILE CREATED IN WORKSPACE[/bold cyan]\n\n"
                            f"📁 [bold white]File Path:[/bold white] [dim]{rel_path}[/dim]\n"
                            f"⏱️ [bold white]Detected At:[/bold white] [dim]{timestamp_str}[/dim]",
                            title="[bold cyan]WORKSPACE FILE ADDED[/bold cyan]",
                            border_style="cyan"
                        ))

                    for filepath in changed_files:
                        rel_path = os.path.relpath(filepath, BASE_DIR)
                        
                        if rel_path == "cli.py":
                            console.print("\n")
                            console.print(Panel(
                                f"[bold yellow]⚠️ cli.py edit detected at {timestamp_str}![/bold yellow]\n"
                                "Main runner script changes apply karne ke liye app restart karein.",
                                border_style="yellow"
                            ))
                            continue

                        mod_name = rel_path.replace(os.sep, ".").rstrip(".py")
                        if mod_name.endswith(".__init__"):
                            mod_name = mod_name[:-9]

                        with model_lock:
                            if mod_name in sys.modules:
                                reloaded_mod = importlib.reload(sys.modules[mod_name])
                            else:
                                reloaded_mod = importlib.import_module(mod_name)

                            patched_list = patch_organ_instances(jarvis, reloaded_mod)
                            patch_info = f"\n🧩 [bold white]Patched Organs:[/bold white] [green]{', '.join(patched_list)}[/green]" if patched_list else ""

                            console.print("\n")
                            console.print(Panel(
                                f"[bold yellow]⚡ MT MANAGER FILE CHANGE DETECTED[/bold yellow]\n\n"
                                f"📁 [bold white]File Path:[/bold white] [dim]{rel_path}[/dim]\n"
                                f"⚙️ [bold white]Module Name:[/bold white] [bold cyan]{mod_name}[/bold cyan]\n"
                                f"⏱️ [bold white]Applied At:[/bold white] [dim]{timestamp_str}[/dim]"
                                f"{patch_info}\n"
                                f"🧠 [bold green]Status:[/bold green] Live-Patched into RAM",
                                title="[bold green]HOT-RELOAD SUCCESSFUL[/bold green]",
                                border_style="green"
                            ))

                            if web_event_broadcaster and callable(web_event_broadcaster):
                                web_event_broadcaster({
                                    "type": "system_toast",
                                    "level": "success",
                                    "title": "Module Live Patched",
                                    "message": f"Updated {mod_name} instantly!",
                                    "timestamp": timestamp_str
                                })

            except Exception as loop_err:
                time.sleep(1.0)

    watcher_thread = threading.Thread(target=_watch_loop, daemon=True)
    watcher_thread.start()

def main():
    global _global_jarvis_instance
    print_banner()

    menu_panel = Panel.fit(
        "[bold yellow]Select Runtime Execution Target:[/bold yellow]\n\n"
        "  [bold cyan][1][/bold cyan] [bold white]CLI Diagnostic Mode[/bold white] (Pure Local Terminal, No Server)\n"
        "  [bold cyan][2][/bold cyan] [bold white]Web PWA Container Mode[/bold white] (Single FastAPI Server + Full Bi-directional CLI Live Sync)\n"
        "  [bold cyan][3][/bold cyan] [bold white]Development Mode[/bold white] (Full Synchronized Error Traces)\n",
        title="[bold magenta]CONTROL INTERFACE SELECTION[/bold magenta]",
        border_style="cyan"
    )
    console.print(menu_panel)
    
    choice = console.input("[bold yellow]Option Selection (1, 2, or 3): [/bold yellow]").strip()

    console.print("\n[bold yellow]Initializing JARVIS Subsystems...[/bold yellow]")
<<<<<<< HEAD
    jarvis = start_jarvis(
        heartbeat_interval=2.0,
        idle_threshold=10.0,
    )
=======
    jarvis = start_jarvis(heartbeat_interval=2.0, idle_threshold=10.0)

    # RUNTIME LIFECYCLE. Records this run and flags any previous run that
    # never wrote a shutdown -- i.e. was killed. Termux went down several
    # times with nothing recording it; now there is a timestamped row.
    try:
        from core.runtime.session_registry import record_start, record_stop, touch_session
        import atexit
        record_start()
        atexit.register(lambda: record_stop("clean"))

        # RESOURCE SAMPLING. Starts with the process so the minutes
        # before a crash are already on disk when it happens -- an OOM
        # kill runs no handler, so the breadcrumb trail IS the
        # diagnosis.
        from core.runtime.resource_monitor import start as _res_start, stop as _res_stop
        _res_start(brain=getattr(jarvis, "brain", None))
        atexit.register(_res_stop)
    except Exception:
        touch_session = None

    # NO LOGIN PROMPT HERE (2026-09-14, per UK's spec section 5/6).
    #
    # cli.py is the runtime CONTROL interface -- it starts the servers,
    # monitors the organism and displays traces. It is infrastructure,
    # not a person. Making it ask for a password was wrong twice:
    #   - on a cloud box the server must start unattended, and
    #   - "SERVER IDENTITY != USER IDENTITY" (spec section 6).
    #
    # Identity comes from authenticated frontend sessions. The CLI
    # operator proves who they are with /login when they want to SEE
    # something restricted -- not to start the process.
    _cli_viewer = {"role": "guest", "is_verified": False, "username": None,
                   "channel": "cli", "session_id": "cli"}
    globals()["_CLI_VIEWER"] = _cli_viewer
>>>>>>> 90fbd2a (Save local project changes before branch checkout)
    _global_jarvis_instance = jarvis

    brain = jarvis.get_organ("brain")
    if brain:
        console.print("[cyan]Connecting LLM Inference Engine to Core Brain...[/cyan]")
        try:
            brain.llm = LlamaCppBridge(
                model_filename="qwen2.5-3b-instruct-q4_k_m.gguf", 
                n_threads=4,
                n_ctx=4096
            )
            # THE ACTUAL BUG THIS FIXES: constructing HybridLLMBridge
            # never used to try loading anything -- it always
            # "succeeded" even if llama-cpp-python wasn't installed
            # or the GGUF file was missing/misnamed, so this message
            # printed green regardless of whether the model would
            # ever actually respond. verify_offline_ready() forces the
            # real load right now, so a broken setup is caught here,
            # loudly, with the real Python exception -- not silently,
            # three steps later, disguised as a chat reply.
            console.print("[cyan]Loading offline model into RAM (this can take a minute)...[/cyan]")
            if brain.llm.verify_offline_ready():
                console.print("[bold green]Neural Bridge Online -- offline model loaded and verified.[/bold green]\n")
            else:
                console.print(
                    f"[bold red]Neural Bridge NOT ready -- model failed to load: "
                    f"{brain.llm.last_error}[/bold red]\n"
                    f"[dim]Common causes: llama-cpp-python not installed "
                    f"(pip install llama-cpp-python), or the .gguf file isn't at "
                    f"models/qwen2.5-3b-instruct-q4_k_m.gguf.[/dim]\n"
                )
        except Exception as e:
            console.print(f"[bold red]Neural Bridge Connection Failure: {e}[/bold red]\n")
            
    start_silent_heartbeat_sync(jarvis)

    if choice == "3":
        console.print("[bold yellow]⚡ Development Mode Active: Hot-Reload Watcher Enabled.[/bold yellow]")
        start_live_module_watcher(jarvis)
    else:
        console.print("[dim white]ℹ️ Static Mode Active: Live File Watcher disabled.[/dim white]")

    if choice in ["2", "3"]:
        console.print("[bold green]Starting background FastAPI server for Web Integration...[/bold green]")
        
        server_thread = threading.Thread(
            target=start_web_server_thread,
            args=(jarvis,),
            daemon=True
        )
        server_thread.start()
        time.sleep(1.5)
        console.print("[bold cyan]Bi-Directional Telemetry Stream Active. Access dashboard at http://127.0.0.1:8000[/bold cyan]\n")

    EXIT_COMMANDS = ["exit", "quit", "shutdown", "stop", "q"]

    try:
        while True:
            try:
                user_input = console.input("[bold cyan]UK > [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Termination signal received.[/bold red]")
                break

            if not user_input:
                continue

            if user_input.lower() in EXIT_COMMANDS:
                console.print("\n[bold yellow]Terminated by operator. Shutting down system...[/bold yellow]")
                break

            if user_input.lower() == "status":
                render_organ_matrix(jarvis)
                continue

            elif user_input.lower() == "memory":
                memory = jarvis.get_organ("memory")
                if memory and hasattr(memory, "statistics"):
                    stats = memory.statistics()
                    console.print(Panel(f"[bold cyan]Memory Statistics:[/bold cyan]\n{stats}", border_style="blue"))
                else:
                    console.print("[red]Memory metrics inaccessible.[/red]")
                continue

            execute_cognitive_query(jarvis, user_input, source="cli")

    except KeyboardInterrupt:
        console.print("\n[bold red]Execution interrupted by user.[/bold red]")

    finally:
        stop_jarvis(jarvis)
        console.print("[dim text-gray]SYSTEM STATE: OFFLINE[/dim text-gray]")

if __name__ == "__main__":
    main()
