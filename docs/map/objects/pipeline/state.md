---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/state.py
hits:
  - schemas/state.schema.json
  - pipeline/video_factory/context.py
  - tests/test_state.py
---

# state

Reads `state.json` (moving an empty version 1 state to version 2), validates every write against the published schema, and writes through a temporary file renamed in place.

## Why this shape

A state is never half written and never breaks its contract; version 1 states had no step, so only empty ones are moved.

## If you change this

- **Hits:** every `state.json` in `video-content`; the [state schema](../contracts/state-schema.md); `tests/test_state.py`.
- **Does not hit:** the steps' logic.

## See

- [`load`](../../../../pipeline/video_factory/state.py), [`save`](../../../../pipeline/video_factory/state.py), [`migrate`](../../../../pipeline/video_factory/state.py)
