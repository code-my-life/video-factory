---
type: object
cluster: contracts
universe: live
paths:
  - schemas/routes.schema.json
hits:
  - mask/routes.json
  - pipeline/video_factory/routes.py
---

# routes schema

`schemas/routes.schema.json`, version 1: the shape of `mask/routes.json`: a default route, and per route its source size, its 9:16 crop (even offsets and sizes), the mirror, and what remains provisional.

## Why this shape

Even numbers keep crops on the chroma grid of 4:2:0 video; rules a schema cannot say live in [routes](../pipeline/routes.md).

## If you change this

- **Hits:** the [routes file](../mask/routes.md); [routes](../pipeline/routes.md).
- **Does not hit:** the state or script schemas.

## See

- The schema: [`routes.schema.json`](../../../../schemas/routes.schema.json)
