# -*- coding: utf-8 -*-
"""JARVIS terminal/runtime control interface.

The CLI is intentionally a runtime control surface, not a second cognition
engine. While idle it continuously monitors the organism's real lifecycle and
organ health. When a query arrives, the active Brain produces the single
cognitive turn and deep_inspector.py renders that exact turn data.
"""

import os
import socket
import signal
import sys
import time
import warnings
import threading
import traceback
import importlib
import hashlib
import json
import subprocess
import urllib.request
from typing import Any, Dict, Optional

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
warnings.filterwarnings("ignore")

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
from core.memory.inspect_memory import render_dashboard as render_memory_dashboard
from cli_runtime_monitor import OrganismCLIMonitor
from deep_inspector import render_query_trace

console = Console()

web_event_broadcaster = None
model_lock = threading.Lock()
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
    "/pending_rules": "List self-authored rules JARVIS has proposed but you haven't confirmed yet",
    "/confirm_rule <n>": "Confirm pending self-authored rule #n (from /pending_rules) -- only then does it start influencing responses",
    "/reject_rule <n>": "Reject pending self-authored rule #n -- remembered as rejected, so the identical rule won't be re-proposed later",
    "/explain_rule <n>": "Show WHY JARVIS proposed pending self-authored rule #n -- the actual reasoning evidence, not just the final rule text",
    "/instructions": "List active daily standing instructions (e.g. \"roz subah good morning bolo\") and their next trigger time",
    "/remove_instruction <n>": "Delete standing instruction #n (from /instructions) outright",
    "/contested_facts": "List facts where a less-trusted source tried to overwrite a more-trusted one and was held back for your review",
    "/resolve_contested <n> <accept|keep>": "Resolve contested fact #n (from /contested_facts) -- accept applies the proposed new value, keep discards it",
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


def print_banner():
    console.print(
        Panel.fit(
            "[bold cyan]JARVIS COGNITIVE OS[/bold cyan] [dim]v2026.1[/dim]\n"
            "[dim white]Real-time Organism Runtime & Cognitive Lifecycle Monitor[/dim white]",
            border_style="cyan",
            subtitle="[dim]UK ARCHITECTURE WORKSPACE[/dim]",
        )
    )
    print_cli_commands()


def print_cli_commands():
    table = Table(title="JARVIS CLI COMMANDS", border_style="cyan", header_style="bold cyan")
    table.add_column("Command", style="bold yellow", width=22)
    table.add_column("Purpose", style="white")
    for command, description in CLI_COMMANDS.items():
        table.add_row(command, description)
    table.add_row("exit / quit", "Shutdown JARVIS")
    console.print(table)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fmt(value: Any, limit: int = 220) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _stage(tree: Tree, number: str, title: str, status: str, details: str = ""):
    label = f"[bold]{number}[/bold] [bold white]{title}[/bold white]  {status}"
    branch = tree.add(label)
    if details:
        branch.add(f"[dim]{_fmt(details)}[/dim]")
    return branch


def _status_text(ok: bool, true_label: str = "COMPLETED", false_label: str = "NOT EXPOSED") -> str:
    return f"[bold green]{true_label}[/bold green]" if ok else f"[bold yellow]{false_label}[/bold yellow]"


def render_organ_matrix(jarvis):
    table = Table(
        title="SYSTEM SUBSYSTEM & ORGAN DIAGNOSTICS MATRIX",
        border_style="blue",
        header_style="bold cyan",
        title_style="bold white",
    )
    table.add_column("Organ Designation", style="bold white", width=24)
    table.add_column("Class Type", style="dim white", width=22)
    table.add_column("State", justify="center", width=14)
    table.add_column("Operational Role & Diagnostics", style="dim")

    organs_status = jarvis.get_organ_status() if hasattr(jarvis, "get_organ_status") else {}
    for name, info in organs_status.items():
        info = _safe_dict(info)
        attached = bool(info.get("attached", False))
        state = "[bold green]ONLINE[/bold green]" if attached else "[bold red]OFFLINE[/bold red]"
        table.add_row(name, str(info.get("type", "Subsystem")), state, describe_organ(jarvis, name, info))

    hb_status = jarvis.heartbeat.status() if getattr(jarvis, "heartbeat", None) else {}
    hb_status = _safe_dict(hb_status)
    hb_state = "[bold green]ACTIVE[/bold green]" if hb_status.get("running") else "[bold red]STOPPED[/bold red]"
    table.add_row(
        "heartbeat_daemon",
        "Background Thread",
        hb_state,
        f"Beat Pulses: {hb_status.get('beat_count', 0)} | Idle State: {hb_status.get('is_idle', False)}",
    )

    brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
    if brain is not None and hasattr(brain, "status"):
        try:
            queue_status = _safe_dict(brain.status().get("async_learning_queue", {}))
        except Exception:
            queue_status = {}
        q_alive = bool(queue_status.get("alive", False))
        q_state = "[bold green]ACTIVE[/bold green]" if q_alive else "[bold red]STOPPED[/bold red]"
        table.add_row(
            "async_learning_queue",
            "Background Thread",
            q_state,
            f"Pending: {queue_status.get('pending', 0)} | Processed: {queue_status.get('processed', 0)} | Failed: {queue_status.get('failed', 0)} | Dropped: {queue_status.get('dropped', 0)}",
        )

    llm_bridge = getattr(brain, "llm", None) if brain is not None else None
    if llm_bridge is not None:
        ready = bool(getattr(llm_bridge, "is_ready", False))
        last_error = getattr(llm_bridge, "last_error", None)
        model_name = getattr(llm_bridge, "_model_filename", "unknown.gguf")
        if ready:
            llm_state = "[bold green]ONLINE[/bold green]"
            metrics = f"Offline bridge | model={model_name} | verified loaded"
        elif last_error:
            llm_state = "[bold red]FAILED[/bold red]"
            metrics = f"model={model_name} | error: {last_error}"
        else:
            llm_state = "[bold yellow]UNVERIFIED[/bold yellow]"
            metrics = f"model={model_name} | not yet loaded"
        table.add_row("llm", type(llm_bridge).__name__, llm_state, metrics)
    else:
        table.add_row("llm", "HybridLLMBridge", "[bold red]DISCONNECTED[/bold red]", "brain.llm is None")

    console.print(table)


