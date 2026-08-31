# -*- coding: utf-8 -*-
"""Detailed CLI inspection helpers for the JARVIS organism.

This module is intentionally read-only. It does not run cognition, mutate
memory, or perform a second build_context() retrieval. It consumes the real
runtime trace exposed by Brain and renders the data that the CLI should show.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


def _d(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _short(value: Any, limit: int = 500) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _items(value: Any) -> list:
    return value if isinstance(value, list) else []


def _add_rows(branch: Tree, title: str, rows: Iterable[Any], fields: tuple[str, ...]) -> None:
    rows = list(rows)
    branch.add(f"{title}: {len(rows)}")
    for index, row in enumerate(rows, 1):
        if isinstance(row, dict):
            values = " | ".join(f"{field}={_short(row.get(field))}" for field in fields)
        else:
            values = _short(row)
        branch.add(f"[{index}] {values}")


def render_detailed_inspection(
    brain: Any,
    trace: Optional[Dict[str, Any]] = None,
    *,
    source: str = "cli",
    query: Optional[str] = None,
    response: Optional[str] = None,
) -> None:
    """Render every real data object available for the completed turn.

    The preferred source is ``brain.last_turn_trace``. Newer Brain versions
    may additionally expose ``memory_context`` inside that trace. The
    function never claims data exists when only a count is available.
    """
    trace = _d(trace) or _d(getattr(brain, "last_turn_trace", None))
    perception = _d(getattr(brain, "last_perception", None))
    route = _d(getattr(brain, "last_cognitive_decision", None))
    decision = _d(getattr(brain, "last_brain_decision", None))
    action = _d(getattr(brain, "last_action_response", None))
    memory = _d(trace.get("memory"))
    context = _d(trace.get("memory_context"))

    tree = Tree(
        f"[bold cyan]FULL JARVIS DATA INSPECTOR[/bold cyan] "
        f"[dim](source={source} | trace={trace.get('timestamp', 'unknown')})[/dim]"
    )

    s1 = tree.add("[bold yellow]01 EVENT / INPUT[/bold yellow]")
    s1.add(f"source={source}")
    s1.add(f"query={_short(query if query is not None else trace.get('query', ''))}")

    s2 = tree.add("[bold cyan]02 PERCEPTION[/bold cyan]")
    if perception:
        for key in ("user_input", "normalized_text", "intent", "entities", "goal", "requested_capability", "speech_act", "language", "confidence", "uncertainty", "source", "reason"):
            if key in perception:
                s2.add(f"{key}: {_short(perception[key])}")
    else:
        s2.add("NOT EXPOSED")

    s3 = tree.add("[bold blue]03 MEMORY / CONTEXT — RAW RETRIEVED DATA[/bold blue]")
    s3.add(f"recent_experiences count={memory.get('recent_experiences', 0)}")
    s3.add(f"semantic knowledge count={memory.get('relevant_knowledge', 0)}")
    s3.add(f"graph relations count={memory.get('graph_relations', 0)}")

    recent = _items(context.get("recent_experiences"))
    knowledge = _items(context.get("relevant_knowledge"))
    relations = _items(context.get("graph_relations"))

    if recent:
        _add_rows(s3, "Recent episodic memories", recent, ("episode_id", "event_type", "context", "action", "outcome"))
    elif memory.get("recent_experiences", 0):
        s3.add("Recent memory objects were retrieved but raw objects were not retained in the trace.")

    if knowledge:
        _add_rows(s3, "Semantic knowledge injected", knowledge, ("knowledge_id", "subject", "predicate", "value", "confidence", "importance", "source"))
    elif memory.get("relevant_knowledge", 0):
        s3.add("Semantic knowledge count is non-zero, but raw objects were not retained in the trace.")

    if relations:
        _add_rows(s3, "Knowledge graph relations", relations, ("subject", "predicate", "target", "source", "relation", "value"))
    elif memory.get("graph_relations", 0):
        s3.add("Graph relation count is non-zero, but raw relations were not retained in the trace.")

    vectors = _items(trace.get("vector_matches"))
    if vectors:
        _add_rows(s3, "Vector-ranked matches", vectors, ("id", "subject", "predicate", "value", "similarity"))
    else:
        s3.add("Vector match objects: none exposed")

    s4 = tree.add("[bold magenta]04 COGNITIVE ROUTER[/bold magenta]")
    if route:
        for key, value in route.items():
            s4.add(f"{key}: {_short(value)}")
    else:
        s4.add("NOT EXPOSED")

    s5 = tree.add("[bold white]05 BRAIN DECISION[/bold white]")
    if decision:
        for key, value in decision.items():
            s5.add(f"{key}: {_short(value)}")
    else:
        s5.add("NOT EXPOSED")

    s6 = tree.add("[bold green]06 ACTION / RESPONSE[/bold green]")
    if action:
        for key, value in action.items():
            s6.add(f"{key}: {_short(value, 1000)}")
    elif response is not None:
        s6.add(f"response: {_short(response, 1000)}")
    else:
        s6.add("NOT EXPOSED")

    s7 = tree.add("[bold green]07 EXPERIENCE / EVALUATION HANDOFF[/bold green]")
    signal = trace.get("memory_signal")
    s7.add(f"memory_signal: {_short(signal) if signal else 'none'}")
    s7.add(f"pipeline_success: {trace.get('pipeline_success', False)}")

    s8 = tree.add("[bold yellow]08 LEARNING / KNOWLEDGE COMMIT[/bold yellow]")
    queue = _d(trace.get("learning_queue"))
    if queue:
        for key, value in queue.items():
            s8.add(f"queue.{key}: {_short(value)}")
    candidate = signal if isinstance(signal, dict) else None
    if candidate:
        s8.add(f"candidate subject: {_short(candidate.get('subject'))}")
        s8.add(f"candidate predicate: {_short(candidate.get('predicate'))}")
        s8.add(f"candidate value: {_short(candidate.get('value'))}")
    else:
        s8.add("No candidate fact returned by the LLM for this turn.")

    s9 = tree.add("[bold yellow]09 SELF-EVALUATION[/bold yellow]")
    self_eval = trace.get("self_evaluation")
    s9.add(_short(self_eval) if self_eval is not None else "NOT EXPOSED")

    s10 = tree.add("[bold yellow]10 EVOLUTION[/bold yellow]")
    evolution = trace.get("evolution")
    s10.add(_short(evolution) if evolution is not None else "NOT EXPOSED")

    timings = _d(trace.get("timings"))
    metrics = tree.add("[bold white]RUNTIME METRICS[/bold white]")
    for key, value in timings.items():
        metrics.add(f"{key}: {value}")
    metrics.add(f"timestamp: {trace.get('timestamp', 'unknown')}")

    console.print(Panel(tree, title="[bold white]JARVIS DEEP INSPECTION[/bold white]", border_style="cyan"))


def render_knowledge_table(rows: Iterable[Any], title: str = "SEMANTIC KNOWLEDGE") -> None:
    """Optional compact table for raw subject-predicate-value records."""
    table = Table(title=title, border_style="blue", header_style="bold cyan")
    table.add_column("Subject")
    table.add_column("Predicate")
    table.add_column("Value")
    table.add_column("Confidence")
    table.add_column("Source")
    for row in rows:
        if not isinstance(row, dict):
            continue
        table.add_row(
            _short(row.get("subject")),
            _short(row.get("predicate")),
            _short(row.get("value")),
            _short(row.get("confidence")),
            _short(row.get("source")),
        )
    console.print(table)
