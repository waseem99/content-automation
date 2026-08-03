from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from src.application.local_video.models import LocalVideoRequest
from src.application.local_video.provider import ComfyUILocalVideoProvider


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "config" / "local-video-workflows" / "wan22-ti2v-5b.manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_loopback(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("ComfyUI diagnostics require a loopback HTTP endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("ComfyUI diagnostic endpoint must not contain credentials, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("ComfyUI diagnostic endpoint must not contain a path")


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )


def _contains_token(value: Any) -> bool:
    return isinstance(value, str) and "{{" in value and "}}" in value


def _allowed_values(definition: Any) -> list[Any] | None:
    if not isinstance(definition, (list, tuple)) or not definition:
        return None
    first = definition[0]
    if isinstance(first, list):
        return first
    return None


def validate_workflow_schema(
    workflow: dict[str, Any],
    object_info: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare an API-format workflow with the live ComfyUI node schema."""
    issues: list[dict[str, Any]] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            issues.append({"node_id": str(node_id), "code": "node_not_object"})
            continue
        class_type = str(node.get("class_type") or "")
        inputs = node.get("inputs")
        if not class_type or not isinstance(inputs, dict):
            issues.append({"node_id": str(node_id), "code": "node_not_api_format"})
            continue
        node_info = object_info.get(class_type)
        if not isinstance(node_info, dict):
            issues.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "code": "missing_node_class",
                }
            )
            continue

        input_schema = node_info.get("input") or {}
        required = dict(input_schema.get("required") or {})
        optional = dict(input_schema.get("optional") or {})
        hidden = dict(input_schema.get("hidden") or {})
        allowed_keys = set(required) | set(optional) | set(hidden)
        actual_keys = set(inputs)

        for key in sorted(set(required) - actual_keys):
            issues.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "input": key,
                    "code": "missing_required_input",
                }
            )
        for key in sorted(actual_keys - allowed_keys):
            issues.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "input": key,
                    "code": "unknown_input",
                }
            )

        definitions = {**required, **optional}
        for key, value in inputs.items():
            if key not in definitions or _is_link(value) or _contains_token(value):
                continue
            allowed = _allowed_values(definitions[key])
            if allowed is not None and value not in allowed:
                issues.append(
                    {
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "input": key,
                        "code": "invalid_literal_option",
                        "value": value,
                        "allowed": allowed,
                    }
                )
    return issues


def _load_manifest(path: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    workflow_path = Path(str(manifest["workflow_path"]))
    if not workflow_path.is_absolute():
        workflow_path = ROOT / workflow_path
    workflow_path = workflow_path.resolve()
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    if _sha256(workflow_path) != str(manifest["workflow_sha256"]):
        raise RuntimeError("Wan2.2 workflow SHA-256 does not match the manifest")
    if not isinstance(workflow, dict) or not workflow:
        raise RuntimeError("Wan2.2 workflow must be a non-empty API-format object")
    return manifest, workflow_path, workflow


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text[-8000:]


def diagnose(
    *,
    base_url: str,
    manifest_path: Path,
    input_image: Path | None = None,
    submit_prompt: bool = False,
    keep_queued: bool = False,
) -> dict[str, Any]:
    _require_loopback(base_url)
    manifest, workflow_path, workflow = _load_manifest(manifest_path)
    provider = ComfyUILocalVideoProvider(base_url=base_url)
    try:
        health = provider.health()
        object_info = provider.object_info()
        queue_response = provider.client.get("/queue")
        queue_response.raise_for_status()
        queue = queue_response.json()
        schema_issues = validate_workflow_schema(workflow, object_info)
        required_nodes = {str(value) for value in manifest.get("required_nodes") or []}
        missing_required_nodes = sorted(required_nodes - set(object_info))
        result: dict[str, Any] = {
            "ok": not schema_issues and not missing_required_nodes,
            "kind": "p114_comfyui_diagnostic",
            "base_url": base_url,
            "manifest_path": str(manifest_path),
            "manifest_sha256": _sha256(manifest_path),
            "workflow_path": str(workflow_path),
            "workflow_sha256": _sha256(workflow_path),
            "model_bundle_sha256": manifest["model_bundle_sha256"],
            "health": health,
            "queue": {
                "running": len(queue.get("queue_running") or []),
                "pending": len(queue.get("queue_pending") or []),
            },
            "required_nodes": sorted(required_nodes),
            "missing_required_nodes": missing_required_nodes,
            "schema_issues": schema_issues,
            "prompt_probe": None,
            "external_fee_possible": False,
            "automatic_approval": False,
            "automatic_publishing": False,
        }
        if submit_prompt:
            if input_image is None or not input_image.is_file():
                raise ValueError("--input-image is required for --submit-prompt")
            resolution = dict((manifest.get("supported_resolutions") or [])[0])
            request = LocalVideoRequest(
                generation_job_id=uuid4(),
                generation_attempt_id=uuid4(),
                pilot_case_id=None,
                provider_key=str(manifest["provider_key"]),
                model_key=str(manifest["model_key"]),
                workflow_key=str(manifest["workflow_key"]),
                workflow_path=workflow_path,
                workflow_sha256=str(manifest["workflow_sha256"]),
                checkpoint_sha256=str(manifest["model_bundle_sha256"]),
                input_image_path=input_image.resolve(),
                end_image_path=None,
                prompt="Subtle natural motion. Preserve subject, composition, lighting, and identity. No cuts.",
                negative_prompt="watermark, text, deformation, flicker, duplicate subject, abrupt camera motion",
                seed=114,
                width=int(resolution["width"]),
                height=int(resolution["height"]),
                fps=int(manifest["default_fps"]),
                frame_count=int(manifest["default_frame_count"]),
                inference_steps=int(manifest["default_steps"]),
                output_prefix="p114-diagnostic/prompt-probe",
            )
            remote_name = provider._remote_image_name(input_image, "p114-diagnostic")
            uploaded_name = provider._upload_image(input_image, remote_name)
            rendered = provider.workflow_for(request, uploaded_input_name=uploaded_name)
            response = provider.client.post(
                "/prompt",
                json={"prompt": rendered, "client_id": "p114-diagnostic"},
                headers={"Idempotency-Key": request.idempotency_key},
            )
            payload = _response_body(response)
            prompt_id = ""
            if isinstance(payload, dict):
                prompt_id = str(payload.get("prompt_id") or "")
            prompt_ok = 200 <= response.status_code < 300 and bool(prompt_id)
            result["prompt_probe"] = {
                "ok": prompt_ok,
                "status_code": response.status_code,
                "response": payload,
                "prompt_id": prompt_id or None,
                "uploaded_input_name": uploaded_name,
                "cancelled_after_validation": False,
            }
            if prompt_ok and not keep_queued:
                cancel = provider.client.post("/queue", json={"delete": [prompt_id]})
                result["prompt_probe"]["cancel_status_code"] = cancel.status_code
                result["prompt_probe"]["cancel_response"] = _response_body(cancel)
                result["prompt_probe"]["cancelled_after_validation"] = cancel.is_success
            result["ok"] = bool(result["ok"] and prompt_ok)
        return result
    finally:
        provider.client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose the live P114 ComfyUI workflow contract")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--input-image", type=Path)
    parser.add_argument("--submit-prompt", action="store_true")
    parser.add_argument("--keep-queued", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = diagnose(
            base_url=args.base_url,
            manifest_path=args.manifest.resolve(),
            input_image=args.input_image.resolve() if args.input_image else None,
            submit_prompt=args.submit_prompt,
            keep_queued=args.keep_queued,
        )
    except Exception as exc:
        result = {
            "ok": False,
            "kind": "p114_comfyui_diagnostic",
            "error": f"{type(exc).__name__}: {exc}",
        }
    rendered = json.dumps(result, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
