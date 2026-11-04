---
type: object
cluster: contracts
universe: live
paths:
  - schemas/script.schema.json
hits:
  - templates/script.md
  - pipeline/video_factory/videos.py
  - tests/test_schemas.py
---

# script schema

`schemas/script.schema.json`: the front matter of `script.md`: `id`, `titre`, `plateforme` (tiktok) and `duree_visee`, a whole number of seconds from 61 to 90.

## Why this shape

TikTok Creator Rewards only pays videos of a minute or more, and the chain aims at 90 seconds at most: the bound lives in the contract so a script out of range is refused before any shooting. The id rule is copied from the state schema (a test keeps both equal) so each published schema stands alone.

## If you change this

- **Hits:** the [script template](../templates/script-template.md), which must still validate; every `script.md` in `video-content`; [videos](../pipeline/videos.md); `tests/test_schemas.py`.
- **Does not hit:** the body of the script, which this schema does not describe.

## See

- Checked by [`script_problems`](../../../../pipeline/video_factory/videos.py); the schema: [`script.schema.json`](../../../../schemas/script.schema.json)
