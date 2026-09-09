"""Controller action interfaces for Android automation."""


def tap(x: int, y: int) -> None:
    """Tap at screen coordinates. Implementation will be added later."""
    raise NotImplementedError


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    """Swipe between two coordinates. Implementation will be added later."""
    raise NotImplementedError


def long_press(x: int, y: int, duration_ms: int = 800) -> None:
    """Long-press at screen coordinates. Implementation will be added later."""
    raise NotImplementedError


def type_text(text: str) -> None:
    """Type text into the focused Android field. Implementation will be added later."""
    raise NotImplementedError
