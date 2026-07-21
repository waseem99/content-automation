from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Iterable

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from src.infrastructure.database.connection import Database


class OperatorRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    PRODUCER = "producer"
    PUBLISHER = "publisher"


class AccessPermission(StrEnum):
    MANAGE_USERS = "manage_users"
    MANAGE_BRANDS = "manage_brands"
    READ_PORTFOLIO = "read_portfolio"
    EDIT_CONTENT = "edit_content"
    REVIEW_CONTENT = "review_content"
    RUN_PRODUCTION = "run_production"
    DELIVER_RELEASE = "deliver_release"


ROLE_PERMISSIONS: dict[OperatorRole, frozenset[AccessPermission]] = {
    OperatorRole.ADMIN: frozenset(AccessPermission),
    OperatorRole.REVIEWER: frozenset(
        {AccessPermission.READ_PORTFOLIO, AccessPermission.REVIEW_CONTENT}
    ),
    OperatorRole.PRODUCER: frozenset(
        {
            AccessPermission.READ_PORTFOLIO,
            AccessPermission.EDIT_CONTENT,
            AccessPermission.RUN_PRODUCTION,
        }
    ),
    OperatorRole.PUBLISHER: frozenset(
        {AccessPermission.READ_PORTFOLIO, AccessPermission.DELIVER_RELEASE}
    ),
}


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    operator_id: str
    key_name: str
    roles: frozenset[OperatorRole]
    brand_ids: frozenset[str] = frozenset()
    active: bool = True
    display_name: str | None = None

    @property
    def is_admin(self) -> bool:
        return OperatorRole.ADMIN in self.roles

    def permits(self, permission: AccessPermission) -> bool:
        return self.active and any(permission in ROLE_PERMISSIONS[role] for role in self.roles)

    def can_access_brand(self, brand_id: str | None) -> bool:
        if not self.active:
            return False
        if self.is_admin:
            return True
        return brand_id is not None and str(brand_id) in self.brand_ids


def require_access(
    identity: OperatorIdentity,
    permission: AccessPermission,
    *,
    brand_id: str | None = None,
) -> None:
    if not identity.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="operator_inactive")
    if not identity.permits(permission):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission_denied")
    if brand_id is not None and not identity.can_access_brand(str(brand_id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="brand_access_denied")


def visible_brand_ids(identity: OperatorIdentity) -> frozenset[str] | None:
    """Return None for portfolio-wide admins, otherwise the explicit brand scope."""
    return None if identity.is_admin else identity.brand_ids


class OperatorAccessService:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def identity(self, operator_id: str, *, key_name: str = "operator-key") -> OperatorIdentity | None:
        with self.database.connection() as conn:
            user = conn.execute(
                "SELECT id, operator_id, display_name, active FROM football_brief.operator_users WHERE operator_id=%s",
                (operator_id,),
            ).fetchone()
            if not user:
                return None
            roles = conn.execute(
                "SELECT role FROM football_brief.operator_user_roles WHERE operator_user_id=%s ORDER BY role",
                (user["id"],),
            ).fetchall()
            brands = conn.execute(
                "SELECT brand_id FROM football_brief.operator_brand_assignments WHERE operator_user_id=%s ORDER BY brand_id",
                (user["id"],),
            ).fetchall()
        return OperatorIdentity(
            operator_id=str(user["operator_id"]),
            key_name=key_name,
            display_name=str(user["display_name"]),
            active=bool(user["active"]),
            roles=frozenset(OperatorRole(str(row["role"])) for row in roles),
            brand_ids=frozenset(str(row["brand_id"]) for row in brands),
        )

    def list_users(self) -> list[dict[str, Any]]:
        with self.database.connection() as conn:
            rows = conn.execute(
                """SELECT u.id, u.operator_id, u.display_name, u.active, u.created_by,
                          u.created_at, u.updated_at,
                          COALESCE(array_agg(DISTINCT r.role) FILTER (WHERE r.role IS NOT NULL), '{}') AS roles,
                          COALESCE(array_agg(DISTINCT a.brand_id::text) FILTER (WHERE a.brand_id IS NOT NULL), '{}') AS brand_ids
                   FROM football_brief.operator_users u
                   LEFT JOIN football_brief.operator_user_roles r ON r.operator_user_id=u.id
                   LEFT JOIN football_brief.operator_brand_assignments a ON a.operator_user_id=u.id
                   GROUP BY u.id
                   ORDER BY u.display_name, u.operator_id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_user(
        self,
        *,
        operator_id: str,
        display_name: str,
        active: bool,
        roles: Iterable[str],
        brand_ids: Iterable[str],
        actor: str,
    ) -> dict[str, Any]:
        normalized_roles = sorted({OperatorRole(str(role)).value for role in roles})
        normalized_brands = sorted({str(brand_id) for brand_id in brand_ids})
        if not normalized_roles:
            raise ValueError("at least one operator role is required")
        if OperatorRole.ADMIN.value not in normalized_roles and not normalized_brands:
            raise ValueError("non-admin operators require at least one brand assignment")
        with self.database.transaction() as conn:
            user = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id, display_name, active, created_by)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (operator_id) DO UPDATE SET
                     display_name=EXCLUDED.display_name,
                     active=EXCLUDED.active
                   RETURNING *""",
                (operator_id, display_name, active, actor),
            ).fetchone()
            conn.execute(
                "DELETE FROM football_brief.operator_user_roles WHERE operator_user_id=%s",
                (user["id"],),
            )
            for role in normalized_roles:
                conn.execute(
                    """INSERT INTO football_brief.operator_user_roles
                       (operator_user_id, role, assigned_by) VALUES (%s,%s,%s)""",
                    (user["id"], role, actor),
                )
            conn.execute(
                "DELETE FROM football_brief.operator_brand_assignments WHERE operator_user_id=%s",
                (user["id"],),
            )
            for brand_id in normalized_brands:
                conn.execute(
                    """INSERT INTO football_brief.operator_brand_assignments
                       (operator_user_id, brand_id, assigned_by) VALUES (%s,%s::uuid,%s)""",
                    (user["id"], brand_id, actor),
                )
        identity = self.identity(operator_id)
        if identity is None:
            raise RuntimeError("operator identity was not persisted")
        return {
            "operator_id": identity.operator_id,
            "display_name": identity.display_name,
            "active": identity.active,
            "roles": sorted(role.value for role in identity.roles),
            "brand_ids": sorted(identity.brand_ids),
        }
