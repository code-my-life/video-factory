---
type: object
cluster: barriers
universe: live
paths:
  - .github/workflows/ci.yml
  - .github/workflows/conventions.yml
  - .github/CODEOWNERS
hits:
  - docs/RUNBOOK.md
  - AGENTS.md
---

# workflows

The GitHub barriers: `ci.yml` runs "Aucun contenu" and "Lint et tests (Python 3.12)" on every push of any branch and on each pull request (the second installs the pinned FFmpeg, cached by the lock's hash, and requires them); `conventions.yml` calls the shared Conventions check of code-my-life/.github; `CODEOWNERS` makes the owner's approval required.

## Why this shape

A push to a public repository is public, so the no-content check runs on every branch, before any pull request. Actions are pinned by commit SHA and uv by version. The job names are the contract with the ruleset "main", which requires them by name.

## If you change this

- **Hits:** the ruleset "main" (a renamed job blocks every pull request until the ruleset follows); `docs/RUNBOOK.md` and `AGENTS.md`, which name the jobs.
- **Does not hit:** what a job checks: the [no-content check](no-content.md) and the [tests](tests.md) hold the rules.

## See

- The `verify` and `no-content` jobs in [`ci.yml`](../../../../.github/workflows/ci.yml), the `conventions` job in [`conventions.yml`](../../../../.github/workflows/conventions.yml)
