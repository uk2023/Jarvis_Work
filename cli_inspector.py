# -*- coding: utf-8 -*-
"""Opt-in raw cognitive retrieval inspector.

The normal CLI turn already renders the lifecycle trace. This module is
strictly a read-only data inspector and is intentionally silent unless the
operator explicitly asks for a deep inspection command.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

console = Console()

_INSPECT_COMMANDS = {"inspect", "deep", "deep inspect", "inspect memory", "debug memory"}


def _d(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list:
    return value if isinstance(value, list) else []


def _short(value: Any, limit: int = 700) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def render_detailed_inspection(
    brain: Any,
    trace: Optional[Dict[str, Any]] = None,
    *,
    source: str = "cli",
    query: Optional[str] = None,
    response: Optional[str] = None,
) -> None:
    """Print raw turn data only for an explicit inspector command.

    No retrieval, LLM call, learning call, or mutation happens here. The
    inspector consumes the exact ``last_turn_trace`` produced by Brain.
    """
    command = (query or "").strip().lower()
    if command not in _INSPECT_COMMANDS:
        return

    trace = _d(trace) or _d(getattr(brain, "last_turn_trace", None))
    context = _d(trace.get("memory_context"))
    memory = _d(trace.get("memory"))

    tree = Tree(
        f"[bold cyan]JARVIS DEEP INSPECTOR[/bold cyan] "
        f"[dim](source={source} | trace={trace.get('timestamp', 'unknown')})[/dim]"
    )

    raw = tree.add("[bold blue]RAW RETRIEVAL — SINGLE build_context() RESULT[/bold blue]")
    recent = _items(context.get("recent_experiences"))
    knowledge = _items(context.get("relevant_knowledge"))
    relations = _items(context.get("graph_relations"))
    vectors = _items(trace.get("vector_matches"))

    raw.add(f"recent_experiences: {len(recent)} | reported={memory.get('recent_experiences', 0)}")
    for i, item in enumerate(recent, 1):
        raw.add(f"MEMORY[{i}]: {_short(item)}")

    raw.add(f"relevant_knowledge: {len(knowledge)} | reported={memory.get('relevant_knowledge', 0)}")
    for i, item in enumerate(knowledge, 1):
        raw.add(f"KNOWLEDGE[{i}]: {_short(item)}")

    raw.add(f"graph_relations: {len(relations)} | reported={memory.get('graph_relations', 0)}")
    for i, item in enumerate(relations, 1):
        raw.add(f"GRAPH[{i}]: {_short(item)}")

    raw.add(f"vector_matches: {len(vectors)}")
    for i, item in enumerate(vectors, 1):
        raw.add(f"VECTOR[{i}]: {_short(item)}")

    signal = trace.get("memory_signal")
    learning = _d(trace.get("learning_queue"))
    pipeline = tree.add("[bold yellow]LEARNING / KNOWLEDGE SIGNAL[/bold yellow]")
    pipeline.add(f"memory_signal: {_short(signal) if signal is not None else 'none'}")
    pipeline.add(f"queue: {_short(learning)}")
    pipeline.add(f"pipeline_success: {trace.get('pipeline_success', False)}")

    state = tree.add("[bold magenta]TURN STATE[/bold magenta]")
    state.add(f"query: {_short(query if query is not None else trace.get('query', ''))}")
    state.add(f"response: {_short(response if response is not None else trace.get('response_preview', ''), 1000)}")
    state.add(f"typos_corrected: {_short(trace.get('typos_corrected', []))}")
    state.add(f"self_evaluation: {_short(trace.get('self_evaluation'))}")
    state.add(f"evolution: {_short(trace.get('evolution'))}")

    timings = _d(trace.get("timings"))
    metrics = tree.add("[bold white]REAL TURN METRICS[/bold white]")
    for key, value in timings.items():
        metrics.add(f"{key}: {value}")

    console.print(Panel(tree, title="[bold white]DEEP INSPECTION[/bold white]", border_style="cyan"))
