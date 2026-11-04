---
type: object
cluster: toolchain
universe: live
paths:
  - toolchain/tools.lock.json
  - toolchain/tools.lock.schema.json
hits:
  - pipeline/video_factory/lock.py
  - pipeline/video_factory/doctor.py
  - pipeline/video_factory/install.py
  - tests/test_lock.py
  - docs/RUNBOOK.md
---

# tools lock

`toolchain/tools.lock.json`: every external tool of the chain, pinned by exact version and SHA-256, with its download URL and its install command; its schema fixes the fields of each kind (archive, file, source build, npm, Docker image).

## Why this shape

Determinism starts with the tools: the same inputs only give the same frames with the same FFmpeg, whisper.cpp, model and HyperFrames. Each hash was computed from the downloaded file, never copied. `not_pinned_yet` says what the lock does not hold yet (the fonts, the HyperFrames render image) rather than leaving it implied.

## If you change this

- **Hits:** the machines, which `vf doctor` reports as out of date until `vf doctor --install` runs; `tests/test_lock.py`; the version notes in `docs/RUNBOOK.md`; for HyperFrames, the [npm lockfile](hyperframes-npm.md) in the same pull request.
- **Does not hit:** the Python dependencies, pinned by `uv.lock` ([Python project](../project/python-project.md)).

## See

- [`load`](../../../../pipeline/video_factory/lock.py) reads it; the data: [`tools.lock.json`](../../../../toolchain/tools.lock.json), [`tools.lock.schema.json`](../../../../toolchain/tools.lock.schema.json)
