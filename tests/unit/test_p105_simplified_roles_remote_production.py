from pathlib import Path

from src.operator_api.access import (
    AccessPermission,
    OperatorIdentity,
    OperatorRole,
    expand_operator_roles,
    public_operator_roles,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0092_simplified_operator_roles.sql"
START = ROOT / "scripts" / "windows" / "start_local_production.ps1"
REMOTE = ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1"
HIGGSFIELD = ROOT / "scripts" / "windows" / "setup_higgsfield_official.ps1"
READINESS = ROOT / "scripts" / "windows" / "check_production_readiness.ps1"
ROLE_BRIDGE = ROOT / "web" / "static-creator-ui" / "assets" / "role-aware-api.js"
RUNBOOK = ROOT / "docs" / "operations" / "PRODUCTION_ACTIVATION.md"


def test_public_roles_expand_to_existing_service_capabilities() -> None:
    super_admin = expand_operator_roles((OperatorRole.SUPER_ADMIN,))
    admin = expand_operator_roles((OperatorRole.ADMIN,))
    reviewer = expand_operator_roles((OperatorRole.REVIEWER,))

    assert super_admin == frozenset(OperatorRole)
    assert {OperatorRole.ADMIN, OperatorRole.REVIEWER, OperatorRole.PRODUCER, OperatorRole.PUBLISHER} <= admin
    assert {OperatorRole.REVIEWER, OperatorRole.PRODUCER, OperatorRole.PUBLISHER} <= reviewer
    assert public_operator_roles(super_admin) == ("super_admin",)
    assert public_operator_roles(admin) == ("admin",)
    assert public_operator_roles(reviewer) == ("reviewer",)


def test_public_reviewer_can_complete_workflow_but_bare_legacy_reviewer_stays_limited() -> None:
    public_reviewer = OperatorIdentity(
        operator_id="reviewer.one",
        key_name="reviewer-key",
        roles=expand_operator_roles((OperatorRole.REVIEWER,)),
        brand_ids=frozenset({"brand-one"}),
    )
    for permission in (
        AccessPermission.READ_PORTFOLIO,
        AccessPermission.EDIT_CONTENT,
        AccessPermission.REVIEW_CONTENT,
        AccessPermission.RUN_PRODUCTION,
        AccessPermission.DELIVER_RELEASE,
    ):
        assert public_reviewer.permits(permission)
    assert not public_reviewer.permits(AccessPermission.MANAGE_USERS)
    assert not public_reviewer.permits(AccessPermission.MANAGE_BRANDS)

    legacy_reviewer = OperatorIdentity(
        operator_id="legacy.reviewer",
        key_name="legacy-key",
        roles=frozenset({OperatorRole.REVIEWER}),
        brand_ids=frozenset({"brand-one"}),
    )
    assert legacy_reviewer.permits(AccessPermission.REVIEW_CONTENT)
    assert not legacy_reviewer.permits(AccessPermission.RUN_PRODUCTION)
    assert not legacy_reviewer.permits(AccessPermission.DELIVER_RELEASE)


def test_forward_migration_preserves_internal_capabilities() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "'super_admin'" in migration
    assert "'admin'" in migration
    assert "'reviewer'" in migration
    assert "'producer'" in migration
    assert "'publisher'" in migration
    assert "ON CONFLICT DO NOTHING" in migration
    assert "DELETE FROM football_brief.operator_user_roles" not in migration


def test_windows_launcher_upgrades_existing_keys_without_exposing_secrets() -> None:
    script = START.read_text(encoding="utf-8")
    assert "Sync-SimplifiedOperatorKeys" in script
    assert '"local-super-admin"' in script
    assert '"local-admin"' in script
    assert '"local-reviewer"' in script
    assert "local-producer" in script
    assert "local-publisher" in script
    assert "operator-keys.json" in script
    assert "Write-Host $superAdminKey" not in script


def test_remote_deployment_exposes_only_authenticated_creator_studio() -> None:
    script = REMOTE.read_text(encoding="utf-8")
    assert "ngrok config check" in script
    assert "-ExposeWithNgrok" in script
    assert "http://127.0.0.1:4040/api/tunnels" in script
    assert "authentication_required = $true" in script
    assert "postgres_exposed = $false" in script
    assert "ollama_exposed = $false" in script
    assert "comfyui_exposed = $false" in script


def test_official_higgsfield_setup_is_account_gated_and_spend_safe() -> None:
    script = HIGGSFIELD.read_text(encoding="utf-8")
    assert "npm install --global @higgsfield/cli" in script
    assert "higgsfield auth login" in script
    assert "https://mcp.higgsfield.ai/mcp" in script
    assert "external_spend_enabled = $false" in script
    assert "No generation or credit spend was triggered" in script


def test_readiness_report_does_not_claim_real_execution() -> None:
    script = READINESS.read_text(encoding="utf-8")
    assert "live_publishing_validated = $false" in script
    assert "p100_real_pilot_completed = $false" in script
    assert "six_video_benchmark_completed = $false" in script
    assert "three_role_model" in script
    assert "remote_https_ready" in script


def test_creator_studio_collapses_internal_roles_for_users() -> None:
    javascript = ROLE_BRIDGE.read_text(encoding="utf-8")
    assert 'if (values.has("super_admin")) return "super_admin"' in javascript
    assert 'if (values.has("admin")) return "admin"' in javascript
    assert 'return "reviewer"' in javascript
    assert "internal_roles" in javascript
    assert "upsertOperator" in javascript


def test_activation_runbook_keeps_real_evidence_gates_explicit() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "Do not create placeholder evidence" in runbook
    assert "one real shot" in runbook
    assert "one separately approved external live result" in runbook
    assert "three Rawr Nation and three Animal X" in runbook
