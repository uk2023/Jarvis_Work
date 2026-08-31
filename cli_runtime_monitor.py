# -*- coding: utf-8 -*-
"""Input-safe live JARVIS organism monitor for the CLI.

Rich Live must not redraw the same terminal while ``console.input`` owns the
cursor. That caused the dashboard to duplicate/corrupt the prompt. This
monitor therefore owns only the organism snapshot thread and installs a
prompt_toolkit-backed input surface whose bottom toolbar is refreshed from the
same live snapshot. Queries are still executed by cli.py and inspected once by
deep_inspector.py.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class OrganismCLIMonitor:
    """Background organism monitor with terminal-safe live input."""

    def __init__(self, jarvis: Any, console: Any, interval: float = 0.75) -> None:
        self.jarvis = jarvis
        self.console = console
        self.interval = max(0.25, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._snapshot: tuple = ()
        self._original_console_input = None
        self._prompt_session = None

    @staticmethod
    def _dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def snapshot(self) -> tuple:
        with self._lock:
            return self._snapshot

    def _collect_snapshot(self) -> tuple:
        j = self.jarvis
        state_obj = getattr(j, "state", None)
        if isinstance(state_obj, dict):
            state = state_obj
        else:
            state = self._dict(getattr(state_obj, "__dict__", None))

        try:
            organs = j.get_organ_status() if hasattr(j, "get_organ_status") else {}
            organs = organs or {}
        except Exception:
            organs = {}

        organ_rows = []
        for name, info in organs.items():
            info = self._dict(info)
            organ_rows.append((str(name), bool(info.get("attached", False)), str(info.get("type", "Subsystem"))))

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
        lifecycle = state.get("lifecycle", state.get("status", "ACTIVE"))
        runtime = state.get("runtime_state", "ONLINE")

        return (
            tuple(organ_rows),
            bool(hb.get("running", False)),
            hb.get("beat_count", 0),
            bool(hb.get("is_idle", True)),
            bool(queue.get("alive", False)),
            queue.get("pending", 0),
            queue.get("processed", 0),
            queue.get("failed", 0),
            llm_ready,
            str(lifecycle),
            str(runtime),
            str(last_event),
            last_activity,
        )

    def _set_snapshot(self, snap: tuple) -> None:
        with self._lock:
            self._snapshot = snap

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self._set_snapshot(self._collect_snapshot())
            except Exception:
                pass

    def _status_lines(self, snap: Optional[tuple] = None) -> list[str]:
        snap = snap or self.snapshot()
        if not snap:
            snap = self._collect_snapshot()
            self._set_snapshot(snap)

        (
            organs,
            hb_running,
            beats,
            idle,
            queue_alive,
            pending,
            processed,
            failed,
            llm_ready,
            lifecycle,
            runtime,
            last_event,
            last_activity,
        ) = snap

        lines = [
            "╭──────────────────── JARVIS ORGANISM LIVE STATUS ────────────────────╮",
            f"│ Runtime          : {runtime:<18}  Lifecycle : {lifecycle:<18} │",
            f"│ Heartbeat        : {'ALIVE' if hb_running else 'STOPPED':<18}  beats={str(beats):<8} │",
            f"│ Event activity   : {str(last_event)[:22]:<22}  Mode={'IDLE' if idle else 'PROCESSING':<11} │",
            f"│ Learning queue   : {'ACTIVE' if queue_alive else 'INACTIVE':<10} pending={pending:<4} processed={processed:<4} │",
            f"│ LLM bridge       : {'READY' if llm_ready else 'UNVERIFIED':<18}                         │",
            "│ ORGANISM ORGANS                                                       │",
        ]
        for name, attached, kind in organs:
            marker = "● ONLINE" if attached else "● OFFLINE"
            lines.append(f"│ {name:<24} {marker:<12} {kind[:27]:<27} │")
        lines.append("│                                                                       │")
        lines.append(f"│ Last activity: {str(last_activity)[:30]:<30} • live refresh={self.interval:.2f}s │")
        lines.append("╰───────────────────────────────────────────────────────────────────────╯")
        return lines

    def render_dashboard(self) -> None:
        """Print one clean dashboard before the interactive prompt starts."""
        text = "\n".join(self._status_lines())
        self.console.print(text, markup=False)

    def _toolbar(self):
        """Multiline prompt-toolkit toolbar; it refreshes without touching input."""
        return "\n".join(self._status_lines())

    def _install_input_bridge(self) -> None:
        if self._original_console_input is not None:
            return
        try:
            from prompt_toolkit import PromptSession
        except Exception:
            # prompt_toolkit is optional; leave the normal Rich input intact.
            return

        self._original_console_input = self.console.input
        self._prompt_session = PromptSession(
            refresh_interval=self.interval,
            bottom_toolbar=self._toolbar,
        )

        def safe_input(prompt="", *args, **kwargs):
            # Rich markup in the prompt is not needed by prompt_toolkit.
            plain_prompt = str(prompt)
            try:
                return self._prompt_session.prompt(plain_prompt)
            except TypeError:
                return self._prompt_session.prompt(plain_prompt)

        self.console.input = safe_input

    def _restore_input_bridge(self) -> None:
        if self._original_console_input is not None:
            try:
                self.console.input = self._original_console_input
            except Exception:
                pass
            self._original_console_input = None
            self._prompt_session = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._set_snapshot(self._collect_snapshot())
        self.render_dashboard()
        self._install_input_bridge()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-cli-organism-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._restore_input_bridge()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
