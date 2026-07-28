from pathlib import Path

import pytest
from fastapi import HTTPException

from src.operator_api.access import (
    AccessPermission,
    OperatorIdentity,
    OperatorRole,
    require_access,
    visible_brand_ids,
)
from src.operator_api.access_runtime import (
    _brand_is_required,
    _required_permission,
    self_review_conflict,
)
from src.operator_api.auth import OperatorAuthSettings


ROOT = Path(__file__).resolve().parents[2]
BRAND_A = "11111111-1111-1111-1111-111111111111"
BRAND_B = "22222222-2222-2222-2222-222222222222"


def identity(*roles: OperatorRole, brands: tuple[str, ...] = (BRAND_A,), active: bool = True) -> OperatorIdentity:
    return OperatorIdentity(
        operator_id="person.one",
        key_name="test",
        display_name="Person One",
        roles=frozenset(roles),
        brand_ids=frozenset(brands),
        active=active,
    )


def test_simplified_reviewer_role_can_complete_the_content_workflow() -> None:
    reviewer = identity(OperatorRole.REVIEWER)
    legacy_producer = identity(OperatorRole.PRODUCER)
    legacy_publisher = identity(OperatorRole.PUBLISHER)

    require_access(reviewer, AccessPermission.READ_PORTFOLIO, brand_id=BRAND_A)
    require_access(reviewer, AccessPermission.EDIT_CONTENT, brand_id=BRAND_A)
    require_access(reviewer, AccessPermission.REVIEW_CONTENT, brand_id=BRAND_A)
    require_access(reviewer, AccessPermission.RUN_PRODUCTION, brand_id=BRAND_A)
    require_access(reviewer, AccessPermission.DELIVER_RELEASE, brand_id=BRAND_A)

    with pytest.raises(HTTPException):
        require_access(reviewer, AccessPermission.MANAGE_USERS)
    with pytest.raises(HTTPException):
        require_access(reviewer, AccessPermission.MANAGE_BRANDS)

    # Historical capability roles remain least-privilege when encountered in
    # old audit records or pre-upgrade fixtures.
    with pytest.raises(HTTPException):
        require_access(legacy_producer, AccessPermission.REVIEW_CONTENT, brand_id=BRAND_A)
    with pytest.raises(HTTPException):
        require_access(legacy_publisher, AccessPermission.EDIT_CONTENT, brand_id=BRAND_A)


def test_brand_assignments_fail_closed_for_non_admins() -> None:
    reviewer = identity(OperatorRole.REVIEWER)
    require_access(reviewer, AccessPermission.READ_PORTFOLIO, brand_id=BRAND_A)
    with pytest.raises(HTTPException) as denied:
        require_access(reviewer, AccessPermission.READ_PORTFOLIO, brand_id=BRAND_B)
    assert denied.value.detail == "brand_access_denied"
    assert visible_brand_ids(reviewer) == frozenset({BRAND_A})


def test_admin_is_portfolio_wide_but_inactive_users_are_blocked() -> None:
    admin = identity(OperatorRole.ADMIN, brands=())
    require_access(admin, AccessPermission.MANAGE_USERS, brand_id=BRAND_B)
    assert visible_brand_ids(admin) is None

    super_admin = identity(OperatorRole.SUPER_ADMIN, brands=())
    require_access(super_admin, AccessPermission.MANAGE_USERS, brand_id=BRAND_B)
    assert visible_brand_ids(super_admin) is None

    inactive = identity(OperatorRole.ADMIN, active=False)
    with pytest.raises(HTTPException) as denied:
        require_access(inactive, AccessPermission.MANAGE_USERS)
    assert denied.value.detail == "operator_inactive"


def test_test_auth_defaults_to_an_explicit_admin_identity() -> None:
    settings = OperatorAuthSettings.for_tests()
    operator_id = settings.api_keys["test-key"]
    principal = settings.identities[operator_id]
    assert principal.roles == frozenset({OperatorRole.ADMIN})
    assert principal.active is True


def test_runtime_permission_map_separates_review_production_and_delivery() -> None:
    assert _required_permission("POST", "/portfolio/content/x/approvals") == AccessPermission.REVIEW_CONTENT
    assert _required_permission("POST", "/portfolio/content/x/artifacts") == AccessPermission.RUN_PRODUCTION
    assert _required_permission("POST", "/portfolio/content/x/packages") == AccessPermission.RUN_PRODUCTION
    assert _required_permission("POST", "/portfolio/packages/x/metrics") == AccessPermission.DELIVER_RELEASE
    assert _required_permission("POST", "/portfolio/brands") == AccessPermission.MANAGE_BRANDS
    assert _required_permission("GET", "/portfolio/queue") == AccessPermission.READ_PORTFOLIO
    assert _required_permission("GET", "/health") is None


def test_brand_scope_is_required_for_mutating_and_detailed_resources() -> None:
    assert _brand_is_required("POST", "/portfolio/content/11111111-1111-1111-1111-111111111111/workspace")
    assert _brand_is_required("POST", "/portfolio/plans")
    assert _brand_is_required("POST", "/portfolio/reference-jobs/11111111-1111-1111-1111-111111111111/progress")
    assert _brand_is_required("GET", "/portfolio/references/11111111-1111-1111-1111-111111111111")
    assert not _brand_is_required("POST", "/portfolio/brands")
    assert not _brand_is_required("POST", "/portfolio/references")


def test_reviewer_cannot_approve_own_preview_or_final_artifact() -> None:
    own_preview = [
        {"kind": "voiceover", "created_by": "person.one"},
        {"kind": "preview", "created_by": "other.person"},
    ]
    assert self_review_conflict(stage="preview", reviewer="person.one", artifacts=own_preview)
    assert not self_review_conflict(stage="preview", reviewer="independent.reviewer", artifacts=own_preview)
    assert self_review_conflict(
        stage="package",
        reviewer="person.one",
        artifacts=[{"kind": "final_video", "created_by": "person.one"}],
    )
    assert not self_review_conflict(
        stage="script",
        reviewer="person.one",
        artifacts=[{"kind": "preview", "created_by": "person.one"}],
    )


def test_access_migration_and_runtime_wiring_are_present() -> None:
    migration = (ROOT / "migrations" / "0029_operator_access_control.sql").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(encoding="utf-8")
    entrypoint = (ROOT / "src" / "operator_api" / "entrypoint.py").read_text(encoding="utf-8")
    access_runtime = (ROOT / "src" / "operator_api" / "access_runtime.py").read_text(encoding="utf-8")
    creator_api = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text(encoding="utf-8")

    assert migration.startswith("-- Football Brief")
    assert "CREATE TABLE football_brief.operator_users" in migration
    assert "CREATE TABLE football_brief.operator_user_roles" in migration
    assert "CREATE TABLE football_brief.operator_brand_assignments" in migration
    assert "role IN ('admin', 'reviewer', 'producer', 'publisher')" in migration
    assert "API keys remain outside PostgreSQL" in migration
    assert migration.rstrip().endswith("COMMIT;")
    assert "install_operator_access" in runtime
    assert "resolve_identities_from_database=True" in entrypoint
    assert "self_review_not_allowed" in access_runtime
    assert '"/access/me"' in access_runtime
    assert 'access: () => request("/access/me")' in creator_api
