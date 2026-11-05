---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/capture/
hits:
  - pipeline/video_factory/cli.py
  - schemas/capture-plan.schema.json
  - schemas/capture-source.schema.json
  - templates/hyperframes/camera-follow/
  - tests/test_capture.py
  - docs/RUNBOOK.md
  - .claude/skills/video-factory/SKILL.md
---

# capture

The `vf capture` package: an app's real demo, driven frame by frame on a fake clock, and the camera that follows one of its elements (#19, ADR 0005). `plan` reads and checks a capture plan and the app's pinned source (a refused plan names each field at fault); `demo` fetches the pinned commit alone into a work folder, applies the scenario variant with `git apply` and builds with the lock's Node.js, keyed by everything the build depends on; `shoot` runs `driver.mjs` with the pinned Node.js, Playwright and Chromium and fingerprints every frame and the track (`empreintes.json`); `camera` turns the track into a path (target, anchor, stage clamp, dead zone, fixed-length cubic moves, holds); `scene` writes the « camera follow » project, checks it, renders it in the pinned image without the network and measures it (`mesures.json`).

## Why this shape

The driver is the only part that runs in the browser, so it reads what the camera needs and nothing decides there: the path, the titles and the measures are pure Python, tested. The real time is kept out (clock installed and paused before the page loads, WAAPI removed so Motion uses requestAnimationFrame, CSS animations set from the fake clock), so two captures are meant to give the same bytes; a residual drift (a tenth of a CSS pixel on Motion animations, a few hundred pixels around spinners) remains on long plans, still to be found (#19). A move is a cubic ease of fixed duration from where the camera is, never a spring, so it cannot overshoot.

## If you change this

- **Hits:** [cli](cli.md) (`vf capture`), the [capture plan schema](../contracts/capture-plan-schema.md), the [camera follow scene](../templates/hyperframes-templates.md), the [factory-live source](../vitrine/factory-live.md) and its plans, `tests/test_capture.py`, the RUNBOOK and the [video-factory skill](../skills/skills.md).
- **Does not hit:** the chain and its eight steps; `compose` is only called for its check, render and encoding helpers.

## See

- [`driver.mjs`](../../../../pipeline/video_factory/capture/driver.mjs), [`camera.path`](../../../../pipeline/video_factory/capture/camera.py), [`scene.make`](../../../../pipeline/video_factory/capture/scene.py), [`demo.build`](../../../../pipeline/video_factory/capture/demo.py), [`plan.check`](../../../../pipeline/video_factory/capture/plan.py)
