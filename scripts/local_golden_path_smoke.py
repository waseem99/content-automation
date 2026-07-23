from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from typing import Any

import httpx


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"{method} {path} returned non-JSON ({response.status_code})") from exc
    if response.is_error or payload.get("ok") is False:
        detail = payload.get("detail") or payload.get("error") or payload
        raise RuntimeError(f"{method} {path} failed ({response.status_code}): {detail}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exercise the real local API/database path without approving or publishing."
    )
    parser.add_argument("--base-url", default=os.getenv("LOCAL_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--operator-key", default=os.getenv("LOCAL_ADMIN_OPERATOR_KEY", ""))
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
    parser.add_argument("--brand", default="rawr-nation")
    parser.add_argument("--candidate-count", type=int, default=4)
    args = parser.parse_args(argv)
    if not args.operator_key:
        raise SystemExit("LOCAL_ADMIN_OPERATOR_KEY or --operator-key is required")

    headers = {"X-Operator-Key": args.operator_key, "Content-Type": "application/json"}
    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=120) as client:
        ready = request(client, "GET", "/runtime/ready")
        access = request(client, "GET", "/access/me")
        brands = request(client, "GET", "/portfolio/brands")
        brand = next((item for item in brands.get("brands", []) if item.get("slug") == args.brand), None)
        if not brand:
            raise RuntimeError(f"seeded brand not found: {args.brand}")

        month = os.getenv("LOCAL_PLAN_MONTH", date.today().replace(day=1).isoformat())
        count = args.candidate_count
        pillars = list(brand.get("content_pillars") or ["education"])
        pillar_targets = {pillars[index % len(pillars)].lower().replace(" ", "_"): 0 for index in range(count)}
        for index in range(count):
            key = pillars[index % len(pillars)].lower().replace(" ", "_")
            pillar_targets[key] += 1
        batch = request(
            client,
            "POST",
            "/concepts/batches",
            json={
                "brand_id": brand["id"],
                "month_start": month,
                "candidate_count": count,
                "format_mix": {"vertical_short": count},
                "pillar_targets": pillar_targets,
                "seed": 20260722,
                "adapter_mode": "local_model",
                "local_model_id": args.model,
                "local_endpoint": "http://127.0.0.1:11434",
                "local_timeout_seconds": 120,
            },
        )
        queue = request(client, "GET", f"/portfolio/queue?brand_id={brand['id']}")
        sample = next((item for item in queue.get("items", []) if item.get("metadata", {}).get("local_smoke_fixture")), None)
        workflow = None
        if sample:
            try:
                workflow = request(client, "POST", f"/production/content/{sample['id']}/workflow")
            except RuntimeError as exc:
                if "already" not in str(exc).lower() and "conflict" not in str(exc).lower():
                    raise
                workflow = request(client, "GET", f"/production/content/{sample['id']}/workflow")
        jobs = request(client, "GET", "/generation/jobs?limit=20")

    output = {
        "ok": True,
        "kind": "local_golden_path_smoke",
        "runtime_ready": bool(ready.get("ok")),
        "operator": access.get("operator_id") or access.get("operator", {}).get("operator_id"),
        "brand": {"id": brand["id"], "slug": brand["slug"]},
        "concept_batch": {
            "id": str(batch.get("batch", {}).get("id") or ""),
            "candidate_count": len(batch.get("candidates") or []),
            "adapter": (batch.get("batch", {}).get("adapter_mode")),
            "fallback_evidence": (batch.get("candidates") or [{}])[0].get("generation_evidence", {}),
        },
        "sample_content_id": sample.get("id") if sample else None,
        "workflow_initialized": bool(workflow),
        "queue_count": jobs.get("count", 0),
        "next_human_gate": "shortlist and approve concepts before script generation",
        "automatic_approval": False,
        "managed_spend": False,
        "live_delivery": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2), file=sys.stderr)
        raise
