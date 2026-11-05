---
type: process
paths:
  - pipeline/video_factory/cli.py
  - pipeline/video_factory/capture/
hits:
  - vitrine/
consumes:
  - ../objects/pipeline/capture.md
  - ../objects/vitrine/factory-live.md
  - ../objects/contracts/capture-plan-schema.md
produces:
  - VF_MEDIA/vitrine/<plan>/ (frames, track.json, empreintes.json; with a camera, scene/, check.json, mesures.json and <plan>.mp4)
---

# shoot a capture plan

`vf capture <plan.json> [--sortie DIR] [--travail DIR] [--sans-rendu]` films an app's real demo for a showcase video.

## Input, movement, output

A plan and the app's pinned source come in; the demo is built (or found) in the work folder, driven frame by frame on a fake clock, and its frames, track and fingerprints written; with a camera, the scene is written, checked, rendered offline and measured.

## Why this shape

The same plan gives the same frames and track, byte for byte, so a shot can be redone at any time; the rules of the showcase videos (move length, smallest text during the holds, empty bands) are measured on the result.

## Steps

1. [`plan.load`](../../../pipeline/video_factory/capture/plan.py) and [`plan.load_source`](../../../pipeline/video_factory/capture/plan.py) check the plan and the source.
2. [`demo.build`](../../../pipeline/video_factory/capture/demo.py) fetches the commit, applies the variant, installs and builds.
3. [`shoot.shoot`](../../../pipeline/video_factory/capture/shoot.py) runs [`driver.mjs`](../../../pipeline/video_factory/capture/driver.mjs) and fingerprints the frames and the track.
4. [`scene.make`](../../../pipeline/video_factory/capture/scene.py) computes the camera path, writes the project, checks, renders, encodes and measures it.
