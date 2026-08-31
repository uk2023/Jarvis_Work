# -*- coding: utf-8 -*-
"""JARVIS terminal/runtime control interface.

The CLI is intentionally a diagnostic surface, not a second cognition engine.
It reads the organism's real runtime state and trace objects and renders the
same lifecycle that the web runtime consumes:

USER INPUT -> PERCEPTION -> MEMORY/CONTEXT -> COGNITIVE ROUTER ->
BRAIN DECISION -> ACTION/RESPONSE -> EXPERIENCE/EVALUATION ->
LEARNING/KNOWLEDGE -> SELF-EVALUATION -> EVOLUTION.

No stage is allowed to manufacture success data. If the current runtime does
not expose a stage-level result yet, the CLI marks it as NOT EXPOSED rather
than inventing telemetry.
"""

import os
import sys
import time
import warnings
import threading
import traceback
import importlib
import hashlib
import subprocess
import urllib.request
from typing import Any, Dict, Optional

# --- System & Environment Setup ---
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
from cli_inspector import render_detailed_inspection

console = Console()

# --- Global State & Threading Synchronization ---
web_event_broadcaster = None
model_lock = threading.Lock()
_global_jarvis_instance = None
_frontend_process = None


def print_banner():
    console.print(
        Panel.fit(
            "[bold cyan]JARVIS COGNITIVE OS[/bold cyan] [dim]v2026.1[/dim]\n"
            "[dim white]Real-time Organism Runtime & Cognitive Lifecycle Diagnostics[/dim white]",
            border_style="cyan",
            subtitle="[dim]UK ARCHITECTURE WORKSPACE[/dim]",
        )
    )


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
    """Render the complete observable lifecycle for the last turn.

    Perception/router data are read from LLMOptionalBrain's dedicated runtime
    fields because BaseBrain's final trace is allowed to contain only its own
    response/learning telemetry. This keeps the CLI truthful while still
    showing the entire architecture from input to evolution boundary.
    """
    trace = _safe_dict(trace)
    perception = _safe_dict(getattr(brain, "last_perception", None))
    route = _safe_dict(getattr(brain, "last_cognitive_decision", None))
    brain_decision = _safe_dict(getattr(brain, "last_brain_decision", None))
    action_response = _safe_dict(getattr(brain, "last_action_response", None))

    if not trace and not perception and not route and not brain_decision:
        console.print(Panel("[dim]No cognitive trace data available for this turn.[/dim]", border_style="dim"))
        return

    timings = _safe_dict(trace.get("timings"))
    total_time = float(timings.get("total", 0.0) or 0.0)
    mem_time = float(timings.get("memory", 0.0) or 0.0)
    llm_time = float(timings.get("llm", 0.0) or 0.0)

    tree = Tree(
        f"[bold cyan]COGNITIVE EXECUTION TRACE[/bold cyan] [dim](Source: {source.upper()} | Total: {total_time:.3f}s)[/dim]"
    )

    query = trace.get("query") or perception.get("user_input") or ""
    _stage(tree, "01", "USER INPUT / EVENT INGESTION", "[bold green]RECEIVED[/bold green]", f"source={source} | text={query}")

    pbranch = tree.add("[bold]02[/bold] [bold white]PERCEPTION[/bold white]  " + _status_text(bool(perception), "COMPLETED", "NOT EXPOSED"))
    if perception:
        pbranch.add(f"normalized_text: [white]{_fmt(perception.get('normalized_text', ''))}[/white]")
        pbranch.add(f"intent: [cyan]{_fmt(perception.get('intent', {}))}[/cyan]")
        pbranch.add(f"entities: [cyan]{_fmt(perception.get('entities', {}))}[/cyan]")
        pbranch.add(f"goal: [cyan]{_fmt(perception.get('goal'))}[/cyan]")
        pbranch.add(f"requested_capability: [cyan]{_fmt(perception.get('requested_capability'))}[/cyan]")
        pbranch.add(f"speech_act: [cyan]{_fmt(perception.get('speech_act'))}[/cyan]")
        pbranch.add(f"language: [cyan]{_fmt(perception.get('language'))}[/cyan]")
        pbranch.add(f"confidence={perception.get('confidence', 0.0)} | uncertainty={perception.get('uncertainty', 1.0)} | provider={perception.get('source', 'unknown')}")
        pbranch.add(f"reason: [dim]{_fmt(perception.get('reason', ''))}[/dim]")
    else:
        pbranch.add("[yellow]Perception result was not retained on the current Brain instance.[/yellow]")

    mem = _safe_dict(trace.get("memory"))
    mem_branch = tree.add(
        f"[bold]03[/bold] [bold white]MEMORY / CONTEXT[/bold white]  [bold green]COMPLETED[/bold green] [dim]({mem_time:.3f}s)[/dim]"
    )
    mem_branch.add(f"recent experiences retrieved: {mem.get('recent_experiences', 0)}")
    mem_branch.add(f"semantic knowledge retrieved: {mem.get('relevant_knowledge', 0)}")
    mem_branch.add(f"knowledge graph relations: {mem.get('graph_relations', 0)}")
    vector_matches = trace.get("vector_matches", [])
    if vector_matches:
        top = vector_matches[0]
        mem_branch.add(
            f"top retrieved fact: {top.get('subject')} -> {top.get('predicate')} -> {top.get('value')} | rank #1"
        )
    else:
        mem_branch.add("vector matches: none exposed for this turn")
    graph_edges = trace.get("graph_edges", [])
    if graph_edges:
        mem_branch.add(f"graph edges exposed: {len(graph_edges)}")

    rbranch = tree.add("[bold]04[/bold] [bold white]COGNITIVE ROUTER[/bold white]  " + _status_text(bool(route), "DECIDED", "NOT EXPOSED"))
    if route:
        rbranch.add(f"mode: [bold cyan]{route.get('mode', 'unknown')}[/bold cyan]")
        if route.get("reason") is not None:
            rbranch.add(f"reason: {_fmt(route.get('reason'))}")
        if route.get("confidence") is not None:
            rbranch.add(f"confidence={route.get('confidence')} | uncertainty={route.get('uncertainty', 1.0 - float(route.get('confidence', 0.0) or 0.0))}")
        if route.get("alternatives") is not None:
            rbranch.add(f"alternatives: {_fmt(route.get('alternatives'))}")
    else:
        rbranch.add("[yellow]Router decision was not retained on the current Brain instance.[/yellow]")

    bbranch = tree.add("[bold]05[/bold] [bold white]BRAIN DECISION[/bold white]  " + _status_text(bool(brain_decision), "RECORDED", "NOT EXPOSED"))
    if brain_decision:
        for key in ("mode", "status", "skill", "native_skill", "error"):
            if key in brain_decision:
                bbranch.add(f"{key}: {_fmt(brain_decision[key])}")
    else:
        bbranch.add("[yellow]No explicit Brain decision record exposed.[/yellow]")

    abranch = tree.add("[bold]06[/bold] [bold white]ACTION / RESPONSE[/bold white]  " + _status_text(bool(action_response), "COMPLETED", "NOT EXPOSED"))
    if action_response:
        abranch.add(f"mode: {action_response.get('mode', 'unknown')} | status: {action_response.get('status', 'unknown')}")
        if action_response.get("action") is not None:
            abranch.add(f"action: {_fmt(action_response.get('action'))}")
        if action_response.get("error") is not None:
            abranch.add(f"error: [red]{_fmt(action_response.get('error'))}[/red]")
        abranch.add(f"response: [white]{_fmt(action_response.get('response', ''), 500)}[/white]")
    else:
        abranch.add(f"response preview: [white]{_fmt(trace.get('response_preview', ''), 500)}[/white]")

    memory_signal = trace.get("memory_signal")
    ebranch = tree.add("[bold]07[/bold] [bold white]EXPERIENCE / EVALUATION[/bold white]  " + _status_text(bool(trace), "HANDOFF OBSERVED", "NOT EXPOSED"))
    if trace:
        ebranch.add("completed interaction was handed to Brain learning boundary")
        ebranch.add(f"memory signal: {_fmt(memory_signal) if memory_signal else 'none detected'}")
    else:
        ebranch.add("No turn trace available.")

    lbranch = tree.add("[bold]08[/bold] [bold white]LEARNING / KNOWLEDGE[/bold white]  " + _status_text(bool(trace.get("pipeline_success")), "QUEUED/PROCESSED", "NOT CONFIRMED"))
    queue = _safe_dict(trace.get("learning_queue"))
    if queue:
        lbranch.add(
            f"async queue: alive={queue.get('alive', '?')} | pending={queue.get('pending', '?')} | processed={queue.get('processed', '?')} | failed={queue.get('failed', '?')} | dropped={queue.get('dropped', '?')}"
        )
    if memory_signal:
        lbranch.add(f"candidate memory signal: {_fmt(memory_signal)}")
    elif trace:
        lbranch.add("no candidate fact detected this turn")
    lbranch.add("persistence acceptance is owned by KnowledgeBuilder/SemanticMemory, not the CLI")

    sebranch = tree.add("[bold]09[/bold] [bold white]SELF-EVALUATION[/bold white]  [bold yellow]NOT EXPOSED[/bold yellow]")
    sebranch.add("No per-turn self-evaluation result is currently published into last_turn_trace.")

    evbranch = tree.add("[bold]10[/bold] [bold white]EVOLUTION[/bold white]  [bold yellow]NOT EXPOSED[/bold yellow]")
    evbranch.add("Evolution organ may be running, but this turn has no explicit evolution result in the trace.")

    diag = tree.add("[bold]RUNTIME METRICS[/bold]")
    diag.add(f"LLM inference: {llm_time:.3f}s")
    diag.add(f"Total turn: {total_time:.3f}s")
    diag.add(f"pipeline_success={trace.get('pipeline_success', False)}")
    diag.add(f"trace timestamp={trace.get('timestamp', 'unknown')}")

    typos = trace.get("typos_corrected", [])
    if typos:
        typo_str = ", ".join(f"{t.get('raw')}→{t.get('corrected')}" for t in typos[:12])
        diag.add(f"typo normalization (retrieval only): {typo_str}")

    console.print(
        Panel(
            tree,
            border_style="dim",
            title="[bold white]FULL ORGANISM COGNITIVE TRACE[/bold white]",
            subtitle="[dim]No fabricated stage telemetry[/dim]",
        )
    )


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

    This is important: assigning ``brain.llm`` directly can bypass
    LLMOptionalBrain.set_llm_bridge(), which is responsible for registering
    the shared bridge as the LLM perception provider too.
    """
    bridge = LlamaCppBridge(
        model_filename="qwen2.5-3b-instruct-q4_k_m.gguf",
        n_threads=4,
        n_ctx=4096,
    )
    if hasattr(brain, "set_llm_bridge") and callable(brain.set_llm_bridge):
        brain.set_llm_bridge(bridge)
    else:
        brain.llm = bridge
    return bridge


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

        jarvis.receive_event("USER_INPUT", {"text": user_input}, source=source)
        reply = "[System Error: Core Cognitive Engine Offline]"
        error_stack = None

        if brain:
            console.print(f"\n[bold cyan][{source.upper()} INGESTION][/bold cyan] USER_INPUT received -> entering organism cognitive pipeline...")
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
        render_cognition_trace(brain, trace, source=source)
        render_detailed_inspection(
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

        if web_event_broadcaster and callable(web_event_broadcaster):
            try:
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
        console.print(
            Panel(
                f"[bold red]Web Server Initialization Exception:[/bold red]\n{traceback.format_exc()}",
                border_style="red",
            )
        )


def _http_ready(url, timeout=1.5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def start_frontend_server():
    """Start NEW web_frontend with Vite on :5173, without touching :8000."""
    global _frontend_process
    frontend_dir = os.environ.get("JARVIS_FRONTEND_DIR", os.path.join(BASE_DIR, "web_frontend"))
    if not os.path.isdir(frontend_dir):
        console.print(f"[bold red]New frontend directory not found:[/bold red] {frontend_dir}")
        return None

    port = os.environ.get("JARVIS_FRONTEND_PORT", "5173")
    host = os.environ.get("JARVIS_FRONTEND_HOST", "127.0.0.1")
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
    classes_in_mod = {
        name: obj for name, obj in reloaded_mod.__dict__.items() if isinstance(obj, type)
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
                        console.print(Panel(
                            f"[bold cyan]NEW FILE CREATED[/bold cyan]\n\nFile: [white]{rel_path}[/white]\nDetected: [dim]{timestamp_str}[/dim]",
                            title="WORKSPACE FILE ADDED",
                            border_style="cyan",
                        ))
                    for filepath in changed_files:
                        rel_path = os.path.relpath(filepath, BASE_DIR)
                        if rel_path == "cli.py":
                            console.print(Panel(
                                f"[bold yellow]cli.py edit detected at {timestamp_str}.[/bold yellow]\nRestart the runner to apply cli.py changes.",
                                border_style="yellow",
                            ))
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
                                console.print(Panel(
                                    f"[bold yellow]FILE CHANGE DETECTED[/bold yellow]\n\nFile: [white]{rel_path}[/white]\nModule: [cyan]{mod_name}[/cyan]\nApplied: [dim]{timestamp_str}[/dim]{patch_info}\n[bold green]Status: Live-Patched into RAM[/bold green]",
                                    title="HOT-RELOAD SUCCESSFUL",
                                    border_style="green",
                                ))
                                if web_event_broadcaster and callable(web_event_broadcaster):
                                    web_event_broadcaster({
                                        "type": "system_toast",
                                        "level": "success",
                                        "title": "Module Live Patched",
                                        "message": f"Updated {mod_name} instantly!",
                                        "timestamp": timestamp_str,
                                    })
                            except Exception:
                                console.print(f"[dim red]Hot-reload failed for {rel_path}: {traceback.format_exc()}[/dim red]")
            except Exception:
                time.sleep(1.0)

    threading.Thread(target=_watch_loop, daemon=True).start()


def main():
    global _global_jarvis_instance
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
            console.print("[cyan]Loading offline model into RAM (this can take a minute)...[/cyan]")
            if bridge.verify_offline_ready():
                provider_count = len(getattr(getattr(brain, "perception", None), "providers", []) or [])
                console.print(f"[bold green]Neural Bridge Online -- offline model loaded and verified. Perception providers={provider_count}.[/bold green]\n")
            else:
                console.print(f"[bold red]Neural Bridge NOT ready -- model failed to load: {bridge.last_error}[/bold red]\n")
        except Exception as exc:
            console.print(f"[bold red]Neural Bridge Connection Failure: {exc}[/bold red]\n")

    start_silent_heartbeat_sync(jarvis)

    if choice == "3":
        console.print("[bold yellow]Development Mode Active: Hot-Reload Watcher Enabled.[/bold yellow]")
        start_live_module_watcher(jarvis)
    else:
        console.print("[dim white]Static Mode Active: Live File Watcher disabled.[/dim white]")

    if choice in {"2", "3"}:
        console.print("[bold green]Starting FastAPI backend on :8000...[/bold green]")
        threading.Thread(target=start_web_server_thread, args=(jarvis,), daemon=True).start()
        start_frontend_server()
        console.print("[bold cyan]Web stack active:[/bold cyan] legacy http://127.0.0.1:8000 | new http://127.0.0.1:5173\n")

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
            if lower == "status":
                render_organ_matrix(jarvis)
                continue
            if lower == "memory":
                memory = jarvis.get_organ("memory") if hasattr(jarvis, "get_organ") else None
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
        stop_frontend_server()
        stop_jarvis(jarvis)
        console.print("[dim text-gray]SYSTEM STATE: OFFLINE[/dim text-gray]")


if __name__ == "__main__":
    main()
