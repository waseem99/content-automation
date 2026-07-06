from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_intake import IntakeRecord, IntakeRepository
from src.infrastructure.database.uow import unit_of_work


class IntakeValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CreateIntakeRequest:
    workflow_run_id: UUID
    created_by: str
    topic: str | None = None
    angle: str | None = None
    source_urls: tuple[str, ...] = ()
    football_metadata: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntakeResult:
    intake: IntakeRecord
    references: list[dict[str, Any]]
    created: bool


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _digest(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _normalize_url(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise IntakeValidationError("Only http and https URLs are supported")
    if not parsed.netloc:
        raise IntakeValidationError("URL host is required")
    host = parsed.netloc.lower()
    if host in {"localhost", "127.0.0.1", "[::1]"}:
        raise IntakeValidationError("Local URLs are not supported")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), host, path, "", query, ""))


class SourceIntakeService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, request: CreateIntakeRequest) -> IntakeResult:
        topic = _clean_text(request.topic)
        angle = _clean_text(request.angle)
        normalized_refs = tuple(dict.fromkeys(_normalize_url(url) for url in request.source_urls))
        if topic is None and not normalized_refs:
            raise IntakeValidationError("Provide a topic, URL, or both")
        canonical = {
            "topic": topic,
            "angle": angle,
            "refs": normalized_refs,
            "football_metadata": request.football_metadata,
        }
        digest = _digest(canonical)
        with unit_of_work(self.database) as uow:
            repo = IntakeRepository(uow.conn)
            existing = repo.find_existing(request.workflow_run_id, digest)
            if existing is not None:
                uow.workflow_events.create(
                    workflow_run_id=request.workflow_run_id,
                    stage_execution_id=None,
                    event_type="content_intake_reused",
                    actor=request.created_by,
                    reason="duplicate input",
                    payload={"intake_id": str(existing.id), "canonical_input_hash": digest},
                )
                return IntakeResult(existing, repo.list_references(existing.id), created=False)

            intake = repo.create(
                workflow_run_id=request.workflow_run_id,
                topic=topic,
                angle=angle,
                canonical_input_hash=digest,
                football_metadata=request.football_metadata,
                metadata=request.metadata,
                created_by=request.created_by,
            )
            refs = [
                repo.add_reference(
                    intake_id=intake.id,
                    ref_url=original,
                    normalized_ref=normalized,
                    ref_hash=_digest({"url": normalized}),
                )
                for original, normalized in zip(request.source_urls, normalized_refs, strict=False)
            ]
            uow.workflow_events.create(
                workflow_run_id=request.workflow_run_id,
                stage_execution_id=None,
                event_type="content_intake_created",
                actor=request.created_by,
                reason="operator intake",
                payload={"intake_id": str(intake.id), "canonical_input_hash": digest, "reference_count": len(refs)},
            )
            return IntakeResult(intake, refs, created=True)

    def list_for_workflow(self, workflow_run_id: UUID) -> list[IntakeRecord]:
        with unit_of_work(self.database) as uow:
            return IntakeRepository(uow.conn).list_for_workflow(workflow_run_id)
