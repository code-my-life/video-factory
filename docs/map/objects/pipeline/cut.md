---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/cut.py
hits:
  - pipeline/video_factory/voice.py
  - pipeline/video_factory/compose.py
  - tests/test_cut.py
---

# cut

`cut`: the edit decision list on the 48 kHz sample grid: kept and off-script words from the first kept word to the last, pauses over 400 ms brought to 150 ms, fillers and retakes removed whole; each said word with its output time, the pieces of a word whisper heard apart cut like two words (a long pause between them shortened too) and then listed as one, so the captions show it once; `source_frames` maps each output frame to the source frame on screen.

## Why this shape

Cutting on the sample grid lets a pause be exactly 150 ms while the video follows at frame precision. The list is refused (a `CutError` naming word and frames) rather than ever cutting inside a kept word, and `problems` re-checks every list, so criterion C3 holds by construction.

## If you change this

- **Hits:** [voice](voice.md) and [compose](compose.md), which apply the list; the C3 guarantee; `tests/test_cut.py`.
- **Does not hit:** the alignment ([align](align.md)) it reads.

## See

- [`decide`](../../../../pipeline/video_factory/cut.py), [`pause_cuts`](../../../../pipeline/video_factory/cut.py), [`problems`](../../../../pipeline/video_factory/cut.py), [`source_frames`](../../../../pipeline/video_factory/cut.py)
