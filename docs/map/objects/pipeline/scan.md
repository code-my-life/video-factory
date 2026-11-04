---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/scan.py
hits:
  - pipeline/video_factory/cut.py
  - tests/test_faces.py
---

# scan

`scan`: every frame of the working copy through the [face detector](faces.md); the report lists the frames with a face (number, time, score) and the ranges to remove, widened by `MARGIN` frames.

## Why this shape

The report never holds an image, only numbers. Widening the ranges covers the first and last frames of a slipping mask that the detector may miss.

## If you change this

- **Hits:** [cut](cut.md), which removes the ranges or refuses a range inside a kept word; `tests/test_faces.py`.
- **Does not hit:** the detector itself ([faces](faces.md)).

## See

- [`frame_scores`](../../../../pipeline/video_factory/scan.py), [`report`](../../../../pipeline/video_factory/scan.py), [`ranges`](../../../../pipeline/video_factory/scan.py)
