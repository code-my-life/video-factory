---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/videos.py
hits:
  - schemas/state.schema.json
  - schemas/script.schema.json
  - templates/script.md
  - tests/test_new.py
---

# videos

`vf new <id>`: builds `script.md` from the template and `state.json` at schema version 1, validates both against the published schemas, and writes them into `VF_CONTENT/videos/<id>/`, refusing an id that exists.

## Why this shape

The texts are built by pure functions (`build`, `new_state`) and written only once both are valid, through a staged folder renamed in one step, so a failed `vf new` leaves nothing behind and an existing video is never overwritten. The id is checked against the schema's own rule before it becomes a path.

## If you change this

- **Hits:** the shape of `state.json` ([state schema](../contracts/state-schema.md)); the front matter the [template](../templates/script-template.md) must produce; `tests/test_new.py`; the files already committed in `video-content`.
- **Does not hit:** the toolchain ([lock](lock.md)); `vf new` needs no installed tool.

## See

- [`create`](../../../../pipeline/video_factory/videos.py), [`build`](../../../../pipeline/video_factory/videos.py), [`new_state`](../../../../pipeline/video_factory/videos.py), [`script_problems`](../../../../pipeline/video_factory/videos.py)
