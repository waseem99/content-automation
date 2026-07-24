from __future__ import annotations

from array import array
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.application.audio.models import (
    AlignmentSource,
    MixRegistrationRequest,
    MixTrackRequest,
    TrackRole,
)
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class BuildLocalAudioMixRequest(BaseModel):
    expected_lock_version: int = Field(ge=1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_media_response(
    path: Path,
    *,
    artifact_root: Path,
    mime_type: str = "",
) -> FileResponse:
    candidate = path.resolve()
    if not candidate.is_file() or (
        candidate != artifact_root and artifact_root not in candidate.parents
    ):
        raise HTTPException(status_code=404, detail="local_media_unavailable")
    guessed = mimetypes.guess_type(candidate.name)[0]
    media_type = mime_type.strip() or guessed or "application/octet-stream"
    if not media_type.startswith(("audio/", "image/", "video/")):
        raise HTTPException(status_code=415, detail="unsupported_local_media_type")
    response = FileResponse(candidate, media_type=media_type, filename=candidate.name)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _concat_manifest_line(path: Path) -> str:
    # FFmpeg concat manifests accept forward-slash absolute paths on Windows.
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def _run_ffmpeg(
    executable: str,
    arguments: list[str],
    *,
    failure_code: str,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout or "ffmpeg failed")[-3000:]
        raise HTTPException(
            status_code=500,
            detail={"code": failure_code, "diagnostic": diagnostic},
        )
    return completed


def _finite_metric(value: Any, *, name: str) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "local_audio_measurement_invalid", "metric": name},
        ) from exc
    if not math.isfinite(number):
        raise HTTPException(
            status_code=500,
            detail={"code": "local_audio_measurement_invalid", "metric": name},
        )
    return number


def _probe_loudness(executable: str, path: Path) -> tuple[float, float]:
    completed = _run_ffmpeg(
        executable,
        [
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        failure_code="local_audio_loudness_probe_failed",
    )
    diagnostic = f"{completed.stderr}\n{completed.stdout}"
    payload: dict[str, Any] | None = None
    for candidate in reversed(re.findall(r"\{[^{}]+\}", diagnostic, flags=re.DOTALL)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if "input_i" in parsed and "input_tp" in parsed:
            payload = parsed
            break
    if payload is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "local_audio_loudness_evidence_missing"},
        )
    return (
        _finite_metric(payload["input_i"], name="integrated_lufs"),
        _finite_metric(payload["input_tp"], name="true_peak_dbfs"),
    )


def _wave_quality(path: Path) -> dict[str, float | int]:
    with wave.open(str(path), "rb") as handle:
        sample_rate = int(handle.getframerate())
        channels = int(handle.getnchannels())
        sample_width = int(handle.getsampwidth())
        frame_count = int(handle.getnframes())
        frames = handle.readframes(frame_count)
    if sample_width != 2 or channels != 1 or sample_rate <= 0 or frame_count <= 0:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "local_audio_wave_contract_invalid",
                "sample_rate_hz": sample_rate,
                "channels": channels,
                "sample_width_bytes": sample_width,
            },
        )
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        raise HTTPException(status_code=500, detail="local_audio_wave_is_empty")
    clipping_count = sum(1 for sample in samples if abs(sample) >= 32767)
    silence_threshold = 33  # approximately -60 dBFS for signed 16-bit PCM.
    silence_ratio = sum(1 for sample in samples if abs(sample) <= silence_threshold) / len(samples)
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "duration_seconds": frame_count / sample_rate,
        "clipping_count": clipping_count,
        "silence_ratio": round(silence_ratio, 6),
    }


def _register_local_audio_asset(
    database: Database,
    *,
    path: Path,
    production_id: UUID,
    mix_version_id: UUID,
    selected_take_ids: list[str],
    role: str,
    actor: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    digest = _sha256(path)
    metadata = {
        "storage_path": str(path),
        "audio_production_id": str(production_id),
        "audio_mix_version_id": str(mix_version_id),
        "selected_take_ids": selected_take_ids,
        "audio_role": role,
        "local_only": True,
        "external_fee_incurred": False,
        "generated_by": "studio_v2_local_ffmpeg_mix",
        **dict(extra_metadata or {}),
    }
    storage_uri = f"local-artifact://audio-mixes/{production_id}/{path.name}"
    with database.transaction() as conn:
        existing = conn.execute(
            "SELECT id,metadata FROM football_brief.assets WHERE sha256=%s",
            (digest,),
        ).fetchone()
        if existing is not None:
            existing_metadata = dict(existing["metadata"] or {})
            if existing_metadata.get("audio_role") != role:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "local_audio_asset_role_collision",
                        "sha256": digest,
                        "requested_role": role,
                    },
                )
            return {
                "id": existing["id"],
                "sha256": digest,
                "storage_uri": storage_uri,
                "metadata": existing_metadata,
            }
        row = conn.execute(
            """INSERT INTO football_brief.assets
               (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                sha256,mime_type,size_bytes,metadata,created_by)
               VALUES ('audio','ai_generated','approved',%s,%s,%s,
                       'audio/wav',%s,%s::jsonb,%s)
               RETURNING id""",
            (
                path.name,
                storage_uri,
                digest,
                path.stat().st_size,
                json.dumps(metadata),
                actor,
            ),
        ).fetchone()
    return {
        "id": row["id"],
        "sha256": digest,
        "storage_uri": storage_uri,
        "metadata": metadata,
    }


