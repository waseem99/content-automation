from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOCKERFILE = Path("Dockerfile")
DOCKERIGNORE = Path(".dockerignore")
REQUIREMENTS = Path("requirements.txt")
DOC = Path("docs/operations/p7-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p7_container_file_points_to_runtime_entrypoint() -> None:
    content = DOCKERFILE.read_text(encoding="utf-8")

    required_terms = [
        "FROM python:3.11.15-slim-trixie",
        "WORKDIR /app",
        "COPY requirements.txt ./requirements.txt",
        "pip install --no-cache-dir -r requirements.txt",
        "COPY src ./src",
        "COPY migrations ./migrations",
        "USER appuser",
        "EXPOSE 8000",
        "HEALTHCHECK",
        "http://127.0.0.1:8000/health",
        "uvicorn",
        "src.operator_api.entrypoint:app",
        "0.0.0.0",
        "8000",
    ]

    for term in required_terms:
        assert term in content


def test_p7_container_ignore_and_runtime_dependency_are_present() -> None:
    ignore_content = DOCKERIGNORE.read_text(encoding="utf-8")
    requirements_content = REQUIREMENTS.read_text(encoding="utf-8")

    for term in [".git", "__pycache__", ".pytest_cache", ".venv", ".env"]:
        assert term in ignore_content

    assert "uvicorn>=" in requirements_content


def test_p7_container_package_notes_cover_usage_and_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "P7 Step 01",
        "Dockerfile",
        ".dockerignore",
        "docker build -t content-automation-operator:local .",
        "docker run --rm -p 8000:8000 --env-file .env content-automation-operator:local",
        "src.operator_api.entrypoint:app",
        "src.operator_api.entrypoint:create_runtime_app",
        "GET /health",
        "No API route changes are required.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
    ]

    for term in required_terms:
        assert term in content


def test_p7_acceptance_harness_includes_step_wildcard() -> None:
    content = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p7_step_*.py" in content
