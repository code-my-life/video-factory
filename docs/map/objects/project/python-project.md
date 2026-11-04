---
type: object
cluster: project
universe: live
paths:
  - pyproject.toml
  - uv.lock
  - .python-version
hits:
  - .github/workflows/ci.yml
  - pipeline/video_factory/cli.py
---

# Python project

`pyproject.toml`, `uv.lock` and `.python-version`: Python 3.12, the package `video_factory` from `pipeline/` (uv_build backend), the console script `vf`, the exact versions of `jsonschema`, `pytest` and `ruff`, and the ruff and pytest settings.

## Why this shape

Dependencies are pinned twice (exact versions in `pyproject.toml`, hashes in `uv.lock`), and CI installs with `uv sync --locked`, which fails when the two disagree. The package root is `pipeline/` so the repository keeps one top-level folder per part of the chain.

## If you change this

- **Hits:** the `verify` job of the [workflows](../barriers/workflows.md) (`uv sync --locked`); the command name `vf` used by [cli](../pipeline/cli.md) and every document; the lint rules every file must pass.
- **Does not hit:** the external tools ([tools lock](../toolchain/tools-lock.md)).

## See

- The entry point [`main`](../../../../pipeline/video_factory/cli.py) declared as `vf`; the project: [`pyproject.toml`](../../../../pyproject.toml)
