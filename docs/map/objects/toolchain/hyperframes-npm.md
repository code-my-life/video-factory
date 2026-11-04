---
type: object
cluster: toolchain
universe: live
paths:
  - toolchain/hyperframes/package.json
  - toolchain/hyperframes/package-lock.json
hits:
  - toolchain/tools.lock.json
  - pipeline/video_factory/install.py
  - tests/test_lock.py
---

# HyperFrames npm lockfile

The npm project that `vf doctor --install hyperframes` installs with `npm ci`: `hyperframes` at its exact version, and the whole dependency tree pinned by sha512 integrity.

## Why this shape

The SHA-256 of the HyperFrames tarball pins one package, not its dependencies; `npm ci` from this lockfile pins the rest. Before `npm ci`, the installer checks that this lockfile pins the very tarball whose SHA-256 the tools lock holds.

## If you change this

- **Hits:** the `hyperframes` entry of the [tools lock](tools-lock.md) (version, URL, `sha256`, `tree_sha256`), in the same pull request; installed copies, which doctor reports as "installé depuis un autre package-lock.json"; `tests/test_lock.py`.
- **Does not hit:** the Docker render image, whose own npm install is not pinned by this file (see `not_pinned_yet` in the tools lock).

## See

- [`install_npm`](../../../../pipeline/video_factory/install.py), [`lockfile_integrity`](../../../../pipeline/video_factory/install.py)