def render_cognition_trace(brain: Any, trace: Optional[Dict[str, Any]], source: str = "cli"):
    """Legacy renderer retained for compatibility; query rendering is now owned by deep_inspector."""
    return None


def _brain(jarvis):
    return jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None


def _memory(jarvis):
    return jarvis.get_organ("memory") if hasattr(jarvis, "get_organ") else None


def render_memory_inspection(jarvis):
    """Run the repository's canonical semantic-memory diagnostic dashboard.

    This reuses core/memory/inspect_memory.py instead of duplicating its
    SQLite/FAISS/graph inspection logic inside the CLI. The dashboard reads
    the configured live database/index and does not invoke pytest fixtures.
    """
    try:
        render_memory_dashboard()
    except Exception as exc:
        console.print(
            Panel(
                f"[bold red]Memory inspection failed:[/bold red]\n{traceback.format_exc()}",
                title="JARVIS MEMORY INSPECTION ERROR",
                border_style="red",
            )
        )


def render_trace_inspection(jarvis):
    brain = _brain(jarvis)
    trace = getattr(brain, "last_turn_trace", None) if brain is not None else None
    if trace:
        query = trace.get("user_input") or trace.get("query") or "<latest>"
        response = trace.get("response")
        render_query_trace(brain, trace, source="cli", query=query, response=response)
    else:
        console.print(Panel("[yellow]No cognitive turn trace is currently available.[/yellow]", title="JARVIS TRACE INSPECTION", border_style="yellow"))


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


def start_silent_heartbeat_sync(jarvis):
    def _sync_loop():
        while True:
            try:
                time.sleep(3.0)
                if web_event_broadcaster and callable(web_event_broadcaster):
                    hb = jarvis.heartbeat.status() if getattr(jarvis, "heartbeat", None) else {}
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
                        "beats": hb.get("beat_count", 0),
                        "state": "Idle Scanning" if hb.get("is_idle", True) else "Active Processing",
                        "learning_queue": queue_status,
                        "goals": goals_snapshot,
                    })
            except Exception:
                pass
    threading.Thread(target=_sync_loop, daemon=True).start()


def _connect_llm_to_brain(brain):
    """Connect the same bridge through the Brain's official setter.
    Model choice is LOCKED in config/models.json -- HybridLLMBridge
    reads it itself, so nothing here needs to name a specific file."""
    bridge = LlamaCppBridge()
    if hasattr(brain, "set_llm_bridge") and callable(brain.set_llm_bridge):
        brain.set_llm_bridge(bridge)
    else:
        brain.llm = bridge
    return bridge


def _current_knowledge_count(brain: Any) -> Optional[int]:
    """Total rows in semantic memory right now, or None if unreachable.
    Used to compute a genuine before/after diff for the post-response
    follow-up rather than reporting a bare total that says nothing
    about whether THIS turn actually wrote anything."""
    memory = getattr(brain, "memory", None)
    semantic = getattr(memory, "semantic", None)
    if semantic is None:
        return None
    counter = getattr(semantic, "count", None)
    try:
        return int(counter) if counter is not None else None
    except (TypeError, ValueError):
        return None


def render_post_response_learning(brain: Any, poll_seconds: float = 1.0, poll_interval: float = 0.05, knowledge_count_before: Optional[int] = None) -> None:
    """AFTER the main reply + workflow panel are already on screen, this
    is the genuine "phir dubara, after-response evolution/next-cycle"
    follow-up: a SHORT, bounded wait for the background learning job
    THIS turn just queued to actually finish, then EVERYTHING that
    happened in that phase -- not just a reasoning summary, but
    semantic memory DB writes, evolution proposals, and self-rule
    adoption together, since a person genuinely watching the whole
    post-response phase (async/sync, evolution, learning, behavior,
    semantic memory save) wants all of it in one place, not scattered
    across separate commands. Bounded on purpose: never blocks the
    next prompt indefinitely -- if it hasn't finished within
    poll_seconds, says so honestly instead of pretending completion.
    """
    status_fn = getattr(brain, "status", None)
    if not callable(status_fn):
        return
    deadline = time.time() + poll_seconds
    finished = False
    while time.time() < deadline:
        try:
            queue_status = _safe_dict(status_fn()).get("async_learning_queue", {})
        except Exception:
            return
        if not queue_status.get("active") and int(queue_status.get("pending", 0) or 0) == 0:
            finished = True
            break
        time.sleep(poll_interval)

    console.print("[dim cyan]  ↳ POST-RESPONSE PHASE (async background cycle)[/dim cyan]")

    if not finished:
        console.print("[dim]    still processing -- check /runtime_inspect or monitor.py[/dim]")
        return

    # Semantic memory DB write -- genuine before/after diff, not a guess.
    count_after = _current_knowledge_count(brain)
    if knowledge_count_before is not None and count_after is not None:
        delta = count_after - knowledge_count_before
        if delta > 0:
            console.print(f"[dim]    semantic memory (DB): [green]+{delta} new record(s)[/green] written -- total now {count_after}[/dim]")
        else:
            console.print(f"[dim]    semantic memory (DB): no new record written this turn -- total unchanged at {count_after}[/dim]")
    else:
        console.print("[dim]    semantic memory (DB): could not verify (memory organ unreachable)[/dim]")

    # Reasoning cycle outcome.
    traces = getattr(brain, "last_reasoning_traces", None) or []
    latest = traces[-1] if traces and isinstance(traces[-1], dict) else {}
    if latest:
        if latest.get("adopt_as_learning"):
            console.print(f"[dim]    self-learning: [green]RULE ADOPTED[/green] -- \"{_fmt(latest.get('next_time_different', ''), limit=80)}\"[/dim]")
        elif latest.get("should_change_strategy"):
            console.print("[dim]    self-learning: flagged for possible strategy change (not yet adopted -- needs repeated evidence)[/dim]")
        else:
            console.print("[dim]    self-learning: no strategy change flagged this cycle[/dim]")
        llm_cost = latest.get("llm_cost") or {}
        if llm_cost.get("retry_used"):
            console.print(f"[dim]    LLM cost: retry {'paid off' if llm_cost.get('retry_paid_off') else 'did NOT pay off'}[/dim]")
    else:
        console.print("[dim]    self-learning: no reasoning trace recorded yet[/dim]")

    # Evolution -- was anything proposed as a result of this turn's pattern history.
    evolution = getattr(brain, "evolution", None)
    proposals = getattr(evolution, "proposals", None) if evolution is not None else None
    if isinstance(proposals, dict) and proposals:
        latest_proposal = max(proposals.values(), key=lambda p: p.get("created_at", 0) if isinstance(p, dict) else 0)
        age = time.time() - latest_proposal.get("created_at", time.time())
        if age < poll_seconds + 2.0:  # only mention it if it's fresh (from around this turn)
            console.print(f"[dim]    evolution: [yellow]NEW PROPOSAL[/yellow] [{latest_proposal.get('status')}] target={latest_proposal.get('target')} -- {_fmt(str(latest_proposal.get('reason', '')), limit=150)}[/dim]")


