from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".sql", ".toml", ".ini", ".feature", ".svg", ".example"}
SKIP_DIRS = {".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "data", "__pycache__"}
PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}\b", re.IGNORECASE),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|authorization)\b\s*[:=]\s*['\"]?([A-Za-z0-9_./+=\-]{12,})"),
)
PLACEHOLDER_VALUES = {"...", "changeme", "change_me", "placeholder", "example", "dummy", "test", "not-a-secret", "redacted"}
SAFE_VALUE_PREFIXES = ("settings.", "self.", "config.", "os.environ", "getenv(", "env.")
SAFE_RUNTIME_ASSIGNMENTS = (
    re.compile(r"\btoken\s*=\s*secrets\.token_urlsafe\("),
    re.compile(r"\btoken\s*=\s*token_from_url\("),
    re.compile(r"\btoken\s*=\s*[^,)]*token_from_url\("),
)


def _is_text_file(path: Path) -> bool:
    if path.name.endswith(".env") and path.name != ".env.example":
        return True
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"requirements.txt", "pytest.ini"}


def _is_runtime_derived_access_value(line: str) -> bool:
    return any(pattern.search(line) for pattern in SAFE_RUNTIME_ASSIGNMENTS)


def _is_placeholder(line: str, match: re.Match[str]) -> bool:
    value = match.group(1) if match.lastindex else match.group(0)
    cleaned = value.strip("'\" ,)").lower()
    if cleaned in PLACEHOLDER_VALUES:
        return True
    if cleaned.startswith(SAFE_VALUE_PREFIXES):
        return True
    if _is_runtime_derived_access_value(line):
        return True
    if "..." in line or "<" in line or ">" in line:
        return True
    lowered = line.lower()
    return "example" in lowered or "placeholder" in lowered or "[redacted]" in lowered or " is not set" in lowered


@pytest.mark.acceptance
@pytest.mark.compliance
def test_no_committed_env_files_or_obvious_sensitive_values() -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if not path.is_file() or not _is_text_file(path):
            continue
        relative = path.relative_to(ROOT)
        if path.name == ".env":
            findings.append(f"{relative}: committed .env file")
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for pattern in PATTERNS:
                match = pattern.search(line)
                if match and not _is_placeholder(line, match):
                    findings.append(f"{relative}:{line_number}: sensitive-looking value")
    assert findings == []
