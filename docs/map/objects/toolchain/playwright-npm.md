---
type: object
cluster: toolchain
universe: live
paths:
  - toolchain/playwright/package.json
  - toolchain/playwright/package-lock.json
hits:
  - toolchain/tools.lock.json
  - pipeline/video_factory/capture/shoot.py
  - tests/test_lock.py
---

# Playwright npm lockfile

The npm project that `vf doctor --install playwright` installs with `npm ci`: `playwright-core` 1.64.1 alone (the version of factory-live's e2e), pinned by its sha512 integrity. Its browser is its own lock entry, `chromium-headless-shell` 156.0.8078.4 (revision 1248), a zip from Playwright's CDN; `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` keeps Playwright from fetching anything.

## Why this shape

Like HyperFrames: the tools lock pins the tarball by SHA-256, this lockfile pins what `npm ci` installs, and the installer checks that both agree. The driver launches the pinned Chromium by its path.

## If you change this

- **Hits:** the `playwright` and `chromium-headless-shell` entries of the [tools lock](tools-lock.md), in the same pull request (a new Playwright wants its own browser revision); every capture (two captures of a plan are only identical on the same browser).
- **Does not hit:** the render image of HyperFrames.

## See

- [`run_driver`](../../../../pipeline/video_factory/capture/shoot.py), [`extract_zip`](../../../../pipeline/video_factory/install.py)