def render_workflow_panel(brain: Any, trace: Optional[Dict[str, Any]], total_duration: float):
    """The organized, complete per-turn workflow view shown after every
    message by default: one stage per line, in pipeline order, with the
    real numbers from that stage -- not the old unconditional raw
    contract-payload dump (which is still one command away: /verbose or
    /trace_inspect), and not just a bare one-line summary either. This
    is the single place that answers "what did JARVIS actually just do".
    """
    trace = _safe_dict(trace)
    perception = _safe_dict(trace.get("perception"))
    route = _safe_dict(trace.get("cognitive_route"))
    decision = _safe_dict(trace.get("brain_decision"))
    action_response = _safe_dict(trace.get("action_response"))
    context = _safe_dict(getattr(brain, "last_context", None))

    tree = Tree(f"[bold cyan]JARVIS WORKFLOW[/bold cyan] [dim]-- this turn, {total_duration:.2f}s[/dim]")

    # 1. PERCEPTION
    intent = perception.get("intent")
    intent_name = intent.get("name") if isinstance(intent, dict) else intent
    p_conf = perception.get("confidence")
    p_conf_txt = f"{float(p_conf):.2f}" if isinstance(p_conf, (int, float)) else "—"
    tree.add(
        f"[bold]1. PERCEPTION[/bold]   source=[yellow]{perception.get('source', '—')}[/yellow]  "
        f"intent=[white]{intent_name or '—'}[/white]  confidence={p_conf_txt}  lang={perception.get('language', '—')}"
    )

    # 2. INDEXING / MEMORY RETRIEVAL
    mem_n = len(context.get("recent_experiences") or [])
    know_n = len(context.get("relevant_knowledge") or [])
    graph_n = len(context.get("graph_relations") or [])
    tree.add(f"[bold]2. INDEXING[/bold]     memory=[white]{mem_n}[/white]  knowledge=[white]{know_n}[/white]  graph=[white]{graph_n}[/white]")

    # 2b. SEMANTIC UNDERSTANDING CONCLUSION -- what cognition actually
    # concluded about THIS turn's input (relations/entities extracted,
    # which provenance path produced it), distinct from stage 2's
    # memory RETRIEVAL counts above. Previously this was ONLY visible
    # via /verbose's raw per-layer contract dump; this is the readable
    # conclusion of that same data, shown by default.
    semantic = perception.get("semantic_understanding") if isinstance(perception.get("semantic_understanding"), dict) else {}
    if semantic:
        s_relations = semantic.get("relations") or []
        s_entities = semantic.get("entities") or []
        s_provenance = _safe_dict(semantic.get("provenance")).get("source", semantic.get("provenance", "—"))
        s_conf = semantic.get("confidence")
        s_conf_txt = f"{float(s_conf):.2f}" if isinstance(s_conf, (int, float)) else "—"
        degraded = _safe_dict(semantic.get("provenance")).get("degraded", False)
        style = "red" if degraded else "green"
        rel_preview = ""
        if s_relations:
            first = s_relations[0]
            if isinstance(first, dict):
                rel_preview = f"  e.g. {first.get('subject', '?')}.{first.get('predicate', '?')}={_fmt(str(first.get('value', '')), limit=30)}"
        elif not degraded:
            # A common, previously-invisible failure mode: perception/
            # semantic understanding both reported reasonable confidence,
            # but the relation extractor still found NOTHING -- meaning
            # no fact was stored this turn even though nothing looked
            # "wrong" anywhere else in the trace. Surfacing this
            # explicitly is what actually answers "why did my statement
            # not get saved" without needing /verbose.
            rel_preview = "  [yellow]-- no relation extracted, nothing will be stored this turn[/yellow]"
        tree.add(
            f"[bold]2b. SEMANTIC UNDERSTANDING[/bold]  provenance=[{style}]{s_provenance}[/{style}]  "
            f"confidence={s_conf_txt}  relations_extracted=[white]{len(s_relations)}[/white]  "
            f"entities=[white]{len(s_entities)}[/white]{rel_preview}"
        )

    # 3a. COGNITION -- the router's raw evidence tuple, previously only
    # visible via /verbose's raw contract dump. This is what the
    # cognition layer actually SAW before the router made a decision:
    # how many memory/knowledge/graph matches existed, whether a skill
    # or active goal was available, and where the semantic result came
    # from -- the actual "brain" of the decision, not just its outcome.
    evidence = route.get("evidence")
    if isinstance(evidence, (list, tuple)) and evidence:
        try:
            ev = dict(evidence)
        except (TypeError, ValueError):
            ev = {}
        if ev:
            tree.add(
                f"[bold]3a. COGNITION[/bold]   memory_matches=[white]{ev.get('memory_matches', 0)}[/white]  "
                f"knowledge_matches=[white]{ev.get('knowledge_matches', 0)}[/white]  "
                f"graph_relations=[white]{ev.get('graph_relations', 0)}[/white]  "
                f"skills=[white]{ev.get('available_skills', 0)}[/white]  "
                f"goals=[white]{ev.get('active_goals', 0)}[/white]  "
                f"semantic_source=[yellow]{ev.get('semantic_source', '—')}[/yellow]"
            )

    # 3. ROUTING
    r_conf = route.get("confidence")
    r_conf_txt = f"{float(r_conf):.2f}" if isinstance(r_conf, (int, float)) else "—"
    # Previously truncated to 90 chars, which is EXACTLY why real
    # traces showed "...no executable native capability wa..." cut off
    # mid-sentence -- the actual reason existed in full, it was just
    # never shown. No truncation here now; routing reasons are short
    # enough (a sentence or two) that showing the full text costs
    # nothing and directly answers "kyun is tarah route hua" without
    # needing /verbose.
    reason = str(route.get("reason", "—"))
    tree.add(f"[bold]3. ROUTING[/bold]      route=[green]{route.get('mode', '—')}[/green]  confidence={r_conf_txt}\n    [dim]{reason}[/dim]")

    # 3b. LLM BUDGET -- calls actually made this turn, why, and how
    # many remain against the LOCKED per-turn ceiling (config/
    # cognition.json). Previously only visible via /verbose's raw
    # dump; this is the direct answer to "aakhir kyun LLM calls hue,
    # aur kitne" every single turn, not just on request.
    llm_bridge = getattr(brain, "llm", None)
    budget_fn = getattr(llm_bridge, "budget_status", None)
    if callable(budget_fn):
        try:
            budget = _safe_dict(budget_fn())
        except Exception:
            budget = {}
        if budget:
            why_parts = []
            p_source = perception.get("source", "")
            if p_source in ("llm", "llm_refined"):
                why_parts.append(f"perception needed LLM ({p_source})")
            elif p_source == "safe_fallback":
                why_parts.append("perception's own cascade was exhausted (native + LLM both did not produce a confident result)")
            s_prov = _safe_dict(_safe_dict(perception.get("semantic_understanding")).get("provenance"))
            if s_prov.get("source") in ("llm_fallback", "llm_fallback_refined"):
                why_parts.append(f"semantic understanding needed LLM ({s_prov.get('source')})")
            elif s_prov.get("source") == "reused_from_perception_llm":
                why_parts.append("semantic understanding REUSED perception's LLM result (0 extra calls)")
            if route.get("mode") == "llm" and decision.get("mode") == "llm":
                why_parts.append("final response phrasing (Brain's job is structuring data, LLM's job is wording it)")
            why_txt = "; ".join(why_parts) if why_parts else "no LLM calls needed -- fully native this turn"
            calls_made = budget.get("calls", 0)
            style = "green" if calls_made == 0 else ("yellow" if calls_made <= 2 else "red")
            tree.add(
                f"[bold]3b. LLM BUDGET[/bold]  calls_used=[{style}]{calls_made}[/{style}]/{budget.get('max_calls', '—')}  "
                f"remaining=[white]{budget.get('remaining_calls', '—')}[/white]  "
                f"tokens_used=[white]{budget.get('reserved_output_tokens', '—')}[/white]/{budget.get('max_output_tokens', '—')}\n"
                f"    [dim]why: {why_txt}[/dim]"
            )

    # 4. EXECUTION
    status = decision.get("status") or action_response.get("status") or "—"
    status_color = "green" if status in ("completed", "planned") else ("red" if status == "failed" else "yellow")
    action_payload = action_response.get("action")
    skill = decision.get("skill") or (action_payload.get("skill") if isinstance(action_payload, dict) else None)
    skill_txt = f"  skill={skill}" if skill else ""
    tree.add(f"[bold]4. EXECUTION[/bold]    mode=[white]{decision.get('mode', route.get('mode', '—'))}[/white]  status=[{status_color}]{status}[/{status_color}]{skill_txt}")

    # 4b. BRAIN -> RESPONSE HANDOFF -- what Brain's decision actually
    # passed downstream to response generation, and whether the
    # returned text stayed inside that handoff (see response_brief.py's
    # check_response_grounding). This is the literal "layer A output
    # = layer B input" boundary for the LLM route specifically.
    if "stayed_within_brief" in decision:
        grounded = decision.get("stayed_within_brief")
        g_style = "green" if grounded else "red"
        g_txt = "grounded -- response stayed within the structured brief Brain provided" if grounded else "[bold]FLAGGED[/bold] -- response may contain content not present in Brain's brief"
        tree.add(f"[bold]4b. BRAIN → RESPONSE[/bold]  [{g_style}]{g_txt}[/{g_style}]")

    # 4c. TOOL CALLS (2026-09-11 -- previously invisible in this panel
    # even though the tool-calling loop is tried BEFORE the plain
    # brief-driven path on every turn; UK's explicit complaint was not
    # being able to tell whether/why it fired without a separate
    # /tool_trace call). Shown only when this exact turn actually used
    # it, so it doesn't clutter turns that didn't need a tool.
    tool_trace = getattr(brain, "last_tool_call_trace", None)
    if tool_trace:
        branch = tree.add(f"[bold]4c. TOOL CALLS[/bold]  {len(tool_trace)} call(s) this turn (LLM-decided, not hardcoded)")
        for call in tool_trace[-5:]:
            if call.get("builtin_tool"):
                branch.add(f"[cyan]browser_search[/cyan] (server-side)")
            else:
                result = call.get("result") or {}
                failed = isinstance(result, dict) and result.get("error")
                style = "red" if failed else "green"
                branch.add(f"[{style}]{call.get('name')}[/{style}]  args={call.get('arguments')}")

    # 5. LEARNING (background, async -- may still be pending as this renders)
    queue_status = {}
    dependency_metrics = {}
    status_fn = getattr(brain, "status", None)
    if callable(status_fn):
        try:
            full_status = _safe_dict(status_fn())
            queue_status = full_status.get("async_learning_queue", {})
            dependency_metrics = full_status.get("dependency_metrics", {})
        except Exception:
            pass
    learning_txt = (
        f"queued -> pending=[white]{queue_status.get('pending', '—')}[/white] "
        f"processed=[white]{queue_status.get('processed', '—')}[/white] "
        f"failed=[white]{queue_status.get('failed', '—')}[/white]"
        if decision.get("mode") != "error" else "[dim]skipped (pipeline error)[/dim]"
    )
    tree.add(f"[bold]5. LEARNING[/bold]     {learning_txt}")

    # 6. LEARNING RESULT -- what actually happened, not just a queue
    # counter. Background learning is async (see LearningQueue), so
    # what's shown here is the MOST RECENTLY COMPLETED cycle at render
    # time -- usually this turn's, but if processing hasn't finished
    # yet it may still reflect the previous turn; that honest caveat
    # beats pretending completion that hasn't happened. Rule capture
    # is synchronous (runs before the LLM call), so that line is
    # always accurate for THIS turn specifically.
    rule_store = getattr(brain, "_user_rules", None)
    rule_line = "no rule captured this turn"
    if rule_store is not None:
        try:
            active = rule_store.get_active_rules(limit=1)
            if active:
                rule_line = f"active rule on file: \"{active[0]}\""
        except Exception:
            pass

    traces = getattr(brain, "last_reasoning_traces", None) or []
    if traces:
        latest = traces[-1] if isinstance(traces[-1], dict) else {}
        mode_seen = latest.get("mode", "—")
        should_change = latest.get("should_change_strategy", False)
        adopt = latest.get("adopt_as_learning", False)
        llm_cost = latest.get("llm_cost") or {}
        parts = [f"latest completed cycle: mode={mode_seen}"]
        if llm_cost.get("retry_used"):
            parts.append(f"retry {'paid off' if llm_cost.get('retry_paid_off') else 'did NOT pay off'}")
        if adopt:
            parts.append(f"[green]SELF-RULE ADOPTED[/green]: \"{_fmt(latest.get('next_time_different', ''), limit=70)}\"")
        elif should_change:
            parts.append("flagged for possible strategy change (not yet adopted -- needs repeated evidence)")
        reasoning_txt = "  ".join(parts)
    else:
        reasoning_txt = "no reasoning cycle completed yet this session"

    retry_rate = dependency_metrics.get("retry_value_rate")
    retry_rate_txt = f"{retry_rate:.2f}" if isinstance(retry_rate, (int, float)) else "—"

    # Explicit, readable "why" for knowledge extraction -- directly
    # answers "knowledge kyun nahi extract hui, iska proper reason
    # hona chahiye". Reuses the SAME semantic_understanding data
    # already computed for stage 2b, so this is never a second,
    # possibly-inconsistent guess -- it is the same evidence, just
    # summarized here as a clear yes/no + reason instead of raw counts.
    s_relations = semantic.get("relations") or [] if semantic else []
    s_provenance_dict = _safe_dict(semantic.get("provenance")) if semantic else {}
    if s_relations:
        first = s_relations[0]
        knowledge_line = f"[green]YES[/green] -- {first.get('subject', '?')}.{first.get('predicate', '?')}={_fmt(str(first.get('value', '')), limit=40)}"
    elif not semantic:
        knowledge_line = "[yellow]NO[/yellow] -- semantic understanding did not run this turn (no perception input to analyze)"
    elif s_provenance_dict.get("degraded"):
        # No truncation here now -- "extraction degraded: <reason>" is
        # exactly the WHY answer this line exists to give, and the
        # previous 70-char cutoff is what produced real traces reading
        # "...LLM per-level call budget exceed..." with the actual
        # explanation chopped off mid-sentence.
        knowledge_line = f"[yellow]NO[/yellow] -- extraction degraded: {str(s_provenance_dict.get('reason', 'unknown'))}"
    else:
        knowledge_line = "[yellow]NO[/yellow] -- no statement pattern matched (question/greeting/command, not a fact to store)"

    tree.add(
        f"[bold]6. LEARNING RESULT[/bold]  knowledge_stored: {knowledge_line}\n"
        f"    [dim]{rule_line}[/dim]\n"
        f"    [dim]{reasoning_txt}[/dim]\n"
        f"    [dim]native_resolution_rate={dependency_metrics.get('native_resolution_rate', '—')}  "
        f"retry_value_rate={retry_rate_txt}[/dim]"
    )

    console.print(Panel(tree, border_style="blue", padding=(0, 1)))


