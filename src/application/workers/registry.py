from __future__ import annotations

from dataclasses import dataclass

from src.application.workers.models import WorkerDefinition, WorkerHandler


class WorkerRegistryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredWorker:
    definition: WorkerDefinition
    handler: WorkerHandler


class WorkerRegistry:
    def __init__(self) -> None:
        self._workers: dict[tuple[str, str], RegisteredWorker] = {}

    def register(self, definition: WorkerDefinition, handler: WorkerHandler) -> None:
        key = (definition.name, definition.version)
        if key in self._workers:
            raise WorkerRegistryError(f"Worker already registered: {definition.name}@{definition.version}")
        self._workers[key] = RegisteredWorker(definition=definition, handler=handler)

    def get(self, name: str, version: str) -> RegisteredWorker:
        key = (name, version)
        try:
            return self._workers[key]
        except KeyError as exc:
            raise WorkerRegistryError(f"Worker not registered: {name}@{version}") from exc

    def definitions(self) -> tuple[WorkerDefinition, ...]:
        return tuple(worker.definition for worker in self._workers.values())
