---
type: object
cluster: studio
universe: live
paths:
  - pipeline/video_factory/studio/stations.py
hits:
  - hermes/manifest.json
  - tests/test_board.py
---

# stations

The stations of a video on the studio board, read from `hermes/manifest.json`, and `decide`: from a card (its lane, status, events and comments) and the facts of its `state.json`, the next move of the card. Pure functions only.

## Why this shape

A card's station is its assignee, a lane name that is not a profile, so the dispatcher never spawns anything on it; its status says whether it waits (`scheduled`) or has work (`ready`). The owner's answer is the unblock since the card arrived at its station, and a reason starting with « refaire » goes back one station. Keeping the decision pure makes every path testable without Hermès.

## If you change this

- **Hits:** the lanes ([lanes](lanes.md)), the page's view of a station ([page](page.md)), the board's cards already in flight (a renamed lane strands them), `tests/test_board.py`.
- **Does not hit:** the chain of `vf run`, the state schema (the board reads `state.json`, never writes it).

## See

- [`decide`](../../../../pipeline/video_factory/studio/stations.py), [`owner_answer`](../../../../pipeline/video_factory/studio/stations.py), [`station_from_state`](../../../../pipeline/video_factory/studio/stations.py), [`facts_of`](../../../../pipeline/video_factory/studio/stations.py)
