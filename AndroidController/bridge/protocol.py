"""Transport-neutral action/event protocol placeholder."""

PROTOCOL_VERSION = "0.1"


def make_event(event_type: str, payload: dict) -> dict:
    return {
        "protocol": PROTOCOL_VERSION,
        "type": event_type,
        "payload": payload,
    }
