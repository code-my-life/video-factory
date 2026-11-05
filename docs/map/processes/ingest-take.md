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
produces:
  - the takes and captures in VF_MEDIA, their references in state.json, and the working copy
---

# ingest a take or a capture

`vf ingest <id> <takes>`, `vf ingest <id> --voix <file>` (the voice of a showcase) and `vf ingest <id> --capture <name> <file>` bring outside files into a video, from the command line or from the studio page (a showcase's audio file as its voice, each other file as the capture of its name).

## Input, movement, output

Takes are copied into the store as delivered (clean and framed in 9:16), under their fingerprint, become the video's takes in `state.json`, and the `ingest` step makes the working copy; a showcase's voice is stored the same way and its working copy is the voice alone; a capture (a plan of `vf capture`, or a rush without sound) is cleaned first, then stored and recorded under its name.

## Why this shape

The take as shot stays available to redo the working copy whenever the code changes; a capture is only ever stored clean, so its metadata never reaches a video.

## Steps

1. [`register_takes`](../../../pipeline/video_factory/chain.py) stores the takes, or [`register_voice`](../../../pipeline/video_factory/chain.py) the voice of a showcase.
2. [`run_step`](../../../pipeline/video_factory/chain.py) runs `ingest` ([`make_working_copy`](../../../pipeline/video_factory/ingest.py), or [`make_voice_copy`](../../../pipeline/video_factory/ingest.py) for a showcase).
3. [`register_capture`](../../../pipeline/video_factory/chain.py) cleans ([`clean`](../../../pipeline/video_factory/captures.py)) and records a capture.

## If you change this

- **Hits:** `state.json` (takes, voice, captures) and the store.
- **Does not hit:** the original files, which stay where they are.