def execute_cognitive_query(jarvis, user_input: str, source: str = "cli") -> str:
    with model_lock:
        brain = jarvis.get_organ("brain")
        start_total = time.time()
        now = time.time()
        if getattr(jarvis, "state", None) is not None:
            if hasattr(jarvis.state, "update"):
                jarvis.state.update(last_activity_at=now)
            else:
                setattr(jarvis.state, "last_activity_at", now)

        # Captured BEFORE the turn runs so the post-response follow-up
        # can show a genuine before/after diff ("a new fact was
        # actually written to semantic memory") instead of just a
        # current total that says nothing about THIS turn specifically.
        knowledge_count_before = _current_knowledge_count(brain)

        jarvis.receive_event("USER_INPUT", {"text": user_input}, source=source)
        reply = "[System Error: Core Cognitive Engine Offline]"
        error_stack = None

        if brain:
            identity_profile = {
                "name": "JARVIS",
                "creator": "UK",
                "nature": "Modular Cognitive Organism",
                "instruction": "Respond accurately in Hinglish directly as JARVIS. User is UK, your creator.",
            }
            try:
                reply = brain.think_and_respond(user_input, identity_profile=identity_profile, source=source)
            except Exception as err:
                reply = f"[Brain Processing Fault: {err}]"
                error_stack = traceback.format_exc()

        total_duration = time.time() - start_total
        trace = getattr(brain, "last_turn_trace", None) if brain is not None else None

        # THE ACTUAL FIX (UK's explicit ask: "chat aur conversation
        # thread stored nahi hote kahi"): terminal-typed turns never
        # reached the SAME SQLite chat_messages table the web/websocket
        # paths already write to (see backend/routes_frontend_v6.py's
        # chat_v6 and backend/routes_ws.py's _handle_user_message) -- so
        # every conversation held directly in this terminal vanished the
        # moment the process exited, and never showed up in the web
        # Trace Inspector's turn history either. Lazy-imported and fully
        # guarded: `python3 cli.py` option 1 (pure CLI, no web server)
        # must keep working even on a machine without fastapi installed,
        # since backend.ws_manager imports fastapi at module level.
        # Uses "main_session" to match the SAME session_id the
        # web_event_broadcaster call below already uses for this exact
        # turn, so a browser watching that session sees one unified
        # thread instead of two disconnected ones.
        if not error_stack:
            try:
                from backend import database as _backend_db
                from backend.trace_utils import real_turn_trace as _real_turn_trace, turn_trace_to_json as _trace_to_json, extracted_fact_from_trace as _fact_from_trace
                _backend_db.save_message_to_db(session_id="main_session", sender="user", text=user_input, source=source)
                _cli_trace = _real_turn_trace(brain)
                _cli_fact = _fact_from_trace(_cli_trace)
                _backend_db.save_message_to_db(
                    session_id="main_session", sender="jarvis", text=reply, source=source,
                    trace_log=_trace_to_json(_cli_trace),
                    extracted_fact=json.dumps(_cli_fact) if _cli_fact else None,
                )
            except Exception:
                # Persistence is additive -- a missing/broken backend
                # package must never break the chat turn that already
                # succeeded and is about to be printed.
                pass

        if not error_stack:
            render_workflow_panel(brain, trace, total_duration)
            render_post_response_learning(brain, knowledge_count_before=knowledge_count_before)
        if _verbose_trace and not error_stack:
            # Full per-layer raw contract-payload dump, additive on top
            # of the organized panel above -- for deep debugging, not
            # every-turn reading.
            render_query_trace(
                brain,
                trace,
                source=source,
                query=user_input,
                response=reply,
            )

        if error_stack:
            console.print(
                Panel(
                    f"[bold red]RUNTIME EXCEPTION DETECTED ({source.upper()}):[/bold red]\n{error_stack}",
                    border_style="red",
                    title="[bold red]System Error Fault[/bold red]",
                )
            )
        else:
            console.print(
                Panel(
                    f"[white]{reply}[/white]",
                    title=f"[bold green]JARVIS Output ({source.upper()})[/bold green]",
                    border_style="cyan",
                )
            )
            if _voice_enabled:
                try:
                    from core.runtime.voice import speak
                    speak(reply)
                except Exception:
                    pass

        if web_event_broadcaster and callable(web_event_broadcaster):
            try:
                # THE ACTUAL SYNC BUG: this used to broadcast type
                # "cli_stream" -- a generic one-line log summary, NOT
                # the "chat_response" shape VirtualCLIScreen/
                # UserChatView actually render as a real chat turn (see
                # routes_ws.py's _handle_user_message, which broadcasts
                # this exact shape for WEB-originated turns). A
                # terminal-originated turn never matched that shape, so
                # even a frontend that DOES listen on /ws would never
                # have shown it as a synced reply -- only as an
                # unrelated log line, if anything rendered it at all.
                # Sending the SAME shape here means terminal and web
                # turns are indistinguishable to anything listening.
                web_event_broadcaster({
                    "type": "chat_response",
                    "sender": "jarvis",
                    "text": reply,
                    "session_id": "main_session",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": source,
                })
                web_event_broadcaster({
                    "type": "cli_stream",
                    "text": f"[{source.upper()}] Query: {user_input} -> Responded ({total_duration:.2f}s)",
                    "tag": "INFO",
                })
            except Exception as b_err:
                console.print(f"[dim red]Web broadcast sync error: {b_err}[/dim red]")
        return reply


