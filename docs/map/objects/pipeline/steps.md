---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/steps.py
hits:
  - pipeline/video_factory/chain.py
  - tests/test_state.py
---

# steps

The eight steps as inputs (name to fingerprint), parameters and run, each run working in a store scratch folder and returning its files and a summary; plus the cleaning of captures. A showcase (`genre: vitrine`) takes its own branch ([montage](montage.md)): `ingest` reads its voice, not takes; `transcribe` and `align` are those of every video; `cut` writes its decision list, `voice` places its voice line by line, `compose` writes and renders its project in its theme, with a silent track for music; `master` and `qc` are those of every video. `check_and_render` (check, then the frames and the text pass) serves both genres.

## Why this shape

Inputs and parameters are functions of the video, so status can recompute them and compare with what each step recorded.

## If you change this

- **Hits:** [chain](chain.md), which registers them; the studio API, which reads `plan.words` and `edl.words` of every genre; every `state.json` (a new input or parameter makes the step stale); `tests/test_state.py`.
- **Does not hit:** the media work, which lives in each step's module.

## See

- [`compose_run`](../../../../pipeline/video_factory/steps.py), [`compose_inputs`](../../../../pipeline/video_factory/steps.py), [`qc_run`](../../../../pipeline/video_factory/steps.py), [`Result`](../../../../pipeline/video_factory/steps.py)
