from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    operator_id: str
    token_name: str


@dataclass(frozen=True, slots=True)
class OperatorAuthSettings:
    api_keys: dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    disabled_operator_id: str = "local-test-operator"

    @classmethod
    def for_tests(cls, *, token: str = "test-token", operator_id: str = "api-test-operator") -> "OperatorAuthSettings":
        return cls(api_keys={token: operator_id})

    @classmethod
    def disabled_for_local_tests(cls, *, operator_id: str = "local-test-operator") -> "OperatorAuthSettings":
        return cls(disabled=True, disabled_operator_id=operator_id)


def build_operator_auth(settings: OperatorAuthSettings):
    def authenticate(request: Request) -> OperatorIdentity:
        if settings.disabled:
            return OperatorIdentity(operator_id=settings.disabled_operator_id, token_name="disabled-local-test")
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="operator auth token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        operator_id = settings.api_keys.get(token)
        if operator_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="operator auth token is invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return OperatorIdentity(operator_id=operator_id, token_name="api-key")

    return authenticate
