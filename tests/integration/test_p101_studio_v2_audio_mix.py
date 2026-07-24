from __future__ import annotations

import json
import wave
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.application.audio.adapters import proportional_preview_timings
from src.application.audio.models import AlignmentSource, AudioInitializeRequest, AudioTakeResult
from src.application.audio.service import AudioProductionService
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from src.operator_api.studio_v2_media_runtime import install_studio_v2_media_routes
from tests.integration.p89_script_support import p89_seeded
from tests.integration.p90_audio_support import (
    complete_next_narration_job,
    p89_database,
    p90_ready,
    register_audio_asset,
)


pytestmark = pytest.mark.integration


def _write_wave(path: Path, *, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 24000
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * seconds))


def _auth_settings(ready) -> OperatorAuthSettings:
    brand_one = str(ready["brand_one"])
    brand_two = str(ready["brand_two"])
    identities = {
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["outsider"]: OperatorIdentity(
            operator_id=str(ready["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_two}),
            active=True,
        ),
    }
    return OperatorAuthSettings(
        api_keys={
            "producer-key": str(ready["producer"]),
            "reviewer-key": str(ready["reviewer"]),
            "outsider-key": str(ready["outsider"]),
        },
        identities=identities,
    )


def test_studio_builds_brand_scoped_local_mix_and_unlocks_submit(
    p89_database,
    p90_ready,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("LOCAL_ARTIFACT_ROOT", str(artifact_root))
    service = AudioProductionService(p89_database)
    initialized = service.initialize(
        content_id=p90_ready["content_one"],
        request=AudioInitializeRequest(model_id="kokoro-v1.0"),
        actor=p90_ready["producer"],
    )
    production_id = initialized["production"]["id"]

    for index in range(len(initialized["paragraphs"])):
        job = complete_next_narration_job(
            p89_database,
            worker=p90_ready["producer"],
            brand_id=p90_ready["brand_one"],
        )
        detail = service.detail(production_id=production_id)
        take = next(
            row
            for row in detail["takes"]
            if str(row["generation_job_id"]) == str(job["id"])
        )
        paragraph = next(
            row
            for row in detail["paragraphs"]
            if str(row["id"]) == str(take["paragraph_id"])
        )
        source = artifact_root / "jobs" / str(job["id"]) / "narration.wav"
        _write_wave(source)
        with p89_database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.generation_jobs
                   SET output_payload=%s::jsonb WHERE id=%s""",
                (
                    json.dumps(
                        {
                            "storage_path": str(source),
                            "mime_type": "audio/wav",
                            "kind": "local_kokoro_narration",
                            "external_fee_incurred": False,
                        }
                    ),
                    job["id"],
                ),
            )
        asset_id = register_audio_asset(
            p89_database,
            key=f"studio-v2-segment-{production_id}-{index}",
            created_by=p90_ready["producer"],
        )
        timings = proportional_preview_timings(paragraph["source_text"], 0.25)
        service.register_take_result(
            take_id=take["id"],
            result=AudioTakeResult(
                asset_id=asset_id,
                duration_seconds=0.25,
                sample_rate_hz=24000,
                channels=1,
                integrated_lufs=-16.0,
                true_peak_dbfs=-1.5,
                clipping_count=0,
                silence_ratio=0.05,
                timing_source=AlignmentSource.FORCED_ALIGNMENT,
                word_timings=timings,
                qc_evidence={"local_worker": True, "external_fee_incurred": False},
            ),
            actor=p90_ready["producer"],
        )
        refreshed = service.detail(production_id=production_id)
        service.select_take(
            production_id=production_id,
            take_id=take["id"],
            expected_lock_version=refreshed["production"]["lock_version"],
            actor=p90_ready["producer"],
        )

    def fake_ffmpeg(arguments, **_kwargs):
        _write_wave(Path(arguments[-1]), seconds=0.5)
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(
        "src.operator_api.studio_v2_media_runtime.shutil.which",
        lambda _value: "/fake/ffmpeg",
    )
    monkeypatch.setattr(
        "src.operator_api.studio_v2_media_runtime.subprocess.run",
        fake_ffmpeg,
    )

    auth = _auth_settings(p90_ready)
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    app = create_configured_app(
        database=p89_database,
        auth_settings=auth,
        runtime_settings=runtime,
    )
    install_studio_v2_media_routes(
        app,
        database=p89_database,
        auth_settings=auth,
    )
    client = TestClient(app)
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}

    before_mix = service.detail(production_id=production_id)
    forbidden = client.post(
        f"/studio-v2/audio/{production_id}/build-local-mix",
        headers=outsider,
        json={"expected_lock_version": before_mix["production"]["lock_version"]},
    )
    assert forbidden.status_code == 403

    mixed = client.post(
        f"/studio-v2/audio/{production_id}/build-local-mix",
        headers=producer,
        json={"expected_lock_version": before_mix["production"]["lock_version"]},
    )
    assert mixed.status_code == 200, mixed.text
    body = mixed.json()
    assert body["ok"] is True
    assert body["reused"] is False
    assert body["production"]["current_mix_status"] == "working"
    assert body["mixes"][0]["final_mix_asset_id"] is not None
    assert body["mixes"][0]["qc_status"] == "pass"
    assert body["mixes"][0]["alignment_source"] == "forced_alignment"

    reviewer_media = client.get(
        f"/studio-v2/audio/{production_id}/mix-media",
        headers=reviewer,
    )
    assert reviewer_media.status_code == 200
    assert reviewer_media.headers["content-type"].startswith("audio/wav")
    assert reviewer_media.headers["cache-control"] == "private, no-store"
    assert client.get(
        f"/studio-v2/audio/{production_id}/mix-media",
        headers=outsider,
    ).status_code == 403

    submitted = client.post(
        f"/audio/{production_id}/submit",
        headers=producer,
        json={"expected_lock_version": body["production"]["lock_version"]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["production"]["status"] == "in_review"
