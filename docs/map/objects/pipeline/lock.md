---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/lock.py
hits:
  - toolchain/tools.lock.json
  - toolchain/tools.lock.schema.json
  - pipeline/video_factory/doctor.py
  - pipeline/video_factory/install.py
  - tests/test_lock.py
---

# lock

Reads `toolchain/tools.lock.json`, checks it against its schema and the rules a schema cannot say (unique names, requirements declared first, install command equal to the one doctor prints), and gives each tool its directory and its environment.

## Why this shape

The lock is data; this module is the only reader, so `doctor` and `install` agree on where a tool lives (`tool_dir`) and how it runs (`tool_env`: the bin directories of its requirements first on `PATH`, then its own variables, which turn HyperFrames' telemetry and self-update off).

## If you change this

- **Hits:** every tool's location under `VF_TOOLS` (changing `tool_dir` orphans installed tools); [doctor](doctor.md) and [install](install.md); `tests/test_lock.py`.
- **Does not hit:** the published schemas of `video-content` ([state schema](../contracts/state-schema.md)).

## See

- [`load`](../../../../pipeline/video_factory/lock.py), [`rule_problems`](../../../../pipeline/video_factory/lock.py), [`tool_dir`](../../../../pipeline/video_factory/lock.py), [`tool_env`](../../../../pipeline/video_factory/lock.py), [`requirement_order`](../../../../pipeline/video_factory/lock.py)
