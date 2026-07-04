from __future__ import annotations

import hashlib
import json
from typing import Any

from src.domain.render_manifest_models import RenderManifestDocument


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def manifest_hash(document: RenderManifestDocument) -> str:
    return sha256_json(document.model_dump(mode="json"))


def material_input_payload(document: RenderManifestDocument) -> dict[str, Any]:
    payload = document.model_dump(mode="json")
    payload.pop("manifest_version", None)
    payload.pop("approval", None)
    payload.pop("rights_evaluation", None)
    return payload


def material_input_hash(document: RenderManifestDocument) -> str:
    return sha256_json(material_input_payload(document))
