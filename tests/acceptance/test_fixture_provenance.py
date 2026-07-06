from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = ROOT / "tests" / "fixtures" / "provenance.json"
GOLDEN_DIR = ROOT / "tests" / "fixtures" / "golden"
MEDIA_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".wav", ".mp3", ".json"}
SAFE_SOURCE_TYPES = {"owned_by_project", "public_domain", "explicit_license", "generated_safe"}
SAFE_LICENSE_STATUSES = {"owned_by_project", "public_domain", "explicit_license", "generated_safe"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.acceptance
@pytest.mark.compliance
def test_fixture_provenance_records_are_complete_and_safe() -> None:
    payload = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    records = payload["fixtures"]
    assert records, "Fixture provenance must not be empty"

    seen: set[str] = set()
    for record in records:
        path = ROOT / record["path"]
        seen.add(record["path"])
        assert path.exists(), f"Fixture does not exist: {record['path']}"
        assert record["purpose"].strip()
        assert record["source_type"] in SAFE_SOURCE_TYPES
        assert record["license_status"] in SAFE_LICENSE_STATUSES
        assert record["created_by"].strip()
        assert record["created_at"].strip()
        assert record["sha256"] == _sha256(path)
        assert record["notes"].strip()

    committed_media = {
        str(path.relative_to(ROOT))
        for path in GOLDEN_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    }
    assert committed_media == seen
