---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/voice.py
hits:
  - pipeline/video_factory/master.py
  - tests/test_voice.py
---

# voice

`voice`: the decision list applied to the sound on the sample grid with 4 ms fades, a fixed chain (high-pass, denoiser, equaliser, compressor, then the « casque » colour `HELMET`), and loudness in two passes to -14 LUFS and -2 dBTP.

## Why this shape

The chain is fixed text, recorded as the step's parameters; -2 dBTP leaves room under qc's -1 dBTP for the music and the AAC encoder.

## If you change this

- **Hits:** [master](master.md), which mixes the voice; `tests/test_voice.py`.
- **Does not hit:** the music bed ([music](music.md)).

## See

- [`cut_graph`](../../../../pipeline/video_factory/voice.py), [`coloured_command`](../../../../pipeline/video_factory/voice.py), [`measure`](../../../../pipeline/video_factory/voice.py), [`normalize`](../../../../pipeline/video_factory/voice.py)
