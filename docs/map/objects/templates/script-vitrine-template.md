---
type: object
cluster: templates
universe: live
paths:
  - templates/script-vitrine.md
hits:
  - pipeline/video_factory/videos.py
  - pipeline/video_factory/paths.py
  - tests/test_vitrine.py
---

# showcase script template

`templates/script-vitrine.md`: the script `vf new <id> --vitrine` copies, its front matter with the video id filled in (`duree_visee: 62`, `genre: vitrine`, `theme: primer`) and an HTML comment that recalls the annotations of a showcase (`[plan: …]`, `[jumeaux: …]`, `[suite: …]`, `[fin: …]`, `[appel: …]`, `[ton: …]`) and the settings of the header, each a choice of the video, open to change.

## Why this shape

A new showcase starts valid against the [script schema](../contracts/script-schema.md), its body empty until the lines are written; [vitrine](../pipeline/vitrine.md) reads it. The theme is filled with the current choice (Primer, the look of factory-live) so the field is never forgotten.

## If you change this

- **Hits:** every showcase created afterwards (not the existing ones); `tests/test_vitrine.py`, which creates one with `vf new --vitrine`.
- **Does not hit:** the face camera [script template](script-template.md).

## See

- Path: [`SCRIPT_VITRINE_TEMPLATE`](../../../../pipeline/video_factory/paths.py); the template: [`script-vitrine.md`](../../../../templates/script-vitrine.md)
