---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/lanes.py
hits:
  - tests/test_board.py
  - tests/test_upload.py
---

# lanes

`Studio`: one pass reads the board, decides each card and carries the plan out; the code lanes run `vf new`, `vf run` and `vf publish`, the Script station asks `studio-writer` for a draft, and a park sends the owner a Telegram message. Long jobs run one at a time beside the passes. It also opens a video's card and acts on the page's gestures and takes. For a showcase the received files become `vf ingest --voix` (the audio file) and `--capture <name>` (each other file, under the name it was sent with), and the card goes to Montage only once the video is shot.

## Why this shape

Only the Script station claims its card (running) while the model writes, so the local model stays loaded for it and is released by vram-release afterwards; a Montage card stays `ready` while `vf run` renders, holding no dispatch slot. Every move re-reads the card first, since the owner may have moved it meanwhile.

## If you change this

- **Hits:** the service ([service](service.md)), the page, the RUNBOOK's station table.
- **Does not hit:** the steps of the chain: the lanes call `vf`, never its modules.

## See

- [`Studio.tick`](../../../../pipeline/video_factory/studio/lanes.py), [`Studio.move`](../../../../pipeline/video_factory/studio/lanes.py), [`Studio.job_montage`](../../../../pipeline/video_factory/studio/lanes.py), [`Studio.takes_received`](../../../../pipeline/video_factory/studio/lanes.py)
