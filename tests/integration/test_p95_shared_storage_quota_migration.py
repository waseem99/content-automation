from __future__ import annotations

from datetime import timedelta

import psycopg
import pytest
from pydantic import ValidationError

from src.application.shared_storage.models import (
    ArtifactVersionRequest,
    ExistingAssetMigrationRequest,
    SignedAccessRequest,
    StorageQuotaRequest,
)
from src.application.shared_storage.service import SharedArtifactError, _utcnow
from src.application.shared_storage.validated_service import ValidatedSharedArtifactService
from tests.integration.p95_shared_storage_support import p93_database, p93_seeded, p95_ready


pytestmark = pytest.mark.integration


def validated_service(ready) -> ValidatedSharedArtifactService:
    return ValidatedSharedArtifactService(
        ready["service"].database,
        providers=ready["registry"],
        public_base_url="https://review.example.test",
    )


def test_versioned_quota_blocks_overflow_then_allows_deliberate_capacity_revision(
    p93_database,
    p95_ready,
) -> None:
    service = validated_service(p95_ready)
    original_size = p95_ready["paths"]["original"].stat().st_size
    proxy_size = p95_ready["paths"]["proxy"].stat().st_size
    first_limit = original_size + proxy_size - 1

    configured = service.configure_quota(
        request=StorageQuotaRequest(
            backend_id=p95_ready["shared_backend"]["id"],
            hard_limit_bytes=first_limit,
            warning_threshold_bytes=original_size,
        ),
        actor=p95_ready["admin"],
    )
    assert configured["quota"]["version"] == 1

    migrated = service.migrate_existing_assets(
        request=ExistingAssetMigrationRequest(
            backend_id=p95_ready["shared_backend"]["id"],
            asset_ids=(p95_ready["assets"]["original"],),
        ),
        actor=p95_ready["admin"],
    )
    assert migrated["ok"] is True
    assert migrated["migrated"] == 1
    assert migrated["quota"]["warning_exceeded"] is True

    with pytest.raises(psycopg.Error, match="quota exceeded"):
        service.migrate_existing_assets(
            request=ExistingAssetMigrationRequest(
                backend_id=p95_ready["shared_backend"]["id"],
                asset_ids=(p95_ready["assets"]["proxy"],),
            ),
            actor=p95_ready["admin"],
        )

    revised = service.configure_quota(
        request=StorageQuotaRequest(
            backend_id=p95_ready["shared_backend"]["id"],
            hard_limit_bytes=original_size + proxy_size + 1024,
            warning_threshold_bytes=original_size + proxy_size,
        ),
        actor=p95_ready["admin"],
    )
    assert revised["quota"]["version"] == 2
    assert revised["quota"]["parent_policy_id"] is not None

    second = service.migrate_existing_assets(
        request=ExistingAssetMigrationRequest(
            backend_id=p95_ready["shared_backend"]["id"],
            asset_ids=(p95_ready["assets"]["proxy"],),
        ),
        actor=p95_ready["admin"],
    )
    assert second["ok"] is True
    assert second["quota"]["consumed_bytes"] == original_size + proxy_size
    with p93_database.connection() as conn:
        policies = conn.execute(
            """SELECT version,status FROM football_brief.shared_storage_quota_policies
               WHERE backend_id=%s ORDER BY version""",
            (p95_ready["shared_backend"]["id"],),
        ).fetchall()
    assert [(row["version"], row["status"]) for row in policies] == [(1, "retired"), (2, "active")]


def test_review_access_requires_completed_proxy_at_model_service_and_database_boundaries(
    p93_database,
    p95_ready,
) -> None:
    service = validated_service(p95_ready)
    with pytest.raises(ValidationError, match="completed review proxy"):
        SignedAccessRequest(role="original", access_purpose="review")

    artifact = service.create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=p95_ready["brand_one"],
            portfolio_content_id=p95_ready["content_one"],
            content_version=p95_ready["content_one_version"],
            artifact_key="review/incomplete",
            artifact_kind="preview",
            original_asset_id=p95_ready["assets"]["original"],
            backend_id=p95_ready["shared_backend"]["id"],
            retention_until=_utcnow() + timedelta(days=30),
        ),
        actor=p95_ready["producer"],
    )
    with pytest.raises(SharedArtifactError, match="shared_artifact_role_not_available"):
        service.issue_access(
            artifact_version_id=artifact["artifact"]["id"],
            request=SignedAccessRequest(role="review_proxy", access_purpose="review"),
            actor=p95_ready["reviewer"],
        )

    with p93_database.connection() as conn:
        original_object = conn.execute(
            """SELECT saor.storage_object_id
               FROM football_brief.shared_artifact_object_roles saor
               WHERE saor.artifact_version_id=%s AND saor.role='original'""",
            (artifact["artifact"]["id"],),
        ).fetchone()
    with pytest.raises(psycopg.Error, match="completed review proxy"):
        with p93_database.transaction() as conn:
            conn.execute(
                """INSERT INTO football_brief.shared_access_grants
                   (artifact_version_id,storage_object_id,brand_id,access_purpose,
                    token_digest,expires_at,created_by)
                   VALUES (%s,%s,%s,'review',%s,now()+interval '5 minutes',%s)""",
                (
                    artifact["artifact"]["id"],
                    original_object["storage_object_id"],
                    p95_ready["brand_one"],
                    "a" * 64,
                    p95_ready["reviewer"],
                ),
            )
