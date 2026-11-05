---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/chain.py
hits:
  - pipeline/video_factory/cli.py
  - tests/test_state.py
  - tests/test_capture.py
---

# chain

The registry of steps (order, upstream steps, tools, code files), the staleness reasons, `status`, `run` (never run, stale or asked for; later steps only when their inputs change), the record written after each step, and the registration of takes and captures.

## Why this shape

Comparing fingerprints, tool versions, parameters and a fingerprint of each step's own sources means a change anywhere that matters marks the step stale, and an unchanged output stops the cascade (criterion C4). Compose's sources include every file of `templates/hyperframes/` except `camera-follow/`, the scene of `vf capture`, which compose never reads (#19).

## If you change this

- **Hits:** `vf ingest`, `vf status` and `vf run` ([cli](cli.md)); every `state.json`; `tests/test_state.py`; `tests/test_capture.py` (the capture scene stays out of `TEMPLATE`).
- **Does not hit:** what each step does ([steps](steps.md)).

## See

- [`STEPS`](../../../../pipeline/video_factory/chain.py), [`reasons`](../../../../pipeline/video_factory/chain.py), [`status`](../../../../pipeline/video_factory/chain.py), [`run`](../../../../pipeline/video_factory/chain.py), [`run_step`](../../../../pipeline/video_factory/chain.py)
