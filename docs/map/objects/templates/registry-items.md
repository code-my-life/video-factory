---
type: object
cluster: templates
universe: live
paths:
  - templates/hyperframes/blocks/
  - templates/hyperframes/components/
  - templates/hyperframes/hyperframes.json
  - templates/hyperframes/hyperframes.lock.json
hits:
  - pipeline/video_factory/compose.py
  - tests/test_compose.py
  - CREDITS.md
---

# registry items

Blocks and components of the HyperFrames registry, installed as source by `hyperframes add` (development time only) from the registry pinned at the v0.9.12 tag in `hyperframes.json`, then restyled: `blocks/mk-specs-list.html` (the « etapes » shots), `blocks/mk-progress-stat.html` (the « stat » shots), `components/caption-highlight.html` (the captions track). `hyperframes.lock.json`, written by `add`, keeps the fingerprint of each file as installed.

## Why this shape

Starting from a reviewed registry item beats hand-building the effect. Each file was committed exactly as installed, then adapted in a second commit (no CDN script or online font, ids prefixed with `{{ID}}`, data from `{{CONFIG}}`, sized to 1440x2560, sober provisional look), so git keeps the upstream source to diff against on an upgrade.

## If you change this

- **Hits:** the code fingerprint of `compose`; the look of the shots and captions; `tests/test_compose.py`; the credits (Apache 2.0, HeyGen) in `CREDITS.md`.
- **Does not hit:** the HyperFrames CLI or render image, pinned in the [tools lock](../toolchain/tools-lock.md).

## See

- [`hyperframes.json`](../../../../templates/hyperframes/hyperframes.json), [`blocks/`](../../../../templates/hyperframes/blocks/), [`components/`](../../../../templates/hyperframes/components/)
