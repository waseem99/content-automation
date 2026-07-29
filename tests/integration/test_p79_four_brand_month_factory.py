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


def test_static_snapshot_is_built_while_studio_v2_uses_runtime_data() -> None:
    app = (ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2.js").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build-static-creator-ui.js").read_text(encoding="utf-8")

    assert "StudioApi.brands()" in app
    assert "StudioApi.overview()" in app
    assert "data.blockers?.length" in app
    assert 'fetch("data/month-factory.json"' not in app
    assert 'path.join("data", "month-factory.json")' in build
    assert "/publish" not in app
