---
type: object
cluster: templates
universe: live
paths:
  - templates/hyperframes/phone/
hits:
  - pipeline/video_factory/capture/scene.py
  - tests/test_capture.py
---

# phone scene

`templates/hyperframes/phone/`: the HyperFrames scene `vf capture` writes for a plan shot on the iPhone with a `phone` block (#22). `index.html` is its one root (1440x2560, 30 fps): the x3 capture as the screen of a generic phone in CSS 3D (a body, an edge made of slices, a punch-hole camera), its poses eased one to the next by GSAP, a finger on each tap, and a notification with the app's icon that drops at the top of the screen and goes back up on the first tap after it. The font is copied from [camera follow](camera-follow.md).

## Why this shape

The SPEC of video 1 shows the phone in 3D; a 3D model would cost a library and a model to license, while a few CSS layers turn and tilt well enough at these angles. The shape is generic on purpose: no real phone's outline or brand. Like camera follow, the folder is left out of compose's code fingerprint ([chain](../pipeline/chain.md), `CAPTURE_SCENES`).

## If you change this

- **Hits:** [capture](../pipeline/capture.md) (`scene.write_phone` fills `{{DURATION}}`, `{{LAYERS}}`, `{{NOTE}}`, `{{CONFIG}}`), `tests/test_capture.py`.
- **Does not hit:** compose and its projects, the camera follow scene.

## See

- [`index.html`](../../../../templates/hyperframes/phone/index.html), [`scene.write_phone`](../../../../pipeline/video_factory/capture/scene.py)
