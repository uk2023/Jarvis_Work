# -*- coding: utf-8 -*-
"""Dedicated Terminal-B live monitor for the JARVIS CLI.

The interactive CLI (Terminal A) must own stdin and query/deep-inspection output.
The organism monitor therefore runs in a separate terminal process (Terminal B).
The parent CLI publishes one small JSON snapshot file; Terminal B renders that
snapshot with Rich Live in-place. No cursor sharing, repeated dashboard prints,
or prompt-toolkit toolbar hacks are required.

The monitor is started by cli.py for all three runtime choices. It is intentionally
runtime-agnostic: mode 1, 2, and 3 all use the same Terminal-A/Terminal-B split.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class OrganismCLIMonitor:
    """Publish organism state from Terminal A and render it in Terminal B."""

    def __init__(self, jarvis: Any, console: Any, interval: float = 0.75) -> None:
        self.jarvis = jarvis
        self.console = console
        self.interval = max(0.25, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._snapshot: Dict[str, Any] = {}
        self._monitor_process: Optional[subprocess.Popen] = None
        self._state_path = Path(tempfile.gettempdir()) / f"jarvis_organism_monitor_{os.getpid()}.json"

    @staticmethod
    def _dict(value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    def _collect_snapshot(self) -> Dict[str, Any]:
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
            organ_rows.append({
                "name": str(name),
                "online": bool(info.get("attached", False)),
                "type": str(info.get("type", "Subsystem")),
            })

        hb: Dict[str, Any] = {}
        try:
            hb = self._dict(j.heartbeat.status()) if getattr(j, "heartbeat", None) else {}
        except Exception:
            pass

        brain = None
        try:
            brain = j.get_organ("brain") if hasattr(j, "get_organ") else None
        except Exception:
            pass

        queue: Dict[str, Any] = {}
        if brain is not None and hasattr(brain, "status"):
            try:
                queue = self._dict(brain.status().get("async_learning_queue", {}))
            except Exception:
                pass

        llm = getattr(brain, "llm", None) if brain is not None else None
        llm_ready = bool(getattr(llm, "is_ready", False)) if llm else False

        lifecycle = state.get("lifecycle", state.get("status", "ACTIVE"))
        runtime = state.get("runtime_state", "ONLINE")
        last_event = state.get("last_event") or state.get("last_event_type") or "—"
        last_activity = state.get("last_activity_at") or state.get("last_activity") or "—"

        return {
            "version": 1,
            "pid": os.getpid(),
            "updated_at": time.time(),
            "runtime": str(runtime),
            "lifecycle": str(lifecycle),
            "heartbeat": {
                "running": bool(hb.get("running", False)),
                "beats": hb.get("beat_count", 0),
                "idle": bool(hb.get("is_idle", True)),
            },
            "event": str(last_event),
            "last_activity": last_activity,
            "learning": {
                "alive": bool(queue.get("alive", False)),
                "pending": queue.get("pending", 0),
                "processed": queue.get("processed", 0),
                "failed": queue.get("failed", 0),
            },
            "llm_ready": llm_ready,
            "organs": organ_rows,
            "shutdown": False,
        }

    def _set_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self._snapshot = dict(snapshot)

    def _publish(self, snapshot: Dict[str, Any]) -> None:
        """Atomically publish one complete snapshot so Terminal B never sees partial JSON."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".jarvis_monitor_{os.getpid()}_",
            suffix=".tmp",
            dir=str(self._state_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, self._state_path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                snapshot = self._collect_snapshot()
                self._set_snapshot(snapshot)
                self._publish(snapshot)
            except Exception:
                # Monitoring must never interfere with cognition/query execution.
                pass

    @staticmethod
    def _terminal_candidates() -> list[tuple[str, list[str]]]:
        python = sys.executable
        monitor = os.path.abspath(__file__)
        return [
            ("JARVIS_MONITOR_TERMINAL", []),
            ("x-terminal-emulator", ["-e", python, monitor, "--monitor-state"]),
            ("gnome-terminal", ["--", python, monitor, "--monitor-state"]),
            ("konsole", ["-e", python, monitor, "--monitor-state"]),
            ("xfce4-terminal", ["--command", f"{python} {monitor} --monitor-state"]),
            ("xterm", ["-e", python, monitor, "--monitor-state"]),
        ]

    def _spawn_terminal_b(self) -> Optional[subprocess.Popen]:
        # Allow an explicit executable through JARVIS_MONITOR_TERMINAL.
        explicit = os.environ.get("JARVIS_MONITOR_TERMINAL")
        candidates = self._terminal_candidates()
        if explicit:
            candidates = [(explicit, [python_arg for python_arg in [])] for _ in [0]]
            # For an explicit terminal executable, use its normal "-e" contract.
            candidates[0] = (explicit, ["-e", sys.executable, os.path.abspath(__file__), "--monitor-state"])

        for executable, args in candidates:
            if executable == "JARVIS_MONITOR_TERMINAL":
                continue
            path = shutil.which(executable)
            if not path:
                continue
            command = [path, *args, str(self._state_path)] if "--monitor-state" in args and str(self._state_path) not in args else [path, *args]
            try:
                return subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
            except Exception:
                continue
        return None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        snapshot = self._collect_snapshot()
        self._set_snapshot(snapshot)
        self._publish(snapshot)
        self._monitor_process = self._spawn_terminal_b()
        if self._monitor_process is None:
            # Do not hijack Terminal A. Make the failure visible once, without
            # starting a competing live renderer in the query terminal.
            self.console.print(
                "[bold yellow]Terminal-B monitor could not be opened automatically.[/bold yellow] "
                "Set JARVIS_MONITOR_TERMINAL to a terminal emulator executable."
            )
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-cli-organism-state-publisher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            final = self._collect_snapshot()
            final["runtime"] = "OFFLINE"
            final["lifecycle"] = "STOPPING"
            final["shutdown"] = True
            self._set_snapshot(final)
            self._publish(final)
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        proc = self._monitor_process
        self._monitor_process = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        try:
            self._state_path.unlink(missing_ok=True)
        except Exception:
            pass


def _load_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (FileNotFoundError, PermissionError, json.JSONDecodeError, OSError):
        return None


def _monitor_render(snapshot: Optional[Dict[str, Any]], interval: float) -> Group:
    if not snapshot:
        return Group(
            Panel(
                "Waiting for the JARVIS runtime state publisher...",
                title="JARVIS ORGANISM MONITOR",
                border_style="yellow",
            )
        )

    heartbeat = snapshot.get("heartbeat") or {}
    learning = snapshot.get("learning") or {}
    organs = snapshot.get("organs") or []

    summary = Table.grid(expand=True, padding=(0, 1))
    summary.add_column(justify="left")
    summary.add_column(justify="left")
    summary.add_row(f"Runtime        : {snapshot.get('runtime', 'UNKNOWN')}", f"Lifecycle      : {snapshot.get('lifecycle', 'UNKNOWN')}")
    summary.add_row(
        f"Heartbeat      : {'ALIVE' if heartbeat.get('running') else 'STOPPED'} • beats={heartbeat.get('beats', 0)}",
        f"Mode           : {'IDLE' if heartbeat.get('idle', True) else 'ACTIVE PROCESSING'}",
    )
    summary.add_row(
        f"Event activity : {str(snapshot.get('event', '—'))[:45]}",
        f"Learning queue : {'ACTIVE' if learning.get('alive') else 'INACTIVE'} • pending={learning.get('pending', 0)} • processed={learning.get('processed', 0)}",
    )
    summary.add_row(
        f"LLM bridge     : {'READY' if snapshot.get('llm_ready') else 'UNVERIFIED'}",
        f"Last activity  : {str(snapshot.get('last_activity', '—'))[:32]}",
    )

    organs_table = Table(title="ORGANISM ORGANS", expand=True, show_lines=False)
    organs_table.add_column("Organ", style="bold white")
    organs_table.add_column("State", justify="center")
    organs_table.add_column("Type", style="dim")
    for organ in organs:
        online = bool(organ.get("online"))
        organs_table.add_row(
            str(organ.get("name", "unknown")),
            "[green]● ONLINE[/green]" if online else "[red]● OFFLINE[/red]",
            str(organ.get("type", "Subsystem")),
        )

    footer = f"Terminal B • live state bus • refresh={interval:.2f}s • source PID={snapshot.get('pid', '?')}"
    return Group(
        Panel(summary, title="JARVIS ORGANISM LIVE STATUS", border_style="cyan"),
        organs_table,
        Panel(footer, border_style="dim"),
    )


def run_monitor_terminal(state_path: str, interval: float = 0.75) -> int:
    """Run the dedicated Terminal-B renderer."""
    path = Path(state_path)
    console = Console()
    with Live(
        _monitor_render(None, interval),
        console=console,
        refresh_per_second=max(1, int(round(1.0 / interval))),
        screen=True,
        transient=False,
    ) as live:
        while True:
            snapshot = _load_snapshot(path)
            live.update(_monitor_render(snapshot, interval), refresh=True)
            if snapshot and snapshot.get("shutdown"):
                time.sleep(0.35)
                return 0
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS Terminal-B live organism monitor")
    parser.add_argument("--monitor-state", metavar="PATH", help="Run as the dedicated Terminal-B renderer")
    parser.add_argument("--interval", type=float, default=0.75)
    args = parser.parse_args()
    if args.monitor_state:
        return run_monitor_terminal(args.monitor_state, max(0.25, args.interval))
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
