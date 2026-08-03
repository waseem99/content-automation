from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import threading
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobType,
)
from src.application.renderers.fal_api import FalQueueRendererAdapter
from src.application.renderers.provider_http import (
    ManagedProviderError,
    ManagedProviderState,
)
from src.application.renderers.vidu_api import ViduRendererAdapter
from src.application.shared_storage.models import ArtifactKind, ArtifactVersionRequest
from src.application.shared_storage.runtime import CanonicalAssetSourceResolver
from src.application.shared_storage.service import SharedArtifactService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.job_logging import ObservedGenerationJobService


class ProviderAdapter(Protocol):
    provider_key: str

    def submit(
        self,
        *,
        model_key: str,
        request_payload: dict[str, Any],
        input_paths: list[Path],
    ) -> ManagedProviderState: ...

    def poll(self, provider_job_id: str, *, model_key: str) -> ManagedProviderState: ...

    def wait(
        self,
        provider_job_id: str,
        *,
        model_key: str,
        timeout_seconds: int,
        poll_seconds: float,
    ) -> ManagedProviderState: ...

    def download(self, state: ManagedProviderState, destination: Path) -> Path: ...

    def close(self) -> None: ...


PROVIDER_SETTINGS = {
    "fal": {
        "enabled": "FAL_RENDERER_ENABLED",
        "worker_id": "FAL_WORKER_OPERATOR_ID",
        "default_worker_id": "fal-worker",
        "lease_seconds": "FAL_WORKER_LEASE_SECONDS",
        "poll_seconds": "FAL_POLL_SECONDS",
    },
    "vidu": {
        "enabled": "VIDU_RENDERER_ENABLED",
        "worker_id": "VIDU_WORKER_OPERATOR_ID",
        "default_worker_id": "vidu-worker",
        "lease_seconds": "VIDU_WORKER_LEASE_SECONDS",
        "poll_seconds": "VIDU_POLL_SECONDS",
    },
}


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def build_adapter(provider: str) -> ProviderAdapter:
    if provider == "fal":
        return FalQueueRendererAdapter()
    if provider == "vidu":
        return ViduRendererAdapter()
    raise ValueError(f"unsupported managed provider: {provider}")


