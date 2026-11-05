---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/cli.py
  - pipeline/video_factory/__init__.py
hits:
  - pipeline/video_factory/capture/
  - pyproject.toml
  - README.md
  - AGENTS.md
  - docs/RUNBOOK.md
  - tests/test_new.py
---

# cli

The `vf` command: it parses `vf doctor [--install [TOOL ...]]`, `vf new <id>`, `vf ingest <id> [takes] [--capture NAME FILE]`, `vf status <id>`, `vf run <id> [--refaire STEP ...]`, `vf publish <id>`, `vf studio serve|tick|carte` and `vf capture <plan> [--sortie DIR] [--travail DIR] [--sans-rendu]` ([capture](capture.md)), hands the environment and the home directory to the modules, and turns their results into French messages and exit codes (`vf run` exits 1 when a step fails or `qc` refuses the master).

## Why this shape

Everything that depends on the session (environment variables, home directory, printing, exit codes) stays in this module, so the other modules take those as arguments and are tested without touching the real machine.

## If you change this

- **Hits:** the console script `vf` in `pyproject.toml`; the commands documented in `README.md`, `AGENTS.md` and `docs/RUNBOOK.md`; `tests/test_new.py`, which calls `main`.
- **Does not hit:** what a check means ([doctor](doctor.md)), what `vf new` writes ([videos](videos.md)) or what a step does ([chain](chain.md)): the CLI only routes to them.

## See

- [`main`](../../../../pipeline/video_factory/cli.py), [`run_doctor`](../../../../pipeline/video_factory/cli.py), [`run_new`](../../../../pipeline/video_factory/cli.py), [`run_ingest`](../../../../pipeline/video_factory/cli.py), [`run_chain`](../../../../pipeline/video_factory/cli.py)
