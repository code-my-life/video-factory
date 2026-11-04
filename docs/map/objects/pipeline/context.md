---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/context.py
hits:
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/chain.py
---

# context

The video a step works on (`Video`): its folder, state, script, the store, the toolbox and the route; steps read earlier outputs through it, checked to be in the store.

## Why this shape

Steps never look up a path themselves, so the store layout and the state shape are known in one place.

## If you change this

- **Hits:** [steps](steps.md) and [chain](chain.md).
- **Does not hit:** the state file format ([state](state.md)).

## See

- [`Video`](../../../../pipeline/video_factory/context.py), [`StepError`](../../../../pipeline/video_factory/context.py)
