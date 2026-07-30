from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from threading import Lock
from typing import Any, Iterable


_MODEL_BUNDLE_CACHE: dict[str, tuple[tuple[tuple[str, int, int, str], ...], dict[str, Any]]] = {}
_MODEL_BUNDLE_CACHE_LOCK = Lock()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using the repository's canonical encoding."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"P114 manifest is unavailable: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 0) != 1:
        raise RuntimeError("P114 manifest schema is invalid")
    return payload


def resolve_workflow_path(
    manifest: dict[str, Any],
    *,
    repository_root: Path,
    approved_root: Path,
) -> Path:
    raw_path = Path(str(manifest.get("workflow_path") or ""))
    path = raw_path if raw_path.is_absolute() else repository_root / raw_path
    path = path.resolve()
    approved = approved_root.resolve()
    if not path.is_file() or approved not in path.parents:
        raise RuntimeError("P114 workflow is outside the approved repository workflow root")
    return path


def validate_workflow(
    manifest: dict[str, Any],
    *,
    workflow_path: Path,
) -> dict[str, Any]:
    actual_sha256 = sha256_file(workflow_path)
    if actual_sha256 != str(manifest.get("workflow_sha256") or "").lower():
        raise RuntimeError("P114 workflow SHA-256 does not match the manifest")

    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    if not isinstance(workflow, dict) or not workflow:
        raise RuntimeError("P114 workflow must be a non-empty ComfyUI API workflow")
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or not node.get("class_type") or not isinstance(node.get("inputs"), dict):
            raise RuntimeError(f"P114 workflow node {node_id} is not API format")
    return {"workflow": workflow, "workflow_sha256": actual_sha256}


def verify_comfyui_commit(comfyui_root: Path, expected_commit: str) -> dict[str, str]:
    """Fail closed when the workstation ComfyUI checkout drifts from validation."""
    root = comfyui_root.resolve()
    expected = str(expected_commit or "").strip().lower()
    if len(expected) != 40 or any(character not in "0123456789abcdef" for character in expected):
        raise RuntimeError("validated ComfyUI commit declaration is invalid")
    if not (root / "main.py").is_file() or not (root / ".git").exists():
        raise RuntimeError("P114 ComfyUI root must be the validated Git checkout")
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    actual = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(actual) != 40:
        diagnostic = (completed.stderr or completed.stdout or "git rev-parse failed")[-1000:]
        raise RuntimeError(f"could not verify ComfyUI commit: {diagnostic}")
    if actual != expected:
        raise RuntimeError(f"ComfyUI commit mismatch: expected {expected}, found {actual}")
    return {"comfyui_root": str(root), "expected_commit": expected, "actual_commit": actual}


