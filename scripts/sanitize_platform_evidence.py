from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import tempfile
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REDACTION = "<redacted-operator-key>"
SECRET_ENV_NAMES = (
    "PLATFORM_ADMIN_KEY",
    "PLATFORM_SUPER_ADMIN_KEY",
    "PLATFORM_REVIEWER_KEY",
)
TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".log",
    ".md",
    ".network",
    ".stacks",
    ".trace",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
HTML_ZIP_PATTERN = re.compile(
    rb"(data:application/zip;base64,)([A-Za-z0-9+/=\r\n]+)"
)


@dataclass
class Counters:
    files_checked: int = 0
    files_rewritten: int = 0
    archives_rewritten: int = 0
    embedded_reports_rewritten: int = 0
    redactions: int = 0


def _variants(secret: str) -> list[tuple[bytes, bytes]]:
    raw = secret.encode("utf-8")
    values = {
        raw: REDACTION.encode("utf-8"),
        secret.encode("utf-16-le"): REDACTION.encode("utf-16-le"),
        secret.encode("utf-16-be"): REDACTION.encode("utf-16-be"),
        base64.b64encode(raw): base64.b64encode(REDACTION.encode("utf-8")),
        urllib.parse.quote(secret, safe="").encode("ascii"): REDACTION.encode("ascii"),
    }
    return sorted(values.items(), key=lambda item: len(item[0]), reverse=True)


def _all_variants(secrets: Iterable[str]) -> list[tuple[bytes, bytes]]:
    unique: dict[bytes, bytes] = {}
    for secret in secrets:
        for source, replacement in _variants(secret):
            if source:
                unique[source] = replacement
    return sorted(unique.items(), key=lambda item: len(item[0]), reverse=True)


def _redact_bytes(data: bytes, variants: list[tuple[bytes, bytes]], counters: Counters) -> bytes:
    result = data
    for source, replacement in variants:
        count = result.count(source)
        if count:
            counters.redactions += count
            result = result.replace(source, replacement)
    return result


def _copy_zip_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    copied.compress_type = info.compress_type
    copied.comment = info.comment
    copied.extra = info.extra
    copied.internal_attr = info.internal_attr
    copied.external_attr = info.external_attr
    copied.create_system = info.create_system
    copied.create_version = info.create_version
    copied.extract_version = info.extract_version
    copied.flag_bits = info.flag_bits
    return copied


def _sanitize_html_bytes(
    data: bytes,
    variants: list[tuple[bytes, bytes]],
    counters: Counters,
) -> bytes:
    output = _redact_bytes(data, variants, counters)

    def replace_embedded(match: re.Match[bytes]) -> bytes:
        encoded = re.sub(rb"\s+", b"", match.group(2))
        try:
            decoded = base64.b64decode(encoded, validate=False)
        except Exception:
            return match.group(0)
        decoded = _redact_bytes(decoded, variants, counters)
        if zipfile.is_zipfile(io.BytesIO(decoded)):
            decoded = _sanitize_zip_bytes(decoded, variants, counters)
        counters.embedded_reports_rewritten += 1
        return match.group(1) + base64.b64encode(decoded)

    return HTML_ZIP_PATTERN.sub(replace_embedded, output)


