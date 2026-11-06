---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/ingest.py
hits:
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/captures.py
  - tests/test_ingest.py
---

# ingest

`ingest`: the working copy of a video from its takes, each delivered clean and framed: a take that is not 9:16 is refused with its size, its frame is kept as is (no crop, no flip, no blur), 30 fps constant, BT.709 SDR (gamut conversion, fixed Hable tone map for HLG and PQ), 48 kHz mono 24-bit, takes joined end to end, no metadata at all. For a showcase, the working copy is its voice alone (`make_voice_copy`): any audio file (MP3, WAV) becomes 48 kHz mono 24-bit WAV, without tags; a file without sound is refused as a voice.

## Why this shape

Colour is read from each take (a screen recording and a camera take differ), geometry is the take's own: the takes come prepared, so ingest only normalises what the later steps need. Only the video and audio streams are mapped, metadata and chapters dropped, encoder names removed, so ffprobe finds neither place, nor device, nor date (criterion C5).

## If you change this

- **Hits:** every later step, which reads the working copy; [captures](captures.md), which reuses `colour_filter`; `tests/test_ingest.py`.
- **Does not hit:** the takes as delivered, stored untouched by [chain](chain.md).

## See

- [`make_working_copy`](../../../../pipeline/video_factory/ingest.py), [`colour_filter`](../../../../pipeline/video_factory/ingest.py), [`take_filters`](../../../../pipeline/video_factory/ingest.py), [`command`](../../../../pipeline/video_factory/ingest.py), [`make_voice_copy`](../../../../pipeline/video_factory/ingest.py)
