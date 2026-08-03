from __future__ import annotations

from pathlib import Path

from src.operations.p114_comfyui_diagnostics import validate_workflow_schema


ROOT = Path(__file__).resolve().parents[2]


def _object_info() -> dict:
    return {
        "LoadImage": {
            "input": {
                "required": {
                    "image": [["approved.png", "other.png"], {}],
                    "upload": ["IMAGEUPLOAD", {}],
                },
                "optional": {"channel": [["image", "mask"], {}]},
                "hidden": {},
            }
        },
        "KSampler": {
            "input": {
                "required": {
                    "seed": ["INT", {}],
                    "sampler_name": [["uni_pc", "euler"], {}],
                    "model": ["MODEL", {}],
                },
                "optional": {},
                "hidden": {},
            }
        },
    }


def test_live_schema_accepts_valid_api_nodes() -> None:
    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "approved.png", "upload": "image", "channel": "image"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"seed": 114, "sampler_name": "uni_pc", "model": ["3", 0]},
        },
    }
    assert validate_workflow_schema(workflow, _object_info()) == []


def test_live_schema_reports_real_contract_mismatches() -> None:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "wrong.png", "unknown": True}},
        "2": {"class_type": "MissingNode", "inputs": {}},
    }
    codes = {item["code"] for item in validate_workflow_schema(workflow, _object_info())}
    assert codes == {
        "invalid_literal_option",
        "missing_node_class",
        "missing_required_input",
        "unknown_input",
    }


def test_template_tokens_and_links_are_not_invalid_literals() -> None:
    workflow = {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": "{{SEED}}",
                "sampler_name": "{{SAMPLER}}",
                "model": ["3", 0],
            },
        }
    }
    assert validate_workflow_schema(workflow, _object_info()) == []


def test_provider_preserves_comfyui_http_rejection_body() -> None:
    source = (ROOT / "src/application/local_video/safe_provider.py").read_text(encoding="utf-8")
    package = (ROOT / "src/application/local_video/__init__.py").read_text(encoding="utf-8")
    assert "except httpx.HTTPStatusError" in source
    assert "response.json()" in source
    assert "response.status_code" in source
    assert "safe_provider import ComfyUILocalVideoProvider" in package


def test_evidence_requires_zero_cost_internal_pending_mp4() -> None:
    source = (ROOT / "src/operations/p114_first_mp4_evidence.py").read_text(encoding="utf-8")
    for marker in (
        "asset_internal_only",
        "asset_is_mp4",
        "zero_execution_cost",
        "zero_job_cost",
        "review_pending",
        "human_review_required",
        "automatic_approval_disabled",
        "automatic_publishing_disabled",
        "sha256_matches",
    ):
        assert marker in source


def test_windows_proof_is_supervised_and_local_only() -> None:
    script = (ROOT / "scripts/windows/prove_p114_first_local_mp4.ps1").read_text(encoding="utf-8")
    assert "MinimumVramMiB = 20000" in script
    assert "[switch]$ProbePrompt" in script
    assert "collect_p114_workstation_evidence.ps1" in script
    assert "p114_comfyui_diagnostics" in script
    assert "p114_first_mp4_evidence" in script
    assert "human_review_still_required = $true" in script
    assert "automatic_paid_generation = $false" in script
    assert "automatic_approval = $false" in script
    assert "automatic_public_publishing = $false" in script
