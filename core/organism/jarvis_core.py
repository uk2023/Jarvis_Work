from __future__ import annotations

from typing import Any, Dict, Optional
import time

from core.identity import Identity, Values, Personality
from .organ_role_registry import OrganRoleRegistry


class JarvisCore:
    """Central organism coordinator and observable organism boundary."""

    VERSION = "0.2.0"

    def __init__(self, identity=None, personality=None, values=None,
                 state=None, event_bus=None, lifecycle=None, heartbeat=None,
                 organs=None, organ_roles=None):
        self.identity = identity if identity is not None else Identity()
        self.personality = personality if personality is not None else Personality()
        self.values = values if values is not None else Values()
        self.state = state

        self.event_bus = event_bus
        self.events = event_bus
        self.lifecycle = lifecycle
        self.heartbeat = heartbeat
        self.organs: Dict[str, Any] = dict(organs or {})
        self.organ_roles = organ_roles if organ_roles is not None else OrganRoleRegistry()
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
        brain = self.organs.get("brain")
        brain_start = getattr(brain, "start", None)
        if callable(brain_start):
            brain_start()
        self._set_state(mode="ACTIVE", learning_state="IDLE")
        self._publish("JARVIS_STARTED", {"version": self.VERSION, "timestamp": time.time()})

    def stop(self) -> None:
        if not self.running:
            return
        brain = self.organs.get("brain")
        brain_stop = getattr(brain, "stop", None)
        if callable(brain_stop):
            try:
                brain_stop()
            except Exception as exc:
                print(f"[JarvisCore Brain Stop Error] {exc}")
        self.running = False
        self._set_state(mode="STOPPED")
        self._publish("JARVIS_STOPPED", {"timestamp": time.time()})

    def receive_event(self, event_name: str, payload: Any = None,
                      source: Optional[str] = None) -> Dict[str, Any]:
        if not event_name:
            raise ValueError("event_name cannot be empty.")
        event = {"name": event_name, "payload": payload, "source": source,
                 "timestamp": time.time()}
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
        bus = self.event_bus
        if bus is None:
            return
        publish_method = getattr(bus, "emit", None)
        if callable(publish_method):
            try:
                publish_method(event_name, payload)
            except Exception as exc:
                print(f"[JarvisCore EventBus Error] {event_name}: {exc}")

    def get_organ_status(self) -> Dict[str, Dict[str, Any]]:
        """Report presence, declared role and optional self-reported runtime state."""
        result: Dict[str, Dict[str, Any]] = {}
        for name, organ in self.organs.items():
            entry: Dict[str, Any] = {
                "type": type(organ).__name__,
                "attached": True,
                "role": self.organ_roles.role_for(name),
            }
            status_method = getattr(organ, "status", None)
            if callable(status_method):
                try:
                    status = status_method()
                    if isinstance(status, dict):
                        entry["status"] = status
                except Exception as exc:
                    entry["status_error"] = str(exc)
            result[name] = entry
        return result

    def get_status(self) -> Dict[str, Any]:
        """Return an evidence-oriented organism snapshot without claiming health."""
        identity = self.identity.snapshot() if self.identity and callable(
            getattr(self.identity, "snapshot", None)
        ) else {}
        return {
            "organism": "JARVIS",
            "version": self.VERSION,
            "running": self.running,
            "uptime_seconds": max(0.0, time.time() - self.started_at),
            "last_event": self.last_event,
            "identity": identity,
            "organs": self.get_organ_status(),
            "state": self.state.snapshot() if self.state and callable(
                getattr(self.state, "snapshot", None)
            ) else {},
        }

    def snapshot(self) -> Dict[str, Any]:
        return self.get_status()

    def describe(self) -> Dict[str, Any]:
        return self.get_status()
