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

`templates/script.md`: the script `vf new` copies, its front matter with the video id filled in (and `duree_visee: 63`) and an HTML comment that recalls the annotations (`[stat: …]`, `[etapes: …]`, `[code: …]`, `[zoom]`); `[capture: <name>]` and the `|` separator are documented in the RUNBOOK and parsed by [script](../pipeline/script.md).

## Why this shape

The template is the only place a new script comes from, so every script starts valid: `vf new` refuses to write one that breaks the [script schema](../contracts/script-schema.md). The id is quoted so an id that starts with a digit stays a string.

## If you change this

- **Hits:** every video created afterwards (not the existing ones); `tests/test_new.py`, which checks the fields `vf new` writes.
- **Does not hit:** the HyperFrames [project templates](hyperframes-templates.md) of `compose`.

## See

- Filled by [`script_text`](../../../../pipeline/video_factory/videos.py); the template: [`script.md`](../../../../templates/script.md)
