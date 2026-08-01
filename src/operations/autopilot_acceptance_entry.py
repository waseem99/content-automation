from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from src.operations import autopilot_acceptance as acceptance


T = TypeVar("T")


def _timed(
    timings: dict[str, float],
    key: str,
    callable_fn: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Time a callable without consuming its legitimate ``function`` keyword.

    The acceptance runner passes ``function=...`` through to ``_parallel``.
    Naming the wrapped callable ``callable_fn`` preserves that keyword instead
    of binding it twice at this timing boundary.
    """

    started = time.perf_counter()
    result = callable_fn(*args, **kwargs)
    timings[key] = round((time.perf_counter() - started) * 1000, 3)
    return result


def main() -> int:
    acceptance._timed = _timed
    return acceptance.main()


if __name__ == "__main__":
    raise SystemExit(main())
