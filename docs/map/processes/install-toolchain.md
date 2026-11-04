---
type: process
paths:
  - pipeline/video_factory/install.py
  - toolchain/tools.lock.json
hits:
  - pipeline/video_factory/doctor.py
consumes:
  - ../objects/toolchain/tools-lock.md
  - ../objects/toolchain/hyperframes-npm.md
produces:
  - VF_TOOLS/<tool>/<version>/ and its stamps
---

# install the toolchain

`vf doctor --install [TOOL ...]` brings the machine to the lock, then reruns the doctor.

## Input, movement, output

The lock and the names asked for come in; each tool not already in place (as the doctor sees it) is downloaded, verified, extracted, built or installed in lock order, requirements first; the doctor report closes the run.

## Why this shape

The doctor and the installer share one notion of "in place", so the installer never redoes a good tool and never skips a broken one; a failure stops at the first tool that cannot be installed, with nothing unverified left behind.

## Steps

1. [`requirement_order`](../../../pipeline/video_factory/lock.py) expands the names with what they require.
2. [`install`](../../../pipeline/video_factory/install.py) skips the tools [`check_tool`](../../../pipeline/video_factory/doctor.py) finds in place.
3. [`install_tool`](../../../pipeline/video_factory/install.py) runs the kind's installer in a scratch directory, then swaps the result in.
4. [`diagnose`](../../../pipeline/video_factory/doctor.py) reports every tool and place.

## If you change this

- **Hits:** what lands under `VF_TOOLS`, Docker's local images, and HyperFrames' `~/.hyperframes/config.json`.
- **Does not hit:** the repository or the content clone.
