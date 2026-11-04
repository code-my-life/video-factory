---
name: video-factory
description: How video-factory turns an annotated script into the HyperFrames project of `compose` - which annotation becomes which scene, the strictest safe zones of TikTok, Reels and Shorts, the offline render, how each allowed animation library is shipped, and how to pull a block or component from the HyperFrames registry into templates/hyperframes/. Use when changing compose, a scene template, the captions, or adding a registry item or a library to this repository.
---

# video-factory: from the script to the HyperFrames project

`vf run <id>` makes the master; `compose` (`pipeline/video_factory/compose.py`) is the step that writes and renders a
real HyperFrames project from `templates/hyperframes/`. Read the `hyperframes`, `hyperframes-cli` and
`hyperframes-registry` skills for the format itself; this skill holds what is specific to this repository.
`motion-doctrine`, `captions-overlay`, `seam-craft` and `cut-the-curve` (copied from HyperFrames, see their `ORIGIN.md`)
apply on top.

## The project compose writes

| File | What it is |
| --- | --- |
| `index.html` | The only root: 1440x2560, `data-fps="30"`, `data-duration` = the cut. The take (`assets/camera.mp4`, muted, timed) sits in `#camera-wrap`; the root timeline `main` scales that wrapper for punch-ins, never the video. |
| `compositions/shot-<n>.html` | One scene per shot of the script, mounted by a host whose id, composition id and timeline key are `shot-<n>`, on track 1 (`graphics`). |
| `compositions/captions.html` | The one host of the `captions` track: caption groups, one visible at a time. |
| `assets/lib/<name>/` | Each pinned library a page loads (GSAP always), copied from the lock. |
| `assets/fonts/` | The one provisional font, Inter Bold, as `"VF Provisoire"` through `@font-face`. |
| `texte.html` (outside the project) | The text pass: the same hosts, text only, white on black; mounted over `index.html` for the second render, so the project keeps one root. |

The plan (shots, words, caption groups, punch-ins) is computed in Python, in output frames, then written as JSON into
each scene's `CONFIG`; a scene never decides timing on its own.

## Annotations to scenes

An annotation at the end of a line covers its sentence; inside a line it starts on the word before it. A shot lasts
until the next sentence or the next shot.

| In `script.md` | Scene template | Notes |
| --- | --- | --- |
| `[etapes: a \| b \| c]` | `blocks/mk-specs-list.html` (registry) | One row per step, arriving over the first 60 % of the shot. |
| `[stat: 9 postes \| caption]` | `blocks/mk-progress-stat.html` (registry) | A leading whole number counts up; the rest of the figure is its label. |
| `[code: ...]` | `scenes/code.html` | Typed over 60 % of the shot by a tween of a counter. |
| `[capture: name]` | `scenes/capture.html` | A still (slow push on a wrapper) or a silent clip, registered by `vf ingest <id> --capture`. |
| `[zoom]` | root timeline `main` | Punch-in on `#camera-wrap`: 1.12 in 4 frames, cut back after 1 s. |
| every said word | `components/caption-highlight.html` (registry) | Groups of 3 words at most, closed at a sentence end or a 150 ms pause. |

Each template takes `{{ID}}` (prefix of every id, so two shots of one kind never collide), `{{DURATION}}` and
`{{CONFIG}}` (`{{MEDIA}}` for a capture). A placeholder left unfilled stops compose. Map a new kind in `compose.SCENES`.

## Safe zones

Text stays inside the strictest zone of TikTok, Instagram Reels and YouTube Shorts: 15 % of the height at the top,
35 % at the bottom, 6 % of the width on the left, 17.8 % on the right. On 1440x2560 that is x 86 to 1183, y 384 to 1664
(`compose.safe_box()`). Shots write in `compose.SHOT` (96, 404, 1078x980), captions in `compose.CAPTION`
(96, 1424, 1078x220). `qc` measures every frame of the text pass and refuses a master whose text leaves the zone.

## Offline and deterministic

