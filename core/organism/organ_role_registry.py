from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class OrganRoleRegistry:
    """Read-only metadata registry for the organism's declared organ roles."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (
            Path(__file__).resolve().parents[2] / "config" / "organism_roles.json"
        )
        self._roles: Dict[str, str] = {}
        self.reload()

    def reload(self) -> Dict[str, str]:
        with self.config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        organs = payload.get("organs", {})
        if not isinstance(organs, dict):
            raise ValueError("organism_roles.json must contain an object under 'organs'.")
        self._roles = {str(name): str(role) for name, role in organs.items()}
        return dict(self._roles)

    def role_for(self, name: str) -> Optional[str]:
        return self._roles.get(name)

    def all_roles(self) -> Dict[str, str]:
        return dict(self._roles)
