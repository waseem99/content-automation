from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status


OPERATOR_KEY_HEADER = "x-operator-key"


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    operator_id: str
    key_name: str


@dataclass(frozen=True, slots=True)
class OperatorAuthSettings:
    api_keys: dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    disabled_operator_id: str = "local-test-operator"

    @classmethod
    def for_tests(cls, *, key: str = "test-key", operator_id: str = "api-test-operator") -> "OperatorAuthSettings":
        return cls(api_keys={key: operator_id})

    @classmethod
    def disabled_for_local_tests(cls, *, operator_id: str = "local-test-operator") -> "OperatorAuthSettings":
        return cls(disabled=True, disabled_operator_id=operator_id)


def build_operator_auth(settings: OperatorAuthSettings):
    def authenticate(request: Request) -> OperatorIdentity:
        if settings.disabled:
            return OperatorIdentity(operator_id=settings.disabled_operator_id, key_name="disabled-local-test")
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
        return OperatorIdentity(operator_id=operator_id, key_name="operator-key")

    return authenticate
