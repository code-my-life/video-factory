---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/hashing.py
hits:
  - toolchain/tools.lock.json
  - pipeline/video_factory/doctor.py
  - pipeline/video_factory/install.py
  - tests/test_hashing.py
---

# hashing

The fingerprints: SHA-256 of a file, `tree_sha256` of a whole extracted tree, and the "sha512-" integrity string npm writes in a lockfile.

## Why this shape

An archive tool is checked by the fingerprint of everything it extracts, not of one binary: names and contents count, links are recorded by their target and never followed, dates and modes do not count, so the same archive gives the same value on any machine and the value can live in the lock.

## If you change this

- **Hits:** every `tree_sha256` in the [tools lock](../toolchain/tools-lock.md), which must be recomputed; [doctor](doctor.md) and [install](install.md); `tests/test_hashing.py`.
- **Does not hit:** the plain `sha256` of downloads and models, which is the standard SHA-256 of the file.

## See

- [`tree_sha256`](../../../../pipeline/video_factory/hashing.py), [`tree_lines`](../../../../pipeline/video_factory/hashing.py), [`sha256_file`](../../../../pipeline/video_factory/hashing.py), [`npm_integrity`](../../../../pipeline/video_factory/hashing.py)
