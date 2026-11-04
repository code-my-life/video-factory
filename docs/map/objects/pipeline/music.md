---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/music.py
hits:
  - pipeline/video_factory/compose.py
  - tests/test_music.py
---

# music

The music bed of `compose`: four chords played by a soft pad and a seeded arpeggio, sines and envelopes only, at a fixed low level, with a fade in and out, written as 16-bit stereo WAV.

## Why this shape

No third-party audio and no randomness without a seed: the same duration gives the same bed on every render. Generated music (#10) can replace it later.

## If you change this

- **Hits:** [compose](compose.md), which writes it, and [master](master.md), which mixes it; `tests/test_music.py`.
- **Does not hit:** the voice ([voice](voice.md)).

## See

- [`bed`](../../../../pipeline/video_factory/music.py), [`write`](../../../../pipeline/video_factory/music.py)
