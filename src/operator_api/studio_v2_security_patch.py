from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from src.operator_api import studio_v2_runtime as _runtime


_VISIBLE_LOCAL_ROLE_IDS = frozenset(
    {
        "local-reviewer",
        "local-producer",
        "local-publisher",
    }
)


def safe_team_keys_payload() -> dict[str, Any]:
    """Load the local role-key file without ever returning an admin credential."""

    if os.getenv("OPS_ENVIRONMENT", "development").strip().lower() == "production":
        raise HTTPException(status_code=403, detail="local_key_reveal_disabled_in_production")

    path = Path(os.getenv("STUDIO_OPERATOR_KEYS_FILE", ".runtime/operator-keys.json")).resolve()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="operator_key_file_not_found")

    try:
        # Windows PowerShell 5.1 writes `-Encoding utf8` files with a UTF-8 BOM.
        # utf-8-sig accepts both BOM and BOM-less files without weakening JSON validation.
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail="operator_key_file_invalid") from exc

    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="operator_key_file_invalid")

    items = [
        {"operator_id": str(operator_id), "key": str(key)}
        for operator_id, key in value.items()
        if str(operator_id) in _VISIBLE_LOCAL_ROLE_IDS and isinstance(key, str) and key
    ]
    items.sort(key=lambda item: item["operator_id"])
    return {
        "ok": True,
        "kind": "studio_v2_team_keys",
        "items": items,
        "admin_keys_exposed": False,
    }


def apply_studio_v2_security_patch() -> None:
    """Install the fail-closed key loader before Studio v2 routes are created."""

    if getattr(_runtime.StudioV2Service, "_p135_security_patch", False):
        return

    def team_keys(self: _runtime.StudioV2Service) -> dict[str, Any]:
        del self
        return safe_team_keys_payload()

    _runtime.StudioV2Service.team_keys = team_keys
    _runtime.StudioV2Service._p135_security_patch = True


__all__ = ["apply_studio_v2_security_patch", "safe_team_keys_payload"]
