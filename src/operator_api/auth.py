from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException, Request, status

from src.operator_api.access import OperatorIdentity, OperatorRole


OPERATOR_KEY_HEADER = "x-operator-key"
IdentityLoader = Callable[[str, str], OperatorIdentity | None]


@dataclass(frozen=True, slots=True)
class OperatorAuthSettings:
    api_keys: dict[str, str] = field(default_factory=dict)
    identities: dict[str, OperatorIdentity] = field(default_factory=dict)
    resolve_identities_from_database: bool = False
    disabled: bool = False
    disabled_operator_id: str = "local-test-operator"

    @classmethod
    def for_tests(
        cls,
        *,
        key: str = "test-key",
        operator_id: str = "api-test-operator",
        roles: tuple[OperatorRole, ...] = (OperatorRole.ADMIN,),
        brand_ids: tuple[str, ...] = (),
        active: bool = True,
    ) -> "OperatorAuthSettings":
        identity = OperatorIdentity(
            operator_id=operator_id,
            key_name="test-key",
            roles=frozenset(roles),
            brand_ids=frozenset(brand_ids),
            active=active,
            display_name=operator_id,
        )
        return cls(api_keys={key: operator_id}, identities={operator_id: identity})

    @classmethod
    def disabled_for_local_tests(cls, *, operator_id: str = "local-test-operator") -> "OperatorAuthSettings":
        return cls(disabled=True, disabled_operator_id=operator_id)


def build_operator_auth(settings: OperatorAuthSettings, identity_loader: IdentityLoader | None = None):
    def authenticate(request: Request) -> OperatorIdentity:
        injected = getattr(request.state, "operator_identity", None)
        if isinstance(injected, OperatorIdentity):
            return injected
        if settings.disabled:
            return OperatorIdentity(
                operator_id=settings.disabled_operator_id,
                key_name="disabled-local-test",
                roles=frozenset({OperatorRole.ADMIN}),
                active=True,
                display_name=settings.disabled_operator_id,
            )
        key = request.headers.get(OPERATOR_KEY_HEADER, "")
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="operator key is required",
            )
        operator_id = settings.api_keys.get(key)
        if operator_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="operator key is invalid",
            )
        identity = settings.identities.get(operator_id)
        if identity is None and settings.resolve_identities_from_database and identity_loader is not None:
            identity = identity_loader(operator_id, "operator-key")
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="operator access record is missing",
            )
        if not identity.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="operator is inactive",
            )
        if not identity.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="operator has no assigned role",
            )
        return identity

    return authenticate
