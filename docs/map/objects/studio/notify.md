---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/notify.py
hits:
  - tests/test_board.py
---

# notify

The Telegram messages to the owner, sent by the gateway's own sender (`hermes send -t telegram:<TELEGRAM_CHAT_ID>`): the video, the station, what to do, the page of the video and the `/kanban --board studio unblock` command.

## Why this shape

Reusing `hermes send` keeps one bot and one set of credentials; the chat id is read from the environment or from Hermès's root `.env`, never written.

## If you change this

- **Hits:** the owner's messages; the RUNBOOK's gestures.
- **Does not hit:** the factory's messages (factory-notify).

## See

- [`message`](../../../../pipeline/video_factory/studio/notify.py), [`send`](../../../../pipeline/video_factory/studio/notify.py)
