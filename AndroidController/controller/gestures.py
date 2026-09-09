"""Gesture primitives. Real Android dispatch is implemented by the app layer later."""


def dispatch_tap(x: int, y: int) -> None:
    raise NotImplementedError


def dispatch_swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    raise NotImplementedError
