---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/transcribe.py
hits:
  - pipeline/video_factory/align.py
  - tests/test_transcribe.py
---

# transcribe

`transcribe`: whisper-cli at its pinned version and model, `-l fr`, temperature 0, no fallback, beam 5, 8 threads, DTW `large.v3.turbo`, flash attention off, a fixed prompt full of hesitations; words built from tokens, ending at their DTW time and held in their stretch of speech between FFmpeg's silences.

## Why this shape

Every setting that changes the result is written out and recorded. Whisper drops hesitations unless prompted with them, and DTW marks token ends more accurately than the segment offsets; the pauses come from the sound itself.

## If you change this

- **Hits:** [align](align.md) and [cut](cut.md), which depend on the word times; `tests/test_transcribe.py` (with a recorded whisper output: whisper.cpp does not run in CI).
- **Does not hit:** the audio of the take ([ingest](ingest.md)).

## See

- [`whisper_command`](../../../../pipeline/video_factory/transcribe.py), [`tokens_to_words`](../../../../pipeline/video_factory/transcribe.py), [`place`](../../../../pipeline/video_factory/transcribe.py), [`silences`](../../../../pipeline/video_factory/transcribe.py)
