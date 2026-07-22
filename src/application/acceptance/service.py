from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from src.application.acceptance.models import (
    DefectOpenRequest,
    DefectResolveRequest,
    EvidenceCategory,
    LiveDeliveryEvidenceRequest,
    OperationsEvidenceRequest,
    PilotCreateRequest,
    PilotItemRequest,
    SignoffRequest,
)

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class AcceptancePilotError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


CONTENT_CATEGORIES = tuple(
    category
    for category in EvidenceCategory
    if category not in {
        EvidenceCategory.BACKUP_RESTORE,
        EvidenceCategory.WORKER_RESTART,
        EvidenceCategory.RUNBOOK_VALIDATION,
    }
)


class AcceptancePilotService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def create(self, request: PilotCreateRequest, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (request.pilot_key,))
            current = conn.execute(
                """SELECT * FROM football_brief.acceptance_pilots
                   WHERE pilot_key=%s ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (request.pilot_key,),
            ).fetchone()
            if current and current["status"] in {"draft", "running", "blocked"}:
                return {"ok": True, "pilot": dict(current), "reused": True}
            version = int(current["version"]) + 1 if current else 1
            pilot = conn.execute(
                """INSERT INTO football_brief.acceptance_pilots
                   (pilot_key,version,parent_pilot_id,scope,acceptance_policy,created_by)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s) RETURNING *""",
                (
                    request.pilot_key,
                    version,
                    current["id"] if current else None,
                    _json(request.canonical_scope()),
                    _json(request.acceptance_policy),
                    actor,
                ),
            ).fetchone()
            self._event(conn, pilot["id"], None, "pilot_created", actor, {"version": version})
        return {"ok": True, "pilot": dict(pilot), "reused": False}

    def add_item(
        self,
        *,
        pilot_id: UUID,
        request: PilotItemRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            content = conn.execute(
                """SELECT pc.id,pc.version,mp.brand_id,b.slug
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   WHERE pc.id=%s""",
                (request.portfolio_content_id,),
            ).fetchone()
            if not content:
                raise AcceptancePilotError("pilot_content_not_found")
            item = conn.execute(
                """INSERT INTO football_brief.acceptance_pilot_items
                   (pilot_id,brand_id,portfolio_content_id,content_version,production_mode,
                    required_revision_stages,live_delivery_evidence_required,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (pilot_id,portfolio_content_id,content_version) DO NOTHING
                   RETURNING *""",
                (
                    pilot_id,
                    content["brand_id"],
                    request.portfolio_content_id,
                    request.content_version,
                    request.production_mode.value,
                    list(request.required_revision_stages),
                    request.live_delivery_evidence_required,
                    actor,
                ),
            ).fetchone()
            if item is None:
                item = conn.execute(
                    """SELECT * FROM football_brief.acceptance_pilot_items
                       WHERE pilot_id=%s AND portfolio_content_id=%s AND content_version=%s""",
                    (pilot_id, request.portfolio_content_id, request.content_version),
                ).fetchone()
            self._event(
                conn,
                pilot_id,
                item["id"],
                "item_added",
                actor,
                {"brand_slug": content["slug"], "production_mode": request.production_mode.value},
            )
        return {"ok": True, "item": dict(item)}

    def start(self, *, pilot_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='running',started_at=now()
                   WHERE id=%s AND status='draft' RETURNING *""",
                (pilot_id,),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_startable")
            self._event(conn, pilot_id, None, "pilot_started", actor, {})
        return {"ok": True, "pilot": dict(pilot)}

    def collect_item(self, *, item_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_any_role(conn, actor, {"admin", "reviewer"})
            context = self._item_context(conn, item_id)
            if not context:
                raise AcceptancePilotError("pilot_item_not_found")
            checks = self._system_checks(conn, context)
            evidence_rows: list[dict[str, Any]] = []
            for category in CONTENT_CATEGORIES:
                result = checks[category]
                row = self._record_evidence(
                    conn,
                    item_id=item_id,
                    category=category,
                    result=result,
                    actor=actor,
                )
                evidence_rows.append(row)
            staging = checks[EvidenceCategory.STAGING_DELIVERY]
            staging_id = staging["details"].get("delivery_request_id") if staging["passed"] else None
            passed = all(checks[category]["passed"] for category in CONTENT_CATEGORIES)
            item = conn.execute(
                """UPDATE football_brief.acceptance_pilot_items
                   SET status=%s,staging_delivery_request_id=COALESCE(%s,staging_delivery_request_id)
                   WHERE id=%s RETURNING *""",
                ("passed" if passed else "blocked", staging_id, item_id),
            ).fetchone()
            self._event(
                conn,
                context["pilot_id"],
                item_id,
                "item_evaluated",
                actor,
                {
                    "passed": passed,
                    "passed_categories": sum(1 for value in checks.values() if value["passed"]),
                    "required_categories": len(CONTENT_CATEGORIES),
                },
            )
        return {"ok": passed, "item": dict(item), "evidence": evidence_rows}

    def record_operations_evidence(
        self,
        *,
        item_id: UUID,
        request: OperationsEvidenceRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            context = self._item_context(conn, item_id)
            if not context:
                raise AcceptancePilotError("pilot_item_not_found")
            result = self._resolve_operations_evidence(conn, request)
            row = self._record_evidence(
                conn,
                item_id=item_id,
                category=request.category,
                result=result,
                actor=actor,
            )
        return {"ok": result["passed"], "evidence": row}

    def open_defect(
        self,
        *,
        pilot_id: UUID,
        request: DefectOpenRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_any_role(conn, actor, {"admin", "reviewer"})
            row = conn.execute(
                """INSERT INTO football_brief.acceptance_pilot_defects
                   (pilot_id,pilot_item_id,defect_key,severity,summary,evidence,opened_by)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                (
                    pilot_id,
                    request.pilot_item_id,
                    request.defect_key,
                    request.severity.value,
                    request.summary,
                    _json(request.evidence),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """UPDATE football_brief.acceptance_pilots SET status='blocked'
                   WHERE id=%s AND status='running'""",
                (pilot_id,),
            )
            self._event(conn, pilot_id, request.pilot_item_id, "defect_opened", actor, {"defect_id": str(row["id"])})
        return {"ok": True, "defect": dict(row)}

    def resolve_defect(
        self,
        *,
        defect_id: UUID,
        request: DefectResolveRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_any_role(conn, actor, {"admin", "reviewer"})
            row = conn.execute(
                """UPDATE football_brief.acceptance_pilot_defects
                   SET status=%s,resolved_by=%s,resolved_at=now(),resolution=%s
                   WHERE id=%s AND status='open' RETURNING *""",
                (request.status.value, actor, request.resolution, defect_id),
            ).fetchone()
            if not row:
                raise AcceptancePilotError("pilot_defect_not_open")
            self._event(conn, row["pilot_id"], row["pilot_item_id"], "defect_resolved", actor, {"defect_id": str(defect_id)})
        return {"ok": True, "defect": dict(row)}

    def signoff(
        self,
        *,
        pilot_id: UUID,
        request: SignoffRequest,
        actor: str,
    ) -> dict[str, Any]:
        snapshot = self.detail(pilot_id=pilot_id)
        digest = _digest(snapshot)
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.acceptance_pilot_signoffs
                   (pilot_id,signoff_role,decision,rationale,operator_id,evidence_snapshot,evidence_digest)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                (
                    pilot_id,
                    request.role.value,
                    request.decision.value,
                    request.rationale,
                    actor,
                    _json(snapshot),
                    digest,
                ),
            ).fetchone()
            self._event(conn, pilot_id, None, "signoff_recorded", actor, {"role": request.role.value, "decision": request.decision.value})
        return {"ok": request.decision.value == "approved", "signoff": dict(row)}

    def record_live_delivery(
        self,
        *,
        pilot_id: UUID,
        request: LiveDeliveryEvidenceRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            row = conn.execute(
                """INSERT INTO football_brief.acceptance_live_delivery_evidence
                   (pilot_id,pilot_item_id,final_release_id,platform,platform_reference,
                    result_status,external_response_digest,evidence,recorded_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                (
                    pilot_id,
                    request.pilot_item_id,
                    request.final_release_id,
                    request.platform,
                    request.platform_reference,
                    request.result_status.value,
                    request.external_response_digest,
                    _json(request.evidence),
                    actor,
                ),
            ).fetchone()
            self._event(conn, pilot_id, request.pilot_item_id, "live_delivery_evidence_recorded", actor, {"live_evidence_id": str(row["id"])})
        return {"ok": True, "live_delivery_evidence": dict(row)}

    def accept(self, *, pilot_id: UUID, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_role(conn, actor, "admin")
            pilot = conn.execute(
                """UPDATE football_brief.acceptance_pilots
                   SET status='accepted',accepted_by=%s,accepted_at=now()
                   WHERE id=%s AND status IN ('running','blocked') RETURNING *""",
                (actor, pilot_id),
            ).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_acceptable")
            self._event(conn, pilot_id, None, "pilot_accepted", actor, {})
        return {"ok": True, "pilot": dict(pilot)}

    def detail(self, *, pilot_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            pilot = conn.execute("SELECT * FROM football_brief.acceptance_pilots WHERE id=%s", (pilot_id,)).fetchone()
            if not pilot:
                raise AcceptancePilotError("pilot_not_found")
            items = conn.execute(
                """SELECT api.*,b.slug AS brand_slug,b.display_name AS brand_name
                   FROM football_brief.acceptance_pilot_items api
                   JOIN football_brief.brands b ON b.id=api.brand_id
                   WHERE api.pilot_id=%s ORDER BY b.slug,api.created_at,api.id""",
                (pilot_id,),
            ).fetchall()
            evidence = conn.execute(
                """SELECT ape.* FROM football_brief.acceptance_pilot_evidence ape
                   JOIN football_brief.acceptance_pilot_items api ON api.id=ape.pilot_item_id
                   WHERE api.pilot_id=%s ORDER BY ape.observed_at,ape.id""",
                (pilot_id,),
            ).fetchall()
            defects = conn.execute(
                "SELECT * FROM football_brief.acceptance_pilot_defects WHERE pilot_id=%s ORDER BY opened_at,id",
                (pilot_id,),
            ).fetchall()
            signoffs = conn.execute(
                "SELECT * FROM football_brief.acceptance_pilot_signoffs WHERE pilot_id=%s ORDER BY created_at,id",
                (pilot_id,),
            ).fetchall()
            live = conn.execute(
                "SELECT * FROM football_brief.acceptance_live_delivery_evidence WHERE pilot_id=%s ORDER BY recorded_at,id",
                (pilot_id,),
            ).fetchall()
        return {
            "ok": True,
            "pilot": dict(pilot),
            "items": [dict(row) for row in items],
            "evidence": [dict(row) for row in evidence],
            "defects": [dict(row) for row in defects],
            "signoffs": [dict(row) for row in signoffs],
            "live_delivery_evidence": [dict(row) for row in live],
        }

    def _system_checks(self, conn: Any, context: Any) -> dict[EvidenceCategory, dict[str, Any]]:
        content_id = context["portfolio_content_id"]
        version = int(context["content_version"])
        brand_id = context["brand_id"]
        production_mode = context["production_mode"]
        checks: dict[EvidenceCategory, dict[str, Any]] = {}

        profile = conn.execute(
            """SELECT bp.id,bp.version,bp.status FROM football_brief.portfolio_content pc
               JOIN football_brief.brand_profiles bp ON bp.id=pc.brand_profile_id
               WHERE pc.id=%s AND bp.brand_id=%s AND bp.status IN ('active','retired')""",
            (content_id, brand_id),
        ).fetchone()
        checks[EvidenceCategory.BRAND_PROFILE] = self._result(profile, "brand_profile", profile)

        preset = conn.execute(
            """SELECT bnp.id,bnp.preset_key,bnp.role,bnp.approved_voice_id
               FROM football_brief.portfolio_content pc
               JOIN football_brief.brand_narration_presets bnp ON bnp.id=pc.narration_preset_id
               JOIN football_brief.brand_profiles bp ON bp.id=bnp.brand_profile_id
               WHERE pc.id=%s AND bp.brand_id=%s AND bnp.active""",
            (content_id, brand_id),
        ).fetchone()
        checks[EvidenceCategory.NARRATION_PRESET] = self._result(preset, "brand_narration_preset", preset)

        roles = conn.execute(
            """SELECT our.role,count(*) AS count
               FROM football_brief.operator_users ou
               JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
               LEFT JOIN football_brief.operator_brand_assignments oba
                 ON oba.operator_user_id=ou.id AND oba.brand_id=%s
               WHERE ou.active AND (our.role='admin' OR oba.brand_id IS NOT NULL)
                 AND our.role IN ('admin','producer','reviewer','publisher')
               GROUP BY our.role""",
            (brand_id,),
        ).fetchall()
        role_counts = {row["role"]: int(row["count"]) for row in roles}
        checks[EvidenceCategory.ROLE_ASSIGNMENT] = self._result(
            all(role_counts.get(role, 0)>0 for role in ("admin","producer","reviewer","publisher")),
            "operator_brand_assignments",
            {"role_counts": role_counts, "brand_id": str(brand_id)},
        )

        concept = conn.execute(
            """SELECT id,batch_id,status,concept_fingerprint,total_score
               FROM football_brief.concept_candidates
               WHERE accepted_content_id=%s AND status='accepted'
               ORDER BY reviewed_at DESC NULLS LAST,id DESC LIMIT 1""",
            (content_id,),
        ).fetchone()
        checks[EvidenceCategory.CONCEPT_APPROVAL] = self._result(concept, "concept_candidate", concept)

        script = conn.execute(
            """SELECT sv.*,sd.id AS document_id FROM football_brief.script_documents sd
               JOIN football_brief.script_versions sv ON sv.script_document_id=sd.id
               WHERE sd.portfolio_content_id=%s AND sv.basis_content_version=%s AND sv.status='approved'
               ORDER BY sv.version DESC LIMIT 1""",
            (content_id, version),
        ).fetchone()
        checks[EvidenceCategory.SCRIPT_APPROVAL] = self._result(script, "script_version", script)
        script_id = script["id"] if script else None
        source_summary = None
        if script_id:
            source_summary = conn.execute(
                """SELECT count(*) AS source_count,
                          count(*) FILTER (WHERE sc.support_status IN ('unsupported','needs_source')) AS unsupported_count
                   FROM football_brief.script_sources ss
                   FULL JOIN football_brief.script_claims sc ON sc.script_version_id=ss.script_version_id
                   WHERE COALESCE(ss.script_version_id,sc.script_version_id)=%s""",
                (script_id,),
            ).fetchone()
        source_passed = bool(source_summary and int(source_summary["source_count"])>0 and int(source_summary["unsupported_count"])==0)
        checks[EvidenceCategory.SOURCE_EVIDENCE] = self._result(source_passed, "script_source_pack", source_summary or {"script_version_id": str(script_id) if script_id else None})
        revision = None
        if script:
            revision = conn.execute(
                """SELECT id,version,parent_version_id,revision_reason,status
                   FROM football_brief.script_versions
                   WHERE script_document_id=%s AND version>1 AND parent_version_id IS NOT NULL
                     AND nullif(btrim(revision_reason),'') IS NOT NULL
                   ORDER BY version DESC LIMIT 1""",
                (script["document_id"],),
            ).fetchone()
        checks[EvidenceCategory.SCRIPT_REVISION] = self._result(revision, "script_revision", revision)

        audio = conn.execute(
            """SELECT ap.id,ap.status,ap.provider,ap.model_id,ap.narration_preset_id,
                      amv.id AS mix_id,amv.version AS mix_version,amv.status AS mix_status,
                      amv.qc_status,amv.alignment_source,amv.final_mix_asset_id
               FROM football_brief.audio_productions ap
               JOIN football_brief.audio_mix_versions amv ON amv.id=ap.current_mix_version_id
               WHERE ap.portfolio_content_id=%s AND ap.content_version=%s
                 AND ap.status='approved' AND amv.status='approved' AND amv.qc_status='pass'
               ORDER BY ap.decided_at DESC LIMIT 1""",
            (content_id, version),
        ).fetchone()
        checks[EvidenceCategory.NARRATION_APPROVAL] = self._result(audio, "audio_mix_version", audio)
        audio_revision = None
        if audio:
            audio_revision = conn.execute(
                """SELECT id,version,parent_mix_version_id,status FROM football_brief.audio_mix_versions
                   WHERE audio_production_id=%s AND version>1 AND parent_mix_version_id IS NOT NULL
                   ORDER BY version DESC LIMIT 1""",
                (audio["id"],),
            ).fetchone()
        checks[EvidenceCategory.NARRATION_REVISION] = self._result(audio_revision, "audio_mix_revision", audio_revision)

        visual = conn.execute(
            """SELECT vp.id,vp.status,vp.provider,vp.model_id,vp.visual_preset_id,
                      count(vs.id) AS shot_count,
                      count(vs.id) FILTER (WHERE vs.status='approved') AS approved_shots
               FROM football_brief.visual_projects vp
               LEFT JOIN football_brief.visual_shots vs ON vs.visual_project_id=vp.id
               WHERE vp.portfolio_content_id=%s AND vp.content_version=%s AND vp.status='approved'
               GROUP BY vp.id ORDER BY vp.decided_at DESC LIMIT 1""",
            (content_id, version),
        ).fetchone()
        visual_passed = bool(visual and int(visual["shot_count"])>0 and int(visual["approved_shots"])==int(visual["shot_count"]))
        checks[EvidenceCategory.VISUAL_APPROVAL] = self._result(visual_passed, "visual_project", visual or {})
        visual_revision = None
        if visual:
            visual_revision = conn.execute(
                """SELECT vsv.id,vsv.version,vsv.parent_version_id,vsv.revision_reason
                   FROM football_brief.visual_shot_versions vsv
                   JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
                   WHERE vs.visual_project_id=%s AND vsv.version>1 AND vsv.parent_version_id IS NOT NULL
                     AND nullif(btrim(vsv.revision_reason),'') IS NOT NULL
                   ORDER BY vsv.version DESC LIMIT 1""",
                (visual["id"],),
            ).fetchone()
        checks[EvidenceCategory.VISUAL_REVISION] = self._result(visual_revision, "visual_shot_revision", visual_revision)

        routing = conn.execute(
            """SELECT srp.id,srp.version,srp.status,srp.total_estimated_cost,
                      srp.managed_shot_count,srp.local_shot_count,srp.manual_shot_count,
                      psd.id AS spend_decision_id,psd.decision,psd.approved_ceiling
               FROM football_brief.shot_routing_plans srp
               JOIN football_brief.production_spend_decisions psd ON psd.routing_plan_id=srp.id
               WHERE srp.portfolio_content_id=%s AND srp.content_version=%s
                 AND srp.status='approved' AND psd.decision='approved'
               ORDER BY srp.version DESC LIMIT 1""",
            (content_id, version),
        ).fetchone()
        route_summary = None
        if routing:
            route_summary = conn.execute(
                """SELECT count(*) AS item_count,
                          count(*) FILTER (WHERE nullif(btrim(rationale),'') IS NOT NULL) AS explained_count,
                          count(*) FILTER (WHERE route='managed_render') AS managed_count
                   FROM football_brief.shot_routing_items WHERE routing_plan_id=%s""",
                (routing["id"],),
            ).fetchone()
        routing_passed = bool(route_summary and int(route_summary["item_count"])>0 and int(route_summary["item_count"])==int(route_summary["explained_count"]))
        checks[EvidenceCategory.ROUTING_EXPLANATION] = self._result(routing_passed, "shot_routing_plan", {**dict(routing or {}), **dict(route_summary or {})})
        spend_passed = bool(routing)
        if routing and production_mode == "managed_render":
            reservation = conn.execute(
                """SELECT count(*) AS total,
                          count(*) FILTER (WHERE status='reconciled' AND generation_job_id IS NOT NULL) AS reconciled,
                          COALESCE(sum(actual_amount),0) AS actual_amount
                   FROM football_brief.production_spend_reservations WHERE routing_plan_id=%s""",
                (routing["id"],),
            ).fetchone()
            spend_passed = int(reservation["total"])>0 and int(reservation["total"])==int(reservation["reconciled"])
            spend_details = {**dict(routing), **dict(reservation)}
        else:
            spend_details = dict(routing or {})
            spend_passed = bool(routing and int(routing["managed_shot_count"])==0 and float(routing["total_estimated_cost"])==0)
        checks[EvidenceCategory.SPEND_APPROVAL] = self._result(spend_passed, "production_spend_decision", spend_details)

        renderer = None
        if routing and production_mode == "managed_render":
            renderer = conn.execute(
                """SELECT count(*) AS managed_count,
                          count(*) FILTER (WHERE rpr.accepted AND rce.id IS NOT NULL) AS verified_count,
                          jsonb_agg(DISTINCT jsonb_build_object(
                              'renderer_entry_id',rce.id,'provider_key',rce.provider_key,
                              'model_key',rce.model_key,'preflight_id',rpr.id
                          )) AS lineage
                   FROM football_brief.shot_routing_items sri
                   JOIN football_brief.renderer_preflight_records rpr ON rpr.id=sri.renderer_preflight_id
                   JOIN football_brief.renderer_catalogue_entries rce ON rce.id=rpr.renderer_catalogue_entry_id
                   WHERE sri.routing_plan_id=%s AND sri.route='managed_render'""",
                (routing["id"],),
            ).fetchone()
            renderer_passed = int(renderer["managed_count"])>0 and int(renderer["managed_count"])==int(renderer["verified_count"])
        else:
            renderer = visual
            renderer_passed = bool(visual and visual["provider"] and visual["model_id"])
        checks[EvidenceCategory.RENDERER_LINEAGE] = self._result(renderer_passed, "renderer_lineage", renderer or {})

        release = conn.execute(
            """SELECT fr.*,sav.status AS artifact_status,sso.status AS object_status,sso.sha256 AS object_sha256
               FROM football_brief.final_releases fr
               JOIN football_brief.shared_artifact_versions sav ON sav.id=fr.output_artifact_version_id
               JOIN football_brief.shared_artifact_object_roles saor
                 ON saor.artifact_version_id=sav.id AND saor.role='original'
               JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
               WHERE fr.portfolio_content_id=%s AND fr.content_version=%s AND fr.status='approved'
                 AND sav.status IN ('current','retained') AND sso.status='available'
               ORDER BY fr.version DESC LIMIT 1""",
            (content_id, version),
        ).fetchone()
        checks[EvidenceCategory.ARTIFACT_LINEAGE] = self._result(release, "shared_artifact_version", release)
        qa = None
        if release:
            qa = conn.execute(
                """SELECT id,outcome,report_hash,output_hash,created_at
                   FROM football_brief.final_release_qa_reports
                   WHERE release_id=%s AND outcome='pass' ORDER BY created_at DESC,id DESC LIMIT 1""",
                (release["id"],),
            ).fetchone()
        checks[EvidenceCategory.FINAL_QA] = self._result(qa, "final_release_qa_report", qa)
        manifest_passed = bool(release and release["release_manifest"] is not None and release["manifest_hash"])
        checks[EvidenceCategory.RELEASE_MANIFEST] = self._result(manifest_passed, "final_release", release or {})

        delivery = None
        if release:
            delivery = conn.execute(
                """SELECT pdr.id,pdr.status,pdr.platform_reference,pdr.privacy,pdr.created_by,
                          pdt.environment,pdt.simulated,pdt.platform,pdt.target_key
                   FROM football_brief.platform_delivery_requests pdr
                   JOIN football_brief.platform_delivery_targets pdt ON pdt.id=pdr.target_id
                   WHERE pdr.final_release_id=%s AND pdr.status='succeeded'
                     AND pdt.environment='staging' AND pdt.simulated
                   ORDER BY pdr.completed_at DESC LIMIT 1""",
                (release["id"],),
            ).fetchone()
        publisher_passed = False
        if delivery:
            publisher_passed = bool(conn.execute(
                """SELECT EXISTS(
                       SELECT 1 FROM football_brief.operator_users ou
                       JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
                       WHERE ou.operator_id=%s AND ou.active AND our.role='publisher'
                   ) AS allowed""",
                (delivery["created_by"],),
            ).fetchone()["allowed"])
        checks[EvidenceCategory.PUBLISHER_DECISION] = self._result(publisher_passed, "platform_delivery_request", delivery or {})
        checks[EvidenceCategory.STAGING_DELIVERY] = self._result(delivery, "platform_delivery_request", {**dict(delivery or {}), "delivery_request_id": str(delivery["id"]) if delivery else None})

        observation = None
        if delivery and release:
            observation = conn.execute(
                """SELECT pdo.*,pdeo.cost_per_thousand_views_usd,
                          pdeo.revenue_per_thousand_views_usd,pdeo.contribution_after_production_cost_usd
                   FROM football_brief.performance_delivery_observations pdo
                   JOIN football_brief.performance_delivery_observation_economics pdeo ON pdeo.id=pdo.id
                   WHERE pdo.delivery_request_id=%s AND pdo.final_release_id=%s
                   ORDER BY pdo.observed_at DESC LIMIT 1""",
                (delivery["id"], release["id"]),
            ).fetchone()
        checks[EvidenceCategory.ANALYTICS_OBSERVATION] = self._result(observation, "performance_delivery_observation", observation)
        economics_passed = bool(observation and observation["production_cost_usd"] is not None)
        checks[EvidenceCategory.PRODUCTION_ECONOMICS] = self._result(economics_passed, "performance_delivery_observation_economics", observation or {})
        return checks

    def _resolve_operations_evidence(self, conn: Any, request: OperationsEvidenceRequest) -> dict[str, Any]:
        try:
            subject_uuid = UUID(request.subject_id)
        except ValueError as exc:
            raise AcceptancePilotError("operations_subject_id_must_be_uuid") from exc
        if request.category == EvidenceCategory.BACKUP_RESTORE:
            row = conn.execute(
                """SELECT ore.*,obs.backup_key,obs.migration_head
                   FROM football_brief.operations_restore_events ore
                   JOIN football_brief.operations_backup_sets obs ON obs.id=ore.backup_set_id
                   WHERE ore.id=%s AND ore.database_restored AND ore.artifacts_restored
                     AND ore.migration_head_verified AND ore.database_sha256_verified
                     AND ore.artifact_sha256_verified""",
                (subject_uuid,),
            ).fetchone()
        elif request.category == EvidenceCategory.WORKER_RESTART:
            row = conn.execute(
                """SELECT * FROM football_brief.operations_drill_runs
                   WHERE id=%s AND drill_kind='worker_restart' AND status='passed'""",
                (subject_uuid,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT * FROM football_brief.operations_drill_runs
                   WHERE id=%s AND drill_kind IN ('staging_recreate','security_scan') AND status='passed'""",
                (subject_uuid,),
            ).fetchone()
        return self._result(row, request.subject_type, row)

    def _record_evidence(
        self,
        conn: Any,
        *,
        item_id: UUID,
        category: EvidenceCategory,
        result: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        details = result["details"]
        digest = _digest(details)
        row = conn.execute(
            """INSERT INTO football_brief.acceptance_pilot_evidence
               (pilot_item_id,category,passed,subject_type,subject_id,subject_version,
                details,details_digest,observed_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               ON CONFLICT (pilot_item_id,category,subject_type,subject_id,details_digest)
               DO NOTHING RETURNING *""",
            (
                item_id,
                category.value,
                result["passed"],
                result["subject_type"],
                result["subject_id"],
                result.get("subject_version"),
                _json(details),
                digest,
                actor,
            ),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """SELECT * FROM football_brief.acceptance_pilot_evidence
                   WHERE pilot_item_id=%s AND category=%s AND subject_type=%s
                     AND subject_id=%s AND details_digest=%s""",
                (item_id, category.value, result["subject_type"], result["subject_id"], digest),
            ).fetchone()
        return dict(row)

    @staticmethod
    def _result(value: Any, subject_type: str, details: Any) -> dict[str, Any]:
        passed = bool(value)
        normalized = dict(details) if details is not None and hasattr(details, "keys") else (details if isinstance(details, dict) else {})
        subject_id = None
        subject_version = None
        if normalized:
            subject_id = normalized.get("id") or normalized.get("mix_id") or normalized.get("delivery_request_id")
            subject_version = normalized.get("version") or normalized.get("mix_version")
        return {
            "passed": passed,
            "subject_type": subject_type,
            "subject_id": str(subject_id or f"missing:{subject_type}"),
            "subject_version": str(subject_version) if subject_version is not None else None,
            "details": normalized,
        }

    @staticmethod
    def _item_context(conn: Any, item_id: UUID) -> Any:
        return conn.execute(
            """SELECT api.*,b.slug AS brand_slug
               FROM football_brief.acceptance_pilot_items api
               JOIN football_brief.brands b ON b.id=api.brand_id
               WHERE api.id=%s FOR UPDATE OF api""",
            (item_id,),
        ).fetchone()

    @staticmethod
    def _require_role(conn: Any, actor: str, role: str) -> None:
        allowed = conn.execute(
            """SELECT EXISTS(
                   SELECT 1 FROM football_brief.operator_users ou
                   JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
                   WHERE ou.operator_id=%s AND ou.active AND our.role=%s
               ) AS allowed""",
            (actor, role),
        ).fetchone()["allowed"]
        if not allowed:
            raise AcceptancePilotError("pilot_role_required", details={"role": role})

    @staticmethod
    def _require_any_role(conn: Any, actor: str, roles: set[str]) -> None:
        allowed = conn.execute(
            """SELECT EXISTS(
                   SELECT 1 FROM football_brief.operator_users ou
                   JOIN football_brief.operator_user_roles our ON our.operator_user_id=ou.id
                   WHERE ou.operator_id=%s AND ou.active AND our.role=ANY(%s::text[])
               ) AS allowed""",
            (actor, sorted(roles)),
        ).fetchone()["allowed"]
        if not allowed:
            raise AcceptancePilotError("pilot_role_required", details={"roles": sorted(roles)})

    @staticmethod
    def _event(conn: Any, pilot_id: UUID, item_id: UUID | None, event: str, actor: str, details: dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO football_brief.acceptance_pilot_events
               (pilot_id,pilot_item_id,event,actor,details)
               VALUES (%s,%s,%s,%s,%s::jsonb)""",
            (pilot_id, item_id, event, actor, _json(details)),
        )
