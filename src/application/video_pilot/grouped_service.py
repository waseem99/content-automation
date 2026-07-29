from __future__ import annotations

from src.application.video_pilot.service import VideoPilotService


class GroupedVideoPilotService(VideoPilotService):
    """Compatibility name for the complete-video-aware P113 lifecycle service."""


__all__ = ["GroupedVideoPilotService"]
