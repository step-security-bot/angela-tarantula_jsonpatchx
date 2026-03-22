import pytest
from httpx import AsyncClient

from tests.integration.fastapi_tests.conftest import patch_json

pytestmark = pytest.mark.anyio


async def test_demo3_rocket_boost(demo3_client: AsyncClient) -> None:
    patch = [
        {"op": "increment", "path": "/limits/max_users", "value": 50},
        {"op": "toggle", "path": "/features/chat"},
    ]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["limits"]["max_users"] == 300
    assert payload["features"]["chat"] is False


async def test_demo3_tag_and_seal(demo3_client: AsyncClient) -> None:
    patch = [
        {"op": "ensure_object", "path": "/features"},
        {"op": "append", "path": "/tags", "value": "beta"},
    ]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert "beta" in payload["tags"]
    assert isinstance(payload["features"], dict)


async def test_demo3_shuffle_switch(demo3_client: AsyncClient) -> None:
    patch = [
        {"op": "swap", "a": "/service_name", "b": "/features/chat"},
        {"op": "toggle", "path": "/features/chat"},
    ]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 409


async def test_demo3_oops_expected(demo3_client: AsyncClient) -> None:
    patch = [
        {"op": "ensure_object", "path": "/features"},
        {"op": "remove_number", "path": "/service_name"},
    ]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 409


async def test_demo3_set_message_string(demo3_client: AsyncClient) -> None:
    patch = [
        {
            "op": "set_message",
            "path": "/service_name",
            "message": "Atlas rolling deploy",
        }
    ]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["service_name"] == "Atlas rolling deploy"


async def test_demo3_set_message_null(demo3_client: AsyncClient) -> None:
    patch = [{"op": "set_message", "path": "/service_name", "message": None}]

    response = await patch_json(demo3_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["service_name"] is None
