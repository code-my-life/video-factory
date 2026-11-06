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

`vf publish <id>`: checks that `qc` passed and the master's outputs are in the store, then puts the TikTok export, the master (hard links) and the caption in `VF_MEDIA/publication/<id>/`. The caption is the script's `legende` (its title otherwise), « Voix générée par IA (…) » when `voix_ia` names the tool, the robot credit and the script's `mots_cles`; an AI voice also prints the reminder of each platform's AI label. A showcase with a `vignette` gets its cover (`couverture.png`): the frame of the TikTok export at `vignette_image` under the vignette's text, in its theme's `cover.html`, rendered by the pinned Chromium. It posts nothing.

## Why this shape

Publication is manual until #6; the Publication lane only prepares, and the owner posts. AI is always shown (docs/publication.md), so the caption says it and the reminder comes with every AI voice.

## If you change this

- **Hits:** the Publication lane and the page's publication view; the credit text and the AI rule of `docs/publication.md`; `tests/test_publish.py`.
- **Does not hit:** the state: nothing is written to `state.json`.

## See

- [`prepare`](../../../../pipeline/video_factory/publish.py), [`write`](../../../../pipeline/video_factory/publish.py), [`caption`](../../../../pipeline/video_factory/publish.py), [`render_cover`](../../../../pipeline/video_factory/publish.py)
