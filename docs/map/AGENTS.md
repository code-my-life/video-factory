# video-factory map

The map of this repository for an agent about to change it, in the ICM "System map" form adapted by code-my-life/hermes-software-factory#24. One card per module under `objects/<cluster>/`, real movements only under `processes/`. Each card declares the paths it covers (`paths`) and what moves when they change (`hits`) in its front matter. There is no hand-written index: the impact index is computed from those front matters by the shared checker of code-my-life/.github, which does not exist yet; until then, open the card whose `paths` cover the file you change.

Covered roots: `pipeline/`, `hermes/`, `vitrine/`, `templates/`, `.claude/skills/`, `toolchain/`, `schemas/`, `scripts/`, `tests/`, `.github/`, and the Python project files at the top (`pyproject.toml`, `uv.lock`, `.python-version`).

## Clusters

- `objects/pipeline/`: the `video_factory` package behind the `vf` command, one card per module (the eight steps, the chain that runs them, the store, the state), and `capture`, the package of `vf capture`.
- `objects/vitrine/`: the apps `vf capture` films, one card per app (pinned source, scenario variant, plans).
- `objects/studio/`: the Hermès board « studio » (#7): its stations, the board through the Hermès CLI, the lanes, the writer, the messages, the page and the service, and `hermes/` (manifest, profile, install).
- `objects/toolchain/`: the lock of external tools, the npm lockfiles of HyperFrames and Playwright, and the render image.
- `objects/contracts/`: the schemas this repository publishes (state, script, capture plan and source).
- `objects/templates/`: the script template, the HyperFrames project templates of `compose`, the registry items restyled for it, and the camera follow scene of `vf capture`.
- `objects/skills/`: the agent skills shipped with this repository (`video-factory` and four internal skills of HyperFrames).
- `objects/barriers/`: what keeps content out and conventions in (no-content check, workflows, tests).
- `objects/project/`: the Python project definition.
- `processes/`: `vf new`, `vf doctor --install`, `vf ingest`, `vf run`, `vf capture`, a studio pass, a take sent from the phone, and the CI gate of a push or a pull request.

## Names that collide

- "board": the Hermès kanban board « studio » of this repository, or the factory's board « factory »; never a whiteboard.
- "lane" (voie): a station's assignee on the studio board (`studio-montage`…), a name the dispatcher never spawns.
- "chaîne": the chain of steps from `ingest` to `qc` (the pipeline), or the Code My Life channel that publishes the videos.
- "lock": `toolchain/tools.lock.json` (external tools and libraries, by SHA-256), `uv.lock` (Python dependencies), `toolchain/hyperframes/package-lock.json` (the npm tree of HyperFrames) and `templates/hyperframes/hyperframes.lock.json` (the fingerprints of registry items as `hyperframes add` installed them). Four files, four owners.
- "registry": the HyperFrames registry of blocks and components (`hyperframes catalog`, `hyperframes add`), not a container or npm registry.
- "state": `state.json` of a video in `video-content` (schema `schemas/state.schema.json`), not the install stamps `.vf-build.json` and `.vf-install.json` that `vf doctor --install` writes in the tools directory.
- "template" (gabarit): `templates/script.md`, the script template, or `templates/hyperframes/`, the HyperFrames project templates of `compose` (provisional look); the design system will bring the final look.
- "capture": a still or clip of a real screen shown by `[capture: <name>]`, not a video capture of the take; `vf capture` shoots such a clip from an app's real demo (`pipeline/video_factory/capture/`), while `pipeline/video_factory/captures.py` cleans a capture before it is stored.
- "plan": a capture plan of `vf capture` (`vitrine/<app>/plans/*.json`), or a shot of a showcase video's script (« plan 3 »); compose's own plan is the JSON of shots, words and groups it computes.
- "track": `track.json` of a capture (each tracked element's box per frame), not a track of the timeline.
- "frames": the PNG frames `compose` stores as a folder `<sha256>.frames/`, or the framemd5 files of `master`.
- "doctor": `vf doctor` (this repository); `hyperframes doctor` is HyperFrames' own command and is never called.
- "videos": `videos/<id>/` folders live in `video-content`; `pipeline/video_factory/videos.py` is the module that creates them. The no-content check refuses a `videos/` folder, never a file named `videos.py`.
- "pipeline": the package directory `pipeline/` (Python source root), and the chain of steps it will run.

## Universes

- **live**: `vf doctor`, `vf doctor --install`, `vf new`, `vf ingest`, `vf status`, `vf run` and the eight steps, `vf publish`, `vf studio` and the board « studio », `vf capture`, its plans and the scenario variant of factory-live, the lock and its schema, the render image, the two published schemas, the script template, the HyperFrames project templates and registry items, the agent skills, the no-content check, the CI and Conventions workflows.
- **leftover**: none.
- **ghost** (named, not built; do not implement against these):
  - `design/`: the video design system, its tokens and fonts (design system issue, after the key frames are validated); it replaces the provisional look of the project templates;
  - `mask/`: the robot helmet and its build scripts (#3).

## What points into this repository from outside

- `code-my-life/video-content`: its README sends here; its `videos/<id>/script.md` and `state.json` follow `schemas/`, whose `$id` is the raw URL of `main`. Moving or renaming a schema breaks that URL. Every `state.json` records a fingerprint of the sources of each step: changing a step's code makes it stale in every video.
- Hermès: the board `studio`, the profile `studio-writer` and the user service `video-factory-studio.service`, installed by `hermes/install.sh`; the page on the tailnet's port 8448 (`tailscale serve`).
- code-my-life/factory-live: `vitrine/factory-live/source.json` pins its commit and `scenario.patch` must apply to it; `vf capture` fetches that commit from GitHub.
- The machine: `VF_TOOLS` (`~/.local/share/video-factory/tools`), `VF_MEDIA` (`~/studio/media`, holding every take and output by fingerprint, and `vitrine/` for the plans `vf capture` shoots and the demos it builds), `VF_CONTENT` (`~/perso/video-content`), HyperFrames' own `~/.hyperframes/config.json` (telemetry choice), and the Docker images `node:22.23.4-bookworm-slim` and `vf-hyperframes-render:0.9.12-1`.
- GitHub: the ruleset "main" requires the check names "Aucun contenu", "Lint et tests (Python 3.12)" and "Conventions / Branche, titre et texte de PR"; renaming a job blocks every pull request until the ruleset follows. The ruleset "noms de branches" refuses a branch outside the typed prefixes.
- code-my-life/.github: the reusable Conventions workflow, read at `main`.
