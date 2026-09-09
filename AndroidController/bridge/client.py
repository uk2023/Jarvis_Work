"""Bridge client placeholder."""


class AndroidClient:
    def connect(self) -> None:
        raise NotImplementedError

    def send_action(self, action: dict) -> dict:
        raise NotImplementedError
