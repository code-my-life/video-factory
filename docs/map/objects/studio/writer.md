---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/writer.py
hits:
  - pipeline/video_factory/script.py
  - schemas/script.schema.json
  - tests/test_board.py
---

# writer

The Script station: the prompt for `studio-writer` (the idea, `idees.md`, the brand positioning, the template, and on a redo the current script and the owner's request), one `hermes -p studio-writer chat --oneshot` call, and the rules a draft must pass before it replaces `script.md`.

## Why this shape

The model only writes text; code accepts it: the script schema and id, the same parser as `align` and `compose`, 140 to 190 spoken words for 61 to 65 s, no em dash. A refused draft leaves `script.md` as it was and parks the card with the reason.

## If you change this

- **Hits:** the profile's instructions (`hermes/profiles/studio-writer/SOUL.md`); the script parser and schema it reuses.
- **Does not hit:** the chain; no other station calls a model.

## See

- [`prompt`](../../../../pipeline/video_factory/studio/writer.py), [`problems`](../../../../pipeline/video_factory/studio/writer.py), [`draft`](../../../../pipeline/video_factory/studio/writer.py)
