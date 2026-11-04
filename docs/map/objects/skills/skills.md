---
type: object
cluster: skills
universe: live
paths:
  - .claude/skills/
hits:
  - docs/decisions/0003-projet-hyperframes-gsap-et-registre.md
  - CREDITS.md
---

# agent skills

`.claude/skills/`: `video-factory` (written here: script annotations to scenes, the strictest safe zones, the offline render, how each allowed library is shipped, how to pull a registry item) and four internal skills of HyperFrames copied at commit 2679bcd (`motion-doctrine`, `captions-overlay`, `seam-craft`, `cut-the-curve`), each with its Apache 2.0 `LICENSE` and an `ORIGIN.md`.

## Why this shape

Claude Code loads project skills from `.claude/skills/`; the HyperFrames skills installed for the user (`hyperframes`, `hyperframes-cli`, `hyperframes-registry`) say how HyperFrames works, these say how this repository uses it. The copies are frozen at the commit read, changed only to replace em dashes.

## If you change this

- **Hits:** what an agent does in this repository; for the copied skills, their `ORIGIN.md` (a new upstream commit, or any change made here) and the credits.
- **Does not hit:** the chain: no step reads a skill.

## See

- [`video-factory/SKILL.md`](../../../../.claude/skills/video-factory/SKILL.md)
