---
type: object
cluster: toolchain
universe: live
paths:
  - toolchain/hyperframes/Dockerfile.render
hits:
  - toolchain/tools.lock.json
  - pipeline/video_factory/install.py
  - tests/test_lock.py
---

# render image

`toolchain/hyperframes/Dockerfile.render`: the HyperFrames render image with every layer pinned (base by digest, Debian snapshot, chrome-headless-shell 152.0.7977.30, FFmpeg n8.0.1, HyperFrames from the npm lockfile); its arguments are in the lock, without defaults here.

## Why this shape

HyperFrames publishes no image and its own build is unpinned; with timestamps clamped and no attestation, two builds give the same digest, which the lock records and doctor checks.

## If you change this

- **Hits:** the `hyperframes-render` entry of the [tools lock](tools-lock.md) (`context_sha256`, `sha256`, `config_sha256`) in the same pull request; every video's compose (the image digest is a parameter); `tests/test_lock.py`.
- **Does not hit:** the host install of HyperFrames ([HyperFrames npm lockfile](hyperframes-npm.md)), which shares only the lockfile.

## See

- Built by [`install_docker_build`](../../../../pipeline/video_factory/install.py), run by [`render_command`](../../../../pipeline/video_factory/compose.py)
