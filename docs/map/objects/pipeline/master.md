---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/master.py
hits:
  - pipeline/video_factory/qc.py
  - tests/test_master.py
---

# master

`master`: the 1440x2560 master and the 1080x1920 TikTok export from the PNG frames, H.264 High in BT.709, 30 fps, AAC 48 kHz, bitexact, no metadata, x264 SEI removed, faststart; the voice at -3 dB per channel plus the music, cut to the exact frames; a framemd5 for each.

## Why this shape

Both files come from the frames, not one from the other. The -3 dB pan keeps the stereo master at the loudness the voice was normalized to (BS.1770 adds 3 LU for two equal channels). framemd5 hashes decoded frames, so two renders compare frame by frame (criterion C1).

## If you change this

- **Hits:** [qc](qc.md); the platforms' upload formats; `tests/test_master.py`.
- **Does not hit:** the frames ([compose](compose.md)) or the voice ([voice](voice.md)).

## See

- [`command`](../../../../pipeline/video_factory/master.py), [`video_filter`](../../../../pipeline/video_factory/master.py), [`audio_graph`](../../../../pipeline/video_factory/master.py), [`framemd5_command`](../../../../pipeline/video_factory/master.py)
