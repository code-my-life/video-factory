---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/faces.py
hits:
  - pipeline/video_factory/scan.py
  - pipeline/video_factory/qc.py
  - tests/test_faces.py
---

# faces

The face detector of `scan` and `qc`: MediaPipe BlazeFace short range (the pinned model) on LiteRT, MediaPipe's anchors, decoding and sigmoid, black letterbox and bilinear sampling as MediaPipe does them; a 144x256 frame is looked at through three windows and scored by the best. `THRESHOLD` (0.5) is the one provisional threshold.

## Why this shape

The mediapipe wheel needs OpenGL ES even on CPU, so the model runs on LiteRT directly with MediaPipe's pre- and post-processing rewritten; on MediaPipe's test images the scores match mediapipe 1.1.1 within 0.01. One CPU thread keeps the arithmetic order, hence the scores, fixed. Nothing of an image leaves this module.

## If you change this

- **Hits:** [scan](scan.md) and [qc](qc.md); the face threshold recorded by both steps (changing it makes both stale); its calibration in #3; `tests/test_faces.py` and `tests/test_qc.py`.
- **Does not hit:** the segmentation of [blur](blur.md), which uses another model.

## See

- [`Detector`](../../../../pipeline/video_factory/faces.py), [`anchors`](../../../../pipeline/video_factory/faces.py), [`windows`](../../../../pipeline/video_factory/faces.py), [`THRESHOLD`](../../../../pipeline/video_factory/faces.py)
