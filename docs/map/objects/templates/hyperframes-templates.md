---
type: object
cluster: templates
universe: live
paths:
  - templates/hyperframes/index.html
  - templates/hyperframes/texte.html
  - templates/hyperframes/scenes/
  - templates/hyperframes/assets/
hits:
  - pipeline/video_factory/compose.py
  - pipeline/video_factory/chain.py
  - tests/test_compose.py
  - .claude/skills/video-factory/SKILL.md
---

# HyperFrames project templates

`templates/hyperframes/`: what `compose` fills to write a real HyperFrames project. `index.html` is the one root (1440x2560, 30 fps; the take in `#camera-wrap`, scaled by the `main` timeline for punch-ins; GSAP from `assets/lib/gsap/`); `texte.html` is the root of the text pass (text only, white on black, kept outside the project and mounted over `index.html`); `scenes/code.html` and `scenes/capture.html` are the hand-written shot scenes; `assets/fonts/` holds the one font, Inter Bold, with its OFL licence. The registry items are on their own card ([registry items](registry-items.md)).

## Why this shape

One scene per shot, each a paused GSAP timeline registered under its id, so HyperFrames seeks every frame and `hyperframes check` can audit the project. Placeholders (`{{ID}}`, `{{DURATION}}`, `{{CONFIG}}`, `{{MEDIA}}`, `{{HOSTS}}`, `{{CAMERA}}`, `{{ZOOMS}}`) carry the plan computed in Python; a placeholder left unfilled stops compose. The look is neutral on purpose (white on black, one font) until the video design system.

## If you change this

- **Hits:** the code fingerprint of `compose` (every file under `templates/hyperframes/` counts, so every video's compose becomes stale); the look of every video; the check run before each render; `tests/test_compose.py`; the [video-factory skill](../skills/skills.md).
- **Does not hit:** the plan, computed in [compose](../pipeline/compose.md); `master` and `qc`.

## See

- [`index.html`](../../../../templates/hyperframes/index.html), [`texte.html`](../../../../templates/hyperframes/texte.html), [`scenes/`](../../../../templates/hyperframes/scenes/)