class ProviderManagedWorker:
    """Execute only explicitly approved P94 managed clips for one official provider."""

    def __init__(
        self,
        database: Database,
        *,
        provider: str,
        adapter: ProviderAdapter | None = None,
    ) -> None:
        if provider not in PROVIDER_SETTINGS:
            raise ValueError(f"unsupported managed provider: {provider}")
        settings = PROVIDER_SETTINGS[provider]
        if not _enabled("PROVIDER_PAID_EXECUTION_ENABLED"):
            raise RuntimeError(
                "PROVIDER_PAID_EXECUTION_ENABLED must be explicitly true before a paid worker can start"
            )
        if not _enabled(settings["enabled"]):
            raise RuntimeError(f"{settings['enabled']} must be explicitly true before the worker can start")

        self.database = database
        self.provider = provider
        self.jobs = ObservedGenerationJobService(database)
        self.shared = SharedArtifactService(database)
        self.assets = CanonicalAssetSourceResolver()
        self.adapter = adapter or build_adapter(provider)
        self.worker_id = os.getenv(settings["worker_id"], settings["default_worker_id"])
        self.artifact_root = Path(
            os.getenv("LOCAL_ARTIFACT_ROOT", ".runtime/artifacts")
        ).expanduser().resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.lease_seconds = int(os.getenv(settings["lease_seconds"], "1800"))
        self.poll_seconds = float(os.getenv(settings["poll_seconds"], "5"))

    def run_once(self) -> dict[str, Any]:
        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=(GenerationJobType.PREMIUM_CLIP,),
            requested_job_types=(GenerationJobType.PREMIUM_CLIP,),
            providers=(self.provider,),
            lease_seconds=self.lease_seconds,
        )
        if not claim:
            return {"ok": True, "claimed": False, "provider": self.provider}

        job = dict(claim["job"])
        attempt = dict(claim["attempt"])
        lease_token = claim["lease_token"]
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job, attempt, lease_token, stop_heartbeat),
            daemon=True,
        )
        heartbeat.start()
        provider_job_id: str | None = None
        incurred_cost = Decimal("0")
        provider_credits: Decimal | None = None
        try:
            payload = dict(job["input_payload"])
            request_payload = self._enriched_request(job, payload)
            input_paths = self._input_paths(request_payload)
            model_key = str(job.get("model_id") or payload.get("model_key") or "")
            provider_job_id = self._existing_provider_job_id(job["id"])
            if provider_job_id:
                state = self.adapter.poll(provider_job_id, model_key=model_key)
            else:
                state = self.adapter.submit(
                    model_key=model_key,
                    request_payload=request_payload,
                    input_paths=input_paths,
                )
                provider_job_id = state.provider_job_id
                self._record_provider_request(
                    attempt_id=attempt["id"],
                    provider_job_id=provider_job_id,
                    payload=state.payload,
                )

            if not state.terminal:
                state = self.adapter.wait(
                    provider_job_id,
                    model_key=model_key,
                    timeout_seconds=int(job.get("timeout_seconds") or 1800),
                    poll_seconds=self.poll_seconds,
                )
            provider_credits = state.credits
            incurred_cost = self._cost_or_conservative_ceiling(job, state.actual_cost_usd)
            if state.status != "succeeded":
                raise ManagedProviderError(
                    f"{self.provider}_generation_failed",
                    state.error or f"The {self.provider} generation failed.",
                    retryable=False,
                    actual_cost_usd=incurred_cost,
                    details={"provider_status": state.status},
                )

            output_dir = self.artifact_root / "managed" / self.provider / str(job["id"])
            suffix = self._output_suffix(state.output_url)
            path = self.adapter.download(state, output_dir / f"output{suffix}")
            output = self._register_output(
                job=job,
                request_payload=request_payload,
                provider_job_id=provider_job_id,
                provider_payload=state.payload,
                path=path,
                actual_cost_usd=incurred_cost,
                credits=provider_credits,
            )
            self.jobs.complete(
                GenerationJobCompletion(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    output_payload=output,
                    actual_cost_usd=incurred_cost,
                    provider_request_id=provider_job_id,
                )
            )
            return {
                "ok": True,
                "claimed": True,
                "provider": self.provider,
                "job_id": str(job["id"]),
                "provider_request_id": provider_job_id,
                "shared_artifact_version_id": output["shared_artifact_version_id"],
                "actual_cost_usd": str(incurred_cost),
                "credits": str(provider_credits) if provider_credits is not None else None,
                "human_review_required": True,
            }
        except Exception as exc:
            if isinstance(exc, ManagedProviderError):
                retryable = exc.retryable
                error_code = exc.code
                incurred_cost = max(incurred_cost, exc.actual_cost_usd)
                details = exc.details
            else:
                retryable = isinstance(exc, (TimeoutError, ConnectionError, OSError))
                error_code = f"{self.provider}_worker_execution_failed"
                details = {}
            self.jobs.fail(
                GenerationJobFailure(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    error_code=error_code,
                    error_message=f"{type(exc).__name__}: {exc}"[:5000],
                    retryable=retryable,
                    actual_cost_usd=incurred_cost,
                    error_details={
                        "provider": self.provider,
                        "provider_request_id": provider_job_id,
                        "provider_credits": str(provider_credits) if provider_credits is not None else None,
                        "external_fee_possible": True,
                        "human_review_required": True,
                        "automatic_approval": False,
                        "automatic_publishing": False,
                        **details,
                    },
                )
            )
            return {
                "ok": False,
                "claimed": True,
                "provider": self.provider,
                "job_id": str(job["id"]),
                "provider_request_id": provider_job_id,
                "actual_cost_usd": str(incurred_cost),
                "error": f"{type(exc).__name__}: {exc}",
            }
        finally:
            stop_heartbeat.set()
            heartbeat.join(timeout=5)

    def close(self) -> None:
        self.adapter.close()

    def _heartbeat_loop(
        self,
        job: dict[str, Any],
        attempt: dict[str, Any],
        lease_token: UUID,
        stop: threading.Event,
    ) -> None:
        interval = max(15, min(120, self.lease_seconds // 3))
        while not stop.wait(interval):
            try:
                self.jobs.heartbeat(
                    GenerationJobHeartbeat(
                        job_id=job["id"],
                        attempt_id=attempt["id"],
                        lease_token=lease_token,
                        worker_id=self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )
                )
            except Exception:
                return

    @staticmethod
    def _enriched_request(job: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = dict(payload.get("request") or {})
        metadata = dict(request_payload.get("request_metadata") or {})
        metadata.update(
            {
                "generation_job_id": str(job["id"]),
                "routing_plan_id": payload.get("routing_plan_id"),
                "routing_item_id": payload.get("routing_item_id"),
                "renderer_preflight_id": payload.get("renderer_preflight_id"),
                "request_fingerprint": payload.get("request_fingerprint"),
                "selected_candidate_id": payload.get("selected_candidate_id"),
            }
        )
        request_payload["request_metadata"] = metadata
        return request_payload

    def _input_paths(self, request_payload: dict[str, Any]) -> list[Path]:
        asset_ids = [UUID(str(value)) for value in request_payload.get("input_asset_ids") or []]
        paths: list[Path] = []
        with self.database.connection() as conn:
            for asset_id in asset_ids:
                asset = conn.execute(
                    "SELECT storage_uri FROM football_brief.assets WHERE id=%s",
                    (asset_id,),
                ).fetchone()
                if not asset:
                    raise ManagedProviderError(
                        f"{self.provider}_input_asset_missing",
                        "A reviewed renderer input asset is missing.",
                    )
                paths.append(self.assets.resolve(str(asset["storage_uri"])))
        return paths

    def _existing_provider_job_id(self, job_id: UUID) -> str | None:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT provider_request_id
                   FROM football_brief.generation_job_attempts
                   WHERE job_id=%s AND provider_request_id IS NOT NULL
                   ORDER BY attempt_number DESC LIMIT 1""",
                (job_id,),
            ).fetchone()
        return str(row["provider_request_id"]) if row else None

    def _record_provider_request(
        self,
        *,
        attempt_id: UUID,
        provider_job_id: str,
        payload: dict[str, Any],
    ) -> None:
        evidence = {
            "provider": self.provider,
            "provider_request_id": provider_job_id,
            "submitted": True,
            "response_keys": sorted(payload.keys()),
        }
        with self.database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.generation_job_attempts
                   SET provider_request_id=%s,
                       error_details=error_details || %s::jsonb
                   WHERE id=%s AND status='running'""",
                (provider_job_id, json.dumps(evidence), attempt_id),
            )

    def _register_output(
        self,
        *,
        job: dict[str, Any],
        request_payload: dict[str, Any],
        provider_job_id: str,
        provider_payload: dict[str, Any],
        path: Path,
        actual_cost_usd: Decimal,
        credits: Decimal | None,
    ) -> dict[str, Any]:
        sha256 = self._sha256(path)
        mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
        if not mime_type.startswith("video/"):
            raise RuntimeError("managed renderer output is not a recognized video file")
        with self.database.transaction() as conn:
            context = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (job["portfolio_content_id"],),
            ).fetchone()
            if not context:
                raise RuntimeError("managed output content context is missing")
            existing = conn.execute(
                "SELECT id FROM football_brief.assets WHERE sha256=%s",
                (sha256,),
            ).fetchone()
            if existing:
                asset_id = existing["id"]
            else:
                asset = conn.execute(
                    """INSERT INTO football_brief.assets
                       (asset_type,source_type,lifecycle_status,original_filename,storage_uri,
                        sha256,mime_type,size_bytes,metadata,created_by)
                       VALUES ('video','ai_generated','internal_only',%s,%s,%s,%s,%s,%s::jsonb,%s)
                       RETURNING id""",
                    (
                        path.name,
                        path.as_uri(),
                        sha256,
                        mime_type,
                        path.stat().st_size,
                        json.dumps(
                            {
                                "provider": self.provider,
                                "model_id": job.get("model_id"),
                                "provider_request_id": provider_job_id,
                                "generation_job_id": str(job["id"]),
                                "external_fee_incurred": True,
                                "actual_cost_usd": str(actual_cost_usd),
                                "provider_credits": str(credits) if credits is not None else None,
                                "human_review_required": True,
                                "automatic_approval": False,
                                "automatic_publishing": False,
                            }
                        ),
                        self.worker_id,
                    ),
                ).fetchone()
                asset_id = asset["id"]
            backend = conn.execute(
                """SELECT id FROM football_brief.shared_storage_backends
                   WHERE status='active' AND driver='local'
                   ORDER BY CASE environment WHEN 'staging' THEN 0 WHEN 'development' THEN 1 ELSE 2 END,
                            created_at DESC LIMIT 1"""
            ).fetchone()
            if not backend:
                raise RuntimeError("an active local shared-storage backend is required")

        metadata = dict(request_payload.get("request_metadata") or {})
        routing_item_id = str(metadata.get("routing_item_id") or job["id"])
        artifact = self.shared.create_artifact_version(
            request=ArtifactVersionRequest(
                brand_id=context["brand_id"],
                portfolio_content_id=job["portfolio_content_id"],
                content_version=int(job["content_version"]),
                artifact_key=f"managed/{self.provider}/{job['portfolio_content_id']}/{routing_item_id}",
                artifact_kind=ArtifactKind.PREMIUM_CLIP,
                original_asset_id=asset_id,
                review_proxy_asset_id=asset_id,
                backend_id=backend["id"],
                metadata={
                    "provider": self.provider,
                    "model_id": job.get("model_id"),
                    "provider_request_id": provider_job_id,
                    "generation_job_id": str(job["id"]),
                    "routing_item_id": routing_item_id,
                    "selected_candidate_id": metadata.get("selected_candidate_id"),
                    "actual_cost_usd": str(actual_cost_usd),
                    "provider_credits": str(credits) if credits is not None else None,
                    "review_status": "pending",
                    "human_review_required": True,
                    "automatic_approval": False,
                    "automatic_publishing": False,
                    "provider_payload_digest": hashlib.sha256(
                        json.dumps(provider_payload, sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest(),
                },
            ),
            actor=self.worker_id,
        )
        artifact_row = artifact["artifact"]
        return {
            "kind": f"{self.provider}_managed_clip",
            "provider": self.provider,
            "model_id": job.get("model_id"),
            "provider_request_id": provider_job_id,
            "storage_path": str(path),
            "storage_uri": path.as_uri(),
            "sha256": sha256,
            "mime_type": mime_type,
            "size_bytes": path.stat().st_size,
            "asset_id": str(asset_id),
            "shared_artifact_version_id": str(artifact_row["id"]),
            "routing_item_id": routing_item_id,
            "actual_cost_usd": str(actual_cost_usd),
            "provider_credits": str(credits) if credits is not None else None,
            "external_fee_incurred": True,
            "human_review_required": True,
            "automatic_approval": False,
            "automatic_publishing": False,
        }

    @staticmethod
    def _cost_or_conservative_ceiling(
        job: dict[str, Any],
        observed: Decimal | None,
    ) -> Decimal:
        if observed is not None:
            return max(Decimal("0"), observed)
        return max(
            Decimal(str(job.get("reserved_cost_usd") or "0")),
            Decimal(str(job.get("estimated_cost_usd") or "0")),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _output_suffix(url: str | None) -> str:
        if not url:
            return ".mp4"
        suffix = Path(url.split("?", 1)[0]).suffix.lower()
        return suffix if suffix in {".mp4", ".mov", ".webm"} else ".mp4"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an approved official managed-render worker")
    parser.add_argument("--provider", choices=sorted(PROVIDER_SETTINGS), required=True)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker: ProviderManagedWorker | None = None
    try:
        worker = ProviderManagedWorker(database, provider=args.provider)
        while True:
            result = worker.run_once()
            print(json.dumps(result, sort_keys=True, default=str), flush=True)
            if args.once:
                return 0 if result.get("ok") else 1
            if not result.get("claimed"):
                time.sleep(max(1.0, args.poll_seconds))
    finally:
        if worker is not None:
            worker.close()
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
