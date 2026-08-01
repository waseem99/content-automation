from __future__ import annotations

from typing import Any

from src.application.scripts.models import ScriptGenerateRequest as ValidatedScriptGenerateRequest
from src.application.pre_generation import runtime_patch as pre_generation_runtime
from src.operator_api import p110_runtime, studio_v2_runtime


def _bounded_script_generate_request(*args: Any, **kwargs: Any) -> ValidatedScriptGenerateRequest:
    """Normalize external timeout configuration before strict model validation.

    Both Studio V2 and P110 construct the same validated request, but legacy
    workstation configuration may still contain the former 180-second value.
    Keep the request contract strict and clamp only at this orchestration edge.
    """

    if "local_timeout_seconds" in kwargs and kwargs["local_timeout_seconds"] is not None:
        try:
            configured = int(kwargs["local_timeout_seconds"])
        except (TypeError, ValueError):
            configured = 20
        kwargs["local_timeout_seconds"] = max(1, min(120, configured))
    return ValidatedScriptGenerateRequest(*args, **kwargs)


def _canonical_timeline(
    scenes: list[dict[str, Any]],
    target_seconds: float,
) -> tuple[list[dict[str, Any]], bool, float]:
    """Build the frozen renderer timeline from canonical script-scene columns."""

    ordered = sorted(
        scenes,
        key=lambda row: (int(row.get("sequence") or 0), str(row.get("scene_key") or "")),
    )
    durations = [float(row.get("target_duration_seconds") or 0) for row in ordered]
    total = sum(durations)
    correction = round(target_seconds - total, 3)
    corrected = False
    tolerance = max(2.0, target_seconds * 0.05)
    if ordered and abs(correction) > 0.01 and abs(correction) <= tolerance:
        candidate = durations[-1] + correction
        if candidate >= 1.0:
            durations[-1] = candidate
            total = sum(durations)
            corrected = True

    cursor = 0.0
    timeline: list[dict[str, Any]] = []
    for row, duration in zip(ordered, durations, strict=True):
        start = round(cursor, 3)
        end = round(cursor + duration, 3)
        timeline.append(
            {
                "scene_id": str(row.get("id")),
                "scene_key": str(row.get("scene_key") or ""),
                "position": int(row.get("sequence") or 0),
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": round(duration, 3),
                "narration_text": str(row.get("narration_text") or "").strip(),
                "visual_intent": str(row.get("visual_brief") or "").strip(),
                "on_screen_text": str(row.get("on_screen_text") or "").strip(),
                "metadata": {
                    "source_requirements": list(row.get("source_requirements") or []),
                    "script_section_id": str(row.get("script_section_id") or "") or None,
                },
            }
        )
        cursor = end
    return timeline, corrected, round(target_seconds - total, 3)


def install_final_pre_generation_runtime_patch() -> None:
    if getattr(pre_generation_runtime, "_final_runtime_patch_installed", False):
        return

    # These modules resolve ScriptGenerateRequest through their module globals at
    # call time. Replacing that constructor keeps all validated model semantics
    # while bounding legacy external configuration safely and without mutating
    # process-wide environment variables.
    p110_runtime.ScriptGenerateRequest = _bounded_script_generate_request
    studio_v2_runtime.ScriptGenerateRequest = _bounded_script_generate_request

    # The renderer-ready planning stage installed by runtime_patch resolves the
    # timeline helper from its module global at call time.
    pre_generation_runtime._timeline = _canonical_timeline
    pre_generation_runtime._final_runtime_patch_installed = True


__all__ = ["install_final_pre_generation_runtime_patch"]
