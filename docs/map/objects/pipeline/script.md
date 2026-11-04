---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/script.py
hits:
  - pipeline/video_factory/align.py
  - pipeline/video_factory/compose.py
  - templates/script.md
  - tests/test_script.py
---

# script

Parses the body of `script.md`: one sentence per line, each word in its written form (shown in captions) and its normalized form (compared with the transcript), the full-frame shots (`stat`, `etapes`, `code`, `capture`) with their anchor word and their `|`-separated parts, and the punch-ins (`zoom`).

## Why this shape

A shot noted at the end of a line covers its whole sentence, because that is how the first real script annotates; inside a line it starts on the word before it, as the template says. Errors name the line of the file, comments included, so the author finds them.

## If you change this

- **Hits:** [align](align.md) and [compose](compose.md), which read words, shots and zooms; every `script.md` in `video-content`; the annotations documented in `templates/script.md` and the RUNBOOK; `tests/test_script.py`.
- **Does not hit:** the front matter, read by [frontmatter](frontmatter.md) and checked by the [script schema](../contracts/script-schema.md).

## See

- [`parse`](../../../../pipeline/video_factory/script.py), [`normalize`](../../../../pipeline/video_factory/script.py), [`Shot`](../../../../pipeline/video_factory/script.py)
