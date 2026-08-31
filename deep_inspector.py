# -*- coding: utf-8 -*-
"""JARVIS deep inspection surface.

The CLI uses ``render_query_trace`` after Brain.think_and_respond(). It only
renders the exact ``last_turn_trace`` produced by that Brain turn: no second
retrieval, no second LLM call, and no fabricated telemetry.
"""
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
    return value if isinstance(value, (list, tuple)) else []


def _short(value, limit=900):
    text = str(value)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _dump_mapping(parent, label, value, limit=1400):
    node = parent.add(label)
    if isinstance(value, dict):
        if not value:
            node.add("{}")
        for key, item in value.items():
            node.add(f"{key}: {_short(item, limit)}")
    else:
        node.add(_short(value, limit))
    return node


def render_query_trace(brain, trace=None, *, source="cli", query=None, response=None):
    """Render the exact active Brain turn and all exposed retrieval telemetry."""
    trace = _d(trace) or _d(getattr(brain, "last_turn_trace", None))
    context = _d(trace.get("memory_context"))
    memory_counts = _d(trace.get("memory"))

    tree = Tree(
        f"[bold cyan]JARVIS DEEP INSPECTOR[/bold cyan] "
        f"[dim](source={source} | trace={trace.get('timestamp', 'unknown')})[/dim]"
    )

    raw = tree.add("[bold blue]EXACT COGNITIVE QUERY TRACE[/bold blue]")
    raw.add(f"query: {_short(query if query is not None else trace.get('query', ''))}")
    raw.add(f"source: {_short(trace.get('source', source))}")
    raw.add(f"pipeline_success: {trace.get('pipeline_success', False)}")
    raw.add(f"response_preview: {_short(response if response is not None else trace.get('response_preview', ''), 1400)}")

    perception = _d(getattr(brain, "last_perception", None))
    if perception:
        _dump_mapping(tree, "[bold cyan]PERCEPTION RESULT[/bold cyan]", perception)

    retrieval = tree.add("[bold blue]RAW RETRIEVAL — EXACT SINGLE build_context() RESULT[/bold blue]")
    retrieval.add(f"context keys: {list(context.keys())}")

    recent = _items(context.get("recent_experiences"))
    knowledge = _items(context.get("relevant_knowledge"))
    relations = _items(context.get("graph_relations"))
    vectors = _items(trace.get("vector_matches"))
    graph_edges = _items(trace.get("graph_edges"))

    retrieval.add(f"recent_experiences: {len(recent)} | reported={memory_counts.get('recent_experiences', 0)}")
    for i, item in enumerate(recent, 1):
        retrieval.add(f"MEMORY[{i}]: {_short(item)}")

    retrieval.add(f"relevant_knowledge: {len(knowledge)} | reported={memory_counts.get('relevant_knowledge', 0)}")
    for i, item in enumerate(knowledge, 1):
        retrieval.add(f"KNOWLEDGE[{i}]: {_short(item)}")

    retrieval.add(f"graph_relations: {len(relations)} | reported={memory_counts.get('graph_relations', 0)}")
    for i, item in enumerate(relations, 1):
        retrieval.add(f"GRAPH_RELATION[{i}]: {_short(item)}")

    retrieval.add(f"vector_matches: {len(vectors)}")
    for i, item in enumerate(vectors, 1):
        retrieval.add(f"VECTOR[{i}]: {_short(item)}")

    retrieval.add(f"graph_edges: {len(graph_edges)}")
    for i, item in enumerate(graph_edges, 1):
        retrieval.add(f"GRAPH_EDGE[{i}]: {_short(item)}")

    trace_context = tree.add("[bold white]RAW TRACE PAYLOAD[/bold white]")
    for key in ("memory", "vector_matches", "graph_edges", "typos_corrected", "memory_signal", "learning_queue"):
        if key in trace:
            _dump_mapping(trace_context, key, trace[key])

    router = _d(getattr(brain, "last_cognitive_decision", None))
    if router:
        _dump_mapping(tree, "[bold magenta]COGNITIVE ROUTER[/bold magenta]", router)

    decision = _d(getattr(brain, "last_brain_decision", None))
    if decision:
        _dump_mapping(tree, "[bold magenta]BRAIN DECISION[/bold magenta]", decision)

    action = _d(getattr(brain, "last_action_response", None))
    action_node = tree.add("[bold green]ACTION / RESPONSE[/bold green]")
    if action:
        for key, value in action.items():
            action_node.add(f"{key}: {_short(value)}")
    else:
        action_node.add(f"response: {_short(response if response is not None else trace.get('response_preview', ''), 1400)}")

    learning = tree.add("[bold yellow]EXPERIENCE / LEARNING / KNOWLEDGE[/bold yellow]")
    learning.add(f"memory_signal: {_short(trace.get('memory_signal'))}")
    learning.add(f"learning_queue: {_short(trace.get('learning_queue'))}")
    learning.add(f"typos_corrected: {_short(trace.get('typos_corrected', []))}")
    learning.add(f"self_evaluation: {_short(trace.get('self_evaluation'))}")
    learning.add(f"evolution: {_short(trace.get('evolution'))}")

    timings = _d(trace.get("timings"))
    metrics = tree.add("[bold white]REAL TURN METRICS[/bold white]")
    for key, value in timings.items():
        metrics.add(f"{key}: {value}")
    metrics.add(f"total_turns: {_short(getattr(brain, 'total_turns', 'unknown'))}")
    metrics.add(f"total_latency_seconds: {_short(getattr(brain, 'total_latency_seconds', 'unknown'))}")
    metrics.add(f"total_tokens_estimate: {_short(getattr(brain, 'total_tokens_estimate', 'unknown'))}")

    console.print(Panel(tree, title="[bold white]DEEP INSPECTION[/bold white]", border_style="cyan"))


