from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from src.operator_api.studio_v2_batch_runtime import install_studio_v2_batch_routes
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def _auth_settings(seeded) -> OperatorAuthSettings:
    identities = {
        seeded["producer"]: OperatorIdentity(
            operator_id=str(seeded["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(seeded["brand_one"])}),
            active=True,
        ),
        seeded["outsider"]: OperatorIdentity(
            operator_id=str(seeded["outsider"]),
            key_name="outsider-key",
            display_name="Outside Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(seeded["brand_two"])}),
            active=True,
        ),
    }
    return OperatorAuthSettings(
        api_keys={
            "producer-key": str(seeded["producer"]),
            "outsider-key": str(seeded["outsider"]),
        },
        identities=identities,
    )


def test_content_state_batch_is_bounded_deduplicated_and_brand_scoped(
    p89_database,
    p89_seeded,
) -> None:
    auth = _auth_settings(p89_seeded)
    app = create_configured_app(
        database=p89_database,
        auth_settings=auth,
        runtime_settings=OperatorRuntimeSettings(_env_file=None, database_require_schema=False),
    )
    install_studio_v2_batch_routes(
        app,
        database=p89_database,
        auth_settings=auth,
    )
    client = TestClient(app)

    allowed = client.post(
        "/studio-v2/content-states",
        headers={"X-Operator-Key": "producer-key"},
        json={"content_ids": [str(p89_seeded["content_one"]), str(p89_seeded["content_one"])]},
    )
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["items"][0]["item"]["id"] == str(p89_seeded["content_one"])

    forbidden = client.post(
        "/studio-v2/content-states",
        headers={"X-Operator-Key": "producer-key"},
        json={"content_ids": [str(p89_seeded["content_two"])]},
    )
    assert forbidden.status_code == 403

    outsider = client.post(
        "/studio-v2/content-states",
        headers={"X-Operator-Key": "outsider-key"},
        json={"content_ids": [str(p89_seeded["content_two"])]},
    )
    assert outsider.status_code == 200, outsider.text
