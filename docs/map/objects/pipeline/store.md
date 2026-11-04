---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/store.py
hits:
  - pipeline/video_factory/chain.py
  - tests/test_store.py
---

# store

The media store (`VF_MEDIA`): files at `<sha256>.<ext>`, folders at `<tree sha256>.<ext>`, read-only, stored once; scratch folders inside it so results move in by rename.

## Why this shape

Content addressing makes a reference in `state.json` mean the same bytes forever and lets identical results be kept once.

## If you change this

- **Hits:** [chain](chain.md) and [context](context.md); the RUNBOOK's cleaning advice; `tests/test_store.py`.
- **Does not hit:** the content clone, where only scripts and states live.

## See

- [`put`](../../../../pipeline/video_factory/store.py), [`put_tree`](../../../../pipeline/video_factory/store.py), [`problem`](../../../../pipeline/video_factory/store.py), [`scratch`](../../../../pipeline/video_factory/store.py)