def install_studio_v2_media_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "studio_v2_media_routes_installed", False):
        return
    app.state.studio_v2_media_routes_installed = True
    access = OperatorAccessService(database) if database is not None else None
    audio = AudioProductionService(database) if database is not None else None
    artifact_root = Path(
        os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")
    ).resolve()

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def production_brand_id(production_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.portfolio_content pc ON pc.id=ap.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE ap.id=%s""",
                (production_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="audio_production_not_found")
        return str(row["brand_id"])

    @app.get("/studio-v2/jobs/{job_id}/media", include_in_schema=False)
    def local_job_media(
        job_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> FileResponse:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT gj.status,gj.output_payload,mp.brand_id
                   FROM football_brief.generation_jobs gj
                   JOIN football_brief.portfolio_content pc ON pc.id=gj.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE gj.id=%s""",
                (job_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="generation_job_not_found")
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=str(row["brand_id"]),
        )
        if row["status"] != "succeeded":
            raise HTTPException(status_code=409, detail="generation_job_not_succeeded")
        output = dict(row["output_payload"] or {})
        return _safe_media_response(
            Path(str(output.get("storage_path") or "")),
            artifact_root=artifact_root,
            mime_type=str(output.get("mime_type") or ""),
        )

    @app.post("/studio-v2/audio/{production_id}/build-local-mix")
    def build_local_audio_mix(
        production_id: UUID,
        request: BuildLocalAudioMixRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, object]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        if audio is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        ffmpeg = shutil.which(os.getenv("LOCAL_FFMPEG_PATH", "ffmpeg"))
        if not ffmpeg:
            raise HTTPException(status_code=503, detail="ffmpeg_not_available")

        detail = audio.detail(production_id=production_id)
        production = detail["production"]
        if int(production["lock_version"]) != request.expected_lock_version:
            raise HTTPException(status_code=409, detail="audio_production_conflict")
        current_mix = next(
            (
                item
                for item in detail["mixes"]
                if str(item["id"]) == str(production["current_mix_version_id"])
            ),
            None,
        )
        if current_mix and current_mix.get("final_mix_asset_id"):
            return {
                "ok": True,
                "kind": "studio_v2_local_audio_mix",
                "reused": True,
                **detail,
            }
        if production["status"] not in {"working", "changes_requested"}:
            raise HTTPException(status_code=409, detail="audio_production_not_writable")

        selected: list[dict[str, Any]] = []
        with require_database().connection() as conn:
            rows = conn.execute(
                """SELECT apar.id AS paragraph_id,apar.sequence,ast.id AS take_id,
                          ast.asset_id,ast.duration_seconds,ast.timing_source,
                          ast.silence_ratio,gj.output_payload
                   FROM football_brief.audio_paragraphs apar
                   LEFT JOIN football_brief.audio_segment_takes ast
                     ON ast.paragraph_id=apar.id AND ast.status='selected'
                   LEFT JOIN football_brief.generation_jobs gj ON gj.id=ast.generation_job_id
                   WHERE apar.audio_production_id=%s ORDER BY apar.sequence""",
                (production_id,),
            ).fetchall()
        if not rows or any(row["take_id"] is None for row in rows):
            raise HTTPException(
                status_code=422,
                detail="selected_take_required_for_every_paragraph",
            )
        for row in rows:
            output = dict(row["output_payload"] or {})
            source = Path(str(output.get("storage_path") or "")).resolve()
            if not source.is_file() or (
                source != artifact_root and artifact_root not in source.parents
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "selected_take_media_unavailable",
                        "paragraph_id": str(row["paragraph_id"]),
                    },
                )
            selected.append({**dict(row), "source": source})

        output_dir = artifact_root / "audio-mixes" / str(production_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        mix_version = int(production.get("current_mix_version") or 1)
        manifest = output_dir / f"mix-v{mix_version}-concat.txt"
        narration_path = output_dir / f"narration-v{mix_version}.wav"
        output_path = output_dir / f"mix-v{mix_version}.wav"
        manifest.write_text(
            "\n".join(_concat_manifest_line(item["source"]) for item in selected) + "\n",
            encoding="utf-8",
        )

        _run_ffmpeg(
            ffmpeg,
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest),
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(narration_path),
            ],
            failure_code="local_audio_narration_stem_failed",
        )
        if not narration_path.is_file() or narration_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="local_audio_narration_stem_missing")

        _run_ffmpeg(
            ffmpeg,
            [
                "-y",
                "-i",
                str(narration_path),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-metadata",
                "comment=Content Engine normalized final mix",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            failure_code="local_audio_mix_failed",
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="local_audio_mix_missing")
        if _sha256(narration_path) == _sha256(output_path):
            raise HTTPException(
                status_code=500,
                detail="local_audio_stem_and_mix_must_have_distinct_evidence",
            )

        measured_lufs, true_peak_dbfs = _probe_loudness(ffmpeg, output_path)
        quality = _wave_quality(output_path)
        selected_take_ids = [str(item["take_id"]) for item in selected]
        db = require_database()
        narration_asset = _register_local_audio_asset(
            db,
            path=narration_path,
            production_id=production_id,
            mix_version_id=production["current_mix_version_id"],
            selected_take_ids=selected_take_ids,
            role="narration_stem",
            actor=operator.operator_id,
            extra_metadata={"normalization": "none", "source": "selected_kokoro_takes"},
        )
        final_asset = _register_local_audio_asset(
            db,
            path=output_path,
            production_id=production_id,
            mix_version_id=production["current_mix_version_id"],
            selected_take_ids=selected_take_ids,
            role="final_mix",
            actor=operator.operator_id,
            extra_metadata={
                "normalization": "ebu-r128",
                "narration_asset_id": str(narration_asset["id"]),
                "measured_lufs": measured_lufs,
                "true_peak_dbfs": true_peak_dbfs,
            },
        )
        alignment = (
            AlignmentSource.FORCED_ALIGNMENT
            if {str(item["timing_source"]) for item in selected}
            == {AlignmentSource.FORCED_ALIGNMENT.value}
            else AlignmentSource.PROPORTIONAL_PREVIEW
        )
        try:
            mixed = audio.register_mix(
                production_id=production_id,
                request=MixRegistrationRequest(
                    expected_lock_version=request.expected_lock_version,
                    narration_asset_id=narration_asset["id"],
                    final_mix_asset_id=final_asset["id"],
                    target_lufs=-16.0,
                    peak_limit_dbfs=-1.0,
                    measured_lufs=measured_lufs,
                    true_peak_dbfs=true_peak_dbfs,
                    clipping_count=int(quality["clipping_count"]),
                    silence_ratio=float(quality["silence_ratio"]),
                    duration_seconds=float(quality["duration_seconds"]),
                    waveform_metadata={
                        "sample_rate_hz": int(quality["sample_rate_hz"]),
                        "channels": int(quality["channels"]),
                        "source": "local_ffmpeg",
                        "loudness_measurement": "ffmpeg_loudnorm_json_probe",
                        "selected_segment_count": len(selected),
                    },
                    segment_snapshot=[
                        {
                            "paragraph_id": str(item["paragraph_id"]),
                            "take_id": str(item["take_id"]),
                        }
                        for item in selected
                    ],
                    mix_settings={
                        "normalization": "ebu-r128",
                        "target_lufs": -16.0,
                        "true_peak_dbfs": -1.5,
                        "local": True,
                        "separate_narration_and_final_assets": True,
                    },
                    alignment_source=alignment,
                    tracks=[
                        MixTrackRequest(
                            track_role=TrackRole.NARRATION,
                            asset_id=narration_asset["id"],
                            level_db=0,
                            metadata={"local_narration_stem": True},
                        )
                    ],
                ),
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise HTTPException(
                status_code=409 if "conflict" in exc.code else 422,
                detail={"code": exc.code, **exc.details},
            ) from exc
        return {
            "ok": True,
            "kind": "studio_v2_local_audio_mix",
            "reused": False,
            "narration_storage_uri": narration_asset["storage_uri"],
            "storage_uri": final_asset["storage_uri"],
            **mixed,
        }

    @app.get(
        "/studio-v2/audio/{production_id}/mix-media",
        include_in_schema=False,
    )
    def local_audio_mix_media(
        production_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> FileResponse:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=production_brand_id(production_id),
        )
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT a.mime_type,a.metadata
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.audio_mix_versions amv
                     ON amv.id=ap.current_mix_version_id
                   JOIN football_brief.assets a ON a.id=amv.final_mix_asset_id
                   WHERE ap.id=%s""",
                (production_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="audio_mix_media_unavailable")
        metadata = dict(row["metadata"] or {})
        return _safe_media_response(
            Path(str(metadata.get("storage_path") or "")),
            artifact_root=artifact_root,
            mime_type=str(row["mime_type"] or "audio/wav"),
        )


__all__ = ["BuildLocalAudioMixRequest", "install_studio_v2_media_routes"]
