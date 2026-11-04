---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/routes.py
hits:
  - mask/routes.json
  - schemas/routes.schema.json
  - tests/test_ingest.py
---

# routes

Reads `mask/routes.json` against its schema and the rules a schema cannot say (the default route exists, each crop lies inside its source and is 9:16), picks a route, and fingerprints it.

## Why this shape

A route's fingerprint is that of its canonical JSON, and it is an input of `ingest`: editing a crop makes `ingest` (and everything after it) stale.

## If you change this

- **Hits:** [ingest](ingest.md); the [routes file](../mask/routes.md) and its [schema](../contracts/routes-schema.md); `tests/test_ingest.py`.
- **Does not hit:** the colour handling, read from each take.

## See

- [`load`](../../../../pipeline/video_factory/routes.py), [`pick`](../../../../pipeline/video_factory/routes.py), [`fingerprint`](../../../../pipeline/video_factory/routes.py), [`rule_problems`](../../../../pipeline/video_factory/routes.py)
