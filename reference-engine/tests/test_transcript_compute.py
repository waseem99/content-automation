from __future__ import annotations

import sys
from types import SimpleNamespace

from refintel.transcript import _resolve_compute_type


def test_cpu_prefers_int8(monkeypatch) -> None:
    fake = SimpleNamespace(get_supported_compute_types=lambda _device: {"float32", "int8"})
    monkeypatch.setitem(sys.modules, "ctranslate2", fake)

    assert _resolve_compute_type("cpu", "default") == "int8"


def test_cuda_does_not_request_unsupported_float16(monkeypatch) -> None:
    fake = SimpleNamespace(
        get_supported_compute_types=lambda _device: {"float32", "int8_float32"}
    )
    monkeypatch.setitem(sys.modules, "ctranslate2", fake)

    assert _resolve_compute_type("cuda", "default") == "int8_float32"


def test_explicit_compute_type_is_preserved() -> None:
    assert _resolve_compute_type("cuda", "float32") == "float32"
