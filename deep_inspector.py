# -*- coding: utf-8 -*-
import os
import sys
import time
import sqlite3
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.organism.bootstrap import start_jarvis, stop_jarvis
from core.orchestration.llm_bridge import LlamaCppBridge

console = Console()


def _d(value):
    return value if isinstance(value, dict) else {}


def _items(value):
    return value if isinstance(value, list) else []


def _short(value, limit=900):
    text = str(value)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def render_query_trace(brain, trace=None, *, source="cli", query=None, response=None):
    """Render the exact trace/context produced by the active Brain turn.

    This is read-only. It never builds a second context, invokes the LLM, or
    performs a second retrieval. The active CLI Brain remains the sole source
    of truth for this query.
    """
    trace = _d(trace) or _d(getattr(brain, "last_turn_trace", None))
    context = _d(trace.get("memory_context"))
    memory = _d(trace.get("memory"))

    tree = Tree(
        f"[bold cyan]JARVIS DEEP INSPECTOR[/bold cyan] "
        f"[dim](source={source} | trace={trace.get('timestamp', 'unknown')})[/dim]"
    )

    raw = tree.add("[bold blue]EXACT COGNITIVE QUERY TRACE[/bold blue]")
    raw.add(f"query: {_short(query if query is not None else trace.get('query', ''))}")
    raw.add(f"pipeline_success: {trace.get('pipeline_success', False)}")

    perception = _d(getattr(brain, "last_perception", None))
    if perception:
        p = tree.add("[bold cyan]PERCEPTION RESULT[/bold cyan]")
        for key in ("normalized_text", "intent", "entities", "goal", "requested_capability", "speech_act", "language", "confidence", "uncertainty", "source", "reason"):
            if key in perception:
                p.add(f"{key}: {_short(perception[key])}")

    retrieval = tree.add("[bold blue]RAW MEMORY / KNOWLEDGE / GRAPH — SINGLE build_context() RESULT[/bold blue]")
    recent = _items(context.get("recent_experiences"))
    knowledge = _items(context.get("relevant_knowledge"))
    relations = _items(context.get("graph_relations"))
    vectors = _items(trace.get("vector_matches"))

    retrieval.add(f"recent_experiences: {len(recent)} | reported={memory.get('recent_experiences', 0)}")
    for i, item in enumerate(recent, 1):
        retrieval.add(f"MEMORY[{i}]: {_short(item)}")

    retrieval.add(f"relevant_knowledge: {len(knowledge)} | reported={memory.get('relevant_knowledge', 0)}")
    for i, item in enumerate(knowledge, 1):
        retrieval.add(f"KNOWLEDGE[{i}]: {_short(item)}")

    retrieval.add(f"graph_relations: {len(relations)} | reported={memory.get('graph_relations', 0)}")
    for i, item in enumerate(relations, 1):
        retrieval.add(f"GRAPH[{i}]: {_short(item)}")

    retrieval.add(f"vector_matches: {len(vectors)}")
    for i, item in enumerate(vectors, 1):
        retrieval.add(f"VECTOR[{i}]: {_short(item)}")

    router = _d(getattr(brain, "last_cognitive_decision", None))
    if router:
        r = tree.add("[bold magenta]COGNITIVE ROUTER[/bold magenta]")
        for key, value in router.items():
            r.add(f"{key}: {_short(value)}")

    decision = _d(getattr(brain, "last_brain_decision", None))
    if decision:
        d = tree.add("[bold magenta]BRAIN DECISION[/bold magenta]")
        for key, value in decision.items():
            d.add(f"{key}: {_short(value)}")

    action = _d(getattr(brain, "last_action_response", None))
    a = tree.add("[bold green]ACTION / RESPONSE[/bold green]")
    if action:
        for key, value in action.items():
            a.add(f"{key}: {_short(value)}")
    else:
        a.add(f"response: {_short(response if response is not None else trace.get('response_preview', ''), 1200)}")

    learning = tree.add("[bold yellow]LEARNING / KNOWLEDGE SIGNAL[/bold yellow]")
    learning.add(f"memory_signal: {_short(trace.get('memory_signal'))}")
    learning.add(f"learning_queue: {_short(trace.get('learning_queue'))}")
    learning.add(f"typos_corrected: {_short(trace.get('typos_corrected', []))}")
    learning.add(f"self_evaluation: {_short(trace.get('self_evaluation'))}")
    learning.add(f"evolution: {_short(trace.get('evolution'))}")

    timings = _d(trace.get("timings"))
    metrics = tree.add("[bold white]REAL TURN METRICS[/bold white]")
    for key, value in timings.items():
        metrics.add(f"{key}: {value}")

    console.print(Panel(tree, title="[bold white]DEEP INSPECTION[/bold white]", border_style="cyan"))