def _sanitize_zip_bytes(
    data: bytes,
    variants: list[tuple[bytes, bytes]],
    counters: Counters,
) -> bytes:
    source = io.BytesIO(data)
    target = io.BytesIO()
    with zipfile.ZipFile(source, "r") as archive_in, zipfile.ZipFile(target, "w") as archive_out:
        for info in archive_in.infolist():
            payload = archive_in.read(info.filename)
            payload = _redact_bytes(payload, variants, counters)
            suffix = Path(info.filename).suffix.lower()
            if suffix in {".html", ".htm"}:
                payload = _sanitize_html_bytes(payload, variants, counters)
            elif suffix == ".zip" or zipfile.is_zipfile(io.BytesIO(payload)):
                payload = _sanitize_zip_bytes(payload, variants, counters)
            archive_out.writestr(_copy_zip_info(info), payload)
    counters.archives_rewritten += 1
    return target.getvalue()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.") as handle:
        handle.write(data)
        temporary = Path(handle.name)
    try:
        shutil.copystat(path, temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _scan_binary(path: Path, needles: list[bytes]) -> bool:
    longest = max((len(item) for item in needles), default=1)
    overlap = max(0, longest - 1)
    tail = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                return False
            data = tail + chunk
            if any(needle in data for needle in needles):
                return True
            tail = data[-overlap:] if overlap else b""


def sanitize_file(
    path: Path,
    variants: list[tuple[bytes, bytes]],
    counters: Counters,
) -> None:
    counters.files_checked += 1
    suffix = path.suffix.lower()
    if suffix == ".zip":
        original = path.read_bytes()
        updated = _sanitize_zip_bytes(original, variants, counters)
        if updated != original:
            _write_atomic(path, updated)
            counters.files_rewritten += 1
        return
    if suffix in {".html", ".htm"}:
        original = path.read_bytes()
        updated = _sanitize_html_bytes(original, variants, counters)
        if updated != original:
            _write_atomic(path, updated)
            counters.files_rewritten += 1
        return
    if suffix in TEXT_SUFFIXES:
        original = path.read_bytes()
        updated = _redact_bytes(original, variants, counters)
        if updated != original:
            _write_atomic(path, updated)
            counters.files_rewritten += 1
        return

    needles = [source for source, _ in variants]
    if _scan_binary(path, needles):
        raise RuntimeError(f"Sensitive value was found in an unsupported binary artifact: {path.name}")


def _zip_contains(data: bytes, needles: list[bytes]) -> bool:
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        for info in archive.infolist():
            payload = archive.read(info.filename)
            if any(needle in payload for needle in needles):
                return True
            suffix = Path(info.filename).suffix.lower()
            if suffix in {".html", ".htm"} and _html_contains(payload, needles):
                return True
            if (suffix == ".zip" or zipfile.is_zipfile(io.BytesIO(payload))) and _zip_contains(payload, needles):
                return True
    return False


def _html_contains(data: bytes, needles: list[bytes]) -> bool:
    if any(needle in data for needle in needles):
        return True
    for match in HTML_ZIP_PATTERN.finditer(data):
        encoded = re.sub(rb"\s+", b"", match.group(2))
        try:
            decoded = base64.b64decode(encoded, validate=False)
        except Exception:
            continue
        if any(needle in decoded for needle in needles):
            return True
        if zipfile.is_zipfile(io.BytesIO(decoded)) and _zip_contains(decoded, needles):
            return True
    return False


def verify_file(path: Path, needles: list[bytes]) -> None:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        if _zip_contains(path.read_bytes(), needles):
            raise RuntimeError(f"Sensitive value remains in archive: {path.name}")
        return
    if suffix in {".html", ".htm"}:
        if _html_contains(path.read_bytes(), needles):
            raise RuntimeError(f"Sensitive value remains in HTML report: {path.name}")
        return
    if _scan_binary(path, needles):
        raise RuntimeError(f"Sensitive value remains in evidence: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact operator keys from retained Playwright evidence.")
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Evidence directory does not exist: {root}")

    secrets = [str(os.environ.get(name) or "").strip() for name in SECRET_ENV_NAMES]
    secrets = sorted({value for value in secrets if value})
    if not secrets:
        raise SystemExit("No operator-key environment variables were available for evidence sanitization.")

    variants = _all_variants(secrets)
    counters = Counters()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        sanitize_file(path, variants, counters)

    needles = [source for source, _ in variants]
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        verify_file(path, needles)

    summary = {
        "kind": "platform_evidence_sanitization",
        "status": "passed",
        "files_checked": counters.files_checked,
        "files_rewritten": counters.files_rewritten,
        "archives_rewritten": counters.archives_rewritten,
        "embedded_reports_rewritten": counters.embedded_reports_rewritten,
        "redactions": counters.redactions,
        "secret_values_recorded": False,
    }
    (root / "evidence-sanitization.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Platform evidence sanitized and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
