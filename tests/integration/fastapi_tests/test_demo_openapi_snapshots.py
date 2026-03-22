"""
OpenAPI snapshots for end-to-end FastAPI demo applications.

This test verifies that the published OpenAPI docs for demo1-6 remain stable as
examples evolve, including route-helper behavior and example-driven schema output.
"""

import json
from pathlib import Path

import pytest

from examples.fastapi import demo1, demo2, demo3, demo4, demo5, demo6

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


@pytest.mark.parametrize(
    "name,app",
    [
        ("demo1", demo1.app),
        ("demo2", demo2.app),
        ("demo3", demo3.app),
        ("demo4", demo4.app),
        ("demo5", demo5.app),
        ("demo6", demo6.app),
    ],
    ids=lambda item: item[0] if isinstance(item, tuple) else str(item),
)
def test_demo_openapi_snapshot(name: str, app: object) -> None:
    snapshot_path = SNAPSHOT_DIR / f"{name}_openapi.json"
    if not snapshot_path.exists():  # pragma: no cover
        pytest.fail(f"OpenAPI snapshot missing: {snapshot_path}")

    expected = json.loads(snapshot_path.read_text())
    actual = app.openapi()
    assert actual == expected
