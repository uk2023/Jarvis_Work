# -*- coding: utf-8 -*-
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
_global_jarvis_instance = None  # Global reference for dynamic engine resolver

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

    console.print(Panel(tree, border_style="dim", title="[bold white]Diagnostics[/bold white]", subtitle="[dim]Trace ID: TRC-LIVE[/dim]"))


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
    jarvis = start_jarvis(
        heartbeat_interval=2.0,
        idle_threshold=10.0,
    )
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