def process_query(user_input: str, source: str = "web") -> str:
    global _global_jarvis_instance
    if _global_jarvis_instance:
        return execute_cognitive_query(_global_jarvis_instance, user_input, source=source)
    return "Engine Not Initialized in CLI Process."


def start_web_server_thread(jarvis):
    """Start backend :8000 and bind the shared CLI query executor."""
    global web_event_broadcaster, _global_jarvis_instance
    _global_jarvis_instance = jarvis
    try:
        import main as app_module

        if hasattr(app_module, "set_shared_organism"):
            app_module.set_shared_organism(jarvis)
        else:
            app_module.jarvis = jarvis
        if hasattr(app_module, "bind_query_executor"):
            app_module.bind_query_executor(process_query)
        if hasattr(app_module, "attach_console"):
            app_module.attach_console(console)
        if hasattr(app_module, "broadcast_to_clients"):
            web_event_broadcaster = app_module.broadcast_to_clients
        if hasattr(app_module, "start_server_in_thread"):
            app_module.start_server_in_thread()
            console.print("[bold green]Web Engine Server Thread Successfully Started on :8000.[/bold green]")
    except Exception:
        console.print(Panel(f"[bold red]Web Server Initialization Exception:[/bold red]\n{traceback.format_exc()}", border_style="red"))


