# video-factory map

The map of this repository for an agent about to change it, in the ICM "System map" form adapted by code-my-life/hermes-software-factory#24. One card per module under `objects/<cluster>/`, real movements only under `processes/`. Each card declares the paths it covers (`paths`) and what moves when they change (`hits`) in its front matter. There is no hand-written index: the impact index is computed from those front matters by the shared checker of code-my-life/.github, which does not exist yet; until then, open the card whose `paths` cover the file you change.

Covered roots: `pipeline/`, `templates/`, `toolchain/`, `schemas/`, `scripts/`, `tests/`, `.github/`, and the Python project files at the top (`pyproject.toml`, `uv.lock`, `.python-version`).

## Clusters

- `objects/pipeline/`: the `video_factory` package behind the `vf` command, one card per module.
- `objects/toolchain/`: the lock of external tools and the npm lockfile of HyperFrames.
- `objects/contracts/`: the schemas this repository publishes for `video-content`.
- `objects/templates/`: the script template.
- `objects/barriers/`: what keeps content out and conventions in (no-content check, workflows, tests).
- `objects/project/`: the Python project definition.
- `processes/`: `vf new`, `vf doctor --install`, and the CI gate of a push or a pull request.

## Names that collide

- "chaîne": the chain of steps from `ingest` to `qc` (the pipeline), or the Code My Life channel that publishes the videos.
- "lock": `toolchain/tools.lock.json` (external tools, by SHA-256), `uv.lock` (Python dependencies) and `toolchain/hyperframes/package-lock.json` (the npm tree of HyperFrames). Three files, three owners.
- "state": `state.json` of a video in `video-content` (schema `schemas/state.schema.json`), not the install stamps `.vf-build.json` and `.vf-install.json` that `vf doctor --install` writes in the tools directory.
- "template" (gabarit): `templates/script.md`, the script template; the HyperFrames composition templates come later with the design system.
- "doctor": `vf doctor` (this repository); `hyperframes doctor` is HyperFrames' own command and is never called.
- "videos": `videos/<id>/` folders live in `video-content`; `pipeline/video_factory/videos.py` is the module that creates them. The no-content check refuses a `videos/` folder, never a file named `videos.py`.
- "pipeline": the package directory `pipeline/` (Python source root), and the chain of steps it will run.

## Universes

- **live**: `vf doctor`, `vf doctor --install`, `vf new`, the lock and its schema, the two published schemas, the script template, the no-content check, the CI and Conventions workflows.
- **leftover**: none.
- **ghost** (named, not built; do not implement against these):
  - `design/`: the video design system, its tokens and fonts (design system issue, after the key frames are validated); the fonts are missing from the lock until then;
  - `mask/`: the robot mask and the shooting routes, `mask/routes.json` read by `ingest` (#3, then #4);
  - the steps `ingest`, `scan`, `blur`, `transcribe`, `align`, `cut`, `voice`, `compose`, `master`, `qc`, and `vf status` and `vf run` (#4); their names already exist as the allowed keys of `steps` in `schemas/state.schema.json`;
  - the pinned HyperFrames render image (#4): only its base image is in the lock.

## What points into this repository from outside

- `code-my-life/video-content`: its README sends here; its `videos/<id>/script.md` and `state.json` follow `schemas/`, whose `$id` is the raw URL of `main`. Moving or renaming a schema breaks that URL.
- The machine: `VF_TOOLS` (`~/.local/share/video-factory/tools`), `VF_MEDIA` (`~/studio/media`), `VF_CONTENT` (`~/perso/video-content`), HyperFrames' own `~/.hyperframes/config.json` (telemetry choice), and the Docker tag `node:22.23.4-bookworm-slim`.
- GitHub: the ruleset "main" requires the check names "Aucun contenu", "Lint et tests (Python 3.12)" and "Conventions / Branche, titre et texte de PR"; renaming a job blocks every pull request until the ruleset follows. The ruleset "noms de branches" refuses a branch outside the typed prefixes.
- code-my-life/.github: the reusable Conventions workflow, read at `main`.
