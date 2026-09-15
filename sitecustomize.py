"""Cloud-runtime startup defaults for JARVIS.

Only affects the CLI runtime-selection prompt. It leaves the existing
cli.py implementation and all other Python processes untouched.
"""
import os
import sys

if os.path.basename(sys.argv[0]) == "cli.py":
    try:
        from rich.console import Console
        _original_input = Console.input

        def _jarvis_cloud_default_input(self, prompt="", *args, **kwargs):
            if "Option Selection (1, 2, or 3)" in str(prompt):
                return "3"
            return _original_input(self, prompt, *args, **kwargs)

        Console.input = _jarvis_cloud_default_input
    except Exception:
        pass
