---
type: object
cluster: vitrine
universe: live
paths:
  - vitrine/factory-live/
hits:
  - pipeline/video_factory/capture/demo.py
  - tests/test_capture.py
  - docs/RUNBOOK.md
---

# factory-live, as filmed

`vitrine/factory-live/`: `source.json` (the repository, commit 1c3e8ac in full, `node-24`, the demo build of factory-live's site: `VITE_DATA_SOURCE=demo`, memory router, base `./`, no PWA), `scenario.patch` (the shooting variant) and `plans/` (the capture plans: `plan3-graphe` for the showcase video 1, `iphone-ligne` for the phone, `parcours-une-issue` for the survey of the variant).

## Why this shape

factory-live is never modified: the variant is a patch applied to the pinned commit in a work folder, and `git apply --check` refuses it if the commit moves under it. In the variant, claude-cockpit#73 starts in Intake and goes through Brief (27 s), Implémentation (58 s), the fail-first gate (63 s), Ta revue (70 s), Fusion (76 s), CI de main (79 s), Déploiement (83 s) and Terminé (87 s), each step with the facts the app reads from GitHub; the rest of the demo's scenario is unchanged and factory-live's own tests pass on it.

## If you change this

- **Hits:** every capture of factory-live (a new build key, new frames); the acceptance test of the variant; the plans' times, which follow the variant's.
- **Does not hit:** factory-live itself, nor the chain.

## See

- [`source.json`](../../../../vitrine/factory-live/source.json), [`scenario.patch`](../../../../vitrine/factory-live/scenario.patch), [`plans/`](../../../../vitrine/factory-live/plans/)
