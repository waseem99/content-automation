from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "web/static-creator-ui/assets/portfolio-api.js"
MODULE = ROOT / "web/static-creator-ui/assets/routing-spend.js"
STYLE = ROOT / "web/static-creator-ui/assets/routing-spend.css"


def test_routing_spend_module_is_loaded_by_studio_registry() -> None:
    api = API.read_text(encoding="utf-8")
    assert '["routing-spend", "routing-spend.css", "routing-spend.js"]' in api
    assert "currentRouting" in api
    assert "submitRouting" in api
    assert "decideRouting" in api
    assert "enqueueManagedRoute" in api


def test_routing_spend_panel_exposes_exact_cost_and_alternatives_without_credentials() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "Shot Routing & Spend" in source
    assert "Route alternatives, approval ceiling, and actual cost evidence" in source
    assert "Monthly soft / hard" in source
    assert "Approved ceiling" in source
    assert "Alternatives" in source
    assert "Reserve & enqueue managed shot" in source
    assert "Overage:" in source
    assert "spend reserved" in source.lower()
    assert "provider_request" not in source
    assert "api_key" not in source.lower()
    assert "secret" not in source.lower()
    assert "password" not in source.lower()
    assert "publish" not in source.lower()
    assert "X-Operator-Key" not in source
    assert "openai" not in source.lower()
    assert "replicate" not in source.lower()


def test_routing_spend_styles_are_present() -> None:
    style = STYLE.read_text(encoding="utf-8")
    assert ".routing-spend-section" in style
    assert ".routing-spend-grid" in style
    assert ".routing-spend-metric" in style
    assert ".routing-spend-warning" in style
