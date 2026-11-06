---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/page.py
  - pipeline/video_factory/studio/api.py
  - hermes/workflow.json
  - templates/studio/page.css
  - templates/studio/sha256.js
  - templates/studio/upload.js
hits:
  - tests/test_upload.py
  - tests/test_api.py
---

# page

The studio page on 127.0.0.1:8448, published on the tailnet by `tailscale serve`: the cards, the draft to approve, the takes to send, the master to review (with byte ranges, for Safari), the files and caption to post, and the owner's gestures as unblocks. A take is streamed into the store's scratch folder under its rank and the name it was sent with (a showcase stores each rush as the capture of that name; its form also takes the audio of the voice) while hashed, and refused unless it matches the SHA-256 the phone computed by slices (`sha256.js`).

It also serves the generic workflow API (`api.py`, ADR 0006) that factory-live reads: the sheet (`hermes/workflow.json`, in factory-live's `WorkflowSheet` format), the items and their state, an item's steps and typed files, the master's words in output time, and the owner's gesture.

## Why this shape

Telegram bots cannot fetch files over 20 MB and a take weighs hundreds; a page on the tailnet takes any size, never reaches the Internet, and lets the phone prove the fingerprint of what it sent.

## If you change this

- **Hits:** the owner's gestures; factory-live's view of the studio (the API's version is `api.API_VERSION`); `tests/test_upload.py`, `tests/test_api.py`.
- **Does not hit:** the chain: the page calls `vf ingest` through the lanes.

## See

- [`handler_for`](../../../../pipeline/video_factory/studio/page.py), [`receive`](../../../../pipeline/video_factory/studio/page.py), [`Pages`](../../../../pipeline/video_factory/studio/page.py)