- The render and `hyperframes check --json` run in the pinned image `vf-hyperframes-render`, started by compose with
  `docker run --network none`; check must report no error before any render. Never `npx hyperframes`, never the CLI
  without the `env` of its lock entry, never `render --docker`.
- A project loads only its own files: no `http(s)://` or `//` in `src`, `href`, `url()` or `@import`, no CDN host
  anywhere (`compose.CDN_HOSTS`), no Google Fonts. Fonts come through `@font-face` from `assets/fonts/`.
- Everything visible is a function of the timeline time: paused timelines registered last under their id, `fromTo`,
  no timer, `Date`, `requestAnimationFrame` clock or unseeded randomness, finite repeats. Same inputs, same framemd5.
- Every template file counts in the fingerprint of the compose step: changing one makes compose stale.

## Allowed libraries and how each is shipped

Every library is an entry of kind `library` in `toolchain/tools.lock.json`: files taken from a verified npm archive,
each pinned by SHA-256, installed by `uv run vf doctor --install <name>` and checked by `vf doctor`. compose copies a
library into `assets/lib/<name>/` when a page names that path, and refuses a name the lock does not pin.

| Runtime | Ship | Load and drive |
| --- | --- | --- |
| GSAP 3.15.0 (with CustomEase, MotionPathPlugin), the copy HyperFrames 0.9.12 embeds | `gsap` | `<script src="assets/lib/gsap/gsap.min.js">` in the root (scenes use the global); one paused timeline per scene in `window.__timelines[id]`. |
| CSS `@keyframes`, WAAPI | nothing | Finite iterations, `fill: both` / `animation-fill-mode: both`; WAAPI animations paused, offset by `delay`. |
| Lottie | `lottie-web` | `assets/lib/lottie-web/lottie.min.js`, `autoplay: false`, `loop` set, instance pushed to `window.__hfLottie`. |
| dotLottie | `dotlottie-web` | `import { DotLottie } from "./assets/lib/dotlottie-web/index.js"` in a module script, `DotLottie.setWasmUrl` to the local `dotlottie-player.wasm`, `autoplay: false`, pushed to `window.__hfLottie`. |
| anime.js v4 | `animejs` | `assets/lib/animejs/anime.umd.min.js`, `autoplay: false`, pushed to `window.__hfAnime`, randomness from `anime.createSeededRandom`. |
| Three.js, canvas | `three` (canvas: nothing) | `import * as THREE from "./assets/lib/three/three.module.js"` (it imports `three.core.js`); draw from `e.detail.time` in an `hf-seek` listener; heavy setup behind `window.__hf.buildReady[key]`. |

A new library: add a `library` entry (version at least two weeks old, archive and file hashes computed on the
download), install it, and say in the docs what it is for.

## Pulling a block or component from the registry

1. Find it: `hyperframes catalog --query "<the move, in English>" --json` (offline once the manifest is cached).
2. Install it as source, at development time only (it needs the network; compose never calls it), from
   `templates/hyperframes/`, with the pinned Node on `PATH` and the `env` of the `hyperframes` lock entry:
   `~/.local/share/video-factory/tools/hyperframes/0.9.12/node_modules/.bin/hyperframes add <name> --no-clipboard --json`.
   `hyperframes.json` pins the registry at the v0.9.12 tag (commit 1ff4cef), so the item matches the pinned runtime;
   `add` records the item in `hyperframes.json` and its fingerprint in `hyperframes.lock.json`.
3. Commit the file exactly as installed, then adapt it in a second commit, so git keeps the upstream source:
   remove the jsDelivr GSAP script and any Google Fonts link (the root loads GSAP; use the `"VF Provisoire"`
   `@font-face`), size it to 1440x2560 on the shot box, prefix every id and class with `{{ID}}`, take its data from
   `{{CONFIG}}`, register the timeline under its id, prefer `fromTo`, and restyle it soberly (white on black, one
   font): the final look comes with the video design system, so invent no brand.
4. Wire it in `compose` (`SCENES` and the config of its kind), add a test, then run the tests, a sample project
   through `hyperframes check` in the image, and look at a few rendered frames of both passes.
