"""Review-safe reference intelligence bridge for the portfolio operator API."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


RIGHTS_DECLARATIONS = {
    "owned",
    "permitted",
    "public-internal-research",
    "rights-holder-upload",
}
JOB_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"running", "partial", "succeeded", "failed", "cancelled"},
    "partial": {"running", "partial", "succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}
SOURCE_STATUS_BY_JOB = {
    "queued": "queued",
    "running": "processing",
    "partial": "partial",
    "succeeded": "ready_for_review",
    "failed": "failed",
    "cancelled": "blocked",
}
SENSITIVE_QUERY_PARTS = {
    "auth",
    "authorization",
    "cookie",
    "expires",
    "key",
    "password",
    "secret",
    "session",
    "signature",
    "token",
}
ARTIFACT_KINDS = {
    "contact_sheet",
    "analysis_report",
    "temporal_report",
    "fingerprint",
    "comparison_report",
    "pattern_library",
    "pattern_brief",
    "originality_gate",
}


def sanitize_source_url(value: str | None) -> str | None:
    """Return a canonical public locator without credentials or signed query values."""
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source_url must be an absolute HTTP(S) URL")
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not any(part in key.lower() for part in SENSITIVE_QUERY_PARTS)
    ]
    hostname = parsed.hostname.lower()
    netloc = hostname
    if parsed.port and not (
        (parsed.scheme == "http" and parsed.port == 80)
        or (parsed.scheme == "https" and parsed.port == 443)
    ):
        netloc = f"{hostname}:{parsed.port}"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            re.sub(r"/{2,}", "/", parsed.path) or "/",
            urlencode(query),
            "",
        )
    )


def sanitize_diagnostic(value: str | None) -> str | None:
    if not value:
        return None
    sanitized = re.sub(
        r"(?i)(password|secret|token|cookie|authorization)\s*[=:]\s*\S+",
        r"\1=<redacted>",
        value,
    )
    sanitized = re.sub(r"(?:[A-Za-z]:)?[/\\][^\s]+", "<local-path>", sanitized)
    return sanitized[:500]


def sanitize_review_metadata(value: Any) -> Any:
    """Remove credentials and machine-local paths from bounded review metadata."""
    if isinstance(value, dict):
        return {
            str(key)[:120]: sanitize_review_metadata(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SENSITIVE_QUERY_PARTS)
        }
    if isinstance(value, list):
        return [sanitize_review_metadata(item) for item in value[:100]]
    if isinstance(value, str):
        return sanitize_diagnostic(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_diagnostic(str(value))


def source_locator_hash(local_reference_id: str, canonical_url: str | None) -> str:
    payload = f"{local_reference_id}\n{canonical_url or 'local'}"
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_job_transition(current: str, target: str) -> None:
    if target not in JOB_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid job transition: {current} -> {target}")


def validate_local_locator(value: str) -> str:
    if not re.fullmatch(r"reference://[A-Za-z0-9._/-]+", value):
        raise ValueError("local_locator must use a safe reference:// locator")
    lowered = value.lower()
    if any(part in lowered for part in ("/source/", "analysis.mp4", "audio.wav")):
        raise ValueError("source media cannot be registered as a review artifact")
    return value


class ReferenceIntelligenceService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def enqueue_reference(self, payload: dict[str, Any], *, created_by: str) -> dict[str, Any]:
        rights = str(payload["rights_declaration"])
        if rights not in RIGHTS_DECLARATIONS:
            return {"ok": False, "error": "invalid_rights_declaration"}
        canonical_url = sanitize_source_url(payload.get("source_url"))
        local_reference_id = str(payload["local_reference_id"]).strip()
        locator_hash = source_locator_hash(local_reference_id, canonical_url)
        with self.database.transaction() as conn:
            source = conn.execute(
                """INSERT INTO football_brief.reference_sources
                   (local_reference_id, source_locator_hash, canonical_url, title, platform,
                    media_type, rights_declaration, status, limitations, metadata, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s::jsonb,%s::jsonb,%s)
                   ON CONFLICT (local_reference_id) DO UPDATE SET
                     source_locator_hash=EXCLUDED.source_locator_hash,
                     canonical_url=EXCLUDED.canonical_url, title=EXCLUDED.title,
                     platform=EXCLUDED.platform, media_type=EXCLUDED.media_type,
                     rights_declaration=EXCLUDED.rights_declaration,
                     limitations=EXCLUDED.limitations, metadata=EXCLUDED.metadata
                   RETURNING *""",
                (
                    local_reference_id,
                    locator_hash,
                    canonical_url,
                    payload["title"],
                    payload["platform"],
                    payload.get("media_type", "unknown"),
                    rights,
                    json.dumps(sanitize_review_metadata(payload.get("limitations", []))),
                    json.dumps(sanitize_review_metadata(payload.get("metadata", {}))),
                    created_by,
                ),
            ).fetchone()
            active = conn.execute(
                """SELECT * FROM football_brief.reference_ingestion_jobs
                   WHERE reference_source_id=%s AND status IN ('queued','running','partial')
                   ORDER BY attempt DESC LIMIT 1""",
                (source["id"],),
            ).fetchone()
            if active:
                job = active
                reused = True
            else:
                attempt_row = conn.execute(
                    """SELECT COALESCE(MAX(attempt),0)+1 AS attempt
                       FROM football_brief.reference_ingestion_jobs
                       WHERE reference_source_id=%s""",
                    (source["id"],),
                ).fetchone()
                job = conn.execute(
                    """INSERT INTO football_brief.reference_ingestion_jobs
                       (reference_source_id, attempt, fallback_action)
                       VALUES (%s,%s,%s) RETURNING *""",
                    (
                        source["id"],
                        attempt_row["attempt"],
                        "Use an authorized local export with refintel ingest-file.",
                    ),
                ).fetchone()
                reused = False
        return {"ok": True, "source": dict(source), "job": dict(job), "job_reused": reused}

    def queue(
        self,
        *,
        brand_id: UUID | None = None,
        platform: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        values: list[Any] = []
        if brand_id:
            conditions.append(
                "EXISTS (SELECT 1 FROM football_brief.reference_brand_assignments rba "
                "WHERE rba.reference_source_id=rs.id AND rba.brand_id=%s AND rba.active=true)"
            )
            values.append(brand_id)
        if platform:
            conditions.append("rs.platform=%s")
            values.append(platform)
        if status:
            conditions.append("rs.status=%s")
            values.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.database.connection() as conn:
            rows = conn.execute(
                f"""SELECT rs.*,
                       job.id AS job_id, job.status AS job_status, job.stage AS job_stage,
                       job.progress_percent, job.sanitized_error, job.fallback_action,
                       COALESCE(art.artifact_count,0)::int AS artifact_count,
                       COALESCE(brand.brand_count,0)::int AS brand_count,
                       COALESCE(gate.approved_gate_count,0)::int AS approved_gate_count,
                       COALESCE(link.idea_link_count,0)::int AS idea_link_count
                   FROM football_brief.reference_sources rs
                   LEFT JOIN LATERAL (
                     SELECT * FROM football_brief.reference_ingestion_jobs
                     WHERE reference_source_id=rs.id ORDER BY attempt DESC LIMIT 1
                   ) job ON true
                   LEFT JOIN LATERAL (
                     SELECT COUNT(*) AS artifact_count FROM football_brief.reference_artifacts
                     WHERE reference_source_id=rs.id
                   ) art ON true
                   LEFT JOIN LATERAL (
                     SELECT COUNT(*) AS brand_count
                     FROM football_brief.reference_brand_assignments
                     WHERE reference_source_id=rs.id AND active=true
                   ) brand ON true
                   LEFT JOIN LATERAL (
                     SELECT COUNT(DISTINCT gate) AS approved_gate_count
                     FROM football_brief.reference_approval_gates
                     WHERE reference_source_id=rs.id AND decision='approved'
                   ) gate ON true
                   LEFT JOIN LATERAL (
                     SELECT COUNT(*) AS idea_link_count FROM football_brief.research_idea_links
                     WHERE reference_source_id=rs.id
                   ) link ON true
                   {where} ORDER BY rs.updated_at DESC""",
                tuple(values),
            ).fetchall()
        return [dict(row) for row in rows]

    def detail(self, source_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            source = conn.execute(
                "SELECT * FROM football_brief.reference_sources WHERE id=%s",
                (source_id,),
            ).fetchone()
            if not source:
                return {"ok": False, "error": "reference_not_found"}
            jobs = conn.execute(
                """SELECT * FROM football_brief.reference_ingestion_jobs
                   WHERE reference_source_id=%s ORDER BY attempt DESC""",
                (source_id,),
            ).fetchall()
            artifacts = conn.execute(
                """SELECT * FROM football_brief.reference_artifacts
                   WHERE reference_source_id=%s ORDER BY artifact_kind, version DESC""",
                (source_id,),
            ).fetchall()
            assignments = conn.execute(
                """SELECT rba.*, b.slug AS brand_slug, b.display_name AS brand_name
                   FROM football_brief.reference_brand_assignments rba
                   JOIN football_brief.brands b ON b.id=rba.brand_id
                   WHERE rba.reference_source_id=%s AND rba.active=true
                   ORDER BY b.display_name""",
                (source_id,),
            ).fetchall()
            gates = conn.execute(
                """SELECT DISTINCT ON (gate) * FROM football_brief.reference_approval_gates
                   WHERE reference_source_id=%s ORDER BY gate, version DESC, created_at DESC""",
                (source_id,),
            ).fetchall()
            links = conn.execute(
                """SELECT ril.*, pc.title AS idea_title, pc.stage AS idea_stage
                   FROM football_brief.research_idea_links ril
                   JOIN football_brief.portfolio_content pc ON pc.id=ril.portfolio_content_id
                   WHERE ril.reference_source_id=%s ORDER BY ril.created_at DESC""",
                (source_id,),
            ).fetchall()
        return {
            "ok": True,
            "source": dict(source),
            "jobs": [dict(row) for row in jobs],
            "artifacts": [dict(row) for row in artifacts],
            "brand_assignments": [dict(row) for row in assignments],
            "gates": [dict(row) for row in gates],
            "idea_links": [dict(row) for row in links],
        }

    def record_job_progress(
        self,
        job_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        target_status = str(payload["status"])
        with self.database.transaction() as conn:
            current = conn.execute(
                "SELECT * FROM football_brief.reference_ingestion_jobs WHERE id=%s FOR UPDATE",
                (job_id,),
            ).fetchone()
            if not current:
                return {"ok": False, "error": "reference_job_not_found"}
            validate_job_transition(current["status"], target_status)
            terminal = target_status in {"succeeded", "failed", "cancelled"}
            progress = int(payload.get("progress_percent", current["progress_percent"]))
            if target_status == "succeeded":
                progress = 100
            job = conn.execute(
                """UPDATE football_brief.reference_ingestion_jobs SET
                     status=%s, stage=%s, progress_percent=%s, worker_label=%s,
                     error_code=%s, sanitized_error=%s,
                     started_at=CASE WHEN %s='running' THEN COALESCE(started_at,now()) ELSE started_at END,
                     finished_at=CASE WHEN %s THEN now() ELSE NULL END
                   WHERE id=%s RETURNING *""",
                (
                    target_status,
                    payload.get("stage", current["stage"]),
                    progress,
                    payload.get("worker_label", current["worker_label"]),
                    payload.get("error_code"),
                    sanitize_diagnostic(payload.get("error")),
                    target_status,
                    terminal,
                    job_id,
                ),
            ).fetchone()
            conn.execute(
                "UPDATE football_brief.reference_sources SET status=%s WHERE id=%s",
                (SOURCE_STATUS_BY_JOB[target_status], current["reference_source_id"]),
            )
        return {"ok": True, "job": dict(job)}

    def register_artifact(
        self,
        source_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        kind = str(payload["artifact_kind"])
        if kind not in ARTIFACT_KINDS:
            return {"ok": False, "error": "unsupported_review_artifact"}
        locator = validate_local_locator(str(payload["local_locator"]))
        if payload.get("contains_source_media"):
            return {"ok": False, "error": "source_media_artifacts_forbidden"}
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.reference_artifacts
                   (reference_source_id, ingestion_job_id, artifact_kind, version,
                    local_locator, sha256, mime_type, summary)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT (reference_source_id, artifact_kind, version) DO UPDATE SET
                     ingestion_job_id=EXCLUDED.ingestion_job_id,
                     local_locator=EXCLUDED.local_locator, sha256=EXCLUDED.sha256,
                     mime_type=EXCLUDED.mime_type, summary=EXCLUDED.summary
                   RETURNING *""",
                (
                    source_id,
                    payload.get("job_id"),
                    kind,
                    payload.get("version", 1),
                    locator,
                    payload["sha256"],
                    payload["mime_type"],
                    json.dumps(sanitize_review_metadata(payload.get("summary", {}))),
                ),
            ).fetchone()
        return {"ok": True, "artifact": dict(row)}

    def assign_brand(
        self,
        source_id: UUID,
        *,
        brand_id: UUID,
        assigned_by: str,
        rationale: str | None,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.reference_brand_assignments
                   (reference_source_id, brand_id, assigned_by, rationale)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (reference_source_id, brand_id) WHERE active=true
                   DO UPDATE SET assigned_by=EXCLUDED.assigned_by, rationale=EXCLUDED.rationale
                   RETURNING *""",
                (source_id, brand_id, assigned_by, rationale),
            ).fetchone()
        return {"ok": True, "assignment": dict(row)}

    def decide_gate(
        self,
        source_id: UUID,
        payload: dict[str, Any],
        *,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            version_row = conn.execute(
                """SELECT COALESCE(MAX(version),0)+1 AS version
                   FROM football_brief.reference_approval_gates
                   WHERE reference_source_id=%s AND gate=%s""",
                (source_id, payload["gate"]),
            ).fetchone()
            row = conn.execute(
                """INSERT INTO football_brief.reference_approval_gates
                   (reference_source_id, gate, decision, version, reviewer,
                    rationale, evidence_digest)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    source_id,
                    payload["gate"],
                    payload["decision"],
                    version_row["version"],
                    reviewer,
                    payload["rationale"],
                    payload["evidence_digest"],
                ),
            ).fetchone()
        return {"ok": True, "gate": dict(row)}

    def link_idea(
        self,
        source_id: UUID,
        payload: dict[str, Any],
        *,
        created_by: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            gate_rows = conn.execute(
                """SELECT DISTINCT ON (gate) gate, decision
                   FROM football_brief.reference_approval_gates
                   WHERE reference_source_id=%s AND gate IN ('rights','originality')
                   ORDER BY gate, version DESC, created_at DESC""",
                (source_id,),
            ).fetchall()
            gates = {row["gate"]: row["decision"] for row in gate_rows}
            missing = [gate for gate in ("rights", "originality") if gates.get(gate) != "approved"]
            if missing:
                return {"ok": False, "error": "reference_gates_required", "missing": missing}
            row = conn.execute(
                """INSERT INTO football_brief.research_idea_links
                   (reference_source_id, portfolio_content_id, relationship,
                    pattern_ids, transformation_note, created_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (reference_source_id, portfolio_content_id, relationship)
                   DO UPDATE SET pattern_ids=EXCLUDED.pattern_ids,
                     transformation_note=EXCLUDED.transformation_note,
                     created_by=EXCLUDED.created_by
                   RETURNING *""",
                (
                    source_id,
                    payload["portfolio_content_id"],
                    payload["relationship"],
                    json.dumps(payload.get("pattern_ids", [])),
                    payload["transformation_note"],
                    created_by,
                ),
            ).fetchone()
        return {"ok": True, "link": dict(row)}
