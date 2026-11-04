---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/schemas.py
hits:
  - pipeline/video_factory/videos.py
  - pipeline/video_factory/lock.py
  - tests/test_schemas.py
---

# schemas

Validates a document against a JSON Schema (Draft 2020-12) with `jsonschema`, and returns every violation as a sorted list of "where : what" lines; `duration_bounds` reads the bounds of `duree_visee` from the script schema, the one place they are written, for `qc`.

## Why this shape

The schemas are published files, the single definition of each contract; code never restates them, it validates against them. Validators are cached per file, and `def_problems` validates against one entry of `$defs` (the video id) without copying it.

## If you change this

- **Hits:** [videos](videos.md) and [lock](lock.md), the two callers; `tests/test_schemas.py`; the pinned `jsonschema` in `pyproject.toml` and `uv.lock`.
- **Does not hit:** the schemas themselves ([state schema](../contracts/state-schema.md), [script schema](../contracts/script-schema.md)).

## See

- [`problems`](../../../../pipeline/video_factory/schemas.py), [`def_problems`](../../../../pipeline/video_factory/schemas.py), [`validator`](../../../../pipeline/video_factory/schemas.py)
