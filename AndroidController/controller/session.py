"""Controller session placeholder."""


class ControllerSession:
    """Owns one Android controller execution session."""

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