def search_sqlite_knowledge(query_text, db_path="database/knowledge_graph.db"):
    """Directly queries SQLite to audit matching Subject-Predicate-Object facts."""
    if not os.path.exists(db_path):
        db_path = "database/jarvis.db"
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        keywords = [kw for kw in query_text.split() if len(kw) > 2]
        if not keywords:
            conn.close()
            return []
        query_conditions = " OR ".join(["subject LIKE ? OR predicate LIKE ? OR value LIKE ?" for _ in keywords])
        params = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        cursor.execute(f"SELECT subject, predicate, value FROM knowledge WHERE {query_conditions} LIMIT 5;", params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_latest_knowledge_rows(db_path="database/knowledge_graph.db", limit=2):
    if not os.path.exists(db_path):
        db_path = "database/jarvis.db"
    if not os.path.exists(db_path):
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        target_table = "knowledge" if "knowledge" in tables else (tables[0] if tables else None)
        if not target_table:
            conn.close()
            return []
        cursor.execute(f"SELECT subject, predicate, value, created_at FROM {target_table} ORDER BY rowid DESC LIMIT ?;", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def run_inspector():
    console.print(Panel.fit(
        "[bold cyan]JARVIS LIVE CONTINUOUS PIPELINE INSPECTOR[/bold cyan]\n"
        "[dim]Active queue tracking, SQLite keyword retrieval, and commit audit enabled.[/dim]",
        border_style="cyan"
    ))

    console.print("\n[dim]⚡ Initializing Micro-Organism Environment...[/dim]")
    try:
        jarvis = start_jarvis(heartbeat_interval=2.0, idle_threshold=10.0)
    except Exception as e:
        console.print(f"[bold red]❌ Failed to boot Jarvis organism: {e}[/bold red]")
        return

    brain = jarvis.get_organ("brain")
    if not brain:
        console.print("[bold red]❌ Critical Fault: 'brain' organ missing.[/bold red]")
        stop_jarvis(jarvis)
        return

    if hasattr(brain, "_learning_queue") and brain._learning_queue:
        try:
            brain._learning_queue.start()
            console.print("[green]✔ Async Learning Queue Daemon Started Successfully.[/green]")
        except Exception as q_err:
            console.print(f"[yellow]⚠ Queue Start Warning: {q_err}[/yellow]")

    if not getattr(brain, "llm", None):
        try:
            brain.llm = LlamaCppBridge(
                model_filename="qwen2.5-3b-instruct-q4_k_m.gguf",
                n_threads=4,
                n_ctx=4096
            )
        except Exception as llm_err:
            console.print(f"[yellow]⚠ LLM Bridge Warning: {llm_err}[/yellow]")

    console.print("[bold green]✔ Inspector Ready. Type your query below (Type 'exit' to quit).[/bold green]\n")

    try:
        while True:
            try:
                user_query = console.input("[bold cyan]UK (Inspect) > [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Interrupted by user.[/bold red]")
                break
            if not user_query:
                continue
            if user_query.lower() in ["exit", "quit", "q"]:
                console.print("[bold yellow]Closing inspector session...[/bold yellow]")
                break

            db_before = get_latest_knowledge_rows(limit=2)
            tree = Tree(f"[bold magenta]🔬 TRACE MAP: '{user_query}'[/bold magenta]")
            try:
                jarvis.receive_event("USER_INPUT", {"text": user_query}, source="deep_inspector")
                s1 = tree.add("[bold yellow]Stage 1: Event Ingestion (EventBus)[/bold yellow]")
                s1.add("Status: [green]SUCCESS[/green] | Event published.")
            except Exception as e:
                tree.add(f"[bold red]Stage 1 Error:[/bold red] {e}")

            t_mem = time.time()
            context = {}
            try:
                if hasattr(brain, "build_context"):
                    context = brain.build_context(query=user_query, recent_limit=3)
                recent_frames = context.get("recent_experiences", [])
                sql_matches = search_sqlite_knowledge(user_query)
                graph_relations = context.get("graph_relations", [])
                s2 = tree.add(f"[bold blue]Stage 2: Semantic Memory & Knowledge Retrieval[/bold blue] [dim]({(time.time()-t_mem)*1000:.2f} ms)[/dim]")
                s2.add(f"FAISS Vector Frames Retrieved: [cyan]{len(recent_frames)}[/cyan]")
                s2.add(f"SQLite Knowledge Facts Retrieved: [cyan]{len(sql_matches)}[/cyan]")
                for sf in sql_matches:
                    s2.add(f"  └─ Match ➔ [yellow]Subject:[/yellow] {sf[0]} | [cyan]Predicate:[/cyan] {sf[1]} | [green]Value:[/green] {sf[2]}")
                s2.add(f"NetworkX Graph Relations: [cyan]{len(graph_relations)}[/cyan]")
            except Exception as e:
                tree.add(f"[bold red]Stage 2 Error:[/bold red] {e}")

            t_llm = time.time()
            reply = ""
            try:
                identity_profile = {
                    "name": "JARVIS",
                    "creator": "UK",
                    "nature": "Modular Cognitive Organism",
                    "instruction": "Respond accurately in Hinglish directly as JARVIS. User is UK, your creator."
                }
                s3 = tree.add("[bold cyan]Stage 3: LLM Synthesis & Neural Inference[/bold cyan]")
                reply = brain.think_and_respond(user_query, identity_profile=identity_profile, source="deep_inspector")
                llm_dur = time.time() - t_llm
                s3.add(f"Inference Latency: [green]{llm_dur:.3f} s[/green]")
            except Exception as e:
                reply = f"[Error: {e}]"
                tree.add(f"[bold red]Stage 3 Error:[/bold red] {e}")

            try:
                s4 = tree.add("[bold green]Stage 4: Asynchronous Learning Queue & Background Worker[/bold green]")
                queue_stats = {}
                if hasattr(brain, "status"):
                    try:
                        queue_stats = brain.status().get("async_learning_queue", {})
                    except Exception:
                        pass
                q_alive = queue_stats.get("alive", False)
                s4.add(f"Background Daemon Thread State: [bold cyan]{'ACTIVE' if q_alive else 'INACTIVE'}[/bold cyan]")
                s4.add(f"Queue Telemetry ➔ Pending: [yellow]{queue_stats.get('pending', 0)}[/yellow] | Processed: [green]{queue_stats.get('processed', 0)}[/green] | Failed: [red]{queue_stats.get('failed', 0)}[/red]")
            except Exception as e:
                tree.add(f"[bold red]Stage 4 Error:[/bold red] {e}")

            time.sleep(0.8)
            db_after = get_latest_knowledge_rows(limit=2)
            s5 = tree.add("[bold magenta]Stage 5: SQLite Database Commit Audit[/bold magenta]")
            if db_after != db_before:
                s5.add("[bold green]✔ NEW TRIPLES COMMITTED TO DATABASE DETECTED![/bold green]")
                for row in db_after:
                    s5.add(f"  └─ [yellow]Subject:[/yellow] {row[0]} | [cyan]Predicate:[/cyan] {row[1]} | [green]Value:[/green] {row[2]}")
            else:
                s5.add("[dim]No new SPO triples committed in this turn.[/dim]")

            console.print("\n")
            console.print(Panel(tree, title="[bold white]Live Execution Trace Breakdown[/bold white]", border_style="cyan"))
            console.print(Panel(f"[white]{reply}[/white]", title="[bold green]JARVIS Response[/bold green]", border_style="green"))
            console.print("\n" + "─" * 65 + "\n")

    finally:
        stop_jarvis(jarvis)
        console.print("[dim]Inspector closed cleanly.[/dim]")


if __name__ == "__main__":
    run_inspector()
