---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/board.py
hits:
  - tests/test_board.py
---

# board

The studio board through the Hermès CLI: `hermes kanban --board studio` list, show, create, assign, schedule, unblock, claim, comment and complete, with their JSON output read into `Card` values.

## Why this shape

The CLI is Hermès's native interface; its database and files are never read or written, so a change of Hermès's schema cannot corrupt the board. The runner is injected, and the tests use an in-memory board with the same rules (`FakeBoard` in `tests/conftest.py`).

## If you change this

- **Hits:** every lane and the page; `FakeBoard`, which must keep the CLI's behaviour.
- **Does not hit:** the factory's board: every call names `--board studio`.

## See

- [`Board`](../../../../pipeline/video_factory/studio/board.py), [`card_of`](../../../../pipeline/video_factory/studio/board.py)
