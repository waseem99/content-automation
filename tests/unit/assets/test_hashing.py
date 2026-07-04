from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.application.assets.exceptions import FileChangedDuringHashing
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


def test_file_change_during_hashing_is_rejected(tmp_path, monkeypatch) -> None:
    path = tmp_path / "changing.bin"
    path.write_bytes(b"stable-size")
    resolved = path.resolve()
    original_stat = Path.stat
    matching_calls = 0

    def changing_stat(self: Path, *args, **kwargs):
        nonlocal matching_calls
        result = original_stat(self, *args, **kwargs)
        if str(self) != str(resolved):
            return result
        matching_calls += 1
        if matching_calls >= 3:
            return SimpleNamespace(
                st_mode=result.st_mode,
                st_size=result.st_size,
                st_mtime_ns=result.st_mtime_ns + 1,
            )
        return result

    monkeypatch.setattr(Path, "stat", changing_stat)

    with pytest.raises(FileChangedDuringHashing):
        inspect_file(path, chunk_size=2)
