---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/media.py
hits:
  - pipeline/video_factory/ingest.py
  - pipeline/video_factory/master.py
  - pipeline/video_factory/steps.py
---

# media

FFmpeg and ffprobe as the steps use them: the bitexact and no-metadata flags, the fixed thread count, `BT709` tagging, probing and the technical summary of a take (never its tags), raw frame streams in and out of Python.

## Why this shape

Frames cross into Python as raw pixels through pipes, never as image files; every encoder shares one thread count because x264's output depends on it.

## If you change this

- **Hits:** every media step; changing a flag here changes the code fingerprint of most steps, which then become stale.
- **Does not hit:** the tools' locations ([tools](tools.md)).

## See

- [`frames`](../../../../pipeline/video_factory/media.py), [`RawWriter`](../../../../pipeline/video_factory/media.py), [`summary`](../../../../pipeline/video_factory/media.py), [`ffmpeg`](../../../../pipeline/video_factory/media.py)
