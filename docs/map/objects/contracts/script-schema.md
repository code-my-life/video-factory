---
type: object
cluster: contracts
universe: live
paths:
  - schemas/script.schema.json
hits:
  - templates/script.md
  - templates/script-vitrine.md
  - pipeline/video_factory/videos.py
  - tests/test_schemas.py
---

# script schema

`schemas/script.schema.json`: the front matter of `script.md`: `id`, `titre`, `plateforme` (tiktok) and `duree_visee`, a whole number of seconds from 61 to 65 (the owner's decision of 2026-11-04). These two bounds are the only place the duration of a video is written: `qc` reads them for the master. A showcase adds `genre: vitrine` (`face-camera` otherwise) and must name its `theme`; `bandeau`, `vignette`, `vignette_image` (a second of the video, with a decimal comma or point), `icone` and `ecran_fin` are optional. Any script may give `legende`, `mots_cles` and `voix_ia` for its caption ([publish](../pipeline/publish.md)). Their meaning is read by [vitrine](../pipeline/vitrine.md).

## Why this shape

TikTok Creator Rewards only pays videos of a minute or more, and every video aims just over that: the bounds live in the contract so a script out of range is refused before any shooting, and the master is held to the same pair. The id rule is copied from the state schema (a test keeps both equal) so each published schema stands alone.

## If you change this

- **Hits:** the [script template](../templates/script-template.md) and the [showcase template](../templates/script-vitrine-template.md), which must still validate; every `script.md` in `video-content`; [videos](../pipeline/videos.md); [qc](../pipeline/qc.md), which reads the duration bounds; `tests/test_schemas.py` and `tests/test_qc.py`.
- **Does not hit:** the body of the script, which this schema does not describe.

## See

- Checked by [`script_problems`](../../../../pipeline/video_factory/videos.py); the schema: [`script.schema.json`](../../../../schemas/script.schema.json)
