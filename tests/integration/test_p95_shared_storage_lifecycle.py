from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import psycopg
import pytest

from src.application.shared_storage.models import (
    ArtifactVersionRequest,
    BackupPrepareRequest,
    DeletionRequest,
    LegalHoldRequest,
    RestoreVerifyRequest,
    SignedAccessRequest,
)
from src.application.shared_storage.service import SharedArtifactError
from tests.integration.p95_shared_storage_support import (
    p93_database,
    p93_seeded,
    p95_ready,
)


pytestmark = pytest.mark.integration


def artifact_request(ready, *, next_version=False, retention_until=None, artifact_key="release/main"):
    assets = ready["assets"]
    return ArtifactVersionRequest(
        brand_id=ready["brand_one"],
        portfolio_content_id=ready["content_one"],
        content_version=ready["content_one_version"],
        artifact_key=artifact_key,
        artifact_kind="final_video",
        original_asset_id=assets["next_original"] if next_version else assets["original"],
        review_proxy_asset_id=assets["next_proxy"] if next_version else assets["proxy"],
        thumbnail_asset_id=assets["thumbnail"],
        backend_id=ready["shared_backend"]["id"],
        retention_until=retention_until,
        metadata={"phase": "P95", "version_label": "v2" if next_version else "v1"},
    )


def token_from_url(url: str) -> str:
    return parse_qs(urlsplit(url).query)["token"][0]


def test_remote_signed_access_expiry_revocation_and_version_history(
    p93_database,
    p95_ready,
    monkeypatch,
) -> None:
    service = p95_ready["service"]
    version_one = service.create_artifact_version(
        request=artifact_request(p95_ready),
        actor=p95_ready["producer"],
    )
    assert version_one["artifact"]["version"] == 1
    assert version_one["artifact"]["status"] == "current"
    assert {item["role"] for item in version_one["objects"]} == {
        "original", "review_proxy", "thumbnail"
    }
    assert all(item["status"] == "available" for item in version_one["objects"])
    assert all(Path(item["storage_uri"].replace("shared+local:///shared-test/", str(p95_ready["shared_root"]) + "/")).exists() for item in [])

    access = service.issue_access(
        artifact_version_id=version_one["artifact"]["id"],
        request=SignedAccessRequest(
            role="review_proxy",
            expires_in_seconds=300,
            issued_to_operator_id=p95_ready["reviewer"],
            access_purpose="review",
        ),
        actor=p95_ready["reviewer"],
    )
    assert access.url.startswith("https://review.example.test/shared-media/")
    token = token_from_url(access.url)
    target = service.consume_access(
        grant_id=access.grant_id,
        token=token,
        remote_address="203.0.113.44",
        user_agent="P95 remote reviewer",
    )
    assert target.kind == "file"
    assert Path(target.value).read_bytes() == p95_ready["paths"]["proxy"].read_bytes()

    with p93_database.connection() as conn:
        grant = conn.execute(
            "SELECT token_digest FROM football_brief.shared_access_grants WHERE id=%s",
            (access.grant_id,),
        ).fetchone()
        events = conn.execute(
            "SELECT event,remote_address_hash,user_agent_hash FROM football_brief.shared_access_events WHERE grant_id=%s ORDER BY created_at,id",
            (access.grant_id,),
        ).fetchall()
    assert token not in grant["token_digest"]
    assert [row["event"] for row in events] == ["issued", "accessed"]
    assert events[-1]["remote_address_hash"] is not None
    assert events[-1]["user_agent_hash"] is not None

    version_two = service.create_artifact_version(
        request=artifact_request(p95_ready, next_version=True),
        actor=p95_ready["producer"],
    )
    assert version_two["artifact"]["version"] == 2
    assert version_two["artifact"]["parent_version_id"] == version_one["artifact"]["id"]
    assert version_two["artifact"]["status"] == "current"
    retained_one = service.detail(artifact_version_id=version_one["artifact"]["id"])
    assert retained_one["artifact"]["status"] == "superseded"
    old_target = service.consume_access(grant_id=access.grant_id, token=token)
    assert Path(old_target.value).read_bytes() == p95_ready["paths"]["proxy"].read_bytes()

    revoked = service.issue_access(
        artifact_version_id=version_two["artifact"]["id"],
        request=SignedAccessRequest(role="review_proxy", expires_in_seconds=300),
        actor=p95_ready["reviewer"],
    )
    service.revoke_access(grant_id=revoked.grant_id, actor=p95_ready["reviewer"])
    with pytest.raises(SharedArtifactError, match="access_grant_revoked"):
        service.consume_access(grant_id=revoked.grant_id, token=token_from_url(revoked.url))

    expired = service.issue_access(
        artifact_version_id=version_two["artifact"]["id"],
        request=SignedAccessRequest(role="review_proxy", expires_in_seconds=30),
        actor=p95_ready["reviewer"],
    )
    import src.application.shared_storage.service as service_module

    monkeypatch.setattr(service_module, "_utcnow", lambda: expired.expires_at + timedelta(seconds=1))
    with pytest.raises(SharedArtifactError, match="access_grant_expired"):
        service.consume_access(grant_id=expired.grant_id, token=token_from_url(expired.url))


