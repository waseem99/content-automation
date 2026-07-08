"""Deterministic content package generation helpers.

This module creates a safe first-pass ``content_package.json`` contract from
existing production folders. It intentionally does not call external AI,
image, voice, render, upload, or rights-review services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

ContentType = Literal["short", "explainer"]

SCHEMA_VERSION = "p24.content_package.v1"
DEFAULT_CREATED_AT = "1970-01-01T00:00:00Z"

PLATFORMS = (
    "youtube_shorts",
    "youtube_long_form",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
)

MISSING_CREATOR_READY_ASSETS = [
    "title_options",
    "first_frame_options",
    "thumbnail_concepts",
    "upload_description",
    "hashtags",
    "pinned_comment",
    "retention_score",
    "hook_score",
    "cta_comment_trigger_options",
    "monetization_risk_report",
    "rights_clearance_status",
    "originality_assessment",
    "source_attribution_checklist",
    "music_license_note",
    "platform_export_folders",
    "human_editorial_review_status",
    "publish_readiness_manifest",
]


def _path(value: Path) -> str:
    return value.as_posix()


def _existing_sorted(paths: list[Path]) -> list[Path]:
    return sorted([path for path in paths if path.exists()], key=lambda item: item.as_posix())


def _asset(path: Path, asset_type: str, review_state: str = "review_required") -> dict[str, Any]:
    return {
        "path": _path(path),
        "type": asset_type,
        "review_state": review_state,
    }


def _source_asset(
    *,
    asset_id: str,
    asset_type: str,
    path: Path,
    role: str,
    rights_state: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "path": _path(path),
        "role": role,
        "review_state": "review_required",
        "rights_state": rights_state,
        "notes": notes,
    }


def _rendered_output(path: Path, render_mode: str, publication_eligible: bool, notes: str) -> dict[str, Any]:
    return {
        "path": _path(path),
        "render_mode": render_mode,
        "publication_eligible": publication_eligible,
        "review_state": "review_only" if not publication_eligible else "review_required",
        "notes": notes,
    }


def _platform_suitability(content_type: ContentType, rendered_names: list[str]) -> dict[str, dict[str, Any]]:
    has_publish_video = "publish_video.mp4" in rendered_names
    has_final_video = "final_video.mp4" in rendered_names
    has_video = bool(rendered_names)

    youtube_shorts_status = "usable_now_publish_candidate_after_review" if has_publish_video else "usable_now_review_only"
    if content_type == "explainer" and has_final_video:
        youtube_shorts_status = "usable_now_review_only"

    return {
        "youtube_shorts": {
            "status": youtube_shorts_status,
            "usable_current_assets": rendered_names,
            "missing_assets": [
                "title_options",
                "first_frame_options",
                "upload_description",
                "hashtags",
                "pinned_comment",
                "retention_score",
                "monetization_risk_report",
                "platform_export_folder",
                "editorial_approval",
            ],
            "review_requirements": ["packaging review", "rights review", "music review", "editorial approval"],
            "publish_state": "not_publish_ready",
        },
        "youtube_long_form": {
            "status": "planned_p28" if content_type == "explainer" else "not_supported_today",
            "usable_current_assets": rendered_names if content_type == "explainer" else [],
            "missing_assets": ["16_9_render", "long_form_concept", "chapters", "thumbnail_concepts", "source_list"],
            "review_requirements": ["future P28 long-form planning required"],
            "publish_state": "not_publish_ready",
        },
        "tiktok": {
            "status": "planned_p27" if has_video else "not_supported_today",
            "usable_current_assets": rendered_names,
            "missing_assets": ["tiktok_caption", "hashtags", "music_risk_note", "platform_export_folder"],
            "review_requirements": ["platform-specific music review", "caption review"],
            "publish_state": "not_publish_ready",
        },
        "instagram_reels": {
            "status": "planned_p27" if has_video else "not_supported_today",
            "usable_current_assets": rendered_names,
            "missing_assets": ["reels_caption", "cover_frame_note", "hashtags", "platform_export_folder"],
            "review_requirements": ["cover review", "rights review"],
            "publish_state": "not_publish_ready",
        },
        "facebook_reels": {
            "status": "planned_p27" if has_video else "not_supported_today",
            "usable_current_assets": rendered_names,
            "missing_assets": ["facebook_caption", "monetization_note", "music_risk_note", "platform_export_folder"],
            "review_requirements": ["reused-content review", "rights review"],
            "publish_state": "not_publish_ready",
        },
        "x_twitter": {
            "status": "planned_p27" if has_video else "not_supported_today",
            "usable_current_assets": rendered_names,
            "missing_assets": ["post_copy", "thread_copy", "debate_prompt", "rights_note", "platform_export_folder"],
            "review_requirements": ["factual review", "debate framing review"],
            "publish_state": "not_publish_ready",
        },
    }


def _packaging_placeholder() -> dict[str, Any]:
    return {
        "title_options": [],
        "first_frame_options": [],
        "thumbnail_concepts": [],
        "hook_notes": [],
        "cta_comment_trigger_options": [],
        "status": "pending_p25",
        "planned_epic": "P25",
    }


def _retention_placeholder() -> dict[str, Any]:
    return {
        "retention_score_path": None,
        "hook_score": None,
        "first_three_seconds_score": None,
        "midpoint_reset_score": None,
        "cta_strength_score": None,
        "dead_air_risk": "pending",
        "genericness_risk": "pending",
        "recommended_fixes": [],
        "status": "pending_p25",
        "planned_epic": "P25",
    }


def _rights_placeholder() -> dict[str, Any]:
    return {
        "monetization_risk_report_path": None,
        "publish_allowed": False,
        "review_required": True,
        "rights_clearance_status": "pending_p26",
        "source_attribution_status": "pending_p26",
        "music_license_status": "pending_p26",
        "originality_status": "pending_p26",
        "blocking_reasons": ["rights and monetization review not completed"],
        "required_actions": ["complete P26 risk review before any publish-ready decision"],
        "status": "pending_p26",
        "planned_epic": "P26",
    }


def _exports_placeholder() -> dict[str, Any]:
    return {
        "youtube_shorts": {
            "export_path": None,
            "required_files": ["video.mp4", "title.txt", "description.txt", "hashtags.txt", "pinned_comment.txt", "risk_note.txt"],
            "status": "pending_p27",
            "notes": "YouTube Shorts export pack not generated yet.",
        },
        "youtube_long_form": {
            "export_path": None,
            "required_files": ["video.mp4", "title.txt", "description.txt", "thumbnail_notes.txt", "chapters.txt", "risk_note.txt"],
            "status": "planned_p28_then_p27",
            "notes": "True long-form package requires P28 planning first.",
        },
        "tiktok": {
            "export_path": None,
            "required_files": ["video.mp4", "caption.txt", "hashtags.txt", "music_risk_note.txt"],
            "status": "pending_p27",
            "notes": "TikTok export pack not generated yet.",
        },
        "instagram_reels": {
            "export_path": None,
            "required_files": ["video.mp4", "caption.txt", "hashtags.txt", "cover_notes.txt", "music_risk_note.txt"],
            "status": "pending_p27",
            "notes": "Instagram Reels export pack not generated yet.",
        },
        "facebook_reels": {
            "export_path": None,
            "required_files": ["video.mp4", "caption.txt", "hashtags.txt", "monetization_note.txt", "music_risk_note.txt"],
            "status": "pending_p27",
            "notes": "Facebook Reels export pack not generated yet.",
        },
        "x_twitter": {
            "export_path": None,
            "required_files": ["post.txt", "thread.txt", "hashtags.txt", "debate_prompt.txt", "risk_note.txt"],
            "status": "pending_p27",
            "notes": "X/Twitter export pack not generated yet.",
        },
        "status": "pending_p27",
        "planned_epic": "P27",
    }


def _editorial_placeholder() -> dict[str, Any]:
    return {
        "status": "pending_p29",
        "approval_state": "not_approved",
        "review_owner_role": "editorial reviewer",
        "rights_reviewer_role": "rights reviewer",
        "approved_at": None,
        "blockers": ["editorial review not completed", "rights review not completed"],
        "required_actions": ["complete P29 publish-governance review before publish-ready export"],
        "planned_epic": "P29",
    }


def _next_actions() -> list[dict[str, Any]]:
    return [
        {
            "action_id": "p25_packaging",
            "owner_role": "content strategist",
            "description": "Generate title options, first-frame options, thumbnail concepts, hook notes, and CTA options.",
            "blocking": True,
            "target_epic": "P25",
        },
        {
            "action_id": "p26_risk_review",
            "owner_role": "rights reviewer",
            "description": "Review rights, monetization, attribution, music, and originality risks.",
            "blocking": True,
            "target_epic": "P26",
        },
        {
            "action_id": "p27_exports",
            "owner_role": "publishing operator",
            "description": "Generate platform-specific export folders after packaging and risk review fields exist.",
            "blocking": True,
            "target_epic": "P27",
        },
        {
            "action_id": "p29_editorial_review",
            "owner_role": "editorial reviewer",
            "description": "Approve or block the package before any publish-ready decision.",
            "blocking": True,
            "target_epic": "P29",
        },
    ]


def _guardrails() -> list[str]:
    return [
        "No automatic publishing.",
        "No automatic upload.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No preview render publication.",
        "No workflow gate bypass.",
    ]


def _short_source_assets(production_dir: Path) -> list[dict[str, Any]]:
    run_dir = production_dir.parent
    assets: list[dict[str, Any]] = []
    manifest = run_dir / "manifest.json"
    if manifest.exists():
        assets.append(
            _source_asset(
                asset_id="single_run_manifest",
                asset_type="single_run_manifest",
                path=manifest,
                role="clip and topic source evidence",
                rights_state="unreviewed",
                notes="Contains clip timestamps, scores, labels, and source text for the Short run.",
            )
        )
    for index, clip in enumerate(_existing_sorted(list(run_dir.glob("clip_*.mp4"))), start=1):
        assets.append(
            _source_asset(
                asset_id=f"clip_{index:03d}",
                asset_type="extracted_clip",
                path=clip,
                role="candidate football moment",
                rights_state="unreviewed_high_risk",
                notes="Broadcast footage must not be treated as rights-cleared by default.",
            )
        )
    return assets


def _explainer_source_assets(production_dir: Path) -> list[dict[str, Any]]:
    campaign_dir = production_dir.parent
    assets: list[dict[str, Any]] = []
    concept = campaign_dir / "concept.yaml"
    if concept.exists():
        assets.append(
            _source_asset(
                asset_id="concept_yaml",
                asset_type="concept_yaml",
                path=concept,
                role="campaign concept and section plan",
                rights_state="not_applicable",
                notes="Concept copy and stats require factual source review.",
            )
        )
    clip_pool_manifest = campaign_dir / "clip_pool" / "manifest.json"
    if clip_pool_manifest.exists():
        assets.append(
            _source_asset(
                asset_id="clip_pool_manifest",
                asset_type="clip_pool_manifest",
                path=clip_pool_manifest,
                role="multi-video clip pool evidence",
                rights_state="unreviewed",
                notes="Clip pool references source footage that must be reviewed before publishing.",
            )
        )
    return assets


def _generated_assets(production_dir: Path, content_type: ContentType) -> dict[str, Any]:
    plan_name = "production_plan.json" if content_type == "short" else "explainer_plan.json"
    plan_type = "short_production_plan" if content_type == "short" else "explainer_production_plan"

    production_plans = [_asset(production_dir / plan_name, plan_type)] if (production_dir / plan_name).exists() else []
    visuals = [
        _asset(path, "visual_asset")
        for path in _existing_sorted(
            list(production_dir.glob("image*.png"))
            + list(production_dir.glob("beat_*.png"))
            + [production_dir / "beat_comparison_collage.png"]
        )
    ]
    audio = [_asset(path, "voiceover") for path in _existing_sorted(list(production_dir.glob("narration_*.mp3")))]
    captions = [_asset(production_dir / "subtitles.srt", "subtitles")] if (production_dir / "subtitles.srt").exists() else []

    rendered_outputs: list[dict[str, Any]] = []
    preview_video = production_dir / "preview_video.mp4"
    if preview_video.exists():
        rendered_outputs.append(
            _rendered_output(
                preview_video,
                "preview",
                False,
                "Preview render is not publication eligible.",
            )
        )
    publish_video = production_dir / "publish_video.mp4"
    if publish_video.exists():
        rendered_outputs.append(
            _rendered_output(
                publish_video,
                "publish_candidate",
                False,
                "Publish render still requires package, rights, export, and editorial review.",
            )
        )
    final_video = production_dir / "final_video.mp4"
    if final_video.exists():
        rendered_outputs.append(
            _rendered_output(
                final_video,
                "explainer_final_current",
                False,
                "Current explainer output still requires package, rights, export, and editorial review.",
            )
        )

    source_evidence = [
        _asset(path, "source_evidence")
        for path in _existing_sorted(
            [
                production_dir / "image_sources.json",
                production_dir / "preview_video.mp4.metadata.json",
            ]
        )
    ]
    checkpoints = [_asset(production_dir / "checkpoint.json", "production_checkpoint", "operator_reference")] if (production_dir / "checkpoint.json").exists() else []

    return {
        "production_plans": production_plans,
        "visuals": visuals,
        "audio": audio,
        "captions": captions,
        "rendered_outputs": rendered_outputs,
        "source_evidence": source_evidence,
        "checkpoints": checkpoints,
    }


def build_content_package(
    production_dir: Path,
    *,
    content_type: ContentType,
    package_id: str | None = None,
    run_id: str | None = None,
    campaign_id: str | None = None,
    concept_id: str | None = None,
    created_at: str = DEFAULT_CREATED_AT,
) -> dict[str, Any]:
    """Build a deterministic content package from existing production outputs."""
    production_dir = production_dir.resolve()
    if content_type not in {"short", "explainer"}:
        raise ValueError("content_type must be 'short' or 'explainer'")
    if not production_dir.exists():
        raise FileNotFoundError(f"Production folder not found: {production_dir}")

    source_assets = _short_source_assets(production_dir) if content_type == "short" else _explainer_source_assets(production_dir)
    generated_assets = _generated_assets(production_dir, content_type)
    rendered_names = [Path(output["path"]).name for output in generated_assets["rendered_outputs"]]

    resolved_run_id = run_id or production_dir.parent.name
    resolved_package_id = package_id or f"pkg-{content_type}-{resolved_run_id}"
    resolved_campaign_id = campaign_id if campaign_id is not None else (production_dir.parent.name if content_type == "explainer" else None)

    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": resolved_package_id,
        "run_identity": {
            "run_id": resolved_run_id,
            "run_folder": _path(production_dir),
            "campaign_id": resolved_campaign_id,
            "concept_id": concept_id,
            "source_command": "produce" if content_type == "short" else "produce-explainer",
            "created_at": created_at,
            "package_owner_role": "content operator",
            "reviewer_role": "editorial reviewer",
        },
        "content_type": content_type,
        "content_status": "package_generated",
        "source_assets": source_assets,
        "generated_assets": generated_assets,
        "platform_suitability": _platform_suitability(content_type, rendered_names),
        "missing_assets": list(MISSING_CREATOR_READY_ASSETS),
        "packaging": _packaging_placeholder(),
        "retention": _retention_placeholder(),
        "rights_and_monetization": _rights_placeholder(),
        "exports": _exports_placeholder(),
        "editorial_review": _editorial_placeholder(),
        "next_actions": _next_actions(),
        "guardrails": _guardrails(),
    }


def write_content_package(
    production_dir: Path,
    *,
    content_type: ContentType,
    output_path: Path | None = None,
    package_id: str | None = None,
    run_id: str | None = None,
    campaign_id: str | None = None,
    concept_id: str | None = None,
    created_at: str = DEFAULT_CREATED_AT,
) -> Path:
    """Write ``content_package.json`` for an existing production folder."""
    package = build_content_package(
        production_dir,
        content_type=content_type,
        package_id=package_id,
        run_id=run_id,
        campaign_id=campaign_id,
        concept_id=concept_id,
        created_at=created_at,
    )
    target = output_path or production_dir / "content_package.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
