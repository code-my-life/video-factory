---
type: process
paths:
  - pipeline/video_factory/studio/page.py
  - templates/studio/upload.js
  - templates/studio/sha256.js
hits:
  - pipeline/video_factory/studio/lanes.py
consumes:
  - ../objects/studio/page.md
  - ../objects/pipeline/ingest.md
produces:
  - the takes in VF_MEDIA, their references in state.json, the card in Montage
---

# send a take from the phone

The owner picks the takes in Safari on the tailnet page; they reach the store with the fingerprint the phone computed.

## Input, movement, output

Each file is hashed on the phone by slices, then sent by `PUT /v/<id>/prises/<n>` with its fingerprint; the server hashes it while writing it to the store's scratch folder and refuses a mismatch. `POST /v/<id>/prises` then runs `vf ingest <id> <files>`, removes the received copies, and moves the card from Tournage to Montage.

## Why this shape

A fingerprint computed on both ends proves that what is stored is what the phone sent, before any step uses it.

## Steps

1. [`upload.js`](../../../templates/studio/upload.js) hashes and sends each take.
2. [`receive`](../../../pipeline/video_factory/studio/page.py) writes and hashes it.
3. [`Studio.takes_received`](../../../pipeline/video_factory/studio/lanes.py) runs `vf ingest` and moves the card.

## If you change this

- **Hits:** the takes of the video, `state.json`.
- **Does not hit:** the captures, still sent by `vf ingest --capture`.
