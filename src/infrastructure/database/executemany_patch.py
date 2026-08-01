from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

from src.infrastructure.database.connection import Database


_ORIGINAL_CONNECTION = Database.connection


class _ConnectionWithExecuteMany:
    """Expose cursor.executemany through the platform connection boundary.

    Psycopg 3 keeps ``executemany`` on cursors rather than connections. Several
    database-native bulk workflows intentionally use the transaction connection
    as their unit of work; this proxy preserves that API while still executing
    every batch inside the caller's existing transaction.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def executemany(self, query: Any, params_seq: Iterable[Any]) -> None:
        with self._connection.cursor() as cursor:
            cursor.executemany(query, params_seq)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


@contextmanager
def _connection_with_executemany(self: Database):
    with _ORIGINAL_CONNECTION(self) as connection:
        if hasattr(connection, "executemany"):
            yield connection
        else:
            yield _ConnectionWithExecuteMany(connection)


def install_executemany_connection_patch() -> None:
    if getattr(Database, "_executemany_connection_patch_installed", False):
        return
    Database.connection = _connection_with_executemany
    Database._executemany_connection_patch_installed = True


__all__ = ["install_executemany_connection_patch"]
