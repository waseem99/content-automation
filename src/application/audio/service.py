from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID, uuid4

from src.application.audio.adapters import (
    AudioQualityPolicy,
    KokoroJobAdapter,
    KokoroParagraphContext,
    merge_pronunciation_rules,
    take_input_fingerprint,
    validate_forced_alignment,
)
from src.application.audio.models import (
    AlignmentSource,
    AssemblyEnqueueRequest,
    AudioDecision,
    AudioInitializeRequest,
    AudioReviewActionType,
    AudioTakeResult,
    MixRegistrationRequest,
    MixRevisionRequest,
    PronunciationOverrideRequest,
    ReviewActionRequest,
)
from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class AudioProductionError(RuntimeError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AudioProductionService:
    def __init__(self, database: "Database") -> None:
        self.database = database
        self.jobs = GenerationJobService(database)
        self.kokoro = KokoroJobAdapter()
        self.take_quality = AudioQualityPolicy()

    def initialize(
        self,
        *,
        content_id: UUID,
        request: AudioInitializeRequest,
        actor: str,
    ) -> dict[str, Any]:
        context = self._initial_context(content_id)
        created = False
        production_id: UUID | None = None
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            existing = conn.execute(
                """SELECT * FROM football_brief.audio_productions
                   WHERE portfolio_content_id=%s AND script_version_id=%s
                   FOR UPDATE""",
                (content_id, context["script_version_id"]),
            ).fetchone()
            if existing:
                production_id = existing["id"]
            else:
                live = conn.execute(
                    """SELECT * FROM football_brief.audio_productions
                       WHERE portfolio_content_id=%s
                         AND status IN ('working','in_review','approved')
                       FOR UPDATE""",
                    (content_id,),
                ).fetchone()
                if live:
                    if live["status"] != "approved":
                        raise AudioProductionError(
                            "audio_production_already_active",
                            details={"production_id": str(live["id"]), "status": live["status"]},
                        )
                    conn.execute(
                        """UPDATE football_brief.audio_productions
                           SET status='superseded', last_edited_by=%s,
                               lock_version=lock_version+1
                           WHERE id=%s""",
                        (actor, live["id"]),
                    )
                    conn.execute(
                        """INSERT INTO football_brief.audio_production_events
                           (audio_production_id, audio_mix_version_id, event, actor, details)
                           VALUES (%s,%s,'superseded',%s,%s::jsonb)""",
                        (
                            live["id"],
                            live["current_mix_version_id"],
                            actor,
                            _json({"replacement_script_version_id": str(context["script_version_id"])}),
                        ),
                    )

                production_id = uuid4()
                mix_id = uuid4()
                preset_snapshot = {
                    "brand_profile_id": str(context["brand_profile_id"]),
                    "brand_profile_version": int(context["brand_profile_version"]),
                    "narration_preset_id": str(context["narration_preset_id"]),
                    "preset_key": context["preset_key"],
                    "display_name": context["preset_display_name"],
                    "role": context["preset_role"],
                    "language": context["preset_language"],
                    "speed": float(context["speed"]),
                    "style": dict(context["style"] or {}),
                    "format_filters": list(context["format_filters"] or []),
                    "topic_filters": list(context["topic_filters"] or []),
                }
                pronunciation_snapshot = dict(context["pronunciation_rules"] or {})
                conn.execute(
                    """INSERT INTO football_brief.audio_productions
                       (id, portfolio_content_id, content_version, script_version_id,
                        brand_profile_id, narration_preset_id, approved_voice_id,
                        provider, provider_voice_id, model_id, preset_snapshot,
                        pronunciation_snapshot, status, lock_version, created_by, last_edited_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                               'working',1,%s,%s)""",
                    (
                        production_id,
                        content_id,
                        context["content_version"],
                        context["script_version_id"],
                        context["brand_profile_id"],
                        context["narration_preset_id"],
                        context["approved_voice_id"],
                        context["provider"],
                        context["provider_voice_id"],
                        request.model_id,
                        _json(preset_snapshot),
                        _json(pronunciation_snapshot),
                        actor,
                        actor,
                    ),
                )
                sections = conn.execute(
                    """SELECT id, sequence, text FROM football_brief.script_sections
                       WHERE script_version_id=%s ORDER BY sequence""",
                    (context["script_version_id"],),
                ).fetchall()
                if not sections:
                    raise AudioProductionError("approved_script_has_no_sections")
                for sequence, section in enumerate(sections, start=1):
                    text = str(section["text"]).strip()
                    conn.execute(
                        """INSERT INTO football_brief.audio_paragraphs
                           (audio_production_id, script_section_id, sequence, paragraph_index,
                            source_text, text_fingerprint)
                           VALUES (%s,%s,%s,1,%s,%s)""",
                        (production_id, section["id"], sequence, text, _sha256_text(text)),
                    )
                conn.execute(
                    """INSERT INTO football_brief.audio_mix_versions
                       (id, audio_production_id, version, status, target_lufs,
                        peak_limit_dbfs, created_by, last_edited_by)
                       VALUES (%s,%s,1,'working',-16,-1,%s,%s)""",
                    (mix_id, production_id, actor, actor),
                )
                conn.execute(
                    """UPDATE football_brief.audio_productions
                       SET current_mix_version_id=%s, lock_version=2
                       WHERE id=%s AND lock_version=1""",
                    (mix_id, production_id),
                )
                conn.execute(
                    """INSERT INTO football_brief.audio_production_events
                       (audio_production_id, audio_mix_version_id, event, actor, details)
                       VALUES (%s,%s,'initialized',%s,%s::jsonb)""",
                    (
                        production_id,
                        mix_id,
                        actor,
                        _json(
                            {
                                "script_version_id": str(context["script_version_id"]),
                                "narration_preset_id": str(context["narration_preset_id"]),
                                "provider": context["provider"],
                                "model_id": request.model_id,
                                "external_fee_allowed": False,
                            }
                        ),
                    ),
                )
                created = True

        assert production_id is not None
        self._ensure_initial_take_jobs(
            production_id=production_id,
            request=request,
            actor=actor,
        )
        result = self.detail(production_id=production_id)
        result["created"] = created
        return result

    def detail(self, *, production_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            production = conn.execute(
                """SELECT ap.*, pc.title, pc.concept, pc.format AS content_format,
                          mp.brand_id, b.slug AS brand_slug, b.display_name AS brand_name,
                          sv.version AS script_version, sv.language AS script_language,
                          sv.target_duration_seconds, sv.duration_tolerance_percent,
                          amv.version AS current_mix_version,
                          amv.status AS current_mix_status
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.portfolio_content pc ON pc.id=ap.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   JOIN football_brief.brands b ON b.id=mp.brand_id
                   JOIN football_brief.script_versions sv ON sv.id=ap.script_version_id
                   LEFT JOIN football_brief.audio_mix_versions amv
                     ON amv.id=ap.current_mix_version_id
                   WHERE ap.id=%s""",
                (production_id,),
            ).fetchone()
            if not production:
                raise AudioProductionError("audio_production_not_found")
            paragraphs = conn.execute(
                """SELECT * FROM football_brief.audio_paragraphs
                   WHERE audio_production_id=%s ORDER BY sequence""",
                (production_id,),
            ).fetchall()
            takes = conn.execute(
                """SELECT ast.*, gj.status AS generation_job_status
                   FROM football_brief.audio_segment_takes ast
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=ast.generation_job_id
                   WHERE ast.audio_production_id=%s
                   ORDER BY ast.paragraph_id, ast.take_version""",
                (production_id,),
            ).fetchall()
            mixes = conn.execute(
                """SELECT * FROM football_brief.audio_mix_versions
                   WHERE audio_production_id=%s ORDER BY version DESC""",
                (production_id,),
            ).fetchall()
            tracks = conn.execute(
                """SELECT amt.* FROM football_brief.audio_mix_tracks amt
                   JOIN football_brief.audio_mix_versions amv ON amv.id=amt.audio_mix_version_id
                   WHERE amv.audio_production_id=%s ORDER BY amv.version DESC, amt.track_role, amt.id""",
                (production_id,),
            ).fetchall()
            overrides = conn.execute(
                """SELECT * FROM football_brief.audio_pronunciation_overrides
                   WHERE audio_production_id=%s ORDER BY created_at, id""",
                (production_id,),
            ).fetchall()
            actions = conn.execute(
                """SELECT ara.*, u.display_name AS author_name
                   FROM football_brief.audio_review_actions ara
                   JOIN football_brief.operator_users u ON u.operator_id=ara.author_operator_id
                   WHERE ara.audio_production_id=%s ORDER BY ara.created_at, ara.id""",
                (production_id,),
            ).fetchall()
            decisions = conn.execute(
                """SELECT ard.*, u.display_name AS reviewer_name
                   FROM football_brief.audio_review_decisions ard
                   JOIN football_brief.operator_users u ON u.operator_id=ard.reviewer_operator_id
                   WHERE ard.audio_production_id=%s ORDER BY ard.created_at, ard.id""",
                (production_id,),
            ).fetchall()
            events = conn.execute(
                """SELECT * FROM football_brief.audio_production_events
                   WHERE audio_production_id=%s ORDER BY created_at, id""",
                (production_id,),
            ).fetchall()
        return {
            "ok": True,
            "production": dict(production),
            "paragraphs": [dict(row) for row in paragraphs],
            "takes": [dict(row) for row in takes],
            "mixes": [dict(row) for row in mixes],
            "tracks": [dict(row) for row in tracks],
            "pronunciation_overrides": [dict(row) for row in overrides],
            "review_actions": [dict(row) for row in actions],
            "decisions": [dict(row) for row in decisions],
            "events": [dict(row) for row in events],
        }

    def production_for_content(self, *, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT id FROM football_brief.audio_productions
                   WHERE portfolio_content_id=%s
                   ORDER BY created_at DESC LIMIT 1""",
                (content_id,),
            ).fetchone()
        if not row:
            raise AudioProductionError("audio_production_not_found")
        return self.detail(production_id=row["id"])

    def add_pronunciation_override(
        self,
        *,
        production_id: UUID,
        request: PronunciationOverrideRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, production_id, request.expected_lock_version)
            if row["status"] not in {"working", "changes_requested"}:
                raise AudioProductionError("audio_production_not_writable")
            conn.execute(
                """UPDATE football_brief.audio_pronunciation_overrides
                   SET active=false
                   WHERE audio_production_id=%s AND lower(token)=lower(%s)
                     AND lower(locale)=lower(%s) AND active=true""",
                (production_id, request.token, request.locale),
            )
            conn.execute(
                """INSERT INTO football_brief.audio_pronunciation_overrides
                   (audio_production_id, token, pronunciation, locale, reason, created_by)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    production_id,
                    request.token.strip(),
                    request.pronunciation.strip(),
                    request.locale.strip(),
                    request.reason,
                    actor,
                ),
            )
            self._advance_lock(
                conn,
                production_id=production_id,
                expected_lock=request.expected_lock_version,
                actor=actor,
            )
        return self.detail(production_id=production_id)

    def regenerate_paragraph(
        self,
        *,
        production_id: UUID,
        paragraph_id: UUID,
        request: AudioInitializeRequest,
        actor: str,
    ) -> dict[str, Any]:
        take = self._enqueue_take(
            production_id=production_id,
            paragraph_id=paragraph_id,
            request=request,
            actor=actor,
            force=True,
        )
        result = self.detail(production_id=production_id)
        result["enqueued_take"] = take
        return result

    def register_take_result(
        self,
        *,
        take_id: UUID,
        result: AudioTakeResult,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            take = conn.execute(
                """SELECT ast.*, apar.source_text, gj.status AS job_status
                   FROM football_brief.audio_segment_takes ast
                   JOIN football_brief.audio_paragraphs apar ON apar.id=ast.paragraph_id
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=ast.generation_job_id
                   WHERE ast.id=%s FOR UPDATE OF ast""",
                (take_id,),
            ).fetchone()
            if not take:
                raise AudioProductionError("audio_take_not_found")
            if take["status"] != "queued":
                raise AudioProductionError("audio_take_not_queued")
            if take["generation_job_id"] is not None and take["job_status"] != "succeeded":
                raise AudioProductionError(
                    "narration_job_not_succeeded",
                    details={"job_status": take["job_status"]},
                )
            timings = result.word_timings
            if result.timing_source == AlignmentSource.FORCED_ALIGNMENT:
                timings = validate_forced_alignment(
                    text=take["source_text"],
                    duration_seconds=result.duration_seconds,
                    timings=result.word_timings,
                )
            qc_status, qc_evidence = self.take_quality.evaluate_take(result)
            updated = conn.execute(
                """UPDATE football_brief.audio_segment_takes
                   SET status='generated', asset_id=%s, duration_seconds=%s,
                       sample_rate_hz=%s, channels=%s, integrated_lufs=%s,
                       true_peak_dbfs=%s, clipping_count=%s, silence_ratio=%s,
                       qc_status=%s, qc_evidence=%s::jsonb, timing_source=%s,
                       word_timings=%s::jsonb
                   WHERE id=%s AND status='queued' RETURNING *""",
                (
                    result.asset_id,
                    result.duration_seconds,
                    result.sample_rate_hz,
                    result.channels,
                    result.integrated_lufs,
                    result.true_peak_dbfs,
                    result.clipping_count,
                    result.silence_ratio,
                    qc_status,
                    _json(qc_evidence),
                    result.timing_source.value,
                    _json([item.model_dump(mode="json") for item in timings]),
                    take_id,
                ),
            ).fetchone()
            if not updated:
                raise AudioProductionError("audio_take_registration_conflict")
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, paragraph_id, segment_take_id, event, actor, details)
                   VALUES (%s,%s,%s,'paragraph_take_registered',%s,%s::jsonb)""",
                (
                    take["audio_production_id"],
                    take["paragraph_id"],
                    take_id,
                    actor,
                    _json({"qc_status": qc_status, "timing_source": result.timing_source.value}),
                ),
            )
        return self.detail(production_id=take["audio_production_id"])

    def select_take(
        self,
        *,
        production_id: UUID,
        take_id: UUID,
        expected_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            production = self._locked(conn, production_id, expected_lock_version)
            if production["status"] not in {"working", "changes_requested"}:
                raise AudioProductionError("audio_production_not_writable")
            take = conn.execute(
                """SELECT * FROM football_brief.audio_segment_takes
                   WHERE id=%s AND audio_production_id=%s FOR UPDATE""",
                (take_id, production_id),
            ).fetchone()
            if not take:
                raise AudioProductionError("audio_take_not_found")
            if take["status"] == "selected":
                return self.detail(production_id=production_id)
            if take["status"] != "generated" or take["qc_status"] != "pass":
                raise AudioProductionError("audio_take_not_selectable")
            conn.execute(
                """UPDATE football_brief.audio_segment_takes
                   SET status='superseded'
                   WHERE paragraph_id=%s AND status='selected'""",
                (take["paragraph_id"],),
            )
            conn.execute(
                """UPDATE football_brief.audio_segment_takes
                   SET status='selected' WHERE id=%s""",
                (take_id,),
            )
            self._advance_lock(
                conn,
                production_id=production_id,
                expected_lock=expected_lock_version,
                actor=actor,
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, paragraph_id, segment_take_id, event, actor, details)
                   VALUES (%s,%s,%s,'paragraph_take_selected',%s,'{}'::jsonb)""",
                (production_id, take["paragraph_id"], take_id, actor),
            )
        return self.detail(production_id=production_id)

    def register_mix(
        self,
        *,
        production_id: UUID,
        request: MixRegistrationRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            production = self._locked(conn, production_id, request.expected_lock_version)
            if production["status"] != "working" or production["mix_status"] != "working":
                raise AudioProductionError("audio_mix_not_working")
            selected = conn.execute(
                """SELECT apar.id AS paragraph_id, apar.sequence, ast.id AS take_id,
                          ast.asset_id, ast.duration_seconds, ast.timing_source,
                          ast.input_fingerprint
                   FROM football_brief.audio_paragraphs apar
                   LEFT JOIN football_brief.audio_segment_takes ast
                     ON ast.paragraph_id=apar.id AND ast.status='selected'
                   WHERE apar.audio_production_id=%s ORDER BY apar.sequence""",
                (production_id,),
            ).fetchall()
            if not selected or any(row["take_id"] is None for row in selected):
                raise AudioProductionError("selected_take_required_for_every_paragraph")
            sources = {str(row["timing_source"]) for row in selected}
            derived_alignment = (
                AlignmentSource.FORCED_ALIGNMENT
                if sources == {AlignmentSource.FORCED_ALIGNMENT.value}
                else AlignmentSource.PROPORTIONAL_PREVIEW
            )
            if request.alignment_source != derived_alignment:
                raise AudioProductionError(
                    "mix_alignment_source_mismatch",
                    details={"requested": request.alignment_source.value, "derived": derived_alignment.value},
                )
            snapshot = [
                {
                    "paragraph_id": str(row["paragraph_id"]),
                    "sequence": int(row["sequence"]),
                    "take_id": str(row["take_id"]),
                    "asset_id": str(row["asset_id"]),
                    "duration_seconds": float(row["duration_seconds"]),
                    "timing_source": row["timing_source"],
                    "input_fingerprint": row["input_fingerprint"],
                }
                for row in selected
            ]
            qc_pass = (
                abs(request.measured_lufs - request.target_lufs) <= 1.0
                and request.true_peak_dbfs <= request.peak_limit_dbfs
                and request.clipping_count == 0
                and request.silence_ratio <= 0.25
            )
            conn.execute(
                "DELETE FROM football_brief.audio_mix_tracks WHERE audio_mix_version_id=%s",
                (production["current_mix_version_id"],),
            )
            conn.execute(
                """UPDATE football_brief.audio_mix_versions
                   SET narration_asset_id=%s, final_mix_asset_id=%s, target_lufs=%s,
                       peak_limit_dbfs=%s, measured_lufs=%s, true_peak_dbfs=%s,
                       clipping_count=%s, silence_ratio=%s, duration_seconds=%s,
                       qc_status=%s, waveform_metadata=%s::jsonb,
                       segment_snapshot=%s::jsonb, mix_settings=%s::jsonb,
                       alignment_source=%s, last_edited_by=%s
                   WHERE id=%s""",
                (
                    request.narration_asset_id,
                    request.final_mix_asset_id,
                    request.target_lufs,
                    request.peak_limit_dbfs,
                    request.measured_lufs,
                    request.true_peak_dbfs,
                    request.clipping_count,
                    request.silence_ratio,
                    request.duration_seconds,
                    "pass" if qc_pass else "fail",
                    _json(request.waveform_metadata),
                    _json(snapshot),
                    _json(request.mix_settings),
                    derived_alignment.value,
                    actor,
                    production["current_mix_version_id"],
                ),
            )
            for track in request.tracks:
                conn.execute(
                    """INSERT INTO football_brief.audio_mix_tracks
                       (audio_mix_version_id, track_role, asset_id, asset_rights_id,
                        level_db, ducking_db, start_seconds, end_seconds, metadata)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                    (
                        production["current_mix_version_id"],
                        track.track_role.value,
                        track.asset_id,
                        track.asset_rights_id,
                        track.level_db,
                        track.ducking_db,
                        track.start_seconds,
                        track.end_seconds,
                        _json(track.metadata),
                    ),
                )
            self._advance_lock(
                conn,
                production_id=production_id,
                expected_lock=request.expected_lock_version,
                actor=actor,
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, audio_mix_version_id, event, actor, details)
                   VALUES (%s,%s,%s,%s,%s::jsonb)""",
                (
                    production_id,
                    production["current_mix_version_id"],
                    "mix_built" if int(production["mix_version"]) == 1 else "mix_rebuilt",
                    actor,
                    _json({"qc_status": "pass" if qc_pass else "fail", "alignment_source": derived_alignment.value}),
                ),
            )
        return self.detail(production_id=production_id)

    def submit(
        self,
        *,
        production_id: UUID,
        expected_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, production_id, expected_lock_version)
            if row["status"] != "working" or row["mix_status"] != "working":
                raise AudioProductionError("audio_mix_not_working")
            conn.execute(
                """UPDATE football_brief.audio_mix_versions
                   SET status='in_review', submitted_at=now(), last_edited_by=%s
                   WHERE id=%s""",
                (actor, row["current_mix_version_id"]),
            )
            conn.execute(
                """UPDATE football_brief.audio_productions
                   SET status='in_review', submitted_at=now(), last_edited_by=%s,
                       lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s""",
                (actor, production_id, expected_lock_version),
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, audio_mix_version_id, event, actor, details)
                   VALUES (%s,%s,'submitted',%s,'{}'::jsonb)""",
                (production_id, row["current_mix_version_id"], actor),
            )
        return self.detail(production_id=production_id)

    def add_review_action(
        self,
        *,
        production_id: UUID,
        request: ReviewActionRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, production_id, request.expected_lock_version)
            if row["current_mix_version_id"] != request.audio_mix_version_id:
                raise AudioProductionError("stale_audio_mix_version")
            action = conn.execute(
                """INSERT INTO football_brief.audio_review_actions
                   (audio_production_id, audio_mix_version_id, paragraph_id,
                    segment_take_id, action_type, body, suggested_value,
                    author_operator_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    production_id,
                    request.audio_mix_version_id,
                    request.paragraph_id,
                    request.segment_take_id,
                    request.action_type.value,
                    request.body,
                    request.suggested_value,
                    actor,
                ),
            ).fetchone()
            self._advance_lock(
                conn,
                production_id=production_id,
                expected_lock=request.expected_lock_version,
                actor=actor,
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, audio_mix_version_id, paragraph_id,
                    segment_take_id, event, actor, details)
                   VALUES (%s,%s,%s,%s,'review_action_created',%s,%s::jsonb)""",
                (
                    production_id,
                    request.audio_mix_version_id,
                    request.paragraph_id,
                    request.segment_take_id,
                    actor,
                    _json({"action_id": str(action["id"]), "action_type": request.action_type.value}),
                ),
            )
        return self.detail(production_id=production_id)

    def resolve_review_action(
        self,
        *,
        production_id: UUID,
        action_id: UUID,
        expected_lock_version: int,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, production_id, expected_lock_version)
            action = conn.execute(
                """UPDATE football_brief.audio_review_actions
                   SET resolved_by_operator_id=%s, resolved_at=now()
                   WHERE id=%s AND audio_production_id=%s AND resolved_at IS NULL
                   RETURNING *""",
                (actor, action_id, production_id),
            ).fetchone()
            if not action:
                raise AudioProductionError("audio_review_action_not_found_or_resolved")
            if action["audio_mix_version_id"] != row["current_mix_version_id"]:
                raise AudioProductionError("stale_audio_review_action")
            self._advance_lock(
                conn,
                production_id=production_id,
                expected_lock=expected_lock_version,
                actor=actor,
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, audio_mix_version_id, paragraph_id,
                    segment_take_id, event, actor, details)
                   VALUES (%s,%s,%s,%s,'review_action_resolved',%s,%s::jsonb)""",
                (
                    production_id,
                    action["audio_mix_version_id"],
                    action["paragraph_id"],
                    action["segment_take_id"],
                    actor,
                    _json({"action_id": str(action_id)}),
                ),
            )
        return self.detail(production_id=production_id)

    def decide(
        self,
        *,
        production_id: UUID,
        expected_lock_version: int,
        decision: AudioDecision,
        rationale: str,
        reviewer: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as conn:
            self._require_active_operator(conn, reviewer)
            row = self._locked(conn, production_id, expected_lock_version)
            conn.execute(
                """INSERT INTO football_brief.audio_review_decisions
                   (audio_production_id, audio_mix_version_id, decision,
                    reviewer_operator_id, rationale, production_lock_version)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    production_id,
                    row["current_mix_version_id"],
                    decision.value,
                    reviewer,
                    rationale,
                    expected_lock_version,
                ),
            )
        return self.detail(production_id=production_id)

    def revise_mix(
        self,
        *,
        production_id: UUID,
        request: MixRevisionRequest,
        actor: str,
    ) -> dict[str, Any]:
        new_mix_id = uuid4()
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            row = self._locked(conn, production_id, request.expected_lock_version)
            if row["status"] not in {"changes_requested", "rejected"}:
                raise AudioProductionError("audio_mix_not_revisable")
            conn.execute(
                """INSERT INTO football_brief.audio_mix_versions
                   (id, audio_production_id, version, parent_mix_version_id,
                    status, target_lufs, peak_limit_dbfs, mix_settings,
                    created_by, last_edited_by)
                   VALUES (%s,%s,%s,%s,'working',%s,%s,%s::jsonb,%s,%s)""",
                (
                    new_mix_id,
                    production_id,
                    int(row["mix_version"]) + 1,
                    row["current_mix_version_id"],
                    row["target_lufs"],
                    row["peak_limit_dbfs"],
                    _json({"revision_reason": request.reason}),
                    actor,
                    actor,
                ),
            )
            conn.execute(
                """UPDATE football_brief.audio_productions
                   SET current_mix_version_id=%s, status='working', last_edited_by=%s,
                       lock_version=lock_version+1
                   WHERE id=%s AND lock_version=%s""",
                (new_mix_id, actor, production_id, request.expected_lock_version),
            )
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, audio_mix_version_id, event, actor, details)
                   VALUES (%s,%s,'mix_rebuilt',%s,%s::jsonb)""",
                (production_id, new_mix_id, actor, _json({"revision_reason": request.reason})),
            )
        return self.detail(production_id=production_id)

    def enqueue_assembly(
        self,
        *,
        production_id: UUID,
        request: AssemblyEnqueueRequest,
        actor: str,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT ap.*, amv.final_mix_asset_id, amv.alignment_source,
                          pw.id AS workflow_id, pw.current_version_id AS workflow_version_id
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.audio_mix_versions amv ON amv.id=ap.current_mix_version_id
                   LEFT JOIN football_brief.production_workflows pw
                     ON pw.portfolio_content_id=ap.portfolio_content_id
                   WHERE ap.id=%s""",
                (production_id,),
            ).fetchone()
        if not row:
            raise AudioProductionError("audio_production_not_found")
        if int(row["lock_version"]) != request.expected_lock_version:
            raise AudioProductionError("audio_production_conflict")
        if row["status"] != "approved":
            raise AudioProductionError("approved_audio_mix_required")
        payload = {
            "script_version_id": str(row["script_version_id"]),
            "audio_production_id": str(production_id),
            "audio_mix_version_id": str(row["current_mix_version_id"]),
            "final_mix_asset_id": str(row["final_mix_asset_id"]),
            "alignment_source": row["alignment_source"],
            "runtime": "local_ffmpeg",
            "external_fee_allowed": False,
        }
        enqueue = GenerationJobEnqueue(
            portfolio_content_id=row["portfolio_content_id"],
            content_version=int(row["content_version"]),
            production_workflow_id=row["workflow_id"],
            production_workflow_version_id=row["workflow_version_id"],
            job_type=GenerationJobType.ASSEMBLY,
            provider="local-ffmpeg",
            model_id=request.model_id,
            preferred_worker_id=request.preferred_worker_id,
            idempotency_key=f"p90:assembly:{production_id}:{row['current_mix_version_id']}",
            input_payload=payload,
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
            estimated_cost_usd=0,
            reserved_cost_usd=0,
            legacy_source={"phase": "P90", "runtime": "local_ffmpeg"},
        )
        job = self.jobs.enqueue(enqueue, actor=actor)
        return {"ok": True, "job": job, **self.detail(production_id=production_id)}

    def _ensure_initial_take_jobs(
        self,
        *,
        production_id: UUID,
        request: AudioInitializeRequest,
        actor: str,
    ) -> None:
        with self.database.connection() as conn:
            paragraphs = conn.execute(
                """SELECT apar.id FROM football_brief.audio_paragraphs apar
                   WHERE apar.audio_production_id=%s
                     AND NOT EXISTS (
                         SELECT 1 FROM football_brief.audio_segment_takes ast
                         WHERE ast.paragraph_id=apar.id
                     )
                   ORDER BY apar.sequence""",
                (production_id,),
            ).fetchall()
        for paragraph in paragraphs:
            self._enqueue_take(
                production_id=production_id,
                paragraph_id=paragraph["id"],
                request=request,
                actor=actor,
                force=False,
            )

    def _enqueue_take(
        self,
        *,
        production_id: UUID,
        paragraph_id: UUID,
        request: AudioInitializeRequest,
        actor: str,
        force: bool,
    ) -> dict[str, Any]:
        with self.database.connection() as conn:
            context = conn.execute(
                """SELECT ap.*, apar.source_text, apar.sequence AS paragraph_sequence,
                          sv.language, bnp.speed, bnp.style, bnp.pronunciation_rules,
                          pw.id AS workflow_id, pw.current_version_id AS workflow_version_id,
                          COALESCE(max(ast.take_version),0) AS last_take_version
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.audio_paragraphs apar ON apar.audio_production_id=ap.id
                   JOIN football_brief.script_versions sv ON sv.id=ap.script_version_id
                   JOIN football_brief.brand_narration_presets bnp ON bnp.id=ap.narration_preset_id
                   LEFT JOIN football_brief.production_workflows pw
                     ON pw.portfolio_content_id=ap.portfolio_content_id
                   LEFT JOIN football_brief.audio_segment_takes ast ON ast.paragraph_id=apar.id
                   WHERE ap.id=%s AND apar.id=%s
                   GROUP BY ap.id, apar.id, sv.id, bnp.id, pw.id
                   """,
                (production_id, paragraph_id),
            ).fetchone()
            if not context:
                raise AudioProductionError("audio_paragraph_not_found")
            if context["status"] not in {"working", "changes_requested"}:
                raise AudioProductionError("audio_production_not_writable")
            if not force:
                existing = conn.execute(
                    """SELECT * FROM football_brief.audio_segment_takes
                       WHERE paragraph_id=%s AND status IN ('queued','generated','selected')
                       ORDER BY take_version DESC LIMIT 1""",
                    (paragraph_id,),
                ).fetchone()
                if existing:
                    return dict(existing)
            overrides = conn.execute(
                """SELECT token, pronunciation, active
                   FROM football_brief.audio_pronunciation_overrides
                   WHERE audio_production_id=%s""",
                (production_id,),
            ).fetchall()
        take_version = int(context["last_take_version"]) + 1
        pronunciation = merge_pronunciation_rules(
            dict(context["pronunciation_rules"] or {}),
            [dict(row) for row in overrides],
        )
        take_context = KokoroParagraphContext(
            portfolio_content_id=context["portfolio_content_id"],
            content_version=int(context["content_version"]),
            production_workflow_id=context["workflow_id"],
            production_workflow_version_id=context["workflow_version_id"],
            script_version_id=context["script_version_id"],
            audio_production_id=production_id,
            paragraph_id=paragraph_id,
            paragraph_sequence=int(context["paragraph_sequence"]),
            take_version=take_version,
            source_text=context["source_text"],
            language=context["language"],
            provider=context["provider"],
            provider_voice_id=context["provider_voice_id"],
            approved_voice_id=context["approved_voice_id"],
            narration_preset_id=context["narration_preset_id"],
            speed=float(context["speed"]),
            style=dict(context["style"] or {}),
            pronunciation_rules=pronunciation,
            model_id=context["model_id"],
        )
        enqueue = self.kokoro.build_enqueue(
            take_context,
            actor=actor,
            preferred_worker_id=request.preferred_worker_id,
            timeout_seconds=request.timeout_seconds,
            max_attempts=request.max_attempts,
        )
        job = self.jobs.enqueue(enqueue, actor=actor)
        fingerprint = take_input_fingerprint(
            text=take_context.source_text,
            model_id=take_context.model_id,
            provider_voice_id=take_context.provider_voice_id,
            speed=take_context.speed,
            style=take_context.style,
            pronunciation_rules=take_context.pronunciation_rules,
        )
        with self.database.transaction() as conn:
            self._require_active_operator(conn, actor)
            existing = conn.execute(
                "SELECT * FROM football_brief.audio_segment_takes WHERE generation_job_id=%s",
                (job["id"],),
            ).fetchone()
            if existing:
                return dict(existing)
            take = conn.execute(
                """INSERT INTO football_brief.audio_segment_takes
                   (audio_production_id, paragraph_id, take_version, generation_job_id,
                    status, provider, model_id, approved_voice_id, narration_preset_id,
                    input_fingerprint, pronunciation_snapshot, actual_cost_usd,
                    external_fee_incurred, created_by)
                   VALUES (%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s,%s::jsonb,0,false,%s)
                   RETURNING *""",
                (
                    production_id,
                    paragraph_id,
                    take_version,
                    job["id"],
                    take_context.provider,
                    take_context.model_id,
                    take_context.approved_voice_id,
                    take_context.narration_preset_id,
                    fingerprint,
                    _json(pronunciation),
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.audio_production_events
                   (audio_production_id, paragraph_id, segment_take_id, event, actor, details)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    production_id,
                    paragraph_id,
                    take["id"],
                    "paragraph_regenerated" if force else "paragraph_take_enqueued",
                    actor,
                    _json({"generation_job_id": str(job["id"]), "take_version": take_version}),
                ),
            )
        return dict(take)

    def _initial_context(self, content_id: UUID) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT pc.id AS portfolio_content_id, pc.version AS content_version,
                          pc.brand_profile_id, pc.narration_preset_id,
                          pw.id AS workflow_id, pw.current_version_id AS workflow_version_id,
                          sv.id AS script_version_id, sv.status AS script_status,
                          sv.language, sv.platform, sv.format,
                          bp.version AS brand_profile_version,
                          bnp.preset_key, bnp.display_name AS preset_display_name,
                          bnp.role AS preset_role, bnp.language AS preset_language,
                          bnp.speed, bnp.style, bnp.pronunciation_rules,
                          bnp.format_filters, bnp.topic_filters, bnp.active AS preset_active,
                          av.id AS approved_voice_id, av.provider, av.provider_voice_id,
                          av.approval_status AS voice_status, av.expires_at AS voice_expires_at
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.production_workflows pw ON pw.portfolio_content_id=pc.id
                   JOIN football_brief.script_documents sd ON sd.portfolio_content_id=pc.id
                   JOIN football_brief.script_versions sv ON sv.id=sd.current_version_id
                   JOIN football_brief.brand_profiles bp ON bp.id=pc.brand_profile_id
                   JOIN football_brief.brand_narration_presets bnp ON bnp.id=pc.narration_preset_id
                   JOIN football_brief.approved_voices av ON av.id=bnp.approved_voice_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise AudioProductionError("approved_script_and_pinned_narration_preset_required")
        if row["script_status"] != "approved":
            raise AudioProductionError("approved_script_required")
        if not row["preset_active"] or row["voice_status"] != "approved":
            raise AudioProductionError("eligible_narration_preset_required")
        if row["voice_expires_at"] is not None:
            from datetime import datetime, timezone

            expiry = row["voice_expires_at"]
            if expiry <= datetime.now(timezone.utc):
                raise AudioProductionError("approved_voice_expired")
        if str(row["provider"]).lower() not in self.kokoro.allowed_providers:
            raise AudioProductionError("local_kokoro_voice_required")
        return dict(row)

    def _locked(self, conn, production_id: UUID, expected_lock: int):
        row = conn.execute(
            """SELECT ap.*, amv.status AS mix_status, amv.version AS mix_version,
                      amv.target_lufs, amv.peak_limit_dbfs
               FROM football_brief.audio_productions ap
               LEFT JOIN football_brief.audio_mix_versions amv
                 ON amv.id=ap.current_mix_version_id
               WHERE ap.id=%s FOR UPDATE OF ap""",
            (production_id,),
        ).fetchone()
        if not row:
            raise AudioProductionError("audio_production_not_found")
        if int(row["lock_version"]) != expected_lock:
            raise AudioProductionError(
                "audio_production_conflict",
                details={"expected": expected_lock, "current": int(row["lock_version"])},
            )
        return row

    @staticmethod
    def _advance_lock(conn, *, production_id: UUID, expected_lock: int, actor: str) -> None:
        updated = conn.execute(
            """UPDATE football_brief.audio_productions
               SET lock_version=lock_version+1, last_edited_by=%s
               WHERE id=%s AND lock_version=%s RETURNING id""",
            (actor, production_id, expected_lock),
        ).fetchone()
        if not updated:
            raise AudioProductionError("audio_production_conflict")

    @staticmethod
    def _require_active_operator(conn, operator_id: str) -> None:
        row = conn.execute(
            "SELECT active FROM football_brief.operator_users WHERE operator_id=%s",
            (operator_id,),
        ).fetchone()
        if not row or not row["active"]:
            raise AudioProductionError("operator_inactive_or_missing")
