---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/qc.py
hits:
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/cli.py
  - tests/test_qc.py
---

# qc

`qc`: measures (ffprobe, EBU R 128, compose's text boxes and plan) then pure rules: duration within the script schema's bounds (61 to 65 s), -14 LUFS within 1 LU, true peak at -1 dBTP or below, H.264 High at each platform size, 30 fps constant, BT.709, AAC 48 kHz, text in the strictest safe zone, face camera at half the duration at most; each failure names its bound.

## Why this shape

Facts and rules are apart, so each rule is tested on facts alone and the measures once on real files. The duration bounds are read from `schemas/script.schema.json`, the one place they are written.

## If you change this

- **Hits:** `vf run`'s exit code (1 when refused); the report in the store and the summary in `state.json`; `tests/test_qc.py`.
- **Does not hit:** the master itself: qc only reads it.

## See

- [`judge`](../../../../pipeline/video_factory/qc.py), [`check_text`](../../../../pipeline/video_factory/qc.py), [`stream_facts`](../../../../pipeline/video_factory/qc.py)
