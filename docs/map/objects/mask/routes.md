---
type: object
cluster: mask
universe: live
paths:
  - mask/routes.json
hits:
  - pipeline/video_factory/ingest.py
  - tests/test_ingest.py
---

# routes file

`mask/routes.json`: the shooting routes. `quicklook-screen` is the iPhone screen recording of AR Quick Look (1206x2622, mirrored), cropped to a centred 9:16 zone of 1206x2144, marked provisional until checked against Quick Look's buttons on a real take (#3).

## Why this shape

The route is data, so a new way of filming or a corrected crop needs no code; its fingerprint is an input of `ingest`. The rest of `mask/` (the helmet) comes with #3.

## If you change this

- **Hits:** every video's `ingest` (stale when the route changes); `tests/test_ingest.py`.
- **Does not hit:** the colour handling, read from each take.

## See

- Read by [`load`](../../../../pipeline/video_factory/routes.py); the data: [`routes.json`](../../../../mask/routes.json)
