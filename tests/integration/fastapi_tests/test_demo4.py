import pytest
from httpx import AsyncClient

from tests.integration.fastapi_tests.conftest import patch_json

pytestmark = pytest.mark.anyio


async def test_demo4_spellbook_midnight_runes(demo4_client: AsyncClient) -> None:
    patch = [
        {"op": "replace", "path": "/rituals/summon/enabled", "value": True},
        {"op": "increment", "path": "ingredients.moon_salt", "value": 5},
    ]

    response = await patch_json(demo4_client, "/spellbooks/grimoire", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["rituals"]["summon"]["enabled"] is True
    assert payload["ingredients"]["moon_salt"] == 8


async def test_demo4_apprentice_sparkle_sprint(demo4_client: AsyncClient) -> None:
    patch = [
        {"op": "replace", "path": "/name", "value": "Morgan Vale"},
        {"op": "increment", "path": "mana", "value": 20},
        {"op": "append", "path": "sigils", "value": "aurora"},
    ]

    response = await patch_json(demo4_client, "/apprentices/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Morgan Vale"
    assert payload["mana"] == 140
    assert payload["sigils"][-1] == "aurora"


async def test_demo4_apprentice_lantern_lesson(demo4_client: AsyncClient) -> None:
    patch = [
        {"op": "replace", "path": "/name", "value": "Nova"},
        {"op": "append", "path": "sigils", "value": "ember"},
    ]

    response = await patch_json(demo4_client, "/apprentices/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Nova"
    assert payload["sigils"][-1] == "ember"
