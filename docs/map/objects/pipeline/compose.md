---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/compose.py
hits:
  - templates/composition/
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/qc.py
  - tests/test_compose.py
---

# compose

`compose`: the plan (shots in output frames, captions, punch-ins, face-camera share; a capture not registered stops here, named), the camera track cut from the blurred video, the HyperFrames project of two passes, the `docker run --network none` command of the pinned render image, the frame-count check, and the text boxes read from the text pass.

## Why this shape

Everything is planned in Python and handed to the page as data, so the page only draws frame numbers. The text pass (white text on black) measures where text really lands on every frame, which `qc` holds to the safe zone; the render runs offline in the pinned image as the current user.

## If you change this

- **Hits:** the [composition template](../templates/composition-template.md); [qc](qc.md), which reads the plan and the text boxes; [master](master.md), which encodes the frames; the [render image](../toolchain/render-image.md); `tests/test_compose.py`.
- **Does not hit:** the decision list ([cut](cut.md)) or the script ([script](script.md)) it reads.

## See

- [`plan`](../../../../pipeline/video_factory/compose.py), [`write_project`](../../../../pipeline/video_factory/compose.py), [`camera_track`](../../../../pipeline/video_factory/compose.py), [`render_command`](../../../../pipeline/video_factory/compose.py), [`text_runs`](../../../../pipeline/video_factory/compose.py)
