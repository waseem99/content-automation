from __future__ import annotations

from pydantic import Field

from src.application.secrets.provider import SecretRequirement, SecretValidationReport, SecretValidator
from src.application.storage.provider import LocalStorageProvider
from src.domain.base import FrozenRecord
from src.infrastructure.database.connection import Database, DatabaseHealth


class DependencyStatus(FrozenRecord):
    name: str
    ok: bool
    error: str | None = None


class ReadinessReport(FrozenRecord):
    ok: bool
    dependencies: tuple[DependencyStatus, ...]
    secrets: SecretValidationReport | None = None
    database: DatabaseHealth | None = None


class HealthCheckService:
    def __init__(self, *, database: Database | None = None, storage: LocalStorageProvider | None = None, secrets: SecretValidator | None = None) -> None:
        self.database = database
        self.storage = storage
        self.secrets = secrets

    def readiness(self, *, requirements: tuple[SecretRequirement, ...] = ()) -> ReadinessReport:
        dependencies: list[DependencyStatus] = []
        db_health = None
        if self.database is not None:
            db_health = self.database.health_check()
            dependencies.append(DependencyStatus(name="database", ok=db_health.ok, error=db_health.error))
        if self.storage is not None:
            try:
                self.storage.ensure_ready()
                dependencies.append(DependencyStatus(name="storage", ok=True))
            except Exception as exc:
                dependencies.append(DependencyStatus(name="storage", ok=False, error=str(exc)))
        secret_report = self.secrets.validate(requirements) if self.secrets is not None else None
        if secret_report is not None:
            dependencies.append(DependencyStatus(name="secrets", ok=secret_report.ok, error=",".join(secret_report.missing) if secret_report.missing else None))
        ok = all(item.ok for item in dependencies)
        return ReadinessReport(ok=ok, dependencies=tuple(dependencies), secrets=secret_report, database=db_health)

    def health(self) -> ReadinessReport:
        return self.readiness(requirements=())
