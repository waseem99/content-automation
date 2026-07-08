from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.content_package import build_content_package, write_content_package


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p24-step-04.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def _touch(path: Path, content: str = "fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _assert_common_package_shape(package: dict) -> None:
    for term in [
        "schema_version",
        "package_id",
        "run_identity",
        "content_type",
        "content_status",
        "source_assets",
        "generated_assets",
        "platform_suitability",
        "missing_assets",
        "packaging",
        "retention",
        "rights_and_monetization",
        "exports",
        "editorial_review",
        "next_actions",
        "guardrails",
    ]:
        assert term in package

    assert package["schema_version"] == "p24.content_package.v1"
    assert package["content_status"] == "package_generated"
    assert package["packaging"]["status"] == "pending_p25"
    assert package["retention"]["status"] == "pending_p25"
    assert package["rights_and_monetization"]["status"] == "pending_p26"
    assert package["rights_and_monetization"]["publish_allowed"] is False
    assert package["rights_and_monetization"]["review_required"] is True
    assert package["exports"]["status"] == "pending_p27"
    assert package["editorial_review"]["status"] == "pending_p29"
    assert package["editorial_review"]["approval_state"] == "not_approved"

    for platform in [
        "youtube_shorts",
        "youtube_long_form",
        "tiktok",
        "instagram_reels",
        "facebook_reels",
        "x_twitter",
    ]:
        assert platform in package["platform_suitability"]
        assert package["platform_suitability"][platform]["publish_state"] == "not_publish_ready"
        assert platform in package["exports"]


def test_p24_content_package_generator_documents_scope_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #326. Closes #335 after the PR merges.",
        "src/content_package.py",
        "tests/integration/test_p24_step_04.py",
        "build_content_package(production_dir, *, content_type, ...)",
        "write_content_package(production_dir, *, content_type, output_path=None, ...)",
        "deterministic and local-file-only",
        "read an existing production folder",
        "mark future P25, P26, P27, and P29 fields as pending",
        "default `publish_allowed` to `false`",
        "default editorial approval to `not_approved`",
        "does not generate titles",
        "does not score rights risk",
        "does not render videos",
        "does not upload content",
        "does not publish content",
        "No automatic platform export.",
        "No automatic editorial approval.",
        "No workflow gate bypass.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p24_step_*.py" in HARNESS.read_text(encoding="utf-8")


def test_p24_short_content_package_generator_reads_existing_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "neymar_short_run"
    production_dir = run_dir / "production"
    _touch(run_dir / "manifest.json", '{"topic":"Neymar"}')
    _touch(run_dir / "clip_001.mp4")
    _touch(production_dir / "production_plan.json", '{"title":"Neymar Short"}')
    _touch(production_dir / "image_intro.png")
    _touch(production_dir / "image_01.png")
    _touch(production_dir / "narration_intro.mp3")
    _touch(production_dir / "subtitles.srt")
    _touch(production_dir / "preview_video.mp4")
    _touch(production_dir / "preview_video.mp4.metadata.json", '{"status":"NOT_FOR_PUBLICATION"}')
    _touch(production_dir / "image_sources.json", "[]")

    package = build_content_package(
        production_dir,
        content_type="short",
        package_id="pkg-test-short",
        run_id="short-run-001",
        created_at="2026-07-08T12:00:00Z",
    )

    _assert_common_package_shape(package)
    assert package["package_id"] == "pkg-test-short"
    assert package["content_type"] == "short"
    assert package["run_identity"]["source_command"] == "produce"
    assert package["run_identity"]["campaign_id"] is None

    source_paths = {Path(asset["path"]).name for asset in package["source_assets"]}
    assert {"manifest.json", "clip_001.mp4"} <= source_paths

    generated = package["generated_assets"]
    assert Path(generated["production_plans"][0]["path"]).name == "production_plan.json"
    assert {Path(item["path"]).name for item in generated["visuals"]} == {"image_intro.png", "image_01.png"}
    assert Path(generated["audio"][0]["path"]).name == "narration_intro.mp3"
    assert Path(generated["captions"][0]["path"]).name == "subtitles.srt"

    rendered = generated["rendered_outputs"]
    assert len(rendered) == 1
    assert Path(rendered[0]["path"]).name == "preview_video.mp4"
    assert rendered[0]["render_mode"] == "preview"
    assert rendered[0]["publication_eligible"] is False

    assert package["platform_suitability"]["youtube_shorts"]["status"] == "usable_now_review_only"
    assert "title_options" in package["missing_assets"]
    assert "platform_export_folders" in package["missing_assets"]


def test_p24_explainer_content_package_generator_reads_existing_outputs(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "wc2026_campaign"
    production_dir = campaign_dir / "production"
    _touch(campaign_dir / "concept.yaml", "title: World Cup 2026")
    _touch(campaign_dir / "clip_pool" / "manifest.json", "{}")
    _touch(production_dir / "explainer_plan.json", '{"title":"Explainer"}')
    _touch(production_dir / "beat_hook_001.png")
    _touch(production_dir / "beat_comparison_collage.png")
    _touch(production_dir / "narration_hook.mp3")
    _touch(production_dir / "subtitles.srt")
    _touch(production_dir / "final_video.mp4")
    _touch(production_dir / "image_sources.json", "[]")
    _touch(production_dir / "checkpoint.json", "{}")

    package = build_content_package(
        production_dir,
        content_type="explainer",
        package_id="pkg-test-explainer",
        run_id="explainer-run-001",
        concept_id="wc2026_hype",
        created_at="2026-07-08T12:30:00Z",
    )

    _assert_common_package_shape(package)
    assert package["package_id"] == "pkg-test-explainer"
    assert package["content_type"] == "explainer"
    assert package["run_identity"]["source_command"] == "produce-explainer"
    assert package["run_identity"]["campaign_id"] == "wc2026_campaign"
    assert package["run_identity"]["concept_id"] == "wc2026_hype"

    source_names = {Path(asset["path"]).name for asset in package["source_assets"]}
    assert {"concept.yaml", "manifest.json"} <= source_names

    generated = package["generated_assets"]
    assert Path(generated["production_plans"][0]["path"]).name == "explainer_plan.json"
    assert {Path(item["path"]).name for item in generated["visuals"]} == {
        "beat_hook_001.png",
        "beat_comparison_collage.png",
    }
    assert Path(generated["audio"][0]["path"]).name == "narration_hook.mp3"
    assert Path(generated["captions"][0]["path"]).name == "subtitles.srt"
    assert Path(generated["checkpoints"][0]["path"]).name == "checkpoint.json"

    rendered = generated["rendered_outputs"]
    assert len(rendered) == 1
    assert Path(rendered[0]["path"]).name == "final_video.mp4"
    assert rendered[0]["render_mode"] == "explainer_final_current"
    assert rendered[0]["publication_eligible"] is False

    assert package["platform_suitability"]["youtube_long_form"]["status"] == "planned_p28"


def test_p24_content_package_writer_is_deterministic_and_safe(tmp_path: Path) -> None:
    run_dir = tmp_path / "short_run"
    production_dir = run_dir / "production"
    _touch(run_dir / "manifest.json", "{}")
    _touch(production_dir / "production_plan.json", "{}")
    _touch(production_dir / "preview_video.mp4")

    first_path = write_content_package(
        production_dir,
        content_type="short",
        package_id="pkg-write-test",
        run_id="write-test",
        created_at="2026-07-08T13:00:00Z",
    )
    first_content = first_path.read_text(encoding="utf-8")

    second_path = write_content_package(
        production_dir,
        content_type="short",
        package_id="pkg-write-test",
        run_id="write-test",
        created_at="2026-07-08T13:00:00Z",
    )
    second_content = second_path.read_text(encoding="utf-8")

    assert first_path == production_dir / "content_package.json"
    assert second_path == first_path
    assert first_content == second_content

    package = json.loads(first_content)
    _assert_common_package_shape(package)
    assert package["rights_and_monetization"]["publish_allowed"] is False
    assert package["editorial_review"]["approval_state"] == "not_approved"


def test_p24_content_package_generator_rejects_invalid_inputs(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing" / "production"
    with pytest.raises(FileNotFoundError):
        build_content_package(missing_dir, content_type="short")

    production_dir = tmp_path / "run" / "production"
    production_dir.mkdir(parents=True)
    with pytest.raises(ValueError):
        build_content_package(production_dir, content_type="long_form")  # type: ignore[arg-type]
