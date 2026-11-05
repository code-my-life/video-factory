---
type: object
cluster: templates
universe: live
paths:
  - templates/hyperframes/camera-follow/
hits:
  - pipeline/video_factory/capture/scene.py
  - tests/test_capture.py
  - .claude/skills/video-factory/SKILL.md
---

# camera follow scene

`templates/hyperframes/camera-follow/`: the HyperFrames scene `vf capture` writes for a plan with a camera (#19). `index.html` is its one root (1440x2560, 30 fps): the capture clip in `COPIES` camera layers, each moved by one linear tween per frame along the path vf computed, clipped to the stage over the stage's own ground; the trailing copies (the motion blur by accumulation) show only during the moves; the plan's titles in the subtitle band; the cursor of each click, one state per frame computed by vf on the camera's pose (#22). `assets/fonts/` holds Mona Sans (latin subset of the variable font, OFL) and its licence.

## Why this shape

HyperFrames 0.9.12's `data-motion-blur` leaves out a layer that moves over the whole frame, so the blur is made of copies; hiding them during the holds keeps their cost to the moves. The folder is apart from compose's templates and left out of compose's code fingerprint ([chain](../pipeline/chain.md), `CAPTURE_SCENES`): changing it never makes a video's compose stale.

## If you change this

- **Hits:** [capture](../pipeline/capture.md) (`scene.write_project` fills `{{DURATION}}`, `{{LAYERS}}`, `{{LABELS}}`, `{{CONFIG}}`), the measured render cost in the RUNBOOK, `tests/test_capture.py`.
- **Does not hit:** compose and its projects.

## See

- [`index.html`](../../../../templates/hyperframes/camera-follow/index.html), [`scene.config`](../../../../pipeline/video_factory/capture/scene.py)