def _http_ready(url, timeout=1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def _port_in_use(host: str, port: str) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except Exception:
        return False


def _kill_stale_frontend_on_port(host: str, port: str) -> None:
    """THE ACTUAL FIX for the "two ports" issue: start_frontend_server()
    launches Vite with start_new_session=True (deliberately, so a Vite
    crash never takes the whole CLI down with it) -- but that same
    detachment means if THIS CLI process ever exits without calling
    stop_frontend_server() (Ctrl+C, a crash, terminal closed), the Vite
    child is orphaned and keeps holding the port indefinitely. Next
    launch, Vite (or, before the strictPort fix in vite.config.ts,
    silently) either fails or jumps to :5174/:5175, and the port this
    function was TOLD to check never matches where it's actually
    running. This finds and clears exactly that stale process -- by
    port, not by remembered PID, since the PID is long gone with the
    old CLI process -- before starting a fresh one."""
    if not _port_in_use(host, port):
        return
    console.print(f"[bold yellow]Port {port} is already in use[/bold yellow] -- likely a stale process from a previous session. Attempting to clear it...")
    pids: list = []
    try:
        result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True, timeout=3)
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except Exception:
        pids = []
    if not pids:
        # `lsof` is frequently just not installed on a minimal Termux
        # setup -- this was silently giving up right here before,
        # which is exactly why UK still had to `pkill -f node/python`
        # by hand every time despite this function existing. Try
        # `fuser` next (more commonly present on Linux/Termux).
        try:
            result = subprocess.run(["fuser", f"{port}/tcp"], capture_output=True, text=True, timeout=3)
            pids = [p.strip() for p in result.stdout.split() if p.strip().isdigit()]
        except Exception:
            pids = []
    if not pids:
        # Last resort, pure-Python, no external binary required at
        # all: scan processes directly via psutil (already a project
        # dependency). This is the fallback that should make port
        # cleanup work regardless of which command-line tools happen
        # to be installed on this particular device.
        try:
            import psutil
            for proc in psutil.process_iter(["pid"]):
                try:
                    for conn in proc.net_connections(kind="inet"):
                        if conn.laddr and conn.laddr.port == int(port) and conn.status == psutil.CONN_LISTEN:
                            pids.append(str(proc.pid))
                except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):
                    continue
        except ImportError:
            pids = []
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except Exception:
            pass
    if pids:
        time.sleep(1.0)
    if _port_in_use(host, port):
        console.print(f"[bold red]Could not free port {port}[/bold red] -- free it manually (`fuser -k {port}/tcp` or `kill <pid>`).")


