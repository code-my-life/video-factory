---
type: object
cluster: templates
universe: live
paths:
  - templates/composition/
hits:
  - pipeline/video_factory/compose.py
  - tests/test_compose.py
---

# composition template

`templates/composition/`: the provisional HyperFrames page of `compose` (`index.html` for the video pass, `texte.html` for the text pass), the frame-driven script `vf-frames.js` (no GSAP: each frame drawn from its number on `hf-seek`), and the one font, Inter Bold, with its OFL licence.

## Why this shape

Neutral on purpose (white text, black shots, one word captions, legibility and safe zones only) until the video design system decides the look after validated mockups; every visible state is a function of the frame number.

## If you change this

- **Hits:** the code fingerprint of `compose` (every video's compose becomes stale); the look of every video; `tests/test_compose.py`.
- **Does not hit:** the plan, computed in [compose](../pipeline/compose.md).

## See

- The page: [`index.html`](../../../../templates/composition/index.html), the script: [`vf-frames.js`](../../../../templates/composition/vf-frames.js)
