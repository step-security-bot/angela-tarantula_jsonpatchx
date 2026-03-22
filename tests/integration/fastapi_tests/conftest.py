from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from examples.fastapi import demo1, demo2, demo3, demo4, demo5, demo6
from examples.fastapi.shared import reset_store


@pytest.fixture(autouse=True)
def _reset_demo_store() -> Generator[None]:
    reset_store()
    yield
    reset_store()


def make_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def demo1_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo1.app) as client:
        yield client


@pytest.fixture
async def demo2_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo2.app) as client:
        yield client


@pytest.fixture
async def demo3_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo3.app) as client:
        yield client


@pytest.fixture
async def demo4_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo4.app) as client:
        yield client


@pytest.fixture
async def demo5_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo5.app) as client:
        yield client


@pytest.fixture
async def demo6_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(demo6.app) as client:
        yield client


async def patch_json(client: AsyncClient, url: str, patch: list[dict[str, Any]]):
    return await client.patch(
        url,
        json=patch,
        headers={"Content-Type": "application/json-patch+json"},  # test others
    )
