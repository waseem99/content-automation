"""Resumable P68 production orchestrator for review-only short-form pilots.

The built-in motion renderer intentionally creates preview clips from approved
still plates. Provider-generated video clips can replace those files without
changing assembly, evidence, or review behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from src.p68_clip_stitcher import assemble_clip_plan, probe_media, sha256_file
from src.p68_job_state import (
    STAGE_ORDER,
    atomic_write_json,
    fail_stage,
    finish_stage,
    load_or_create,
    reset_from_stage,
    sha256_paths,
    stage_complete,
    start_stage,
)


PIPELINE_VERSION = "p68.production_pipeline.v1"
MOTION_MODES = ("push_in", "drift_left", "drift_right", "pull_back", "settle", "push_in")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fingerprint(stage: str, *values: str) -> str:
    digest = hashlib.sha256(f"{PIPELINE_VERSION}:{stage}".encode())
    for value in values:
        digest.update(value.encode())
    return digest.hexdigest()


def _run(command: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-4000:])
    return result


def validate_inputs(pilot_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    required = [
        pilot_dir / "source-brief.json",
        pilot_dir / "content-plan.json",
        pilot_dir / "captions.srt",
        pilot_dir / "clip-prompts.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing production inputs: {missing}")
    plan = _json(pilot_dir / "content-plan.json")
    if not plan.get("validation", {}).get("passed"):
        raise ValueError("Continuity/originality plan has not passed validation")
    if not 6 <= len(plan.get("shots") or []) <= 8:
        raise ValueError("P68 pilot must contain six to eight planned shots")
    narration = select_narration(artifact_dir)
    return {
        "pilot_id": plan["pilot_id"],
        "brand_profile": plan["brand_profile"],
        "shot_count": len(plan["shots"]),
        "narration_path": str(narration),
        "narration_probe": probe_media(narration),
    }


def select_narration(artifact_dir: Path) -> Path:
    candidates = sorted((artifact_dir / "narration").glob("*.wav"))
    if not candidates:
        raise FileNotFoundError(f"Narration WAV is required under {artifact_dir / 'narration'}")
    versioned = [path for path in candidates if "-v2" in path.stem]
    return versioned[-1] if versioned else candidates[-1]


def prepare_asset_manifest(pilot_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    plan = _json(pilot_dir / "content-plan.json")
    asset_root = artifact_dir / "generated-assets"
    masters = sorted(asset_root.glob("master-*.png"))
    if not masters:
        raise FileNotFoundError(f"A continuity master is required under {asset_root}")
    master = masters[0]
    assets = []
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        variants = sorted(asset_root.glob(f"{shot_id.lower()}-*.png")) + sorted(
            asset_root.glob(f"{shot_id.lower()}.png")
        )
        selected = variants[-1] if variants else master
        assets.append(
            {
                "shot_id": shot_id,
                "path": str(selected),
                "source": "derived_shot_asset" if variants else "continuity_master_preview_fallback",
                "master_path": str(master),
                "sha256": sha256_file(selected),
                "quality_status": "pending_final_review" if variants else "preview_only",
                "rights_status": "generated_for_project",
            }
        )
    manifest = {
        "schema_version": "p68.asset_manifest.v1",
        "pilot_id": plan["pilot_id"],
        "assets": assets,
        "all_shots_have_derived_assets": all(item["source"] == "derived_shot_asset" for item in assets),
        "publish_allowed": False,
    }
    path = artifact_dir / "assets" / "asset-manifest.json"
    atomic_write_json(path, manifest)
    return {**manifest, "manifest_path": str(path)}


def _motion_filter(mode: str, frames: int) -> str:
    # Motions are deliberately restrained and alternate direction by shot.
    if mode == "drift_left":
        x = "(iw-iw/zoom)*(on/%d)" % max(frames - 1, 1)
        y, z = "(ih-ih/zoom)/2", "1.045"
    elif mode == "drift_right":
        x = "(iw-iw/zoom)*(1-on/%d)" % max(frames - 1, 1)
        y, z = "(ih-ih/zoom)/2", "1.045"
    elif mode == "pull_back":
        x, y, z = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2", f"1.065-0.055*on/{max(frames - 1, 1)}"
    elif mode == "settle":
        x, y, z = "(iw-iw/zoom)/2", "(ih-ih/zoom)*(0.42+0.08*on/%d)" % max(frames - 1, 1), "1.025"
    else:
        x, y, z = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2", f"1.01+0.05*on/{max(frames - 1, 1)}"
    return (
        "scale=1296:2304:force_original_aspect_ratio=increase,crop=1296:2304,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s=1080x1920:fps=30,"
        "eq=contrast=1.015:saturation=1.025,noise=alls=1.2:allf=t+u,format=yuv420p"
    )


def render_motion_clips(plan: dict[str, Any], asset_manifest: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for preview motion rendering")
    clips_dir = artifact_dir / "clips" / "preview-v1"
    clips_dir.mkdir(parents=True, exist_ok=True)
    assets = {item["shot_id"]: item for item in asset_manifest["assets"]}
    records = []
    for index, shot in enumerate(plan["shots"]):
        asset = assets[shot["shot_id"]]
        duration = float(shot["duration_seconds"]) + float(shot.get("transition_handle_seconds") or 0.5)
        frames = round(duration * 30)
        output = clips_dir / f"{shot['shot_id']}.mp4"
        fingerprint = _fingerprint("motion-clip", asset["sha256"], str(duration), MOTION_MODES[index % len(MOTION_MODES)])
        sidecar = output.with_suffix(".json")
        cached = sidecar.is_file() and output.is_file() and _json(sidecar).get("fingerprint") == fingerprint
        if not cached:
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    asset["path"],
                    "-vf",
                    _motion_filter(MOTION_MODES[index % len(MOTION_MODES)], frames),
                    "-frames:v",
                    str(frames),
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
            )
            atomic_write_json(sidecar, {"fingerprint": fingerprint, "asset": asset, "mode": MOTION_MODES[index % len(MOTION_MODES)]})
        records.append(
            {
                "shot_id": shot["shot_id"],
                "path": str(output),
                "provider": "p68-editorial-motion-preview-v1",
                "prompt_or_asset_reference": asset["path"],
                "rights_status": asset["rights_status"],
                "human_review_status": "pending_final_review",
                "motion_mode": MOTION_MODES[index % len(MOTION_MODES)],
                "preview_only": asset["quality_status"] == "preview_only",
            }
        )
    manifest = {
        "schema_version": "p68.clip_manifest.v1",
        "pilot_id": plan["pilot_id"],
        "clips": records,
        "production_candidate": not any(item["preview_only"] for item in records),
        "publish_allowed": False,
    }
    path = artifact_dir / "clips" / "clip-manifest.json"
    atomic_write_json(path, manifest)
    return {**manifest, "manifest_path": str(path)}


def automated_quality(render_manifest: dict[str, Any], clip_manifest: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    output = Path(render_manifest["output_path"])
    ffmpeg = shutil.which("ffmpeg")
    detections = ""
    if ffmpeg:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(output), "-vf", "blackdetect=d=0.25:pix_th=0.02,freezedetect=n=-55dB:d=1.5", "-an", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        detections = result.stderr
    black_segments = detections.count("black_start:")
    freeze_segments = detections.count("freeze_start:")
    checks = {
        "technical_profile": bool(render_manifest.get("technical_pass")),
        "no_black_segments": black_segments == 0,
        "no_long_freezes": freeze_segments == 0,
        "all_shots_have_final_assets": not any(item.get("preview_only") for item in clip_manifest["clips"]),
        "human_review_present": False,
    }
    result = {
        "schema_version": "p68.automated_quality.v1",
        "output_path": str(output),
        "output_sha256": sha256_file(output),
        "checks": checks,
        "black_segment_count": black_segments,
        "long_freeze_count": freeze_segments,
        "automated_pass": all(value for name, value in checks.items() if name not in {"human_review_present", "all_shots_have_final_assets"}),
        "production_candidate": all(checks.values()),
        "revision_tasks": [
            message
            for failed, message in (
                (not checks["technical_profile"], "Re-render to the required 1080x1920 H.264/AAC profile."),
                (not checks["no_black_segments"], "Inspect and replace detected black-frame segments."),
                (not checks["no_long_freezes"], "Replace shots containing unintended long visual freezes."),
                (not checks["all_shots_have_final_assets"], "Replace continuity-master preview fallbacks with shot-specific approved assets."),
                (not checks["human_review_present"], "Complete the 12-dimension human benchmark review."),
            )
            if failed
        ],
        "publish_allowed": False,
    }
    path = artifact_dir / "quality" / "automated-quality.json"
    atomic_write_json(path, result)
    return {**result, "quality_path": str(path)}


class ProductionPipeline:
    def __init__(self, pilot_dir: Path, artifact_root: Path):
        self.pilot_dir = pilot_dir
        self.pilot_id = pilot_dir.name
        self.artifact_dir = artifact_root / "gold" / self.pilot_id
        self.state_path = self.artifact_dir / "job-state.json"
        inputs = [pilot_dir / "source-brief.json", pilot_dir / "content-plan.json", pilot_dir / "captions.srt"]
        self.input_digest = sha256_paths(inputs)
        self.state = load_or_create(self.state_path, self.pilot_id, self.input_digest)

    def _stage(self, name: str, fingerprint: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        if stage_complete(self.state, name, fingerprint):
            return self.state["stages"][name]["outputs"]
        start_stage(self.state_path, self.state, name)
        try:
            outputs = action()
            finish_stage(self.state_path, self.state, name, fingerprint, outputs)
            return outputs
        except Exception as error:
            fail_stage(self.state_path, self.state, name, error)
            raise

    def run(self, through: str = "quality") -> dict[str, Any]:
        if through not in STAGE_ORDER:
            raise ValueError(f"Unknown stage: {through}")
        plan_path = self.pilot_dir / "content-plan.json"
        plan = _json(plan_path)
        validation = self._stage(
            "validate",
            _fingerprint("validate", self.input_digest),
            lambda: validate_inputs(self.pilot_dir, self.artifact_dir),
        )
        if through == "validate":
            return validation
        assets = self._stage(
            "assets",
            _fingerprint("assets", self.input_digest, sha256_file(next(iter(sorted((self.artifact_dir / 'generated-assets').glob('master-*.png')))))),
            lambda: prepare_asset_manifest(self.pilot_dir, self.artifact_dir),
        )
        if through == "assets":
            return assets
        motion = self._stage(
            "motion",
            _fingerprint("motion", json.dumps(assets, sort_keys=True)),
            lambda: render_motion_clips(plan, assets, self.artifact_dir),
        )
        if through == "motion":
            return motion
        narration = validation["narration_path"]
        render = self._stage(
            "assemble",
            _fingerprint("assemble", json.dumps(motion, sort_keys=True), sha256_file(Path(narration))),
            lambda: assemble_clip_plan(
                plan,
                motion,
                self.artifact_dir / "renders" / "review-v1",
                narration_path=narration,
                captions_path=self.pilot_dir / "captions.srt",
            ),
        )
        if not render.get("is_valid"):
            raise RuntimeError(f"Assembly failed validation: {render.get('errors')}")
        if through == "assemble":
            return render
        return self._stage(
            "quality",
            _fingerprint("quality", render["output_sha256"]),
            lambda: automated_quality(render, motion, self.artifact_dir),
        )


def discover_pilots(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob("*/content-plan.json"))


def status(root: Path, artifact_root: Path) -> list[dict[str, Any]]:
    rows = []
    for pilot_dir in discover_pilots(root):
        path = artifact_root / "gold" / pilot_dir.name / "job-state.json"
        if path.is_file():
            state = _json(path)
            rows.append({"pilot_id": pilot_dir.name, "status": state["status"], "stages": {key: value["status"] for key, value in state["stages"].items()}})
        else:
            rows.append({"pilot_id": pilot_dir.name, "status": "not_started"})
    return rows


def retry(pilot_dir: Path, artifact_root: Path, stage: str, shot_id: str | None = None) -> dict[str, Any]:
    pipeline = ProductionPipeline(pilot_dir, artifact_root)
    if stage == "motion" and shot_id:
        plan = _json(pilot_dir / "content-plan.json")
        known = {shot["shot_id"] for shot in plan["shots"]}
        if shot_id not in known:
            raise ValueError(f"Unknown shot {shot_id}; expected one of {sorted(known)}")
        clip = pipeline.artifact_dir / "clips" / "preview-v1" / f"{shot_id}.mp4"
        clip.unlink(missing_ok=True)
        clip.with_suffix(".json").unlink(missing_ok=True)
    elif shot_id:
        raise ValueError("--shot is supported only with --stage motion")
    reset_from_stage(pipeline.state_path, pipeline.state, stage)
    return {"pilot_id": pipeline.pilot_id, "reset_from_stage": stage, "shot_id": shot_id}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "status", "retry"))
    parser.add_argument("--pilots-root", default="p68-pilots")
    parser.add_argument("--artifact-root", default="p68-artifacts")
    parser.add_argument("--pilot")
    parser.add_argument("--through", choices=STAGE_ORDER, default="quality")
    parser.add_argument("--stage", choices=STAGE_ORDER, default="motion")
    parser.add_argument("--shot")
    args = parser.parse_args()
    pilots_root, artifact_root = Path(args.pilots_root), Path(args.artifact_root)
    if args.command == "status":
        print(json.dumps(status(pilots_root, artifact_root), indent=2))
        return 0
    if args.command == "retry":
        if not args.pilot:
            parser.error("retry requires --pilot")
        print(json.dumps(retry(pilots_root / args.pilot, artifact_root, args.stage, args.shot), indent=2))
        return 0
    pilots = [pilots_root / args.pilot] if args.pilot else discover_pilots(pilots_root)
    results = []
    for pilot_dir in pilots:
        try:
            output = ProductionPipeline(pilot_dir, artifact_root).run(args.through)
            results.append({"pilot_id": pilot_dir.name, "status": "complete", "output": output})
        except Exception as error:
            results.append({"pilot_id": pilot_dir.name, "status": "failed", "error": f"{type(error).__name__}: {error}"})
    print(json.dumps(results, indent=2))
    return 1 if any(item["status"] == "failed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
