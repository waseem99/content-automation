from __future__ import annotations

from src.application.scripts.service import ScriptReviewService
from src.application.scripts.validated_service import ValidatedScriptReviewService


def install_validated_script_service() -> None:
    """Install the JSON-safe revision copier on the public service class."""
    ScriptReviewService._copy_children = staticmethod(ValidatedScriptReviewService._copy_children)
