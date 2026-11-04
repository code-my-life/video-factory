---
type: process
paths:
  - pipeline/video_factory/studio/lanes.py
  - pipeline/video_factory/studio/stations.py
hits:
  - hermes/manifest.json
consumes:
  - ../objects/studio/stations.md
  - ../objects/studio/board.md
  - ../objects/studio/writer.md
produces:
  - the cards' moves on the studio board, script.md drafts, vf runs, Telegram messages
---

# a studio pass

Every 20 s the service reads the studio board and moves each card one step.

## Input, movement, output

The open cards come in; for each, `decide` reads its station, its status, its events and its video's `state.json`, and returns a plan: wait, run a lane's job, move it (and park it where the owner must act), park it, or complete it. Jobs (`vf new`, the draft, `vf run`, `vf publish`) run one at a time beside the passes; their outcome moves the card on, or parks it with the reason and a Telegram message.

## Why this shape

The decision is pure and the effects go through the CLI, so a pass can be replayed by hand (`vf studio tick`) and tested without Hermès.

## Steps

1. [`Studio.cards`](../../../pipeline/video_factory/studio/lanes.py) lists the board; only ready cards are read in full.
2. [`decide`](../../../pipeline/video_factory/studio/stations.py) gives the plan.
3. [`Studio.apply`](../../../pipeline/video_factory/studio/lanes.py) moves, parks, completes or queues the job.

## If you change this

- **Hits:** what the owner sees on the board and on Telegram.
- **Does not hit:** the factory's board, its dispatch slots (no studio card runs except during a draft).
