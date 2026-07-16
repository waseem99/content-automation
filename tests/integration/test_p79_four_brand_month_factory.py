import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "web" / "static-creator-ui" / "data" / "month-factory.json"


def test_static_manifest_exposes_real_queue_without_paid_or_publish_actions() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "p79.month_factory.v1"
    assert payload["priority_brand_count"] == 4
    assert payload["summary"]["concepts_ready"] == 48
    assert payload["summary"]["monthly_target"] == 96
    assert payload["summary"]["paid_render_jobs_started"] == 0
    assert payload["summary"]["publish_jobs_started"] == 0
    assert payload["guardrails"]["human_approval_before_paid_render"] is True
    assert payload["guardrails"]["human_approval_before_publish"] is True


def test_static_ui_loads_month_factory_and_surfaces_brief_blockers() -> None:
    app = (ROOT / "web" / "static-creator-ui" / "assets" / "app.js").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build-static-creator-ui.js").read_text(encoding="utf-8")

    assert 'fetch("data/month-factory.json"' in app
    assert "selected.blocker" in app
    assert 'path.join("data", "month-factory.json")' in build
    assert "paid_render_jobs_started" not in app
    assert "/publish" not in app
