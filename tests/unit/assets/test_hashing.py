from __future__ import annotations

import hashlib

from src.application.assets.hashing import inspect_file


def test_inspection_hashes_actual_bytes(tmp_path) -> None:
    path = tmp_path / "sample.bin"
    payload = b"football-brief-canonical-bytes\x00\x01"
    path.write_bytes(payload)

    inspection = inspect_file(path, chunk_size=4)

    assert inspection.sha256 == hashlib.sha256(payload).hexdigest()
    assert inspection.size_bytes == len(payload)
    assert inspection.original_filename == "sample.bin"
    assert inspection.path == path.resolve()


def test_identical_bytes_have_identical_hashes(tmp_path) -> None:
    first = tmp_path / "first.dat"
    second = tmp_path / "second.dat"
    first.write_bytes(b"same bytes")
    second.write_bytes(b"same bytes")

    assert inspect_file(first).sha256 == inspect_file(second).sha256
