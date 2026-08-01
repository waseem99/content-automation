from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from src.infrastructure.database.connection import Database
from src.operations import storage_scale_acceptance as acceptance


_ORIGINAL_CONNECTION = Database.connection


class _TypedAcceptanceConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        if isinstance(query, str):
            query = query.replace(
                "'workspace://p129/' || %s || '/' || value::text",
                "'workspace://p129/' || %s::text || '/' || value::text",
            )
            query = query.replace(
                "digest((%s || ':' || value::text)::bytea,'sha256')",
                "digest((%s::text || ':' || value::text)::bytea,'sha256')",
            )
            query = query.replace(
                "'p129_acceptance',%s,",
                "'p129_acceptance',%s::text,",
            )
            query = query.replace(
                "'gdrive://p129-' || %s || '-' || asset.id::text",
                "'gdrive://p129-' || %s::text || '-' || asset.id::text",
            )
        return self._connection.execute(query, params, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


@contextmanager
def _typed_connection(self: Database):
    """Apply explicit text casts to acceptance-only synthetic seed parameters."""

    with _ORIGINAL_CONNECTION(self) as connection:
        yield _TypedAcceptanceConnection(connection)


def main() -> int:
    Database.connection = _typed_connection
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
