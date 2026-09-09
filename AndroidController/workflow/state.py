"""Workflow execution state placeholder."""


class WorkflowState:
    def __init__(self):
        self.status = "idle"
        self.step = 0
        self.action = None
        self.error = None
