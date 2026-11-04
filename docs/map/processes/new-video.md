---
type: process
paths:
  - pipeline/video_factory/videos.py
  - templates/script.md
hits:
  - schemas/state.schema.json
  - schemas/script.schema.json
consumes:
  - ../objects/templates/script-template.md
  - ../objects/contracts/script-schema.md
  - ../objects/contracts/state-schema.md
produces:
  - videos/<id>/script.md and videos/<id>/state.json in video-content
---

# new video

`vf new <id>` turns an id into a new video folder in the content clone.

## Input, movement, output

The id and the template come in; the script is filled, its front matter validated, its fingerprint put in a version 1 state validated in turn; both files appear in `VF_CONTENT/videos/<id>/` in one rename, or nothing does.

## Why this shape

Writing before validating would leave a half-made video for the next step to trip on; renaming a staged folder makes the creation all or nothing, and an existing id is refused rather than overwritten.

## Steps

1. [`run_new`](../../../pipeline/video_factory/cli.py) reads `VF_CONTENT` and the template.
2. [`build`](../../../pipeline/video_factory/videos.py) checks the id, fills the template, validates the script and the state.
3. [`create`](../../../pipeline/video_factory/videos.py) refuses an existing folder, writes a staged folder and renames it.

## If you change this

- **Hits:** the files `video-content` receives and their schemas.
- **Does not hit:** the tools directory or the media store.
