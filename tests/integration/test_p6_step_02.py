from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p6-step-02.md")


def test_p6_packaging_notes_document_runtime_entrypoint() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "src.operator_api.entrypoint:app",
        "src.operator_api.entrypoint:create_runtime_app",
        "uvicorn src.operator_api.entrypoint:app --host 127.0.0.1 --port 8000",
        "requirements.txt",
        ".env.example",
    ]

    for term in required_terms:
        assert term in content


def test_p6_packaging_notes_document_service_and_container_contracts() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Container packaging contract",
        "Service packaging contract",
        "working directory",
        "repository root",
        "non-root user",
        "stdout",
        "platform log collector",
        "outside the image",
        "build artifacts",
    ]

    for term in required_terms:
        assert term in content


def test_p6_packaging_notes_document_health_and_readiness() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Healthcheck guidance",
        "GET /health",
        "ok",
        "service",
        "version",
        "database_configured",
        "auth_required",
        "Readiness guidance",
        "migrations have been applied",
        "protected routes require operator access",
    ]

    for term in required_terms:
        assert term in content


def test_p6_packaging_notes_preserve_non_goals() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "No Dockerfile is added.",
        "No service unit is added.",
        "No deployment system is selected.",
        "No publishing is added.",
        "No scheduling is added.",
        "No rendering is added.",
        "No external export is added.",
    ]

    for term in required_terms:
        assert term in content
