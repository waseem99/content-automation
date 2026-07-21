from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from src.application.assets.hashing import inspect_file
from src.application.shared_storage.models import StorageBackendRequest
from src.application.shared_storage.providers import LocalSharedStorageProvider
from src.application.shared_storage.runtime import SharedProviderRegistry
from src.application.shared_storage.service import SharedArtifactService
from tests.integration.p93_renderer_support import p93_database, p93_seeded


pytestmark = pytest.mark.integration


def register_asset(database, *, path: Path, asset_type: str, created_by: str) -> UUID:
    inspected = inspect_file(path)
    with database.transaction() as conn:
        row = conn.execute(
            """INSERT INTO football_brief.assets
               (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                sha256,mime_type,size_bytes,metadata,created_by)
               VALUES (%s,'client_supplied','approved',%s,%s,%s,%s,%s,%s::jsonb,%s)
               RETURNING id""",
            (
                asset_type,
                path.name,
                path.resolve().as_uri(),
                inspected.sha256,
                inspected.mime_type,
                inspected.size_bytes,
                '{"phase":"P95","fixture":true}',
                created_by,
            ),
        ).fetchone()
    return row["id"]


def write_asset(root: Path, name: str, payload: bytes) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_bytes(payload)
    return path


@pytest.fixture()
def p95_ready(p93_database, p93_seeded, tmp_path) -> dict[str, object]:
    source_root = tmp_path / "canonical"
    shared_root = tmp_path / "shared"
    restore_root = tmp_path / "restore"

    original_path = write_asset(source_root, "original.mp4", b"P95 original video bytes\n" * 40)
    proxy_path = write_asset(source_root, "review-proxy.mp4", b"P95 review proxy bytes\n" * 25)
    thumbnail_path = write_asset(source_root, "thumbnail.png", b"\x89PNG\r\n\x1a\nP95 thumbnail bytes")
    next_original_path = write_asset(source_root, "original-v2.mp4", b"P95 original version two\n" * 42)
    next_proxy_path = write_asset(source_root, "review-proxy-v2.mp4", b"P95 proxy version two\n" * 28)
    deletion_path = write_asset(source_root, "retention-delete.mp4", b"P95 retention deletion bytes\n" * 10)

    assets = {
        "original": register_asset(
            p93_database,
            path=original_path,
            asset_type="video",
            created_by=p93_seeded["producer"],
        ),
        "proxy": register_asset(
            p93_database,
            path=proxy_path,
            asset_type="video",
            created_by=p93_seeded["producer"],
        ),
        "thumbnail": register_asset(
            p93_database,
            path=thumbnail_path,
            asset_type="image",
            created_by=p93_seeded["producer"],
        ),
        "next_original": register_asset(
            p93_database,
            path=next_original_path,
            asset_type="video",
            created_by=p93_seeded["producer"],
        ),
        "next_proxy": register_asset(
            p93_database,
            path=next_proxy_path,
            asset_type="video",
            created_by=p93_seeded["producer"],
        ),
        "deletion": register_asset(
            p93_database,
            path=deletion_path,
            asset_type="video",
            created_by=p93_seeded["producer"],
        ),
    }

    shared_provider = LocalSharedStorageProvider(backend_key="shared-test", root=shared_root)
    restore_provider = LocalSharedStorageProvider(backend_key="shared-restore", root=restore_root)
    registry = SharedProviderRegistry(
        providers={
            shared_provider.backend_key: shared_provider,
            restore_provider.backend_key: restore_provider,
        }
    )
    service = SharedArtifactService(
        p93_database,
        providers=registry,
        public_base_url="https://review.example.test",
    )

    shared_backend = service.create_backend(
        request=StorageBackendRequest(
            backend_key="shared-test",
            display_name="Shared Test Storage",
            driver="local",
            environment="test",
            configuration={"fixture": True, "root": str(shared_root)},
        ),
        actor=p93_seeded["admin"],
    )["backend"]
    shared_backend = service.activate_backend(
        backend_id=shared_backend["id"],
        actor=p93_seeded["admin"],
    )["backend"]

    restore_backend = service.create_backend(
        request=StorageBackendRequest(
            backend_key="shared-restore",
            display_name="Shared Restore Storage",
            driver="local",
            environment="staging",
            configuration={"fixture": True, "root": str(restore_root)},
        ),
        actor=p93_seeded["admin"],
    )["backend"]
    restore_backend = service.activate_backend(
        backend_id=restore_backend["id"],
        actor=p93_seeded["admin"],
    )["backend"]

    return {
        **p93_seeded,
        "assets": assets,
        "paths": {
            "original": original_path,
            "proxy": proxy_path,
            "thumbnail": thumbnail_path,
            "next_original": next_original_path,
            "next_proxy": next_proxy_path,
            "deletion": deletion_path,
        },
        "shared_root": shared_root,
        "restore_root": restore_root,
        "registry": registry,
        "service": service,
        "shared_backend": shared_backend,
        "restore_backend": restore_backend,
    }
