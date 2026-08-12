from __future__ import annotations

import argparse
import calendar
import json
import os
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from src.application.audio.models import AudioInitializeRequest
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.application.campaigns.models import (
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.concepts.models import (
    CandidateReviewAction,
    ConceptAdapterMode,
    ConceptBatchRequest,
    SlateBuildRequest,
)
from src.application.concepts.validated_service import ValidatedConceptGenerationService
from src.application.pre_generation.service import PreGenerationService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


BRAND_SLUG = "animal-x"
MASTER_TARGET = 20
SHORTS_PER_MASTER = 2
CORE_OUTPUT_TARGET = MASTER_TARGET * (1 + SHORTS_PER_MASTER)
MASTER_DURATION_SECONDS = 135
SHORT_DURATION_SECONDS = 60
PILLARS = (
    "hidden_signals",
    "social_intelligence",
    "anatomy_in_action",
    "field_discoveries",
)
CONCEPTS_PER_PILLAR = 8
RESERVE_MASTERS_PER_PILLAR = 6
FINAL_MASTERS_PER_PILLAR = 5
CONCEPT_CANDIDATE_COUNT = len(PILLARS) * CONCEPTS_PER_PILLAR
CAMPAIGN_MASTER_COUNT = len(PILLARS) * RESERVE_MASTERS_PER_PILLAR
PRIMARY_PLATFORM = "youtube"
MASTER_TARGET_PLATFORMS = ("youtube", "facebook", "instagram")
SHORT_TARGET_PLATFORMS = ("facebook", "instagram", "tiktok", "youtube_shorts")
PROHIBITED_VIDEO_JOB_TYPES = (
    "local_clip",
    "premium_clip",
    "preview",
    "assembly",
    "publishing",
)


class AnimalXPreproductionError(RuntimeError):
    pass


def next_month_start(today: date) -> date:
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def publication_slots(month_start: date, family_ids: list[str]) -> list[dict[str, Any]]:
    """Build exactly two core-output slots per day for a 30-day month.

    September 2026 is the first production target. For any other month, the
    caller must still provide a 30-day month because 60 outputs at two/day is an
    exact 30-day cadence. No clock time is invented here.
    """

    days = calendar.monthrange(month_start.year, month_start.month)[1]
    if days != 30:
        raise AnimalXPreproductionError(
            "60 outputs at exactly two per day requires a 30-day target month"
        )
    if len(family_ids) != MASTER_TARGET:
        raise AnimalXPreproductionError("exactly 20 selected families are required")

    rows: list[dict[str, Any]] = []
    for index, family_id in enumerate(family_ids, start=1):
        scheduled = date(month_start.year, month_start.month, index)
        rows.append(
            {
                "date": scheduled.isoformat(),
                "slot": 1,
                "family_id": family_id,
                "output": "master",
                "platforms": list(MASTER_TARGET_PLATFORMS),
            }
        )
        rows.append(
            {
                "date": scheduled.isoformat(),
                "slot": 2,
                "family_id": family_id,
                "output": "short_1",
                "platforms": list(SHORT_TARGET_PLATFORMS),
            }
        )

    remaining = [
        {
            "family_id": family_id,
            "output": "short_2",
            "platforms": list(SHORT_TARGET_PLATFORMS),
        }
        for family_id in family_ids
    ]
    cursor = 0
    for day in range(21, 31):
        for slot in (1, 2):
            payload = remaining[cursor]
            rows.append(
                {
                    "date": date(month_start.year, month_start.month, day).isoformat(),
                    "slot": slot,
                    **payload,
                }
            )
            cursor += 1
    if len(rows) != CORE_OUTPUT_TARGET:
        raise AnimalXPreproductionError("publication calendar did not produce 60 outputs")
    return sorted(rows, key=lambda row: (row["date"], row["slot"]))


def scene_windows(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose two non-overlapping editorial windows from the approved master.

    These are edit plans, not newly generated factual scripts. Each window is
    assembled only from the approved master's existing scene/narration evidence.
    """

    ordered = sorted(scenes, key=lambda row: (int(row.get("sequence") or 0), str(row.get("id") or "")))
    if len(ordered) < 2:
        raise AnimalXPreproductionError("approved master needs at least two scenes for two shorts")

    def duration(row: dict[str, Any]) -> float:
        return max(0.1, float(row.get("target_duration_seconds") or 0))

    midpoint = max(1, len(ordered) // 2)
    groups = (ordered[:midpoint], ordered[midpoint:])
    output: list[dict[str, Any]] = []
    for short_index, group in enumerate(groups, start=1):
        selected: list[dict[str, Any]] = []
        elapsed = 0.0
        for row in group:
            value = duration(row)
            if selected and elapsed + value > SHORT_DURATION_SECONDS:
                break
            selected.append(row)
            elapsed += value
        if not selected:
            selected = [group[0]]
            elapsed = duration(group[0])
        output.append(
            {
                "short_index": short_index,
                "target_duration_seconds": SHORT_DURATION_SECONDS,
                "planned_duration_seconds": round(elapsed, 3),
                "scene_ids": [str(row.get("id")) for row in selected],
                "scene_keys": [str(row.get("scene_key") or "") for row in selected],
                "narration": [str(row.get("narration_text") or "") for row in selected],
                "source_strategy": "approved_master_scene_extract",
                "new_factual_claims_allowed": False,
                "platforms": list(SHORT_TARGET_PLATFORMS),
            }
        )
    return output


class AnimalXMonthPreproduction:
    def __init__(self, database: Database, *, month_start: date) -> None:
        if month_start.day != 1:
            raise AnimalXPreproductionError("month must start on day 1")
        if calendar.monthrange(month_start.year, month_start.month)[1] != 30:
            raise AnimalXPreproductionError(
                "this 60-output two-per-day production profile requires a 30-day month"
            )
        self.database = database
        self.month_start = month_start
        self.admin = os.getenv("LOCAL_ADMIN_OPERATOR_ID", "local-admin").strip()
        self.reviewer = os.getenv("LOCAL_REVIEWER_OPERATOR_ID", "local-reviewer").strip()
        self.worker = os.getenv("LOCAL_PRODUCER_OPERATOR_ID", "local-producer").strip()
        if self.worker == "local-producer":
            self.worker = self.reviewer
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()
        self.ollama_endpoint = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
        self.kokoro_model = os.getenv("KOKORO_MODEL_ID", "hexgrad/Kokoro-82M").strip()
        self.concepts = ValidatedConceptGenerationService(database)
        self.campaigns = ValidatedCampaignService(database)
        self.pre_generation = PreGenerationService(database)
        self.audio = AudioProductionService(database)

    def prepare(self) -> dict[str, Any]:
        brand = self._brand()
        batch = self._concept_batch(brand)
        slate = self._approved_reserve_slate(batch)
        campaign = self._campaign(brand=brand, batch=batch, slate=slate)
        self.pre_generation.ensure_runs(
            campaign_id=UUID(str(campaign["campaign"]["id"])),
            actor=self.reviewer,
        )
        return self.status(campaign_id=UUID(str(campaign["campaign"]["id"])))

    def status(self, *, campaign_id: UUID | None = None) -> dict[str, Any]:
        brand = self._brand()
        campaign = self._find_campaign(brand_id=UUID(str(brand["id"]))) if campaign_id is None else self.campaigns.detail(campaign_id)
        if not campaign:
            return {
                "ok": True,
                "kind": "animal_x_month_preproduction",
                "status": "not_started",
                "month_start": self.month_start.isoformat(),
                "brand": BRAND_SLUG,
                "target": self._target_summary(),
            }
        campaign_id = UUID(str(campaign["campaign"]["id"]))
        self.pre_generation.ensure_runs(campaign_id=campaign_id, actor=self.reviewer)
        rows = self._campaign_rows(campaign_id)
        selected = self._selected_ready_rows(rows)
        if len(selected) == MASTER_TARGET:
            self._ensure_selected_audio(selected)
            self._store_short_plans(selected)
        snapshot = self._snapshot(campaign=campaign, rows=rows, selected=selected)
        self._write_report(snapshot)
        return snapshot

    def run_until_ready(self, *, timeout_minutes: int, poll_seconds: int) -> dict[str, Any]:
        started = time.monotonic()
        snapshot = self.prepare()
        while snapshot.get("status") != "ready_for_video_generation":
            if time.monotonic() - started >= timeout_minutes * 60:
                snapshot = {**snapshot, "timed_out": True}
                self._write_report(snapshot)
                return snapshot
            print(
                json.dumps(
                    {
                        "status": snapshot.get("status"),
                        "ready_masters": snapshot.get("ready_masters"),
                        "selected_masters": snapshot.get("selected_masters"),
                        "voiceovers_ready": snapshot.get("voiceovers_ready"),
                        "blockers": snapshot.get("blockers"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(max(5, poll_seconds))
            snapshot = self.status()
        return snapshot

    def _brand(self) -> dict[str, Any]:
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT b.*,bp.id AS brand_profile_id,bp.version AS brand_profile_version,
                          bp.audience,bp.content_restrictions
                   FROM football_brief.brands b
                   JOIN football_brief.brand_profiles bp
                     ON bp.brand_id=b.id AND bp.status='active'
                   WHERE b.slug=%s AND b.active=true""",
                (BRAND_SLUG,),
            ).fetchone()
        if row is None:
            raise AnimalXPreproductionError("active Animal X brand/profile is required")
        return dict(row)

    def _concept_batch(self, brand: dict[str, Any]) -> dict[str, Any]:
        seed = int(self.month_start.strftime("%Y%m")) * 100 + 17
        with self.database.connection() as conn:
            row = conn.execute(
                """SELECT id FROM football_brief.concept_generation_batches
                   WHERE brand_id=%s AND month_start=%s AND requested_count=%s
                     AND seed=%s AND adapter_mode='local_model'
                     AND COALESCE(local_model_id,'')=%s AND status<>'failed'
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (
                    brand["id"],
                    self.month_start,
                    CONCEPT_CANDIDATE_COUNT,
                    seed,
                    self.ollama_model,
                ),
            ).fetchone()
        if row:
            return self.concepts.batch_detail(batch_id=UUID(str(row["id"])))
        request = ConceptBatchRequest(
            brand_id=UUID(str(brand["id"])),
            month_start=self.month_start,
            candidate_count=CONCEPT_CANDIDATE_COUNT,
            format_mix={"master_video": CONCEPT_CANDIDATE_COUNT},
            pillar_targets={pillar: CONCEPTS_PER_PILLAR for pillar in PILLARS},
            seed=seed,
            adapter_mode=ConceptAdapterMode.LOCAL_MODEL,
            local_model_id=self.ollama_model,
            local_endpoint=self.ollama_endpoint,
            local_timeout_seconds=120,
        )
        result = self.concepts.generate_batch(request, actor=self.admin)
        adapters = {
            str((row.get("generation_evidence") or {}).get("adapter") or "")
            for row in result["candidates"]
        }
        if adapters != {"local_model"}:
            raise AnimalXPreproductionError(
                "Animal X concept generation fell back from the local model; restore Ollama and rerun"
            )
        return result

    def _approved_reserve_slate(self, batch: dict[str, Any]) -> dict[str, Any]:
        existing = [
            row
            for row in batch.get("slates") or []
            if int(row.get("requested_count") or 0) == CAMPAIGN_MASTER_COUNT
            and str(row.get("status")) in {"approved", "applied"}
        ]
        if existing:
            return self.concepts.slate_detail(slate_id=UUID(str(existing[0]["id"])))

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in batch["candidates"]:
            if str(candidate.get("status")) == "duplicate_blocked":
                continue
            grouped[str(candidate.get("pillar"))].append(candidate)
        selected: list[dict[str, Any]] = []
        for pillar in PILLARS:
            rows = sorted(
                grouped.get(pillar, []),
                key=lambda row: (-float(row.get("total_score") or 0), int(row.get("ordinal") or 0)),
            )
            if len(rows) < RESERVE_MASTERS_PER_PILLAR:
                raise AnimalXPreproductionError(
                    f"not enough non-duplicate concepts for pillar {pillar}: {len(rows)}"
                )
            selected.extend(rows[:RESERVE_MASTERS_PER_PILLAR])

        selected_ids = {str(row["id"]) for row in selected}
        for candidate in batch["candidates"]:
            if str(candidate["id"]) not in selected_ids:
                continue
            if str(candidate.get("status")) == "candidate":
                self.concepts.review_candidate(
                    candidate_id=UUID(str(candidate["id"])),
                    action=CandidateReviewAction.SHORTLIST,
                    rationale="Selected as a high-scoring non-duplicate Animal X reserve concept for the 60-output month.",
                    actor=self.reviewer,
                )

        slate = self.concepts.build_slate(
            SlateBuildRequest(
                batch_id=UUID(str(batch["batch"]["id"])),
                selected_count=CAMPAIGN_MASTER_COUNT,
                format_mix={"master_video": CAMPAIGN_MASTER_COUNT},
                pillar_targets={pillar: RESERVE_MASTERS_PER_PILLAR for pillar in PILLARS},
            ),
            actor=self.reviewer,
        )
        if (slate.get("slate") or {}).get("gap_report"):
            gap = dict((slate.get("slate") or {}).get("gap_report") or {})
            if gap.get("missing_count") or gap.get("format_gaps") or gap.get("pillar_gaps"):
                raise AnimalXPreproductionError(f"concept slate has unresolved distribution gaps: {gap}")
        return self.concepts.approve_slate(
            slate_id=UUID(str(slate["slate"]["id"])),
            actor=self.reviewer,
        )

    def _campaign(self, *, brand: dict[str, Any], batch: dict[str, Any], slate: dict[str, Any]) -> dict[str, Any]:
        key = f"animal-x-{self.month_start:%Y-%m}-60-output-preproduction-v1"
        result = self.campaigns.create_campaign(
            CampaignCreateRequest(
                campaign_key=key,
                brand_id=UUID(str(brand["id"])),
                name=f"Animal X {self.month_start:%B %Y} — 60 output preproduction",
                description=(
                    "Twenty source-backed 135-second master families, two editorial shorts per master, "
                    "local narration, all pre-generation evidence, and no final video generation or publishing."
                ),
                metadata={
                    "animal_x_month_preproduction": True,
                    "master_target": MASTER_TARGET,
                    "core_output_target": CORE_OUTPUT_TARGET,
                    "video_generation_deferred": True,
                    "provider_spend_allowed": False,
                    "public_publishing_allowed": False,
                },
            ),
            actor=self.admin,
        )
        campaign = result["campaign"]
        if str(campaign["status"]) == "active":
            return self.campaigns.detail(UUID(str(campaign["id"])))

        slate_items = slate.get("items") or []
        if len(slate_items) != CAMPAIGN_MASTER_COUNT:
            raise AnimalXPreproductionError("approved reserve slate must contain exactly 24 master concepts")
        inputs: list[CampaignItemInput] = []
        for ordinal, row in enumerate(slate_items, start=1):
            candidate_id = str(row.get("candidate_id") or row.get("id"))
            scheduled = date(self.month_start.year, self.month_start.month, ordinal)
            inputs.append(
                CampaignItemInput(
                    item_key=f"ax-{self.month_start:%Y%m}-{ordinal:02d}",
                    title=str(row["title"]),
                    topic=str(row["concept"]),
                    objective=(
                        "Produce one original premium Animal X master that can yield two source-faithful editorial shorts."
                    ),
                    audience="English-speaking factual animal-video audiences",
                    format_name="master_video",
                    primary_platform=PRIMARY_PLATFORM,
                    target_platforms=MASTER_TARGET_PLATFORMS,
                    target_duration_seconds=MASTER_DURATION_SECONDS,
                    short_cut_count=SHORTS_PER_MASTER,
                    language="en-US",
                    scheduled_for=scheduled,
                    priority=100 - ordinal,
                    metadata={
                        "animal_x_month_preproduction": True,
                        "concept_candidate_id": candidate_id,
                        "concept_batch_id": str(batch["batch"]["id"]),
                        "concept_slate_id": str(slate["slate"]["id"]),
                        "pillar": str(row["pillar"]),
                        "concept_score": float(row.get("total_score") or 0),
                        "video_generation_deferred": True,
                        "shorts_are_editorial_master_cuts": True,
                    },
                )
            )
        version_id = UUID(str(campaign["current_version_id"]))
        self.campaigns.add_items(
            campaign_version_id=version_id,
            request=CampaignItemsAddRequest(items=inputs),
            actor=self.admin,
        )
        validation = self.campaigns.validate_version(campaign_version_id=version_id, actor=self.admin)
        if not validation.get("ok"):
            raise AnimalXPreproductionError(f"Animal X campaign validation failed: {validation}")
        self.campaigns.activate_version(campaign_version_id=version_id, actor=self.admin)
        return self.campaigns.detail(UUID(str(campaign["id"])))

    def _find_campaign(self, *, brand_id: UUID) -> dict[str, Any] | None:
        key = f"animal-x-{self.month_start:%Y-%m}-60-output-preproduction-v1"
        with self.database.connection() as conn:
            row = conn.execute(
                "SELECT id FROM football_brief.production_campaigns WHERE campaign_key=%s AND brand_id=%s",
                (key, brand_id),
            ).fetchone()
        return self.campaigns.detail(UUID(str(row["id"]))) if row else None

    def _campaign_rows(self, campaign_id: UUID) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT item.id,item.item_key,item.ordinal,item.title,item.state,item.portfolio_content_id,
                          item.content_family_id,item.metadata,
                          COALESCE(item.metadata->>'pillar','') AS pillar,
                          COALESCE((item.metadata->>'concept_score')::numeric,0) AS concept_score,
                          run.status AS run_status,run.current_stage,run.last_error_code,
                          package.id AS package_id,package.package_sha256
                   FROM football_brief.production_campaign_items item
                   JOIN football_brief.production_campaign_versions version
                     ON version.id=item.campaign_version_id
                   LEFT JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                   LEFT JOIN football_brief.pre_generation_packages package
                     ON package.campaign_item_id=item.id AND package.status='ready'
                   WHERE version.campaign_id=%s
                   ORDER BY item.ordinal,item.id""",
                (campaign_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _selected_ready_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if str(row.get("state")) != "ready_for_final_video_generation":
                continue
            grouped[str(row.get("pillar") or "")].append(row)
        selected: list[dict[str, Any]] = []
        for pillar in PILLARS:
            ready = sorted(
                grouped.get(pillar, []),
                key=lambda row: (-float(row.get("concept_score") or 0), int(row.get("ordinal") or 0)),
            )
            if len(ready) < FINAL_MASTERS_PER_PILLAR:
                return []
            selected.extend(ready[:FINAL_MASTERS_PER_PILLAR])
        return sorted(selected, key=lambda row: int(row.get("ordinal") or 0))

    def _ensure_selected_audio(self, selected: list[dict[str, Any]]) -> None:
        for row in selected:
            content_id = row.get("portfolio_content_id")
            if not content_id:
                continue
            try:
                self.audio.initialize(
                    content_id=UUID(str(content_id)),
                    request=AudioInitializeRequest(
                        model_id=self.kokoro_model,
                        preferred_worker_id=self.worker,
                        timeout_seconds=900,
                        max_attempts=3,
                    ),
                    actor=self.admin,
                )
            except AudioProductionError as exc:
                if exc.code != "audio_production_already_active":
                    raise

    def _audio_readiness(self, content_ids: list[UUID]) -> dict[str, Any]:
        if not content_ids:
            return {"ready": 0, "total": 0, "details": []}
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT pc.id AS content_id,ap.id AS production_id,
                          count(DISTINCT paragraph.id)::int AS paragraph_count,
                          count(DISTINCT paragraph.id) FILTER (
                            WHERE EXISTS (
                              SELECT 1 FROM football_brief.audio_segment_takes take
                              WHERE take.paragraph_id=paragraph.id
                                AND take.status IN ('generated','selected')
                                AND take.qc_status='pass'
                                AND take.timing_source='forced_alignment'
                            )
                          )::int AS aligned_pass_count,
                          count(DISTINCT paragraph.id) FILTER (
                            WHERE EXISTS (
                              SELECT 1 FROM football_brief.audio_segment_takes take
                              WHERE take.paragraph_id=paragraph.id
                                AND take.status IN ('generated','selected')
                                AND take.qc_status='pass'
                            )
                          )::int AS qc_pass_count
                   FROM football_brief.portfolio_content pc
                   LEFT JOIN football_brief.audio_productions ap
                     ON ap.portfolio_content_id=pc.id
                    AND ap.status IN ('working','in_review','approved')
                   LEFT JOIN football_brief.audio_paragraphs paragraph
                     ON paragraph.audio_production_id=ap.id
                   WHERE pc.id=ANY(%s::uuid[])
                   GROUP BY pc.id,ap.id
                   ORDER BY pc.id""",
                (content_ids,),
            ).fetchall()
        details = []
        ready = 0
        by_content: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = dict(row)
            count = int(payload.get("paragraph_count") or 0)
            aligned = int(payload.get("aligned_pass_count") or 0)
            qc_pass = int(payload.get("qc_pass_count") or 0)
            payload["ready"] = bool(payload.get("production_id") and count > 0 and aligned == count)
            payload["qc_ready_without_alignment"] = bool(payload.get("production_id") and count > 0 and qc_pass == count)
            if payload["ready"]:
                ready += 1
            by_content[str(payload["content_id"])] = payload
        for content_id in content_ids:
            details.append(by_content.get(str(content_id), {"content_id": str(content_id), "ready": False, "paragraph_count": 0}))
        return {"ready": ready, "total": len(content_ids), "details": details}

    def _family_rows(self, family_ids: list[UUID]) -> list[dict[str, Any]]:
        if not family_ids:
            return []
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT id,content_family_id,parent_content_id,variant_type,primary_platform,
                          target_platforms,target_duration_seconds,short_cut_index,title,metadata
                   FROM football_brief.portfolio_content
                   WHERE content_family_id=ANY(%s::uuid[])
                   ORDER BY content_family_id,
                            CASE variant_type WHEN 'master' THEN 0 WHEN 'adaptation' THEN 1 ELSE 2 END,
                            short_cut_index NULLS FIRST,primary_platform,id""",
                (family_ids,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _master_scenes(self, content_id: UUID) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT scene.*
                   FROM football_brief.script_documents document
                   JOIN football_brief.script_versions version ON version.id=document.current_version_id
                   JOIN football_brief.script_scene_plan_entries scene ON scene.script_version_id=version.id
                   WHERE document.portfolio_content_id=%s AND version.status='approved'
                   ORDER BY scene.sequence,scene.id""",
                (content_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _store_short_plans(self, selected: list[dict[str, Any]]) -> None:
        for row in selected:
            family_id = UUID(str(row["content_family_id"]))
            content_id = UUID(str(row["portfolio_content_id"]))
            plans = scene_windows(self._master_scenes(content_id))
            with self.database.transaction() as conn:
                shorts = conn.execute(
                    """SELECT id,short_cut_index FROM football_brief.portfolio_content
                       WHERE content_family_id=%s AND variant_type='short_cut'
                       ORDER BY short_cut_index,id FOR UPDATE""",
                    (family_id,),
                ).fetchall()
                if len(shorts) != SHORTS_PER_MASTER:
                    raise AnimalXPreproductionError(
                        f"family {family_id} must contain exactly two linked short plans"
                    )
                for short in shorts:
                    plan = next(item for item in plans if item["short_index"] == int(short["short_cut_index"]))
                    conn.execute(
                        """UPDATE football_brief.portfolio_content
                           SET metadata=metadata || %s::jsonb
                           WHERE id=%s""",
                        (
                            json.dumps(
                                {
                                    "animal_x_month_short_plan": plan,
                                    "video_generation_deferred": True,
                                    "master_voiceover_reused": True,
                                },
                                sort_keys=True,
                            ),
                            short["id"],
                        ),
                    )

    def _video_job_count(self, family_ids: list[UUID]) -> int:
        if not family_ids:
            return 0
        with self.database.connection() as conn:
            count = conn.execute(
                """SELECT count(*)::int AS value
                   FROM football_brief.generation_jobs job
                   JOIN football_brief.portfolio_content content ON content.id=job.portfolio_content_id
                   WHERE content.content_family_id=ANY(%s::uuid[])
                     AND job.job_type=ANY(%s::text[])""",
                (family_ids, list(PROHIBITED_VIDEO_JOB_TYPES)),
            ).fetchone()["value"]
        return int(count or 0)

    def _snapshot(
        self,
        *,
        campaign: dict[str, Any],
        rows: list[dict[str, Any]],
        selected: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ready_masters = sum(1 for row in rows if str(row.get("state")) == "ready_for_final_video_generation")
        state_counts: dict[str, int] = defaultdict(int)
        blockers: list[dict[str, Any]] = []
        for row in rows:
            state_counts[str(row.get("state"))] += 1
            if row.get("last_error_code"):
                blockers.append(
                    {
                        "item_key": row.get("item_key"),
                        "title": row.get("title"),
                        "state": row.get("state"),
                        "code": row.get("last_error_code"),
                    }
                )

        content_ids = [UUID(str(row["portfolio_content_id"])) for row in selected if row.get("portfolio_content_id")]
        family_ids = [UUID(str(row["content_family_id"])) for row in selected if row.get("content_family_id")]
        family_rows = self._family_rows(family_ids)
        short_count = sum(1 for row in family_rows if str(row.get("variant_type")) == "short_cut")
        facebook_adaptations = sum(
            1
            for row in family_rows
            if str(row.get("variant_type")) == "adaptation" and str(row.get("primary_platform")) == "facebook"
        )
        instagram_adaptations = sum(
            1
            for row in family_rows
            if str(row.get("variant_type")) == "adaptation" and str(row.get("primary_platform")) == "instagram"
        )
        audio = self._audio_readiness(content_ids)
        video_jobs = self._video_job_count(family_ids)
        calendar_rows = publication_slots(self.month_start, [str(value) for value in family_ids]) if len(family_ids) == MASTER_TARGET else []

        selected_ready = len(selected) == MASTER_TARGET
        family_ready = (
            selected_ready
            and short_count == MASTER_TARGET * SHORTS_PER_MASTER
            and facebook_adaptations == MASTER_TARGET
            and instagram_adaptations == MASTER_TARGET
        )
        voiceovers_ready = int(audio["ready"])
        ready = family_ready and voiceovers_ready == MASTER_TARGET and video_jobs == 0 and len(calendar_rows) == CORE_OUTPUT_TARGET
        status = "ready_for_video_generation" if ready else "preparing"
        if selected_ready and family_ready and voiceovers_ready < MASTER_TARGET:
            status = "generating_local_voiceovers"
        if not selected_ready and any(blockers):
            status = "pre_generation_exceptions_present"

        selected_details = []
        for row in selected:
            selected_details.append(
                {
                    "item_key": row["item_key"],
                    "title": row["title"],
                    "pillar": row["pillar"],
                    "concept_score": float(row.get("concept_score") or 0),
                    "content_id": str(row["portfolio_content_id"]),
                    "content_family_id": str(row["content_family_id"]),
                    "package_id": str(row["package_id"]),
                    "package_sha256": str(row["package_sha256"]),
                }
            )

        return {
            "ok": ready,
            "kind": "animal_x_month_preproduction",
            "status": status,
            "month_start": self.month_start.isoformat(),
            "brand": BRAND_SLUG,
            "campaign_id": str(campaign["campaign"]["id"]),
            "campaign_key": str(campaign["campaign"]["campaign_key"]),
            "target": self._target_summary(),
            "campaign_master_candidates": len(rows),
            "ready_masters": ready_masters,
            "selected_masters": len(selected),
            "selected_families": selected_details,
            "core_outputs": len(selected) * (1 + SHORTS_PER_MASTER),
            "linked_shorts": short_count,
            "facebook_master_adaptations": facebook_adaptations,
            "instagram_master_adaptations": instagram_adaptations,
            "voiceovers_ready": voiceovers_ready,
            "voiceovers_total": int(audio["total"]),
            "voiceover_details": audio["details"],
            "publication_calendar": calendar_rows,
            "state_counts": dict(state_counts),
            "blockers": blockers,
            "video_generation_jobs": video_jobs,
            "provider_spend_enabled_by_this_run": False,
            "public_publishing_enabled_by_this_run": False,
            "automatic_audio_approval": False,
            "human_audio_review_required_before_final_video": True,
            "final_video_generation_deferred": True,
        }

    @staticmethod
    def _target_summary() -> dict[str, Any]:
        return {
            "master_families": MASTER_TARGET,
            "master_duration_seconds": MASTER_DURATION_SECONDS,
            "shorts_per_master": SHORTS_PER_MASTER,
            "short_duration_seconds": SHORT_DURATION_SECONDS,
            "core_outputs": CORE_OUTPUT_TARGET,
            "daily_outputs": 2,
            "master_platforms": list(MASTER_TARGET_PLATFORMS),
            "short_platforms": list(SHORT_TARGET_PLATFORMS),
        }

    def _report_dir(self) -> Path:
        return Path(".runtime") / "preproduction" / f"animal-x-{self.month_start:%Y-%m}"

    def _write_report(self, snapshot: dict[str, Any]) -> None:
        root = self._report_dir()
        root.mkdir(parents=True, exist_ok=True)
        (root / "status.json").write_text(
            json.dumps(snapshot, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        lines = [
            f"# Animal X — {self.month_start:%B %Y} preproduction",
            "",
            f"- Status: **{snapshot.get('status')}**",
            f"- Selected master families: **{snapshot.get('selected_masters', 0)}/{MASTER_TARGET}**",
            f"- Core outputs: **{snapshot.get('core_outputs', 0)}/{CORE_OUTPUT_TARGET}**",
            f"- Linked shorts: **{snapshot.get('linked_shorts', 0)}/{MASTER_TARGET * SHORTS_PER_MASTER}**",
            f"- Local master voiceovers ready: **{snapshot.get('voiceovers_ready', 0)}/{MASTER_TARGET}**",
            f"- Final video generation jobs: **{snapshot.get('video_generation_jobs', 0)}**",
            f"- Provider spend enabled by this run: **{snapshot.get('provider_spend_enabled_by_this_run')}**",
            f"- Public publishing enabled by this run: **{snapshot.get('public_publishing_enabled_by_this_run')}**",
            "",
            "Final video generation remains deliberately deferred. Generated narration remains human-review controlled.",
        ]
        (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare one Animal X 60-output month up to, but not including, final video generation."
    )
    parser.add_argument("--month", default="", help="Target month start YYYY-MM-01; defaults to next month.")
    parser.add_argument("--status", action="store_true", help="Read/reconcile status without waiting.")
    parser.add_argument("--timeout-minutes", type=int, default=480)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args(argv)
    month = date.fromisoformat(args.month) if args.month else next_month_start(date.today())
    database = Database(get_database_settings())
    database.open(require_schema=True)
    try:
        service = AnimalXMonthPreproduction(database, month_start=month)
        result = service.status() if args.status else service.run_until_ready(
            timeout_minutes=max(1, args.timeout_minutes),
            poll_seconds=max(5, args.poll_seconds),
        )
    finally:
        database.close()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "ready_for_video_generation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