def test_legal_hold_and_retention_block_then_allow_shared_deletion(
    p93_database,
    p95_ready,
) -> None:
    service = p95_ready["service"]
    import src.application.shared_storage.service as service_module

    artifact = service.create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=p95_ready["brand_one"],
            portfolio_content_id=p95_ready["content_one"],
            content_version=p95_ready["content_one_version"],
            artifact_key="retention/delete-test",
            artifact_kind="preview",
            original_asset_id=p95_ready["assets"]["deletion"],
            backend_id=p95_ready["shared_backend"]["id"],
            retention_until=service_module._utcnow() - timedelta(days=1),
            metadata={"purpose": "retention-test"},
        ),
        actor=p95_ready["producer"],
    )
    artifact_id = artifact["artifact"]["id"]
    service.set_legal_hold(
        artifact_version_id=artifact_id,
        request=LegalHoldRequest(enabled=True, reason="Preserve for an active compliance review."),
        actor=p95_ready["admin"],
    )
    with pytest.raises(psycopg.Error, match="Legal hold blocks artifact deletion"):
        service.delete_artifact(
            artifact_version_id=artifact_id,
            request=DeletionRequest(rationale="Attempt deletion during legal hold."),
            actor=p95_ready["admin"],
        )
    assert service.detail(artifact_version_id=artifact_id)["artifact"]["status"] == "current"

    service.set_legal_hold(
        artifact_version_id=artifact_id,
        request=LegalHoldRequest(enabled=False),
        actor=p95_ready["admin"],
    )
    deleted = service.delete_artifact(
        artifact_version_id=artifact_id,
        request=DeletionRequest(rationale="Retention has expired and legal hold is released."),
        actor=p95_ready["admin"],
    )
    assert deleted["artifact"]["status"] == "deleted"
    assert deleted["deleted_object_count"] == 1
    with p93_database.connection() as conn:
        object_row = conn.execute(
            """SELECT sso.status,sso.deleted_at
               FROM football_brief.shared_artifact_object_roles saor
               JOIN football_brief.shared_storage_objects sso ON sso.id=saor.storage_object_id
               WHERE saor.artifact_version_id=%s""",
            (artifact_id,),
        ).fetchone()
    assert object_row["status"] == "deleted"
    assert object_row["deleted_at"] is not None


def test_backup_restore_drill_verifies_database_metadata_and_object_checksums(
    p93_database,
    p95_ready,
) -> None:
    service = p95_ready["service"]
    artifact = service.create_artifact_version(
        request=artifact_request(p95_ready, artifact_key="backup/main"),
        actor=p95_ready["producer"],
    )
    snapshot = service.prepare_backup(
        request=BackupPrepareRequest(
            backend_id=p95_ready["shared_backend"]["id"],
            metadata={"drill": "P95", "artifact_version_id": str(artifact["artifact"]["id"])},
        ),
        actor=p95_ready["admin"],
    )["snapshot"]
    assert snapshot["status"] == "prepared"
    assert snapshot["artifact_count"] == 1
    assert snapshot["object_count"] == 3
    assert snapshot["total_size_bytes"] > 0

    shutil.copytree(
        p95_ready["shared_root"],
        p95_ready["restore_root"],
        dirs_exist_ok=True,
    )
    verified = service.verify_restore(
        snapshot_id=snapshot["id"],
        request=RestoreVerifyRequest(
            restored_backend_key="shared-restore",
            verifier_label="P95 restore drill",
        ),
        actor=p95_ready["admin"],
    )
    assert verified["ok"] is True
    assert verified["snapshot"]["status"] == "verified"
    assert len(verified["verifications"]) == 3
    assert all(row["metadata_matches"] for row in verified["verifications"])
    assert all(row["checksum_matches"] for row in verified["verifications"])
    assert all(row["status"] == "verified" for row in verified["verifications"])
