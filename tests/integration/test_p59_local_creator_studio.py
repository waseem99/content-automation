import json
import subprocess
import sys
from pathlib import Path

from src.p59_local_creator_studio import (
    build_studio_workspace,
    default_sample_brief,
    guardrails,
)


def test_default_sample_brief_has_required_fields():
    brief = default_sample_brief()
    assert brief["topic"]
    assert brief["platform"] == "youtube_shorts"
    assert brief["audience"]
    assert brief["monetization_goal"]
    assert isinstance(brief["must_use_points"], list)
    assert isinstance(brief["avoid"], list)


def test_build_studio_workspace_writes_expected_files(tmp_path):
    result = build_studio_workspace(tmp_path, overwrite=True)
    assert result["is_valid"] is True
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False

    html_path = tmp_path / "creator_studio.html"
    sample_path = tmp_path / "sample_brief.json"
    manifest_path = tmp_path / "studio_manifest.json"
    readme_path = tmp_path / "studio_readme.md"
    for path in [html_path, sample_path, manifest_path, readme_path]:
        assert path.exists(), path

    html = html_path.read_text(encoding="utf-8")
    assert "Local Creator Studio Starter" in html
    assert "Generated brief JSON" in html
    assert "navigator.clipboard" in html
    assert "python -m src.p58_review_cycle_runner" in html

    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    assert sample["demo_id"] == "custom-ai-operations-short"
    assert sample["monetization_goal"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "p59.local_creator_studio_starter.v1"
    assert manifest["open_first"] == "creator_studio.html"
    assert manifest["sample_brief"] == "sample_brief.json"
    assert manifest["human_review_required_before_production"] is True
    assert manifest["external_calls_performed"] is False

    readme = readme_path.read_text(encoding="utf-8")
    assert "Local workflow" in readme
    assert "review_cycle_index.html" in readme


def test_build_studio_workspace_refuses_overwrite_by_default(tmp_path):
    build_studio_workspace(tmp_path, overwrite=True)
    try:
        build_studio_workspace(tmp_path, overwrite=False)
    except FileExistsError as exc:
        assert "Refusing to overwrite" in str(exc)
    else:
        raise AssertionError("Expected FileExistsError")


def test_cli_creates_workspace(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.p59_local_creator_studio",
            "--output-root",
            str(tmp_path),
            "--overwrite",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert Path(payload["creator_studio_html_path"]).exists()
    assert Path(payload["sample_brief_path"]).exists()
    assert payload["deployment_performed"] is False


def test_guardrails_are_local_only():
    data = guardrails()
    assert data["local_only"] is True
    assert data["hosted_ui_created"] is False
    assert data["api_server_started"] is False
    assert data["external_calls_performed"] is False
    assert data["browser_command_execution"] is False
    assert data["human_review_required_before_production"] is True
