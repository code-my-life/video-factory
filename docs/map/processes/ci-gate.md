---
type: process
paths:
  - .github/workflows/ci.yml
  - .github/workflows/conventions.yml
hits:
  - scripts/check_no_content.py
  - tests/
consumes:
  - ../objects/barriers/no-content.md
  - ../objects/barriers/tests.md
  - ../objects/barriers/workflows.md
produces:
  - the checks "Aucun contenu", "Lint et tests (Python 3.12)" and "Conventions / Branche, titre et texte de PR"
---

# CI gate

A push or a pull request goes through the barriers that the ruleset "main" requires before a merge.

## Input, movement, output

A push on any branch runs the no-content check and the lint and tests; a pull request runs them on the merge result and adds the Conventions check; the ruleset lets a pull request merge only when the three are green and the owner approved.

## Why this shape

Content is caught at the push, since the repository is public; conventions are checked on the pull request, since they read its title, text and issue.

## Steps

1. The `no-content` job runs [`main`](../../../scripts/check_no_content.py) of the no-content check.
2. The `verify` job runs `uv sync --locked`, ruff and pytest.
3. The `conventions` job calls the reusable workflow of code-my-life/.github.

## If you change this

- **Hits:** the ruleset "main", which requires the three check names.
- **Does not hit:** local commands, which run the same tools by hand (`AGENTS.md`).
