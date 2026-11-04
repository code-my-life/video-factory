---
type: object
cluster: barriers
universe: live
paths:
  - scripts/check_no_content.py
  - .gitignore
hits:
  - .github/workflows/ci.yml
  - tests/test_no_content.py
  - AGENTS.md
  - docs/RUNBOOK.md
---

# no-content check

`scripts/check_no_content.py`: fails, naming each file, when git tracks a file under a `videos/` folder, a media file outside `tests/fixtures/`, an image outside `design/` and `tests/fixtures/`, or a fixture over 256 KiB. `.gitignore` keeps the same files out of a careless `git add`.

## Why this shape

This repository is public and must never hold video content. The check reads the git index (what would be published), not the working tree, takes sizes from the blobs, and uses only the standard library so the runner's Python runs it with no install. It prints a GitHub annotation per file so the run names the file.

## If you change this

- **Hits:** the "Aucun contenu" job of the [workflows](workflows.md) and its required check in the ruleset; `tests/test_no_content.py`; the rules in `AGENTS.md` and `docs/RUNBOOK.md`.
- **Does not hit:** `video-content`, which is private and is where scripts and states belong.

## See

- [`problem`](../../../../scripts/check_no_content.py), [`tracked`](../../../../scripts/check_no_content.py), [`main`](../../../../scripts/check_no_content.py)
