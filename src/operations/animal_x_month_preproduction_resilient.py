from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any

import src.application.concepts.service as concept_service_module
from src.application.concepts.adapters import (
    ConceptAdapterError,
    LocalHttpConceptAdapter as CoreLocalHttpConceptAdapter,
)
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


def _load_base_tool() -> Any:
    path = Path(__file__).with_name("animal_x_month_preproduction.py")
    if not path.is_file():
        raise RuntimeError(f"Animal X base preproduction tool is missing: {path}")
    spec = importlib.util.spec_from_file_location("_animal_x_month_preproduction_tool", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Animal X base preproduction tool could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_TOOL = _load_base_tool()
CONCEPT_CANDIDATE_COUNT = BASE_TOOL.CONCEPT_CANDIDATE_COUNT
AnimalXMonthPreproduction = BASE_TOOL.AnimalXMonthPreproduction
next_month_start = BASE_TOOL.next_month_start


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
    """Strict-local Animal X runner that preserves stale fallback audit history."""

    def _matching_concept_batches(self, brand: dict[str, Any]) -> list[dict[str, Any]]:
        seed = int(self.month_start.strftime("%Y%m")) * 100 + 17
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT gb.id,gb.status,gb.created_at,
                          count(c.id)::int AS candidate_count,
                          COALESCE(bool_and(COALESCE(c.generation_evidence->>'adapter','')='local_model'),false)
                            AS local_only
                   FROM football_brief.concept_generation_batches gb
                   LEFT JOIN football_brief.concept_candidates c ON c.batch_id=gb.id
                   WHERE gb.brand_id=%s AND gb.month_start=%s AND gb.requested_count=%s
                     AND gb.seed=%s AND gb.adapter_mode='local_model'
                     AND COALESCE(gb.local_model_id,'')=%s
                   GROUP BY gb.id,gb.status,gb.created_at
                   ORDER BY gb.created_at DESC,gb.id DESC""",
                (
                    brand["id"],
                    self.month_start,
                    CONCEPT_CANDIDATE_COUNT,
                    seed,
                    self.ollama_model,
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _ignored_fallback_count(rows: list[dict[str, Any]]) -> int:
        return sum(
            1
            for row in rows
            if str(row.get("status")) != "failed"
            and not (
                bool(row.get("local_only"))
                and int(row.get("candidate_count") or 0) == CONCEPT_CANDIDATE_COUNT
            )
        )

    def _concept_batch(self, brand: dict[str, Any]) -> dict[str, Any]:
        rows = self._matching_concept_batches(brand)
        reusable = next(
            (
                row
                for row in rows
                if str(row.get("status")) != "failed"
                and bool(row.get("local_only"))
                and int(row.get("candidate_count") or 0) == CONCEPT_CANDIDATE_COUNT
            ),
            None,
        )
        ignored = self._ignored_fallback_count(rows)
        if ignored:
            print(
                json.dumps(
                    {
                        "event": "animal_x_nonlocal_concept_batches_ignored",
                        "count": ignored,
                        "database_history_untouched": True,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        if reusable is not None:
            return self.concepts.batch_detail(batch_id=BASE_TOOL.UUID(str(reusable["id"])))

        seed = int(self.month_start.strftime("%Y%m")) * 100 + 17
        request = BASE_TOOL.ConceptBatchRequest(
            brand_id=BASE_TOOL.UUID(str(brand["id"])),
            month_start=self.month_start,
            candidate_count=CONCEPT_CANDIDATE_COUNT,
            format_mix={"master_video": CONCEPT_CANDIDATE_COUNT},
            pillar_targets={pillar: BASE_TOOL.CONCEPTS_PER_PILLAR for pillar in BASE_TOOL.PILLARS},
            seed=seed,
            adapter_mode=BASE_TOOL.ConceptAdapterMode.LOCAL_MODEL,
            local_model_id=self.ollama_model,
            local_endpoint=self.ollama_endpoint,
            local_timeout_seconds=240,
        )
        result = self.concepts.generate_batch(request, actor=self.admin)
        adapters = {
            str((row.get("generation_evidence") or {}).get("adapter") or "")
            for row in result["candidates"]
        }
        if adapters != {"local_model"}:
            raise BASE_TOOL.AnimalXPreproductionError(
                "strict Animal X concept generation produced a nonlocal candidate"
            )
        return result


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
