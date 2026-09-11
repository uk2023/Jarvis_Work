from __future__ import annotations

"""Clean, human-readable chat transcript -- separate from the
internal debug log (logs/jarvis_runtime.log), which is full of
engineering noise (Groq key rotation, warnings, JSON parse errors)
and was never meant to be read as a conversation record. This is
the file UK can hand to anyone (including this Claude conversation)
to show JARVIS's actual behavior turn by turn, without wading
through internal telemetry to find the real exchange.
"""

import os
import time
from typing import Optional

_CHAT_LOG_PATH = os.path.join("logs", "chat_log.txt")


def log_chat_turn(user_input: str, response: str, path: Optional[str] = None) -> None:
    """Append one (user, JARVIS) exchange in plain, readable form.
    Silently no-ops on any I/O failure -- logging a conversation must
    never be able to break the conversation itself."""
    target = path or _CHAT_LOG_PATH
    if not user_input and not response:
        return
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] UK: {user_input}\n")
            handle.write(f"[{timestamp}] JARVIS: {response}\n\n")
    except Exception:
        pass
