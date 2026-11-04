---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/tools.py
hits:
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/compose.py
  - tests/conftest.py
---

# tools

The pinned tools as steps call them (`Toolbox`): paths under `VF_TOOLS`, models, the render image, the files of a library (each checked against its SHA-256 before a project gets it), and the versions a step records (lock entries, video-factory, the Python packages).

## Why this shape

A missing tool stops a step with the command that installs it; `vf doctor` remains the full check.

## If you change this

- **Hits:** [steps](steps.md) and [chain](chain.md); the tests' `tools` fixture.
- **Does not hit:** the lock's content ([tools lock](../toolchain/tools-lock.md)).

## See

- [`Toolbox`](../../../../pipeline/video_factory/tools.py), [`python_versions`](../../../../pipeline/video_factory/tools.py)
