from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.operations.animal_x_month_preproduction_resilient as module
from src.application.concepts.adapters import ConceptAdapterError


def test_strict_local_generation_never_uses_fallback() -> None:
    class Primary:
        name = "local_model"

        def generate(self, **_: object):
            raise ConceptAdapterError("bad local response")

    class Fallback:
        called = False

        def generate(self, **_: object):
            self.called = True
            return []

    fallback = Fallback()
    with pytest.raises(ConceptAdapterError, match="bad local response"):
        module.strict_local_generation(
            primary=Primary(),
            fallback=fallback,
            context={},
            slots=[SimpleNamespace(ordinal=1)],
            seed=1,
        )
    assert fallback.called is False


def test_adaptive_local_adapter_splits_large_failed_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    class FakeAdapter:
        def __init__(self, **_: object) -> None:
            pass

        def generate(self, *, context: dict, slots: list, seed: int):
            del context, seed
            calls.append(len(slots))
            if len(slots) > 1:
                raise ConceptAdapterError("response too large")
            return [slots[0]]

    monkeypatch.setattr(module, "CoreLocalHttpConceptAdapter", FakeAdapter)
    adapter = module.AdaptiveLocalConceptAdapter(
        endpoint="http://127.0.0.1:11434",
        model_id="qwen2.5:7b",
        timeout_seconds=120,
    )
    slots = [SimpleNamespace(ordinal=index) for index in range(1, 9)]
    output = adapter.generate(context={}, slots=slots, seed=20260917)
    assert [item.ordinal for item in output] == list(range(1, 9))
    assert len(output) == 8
    assert 4 in calls
    assert 1 in calls


def test_adaptive_local_adapter_retries_single_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    class FakeAdapter:
        def __init__(self, **_: object) -> None:
            pass

        def generate(self, *, context: dict, slots: list, seed: int):
            nonlocal attempts
            del context, seed
            attempts += 1
            if attempts < 3:
                raise ConceptAdapterError("temporary malformed json")
            return [slots[0]]

    monkeypatch.setattr(module, "CoreLocalHttpConceptAdapter", FakeAdapter)
    slot = SimpleNamespace(ordinal=1)
    adapter = module.AdaptiveLocalConceptAdapter(
        endpoint="http://127.0.0.1:11434",
        model_id="qwen2.5:7b",
        timeout_seconds=120,
    )
    assert adapter.generate(context={}, slots=[slot], seed=9) == [slot]
    assert attempts == 3
