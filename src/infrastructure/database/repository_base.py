from typing import Any, Generic, TypeVar

from psycopg import Connection
from pydantic import BaseModel

RecordT = TypeVar("RecordT", bound=BaseModel)


class RepositoryError(RuntimeError):
    pass


class NotFoundError(RepositoryError):
    pass


class BaseRepository(Generic[RecordT]):
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    @staticmethod
    def required(
        row: dict[str, Any] | None,
        model: type[RecordT],
        entity: str,
    ) -> RecordT:
        if row is None:
            raise NotFoundError(f"{entity} was not found")
        return model.model_validate(row)
