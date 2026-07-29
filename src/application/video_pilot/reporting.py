from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def compile_pilot_report(detail: dict[str, Any]) -> dict[str, Any]:
    run = detail["run"]
    cases = detail["cases"]
    attempts = detail["attempts"]
    reviews = detail["reviews"]
    case_by_id = {str(row["id"]): row for row in cases}

    latest_review: dict[str, dict[str, Any]] = {}
    for review in reviews:
        latest_review[str(review["pilot_attempt_id"])] = review

    accepted_by_case: dict[str, dict[str, Any]] = {}
    model_rows: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "attempts": 0,
            "succeeded": 0,
            "failed": 0,
            "accepted_clips": 0,
            "gpu_active_ms": 0,
            "wall_clock_ms": 0,
            "external_cost_usd": Decimal("0"),
        }
    )
    for attempt in attempts:
        policy_id = str(attempt["model_policy_id"])
        bucket = model_rows[policy_id]
        bucket["attempts"] += 1
        bucket["succeeded"] += int(attempt["status"] == "succeeded")
        bucket["failed"] += int(attempt["status"] == "failed")
        bucket["gpu_active_ms"] += int(attempt["gpu_active_ms"] or 0)
        bucket["wall_clock_ms"] += int(attempt["wall_clock_ms"] or 0)
        bucket["external_cost_usd"] += _decimal(attempt["external_cost_usd"])
        review = latest_review.get(str(attempt["id"]))
        if review and review["decision"] == "accepted":
            accepted_by_case[str(attempt["pilot_case_id"])] = attempt
            bucket["accepted_clips"] += 1

    accepted_case_ids = set(accepted_by_case)
    attempts_for_accepted = sum(1 for row in attempts if str(row["pilot_case_id"]) in accepted_case_ids)
    accepted_motion_seconds = sum(
        (_decimal(case_by_id[case_id]["target_duration_seconds"]) for case_id in accepted_case_ids),
        Decimal("0"),
    )
    accepted_reviews = [row for row in reviews if row["decision"] == "accepted"]
    quality = {
        field: (
            sum((_decimal(row[field]) for row in accepted_reviews), Decimal("0")) / Decimal(len(accepted_reviews))
            if accepted_reviews
            else None
        )
        for field in ("motion_quality", "reference_consistency", "artifact_control", "composition_quality")
    }

    terminal_attempts = [row for row in attempts if row["status"] != "running"]
    earliest = min((row["started_at"] for row in attempts), default=None)
    latest = max((row["completed_at"] for row in terminal_attempts if row["completed_at"]), default=None)
    elapsed_hours = Decimal("0")
    if earliest and latest and latest > earliest:
        elapsed_hours = Decimal(str((latest - earliest).total_seconds())) / Decimal("3600")
    measured_clips_per_day = None
    if elapsed_hours > 0 and accepted_case_ids:
        measured_clips_per_day = Decimal(len(accepted_case_ids)) * Decimal("24") / elapsed_hours

    defects: dict[str, int] = defaultdict(int)
    for review in reviews:
        if review["decision"] != "accepted":
            for tag in review["defect_tags"] or ():
                defects[str(tag)] += 1

    target_videos = int(run["target_videos"])
    target_attempts = int(run["target_attempts"])
    acceptance_ready = len(accepted_case_ids) >= target_videos and len(terminal_attempts) >= target_attempts
    source_digest = hashlib.sha256(
        _json({"run": run, "cases": cases, "attempts": attempts, "reviews": reviews}).encode("utf-8")
    ).hexdigest()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_run_id": str(run["id"]),
        "status": run["status"],
        "targets": {"videos": target_videos, "attempts": target_attempts},
        "actuals": {
            "cases": len(cases),
            "completed_cases": len(accepted_case_ids),
            "attempts": len(attempts),
            "completed_attempts": len(terminal_attempts),
            "succeeded_attempts": sum(1 for row in attempts if row["status"] == "succeeded"),
            "failed_attempts": sum(1 for row in attempts if row["status"] == "failed"),
            "accepted_motion_seconds": accepted_motion_seconds,
            "attempts_per_accepted_clip": (
                Decimal(attempts_for_accepted) / Decimal(len(accepted_case_ids)) if accepted_case_ids else None
            ),
            "gpu_hours": Decimal(sum(int(row["gpu_active_ms"] or 0) for row in attempts)) / Decimal("3600000"),
            "wall_clock_hours": Decimal(sum(int(row["wall_clock_ms"] or 0) for row in attempts)) / Decimal("3600000"),
            "external_cost_usd": sum((_decimal(row["external_cost_usd"]) for row in attempts), Decimal("0")),
            "measured_clips_per_24h_elapsed": measured_clips_per_day,
        },
        "quality": quality,
        "defect_counts": dict(sorted(defects.items())),
        "models": {key: value for key, value in sorted(model_rows.items())},
        "acceptance_ready": acceptance_ready,
        "insufficiency_reasons": [
            reason
            for condition, reason in (
                (len(accepted_case_ids) < target_videos, "accepted_video_target_not_met"),
                (len(terminal_attempts) < target_attempts, "attempt_target_not_met"),
            )
            if condition
        ],
        "source_digest": source_digest,
    }
