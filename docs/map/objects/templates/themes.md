---
type: object
cluster: templates
universe: live
paths:
  - templates/hyperframes/themes/
hits:
  - pipeline/video_factory/montage.py
  - pipeline/video_factory/publish.py
  - tests/test_vitrine.py
---

# showcase themes

`templates/hyperframes/themes/<theme>/`: the look of a showcase, chosen by the `theme` of its script. A theme holds `index.html` (the page of the project, which [montage](../pipeline/montage.md) fills with `{{DURATION}}`, `{{BODY}}` and `{{CONFIG}}`, and its GSAP timeline), `cover.html` (the cover, filled with `{{LINES}}` by [publish](../pipeline/publish.md)), `icons.json` (the icons an `[appel: …]` or the end card's badge may name, with their colour) and `fonts/`. `primer` is Primer's dark tokens and Mona Sans, as factory-live: the look of video 1, its banner and end card kept in the safe zone since 2026-11-06. Its icons are GitHub's Octicons, under their MIT licence (`OCTICONS-LICENSE.txt`).

## Why this shape

A theme is a choice of the video, open to change: another look is another folder, never a change of the chain. Every file of a theme counts in the fingerprint of `compose`, so changing a theme redoes the montage of the videos that use it.

## If you change this

- **Hits:** every showcase that names the theme (its next `vf run` redoes compose and master) and its cover; the qc safe zone, which every text of the page must respect; `tests/test_vitrine.py` and `tests/test_publish.py`.
- **Does not hit:** the face camera project templates ([hyperframes templates](hyperframes-templates.md)).

## See

- The theme of video 1: [`primer/index.html`](../../../../templates/hyperframes/themes/primer/index.html), [`primer/cover.html`](../../../../templates/hyperframes/themes/primer/cover.html), [`primer/icons.json`](../../../../templates/hyperframes/themes/primer/icons.json)
