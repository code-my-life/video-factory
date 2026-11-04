---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/blur.py
hits:
  - pipeline/video_factory/steps.py
  - tests/test_blur.py
---

# blur

`blur`: MediaPipe Selfie Segmenter on LiteRT writes the person's mask (256x256, FFV1); FFmpeg blurs each frame (Gaussian, sigma 18) and lays the original back on top through the mask; the result is lossless. `measure` gives the share of the variance of the Laplacian each region lost (criterion C6).

## Why this shape

Heavy pixel work stays in FFmpeg; Python only runs the small model. The output is lossless (x264 QP 0) so the person loses nothing to a second encoding, and the measure reads the raw luma planes, never a colour conversion that depends on the files' tags.

## If you change this

- **Hits:** [compose](compose.md), which cuts the blurred video into the camera track; the C6 measure recorded in `state.json`; `tests/test_blur.py`.
- **Does not hit:** the working copy ([ingest](ingest.md)).

## See

- [`Segmenter`](../../../../pipeline/video_factory/blur.py), [`write_masks`](../../../../pipeline/video_factory/blur.py), [`composite_command`](../../../../pipeline/video_factory/blur.py), [`measure`](../../../../pipeline/video_factory/blur.py)
