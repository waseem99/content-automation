import json
from pathlib import Path

from refintel.models import (
    Platform,
    ProjectStatus,
    ReferenceProject,
    RightsDeclaration,
    SourceAccess,
    SourceDescriptor,
)
from refintel.portfolio_sync import build_portfolio_sync_packet


def test_sync_packet_contains_only_sanitized_review_metadata(tmp_path: Path) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "original.mp4").write_bytes(b"source-media-must-not-sync")
    (tmp_path / "frames").mkdir()
    (tmp_path / "frames" / "contact_sheet.jpg").write_bytes(b"review-sheet")
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "reference_fingerprint.json").write_text(
        json.dumps({"schema_version": "p66.reference_fingerprint.v1", "status": "ready"})
    )
    project = ReferenceProject(
        reference_id="ref-safe-01",
        status=ProjectStatus.COMPLETE,
        source=SourceDescriptor(
            kind="url",
            platform=Platform.FACEBOOK,
            original_url="https://facebook.com/reel/123?token=private&view=1#fragment",
            title="Authorized research sample",
            canonical_key="url:facebook-123",
        ),
        access=SourceAccess(declaration=RightsDeclaration.PERMITTED),
        workspace_path=str(tmp_path),
        errors=[f"token=secret failed at {tmp_path}/source/original.mp4"],
    )

    packet = build_portfolio_sync_packet(project, tmp_path)
    rendered = (tmp_path / "exports" / "portfolio_sync_packet.json").read_text()

    assert packet.source_url == "https://facebook.com/reel/123?view=1"
    assert {item.artifact_kind for item in packet.artifacts} == {
        "contact_sheet",
        "fingerprint",
    }
    assert "source-media-must-not-sync" not in rendered
    assert str(tmp_path) not in rendered
    assert "secret" not in rendered
    assert packet.source_media_included is False
    assert packet.automatic_generation is False
    assert packet.automatic_publication is False
    assert packet.human_review_required is True

