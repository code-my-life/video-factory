---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/publish.py
hits:
  - docs/publication.md
  - tests/test_board.py
---

# publish

`vf publish <id>`: checks that `qc` passed and the master's outputs are in the store, then puts the TikTok export, the master (hard links) and the caption (the script's title and the robot credit) in `VF_MEDIA/publication/<id>/`. It posts nothing.

## Why this shape

Publication is manual until #6; the Publication lane only prepares, and the owner posts.

## If you change this

- **Hits:** the Publication lane and the page's publication view; the credit text of `docs/publication.md`.
- **Does not hit:** the state: nothing is written to `state.json`.

## See

- [`prepare`](../../../../pipeline/video_factory/publish.py), [`write`](../../../../pipeline/video_factory/publish.py)
