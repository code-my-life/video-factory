---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/install.py
hits:
  - pipeline/video_factory/doctor.py
  - toolchain/tools.lock.json
  - tests/test_install.py
  - docs/RUNBOOK.md
---

# install

`vf doctor --install`: downloads each tool of the lock, verifies its SHA-256 before any use, then extracts, builds or installs it into `VF_TOOLS/<tool>/<version>/` in one rename.

## Why this shape

Nothing unverified reaches the tools directory: a download is hashed while it is written and deleted on a gap; archives go through the "data" extraction filter; a source archive must also carry the pinned commit in its pax header; the npm lockfile must pin the very tarball whose SHA-256 was just checked. Work happens in a scratch directory next to the tools so the final rename never crosses file systems.

## If you change this

- **Hits:** the stamps [doctor](doctor.md) reads (`.vf-build.json`, `.vf-install.json`); the fields of each kind in the [tools lock](../toolchain/tools-lock.md) and its schema; `tests/test_install.py`; the update procedure in `docs/RUNBOOK.md`, whose tree digest command calls `extract`.
- **Does not hit:** the Python dependencies (`uv.lock`), which uv installs, or the content clone.

## See

- [`install`](../../../../pipeline/video_factory/install.py), [`download`](../../../../pipeline/video_factory/install.py), [`extract`](../../../../pipeline/video_factory/install.py), [`install_npm`](../../../../pipeline/video_factory/install.py), [`install_source_build`](../../../../pipeline/video_factory/install.py)
