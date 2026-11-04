---
type: process
paths:
  - pipeline/video_factory/chain.py
  - pipeline/video_factory/steps.py
hits:
  - pipeline/video_factory/state.py
  - schemas/state.schema.json
consumes:
  - ../objects/pipeline/chain.md
  - ../objects/pipeline/steps.md
  - ../objects/pipeline/store.md
produces:
  - the master, the TikTok export and their framemd5 in VF_MEDIA, and the record of each step in state.json
---

# run the chain

`vf run <id>` takes a video from its working copy to a checked master, redoing only what changed.

## Input, movement, output

The state, the script, the takes, the captures and the pinned tools come in; each step that never ran, is stale, or is asked for runs in a scratch folder of the store, its outputs are stored by fingerprint and its record written into `state.json` at once; `qc` closes the run and its verdict is the exit code.

## Why this shape

Recording inputs, parameters, tools and code per step lets `vf status` explain staleness and `vf run` stop a cascade as soon as an output comes out unchanged; writing the state after each step means an interrupted run resumes where it stopped.

## Steps

1. [`run`](../../../pipeline/video_factory/chain.py) walks [`STEPS`](../../../pipeline/video_factory/chain.py) in order.
2. [`reasons`](../../../pipeline/video_factory/chain.py) compares each step's recorded fingerprints with [`steps`](../../../pipeline/video_factory/steps.py)' current ones.
3. [`run_step`](../../../pipeline/video_factory/chain.py) runs a step, stores its outputs and saves the state.
4. [`judge`](../../../pipeline/video_factory/qc.py) gives the verdict `vf run` exits with.

## If you change this

- **Hits:** every `state.json` in `video-content`, the media store.
- **Does not hit:** the takes as shot, never modified.
