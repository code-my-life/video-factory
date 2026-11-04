---
type: object
cluster: templates
universe: live
paths:
  - templates/script.md
hits:
  - pipeline/video_factory/videos.py
  - tests/test_new.py
---

# script template

`templates/script.md`: the script `vf new` copies, its front matter with the video id filled in and an HTML comment that recalls the annotations (`[stat: …]`, `[etapes: …]`, `[code: …]`, `[zoom]`).

## Why this shape

The template is the only place a new script comes from, so every script starts valid: `vf new` refuses to write one that breaks the [script schema](../contracts/script-schema.md). The id is quoted so an id that starts with a digit stays a string.

## If you change this

- **Hits:** every video created afterwards (not the existing ones); `tests/test_new.py`, which checks the fields `vf new` writes.
- **Does not hit:** the HyperFrames composition templates, which come with the design system and will live elsewhere in `templates/`.

## See

- Filled by [`script_text`](../../../../pipeline/video_factory/videos.py); the template: [`script.md`](../../../../templates/script.md)
