---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/captures.py
hits:
  - pipeline/video_factory/chain.py
  - tests/test_captures.py
---

# captures

Cleans a capture before it is stored: a still becomes an RGB PNG without metadata or colour profile, a clip loses its sound and metadata and becomes H.264 at 30 fps in BT.709.

## Why this shape

What enters the store is never the file as given, so a screenshot's text chunks or a phone clip's metadata cannot reach a video.

## If you change this

- **Hits:** [chain](chain.md) (`register_capture`) and [compose](compose.md), which places the captures; `tests/test_captures.py`.
- **Does not hit:** the shots that call them ([script](script.md)).

## See

- [`clean`](../../../../pipeline/video_factory/captures.py), [`clean_command`](../../../../pipeline/video_factory/captures.py), [`kind_of`](../../../../pipeline/video_factory/captures.py)
