---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/service.py
  - pipeline/video_factory/studio/__init__.py
hits:
  - hermes/install.sh
---

# service

`vf studio serve`: builds the studio from the manifest and the environment (`STUDIO_URL`, `HERMES_BIN`, `VF_*`), runs a pass every `tick_seconds` and serves the page until SIGTERM.

## Why this shape

One process for the page and the passes shares one lock, so a gesture on the page and a pass never move a card at the same time.

## If you change this

- **Hits:** the user service written by `hermes/install.sh`.
- **Does not hit:** Hermès's dispatcher and gateway, which keep running on their own.

## See

- [`build`](../../../../pipeline/video_factory/studio/service.py), [`serve`](../../../../pipeline/video_factory/studio/service.py)
