---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/page.py
  - templates/studio/page.css
  - templates/studio/sha256.js
  - templates/studio/upload.js
hits:
  - tests/test_upload.py
---

# page

The studio page on 127.0.0.1:8448, published on the tailnet by `tailscale serve`: the cards, the draft to approve, the takes to send, the master to review (with byte ranges, for Safari), the files and caption to post, and the owner's gestures as unblocks. A take is streamed into the store's scratch folder while hashed, and refused unless it matches the SHA-256 the phone computed by slices (`sha256.js`).

## Why this shape

Telegram bots cannot fetch files over 20 MB and a take weighs hundreds; a page on the tailnet takes any size, never reaches the Internet, and lets the phone prove the fingerprint of what it sent.

## If you change this

- **Hits:** the owner's gestures; `tests/test_upload.py`.
- **Does not hit:** the chain: the page calls `vf ingest` through the lanes.

## See

- [`handler_for`](../../../../pipeline/video_factory/studio/page.py), [`receive`](../../../../pipeline/video_factory/studio/page.py), [`Pages`](../../../../pipeline/video_factory/studio/page.py)
