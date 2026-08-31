# -*- coding: utf-8 -*-
"""Live, read-only JARVIS organism status monitor for the CLI."""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class OrganismCLIMonitor:
    """Background monitor that redraws only when observable runtime state changes."""

    def __init__(self, jarvis: Any, console: Any, interval: float = 0.75) -> None:
        self.jarvis = jarvis
        self.console = console
        self.interval = max(0.25, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._live: Optional[Live] = None
        self._last_snapshot: Optional[tuple] = None
        self._last_render: Any = None

    @staticmethod
    def _dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _snapshot(self) -> tuple:
        j = self.jarvis
        state = self._dict(getattr(j, "state", None))
        try:
            if hasattr(j, "get_organ_status"):
                organs = j.get_organ_status() or {}
            else:
                organs = {}
        except Exception:
            organs = {}

        organ_rows = []
        for name, info in organs.items():
            info = self._dict(info)
            organ_rows.append((name, info.get("attached", False), info.get("type", "Subsystem")))

        hb = {}
        try:
            hb = self._dict(j.heartbeat.status()) if getattr(j, "heartbeat", None) else {}
        except Exception:
            pass

        brain = None
        try:
            brain = j.get_organ("brain") if hasattr(j, "get_organ") else None
        except Exception:
            pass

        queue = {}
        if brain is not None and hasattr(brain, "status"):
            try:
                queue = self._dict(brain.status().get("async_learning_queue", {}))
            except Exception:
                pass

        llm = getattr(brain, "llm", None) if brain is not None else None
        llm_ready = bool(getattr(llm, "is_ready", False)) if llm else False
        last_event = state.get("last_event") or state.get("last_event_type") or "—"
        last_activity = state.get("last_activity_at") or state.get("last_activity")

        return (
            tuple(organ_rows),
            hb.get("running", False),
            hb.get("beat_count", 0),
            hb.get("is_idle", True),
            queue.get("alive", False),
            queue.get("pending", 0),
            queue.get("processed", 0),
            queue.get("failed", 0),
            llm_ready,
            state.get("lifecycle", state.get("status", "ACTIVE")),
            state.get("runtime_state", "ONLINE"),
            last_event,
            last_activity,
        )

    def _render(self, snap: tuple) -> Any:
        organs, hb_running, beats, idle, queue_alive, pending, processed, failed, llm_ready, lifecycle, runtime, last_event, last_activity = snap

        status = Table.grid(expand=True)
        status.add_column(justify="left")
        status.add_column(justify="right")
        status.add_row("Runtime", f"[bold green]{runtime}[/bold green]")
        status.add_row("Lifecycle", f"[bold cyan]{lifecycle}[/bold cyan]")
        status.add_row("Heartbeat", f"[bold green]ALIVE[/bold green] • beats={beats}" if hb_running else "[bold red]STOPPED[/bold red]")
        status.add_row("Event activity", str(last_event))
        status.add_row("Learning queue", f"[green]ACTIVE[/green] • pending={pending} processed={processed} failed={failed}" if queue_alive else "[yellow]INACTIVE[/yellow]")
        status.add_row("LLM bridge", "[green]READY[/green]" if llm_ready else "[yellow]UNVERIFIED[/yellow]")
        status.add_row("Mode", "[yellow]IDLE / MONITORING[/yellow]" if idle else "[cyan]ACTIVE PROCESSING[/cyan]")

        table = Table(title="ORGANISM ORGANS", expand=True, header_style="bold cyan")
        table.add_column("Organ", style="bold white")
        table.add_column("State", justify="center")
        table.add_column("Type", style="dim")
        for name, attached, kind in organs:
            table.add_row(name, "[green]● ONLINE[/green]" if attached else "[red]● OFFLINE[/red]", str(kind))

        footer = f"Last activity: {last_activity if last_activity is not None else '—'}"
        return Panel(Group(status, table, f"[dim]{footer} • refresh-on-change • interval={self.interval:.2f}s[/dim]"), title="[bold cyan]JARVIS ORGANISM LIVE STATUS[/bold cyan]", border_style="cyan")

    def _loop(self) -> None:
        try:
            self._live = Live(self._render(self._snapshot()), console=self.console, refresh_per_second=4, transient=False)
            self._live.start(refresh=True)
            while not self._stop.wait(self.interval):
                snap = self._snapshot()
                if snap != self._last_snapshot:
                    self._last_snapshot = snap
                    self._last_render = self._render(snap)
                    self._live.update(self._last_render, refresh=True)
        finally:
            if self._live is not None:
                try:
                    self._live.stop()
                except Exception:
                    pass
                self._live = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_snapshot = None
        self._thread = threading.Thread(target=self._loop, name="jarvis-cli-organism-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
