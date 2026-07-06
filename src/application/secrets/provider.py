from __future__ import annotations

import os
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from src.domain.base import FrozenRecord


class RuntimeEnvironment(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"


class SecretRequirement(FrozenRecord):
    name: str = Field(min_length=1)
    provider: str | None = None
    required: bool = True


class SecretValidationReport(FrozenRecord):
    ok: bool
    missing: tuple[str, ...]
    provider_name: str
    environment: RuntimeEnvironment


class SecretProvider(Protocol):
    provider_name: str

    def get(self, name: str) -> str | None:
        ...


class EnvSecretProvider:
    provider_name = "env"

    def get(self, name: str) -> str | None:
        value = os.environ.get(name)
        if value is None or not value.strip():
            return None
        return value


class SecretValidator:
    def __init__(self, provider: SecretProvider, *, environment: RuntimeEnvironment = RuntimeEnvironment.LOCAL) -> None:
        self.provider = provider
        self.environment = environment

    def validate(self, requirements: tuple[SecretRequirement, ...]) -> SecretValidationReport:
        if self.environment == RuntimeEnvironment.PRODUCTION and self.provider.provider_name == "env":
            missing = tuple(req.name for req in requirements if req.required)
            return SecretValidationReport(ok=not missing, missing=missing, provider_name=self.provider.provider_name, environment=self.environment)
        missing = tuple(req.name for req in requirements if req.required and self.provider.get(req.name) is None)
        return SecretValidationReport(ok=not missing, missing=missing, provider_name=self.provider.provider_name, environment=self.environment)