def start_frontend_server():
    global _frontend_process
    frontend_dir = os.environ.get("JARVIS_FRONTEND_DIR", os.path.join(BASE_DIR, "web_frontend"))
    if not os.path.isdir(frontend_dir):
        console.print(f"[bold red]New frontend directory not found:[/bold red] {frontend_dir}")
        return None
    port = os.environ.get("JARVIS_FRONTEND_PORT", "5173")
    host = os.environ.get("JARVIS_FRONTEND_HOST", "127.0.0.1")
    _kill_stale_frontend_on_port(host, port)
    node_bin = os.environ.get("JARVIS_VITE_BIN")
    command = [node_bin, "--host", host, "--port", port] if node_bin and os.path.isfile(node_bin) else ["npm", "run", "dev", "--", "--host", host, "--port", port]
    try:
        _frontend_process = subprocess.Popen(
            command,
            cwd=frontend_dir,
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            start_new_session=True,
        )
    except Exception as exc:
        console.print(f"[bold red]Vite startup failed:[/bold red] {exc}")
        console.print("[dim]Set JARVIS_VITE_BIN to your Vite binary, or ensure npm is available.[/dim]")
        _frontend_process = None
        return None
    console.print(f"[cyan]New frontend starting on http://{host}:{port} ...[/cyan]")
    for _ in range(30):
        if _frontend_process.poll() is not None:
            console.print(f"[bold red]Vite exited during startup (code {_frontend_process.returncode}).[/bold red]")
            _frontend_process = None
            return None
        if _http_ready(f"http://{host}:{port}/"):
            console.print(f"[bold green]New frontend ONLINE: http://{host}:{port}[/bold green]")
            return _frontend_process
        time.sleep(0.25)
    console.print(f"[bold yellow]Vite process is running, but :{port} has not answered yet.[/bold yellow]")
    return _frontend_process


def stop_frontend_server():
    global _frontend_process
    proc = _frontend_process
    _frontend_process = None
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def patch_organ_instances(jarvis, reloaded_mod):
    patched_organs = []
    classes_in_mod = {name: obj for name, obj in reloaded_mod.__dict__.items() if isinstance(obj, type)}
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
            console.print(f"[bold green]Live File Watcher Active[/bold green] [dim](Tracking {len(last_state)} files in {BASE_DIR})[/dim]\n")
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
                        console.print(Panel(f"[bold cyan]NEW FILE CREATED[/bold cyan]\n\nFile: [white]{rel_path}[/white]\nDetected: [dim]{timestamp_str}[/dim]", title="WORKSPACE FILE ADDED", border_style="cyan"))
                    for filepath in changed_files:
                        rel_path = os.path.relpath(filepath, BASE_DIR)
                        if rel_path == "cli.py":
                            console.print(Panel(f"[bold yellow]cli.py edit detected at {timestamp_str}.[/bold yellow]\nRestart the runner to apply cli.py changes.", border_style="yellow"))
                            continue
                        mod_name = rel_path.replace(os.sep, ".").rstrip(".py")
                        if mod_name.endswith(".__init__"):
                            mod_name = mod_name[:-9]
                        with model_lock:
                            try:
                                if mod_name in sys.modules:
                                    reloaded_mod = importlib.reload(sys.modules[mod_name])
                                else:
                                    reloaded_mod = importlib.import_module(mod_name)
                                patched_list = patch_organ_instances(jarvis, reloaded_mod)
                                patch_info = f"\nPatched Organs: [green]{', '.join(patched_list)}[/green]" if patched_list else ""
                                console.print(Panel(f"[bold yellow]FILE CHANGE DETECTED[/bold yellow]\n\nFile: [white]{rel_path}[/white]\nModule: [cyan]{mod_name}[/cyan]\nApplied: [dim]{timestamp_str}[/dim]{patch_info}\n[bold green]Status: Live-Patched into RAM[/bold green]", title="HOT-RELOAD SUCCESSFUL", border_style="green"))
                                if web_event_broadcaster and callable(web_event_broadcaster):
                                    web_event_broadcaster({"type": "system_toast", "level": "success", "title": "Module Live Patched", "message": f"Updated {mod_name} instantly!", "timestamp": timestamp_str})
                            except Exception:
                                console.print(f"[dim red]Hot-reload failed for {rel_path}: {traceback.format_exc()}[/dim red]")
            except Exception:
                time.sleep(1.0)
    threading.Thread(target=_watch_loop, daemon=True).start()


