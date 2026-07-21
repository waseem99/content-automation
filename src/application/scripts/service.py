from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from src.application.scripts.adapters import (
    DeterministicScriptAdapter,
    LocalHttpScriptAdapter,
    estimated_duration_seconds,
    generate_with_fallback,
    word_count,
)
from src.application.scripts.models import (
    ClaimSourceDraft,
    ClaimSupportStatus,
    ClaimType,
    ScriptAdapterMode,
    ScriptDecision,
    ScriptDraft,
    ScriptGenerateRequest,
    ScriptReviewActionRequest,
    ScriptVersionStatus,
    SourceDraft,
    SourceSupportUpdateRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class ScriptReviewError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class ScriptReviewService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def initialize(
        self,
        *,
        content_id: UUID,
        request: ScriptGenerateRequest,
        actor: str,
    ) -> dict[str, Any]:
        if request.adapter_mode == ScriptAdapterMode.MANUAL:
            raise ScriptReviewError("manual_script_requires_replace")
        context = self._context(content_id)
        fallback = DeterministicScriptAdapter()
        if request.adapter_mode == ScriptAdapterMode.LOCAL_MODEL:
            primary = LocalHttpScriptAdapter(
                endpoint=request.local_endpoint or "http://127.0.0.1:11434",
                model_id=request.local_model_id or "",
                timeout_seconds=request.local_timeout_seconds,
            )
        else:
            primary = fallback
        draft, adapter_evidence = generate_with_fallback(
            primary=primary,
            fallback=fallback,
            context=context,
            configuration=request,
        )
        evidence = {**dict(draft.generation_evidence), **adapter_evidence}
        draft = draft.model_copy(update={"generation_evidence": evidence})
        document_id = uuid4()
        version_id = uuid4()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            content = conn.execute(
                """SELECT pc.id, pc.version, pw.id AS workflow_id, pw.current_stage,
                          pw.status AS workflow_status
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.production_workflows pw
                     ON pw.portfolio_content_id=pc.id
                   WHERE pc.id=%s
                   FOR UPDATE OF pc, pw""",
                (content_id,),
            ).fetchone()
            if not content:
                raise ScriptReviewError("content_or_workflow_not_found")
            existing = conn.execute(
                "SELECT id FROM football_brief.script_documents WHERE portfolio_content_id=%s",
                (content_id,),
            ).fetchone()
            if existing:
                return self.detail(document_id=existing["id"])
            if content["workflow_status"] != "active" or content["current_stage"] != "script_draft":
                raise ScriptReviewError(
                    "workflow_not_ready_for_script",
                    details={
                        "status": content["workflow_status"],
                        "stage": content["current_stage"],
                    },
                )
            metrics = self._draft_metrics(draft)
            conn.execute(
                """INSERT INTO football_brief.script_documents
                   (id, portfolio_content_id, production_workflow_id, current_version_id,
                    lock_version, created_by)
                   VALUES (%s,%s,%s,%s,1,%s)""",
                (document_id, content_id, content["workflow_id"], version_id, actor),
            )
            conn.execute(
                """INSERT INTO football_brief.script_versions
                   (id, script_document_id, version, basis_content_version, status,
                    platform, format, language, target_duration_seconds, words_per_minute,
                    word_count, estimated_duration_seconds, duration_tolerance_percent,
                    hook_text, cta_text, full_text, content_fingerprint, adapter_mode,
                    local_model_id, generation_evidence, created_by, last_edited_by)
                   VALUES (%s,%s,1,%s,'working',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           %s,%s,%s::jsonb,%s,%s)""",
                (
                    version_id,
                    document_id,
                    content["version"],
                    draft.platform,
                    draft.format,
                    draft.language,
                    draft.target_duration_seconds,
                    draft.words_per_minute,
                    metrics["word_count"],
                    metrics["duration"],
                    draft.duration_tolerance_percent,
                    draft.hook_text,
                    draft.cta_text,
                    metrics["full_text"],
                    metrics["fingerprint"],
                    request.adapter_mode.value,
                    request.local_model_id,
                    _json(draft.generation_evidence),
                    actor,
                    actor,
                ),
            )
            self._insert_children(conn, version_id=version_id, draft=draft)
        return self.detail(document_id=document_id)

    def detail(self, *, document_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            document = conn.execute(
                """SELECT sd.*, pc.title, pc.concept, pc.format AS content_format,
                          pc.version AS content_version, mp.brand_id, b.slug AS brand_slug,
                          b.display_name AS brand_name, sv.version AS current_version,
                          sv.status AS current_version_status
                   FROM football_brief.script_documents sd
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE sd.id=%s""",
                (document_id,),
            ).fetchone()
            if not document:
                raise ScriptReviewError("script_document_not_found")
            versions = conn.execute(
                """SELECT * FROM football_brief.script_versions
                   WHERE script_document_id=%s ORDER BY version DESC""",
                (document_id,),
            ).fetchall()
            sections = conn.execute(
                """SELECT ss.* FROM football_brief.script_sections ss
                   JOIN football_brief.script_versions sv ON sv.id=ss.script_version_id
                   WHERE sv.script_document_id=%s ORDER BY sv.version DESC, ss.sequence""",
                (document_id,),
            ).fetchall()
            scenes = conn.execute(
                """SELECT sp.* FROM football_brief.script_scene_plan_entries sp
                   JOIN football_brief.script_versions sv ON sv.id=sp.script_version_id
                   WHERE sv.script_document_id=%s ORDER BY sv.version DESC, sp.sequence""",
                (document_id,),
            ).fetchall()
            claims = conn.execute(
                """SELECT sc.* FROM football_brief.script_claims sc
                   JOIN football_brief.script_versions sv ON sv.id=sc.script_version_id
                   WHERE sv.script_document_id=%s ORDER BY sv.version DESC, sc.claim_key""",
                (document_id,),
            ).fetchall()
            sources = conn.execute(
                """SELECT ss.* FROM football_brief.script_sources ss
                   JOIN football_brief.script_versions sv ON sv.id=ss.script_version_id
                   WHERE sv.script_document_id=%s ORDER BY sv.version DESC, ss.source_key""",
                (document_id,),
            ).fetchall()
            links = conn.execute(
                """SELECT cs.* FROM football_brief.script_claim_sources cs
                   JOIN football_brief.script_versions sv ON sv.id=cs.script_version_id
                   WHERE sv.script_document_id=%s ORDER BY sv.version DESC, cs.claim_id""",
                (document_id,),
            ).fetchall()
            actions = conn.execute(
                """SELECT ra.*, u.display_name AS author_name
                   FROM football_brief.script_review_actions ra
                   JOIN football_brief.script_versions sv ON sv.id=ra.script_version_id
                   JOIN football_brief.operator_users u ON u.operator_id=ra.author_operator_id
                   WHERE sv.script_document_id=%s ORDER BY ra.created_at, ra.id""",
                (document_id,),
            ).fetchall()
            decisions = conn.execute(
                """SELECT rd.*, u.display_name AS reviewer_name
                   FROM football_brief.script_review_decisions rd
                   JOIN football_brief.operator_users u ON u.operator_id=rd.reviewer_operator_id
                   WHERE rd.script_document_id=%s ORDER BY rd.created_at, rd.id""",
                (document_id,),
            ).fetchall()
        return {
            "ok": True,
            "document": dict(document),
            "versions": [dict(row) for row in versions],
            "sections": [dict(row) for row in sections],
            "scenes": [dict(row) for row in scenes],
            "claims": [dict(row) for row in claims],
            "sources": [dict(row) for row in sources],
            "claim_sources": [dict(row) for row in links],
            "review_actions": [dict(row) for row in actions],
            "decisions": [dict(row) for row in decisions],
        }

    def document_for_content(self, *, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id FROM football_brief.script_documents WHERE portfolio_content_id=%s",
                (content_id,),
            ).fetchone()
        if not row:
            raise ScriptReviewError("script_document_not_found")
        return self.detail(document_id=row["id"])

    def replace_working_draft(
        self,
        *,
        document_id: UUID,
        expected_lock_version: int,
        draft: ScriptDraft,
        actor: str,
    ) -> dict[str, Any]:
        metrics = self._draft_metrics(draft)
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, expected_lock_version)
            if row["version_status"] != ScriptVersionStatus.WORKING.value:
                raise ScriptReviewError("script_version_not_working")
            version_id = row["current_version_id"]
            self._clear_children(conn, version_id=version_id)
            conn.execute(
                """UPDATE football_brief.script_versions
                   SET platform=%s, format=%s, language=%s, target_duration_seconds=%s,
                       words_per_minute=%s, word_count=%s, estimated_duration_seconds=%s,
                       duration_tolerance_percent=%s, hook_text=%s, cta_text=%s,
                       full_text=%s, content_fingerprint=%s, adapter_mode='manual',
                       local_model_id=NULL, generation_evidence=%s::jsonb, last_edited_by=%s
                   WHERE id=%s""",
                (
                    draft.platform,
                    draft.format,
                    draft.language,
                    draft.target_duration_seconds,
                    draft.words_per_minute,
                    metrics["word_count"],
                    metrics["duration"],
                    draft.duration_tolerance_percent,
                    draft.hook_text,
                    draft.cta_text,
                    metrics["full_text"],
                    metrics["fingerprint"],
                    _json({**dict(draft.generation_evidence), "manual_edit": True}),
                    actor,
                    version_id,
                ),
            )
            self._insert_children(conn, version_id=version_id, draft=draft)
            self._advance_lock(conn, document_id=document_id, expected_lock=expected_lock_version)
        return self.detail(document_id=document_id)

    def update_source_support(
        self,
        *,
        document_id: UUID,
        request: SourceSupportUpdateRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, request.expected_lock_version)
            if row["version_status"] != ScriptVersionStatus.WORKING.value:
                raise ScriptReviewError("script_version_not_working")
            version_id = row["current_version_id"]
            claims = conn.execute(
                "SELECT id, claim_key, claim_type FROM football_brief.script_claims WHERE script_version_id=%s",
                (version_id,),
            ).fetchall()
            claim_map = {str(item["claim_key"]): item for item in claims}
            unknown_supported = sorted(set(request.supported_claim_keys) - set(claim_map))
            if unknown_supported:
                raise ScriptReviewError("unknown_supported_claims", details={"claim_keys": unknown_supported})
            conn.execute(
                "DELETE FROM football_brief.script_claim_sources WHERE script_version_id=%s",
                (version_id,),
            )
            conn.execute(
                "DELETE FROM football_brief.script_sources WHERE script_version_id=%s",
                (version_id,),
            )
            source_map = self._insert_sources(conn, version_id=version_id, sources=request.sources)
            self._insert_claim_links(
                conn,
                version_id=version_id,
                links=request.claim_sources,
                claim_map={key: value["id"] for key, value in claim_map.items()},
                source_map=source_map,
            )
            conn.execute(
                """UPDATE football_brief.script_claims
                   SET support_status=CASE
                         WHEN claim_key = ANY(%s::text[]) THEN 'supported'
                         WHEN claim_type='factual' THEN 'needs_source'
                         ELSE support_status
                       END
                   WHERE script_version_id=%s""",
                (request.supported_claim_keys, version_id),
            )
            conn.execute(
                "UPDATE football_brief.script_versions SET last_edited_by=%s WHERE id=%s",
                (actor, version_id),
            )
            self._advance_lock(
                conn,
                document_id=document_id,
                expected_lock=request.expected_lock_version,
            )
        return self.detail(document_id=document_id)

    def submit(
        self,
        *,
        document_id: UUID,
        expected_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, expected_lock_version)
            if row["version_status"] != ScriptVersionStatus.WORKING.value:
                raise ScriptReviewError("script_version_not_working")
            aggregate = self._aggregate_current(conn, row["current_version_id"])
            conn.execute(
                """UPDATE football_brief.script_versions
                   SET status='in_review', word_count=%s, estimated_duration_seconds=%s,
                       hook_text=%s, cta_text=%s, full_text=%s, content_fingerprint=%s,
                       last_edited_by=%s, submitted_at=now()
                   WHERE id=%s""",
                (
                    aggregate["word_count"],
                    aggregate["duration"],
                    aggregate["hook_text"],
                    aggregate["cta_text"],
                    aggregate["full_text"],
                    aggregate["fingerprint"],
                    actor,
                    row["current_version_id"],
                ),
            )
            self._advance_lock(conn, document_id=document_id, expected_lock=expected_lock_version)
        return self.detail(document_id=document_id)

    def add_review_action(
        self,
        *,
        document_id: UUID,
        expected_lock_version: int,
        request: ScriptReviewActionRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, expected_lock_version)
            if str(row["current_version_id"]) != str(request.script_version_id):
                raise ScriptReviewError("stale_script_version")
            if row["version_status"] != ScriptVersionStatus.IN_REVIEW.value:
                raise ScriptReviewError("script_version_not_in_review")
            action = conn.execute(
                """INSERT INTO football_brief.script_review_actions
                   (script_version_id, script_section_id, claim_id, action_type,
                    body, suggested_text, author_operator_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    request.script_version_id,
                    request.script_section_id,
                    request.claim_id,
                    request.action_type.value,
                    request.body,
                    request.suggested_text,
                    actor,
                ),
            ).fetchone()
            self._advance_lock(conn, document_id=document_id, expected_lock=expected_lock_version)
        return {"ok": True, "action": dict(action), **self.detail(document_id=document_id)}

    def resolve_review_action(
        self,
        *,
        document_id: UUID,
        action_id: UUID,
        expected_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, expected_lock_version)
            action = conn.execute(
                """SELECT ra.* FROM football_brief.script_review_actions ra
                   JOIN football_brief.script_versions sv ON sv.id=ra.script_version_id
                   WHERE ra.id=%s AND sv.script_document_id=%s
                   FOR UPDATE OF ra""",
                (action_id, document_id),
            ).fetchone()
            if not action:
                raise ScriptReviewError("script_review_action_not_found")
            if str(action["script_version_id"]) != str(row["current_version_id"]):
                raise ScriptReviewError("stale_script_review_action")
            resolved = conn.execute(
                """UPDATE football_brief.script_review_actions
                   SET resolved_by_operator_id=%s, resolved_at=now()
                   WHERE id=%s AND resolved_at IS NULL RETURNING *""",
                (actor, action_id),
            ).fetchone()
            if not resolved:
                raise ScriptReviewError("script_review_action_already_resolved")
            self._advance_lock(conn, document_id=document_id, expected_lock=expected_lock_version)
        return {"ok": True, "action": dict(resolved), **self.detail(document_id=document_id)}

    def decide(
        self,
        *,
        document_id: UUID,
        expected_lock_version: int,
        decision: ScriptDecision,
        rationale: str,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            row = self._locked(conn, document_id, expected_lock_version)
            if row["version_status"] != ScriptVersionStatus.IN_REVIEW.value:
                raise ScriptReviewError("script_version_not_in_review")
            conn.execute(
                """INSERT INTO football_brief.script_review_decisions
                   (script_document_id, script_version_id, decision,
                    reviewer_operator_id, rationale, document_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    document_id,
                    row["current_version_id"],
                    decision.value,
                    reviewer,
                    rationale,
                    expected_lock_version,
                ),
            )
            conn.execute(
                """UPDATE football_brief.script_versions
                   SET status=%s, decided_at=now()
                   WHERE id=%s""",
                (decision.value, row["current_version_id"]),
            )
            self._advance_lock(conn, document_id=document_id, expected_lock=expected_lock_version)
        return self.detail(document_id=document_id)

    def revise(
        self,
        *,
        document_id: UUID,
        expected_lock_version: int,
        reason: str,
        actor: str,
    ) -> dict[str, Any]:
        new_version_id = uuid4()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, document_id, expected_lock_version)
            if row["version_status"] not in {
                ScriptVersionStatus.CHANGES_REQUESTED.value,
                ScriptVersionStatus.REJECTED.value,
            }:
                raise ScriptReviewError(
                    "script_version_not_revisable",
                    details={"status": row["version_status"]},
                )
            old_version_id = row["current_version_id"]
            old = conn.execute(
                "SELECT * FROM football_brief.script_versions WHERE id=%s",
                (old_version_id,),
            ).fetchone()
            next_version = int(old["version"]) + 1
            evidence = dict(old["generation_evidence"] or {})
            evidence.update({"revision_from": str(old_version_id), "revision_reason": reason})
            conn.execute(
                """INSERT INTO football_brief.script_versions
                   (id, script_document_id, version, parent_version_id, basis_content_version,
                    status, platform, format, language, target_duration_seconds,
                    words_per_minute, word_count, estimated_duration_seconds,
                    duration_tolerance_percent, hook_text, cta_text, full_text,
                    content_fingerprint, adapter_mode, local_model_id, generation_evidence,
                    revision_reason, created_by, last_edited_by)
                   VALUES (%s,%s,%s,%s,%s,'working',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                           %s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (
                    new_version_id,
                    document_id,
                    next_version,
                    old_version_id,
                    old["basis_content_version"],
                    old["platform"],
                    old["format"],
                    old["language"],
                    old["target_duration_seconds"],
                    old["words_per_minute"],
                    old["word_count"],
                    old["estimated_duration_seconds"],
                    old["duration_tolerance_percent"],
                    old["hook_text"],
                    old["cta_text"],
                    old["full_text"],
                    old["content_fingerprint"],
                    old["adapter_mode"],
                    old["local_model_id"],
                    _json(evidence),
                    reason,
                    actor,
                    actor,
                ),
            )
            self._copy_children(
                conn,
                old_version_id=old_version_id,
                new_version_id=new_version_id,
            )
            updated = conn.execute(
                """UPDATE football_brief.script_documents
                   SET current_version_id=%s, lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s RETURNING id""",
                (new_version_id, document_id, expected_lock_version),
            ).fetchone()
            if not updated:
                raise ScriptReviewError("script_document_conflict")
        return self.detail(document_id=document_id)

    def _context(self, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id, pc.title, pc.concept, pc.format, pc.version,
                          mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                          b.niche, pw.id AS workflow_id, pw.current_stage, pw.status AS workflow_status,
                          COALESCE(pinned.id, active.id) AS brand_profile_id,
                          COALESCE(pinned.version, active.version) AS brand_profile_version,
                          COALESCE(pinned.audience, active.audience, '{}'::jsonb) AS audience,
                          COALESCE(pinned.tone, active.tone, '') AS tone,
                          COALESCE(pinned.content_restrictions, active.content_restrictions, '{}'::jsonb)
                            AS content_restrictions
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   LEFT JOIN football_brief.brand_profiles pinned ON pinned.id=pc.brand_profile_id
                   LEFT JOIN football_brief.brand_profiles active
                     ON active.brand_id=mp.brand_id AND active.status='active'
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise ScriptReviewError("content_or_workflow_not_found")
        if row["brand_profile_id"] is None:
            raise ScriptReviewError("active_brand_profile_required")
        return dict(row)

    def _locked(self, conn, document_id: UUID, expected_lock: int):
        row = conn.execute(
            """SELECT sd.*, sv.status AS version_status, sv.version AS version_number,
                      sv.last_edited_by, pc.version AS current_content_version,
                      mp.brand_id, pw.current_stage, pw.status AS workflow_status
               FROM football_brief.script_documents sd
               JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
               JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               JOIN football_brief.production_workflows pw ON pw.id=sd.production_workflow_id
               WHERE sd.id=%s FOR UPDATE OF sd, sv""",
            (document_id,),
        ).fetchone()
        if not row:
            raise ScriptReviewError("script_document_not_found")
        if int(row["lock_version"]) != expected_lock:
            raise ScriptReviewError(
                "script_document_conflict",
                details={"expected": expected_lock, "current": int(row["lock_version"])},
            )
        return row

    @staticmethod
    def _advance_lock(conn, *, document_id: UUID, expected_lock: int) -> None:
        updated = conn.execute(
            """UPDATE football_brief.script_documents
               SET lock_version=lock_version+1
               WHERE id=%s AND lock_version=%s RETURNING id""",
            (document_id, expected_lock),
        ).fetchone()
        if not updated:
            raise ScriptReviewError("script_document_conflict")

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (operator_id,),
        ).fetchone()
        if not row or not row["active"]:
            raise ScriptReviewError("operator_inactive_or_missing")

    @staticmethod
    def _draft_metrics(draft: ScriptDraft) -> dict[str, Any]:
        full_text = "\n\n".join(item.text.strip() for item in draft.sections)
        total_words = sum(word_count(item.text) for item in draft.sections)
        duration = round(
            sum(estimated_duration_seconds(item.text, draft.words_per_minute) for item in draft.sections),
            3,
        )
        return {
            "word_count": total_words,
            "duration": duration,
            "full_text": full_text,
            "fingerprint": _fingerprint(draft.model_dump(mode="json")),
        }

    def _insert_children(self, conn, *, version_id: UUID, draft: ScriptDraft) -> None:
        section_map: dict[str, UUID] = {}
        for sequence, section in enumerate(draft.sections, start=1):
            section_id = uuid4()
            section_map[section.section_key] = section_id
            conn.execute(
                """INSERT INTO football_brief.script_sections
                   (id, script_version_id, sequence, section_key, section_type, text,
                    target_duration_seconds, estimated_duration_seconds, word_count)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    section_id,
                    version_id,
                    sequence,
                    section.section_key,
                    section.section_type,
                    section.text,
                    section.target_duration_seconds,
                    estimated_duration_seconds(section.text, draft.words_per_minute),
                    word_count(section.text),
                ),
            )
        for sequence, scene in enumerate(draft.scenes, start=1):
            conn.execute(
                """INSERT INTO football_brief.script_scene_plan_entries
                   (script_version_id, script_section_id, sequence, scene_key,
                    narration_text, visual_brief, on_screen_text,
                    target_duration_seconds, source_requirements)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    version_id,
                    section_map[scene.section_key],
                    sequence,
                    scene.scene_key,
                    scene.narration_text,
                    scene.visual_brief,
                    scene.on_screen_text,
                    scene.target_duration_seconds,
                    _json(scene.source_requirements),
                ),
            )
        claim_map: dict[str, UUID] = {}
        for claim in draft.claims:
            claim_id = uuid4()
            claim_map[claim.claim_key] = claim_id
            conn.execute(
                """INSERT INTO football_brief.script_claims
                   (id, script_version_id, script_section_id, claim_key, claim_text,
                    claim_type, confidence, sensitivity, support_status, wording_limitations)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    claim_id,
                    version_id,
                    section_map[claim.section_key],
                    claim.claim_key,
                    claim.claim_text,
                    claim.claim_type.value,
                    claim.confidence,
                    claim.sensitivity.value,
                    claim.support_status.value,
                    claim.wording_limitations,
                ),
            )
        source_map = self._insert_sources(conn, version_id=version_id, sources=draft.sources)
        self._insert_claim_links(
            conn,
            version_id=version_id,
            links=draft.claim_sources,
            claim_map=claim_map,
            source_map=source_map,
        )

    @staticmethod
    def _insert_sources(conn, *, version_id: UUID, sources: list[SourceDraft]) -> dict[str, UUID]:
        source_map: dict[str, UUID] = {}
        for source in sources:
            source_id = uuid4()
            source_map[source.source_key] = source_id
            conn.execute(
                """INSERT INTO football_brief.script_sources
                   (id, script_version_id, source_key, source_type, title, publisher,
                    canonical_url, published_on, quality_score, rights_declaration,
                    permitted_use, evidence_digest, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    source_id,
                    version_id,
                    source.source_key,
                    source.source_type.value,
                    source.title,
                    source.publisher,
                    source.canonical_url,
                    source.published_on,
                    source.quality_score,
                    source.rights_declaration.value,
                    source.permitted_use,
                    source.evidence_digest,
                    source.notes,
                ),
            )
        return source_map

    @staticmethod
    def _insert_claim_links(
        conn,
        *,
        version_id: UUID,
        links: list[ClaimSourceDraft],
        claim_map: dict[str, UUID],
        source_map: dict[str, UUID],
    ) -> None:
        for link in links:
            if link.claim_key not in claim_map:
                raise ScriptReviewError("unknown_claim_key", details={"claim_key": link.claim_key})
            if link.source_key not in source_map:
                raise ScriptReviewError("unknown_source_key", details={"source_key": link.source_key})
            conn.execute(
                """INSERT INTO football_brief.script_claim_sources
                   (script_version_id, claim_id, source_id, support_type, locator, support_note)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    version_id,
                    claim_map[link.claim_key],
                    source_map[link.source_key],
                    link.support_type.value,
                    link.locator,
                    link.support_note,
                ),
            )

    @staticmethod
    def _clear_children(conn, *, version_id: UUID) -> None:
        conn.execute("DELETE FROM football_brief.script_claim_sources WHERE script_version_id=%s", (version_id,))
        conn.execute("DELETE FROM football_brief.script_claims WHERE script_version_id=%s", (version_id,))
        conn.execute("DELETE FROM football_brief.script_scene_plan_entries WHERE script_version_id=%s", (version_id,))
        conn.execute("DELETE FROM football_brief.script_sources WHERE script_version_id=%s", (version_id,))
        conn.execute("DELETE FROM football_brief.script_sections WHERE script_version_id=%s", (version_id,))

    @staticmethod
    def _aggregate_current(conn, version_id: UUID) -> dict[str, Any]:
        sections = conn.execute(
            """SELECT * FROM football_brief.script_sections
               WHERE script_version_id=%s ORDER BY sequence""",
            (version_id,),
        ).fetchall()
        if not sections:
            raise ScriptReviewError("script_sections_required")
        scenes = conn.execute(
            "SELECT * FROM football_brief.script_scene_plan_entries WHERE script_version_id=%s ORDER BY sequence",
            (version_id,),
        ).fetchall()
        claims = conn.execute(
            "SELECT * FROM football_brief.script_claims WHERE script_version_id=%s ORDER BY claim_key",
            (version_id,),
        ).fetchall()
        sources = conn.execute(
            "SELECT * FROM football_brief.script_sources WHERE script_version_id=%s ORDER BY source_key",
            (version_id,),
        ).fetchall()
        links = conn.execute(
            "SELECT * FROM football_brief.script_claim_sources WHERE script_version_id=%s ORDER BY claim_id, source_id",
            (version_id,),
        ).fetchall()
        full_text = "\n\n".join(str(item["text"]).strip() for item in sections)
        hook = next((str(item["text"]) for item in sections if item["section_type"] == "hook"), "")
        cta = next((str(item["text"]) for item in sections if item["section_type"] == "cta"), "")
        return {
            "word_count": sum(int(item["word_count"]) for item in sections),
            "duration": round(sum(float(item["estimated_duration_seconds"]) for item in sections), 3),
            "hook_text": hook,
            "cta_text": cta,
            "full_text": full_text,
            "fingerprint": _fingerprint({
                "sections": [dict(item) for item in sections],
                "scenes": [dict(item) for item in scenes],
                "claims": [dict(item) for item in claims],
                "sources": [dict(item) for item in sources],
                "links": [dict(item) for item in links],
            }),
        }

    @staticmethod
    def _copy_children(conn, *, old_version_id: UUID, new_version_id: UUID) -> None:
        section_rows = conn.execute(
            "SELECT * FROM football_brief.script_sections WHERE script_version_id=%s ORDER BY sequence",
            (old_version_id,),
        ).fetchall()
        section_map: dict[UUID, UUID] = {}
        for row in section_rows:
            new_id = uuid4()
            section_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_sections
                   (id, script_version_id, sequence, section_key, section_type, text,
                    target_duration_seconds, estimated_duration_seconds, word_count)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id, new_version_id, row["sequence"], row["section_key"], row["section_type"],
                    row["text"], row["target_duration_seconds"], row["estimated_duration_seconds"],
                    row["word_count"],
                ),
            )
        for row in conn.execute(
            "SELECT * FROM football_brief.script_scene_plan_entries WHERE script_version_id=%s ORDER BY sequence",
            (old_version_id,),
        ).fetchall():
            conn.execute(
                """INSERT INTO football_brief.script_scene_plan_entries
                   (script_version_id, script_section_id, sequence, scene_key,
                    narration_text, visual_brief, on_screen_text,
                    target_duration_seconds, source_requirements)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_version_id, section_map[row["script_section_id"]], row["sequence"],
                    row["scene_key"], row["narration_text"], row["visual_brief"],
                    row["on_screen_text"], row["target_duration_seconds"], row["source_requirements"],
                ),
            )
        claim_map: dict[UUID, UUID] = {}
        for row in conn.execute(
            "SELECT * FROM football_brief.script_claims WHERE script_version_id=%s ORDER BY claim_key",
            (old_version_id,),
        ).fetchall():
            new_id = uuid4()
            claim_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_claims
                   (id, script_version_id, script_section_id, claim_key, claim_text,
                    claim_type, confidence, sensitivity, support_status, wording_limitations)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id, new_version_id, section_map[row["script_section_id"]], row["claim_key"],
                    row["claim_text"], row["claim_type"], row["confidence"], row["sensitivity"],
                    row["support_status"], row["wording_limitations"],
                ),
            )
        source_map: dict[UUID, UUID] = {}
        for row in conn.execute(
            "SELECT * FROM football_brief.script_sources WHERE script_version_id=%s ORDER BY source_key",
            (old_version_id,),
        ).fetchall():
            new_id = uuid4()
            source_map[row["id"]] = new_id
            conn.execute(
                """INSERT INTO football_brief.script_sources
                   (id, script_version_id, source_key, source_type, title, publisher,
                    canonical_url, published_on, accessed_at, quality_score,
                    rights_declaration, permitted_use, evidence_digest, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    new_id, new_version_id, row["source_key"], row["source_type"], row["title"],
                    row["publisher"], row["canonical_url"], row["published_on"], row["accessed_at"],
                    row["quality_score"], row["rights_declaration"], row["permitted_use"],
                    row["evidence_digest"], row["notes"],
                ),
            )
        for row in conn.execute(
            "SELECT * FROM football_brief.script_claim_sources WHERE script_version_id=%s",
            (old_version_id,),
        ).fetchall():
            conn.execute(
                """INSERT INTO football_brief.script_claim_sources
                   (script_version_id, claim_id, source_id, support_type, locator, support_note)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    new_version_id, claim_map[row["claim_id"]], source_map[row["source_id"]],
                    row["support_type"], row["locator"], row["support_note"],
                ),
            )
