from __future__ import annotations

import argparse
import json
from typing import Any
from uuid import UUID

import src.application.concepts.service as concept_service_module
from src.application.concepts.adapters import (
    ConceptAdapterError,
    LocalHttpConceptAdapter as CoreLocalHttpConceptAdapter,
)
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings
from src.operations.animal_x_month_preproduction import (
    CONCEPT_CANDIDATE_COUNT,
    AnimalXMonthPreproduction,
    date,
    next_month_start,
)


class AdaptiveLocalConceptAdapter:
    """Use Ollama in small deterministic chunks instead of one oversized JSON response."""

    name = "local_model"

    def __init__(self, *, endpoint: str, model_id: str, timeout_seconds: int = 20) -> None:
        self.endpoint = endpoint
        self.model_id = model_id
        self.timeout_seconds = max(int(timeout_seconds), 240)

    def _adapter(self) -> CoreLocalHttpConceptAdapter:
        return CoreLocalHttpConceptAdapter(
            endpoint=self.endpoint,
            model_id=self.model_id,
            timeout_seconds=self.timeout_seconds,
        )

    def _generate_chunk(
        self,
        *,
        context: dict[str, Any],
        slots: list[Any],
        seed: int,
    ) -> list[Any]:
        try:
            return self._adapter().generate(context=context, slots=slots, seed=seed)
        except Exception as exc:
            if len(slots) > 1:
                midpoint = max(1, len(slots) // 2)
                left = self._generate_chunk(
                    context=context,
                    slots=slots[:midpoint],
                    seed=seed + 101,
                )
                right = self._generate_chunk(
                    context=context,
                    slots=slots[midpoint:],
                    seed=seed + 211,
                )
                return [*left, *right]

            last = exc
            for retry in range(1, 4):
                try:
                    return self._adapter().generate(
                        context=context,
                        slots=slots,
                        seed=seed + (retry * 997),
                    )
                except Exception as retry_exc:
                    last = retry_exc
            raise ConceptAdapterError(
                f"local model failed for one concept slot after retries: {type(last).__name__}: {last}"
            ) from last

    def generate(
        self,
        *,
        context: dict[str, Any],
        slots: list[Any],
        seed: int,
    ) -> list[Any]:
        output: list[Any] = []
        chunk_size = 4
        for start in range(0, len(slots), chunk_size):
            chunk = slots[start : start + chunk_size]
            output.extend(
                self._generate_chunk(
                    context=context,
                    slots=chunk,
                    seed=seed + (start * 31),
                )
            )
        if len(output) != len(slots):
            raise ConceptAdapterError(
                f"adaptive local generation returned {len(output)} concepts for {len(slots)} slots"
            )
        return output


def strict_local_generation(
    *,
    primary: Any,
    fallback: Any,
    context: dict[str, Any],
    slots: list[Any],
    seed: int,
) -> tuple[list[Any], dict[str, Any]]:
    """Production mode: fail instead of silently accepting deterministic concepts."""

    del fallback
    drafts = primary.generate(context=context, slots=slots, seed=seed)
    return drafts, {
        "adapter": "local_model",
        "fallback_used": False,
        "adaptive_chunking": True,
        "chunk_size": 4,
    }


class ResilientAnimalXMonthPreproduction(AnimalXMonthPreproduction):
    def _retire_nonlocal_batches(self, brand: dict[str, Any]) -> int:
        seed = int(self.month_start.strftime("%Y%m")) * 100 + 17
        with self.database.transaction() as conn:
            rows = conn.execute(
                """SELECT gb.id,gb.status,
                          count(c.id)::int AS candidate_count,
                          COALESCE(bool_and(COALESCE(c.generation_evidence->>'adapter','')='local_model'),false)
                            AS local_only
                   FROM football_brief.concept_generation_batches gb
                   LEFT JOIN football_brief.concept_candidates c ON c.batch_id=gb.id
                   WHERE gb.brand_id=%s AND gb.month_start=%s AND gb.requested_count=%s
                     AND gb.seed=%s AND gb.adapter_mode='local_model'
                     AND COALESCE(gb.local_model_id,'')=%s
                     AND gb.status<>'failed'
                   GROUP BY gb.id,gb.status
                   ORDER BY gb.created_at DESC,gb.id DESC""",
                (
                    brand["id"],
                    self.month_start,
                    CONCEPT_CANDIDATE_COUNT,
                    seed,
                    self.ollama_model,
                ),
            ).fetchall()
            retired = 0
            for row in rows:
                if bool(row["local_only"]) and int(row["candidate_count"] or 0) == CONCEPT_CANDIDATE_COUNT:
                    continue
                conn.execute(
                    """UPDATE football_brief.concept_generation_batches
                       SET status='failed',completed_at=COALESCE(completed_at,now()),
                           gap_report=COALESCE(gap_report,'{}'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (
                        json.dumps(
                            {
                                "animal_x_retry": {
                                    "reason": "nonlocal_or_incomplete_batch_retired",
                                    "strict_local_required": True,
                                }
                            },
                            sort_keys=True,
                        ),
                        row["id"],
                    ),
                )
                retired += 1
        return retired

    def _concept_batch(self, brand: dict[str, Any]) -> dict[str, Any]:
        retired = self._retire_nonlocal_batches(brand)
        if retired:
            print(
                json.dumps(
                    {
                        "event": "animal_x_nonlocal_concept_batches_retired",
                        "count": retired,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        return super()._concept_batch(brand)


def install_strict_local_generation() -> tuple[Any, Any]:
    original_adapter = concept_service_module.LocalHttpConceptAdapter
    original_fallback = concept_service_module.generate_with_fallback
    concept_service_module.LocalHttpConceptAdapter = AdaptiveLocalConceptAdapter
    concept_service_module.generate_with_fallback = strict_local_generation
    return original_adapter, original_fallback


def restore_generation_hooks(original_adapter: Any, original_fallback: Any) -> None:
    concept_service_module.LocalHttpConceptAdapter = original_adapter
    concept_service_module.generate_with_fallback = original_fallback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Animal X with strict adaptive Ollama concept generation."
    )
    parser.add_argument("--month", default="")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--timeout-minutes", type=int, default=480)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args(argv)
    month = date.fromisoformat(args.month) if args.month else next_month_start(date.today())

    original_adapter, original_fallback = install_strict_local_generation()
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        service = ResilientAnimalXMonthPreproduction(database, month_start=month)
        result = service.status() if args.status else service.run_until_ready(
            timeout_minutes=max(1, args.timeout_minutes),
            poll_seconds=max(5, args.poll_seconds),
        )
    finally:
        database.close()
        restore_generation_hooks(original_adapter, original_fallback)

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "ready_for_video_generation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
