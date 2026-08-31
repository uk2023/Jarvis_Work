from __future__ import annotations

from typing import Any, Callable, Dict, Optional
import time

from core.identity import Identity, Values, Personality


class JarvisCore:
    """
    Central organism coordinator.

    IMPORTANT:
    - This is NOT the LLM.
    - This is NOT the Gatekeeper.
    - This is the persistent coordination layer of JARVIS.
    - Cognitive organs are attached to this core rather than being embedded
      directly into it.

    Current responsibility:
        receive event
        -> maintain organism state
        -> notify organs
        -> expose a stable interface for future evolution

    Later:
        Gatekeeper, Chat, Reasoning, Code, OCR, Memory, Learning,
        Autonomy and Skills will attach to this core.
    """

    VERSION = "0.1.0"

    def __init__(
        self,
        identity=None,
        personality=None,
        values=None,
        state=None,
        event_bus=None,
        lifecycle=None,
        heartbeat=None,
        organs=None,
    ):
        self.identity = identity if identity is not None else Identity()
        self.personality = personality if personality is not None else Personality()
        self.values = values if values is not None else Values()
        self.state = state

        # Canonical runtime name is event_bus. Keep `events` as a compatibility
        # alias for existing organism code that still uses the older name.
        self.event_bus = event_bus
        self.events = event_bus
        self.lifecycle = lifecycle
        self.heartbeat = heartbeat

        self.organs: Dict[str, Any] = dict(organs or {})
        self.started_at = time.time()
        self.last_event = None
        self.running = False

    def attach_organ(self, name: str, organ: Any) -> None:
        if not name:
            raise ValueError("Organ name cannot be empty.")
        self.organs[name] = organ
        self._publish("ORGAN_ATTACHED", {"name": name, "organ_type": type(organ).__name__})

    def detach_organ(self, name: str) -> Optional[Any]:
        organ = self.organs.pop(name, None)
        if organ is not None:
            self._publish("ORGAN_DETACHED", {"name": name, "organ_type": type(organ).__name__})
        return organ

    def get_organ(self, name: str) -> Optional[Any]:
        return self.organs.get(name)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._set_state(mode="ACTIVE", learning_state="IDLE")
        self._publish("JARVIS_STARTED", {"version": self.VERSION, "timestamp": time.time()})

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self._set_state(mode="STOPPED")
        self._publish("JARVIS_STOPPED", {"timestamp": time.time()})

    def receive_event(self, event_name: str, payload: Any = None, source: Optional[str] = None) -> Dict[str, Any]:
        if not event_name:
            raise ValueError("event_name cannot be empty.")
        event = {"name": event_name, "payload": payload, "source": source, "timestamp": time.time()}
        self.last_event = event
        self._set_state(last_event=event)
        self._publish(event_name, event)
        return event

    def _set_state(self, **changes) -> None:
        if self.state is None:
            return
        update_method = getattr(self.state, "update", None)
        if callable(update_method):
            update_method(**changes)
            return
        for key, value in changes.items():
            try:
                setattr(self.state, key, value)
            except Exception:
                pass

    def _publish(self, event_name: str, payload: Any = None) -> None:
        if self.event_bus is None:
            return
        publish_method = getattr(self.event_bus, "emit", None)
        if callable(publish_method):
            try:
                publish_method(event_name, payload)
            except Exception as exc:
                print(f"[JarvisCore EventBus Error] {event_name}: {exc}")

    def get_organ_status(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {"type": type(organ).__name__, "attached": True}
            for name, organ in self.organs.items()
        }

    def snapshot(self) -> Dict[str, Any]:
        state_snapshot = {}
        if self.state is not None:
            snapshot_method = getattr(self.state, "snapshot", None)
            if callable(snapshot_method):
                try:
                    state_snapshot = snapshot_method()
                except Exception as exc:
                    state_snapshot = {"error": str(exc)}

        identity_snapshot = {}
        if self.identity is not None:
            snapshot_method = getattr(self.identity, "snapshot", None)
            if callable(snapshot_method):
                try:
                    identity_snapshot = snapshot_method()
                except Exception:
                    identity_snapshot = {}

        return {
            "version": self.VERSION,
            "running": self.running,
            "started_at": self.started_at,
            "last_event": self.last_event,
            "identity": identity_snapshot,
            "state": state_snapshot,
            "organs": self.get_organ_status(),
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "jarvis": "JARVIS",
            "version": self.VERSION,
            "running": self.running,
            "organs": list(self.organs.keys()),
            "state": (
                self.state.snapshot()
                if self.state and callable(getattr(self.state, "snapshot", None))
                else {}
            ),
        }
