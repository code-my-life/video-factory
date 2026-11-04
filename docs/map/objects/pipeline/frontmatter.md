---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/frontmatter.py
hits:
  - templates/script.md
  - pipeline/video_factory/videos.py
  - tests/test_frontmatter.py
---

# frontmatter

Reads and writes the front matter of `script.md`: a strict subset of YAML (`key: value` lines, a quoted JSON string, a whole number, or a bare word that starts with a letter) without a YAML library.

## Why this shape

Standard library first, and the same text must read the same way here and in any YAML reader: a bare value YAML would turn into a boolean, a null, a float or a date is refused with its line number, and the writer quotes anything that is not a plain word.

## If you change this

- **Hits:** every `script.md` in `video-content`, which must still parse; the [script template](../templates/script-template.md); [videos](videos.md); `tests/test_frontmatter.py`.
- **Does not hit:** the body of the script (the spoken text and its annotations), which this module returns untouched.

## See

- [`split`](../../../../pipeline/video_factory/frontmatter.py), [`render`](../../../../pipeline/video_factory/frontmatter.py), [`parse_value`](../../../../pipeline/video_factory/frontmatter.py)
