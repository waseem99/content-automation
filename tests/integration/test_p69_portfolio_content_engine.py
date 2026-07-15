from pathlib import Path

from src.application.portfolio_service import (
    analytics_recommendation,
    canonical_concept,
    concept_fingerprint,
    paid_render_route,
    platform_package_defaults,
    semantic_key,
)


ROOT = Path(__file__).resolve().parents[2]


def test_concept_fingerprint_is_stable_and_brand_scoped():
    first = concept_fingerprint(brand_slug="animal-x", concept="How elephants hear through the ground!", format_name="vertical")
    same = concept_fingerprint(brand_slug="animal-x", concept="How elephants hear through the ground", format_name="vertical")
    other = concept_fingerprint(brand_slug="rawr", concept="How elephants hear through the ground", format_name="vertical")
    assert first == same
    assert first != other
    assert len(first) == 64
    assert canonical_concept("  The OWL's Flight! ") == "the owl s flight"
    assert semantic_key("Why the owl flies in silence") == "flies-owl-silence"


def test_render_router_escalates_only_quality_critical_shots():
    assert paid_render_route({"hero_shot": True})["tier"] == "premium"
    assert paid_render_route({"realism_critical": True})["paid"] is True
    assert paid_render_route({"factual_graphic": True})["tier"] == "deterministic"
    assert paid_render_route({})["tier"] == "open_source_preview"


def test_platform_packages_are_watermark_free_and_facebook_first():
    packages = platform_package_defaults(title="Elephant signals", caption="A hidden language.", hashtags=["#animals", "science", "animals"])
    assert [item["platform"] for item in packages] == ["facebook", "youtube_shorts", "tiktok"]
    assert all(item["watermark_free"] for item in packages)
    assert packages[0]["hashtags"] == ["animals", "science"]


def test_analytics_changes_creative_before_cadence():
    assert analytics_recommendation({"views": 1000, "three_second_view_rate": 30})["action"] == "rewrite_hook"
    assert analytics_recommendation({"views": 1000, "three_second_view_rate": 70, "average_view_percentage": 40})["action"] == "tighten_middle"
    assert analytics_recommendation({"views": 1000, "three_second_view_rate": 70, "average_view_percentage": 70, "shares": 20})["cadence"] == "increase_selectively"


def test_portfolio_migration_contains_required_persistent_entities():
    sql = (ROOT / "migrations" / "0026_portfolio_content_engine.sql").read_text()
    for table in ("brands", "monthly_content_plans", "portfolio_content", "portfolio_approvals", "reusable_clips", "platform_packages", "performance_observations"):
        assert f"CREATE TABLE football_brief.{table}" in sql
    assert "premium_spend" in sql
    assert "UNIQUE (plan_id, concept_fingerprint)" in sql
    assert "Append-only analytics observations" in sql


def test_operator_api_exposes_portfolio_without_publish_endpoint():
    source = (ROOT / "src" / "operator_api" / "app.py").read_text()
    for route in (
        '/portfolio/brands',
        '/portfolio/plans',
        '/portfolio/queue',
        '/portfolio/content',
        '/portfolio/content/{content_id}/approvals',
        '/portfolio/content/{content_id}/packages',
        '/portfolio/packages/{package_id}/metrics',
    ):
        assert route in source
    assert '/portfolio/publish' not in source
    runtime_factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text()
    assert "from src.operator_api.app import create_app" in runtime_factory
    assert "from src.operator_api.runtime_app import create_app" not in runtime_factory


def test_operator_api_cors_is_explicit_and_never_wildcarded():
    source = (ROOT / "src" / "operator_api" / "app.py").read_text()
    assert "OPERATOR_CORS_ORIGINS" in source
    assert "allow_origins=allowed_origins" in source
    assert 'allow_origins=["*"]' not in source
    assert 'allow_headers=["Content-Type", "X-Operator-Key"]' in source
    assert "Annotated[OperatorIdentity" not in source
    assert "operator=Depends(require_operator)" in source