def _declared_model_files(source: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    if isinstance(source.get("model_files"), list):
        declared = source["model_files"]
        expected_bundle = str(source.get("model_bundle_sha256") or "").lower()
    else:
        capabilities = dict(source.get("capabilities") or {})
        declared = capabilities.get("model_files") or []
        expected_bundle = str(source.get("checkpoint_sha256") or "").lower()

    if not isinstance(declared, list) or not declared:
        raise RuntimeError("active local video workflow must declare exact model files")
    if len(expected_bundle) != 64 or any(character not in "0123456789abcdef" for character in expected_bundle):
        raise RuntimeError("local video model bundle SHA-256 declaration is invalid")
    return declared, expected_bundle


def _model_file_plan(
    source: dict[str, Any],
    *,
    model_root: Path,
) -> tuple[Path, str, list[tuple[Path, str, str]], tuple[tuple[str, int, int, str], ...]]:
    root = model_root.resolve()
    if not root.is_dir():
        raise RuntimeError("P114 model root is unavailable")

    declared, expected_bundle = _declared_model_files(source)
    plan: list[tuple[Path, str, str]] = []
    signatures: list[tuple[str, int, int, str]] = []
    for item in declared:
        if not isinstance(item, dict):
            raise RuntimeError("local video model file declaration is invalid")
        relative = Path(str(item.get("path") or ""))
        expected = str(item.get("sha256") or "").lower()
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("local video model path must be relative to P114_MODEL_ROOT")
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise RuntimeError("local video model SHA-256 declaration is invalid")

        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file():
            raise RuntimeError(f"required local video model file is unavailable: {relative.as_posix()}")
        stat = path.stat()
        declared_size = item.get("size_bytes")
        if declared_size is not None:
            try:
                expected_size = int(declared_size)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("local video model size declaration is invalid") from exc
            if expected_size <= 0 or stat.st_size != expected_size:
                raise RuntimeError(f"local video model size mismatch: {relative.as_posix()}")
        relative_posix = relative.as_posix()
        plan.append((path, relative_posix, expected))
        signatures.append((relative_posix, stat.st_size, stat.st_mtime_ns, expected))
    return root, expected_bundle, plan, tuple(signatures)


def verify_model_bundle(
    source: dict[str, Any],
    *,
    model_root: Path,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Verify exact model files, caching only while their size/mtime signatures remain unchanged."""
    root, expected_bundle, plan, signatures = _model_file_plan(source, model_root=model_root)
    cache_key = f"{root}|{expected_bundle}"
    if use_cache:
        with _MODEL_BUNDLE_CACHE_LOCK:
            cached = _MODEL_BUNDLE_CACHE.get(cache_key)
            if cached and cached[0] == signatures:
                result = json.loads(json.dumps(cached[1]))
                result["verification_cache_hit"] = True
                return result

    verified: list[dict[str, Any]] = []
    canonical: list[dict[str, str]] = []
    for path, relative_posix, expected in plan:
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"local video model hash mismatch: {relative_posix}")
        canonical.append({"path": relative_posix, "sha256": actual})
        verified.append(
            {
                "path": relative_posix,
                "sha256": actual,
                "size_bytes": path.stat().st_size,
            }
        )

    bundle_sha256 = canonical_sha256(canonical)
    if bundle_sha256 != expected_bundle:
        raise RuntimeError("local video model bundle hash mismatch")
    result = {
        "model_root": str(root),
        "bundle_sha256": bundle_sha256,
        "files": verified,
        "verification_cache_hit": False,
    }
    if use_cache:
        with _MODEL_BUNDLE_CACHE_LOCK:
            _MODEL_BUNDLE_CACHE[cache_key] = (signatures, result)
    return json.loads(json.dumps(result))


def select_resolution(
    width: int,
    height: int,
    supported_resolutions: Iterable[dict[str, Any] | list[Any] | tuple[Any, ...] | str],
) -> tuple[int, int]:
    candidates: list[tuple[int, int]] = []
    for item in supported_resolutions:
        if isinstance(item, dict):
            try:
                candidate = (int(item["width"]), int(item["height"]))
            except (KeyError, TypeError, ValueError):
                continue
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                candidate = (int(item[0]), int(item[1]))
            except (TypeError, ValueError):
                continue
        elif isinstance(item, str):
            normalized = item.strip().lower().replace("×", "x").replace(" ", "")
            parts = normalized.split("x", 1)
            if len(parts) != 2:
                continue
            try:
                candidate = (int(parts[0]), int(parts[1]))
            except ValueError:
                continue
        else:
            continue
        if candidate[0] > 0 and candidate[1] > 0 and candidate not in candidates:
            candidates.append(candidate)

    if not candidates:
        raise RuntimeError("P114 manifest does not declare a usable resolution")

    portrait = height >= width
    same_orientation = [item for item in candidates if (item[1] >= item[0]) == portrait]
    pool = same_orientation or candidates
    target_aspect = width / height if height else 1.0
    return min(
        pool,
        key=lambda item: (
            abs((item[0] / item[1]) - target_aspect),
            abs((item[0] * item[1]) - (width * height)),
        ),
    )
