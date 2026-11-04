---
type: object
cluster: contracts
universe: live
paths:
  - schemas/state.schema.json
hits:
  - pipeline/video_factory/videos.py
  - schemas/script.schema.json
  - tests/test_schemas.py
  - tests/test_new.py
---

# state schema

`schemas/state.schema.json`, version 3: the state of a video in `video-content` (`videos/<id>/state.json`): its id, its creation date, the fingerprint of its script, its takes and captures, and for each step passed the fingerprints of its inputs, its outputs as references to the media store, the versions of its tools, its parameters, the fingerprint of its code, a summary, its times and its duration. An empty version 1 state, and a version 2 state without its route and its `scan` and `blur` steps, are read as version 3.

## Why this shape

Each step records what proves it ran on these exact inputs, so `vf status` finds a stale step by comparing fingerprints. The step names are closed (`ingest` to `qc`), and a change that existing states cannot follow creates version 2 instead of editing version 1.

## If you change this

- **Hits:** every `state.json` committed in `video-content`; [videos](../pipeline/videos.md), which writes it; the id rule copied in the [script schema](script-schema.md); the public `$id` URL on `main`; `tests/test_schemas.py` and `tests/test_new.py`.
- **Does not hit:** the tools lock: `tools` in a step records versions by tool name, it does not pin them.

## See

- Validated by [`problems`](../../../../pipeline/video_factory/schemas.py), written by [`new_state`](../../../../pipeline/video_factory/videos.py); the schema: [`state.schema.json`](../../../../schemas/state.schema.json)
