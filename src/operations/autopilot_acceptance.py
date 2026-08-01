from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from typing import Any, Callable, TypeVar
from uuid import UUID

from src.application.campaigns.models import (
    CampaignCreateRequest,
    CampaignItemInput,
    CampaignItemsAddRequest,
)
from src.application.campaigns.validated_service import ValidatedCampaignService
from src.application.pre_generation.validated_service import ValidatedPreGenerationService
from src.application.scripts.models import (
    ClaimSourceDraft,
    ClaimSupportType,
    ScriptAdapterMode,
    ScriptGenerateRequest,
    SourceDraft,
    SourceRightsDeclaration,
    SourceSupportUpdateRequest,
    SourceType,
)
from src.application.scripts.runtime_patch import install_validated_script_service
from src.application.scripts.service import ScriptReviewService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.settings import get_database_settings


T = TypeVar("T")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _key() -> str:
    return datetime.now(timezone.utc).strftime("p127-%Y%m%dt%H%M%S%fz")


def _timed(timings: dict[str, float], key: str, function: Callable[..., T], *args, **kwargs) -> T:
    started = time.perf_counter()
    result = function(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _items(count: int, *, primary_platform: str) -> list[CampaignItemInput]:
    return [
        CampaignItemInput(
            item_key=f"auto-{ordinal:04d}",
            title=f"Unique automatic evidence explainer {ordinal:04d}",
            topic=(
                f"Explain the distinct verified mechanism number {ordinal:04d} using one official source, "
                "a concrete comparison and evidence-led wording."
            ),
            objective="Measure automatic pre-generation progression without individual approvals.",
            audience="Internal acceptance benchmark",
            format_name="master_video",
            primary_platform=primary_platform,
            target_platforms=[primary_platform],
            target_duration_seconds=45,
            short_cut_count=0,
            language="en-US",
            scheduled_for=date(2026, 8, 2),
            priority=50,
            metadata={"p127_acceptance": True, "ordinal": ordinal},
        )
        for ordinal in range(1, count + 1)
    ]


def _parallel(values: list[T], *, concurrency: int, function: Callable[[T], Any]) -> list[Any]:
    results: list[Any] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(function, value) for value in values]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def _claim_and_process(
    database: Database,
    *,
    campaign_id: UUID,
    expected: int,
    owner_prefix: str,
    actor: str,
    max_steps: int,
    concurrency: int,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    claimed_total = 0
    batch_number = 0
    while claimed_total < expected:
        batch_number += 1
        service = ValidatedPreGenerationService(database)
        claimed = service.claim(
            owner=f"{owner_prefix}-{batch_number}",
            limit=min(100, expected - claimed_total),
            lease_seconds=900,
            campaign_id=campaign_id,
        )
        if not claimed:
            raise RuntimeError(
                f"autopilot claim queue exhausted after {claimed_total} of {expected} runs"
            )

        def process(row: dict[str, Any]) -> dict[str, Any]:
            worker = ValidatedPreGenerationService(database)
            return worker.process_claim(
                run_id=UUID(str(row["id"])),
                lease_token=UUID(str(row["lease_token"])),
                actor=actor,
                max_steps=max_steps,
            )

        outcomes.extend(_parallel(claimed, concurrency=concurrency, function=process))
        claimed_total += len(claimed)
    return outcomes


def _initialize_script(database: Database, row: dict[str, Any], *, primary: str, actor: str) -> None:
    scripts = ScriptReviewService(database)
    scripts.initialize(
        content_id=UUID(str(row["portfolio_content_id"])),
        request=ScriptGenerateRequest(
            platform=primary,
            format="master_video",
            language="en-US",
            target_duration_seconds=45,
            adapter_mode=ScriptAdapterMode.DETERMINISTIC,
            seed=int(row["ordinal"]),
        ),
        actor=actor,
    )


def _attach_source(database: Database, row: dict[str, Any], *, actor: str) -> None:
    scripts = ScriptReviewService(database)
    detail = scripts.document_for_content(
        content_id=UUID(str(row["portfolio_content_id"]))
    )
    current_id = str(detail["document"]["current_version_id"])
    claims = [
        claim
        for claim in detail["claims"]
        if str(claim["script_version_id"]) == current_id
    ]
    source_key = "official-p127-source"
    item_key = str(row["item_key"])
    source = SourceDraft(
        source_key=source_key,
        source_type=SourceType.GOVERNMENT,
        title=f"Official benchmark evidence for {item_key}",
        publisher="P127 Acceptance Authority",
        canonical_url=f"https://example.gov/p127/{item_key}",
        quality_score=95,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and citation in the acceptance benchmark.",
        evidence_digest=hashlib.sha256(item_key.encode("utf-8")).hexdigest(),
    )
    links = [
        ClaimSourceDraft(
            claim_key=str(claim["claim_key"]),
            source_key=source_key,
            support_type=ClaimSupportType.DIRECT,
            locator=f"Acceptance evidence {item_key}",
            support_note="Directly supports the deterministic factual claim for this unique item.",
        )
        for claim in claims
    ]
    scripts.update_source_support(
        document_id=UUID(str(detail["document"]["id"])),
        request=SourceSupportUpdateRequest(
            expected_lock_version=int(detail["document"]["lock_version"]),
            sources=[source],
            claim_sources=links,
            supported_claim_keys=[str(claim["claim_key"]) for claim in claims],
        ),
        actor=actor,
    )


def run_acceptance(
    *,
    items: int = 1_000,
    supported_items: int = 950,
    concurrency: int = 8,
    acceptance_key: str | None = None,
    actor: str = "local-admin",
    worker_actor: str = "local-reviewer",
) -> dict[str, Any]:
    if not 1 <= items <= 5_000:
        raise ValueError("items must be between 1 and 5,000")
    if not 0 <= supported_items <= items:
        raise ValueError("supported_items must be between zero and items")
    if supported_items / items < 0.95:
        raise ValueError("supported_items must preserve the 95% automation acceptance floor")
    if not 1 <= concurrency <= 32:
        raise ValueError("concurrency must be between 1 and 32")

    install_validated_script_service()
    key = acceptance_key or _key()
    expected_hard_blocks = items - supported_items
    timings: dict[str, float] = {}
    database = Database(get_database_settings())
    database.open(require_schema=True)
    acceptance_id: UUID | None = None
    try:
        with database.transaction() as conn:
            operator = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (actor,),
            ).fetchone()
            worker = conn.execute(
                "SELECT operator_id FROM football_brief.operator_users WHERE operator_id=%s AND active=true",
                (worker_actor,),
            ).fetchone()
            brand = conn.execute(
                "SELECT id,primary_platform FROM football_brief.brands WHERE active=true ORDER BY slug LIMIT 1"
            ).fetchone()
            if not operator or not worker or not brand:
                raise RuntimeError("acceptance onboarding is incomplete")
            acceptance = conn.execute(
                """INSERT INTO football_brief.autopilot_acceptance_runs
                   (acceptance_key,status,requested_items,expected_ready,expected_hard_blocks,
                    requested_by,environment)
                   VALUES (%s,'running',%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                (
                    key,
                    items,
                    supported_items,
                    expected_hard_blocks,
                    actor,
                    _json(
                        {
                            "hostname": socket.gethostname(),
                            "platform": platform.platform(),
                            "python": platform.python_version(),
                            "git_sha": os.getenv("GITHUB_SHA") or os.getenv("OPS_GIT_SHA"),
                            "real_service_path": True,
                            "final_video_generation": False,
                            "public_publishing": False,
                            "concurrency": concurrency,
                        }
                    ),
                ),
            ).fetchone()
            acceptance_id = UUID(str(acceptance["id"]))

        campaign_service = ValidatedCampaignService(database)
        created = _timed(
            timings,
            "create_campaign",
            campaign_service.create_campaign,
            CampaignCreateRequest(
                campaign_key=key,
                brand_id=UUID(str(brand["id"])),
                name=f"P127 {items:,}-item Autopilot Acceptance",
                description="Real P120 service-path acceptance; no rendering or publishing.",
                metadata={"p127_acceptance": True},
            ),
            actor=actor,
        )
        campaign_id = UUID(str(created["campaign"]["id"]))
        version_id = UUID(str(created["versions"][0]["id"]))
        payload = _timed(
            timings,
            "build_items",
            _items,
            items,
            primary_platform=str(brand["primary_platform"]),
        )
        _timed(
            timings,
            "insert_items",
            campaign_service.add_items,
            campaign_version_id=version_id,
            request=CampaignItemsAddRequest(items=payload),
            actor=actor,
        )
        validation = _timed(
            timings,
            "validate_campaign",
            campaign_service.validate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        if not validation["ok"]:
            raise RuntimeError(f"campaign validation failed: {validation}")
        _timed(
            timings,
            "activate_campaign",
            campaign_service.activate_version,
            campaign_version_id=version_id,
            actor=actor,
        )
        pre = ValidatedPreGenerationService(database)
        ensured = _timed(
            timings,
            "ensure_runs",
            pre.ensure_runs,
            campaign_id=campaign_id,
            actor=worker_actor,
        )
        if int(ensured["created"]) != items:
            raise RuntimeError(f"expected {items} durable runs, created {ensured['created']}")
        expansion = _timed(
            timings,
            "content_expansion",
            _claim_and_process,
            database,
            campaign_id=campaign_id,
            expected=items,
            owner_prefix="p127-expand",
            actor=worker_actor,
            max_steps=1,
            concurrency=concurrency,
        )
        if any(outcome.get("waiting") is not True for outcome in expansion):
            raise RuntimeError("one or more content expansions did not pause at script generation")

        with database.connection() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    """SELECT item.item_key,item.ordinal,item.id AS item_id,
                              run.id AS run_id,run.portfolio_content_id
                       FROM football_brief.production_campaign_items item
                       JOIN football_brief.pre_generation_runs run ON run.campaign_item_id=item.id
                       WHERE item.campaign_version_id=%s
                       ORDER BY item.ordinal""",
                    (version_id,),
                ).fetchall()
            ]
        if len(rows) != items or any(not row["portfolio_content_id"] for row in rows):
            raise RuntimeError("content-family expansion did not bind every master content row")

        _timed(
            timings,
            "initialize_scripts",
            _parallel,
            rows,
            concurrency=concurrency,
            function=lambda row: _initialize_script(
                database,
                row,
                primary=str(brand["primary_platform"]),
                actor=actor,
            ),
        )
        supported_rows = rows[:supported_items]
        _timed(
            timings,
            "attach_source_evidence",
            _parallel,
            supported_rows,
            concurrency=concurrency,
            function=lambda row: _attach_source(database, row, actor=actor),
        )
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.pre_generation_runs
                   SET status='queued',next_attempt_at=now(),lease_owner=NULL,
                       lease_token=NULL,lease_expires_at=NULL,updated_at=now()
                   WHERE campaign_item_id IN (
                       SELECT id FROM football_brief.production_campaign_items
                       WHERE campaign_version_id=%s
                   )""",
                (version_id,),
            )
        outcomes = _timed(
            timings,
            "automatic_progression",
            _claim_and_process,
            database,
            campaign_id=campaign_id,
            expected=items,
            owner_prefix="p127-final",
            actor=worker_actor,
            max_steps=12,
            concurrency=concurrency,
        )
        ready_outcomes = sum(1 for outcome in outcomes if outcome.get("status") == "ready")
        block_outcomes = sum(1 for outcome in outcomes if outcome.get("status") == "hard_block")
        if ready_outcomes != supported_items or block_outcomes != expected_hard_blocks:
            raise RuntimeError(
                f"unexpected outcomes: ready={ready_outcomes}, hard_block={block_outcomes}"
            )

        dashboard = pre.dashboard(campaign_id=campaign_id)
        groups = pre.exception_groups(campaign_id=campaign_id)
        source_groups = [
            row
            for row in groups
            if row["exception_code"] == "source_block"
            and int(row["count"]) == expected_hard_blocks
        ]
        with database.connection() as conn:
            counters = dict(
                conn.execute(
                    """SELECT
                           count(*) FILTER (WHERE run.status='ready')::int AS ready_items,
                           count(*) FILTER (WHERE run.status='hard_block')::int AS hard_block_items,
                           count(*) FILTER (WHERE run.status='human_exception')::int AS human_exception_items,
                           count(*) FILTER (WHERE run.correction_count>0)::int AS corrected_items,
                           count(DISTINCT run.content_family_id)::int AS content_families,
                           count(DISTINCT run.script_document_id)::int AS script_documents,
                           count(*) FILTER (
                             WHERE run.status='ready'
                               AND EXISTS (
                                 SELECT 1 FROM football_brief.pre_generation_checks decision
                                 WHERE decision.run_id=run.id
                                   AND decision.stage='script_approval'
                                   AND decision.check_key='automatic_policy_decision'
                                   AND decision.status='passed'
                               )
                               AND 5 = (
                                 SELECT count(*) FROM football_brief.pre_generation_checks script_check
                                 WHERE script_check.run_id=run.id
                                   AND script_check.stage='script_checks'
                                   AND script_check.rule_version='p120-v1'
                                   AND script_check.status='passed'
                               )
                           )::int AS reproducible_ready_decisions
                       FROM football_brief.pre_generation_runs run
                       JOIN football_brief.production_campaign_items item ON item.id=run.campaign_item_id
                       WHERE item.campaign_version_id=%s""",
                    (version_id,),
                ).fetchone()
            )
            autopilot_reviews = int(
                conn.execute(
                    """SELECT count(*)::int AS value
                       FROM football_brief.script_review_decisions decision
                       JOIN football_brief.script_documents document
                         ON document.id=decision.script_document_id
                       JOIN football_brief.pre_generation_runs run
                         ON run.script_document_id=document.id
                       JOIN football_brief.production_campaign_items item
                         ON item.id=run.campaign_item_id
                       WHERE item.campaign_version_id=%s
                         AND decision.reviewer_operator_id='pre-generation-autopilot-reviewer'
                         AND decision.decision='approved'""",
                    (version_id,),
                ).fetchone()["value"]
            )
        automation_rate = counters["ready_items"] / items
        passed = (
            counters["ready_items"] == supported_items
            and counters["hard_block_items"] == expected_hard_blocks
            and counters["human_exception_items"] == 0
            and counters["content_families"] == items
            and counters["script_documents"] == items
            and counters["reproducible_ready_decisions"] == supported_items
            and autopilot_reviews == supported_items
            and automation_rate >= 0.95
            and len(source_groups) == (1 if expected_hard_blocks else 0)
            and dashboard["metrics"]["ready"] == supported_items
            and dashboard["metrics"]["hard_block"] == expected_hard_blocks
        )
        result = {
            "ok": passed,
            "kind": "autopilot_acceptance",
            "acceptance_key": key,
            "campaign_id": str(campaign_id),
            "campaign_version_id": str(version_id),
            "requested_items": items,
            "ready_items": counters["ready_items"],
            "hard_block_items": counters["hard_block_items"],
            "human_exception_items": counters["human_exception_items"],
            "auto_correction_items": counters["corrected_items"],
            "automation_rate": automation_rate,
            "grouped_source_blocks": len(source_groups),
            "individual_page_approvals": 0,
            "content_families": counters["content_families"],
            "script_documents": counters["script_documents"],
            "reproducible_ready_decisions": counters["reproducible_ready_decisions"],
            "autopilot_reviews": autopilot_reviews,
            "timings_ms": timings,
            "final_video_generation": False,
            "public_publishing": False,
        }
        with database.transaction() as conn:
            conn.execute(
                """UPDATE football_brief.autopilot_acceptance_runs
                   SET campaign_id=%s,campaign_version_id=%s,status=%s,ready_items=%s,
                       hard_block_items=%s,human_exception_items=%s,auto_correction_items=%s,
                       automation_rate=%s,grouped_source_blocks=%s,individual_page_approvals=0,
                       content_families=%s,script_documents=%s,reproducible_ready_decisions=%s,
                       timings_ms=%s::jsonb,counters=%s::jsonb,completed_at=now()
                   WHERE id=%s""",
                (
                    campaign_id,
                    version_id,
                    "passed" if passed else "failed",
                    result["ready_items"],
                    result["hard_block_items"],
                    result["human_exception_items"],
                    result["auto_correction_items"],
                    result["automation_rate"],
                    result["grouped_source_blocks"],
                    result["content_families"],
                    result["script_documents"],
                    result["reproducible_ready_decisions"],
                    _json(timings),
                    _json({**result, "timings_ms": timings}),
                    acceptance_id,
                ),
            )
        if not passed:
            raise RuntimeError(_json(result))
        return result
    except Exception as exc:
        if acceptance_id is not None:
            with database.transaction() as conn:
                conn.execute(
                    """UPDATE football_brief.autopilot_acceptance_runs
                       SET status='failed',error=%s::jsonb,completed_at=now()
                       WHERE id=%s AND status='running'""",
                    (
                        _json({"type": type(exc).__name__, "message": str(exc)[:4000]}),
                        acceptance_id,
                    ),
                )
        raise
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the measured 1,000-item automatic pre-generation acceptance gate."
    )
    parser.add_argument("--items", type=int, default=1_000)
    parser.add_argument("--supported-items", type=int, default=950)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--acceptance-key")
    parser.add_argument("--actor", default="local-admin")
    parser.add_argument("--worker-actor", default="local-reviewer")
    args = parser.parse_args()
    result = run_acceptance(
        items=args.items,
        supported_items=args.supported_items,
        concurrency=args.concurrency,
        acceptance_key=args.acceptance_key,
        actor=args.actor,
        worker_actor=args.worker_actor,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
