import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_staging_compose_is_local_passworded_and_migration_gated():
    compose = (ROOT / "deploy/portfolio-staging/compose.yaml").read_text()
    assert "POSTGRES_PASSWORD" in compose
    assert "POSTGRES_HOST_AUTH_METHOD" not in compose
    assert '127.0.0.1:${POSTGRES_PORT:-5433}:5432' in compose
    assert '127.0.0.1:${OPERATOR_API_PORT:-8000}:8000' in compose
    assert "condition: service_completed_successfully" in compose
    assert 'OPERATOR_RUNTIME_AUTO_CONNECT_DATABASE: "true"' in compose
    assert "OPERATOR_API_KEYS_JSON" in compose
    assert "OPERATOR_CORS_ORIGINS" in compose


def test_brand_bootstrap_has_seven_workspaces_without_invented_links():
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text())
    assert len(config["brands"]) == 7
    assert sum(brand["content_mode"] == "video" for brand in config["brands"]) == 6
    assert sum(brand["content_mode"] == "mixed" for brand in config["brands"]) == 1

    placeholders = [
        brand for brand in config["brands"]
        if brand["metadata"]["onboarding_status"].startswith("blocked")
    ]
    onboarded = [brand for brand in config["brands"] if brand not in placeholders]

    assert len(placeholders) == 3
    assert all(brand["source_links"] == [] for brand in placeholders)
    assert len(onboarded) == 4
    assert all(
        brand["source_links"]
        and all(link.startswith("https://www.facebook.com/") for link in brand["source_links"])
        for brand in onboarded
    )


def test_bootstrap_and_smoke_scripts_never_embed_secrets_or_publish():
    bootstrap = (ROOT / "scripts/p71_bootstrap_portfolio.py").read_text()
    smoke = (ROOT / "scripts/p71_smoke_portfolio.py").read_text()
    assert 'os.getenv("OPERATOR_KEY"' in bootstrap
    assert 'os.getenv("OPERATOR_KEY"' in smoke
    assert "/publish" not in bootstrap
    assert "/publish" not in smoke
    assert "automatic_publishing\": False" in bootstrap


def test_runtime_database_connect_is_explicit_opt_in():
    config = (ROOT / "src/operator_api/runtime_config.py").read_text()
    entrypoint = (ROOT / "src/operator_api/entrypoint.py").read_text()
    assert "auto_connect_database: bool = Field(default=False)" in config
    assert "if not settings.auto_connect_database" in entrypoint
    assert "database.open(require_schema=settings.database_require_schema)" in entrypoint
    assert "OPERATOR_API_KEYS_JSON" in entrypoint
