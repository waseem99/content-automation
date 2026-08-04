from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from src.operations.settings import OperationsSettings
from src.operator_api.operations_middleware import OperationsSafetyMiddleware


ROOT = Path(__file__).resolve().parents[2]


def build_rate_limited_client(
    *,
    anonymous_limit: int,
    authenticated_limit: int,
    trusted_keys: set[str],
) -> TestClient:
    settings = OperationsSettings(
        _env_file=None,
        structured_logs=False,
        requests_per_minute=anonymous_limit,
        authenticated_requests_per_minute=authenticated_limit,
    )
    app = FastAPI()
    app.add_middleware(
        OperationsSafetyMiddleware,
        settings=settings,
        trusted_operator_keys=trusted_keys,
    )

    @app.get("/limited")
    def limited() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_valid_operator_receives_a_separate_but_bounded_rate_window() -> None:
    client = build_rate_limited_client(
        anonymous_limit=1,
        authenticated_limit=3,
        trusted_keys={"trusted-admin"},
    )

    assert client.get("/limited").status_code == 200
    anonymous_limited = client.get("/limited")
    assert anonymous_limited.status_code == 429
    assert anonymous_limited.json()["rate_limit_scope"] == "client"

    headers = {"X-Operator-Key": "trusted-admin"}
    assert [client.get("/limited", headers=headers).status_code for _ in range(3)] == [
        200,
        200,
        200,
    ]
    operator_limited = client.get("/limited", headers=headers)
    assert operator_limited.status_code == 429
    assert operator_limited.json()["rate_limit_scope"] == "authenticated_operator"


def test_unknown_rotating_operator_keys_cannot_bypass_the_client_limit() -> None:
    client = build_rate_limited_client(
        anonymous_limit=1,
        authenticated_limit=10,
        trusted_keys={"trusted-admin"},
    )

    assert client.get("/limited", headers={"X-Operator-Key": "forged-one"}).status_code == 200
    second = client.get("/limited", headers={"X-Operator-Key": "forged-two"})
    assert second.status_code == 429
    assert second.json()["rate_limit_scope"] == "client"


def test_distinct_valid_operators_do_not_share_one_rate_window() -> None:
    client = build_rate_limited_client(
        anonymous_limit=1,
        authenticated_limit=1,
        trusted_keys={"operator-a", "operator-b"},
    )

    assert client.get("/limited", headers={"X-Operator-Key": "operator-a"}).status_code == 200
    assert client.get("/limited", headers={"X-Operator-Key": "operator-a"}).status_code == 429
    assert client.get("/limited", headers={"X-Operator-Key": "operator-b"}).status_code == 200
    assert client.get("/limited", headers={"X-Operator-Key": "operator-b"}).status_code == 429


def test_authenticated_limit_is_never_weaker_than_the_client_contract() -> None:
    with pytest.raises(ValidationError, match="cannot be lower"):
        OperationsSettings(
            _env_file=None,
            requests_per_minute=120,
            authenticated_requests_per_minute=119,
        )


def test_runtime_and_environment_expose_the_two_bounded_limits() -> None:
    runtime = (ROOT / "src/operator_api/runtime_factory.py").read_text(encoding="utf-8")
    sync = (ROOT / "scripts/windows/sync_p131_environment.ps1").read_text(encoding="utf-8")
    staging = (ROOT / "config/staging.env.example").read_text(encoding="utf-8")
    production = (ROOT / "config/production.env.example").read_text(encoding="utf-8")

    assert "trusted_operator_keys=frozenset(auth.api_keys)" in runtime
    assert 'OPS_AUTHENTICATED_REQUESTS_PER_MINUTE"] = "600"' in sync
    assert "OPS_REQUESTS_PER_MINUTE=120" in staging
    assert "OPS_AUTHENTICATED_REQUESTS_PER_MINUTE=600" in staging
    assert "OPS_REQUESTS_PER_MINUTE=120" in production
    assert "OPS_AUTHENTICATED_REQUESTS_PER_MINUTE=600" in production