def main():
    global _global_jarvis_instance, _cli_monitor
    print_banner()
    console.print(Panel.fit(
        "[bold yellow]Select Runtime Execution Target:[/bold yellow]\n\n"
        "  [bold cyan][1][/bold cyan] [bold white]CLI Diagnostic Mode[/bold white] (Pure Local Terminal, No Server)\n"
        "  [bold cyan][2][/bold cyan] [bold white]Web PWA Container Mode[/bold white] (FastAPI :8000 + NEW Vite :5173)\n"
        "  [bold cyan][3][/bold cyan] [bold white]Development Mode[/bold white] (FastAPI :8000 + Vite :5173 + Hot Reload)\n",
        title="[bold magenta]CONTROL INTERFACE SELECTION[/bold magenta]",
        border_style="cyan",
    ))
    choice = console.input("[bold yellow]Option Selection (1, 2, or 3): [/bold yellow]").strip()
    if choice not in {"1", "2", "3"}:
        choice = "1"

    console.print("\n[bold yellow]Initializing JARVIS Subsystems...[/bold yellow]")
    jarvis = start_jarvis(heartbeat_interval=2.0, idle_threshold=10.0)
    _global_jarvis_instance = jarvis

    brain = jarvis.get_organ("brain") if hasattr(jarvis, "get_organ") else None
    if brain:
        console.print("[cyan]Connecting shared offline LLM bridge to Core Brain + Perception...[/cyan]")
        try:
            bridge = _connect_llm_to_brain(brain)
            # Do NOT eagerly force-load the local GGUF model here. On
            # constrained devices (phone/Termux) this was loading a
            # multi-GB model into RAM on every startup, even for
            # sessions that only ever hit native routes (greetings,
            # status, skills). HybridLLMBridge._get_local() already
            # lazy-loads the model on its own the first time it's
            # actually needed (Groq unavailable + a route needs LLM).
            # Set JARVIS_PRELOAD_OFFLINE=1 to restore the old eager
            # behaviour (e.g. if you want the loading delay up front
            # instead of on first LLM-needing turn).
            provider_count = len(getattr(getattr(brain, "perception", None), "providers", []) or [])
            if os.getenv("JARVIS_PRELOAD_OFFLINE") == "1":
                console.print("[cyan]Loading offline model into RAM (this can take a minute)...[/cyan]")
                if bridge.verify_offline_ready():
                    console.print(f"[bold green]Neural Bridge Online -- offline model loaded and verified. Perception providers={provider_count}.[/bold green]\n")
                else:
                    console.print(f"[bold red]Neural Bridge NOT ready -- model failed to load: {bridge.last_error}[/bold red]\n")
            else:
                console.print(f"[bold green]Neural Bridge attached -- offline model loads on first LLM-needing turn. Perception providers={provider_count}.[/bold green]\n")
        except Exception as exc:
            console.print(f"[bold red]Neural Bridge Connection Failure: {exc}[/bold red]\n")

    start_silent_heartbeat_sync(jarvis)

    _cli_monitor = OrganismCLIMonitor(jarvis, console, interval=0.75)
    try:
        _cli_monitor.start()
    except Exception as exc:
        # This legacy Terminal-B view is a nice-to-have, not load-
        # bearing: the new state bus (core/runtime/state_bus.py) is
        # already publishing automatically via bootstrap.py the moment
        # start_jarvis() ran above, regardless of whether this starts.
        console.print(f"[dim yellow]Legacy Terminal-B monitor unavailable ({exc}); continuing without it.[/dim yellow]")

    console.print(
        "[dim cyan]Live internal-state view:[/dim cyan] run [bold]python3 monitor.py[/bold] in another "
        "Termux/tmux/SSH session to watch JARVIS's PERCEIVING/INDEXING/EXECUTING pipeline, recent "
        "schema extractions, and the background learning queue in real time.\n"
        "[dim]Every reply shows an organized workflow panel (Perception/Indexing/Routing/Execution/Learning). "
        "/verbose adds the full raw per-layer contract trace on top.[/dim]"
    )

    if choice == "3":
        console.print("[bold yellow]Development Mode Active: Hot-Reload Watcher Enabled.[/bold yellow]")
        start_live_module_watcher(jarvis)
    else:
        console.print("[dim white]Static Mode Active: Live File Watcher disabled.[/dim white]")

    if choice in {"2", "3"}:
        # Same real issue as the frontend port, just never covered for
        # the backend: start_web_server_thread() binds uvicorn to :8000
        # with no prior check. If the previous CLI session ended
        # without a clean shutdown (Ctrl+C during a hang, terminal
        # closed, phone killed the app), that old process keeps
        # holding :8000 forever -- the exact reason UK had to manually
        # `pkill -f python` before every single restart. Reuses the
        # SAME by-port (not by-remembered-PID) cleanup already proven
        # correct for the frontend above.
        backend_port = os.environ.get("JARVIS_BACKEND_PORT", "8000")
        backend_host = os.environ.get("JARVIS_BACKEND_HOST", "127.0.0.1")
        _kill_stale_frontend_on_port(backend_host, backend_port)
        console.print("[bold green]Starting FastAPI backend on :8000...[/bold green]")
        threading.Thread(target=start_web_server_thread, args=(jarvis,), daemon=True).start()
        start_frontend_server()
        # Was hardcoded to always print :5173 regardless of
        # JARVIS_FRONTEND_PORT/JARVIS_FRONTEND_HOST -- wrong the moment
        # either is customized, or when _kill_stale_frontend_on_port
        # couldn't free the default port and the person needs to set a
        # different one.
        _reported_port = os.environ.get("JARVIS_FRONTEND_PORT", "5173")
        _reported_host = os.environ.get("JARVIS_FRONTEND_HOST", "127.0.0.1")
        console.print(f"[bold cyan]Web stack active:[/bold cyan] legacy http://127.0.0.1:8000 | new http://{_reported_host}:{_reported_port}\n")

    EXIT_COMMANDS = {"exit", "quit", "shutdown", "stop", "q"}
    try:
        while True:
            try:
                user_input = console.input("[bold cyan]UK > [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Termination signal received.[/bold red]")
                break
            if not user_input:
                continue
            lower = user_input.lower()
            if lower in EXIT_COMMANDS:
                console.print("\n[bold yellow]Terminated by operator. Shutting down system...[/bold yellow]")
                break
            if handle_cli_command(jarvis, user_input):
                continue
            if lower == "status":
                render_organ_matrix(jarvis)
                continue
            if lower == "memory":
                render_memory_inspection(jarvis)
                continue
            execute_cognitive_query(jarvis, user_input, source="cli")
    except KeyboardInterrupt:
        console.print("\n[bold red]Execution interrupted by user.[/bold red]")
    finally:
        if _cli_monitor is not None:
            _cli_monitor.stop()
            _cli_monitor = None
        stop_frontend_server()
        stop_jarvis(jarvis)
        console.print("[dim text-gray]SYSTEM STATE: OFFLINE[/dim text-gray]")


if __name__ == "__main__":
    main()
