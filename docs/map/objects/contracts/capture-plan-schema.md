---
type: object
cluster: contracts
universe: live
paths:
  - schemas/capture-plan.schema.json
  - schemas/capture-source.schema.json
hits:
  - pipeline/video_factory/capture/plan.py
  - vitrine/
  - tests/test_capture.py
---

# capture plan and source schemas

`capture-plan.schema.json`: a plan `vf capture` shoots (app, device, window, scale, fps, view, scenario range, actions, stage, tracked elements, texts, camera). `capture-source.schema.json`: `vitrine/<app>/source.json`, the app's repository, pinned commit, scenario variant, Node.js entry of the lock, install and build commands and variables.

## Why this shape

The bounds the showcase videos hold are written here once: camera scale 1.6 to 2 (the action at 1.6 to 2 times its size), moves of 0.4 to 0.6 s, the iPhone at 390x844 (a rule in `plan.py`, with the order of the actions, a scenario that ends after it starts, and a camera that follows a tracked element at 30 fps).

## If you change this

- **Hits:** [capture](../pipeline/capture.md) (its defaults and rules), the plans under `vitrine/`, `tests/test_capture.py`.
- **Does not hit:** the state and script schemas of the chain.

## See

- [`capture-plan.schema.json`](../../../../schemas/capture-plan.schema.json), [`capture-source.schema.json`](../../../../schemas/capture-source.schema.json)
