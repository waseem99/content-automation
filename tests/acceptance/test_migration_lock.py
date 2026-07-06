from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "migrations"
LOCK_FILE = ROOT / "docs" / "operations" / "migration-lock.json"


def _git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


@pytest.mark.acceptance
def test_deployed_migration_lock_matches_current_files() -> None:
    lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    assert lock["hash_algorithm"] == "git_blob_sha1"
    rows = lock["migrations"]
    expected_names = [f"{index:04d}" for index in range(1, 16)]
    assert [row[0][:4] for row in rows] == expected_names

    actual_files = sorted(path.name for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    assert [row[0] for row in rows] == actual_files[: len(rows)]

    mismatches = {
        filename: {"expected": expected, "actual": _git_blob_sha1(MIGRATIONS_DIR / filename)}
        for filename, expected in rows
        if _git_blob_sha1(MIGRATIONS_DIR / filename) != expected
    }
    assert mismatches == {}
