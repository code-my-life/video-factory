---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/compose.py
hits:
  - templates/hyperframes/
  - pipeline/video_factory/steps.py
  - pipeline/video_factory/qc.py
  - tests/test_compose.py
---

# compose

`compose`: the plan (shots in output frames, captions and their groups, punch-ins, face-camera share; a capture not registered stops here, named), the camera track cut from the working copy of `ingest`, as delivered, the HyperFrames project (one root, one scene per shot, one captions track, the pinned libraries it loads copied from the lock), the guard against any URL outside the project, `hyperframes check --json` in the pinned image (an error stops compose), the `docker run --network none` render commands of both passes, the frame-count check, and the text boxes read from the text pass.

## Why this shape

Everything is planned in Python and handed to each scene as data, so a scene only builds a paused timeline from it. The text pass (white text on black) measures where text really lands on every frame, which `qc` holds to the safe zone; the render runs offline in the pinned image as the current user.

## If you change this

- **Hits:** the [project templates](../templates/hyperframes-templates.md) and [registry items](../templates/registry-items.md); [qc](qc.md), which reads the plan and the text boxes; [master](master.md), which encodes the frames; the [render image](../toolchain/render-image.md); `tests/test_compose.py`.
- **Does not hit:** the decision list ([cut](cut.md)) or the script ([script](script.md)) it reads.

## See

- [`plan`](../../../../pipeline/video_factory/compose.py), [`write_project`](../../../../pipeline/video_factory/compose.py), [`camera_track`](../../../../pipeline/video_factory/compose.py), [`ship_libraries`](../../../../pipeline/video_factory/compose.py), [`check_project`](../../../../pipeline/video_factory/compose.py), [`render_command`](../../../../pipeline/video_factory/compose.py), [`text_runs`](../../../../pipeline/video_factory/compose.py)