def search_sqlite_knowledge(query_text, db_path="database/knowledge_graph.db"):
    """Direct SQLite audit helper retained for standalone inspector use."""
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
    """Standalone legacy inspector; cli.py remains the primary runtime surface."""
    console.print(Panel.fit(
        "[bold cyan]JARVIS LIVE CONTINUOUS PIPELINE INSPECTOR[/bold cyan]\n"
        "[dim]Standalone audit mode. The normal CLI uses the single Brain turn instead.[/dim]",
        border_style="cyan"
    ))
    console.print("\n[dim]Initializing Micro-Organism Environment...[/dim]")
    try:
        jarvis = start_jarvis(heartbeat_interval=2.0, idle_threshold=10.0)
    except Exception as e:
        console.print(f"[bold red]Failed to boot Jarvis organism: {e}[/bold red]")
        return

    brain = jarvis.get_organ("brain")
    if not brain:
        console.print("[bold red]Critical Fault: 'brain' organ missing.[/bold red]")
        stop_jarvis(jarvis)
        return

    if hasattr(brain, "_learning_queue") and brain._learning_queue:
        try:
            brain._learning_queue.start()
        except Exception:
            pass

    if not getattr(brain, "llm", None):
        try:
            brain.llm = LlamaCppBridge(
                model_filename="qwen2.5-3b-instruct-q4_k_m.gguf",
                n_threads=4,
                n_ctx=4096
            )
        except Exception:
            pass

    console.print("[bold green]Inspector Ready. Type your query below (Type 'exit' to quit).[/bold green]\n")
    try:
        while True:
            try:
                user_query = console.input("[bold cyan]UK (Inspect) > [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_query:
                continue
            if user_query.lower() in ["exit", "quit", "q"]:
                break

            try:
                reply = brain.think_and_respond(
                    user_query,
                    identity_profile={
                        "name": "JARVIS",
                        "creator": "UK",
                        "nature": "Modular Cognitive Organism",
                        "instruction": "Respond accurately in Hinglish directly as JARVIS. User is UK, your creator."
                    },
                    source="deep_inspector",
                )
                render_query_trace(brain, getattr(brain, "last_turn_trace", None), source="deep_inspector", query=user_query, response=reply)
                console.print(Panel(f"[white]{reply}[/white]", title="[bold green]JARVIS Response[/bold green]", border_style="green"))
            except Exception as exc:
                console.print(Panel(f"[bold red]{exc}[/bold red]", title="Inspector Error", border_style="red"))
    finally:
        stop_jarvis(jarvis)
        console.print("[dim]Inspector closed cleanly.[/dim]")


if __name__ == "__main__":
    run_inspector()
