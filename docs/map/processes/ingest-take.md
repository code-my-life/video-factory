---
type: process
paths:
  - pipeline/video_factory/cli.py
  - pipeline/video_factory/captures.py
hits:
  - pipeline/video_factory/chain.py
consumes:
  - ../objects/pipeline/ingest.md
  - ../objects/pipeline/captures.md
  - ../objects/mask/routes.md
produces:
  - the takes and captures in VF_MEDIA, their references in state.json, and the working copy
---

# ingest a take or a capture

`vf ingest <id> <takes>` and `vf ingest <id> --capture <name> <file>` bring outside files into a video.

## Input, movement, output

Takes are copied into the store as shot, under their fingerprint, become the video's takes in `state.json`, and the `ingest` step makes the working copy; a capture is cleaned first, then stored and recorded under its name.

## Why this shape

The take as shot stays available to redo the working copy whenever the route or the code changes; a capture is only ever stored clean, so its metadata never reaches a video.

## Steps

1. [`register_takes`](../../../pipeline/video_factory/chain.py) stores the takes and records the route.
2. [`run_step`](../../../pipeline/video_factory/chain.py) runs `ingest` ([`make_working_copy`](../../../pipeline/video_factory/ingest.py)).
3. [`register_capture`](../../../pipeline/video_factory/chain.py) cleans ([`clean`](../../../pipeline/video_factory/captures.py)) and records a capture.

## If you change this

- **Hits:** `state.json` (takes, route, captures) and the store.
- **Does not hit:** the original files, which stay where they are.
