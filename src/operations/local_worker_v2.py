from __future__ import annotations

import argparse
import json
import os
import threading
import time
from typing import Any, Iterable

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobType,
)
from src.application.scripts.models import ScriptGenerateRequest
from src.application.scripts.validated_service import ValidatedScriptReviewService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.local_pipeline import LocalPipelineService
from src.operations.local_worker import LocalGenerationWorker


ALL_SUPPORTED_TYPES = {
    GenerationJobType.SCRIPT,
    GenerationJobType.NARRATION,
    GenerationJobType.KEYFRAME,
}


class AlwaysOnLocalGenerationWorker(LocalGenerationWorker):
    """Durable local worker for scripts, narration, and keyframes.

    The worker can run in multiple processes with disjoint job-type sets. It keeps
    leases alive during long local model calls, retries post-completion artifact
    registration, and only continues downstream work after an approved script.
    """

    def __init__(
        self,
        database: Database,
        *,
        allowed_job_types: Iterable[GenerationJobType] = ALL_SUPPORTED_TYPES,
    ) -> None:
        super().__init__(database)
        self.scripts = ValidatedScriptReviewService(database)
        self.pipeline = LocalPipelineService(database)
        self.allowed_job_types = frozenset(allowed_job_types)
        if not self.allowed_job_types or not self.allowed_job_types.issubset(ALL_SUPPORTED_TYPES):
            raise ValueError("at least one supported local job type is required")
        self.lease_seconds = int(os.getenv("LOCAL_WORKER_LEASE_SECONDS", "900"))
        self.auto_continue_seconds = max(
            10,
            int(os.getenv("LOCAL_AUTO_CONTINUE_SECONDS", "30")),
        )
        self.auto_continue_limit = max(
            1,
            min(20, int(os.getenv("LOCAL_AUTO_CONTINUE_LIMIT", "2"))),
        )
        self._next_auto_continue = 0.0
        self._reconcile_after: dict[str, float] = {}

    def run_once(self) -> dict[str, Any]:
        reconciled = self._reconcile_completed_once()
        if reconciled is not None:
            return reconciled

        continued = self._continue_approved_if_due()
        if continued is not None:
            return continued

        claim = self.jobs.claim(
            worker_id=self.worker_id,
            allowed_brand_ids=None,
            allowed_job_types=self.allowed_job_types,
            requested_job_types=self.allowed_job_types,
            providers=(),
            lease_seconds=self.lease_seconds,
        )
        if not claim:
            return {"ok": True, "claimed": False}

        job = claim["job"]
        attempt = claim["attempt"]
        lease_token = claim["lease_token"]
        stop_heartbeat, heartbeat_thread = self._start_heartbeat(
            job_id=job["id"],
            attempt_id=attempt["id"],
            lease_token=lease_token,
        )
        completed = False
        try:
            job_type = GenerationJobType(job["job_type"])
            if job_type == GenerationJobType.SCRIPT:
                output = self._script(job)
            elif job_type == GenerationJobType.NARRATION:
                output = self._narration(job)
            elif job_type == GenerationJobType.KEYFRAME:
                output = self._keyframe(job)
            else:  # pragma: no cover - guarded by the queue claim
                raise RuntimeError(f"unsupported local job type: {job['job_type']}")

            stop_heartbeat.set()
            heartbeat_thread.join(timeout=5)
            self.jobs.complete(
                GenerationJobCompletion(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    output_payload=output,
                    actual_cost_usd=0,
                    provider_request_id=output.get("provider_request_id"),
                )
            )
            completed = True
            if job_type == GenerationJobType.NARRATION:
                self._register_audio(job=job, output=output)
            elif job_type == GenerationJobType.KEYFRAME:
                self._register_keyframe(job=job, output=output)
            return {
                "ok": True,
                "claimed": True,
                "job_id": str(job["id"]),
                "job_type": job["job_type"],
                "output": output,
            }
        except Exception as exc:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=5)
            if completed:
                self._reconcile_after[str(job["id"])] = time.monotonic() + 30
                return {
                    "ok": False,
                    "claimed": True,
                    "job_id": str(job["id"]),
                    "job_type": job["job_type"],
                    "registration_pending": job["job_type"]
                    in {GenerationJobType.NARRATION.value, GenerationJobType.KEYFRAME.value},
                    "error": f"{type(exc).__name__}: {exc}",
                }
            self.jobs.fail(
                GenerationJobFailure(
                    job_id=job["id"],
                    attempt_id=attempt["id"],
                    lease_token=lease_token,
                    worker_id=self.worker_id,
                    error_code="local_worker_execution_failed",
                    error_message=f"{type(exc).__name__}: {exc}"[:5000],
                    retryable=isinstance(exc, (TimeoutError, ConnectionError, OSError)),
                    actual_cost_usd=0,
                    error_details={"job_type": job["job_type"], "external_fee_incurred": False},
                )
            )
            return {
                "ok": False,
                "claimed": True,
                "job_id": str(job["id"]),
                "job_type": job["job_type"],
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _script(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = dict(job["input_payload"])
        request = ScriptGenerateRequest.model_validate(payload["request"])
        result = self.scripts.initialize(
            content_id=job["portfolio_content_id"],
            request=request,
            actor=self.worker_id,
        )
        document = result["document"]
        return {
            "kind": "local_ollama_script",
            "script_document_id": str(document["id"]),
            "script_version_id": str(document["current_version_id"]),
            "status": document["current_version_status"],
            "provider": "ollama-local",
            "model_id": request.local_model_id,
            "external_fee_incurred": False,
            "human_review_required": True,
            "automatic_approval": False,
        }

    def _start_heartbeat(self, *, job_id, attempt_id, lease_token) -> tuple[threading.Event, threading.Thread]:
        stop = threading.Event()
        interval = max(10.0, min(60.0, self.lease_seconds / 3))

        def beat() -> None:
            while not stop.wait(interval):
                try:
                    self.jobs.heartbeat(
                        GenerationJobHeartbeat(
                            job_id=job_id,
                            attempt_id=attempt_id,
                            lease_token=lease_token,
                            worker_id=self.worker_id,
                            lease_seconds=self.lease_seconds,
                        )
                    )
                except Exception:
                    # The main execution path owns terminal state. A heartbeat
                    # failure is observable in logs and must not create a second
                    # completion/failure path.
                    return

        thread = threading.Thread(target=beat, name=f"job-heartbeat-{job_id}", daemon=True)
        thread.start()
        return stop, thread

    def _continue_approved_if_due(self) -> dict[str, Any] | None:
        now = time.monotonic()
        if now < self._next_auto_continue:
            return None
        self._next_auto_continue = now + self.auto_continue_seconds
        include_audio = GenerationJobType.NARRATION in self.allowed_job_types
        include_visuals = GenerationJobType.KEYFRAME in self.allowed_job_types
        if not include_audio and not include_visuals:
            return None
        result = self.pipeline.continue_approved(
            limit=self.auto_continue_limit,
            actor=self.worker_id,
            include_audio=include_audio,
            include_visuals=include_visuals,
        )
        if not result["audio_initialized"] and not result["visuals_initialized"] and not result["blocked"]:
            return None
        return {"claimed": False, "automatic_continuation": True, **result}

    def _reconcile_completed_once(self) -> dict[str, Any] | None:
        wanted: list[str] = []
        if GenerationJobType.NARRATION in self.allowed_job_types:
            wanted.append(GenerationJobType.NARRATION.value)
        if GenerationJobType.KEYFRAME in self.allowed_job_types:
            wanted.append(GenerationJobType.KEYFRAME.value)
        if not wanted:
            return None
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM (
                       SELECT j.*,'narration' AS reconciliation_kind
                       FROM football_brief.generation_jobs j
                       JOIN football_brief.audio_segment_takes ast ON ast.generation_job_id=j.id
                       WHERE j.status='succeeded' AND j.job_type='narration' AND ast.status='queued'
                       UNION ALL
                       SELECT j.*,'keyframe' AS reconciliation_kind
                       FROM football_brief.generation_jobs j
                       JOIN football_brief.visual_candidates vc ON vc.generation_job_id=j.id
                       WHERE j.status='succeeded' AND j.job_type='keyframe' AND vc.status='queued'
                   ) pending
                   WHERE job_type = ANY(%s::text[])
                   ORDER BY completed_at NULLS LAST,queued_at,id LIMIT 20""",
                (wanted,),
            ).fetchall()
        now = time.monotonic()
        selected = next(
            (dict(row) for row in rows if now >= self._reconcile_after.get(str(row["id"]), 0.0)),
            None,
        )
        if selected is None:
            return None
        output = dict(selected.get("output_payload") or {})
        if not output:
            self._reconcile_after[str(selected["id"])] = now + 300
            return {
                "ok": False,
                "claimed": False,
                "reconciliation_job_id": str(selected["id"]),
                "error": "succeeded job has no output payload",
            }
        try:
            if selected["reconciliation_kind"] == "narration":
                self._register_audio(job=selected, output=output)
            else:
                self._register_keyframe(job=selected, output=output)
            self._reconcile_after.pop(str(selected["id"]), None)
            return {
                "ok": True,
                "claimed": False,
                "reconciled": True,
                "job_id": str(selected["id"]),
                "job_type": selected["job_type"],
            }
        except Exception as exc:
            self._reconcile_after[str(selected["id"])] = now + 60
            return {
                "ok": False,
                "claimed": False,
                "reconciled": False,
                "job_id": str(selected["id"]),
                "job_type": selected["job_type"],
                "error": f"{type(exc).__name__}: {exc}",
            }


def _parse_types(raw: str) -> frozenset[GenerationJobType]:
    values = {item.strip() for item in raw.split(",") if item.strip()}
    if not values:
        raise argparse.ArgumentTypeError("at least one job type is required")
    try:
        result = frozenset(GenerationJobType(value) for value in values)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not result.issubset(ALL_SUPPORTED_TYPES):
        allowed = ",".join(sorted(item.value for item in ALL_SUPPORTED_TYPES))
        raise argparse.ArgumentTypeError(f"local worker job types must be a subset of: {allowed}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the always-on local production worker.")
    parser.add_argument("--once", action="store_true", help="Reconcile or claim at most one job.")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument(
        "--job-types",
        type=_parse_types,
        default=frozenset(ALL_SUPPORTED_TYPES),
        help="Comma-separated subset of script,narration,keyframe.",
    )
    args = parser.parse_args(argv)
    database = Database(get_database_settings())
    database.open(require_schema=True)
    worker = AlwaysOnLocalGenerationWorker(database, allowed_job_types=args.job_types)
    try:
        while True:
            result = worker.run_once()
            print(json.dumps(result, default=str, sort_keys=True), flush=True)
            if args.once:
                return 0 if result.get("ok") else 1
            if not result.get("claimed") and not result.get("reconciled"):
                time.sleep(max(args.poll_seconds, 0.5))
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
