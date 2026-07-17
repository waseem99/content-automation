"""P68 six-video pilot scoring and closeout evidence.

This module evaluates real render manifests and human review records against the
P68 benchmark. Missing videos or review evidence keep the epic open.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


P68_BATCH_VERSION = "p68.pilot_batch_closeout.v1"
EXPECTED_BRANDS = {"rawr_nation": 3, "animal_x": 3}
EXPECTED_PILOT_IDS = {
    "rawr-blind-spot",
    "rawr-gecko-grip",
    "rawr-archerfish-aim",
    "animal-elephant-signals",
    "animal-prairie-dog-alarm",
    "animal-octopus-arms",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_benchmark(path: str | Path) -> dict[str, Any]:
    benchmark = json.loads(Path(path).read_text(encoding="utf-8"))
    if benchmark.get("schema_version") != "p68.quality_benchmark.v1":
        raise ValueError("Unsupported P68 quality benchmark")
    return benchmark


def evaluate_spec_batch(pilots_root: str | Path) -> dict[str, Any]:
    """Evaluate planning readiness without implying that media exists.

    This is intentionally separate from ``evaluate_batch``: a complete plan is
    useful for orchestration, but never constitutes production evidence.
    """
    root = Path(pilots_root)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/content-plan.json")):
        plan = json.loads(path.read_text(encoding="utf-8"))
        shots = plan.get("shots") or []
        duration = round(sum(float(shot.get("duration_seconds") or 0) for shot in shots), 3)
        files = {
            name: (path.parent / name).is_file()
            for name in (
                "source-brief.json", "content-plan.json", "script.md", "storyboard.json",
                "clip-prompts.json", "voice-project.json", "captions.srt",
            )
        }
        errors = []
        if not plan.get("validation", {}).get("passed"):
            errors.append("continuity_plan_validation_failed")
        if not 6 <= len(shots) <= 8:
            errors.append("shot_count_must_be_6_to_8")
        if not 25 <= duration <= 38:
            errors.append("duration_must_be_25_to_38_seconds")
        if not all(files.values()):
            errors.append("production_pack_files_missing")
        if any(float(shot.get("transition_handle_seconds") or 0) < 0.5 for shot in shots):
            errors.append("transition_handle_missing")
        rows.append(
            {
                "pilot_id": plan.get("pilot_id"),
                "brand_profile": plan.get("brand_profile"),
                "shot_count": len(shots),
                "duration_seconds": duration,
                "files": files,
                "spec_ready": not errors,
                "preview_ready": False,
                "natural_motion_ready": False,
                "human_review_ready": False,
                "production_candidate": False,
                "errors": sorted(set(errors)),
                "publish_allowed": False,
            }
        )
    ids = {row["pilot_id"] for row in rows}
    counts = {
        brand: sum(row["brand_profile"] == brand for row in rows)
        for brand in EXPECTED_BRANDS
    }
    batch_errors = []
    if ids != EXPECTED_PILOT_IDS:
        batch_errors.append("exact_six_pilot_roster_required")
    for brand, expected in EXPECTED_BRANDS.items():
        if counts[brand] != expected:
            batch_errors.append(f"{brand}:exactly_{expected}_pilots_required")
    all_specs_ready = len(rows) == 6 and all(row["spec_ready"] for row in rows) and not batch_errors
    return {
        "schema_version": "p68.six_pilot_spec_readiness.v1",
        "pilots": rows,
        "brand_counts": counts,
        "batch_errors": sorted(batch_errors),
        "all_specs_ready": all_specs_ready,
        "production_candidate_count": 0,
        "next_gate": "generate_or_source_natural_motion_clips" if all_specs_ready else "repair_specs",
        "paid_provider_calls_made": 0,
        "vercel_deployment_required": False,
        "publish_allowed": False,
    }


def write_spec_readiness(pilots_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    result = evaluate_spec_batch(pilots_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def evaluate_pilot(record: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    output_path = Path(str(record.get("output_path") or ""))
    if not output_path.is_file() or output_path.stat().st_size == 0:
        errors.append("real_video_file_required")
    probe = record.get("probe") or {}
    profile = benchmark["production_profile"]
    duration = float(probe.get("duration_seconds") or 0)
    technical_pass = (
        probe.get("width") == profile["width"]
        and probe.get("height") == profile["height"]
        and abs(float(probe.get("fps") or 0) - profile["fps"]) <= 0.05
        and probe.get("video_codec") == profile["video_codec"]
        and probe.get("audio_codec") == profile["audio_codec"]
        and profile["duration_seconds"]["minimum"] <= duration <= profile["duration_seconds"]["maximum"]
    )
    if not technical_pass:
        errors.append("technical_profile_failed")
    shot_count = int(record.get("shot_count") or 0)
    if not profile["shot_count"]["minimum"] <= shot_count <= profile["shot_count"]["maximum"]:
        errors.append("shot_count_failed")

    dimensions = {item["id"]: item for item in benchmark["dimensions"]}
    review = record.get("human_review") or {}
    scores = review.get("scores") or {}
    notes = review.get("evidence_notes") or {}
    for dimension in dimensions:
        if dimension not in scores:
            errors.append(f"missing_score:{dimension}")
        if not str(notes.get(dimension) or "").strip():
            errors.append(f"missing_evidence_note:{dimension}")
    weighted = round(
        sum(float(scores.get(name) or 0) * item["weight"] for name, item in dimensions.items()) / 100,
        3,
    )
    minimum_dimension = min((float(scores.get(name) or 0) for name in dimensions), default=0)
    hard_gate_pass = all(
        float(scores.get(name) or 0) >= benchmark["acceptance"]["minimum_hard_gate_score"]
        for name, item in dimensions.items()
        if item["hard_gate"]
    )
    evidence_fields = (
        "factual_sources",
        "rights_evidence",
        "originality_evidence",
        "advertiser_suitability_evidence",
        "revision_history",
    )
    for field in evidence_fields:
        if not record.get(field):
            errors.append(f"{field}_required")
    if not str(review.get("reviewer_role") or "").strip():
        errors.append("human_reviewer_role_required")
    if review.get("decision") not in {"reject", "major_revision", "minor_revision", "production_candidate"}:
        errors.append("human_decision_required")
    automated_candidate = (
        technical_pass
        and weighted >= benchmark["acceptance"]["minimum_weighted_score"]
        and minimum_dimension >= benchmark["acceptance"]["minimum_dimension_score"]
        and hard_gate_pass
        and not errors
    )
    accepted = automated_candidate and review.get("decision") == "production_candidate"
    return {
        "pilot_id": record.get("pilot_id"),
        "brand_profile": record.get("brand_profile"),
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path) if output_path.is_file() else None,
        "probe": probe,
        "shot_count": shot_count,
        "weighted_score": weighted,
        "minimum_dimension_score": minimum_dimension,
        "hard_gates_passed": hard_gate_pass,
        "technical_passed": technical_pass,
        "automated_candidate": automated_candidate,
        "human_decision": review.get("decision"),
        "production_candidate": accepted,
        "errors": sorted(set(errors)),
        "publish_allowed": False,
    }


def evaluate_batch(records: list[dict[str, Any]], benchmark: dict[str, Any]) -> dict[str, Any]:
    brand_counts = {
        brand: sum(1 for record in records if record.get("brand_profile") == brand)
        for brand in EXPECTED_BRANDS
    }
    batch_errors = []
    if len(records) != 6:
        batch_errors.append("exactly_six_real_pilots_required")
    for brand, expected in EXPECTED_BRANDS.items():
        if brand_counts[brand] != expected:
            batch_errors.append(f"{brand}:exactly_{expected}_pilots_required")
    ids = [record.get("pilot_id") for record in records]
    if len(set(ids)) != len(ids) or any(not item for item in ids):
        batch_errors.append("six_unique_pilot_ids_required")
    pilots = [evaluate_pilot(record, benchmark) for record in records]
    all_candidates = len(pilots) == 6 and all(item["production_candidate"] for item in pilots)
    status = "quality_accepted_pending_separate_publish_decision" if all_candidates and not batch_errors else "remain_open_for_revision_or_missing_evidence"
    return {
        "schema_version": P68_BATCH_VERSION,
        "pilot_count": len(records),
        "brand_counts": brand_counts,
        "pilots": pilots,
        "batch_errors": sorted(set(batch_errors)),
        "production_candidate_count": sum(1 for item in pilots if item["production_candidate"]),
        "p68_closeout_ready": all_candidates and not batch_errors,
        "readiness_decision": status,
        "historiq_and_ani_films_adaptation_allowed": all_candidates and not batch_errors,
        "publish_allowed": False,
        "human_closeout_review_required": True,
    }


def write_batch_closeout(
    records: list[dict[str, Any]],
    benchmark_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    benchmark = load_benchmark(benchmark_path)
    result = evaluate_batch(records, benchmark)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "p68-pilot-closeout.json"
    report_path = root / "p68-readiness-report.md"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = "\n".join(
        f"| {item['pilot_id']} | {item['brand_profile']} | {item['weighted_score']:.2f} | "
        f"{'yes' if item['technical_passed'] else 'no'} | "
        f"{'yes' if item['production_candidate'] else 'no'} |"
        for item in result["pilots"]
    )
    report_path.write_text(
        "# P68 Pilot Readiness Report\n\n"
        f"Decision: `{result['readiness_decision']}`\n\n"
        "| Pilot | Brand | Score | Technical | Candidate |\n"
        "| --- | --- | ---: | --- | --- |\n"
        f"{rows}\n\n"
        "Publishing remains blocked. Human closeout and a separate publication decision are required.\n",
        encoding="utf-8",
    )
    return {**result, "json_path": str(json_path), "report_path": str(report_path)}
