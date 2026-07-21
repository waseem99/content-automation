from __future__ import annotations

from pathlib import Path

import pytest

from src.application.audio.models import (
    AlignmentSource,
    AudioDecision,
    MixRegistrationRequest,
    MixTrackRequest,
    TrackRole,
)
from src.application.shared_storage.models import StorageBackendRequest
from src.application.shared_storage.providers import LocalSharedStorageProvider
from src.application.shared_storage.runtime import SharedProviderRegistry
from src.application.shared_storage.service import SharedArtifactService
from tests.integration.p90_audio_support import (
    p89_database,
    p89_seeded as p89_seeded_fixture,
    p90_ready as p90_ready_fixture,
)
from tests.integration.p95_shared_storage_support import register_asset, write_asset
from tests.integration.test_p90_audio_lifecycle import initialize_and_select_takes


pytestmark = pytest.mark.integration


@pytest.fixture()
def p96_ready(p89_database, tmp_path) -> dict[str, object]:
    seeded = p89_seeded_fixture.__wrapped__(p89_database)
    p90_ready = p90_ready_fixture.__wrapped__(p89_database, seeded)
    source_root = tmp_path / "p96-canonical"
    shared_root = tmp_path / "p96-shared"

    narration_path = write_asset(
        source_root,
        "approved-narration.wav",
        b"P96 approved narration audio bytes\n" * 80,
    )
    final_mix_path = write_asset(
        source_root,
        "approved-final-mix.wav",
        b"P96 approved final mix audio bytes\n" * 90,
    )
    visual_path = write_asset(
        source_root,
        "approved-visual.mp4",
        b"P96 approved visual bytes\n" * 100,
    )
    branding_path = write_asset(
        source_root,
        "approved-branding.png",
        b"\x89PNG\r\n\x1a\nP96 approved branding bytes",
    )
    output_path = write_asset(
        source_root,
        "final-release-output.mp4",
        b"P96 final release output bytes\n" * 120,
    )

    narration_asset = register_asset(
        p89_database,
        path=narration_path,
        asset_type="audio",
        created_by=p90_ready["producer"],
    )
    final_mix_asset = register_asset(
        p89_database,
        path=final_mix_path,
        asset_type="audio",
        created_by=p90_ready["producer"],
    )
    visual_asset = register_asset(
        p89_database,
        path=visual_path,
        asset_type="video",
        created_by=p90_ready["producer"],
    )
    branding_asset = register_asset(
        p89_database,
        path=branding_path,
        asset_type="image",
        created_by=p90_ready["producer"],
    )
    output_asset = register_asset(
        p89_database,
        path=output_path,
        asset_type="video",
        created_by=p90_ready["producer"],
    )

    audio_service, detail = initialize_and_select_takes(
        p89_database,
        p90_ready,
        timing_source=AlignmentSource.FORCED_ALIGNMENT,
    )
    production_id = detail["production"]["id"]
    mixed = audio_service.register_mix(
        production_id=production_id,
        request=MixRegistrationRequest(
            expected_lock_version=detail["production"]["lock_version"],
            narration_asset_id=narration_asset,
            final_mix_asset_id=final_mix_asset,
            target_lufs=-16.0,
            peak_limit_dbfs=-1.0,
            measured_lufs=-16.1,
            true_peak_dbfs=-1.5,
            clipping_count=0,
            silence_ratio=0.05,
            duration_seconds=60,
            waveform_metadata={"peaks": [0.1, 0.3, 0.2], "sample_rate_hz": 24000},
            segment_snapshot=[
                {"paragraph_id": str(paragraph["id"]), "validated_by_service": True}
                for paragraph in detail["paragraphs"]
            ],
            mix_settings={"normalization": "ebu-r128", "local": True, "phase": "P96"},
            alignment_source=AlignmentSource.FORCED_ALIGNMENT,
            tracks=[
                MixTrackRequest(
                    track_role=TrackRole.NARRATION,
                    asset_id=narration_asset,
                    level_db=0,
                )
            ],
        ),
        actor=p90_ready["producer"],
    )
    submitted = audio_service.submit(
        production_id=production_id,
        expected_lock_version=mixed["production"]["lock_version"],
        actor=p90_ready["producer"],
    )
    approved = audio_service.decide(
        production_id=production_id,
        expected_lock_version=submitted["production"]["lock_version"],
        decision=AudioDecision.APPROVED,
        rationale="Forced alignment, exact selected takes, QC, loudness, peak, and final mix all pass for P96.",
        reviewer=p90_ready["reviewer"],
    )
    audio_mix_version_id = approved["production"]["current_mix_version_id"]

    shared_provider = LocalSharedStorageProvider(
        backend_key="p96-shared",
        root=shared_root,
    )
    registry = SharedProviderRegistry(
        providers={shared_provider.backend_key: shared_provider}
    )
    shared_service = SharedArtifactService(
        p89_database,
        providers=registry,
        public_base_url="https://release-review.example.test",
    )
    backend = shared_service.create_backend(
        request=StorageBackendRequest(
            backend_key="p96-shared",
            display_name="P96 Shared Storage",
            driver="local",
            environment="test",
            configuration={"root": str(shared_root), "phase": "P96"},
        ),
        actor=p90_ready["admin"],
    )["backend"]
    backend = shared_service.activate_backend(
        backend_id=backend["id"],
        actor=p90_ready["admin"],
    )["backend"]
    with p89_database.connection() as conn:
        content_version = int(
            conn.execute(
                "SELECT version FROM football_brief.portfolio_content WHERE id=%s",
                (p90_ready["content_one"],),
            ).fetchone()["version"]
        )

    return {
        **p90_ready,
        "content_one_version": content_version,
        "audio_production_id": production_id,
        "audio_mix_version_id": audio_mix_version_id,
        "assets": {
            "narration": narration_asset,
            "final_mix": final_mix_asset,
            "visual": visual_asset,
            "branding": branding_asset,
            "output": output_asset,
        },
        "paths": {
            "narration": narration_path,
            "final_mix": final_mix_path,
            "visual": visual_path,
            "branding": branding_path,
            "output": output_path,
        },
        "shared_root": shared_root,
        "registry": registry,
        "service": shared_service,
        "shared_backend": backend,
    }
