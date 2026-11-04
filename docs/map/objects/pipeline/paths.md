---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/paths.py
hits:
  - pipeline/video_factory/cli.py
  - docs/RUNBOOK.md
  - tests/test_paths.py
---

# paths

Where `vf` finds its own resources (lock, schemas, template, read from the checkout) and the three outside places: the content clone (`VF_CONTENT`), the media store (`VF_MEDIA`) and the tools (`VF_TOOLS`).

## Why this shape

The package is installed in editable mode by `uv sync` and never distributed alone, so the repository resources are read from the checkout instead of being copied into the package. The outside places come from the environment with defaults under the home directory, and `places` is pure: it takes the environment and the home as arguments.

## If you change this

- **Hits:** every default location (`~/perso/video-content`, `~/studio/media`, `~/.local/share/video-factory/tools`), documented in `docs/RUNBOOK.md`; [cli](cli.md); `tests/test_paths.py`.
- **Does not hit:** the layout inside the tools directory ([lock](lock.md) owns `tool_dir`).

## See

- [`places`](../../../../pipeline/video_factory/paths.py), [`Places`](../../../../pipeline/video_factory/paths.py), [`REPO_ROOT`](../../../../pipeline/video_factory/paths.py)
