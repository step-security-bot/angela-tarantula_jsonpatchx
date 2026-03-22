import pytest
from httpx import AsyncClient

from tests.integration.fastapi_tests.conftest import patch_json

pytestmark = pytest.mark.anyio


async def test_demo6_generic_backend_ops_apply(demo6_client: AsyncClient) -> None:
    patch = [
        {"op": "generic_increment", "path": "mana", "value": 15},
        {"op": "generic_append", "path": "sigils", "value": "flare"},
    ]

    response = await patch_json(demo6_client, "/apprentices/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mana"] == 135
    assert payload["sigils"][-1] == "flare"


async def test_demo6_generic_backend_rejects_slash_paths(
    demo6_client: AsyncClient,
) -> None:
    patch = [{"op": "generic_increment", "path": "/mana", "value": 5}]

    response = await patch_json(demo6_client, "/apprentices/1", patch)

    assert response.status_code == 409
