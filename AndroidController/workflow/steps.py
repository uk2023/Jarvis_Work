"""Workflow step model placeholder."""


class WorkflowStep:
    def __init__(self, action: str, target: str | None = None):
        self.action = action
        self.target = target
