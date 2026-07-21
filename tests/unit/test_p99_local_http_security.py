import pytest

from src.application.concepts.adapters import ConceptAdapterError, LocalHttpConceptAdapter
from src.application.scripts.adapters import LocalHttpScriptAdapter, ScriptAdapterError
from src.infrastructure.http.local_endpoint import LocalEndpointError, validate_local_http_endpoint


@pytest.mark.parametrize(
    "endpoint",
    (
        "https://localhost:11434",
        "http://localhost.evil.example:11434",
        "http://127.0.0.1.evil.example:11434",
        "http://user:pass@localhost:11434",
        "http://localhost:11434/api",
        "http://localhost:11434?redirect=https://evil.example",
        "http://localhost:11434#fragment",
        "file:///tmp/model.sock",
        "http://0.0.0.0:11434",
        "http://localhost:70000",
    ),
)
def test_local_endpoint_validator_rejects_non_origin_or_non_loopback_targets(endpoint: str) -> None:
    with pytest.raises(LocalEndpointError):
        validate_local_http_endpoint(endpoint)


@pytest.mark.parametrize(
    ("endpoint", "normalized"),
    (
        (" http://localhost:11434/ ", "http://localhost:11434"),
        ("http://127.0.0.1:8001", "http://127.0.0.1:8001"),
        ("http://[::1]:9000", "http://[::1]:9000"),
    ),
)
def test_local_endpoint_validator_accepts_only_loopback_http_origins(
    endpoint: str,
    normalized: str,
) -> None:
    assert validate_local_http_endpoint(endpoint) == normalized


def test_concept_and_script_adapters_share_the_fail_closed_validator() -> None:
    with pytest.raises(ConceptAdapterError, match="loopback"):
        LocalHttpConceptAdapter(
            endpoint="http://localhost.evil.example:11434",
            model_id="concept-model",
        )
    with pytest.raises(ScriptAdapterError, match="loopback"):
        LocalHttpScriptAdapter(
            endpoint="http://localhost.evil.example:11434",
            model_id="script-model",
        )

    assert LocalHttpConceptAdapter(
        endpoint="http://127.0.0.1:11434",
        model_id="concept-model",
    ).endpoint == "http://127.0.0.1:11434"
    assert LocalHttpScriptAdapter(
        endpoint="http://[::1]:11434/",
        model_id="script-model",
    ).endpoint == "http://[::1]:11434"
