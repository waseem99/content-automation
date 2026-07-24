from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "src" / "operations" / "local_worker_v2.py"


def test_reconciliation_query_uses_generation_job_queue_timestamp() -> None:
    source = WORKER.read_text(encoding="utf-8")
    assert "ORDER BY queued_at,id LIMIT 20" in source
    assert "ORDER BY completed_at" not in source
