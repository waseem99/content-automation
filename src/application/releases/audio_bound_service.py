from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobError
from src.application.releases.models import AssemblyEnqueueRequest, FinalReleaseCreate
from src.application.releases.service import FinalReleaseError, _hash, _json
from src.application.releases.validated_service import ValidatedFinalReleaseService


class AudioBoundFinalReleaseService(ValidatedFinalReleaseService):
    """Canonical final-release service bound to the exact approved P90 audio mix."""

    def create_release(self, request: FinalReleaseCreate, *, actor: str) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"final-release:{request.portfolio_content_id}:{request.content_version}",),
            )
            open_row = conn.execute(
                """SELECT id,status FROM football_brief.final_releases
                   WHERE portfolio_content_id=%s AND content_version=%s
                     AND status IN ('draft','assembly_queued','assembled','qa_complete','in_review')
                   FOR UPDATE""",
                (request.portfolio_content_id, request.content_version),
            ).fetchone()
            if open_row:
                raise FinalReleaseError(
                    "final_release_open_version_exists",
                    details={"release_id": str(open_row["id"]), "status": open_row["status"]},
                )
            latest = conn.execute(
                """SELECT * FROM football_brief.final_releases
                   WHERE portfolio_content_id=%s AND content_version=%s
                   ORDER BY version DESC LIMIT 1 FOR UPDATE""",
                (request.portfolio_content_id, request.content_version),
            ).fetchone()
            version = int(latest["version"]) + 1 if latest else 1
            parent_id = latest["id"] if latest else None
            snapshots = [self._approved_input_snapshot(conn, item) for item in request.inputs]
            input_document = [
                {
                    "artifact_version_id": str(item["artifact"]["id"]),
                    "role": item["request"].role.value,
                    "sequence_number": item["request"].sequence_number,
                    "required": item["request"].required,
                    "canonical_asset_id": str(item["asset"]["id"]),
                    "asset_sha256": item["asset"]["sha256"],
                    "approval_id": str(item["approval"]["id"]),
                    "metadata": item["request"].metadata,
                }
                for item in snapshots
            ]
            input_document.sort(
                key=lambda item: (
                    item["role"],
                    item["sequence_number"],
                    item["artifact_version_id"],
                )
            )
            input_hash = _hash(
                {
                    "audio_mix_version_id": str(request.audio_mix_version_id),
                    "inputs": input_document,
                }
            )
            release = conn.execute(
                """INSERT INTO football_brief.final_releases
                   (portfolio_content_id,content_version,version,parent_release_id,render_profile_id,
                    audio_mix_version_id,routing_plan_id,status,input_hash,metadata,created_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s::jsonb,%s) RETURNING *""",
                (
                    request.portfolio_content_id,
                    request.content_version,
                    version,
                    parent_id,
                    request.render_profile_id,
                    request.audio_mix_version_id,
                    request.routing_plan_id,
                    input_hash,
                    _json(request.metadata),
                    actor,
                ),
            ).fetchone()
            for item in snapshots:
                artifact_snapshot = {
                    key: item["artifact"].get(key)
                    for key in (
                        "id",
                        "brand_id",
                        "portfolio_content_id",
                        "content_version",
                        "artifact_key",
                        "artifact_kind",
                        "version",
                        "parent_version_id",
                        "status",
                        "original_asset_id",
                        "review_proxy_asset_id",
                        "thumbnail_asset_id",
                        "metadata",
                        "created_at",
                    )
                }
                conn.execute(
                    """INSERT INTO football_brief.final_release_inputs
                       (release_id,artifact_version_id,approval_id,role,sequence_number,required,
                        canonical_asset_id,asset_sha256,artifact_snapshot,metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
                    (
                        release["id"],
                        item["artifact"]["id"],
                        item["approval"]["id"],
                        item["request"].role.value,
                        item["request"].sequence_number,
                        item["request"].required,
                        item["asset"]["id"],
                        item["asset"]["sha256"],
                        _json(artifact_snapshot),
                        _json(item["request"].metadata),
                    ),
                )
            self._event(
                conn,
                release_id=release["id"],
                event="created",
                actor=actor,
                from_lock=None,
                to_lock=1,
                details={
                    "version": version,
                    "input_hash": input_hash,
                    "audio_mix_version_id": str(request.audio_mix_version_id),
                },
            )
            if latest and latest["status"] == "approved":
                superseded = conn.execute(
                    """UPDATE football_brief.final_releases
                       SET status='superseded',superseded_at=now(),lock_version=lock_version+1
                       WHERE id=%s RETURNING *""",
                    (latest["id"],),
                ).fetchone()
                self._event(
                    conn,
                    release_id=latest["id"],
                    event="superseded",
                    actor=actor,
                    from_lock=int(latest["lock_version"]),
                    to_lock=int(superseded["lock_version"]),
                    details={"replacement_release_id": str(release["id"])},
                )
        return self.detail(release_id=release["id"])

    def enqueue_assembly(
        self,
        *,
        release_id: UUID,
        request: AssemblyEnqueueRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            release = self._release(conn, release_id)
            if release["status"] == "assembly_queued" and release["assembly_job_id"]:
                return {
                    "ok": True,
                    "release": dict(release),
                    "job": self.jobs.detail(job_id=release["assembly_job_id"])["job"],
                    "reused": True,
                }
            if release["status"] != "draft":
                raise FinalReleaseError(
                    "final_release_not_ready_for_assembly",
                    details={"status": release["status"]},
                )
            self._require_current_inputs(conn, release_id)
            self._require_routing_ready(conn, release)
            blockers = conn.execute(
                """SELECT count(*) AS count FROM football_brief.creator_revision_tasks
                   WHERE portfolio_content_id=%s AND blocker=true AND status IN ('open','in_progress')""",
                (release["portfolio_content_id"],),
            ).fetchone()["count"]
            if blockers:
                raise FinalReleaseError(
                    "final_release_has_open_blocking_revision_tasks",
                    details={"count": int(blockers)},
                )
            profile = conn.execute(
                "SELECT * FROM football_brief.platform_render_profiles WHERE id=%s",
                (release["render_profile_id"],),
            ).fetchone()
            inputs = conn.execute(
                """SELECT role,sequence_number,artifact_version_id,canonical_asset_id,asset_sha256,
                          artifact_snapshot,metadata
                   FROM football_brief.final_release_inputs WHERE release_id=%s
                   ORDER BY role,sequence_number,id""",
                (release_id,),
            ).fetchall()

        job_request = GenerationJobEnqueue(
            portfolio_content_id=release["portfolio_content_id"],
            content_version=int(release["content_version"]),
            job_type=GenerationJobType.ASSEMBLY,
            provider="local-assembly",
            model_id="deterministic-release-assembler-v1",
            preferred_worker_id=request.preferred_worker_id,
            priority=request.priority,
            idempotency_key=f"final-release:{release_id}:assembly:v{release['version']}",
            input_payload={
                "final_release_id": str(release_id),
                "audio_mix_version_id": str(release["audio_mix_version_id"]),
                "input_hash": release["input_hash"],
                "profile": self._profile_snapshot(profile),
                "inputs": [dict(row) for row in inputs],
            },
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
        )
        try:
            job = self.jobs.enqueue(job_request, actor=actor)
        except GenerationJobError as exc:
            raise FinalReleaseError(
                "final_release_assembly_enqueue_failed",
                details={"job_error": exc.code},
            ) from exc

        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            current = conn.execute(
                "SELECT * FROM football_brief.final_releases WHERE id=%s FOR UPDATE",
                (release_id,),
            ).fetchone()
            if current["status"] == "assembly_queued" and current["assembly_job_id"] == job["id"]:
                return {"ok": True, "release": dict(current), "job": job, "reused": True}
            if current["status"] != "draft":
                raise FinalReleaseError("final_release_assembly_binding_conflict")
            updated = conn.execute(
                """UPDATE football_brief.final_releases
                   SET status='assembly_queued',assembly_job_id=%s,assembly_queued_at=now(),
                       lock_version=lock_version+1
                   WHERE id=%s RETURNING *""",
                (job["id"], release_id),
            ).fetchone()
            self._event(
                conn,
                release_id=release_id,
                event="assembly_queued",
                actor=actor,
                from_lock=int(current["lock_version"]),
                to_lock=int(updated["lock_version"]),
                details={
                    "job_id": str(job["id"]),
                    "audio_mix_version_id": str(release["audio_mix_version_id"]),
                },
            )
        return {
            "ok": True,
            "release": dict(updated),
            "job": job,
            "reused": bool(job.get("reused")),
        }

    def _release_manifest(
        self,
        conn: Any,
        release: Mapping[str, Any],
        *,
        qa: Mapping[str, Any],
        playback: Mapping[str, Any],
        reviewer: str,
        rationale: str,
    ) -> dict[str, Any]:
        manifest = super()._release_manifest(
            conn,
            release,
            qa=qa,
            playback=playback,
            reviewer=reviewer,
            rationale=rationale,
        )
        audio = conn.execute(
            """SELECT amv.id,amv.version,amv.status,amv.audio_production_id,
                      amv.narration_asset_id,amv.final_mix_asset_id,amv.target_lufs,
                      amv.measured_lufs,amv.true_peak_dbfs,amv.clipping_count,
                      amv.silence_ratio,amv.duration_seconds,amv.qc_status,
                      amv.alignment_source,ap.provider,ap.model_id,ap.approved_voice_id,
                      a.sha256 AS final_mix_sha256,a.size_bytes AS final_mix_size_bytes
               FROM football_brief.audio_mix_versions amv
               JOIN football_brief.audio_productions ap ON ap.id=amv.audio_production_id
               JOIN football_brief.assets a ON a.id=amv.final_mix_asset_id
               WHERE amv.id=%s""",
            (release["audio_mix_version_id"],),
        ).fetchone()
        manifest["audio_mix"] = dict(audio)
        return manifest
