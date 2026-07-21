from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from src.application.assets.storage import StorageUriResolver
from src.application.shared_storage.providers import (
    LocalSharedStorageProvider,
    S3CompatibleSharedStorageProvider,
    SharedStorageError,
    SharedStorageProvider,
)


class CanonicalAssetSourceResolver:
    def __init__(
        self,
        *,
        workspace_root: Path | None = None,
        managed_root: Path | None = None,
        ops_storage_root: Path | None = None,
    ) -> None:
        self.workspace_root = (workspace_root or Path(os.getenv("ASSET_WORKSPACE_ROOT", "."))).expanduser().resolve()
        self.managed_root = (managed_root or Path(os.getenv("ASSET_MANAGED_ROOT", "var/managed-assets"))).expanduser().resolve()
        self.ops_storage_root = (ops_storage_root or Path(os.getenv("STORAGE_ROOT", "var/storage"))).expanduser().resolve()
        self.asset_resolver = StorageUriResolver(
            workspace_root=self.workspace_root,
            managed_root=self.managed_root,
        )

    def resolve(self, storage_uri: str) -> Path:
        parsed = urlsplit(storage_uri)
        if parsed.scheme in {"workspace", "managed"}:
            return self.asset_resolver.to_path(storage_uri)
        if parsed.scheme == "file":
            if parsed.netloc not in {"", "localhost"} or parsed.query or parsed.fragment:
                raise SharedStorageError(f"Unsupported canonical file URI: {storage_uri}")
            path = Path(unquote(parsed.path)).expanduser().resolve()
            if not path.is_file():
                raise SharedStorageError(f"Canonical asset file is missing: {path}")
            return path
        if parsed.scheme == "local":
            if parsed.netloc or parsed.query or parsed.fragment:
                raise SharedStorageError(f"Unsupported operations storage URI: {storage_uri}")
            relative = unquote(parsed.path.lstrip("/"))
            path = (self.ops_storage_root / relative).resolve()
            try:
                path.relative_to(self.ops_storage_root)
            except ValueError as exc:
                raise SharedStorageError(f"Operations storage URI escapes root: {storage_uri}") from exc
            if not path.is_file():
                raise SharedStorageError(f"Operations storage asset is missing: {path}")
            return path
        raise SharedStorageError(
            f"Canonical asset URI is not locally readable for shared-copy registration: {storage_uri}"
        )


class SharedProviderRegistry:
    def __init__(
        self,
        *,
        providers: dict[str, SharedStorageProvider] | None = None,
        s3_client_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.providers = dict(providers or {})
        self.s3_client_factory = s3_client_factory

    def register(self, provider: SharedStorageProvider) -> None:
        if provider.backend_key in self.providers:
            raise SharedStorageError(f"Shared provider already registered: {provider.backend_key}")
        self.providers[provider.backend_key] = provider

    def provider(self, backend: dict[str, Any]) -> SharedStorageProvider:
        backend_key = str(backend["backend_key"])
        cached = self.providers.get(backend_key)
        if cached is not None:
            return cached
        driver = str(backend["driver"])
        configuration = dict(backend.get("configuration") or {})
        if driver == "local":
            environment_key = f"SHARED_STORAGE_ROOT_{backend_key.upper().replace('-', '_').replace('.', '_')}"
            configured_root = os.getenv(environment_key) or configuration.get("root")
            if not configured_root:
                default_key = os.getenv("SHARED_STORAGE_LOCAL_BACKEND_KEY", "shared-local")
                if backend_key == default_key:
                    configured_root = os.getenv("SHARED_STORAGE_LOCAL_ROOT", "var/shared-storage")
            if not configured_root:
                raise SharedStorageError(
                    f"Local shared backend {backend_key} has no runtime root configuration"
                )
            provider = LocalSharedStorageProvider(
                backend_key=backend_key,
                root=Path(str(configured_root)),
            )
        elif driver == "s3_compatible":
            client_factory = self.s3_client_factory or self._default_s3_client_factory
            client = client_factory(backend)
            provider = S3CompatibleSharedStorageProvider(
                backend_key=backend_key,
                bucket=str(backend["bucket_name"]),
                client=client,
                base_prefix=str(backend.get("base_prefix") or ""),
            )
        else:
            raise SharedStorageError(f"Unsupported shared storage driver: {driver}")
        self.providers[backend_key] = provider
        return provider

    @staticmethod
    def _default_s3_client_factory(backend: dict[str, Any]) -> Any:
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise SharedStorageError(
                "S3-compatible backend requires boto3 or an injected client factory"
            ) from exc
        return boto3.client(
            "s3",
            endpoint_url=backend.get("endpoint_url"),
            region_name=backend.get("region"),
        )
