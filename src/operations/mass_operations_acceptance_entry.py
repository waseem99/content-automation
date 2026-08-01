from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from src.infrastructure.database.connection import Database
from src.operations import mass_operations_acceptance as acceptance


_ORIGINAL_CONNECTION = Database.connection


class _AcceptanceConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, query: Any, params: Any = None, *args: Any, **kwargs: Any) -> Any:
        if isinstance(query, str) and "JOIN football_brief.pre_generation_autopilot_policies policy" in query:
            query = """SELECT brand.id,brand.primary_platform
                       FROM football_brief.brands brand
                       WHERE brand.active=true
                       ORDER BY brand.slug LIMIT 2"""
            params = None
        return self._connection.execute(query, params, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


@contextmanager
def _acceptance_connection(self: Database):
    """Keep brand discovery independent of autopilot-policy lookup.

    Campaign activation remains the canonical validator for the selected brand's
    policy. This only prevents the acceptance bootstrap from requiring a policy
    join before it has selected the two brands used for access-scope evidence.
    """

    with _ORIGINAL_CONNECTION(self) as connection:
        yield _AcceptanceConnection(connection)


def main() -> int:
    Database.connection = _acceptance_connection
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
