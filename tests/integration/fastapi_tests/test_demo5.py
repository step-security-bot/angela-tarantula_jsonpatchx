import pytest
from httpx import AsyncClient

from tests.integration.fastapi_tests.conftest import patch_json

pytestmark = pytest.mark.anyio


async def test_demo5_explicit_backend_ops_apply(demo5_client: AsyncClient) -> None:
    patch = [
        {"op": "explicit_increment", "path": "mana", "value": 10},
        {"op": "explicit_append", "path": "sigils", "value": "glint"},
    ]

    response = await patch_json(demo5_client, "/apprentices/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mana"] == 130
    assert payload["sigils"][-1] == "glint"


async def test_demo5_explicit_backend_rejects_slash_paths(
    demo5_client: AsyncClient,
) -> None:
    patch = [{"op": "explicit_increment", "path": "/mana", "value": 5}]

    response = await patch_json(demo5_client, "/apprentices/1", patch)

    assert response.status_code == 409
