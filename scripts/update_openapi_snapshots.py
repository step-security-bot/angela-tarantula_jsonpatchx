"""Regenerate FastAPI OpenAPI snapshot fixtures used as API contract artifacts.

This repository treats generated OpenAPI as part of the product surface of
``jsonpatchx``. Committed snapshots make contract changes explicit in each PR
and commit, so reviewers can see exactly what API/schema behavior changed.

The snapshot files are derived artifacts, so they must be refreshed whenever
code or dependency updates affect generated OpenAPI. This script is used both:

- locally via pre-commit/``prek`` hooks, and
- in GitHub automation workflows (including Dependabot-triggered PR updates).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# pylint: disable=wrong-import-position
from examples.fastapi import demo1, demo2, demo3, demo4, demo5, demo6  # noqa: E402
from tests.integration.fastapi_tests.test_openapi_contract_snapshot import (  # noqa: E402
    SNAPSHOT_PATH,
    _build_openapi,
)


def _write_snapshot(path: Path, schema: object) -> None:
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}")


def _format_with_biome(snapshot_paths: list[Path]) -> None:
    targets = [str(path.relative_to(ROOT)) for path in snapshot_paths]

    biome = shutil.which("biome")
    if biome is not None:
        cmd = [biome, "format", "--write", *targets]
    elif shutil.which("npx") is not None:
        cmd = ["npx", "--yes", "@biomejs/biome", "format", "--write", *targets]
    else:
        print("warning: skipped biome formatting (no 'biome' or 'npx' found in PATH)")
        return

    subprocess.run(cmd, cwd=ROOT, check=True)


def _format_with_prettier(snapshot_paths: list[Path]) -> None:
    targets = [str(path.relative_to(ROOT)) for path in snapshot_paths]

    prettier = shutil.which("prettier")
    if prettier is not None:
        cmd = [prettier, "--write", *targets]
    elif shutil.which("npx") is not None:
        cmd = ["npx", "--yes", "prettier", "--write", *targets]
    else:
        print(
            "warning: skipped prettier formatting (no 'prettier' or 'npx' found in PATH)"
        )
        return

    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    """Write and format all generated OpenAPI snapshot files."""
    snapshot_dir = ROOT / "tests" / "integration" / "fastapi_tests" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    snapshot_paths = [
        snapshot_dir / "demo1_openapi.json",
        snapshot_dir / "demo2_openapi.json",
        snapshot_dir / "demo3_openapi.json",
        snapshot_dir / "demo4_openapi.json",
        snapshot_dir / "demo5_openapi.json",
        snapshot_dir / "demo6_openapi.json",
        SNAPSHOT_PATH,
    ]
    snapshot_schemas = [
        demo1.app.openapi(),
        demo2.app.openapi(),
        demo3.app.openapi(),
        demo4.app.openapi(),
        demo5.app.openapi(),
        demo6.app.openapi(),
        _build_openapi(),
    ]

    for path, schema in zip(snapshot_paths, snapshot_schemas, strict=True):
        _write_snapshot(path, schema)

    # _format_with_biome(snapshot_paths)
    _format_with_prettier(snapshot_paths)


if __name__ == "__main__":
    main()
