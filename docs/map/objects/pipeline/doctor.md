---
type: object
cluster: pipeline
universe: live
paths:
  - pipeline/video_factory/doctor.py
hits:
  - pipeline/video_factory/install.py
  - pipeline/video_factory/cli.py
  - tests/test_doctor.py
  - docs/RUNBOOK.md
---

# doctor

`vf doctor`: each tool of the lock is present, at its version and its SHA-256, and the content clone and the media store exist; each gap is a `Problem` that names its subject, the gap and the exact command that fixes it.

## Why this shape

One check per kind of lock entry (archive, file, source build, npm, pulled Docker image, built Docker image, library: each file at its SHA-256 and nothing else in the folder), each returning problems instead of raising, so the report lists every gap at once and the exit code is 1 when there is one. A built image passes when its build folder has the lock's fingerprint and the image carries the pinned digest (manifest or config, depending on Docker's image store). After `--install` of named tools, the report covers those tools only. Commands run through a runner, so tests answer them without processes. A source build cannot be pinned by the hash of its binary (it depends on the compiler), so its stamp records the verified source and the options, and the binary hash only guards against a change after the build.

## If you change this

- **Hits:** [install](install.md), which uses `check_tool` to skip tools in place and writes the stamps these checks read (`build_stamp`, `INSTALL_STAMP`); the messages documented in `docs/RUNBOOK.md`; `tests/test_doctor.py`.
- **Does not hit:** the lock's content ([tools lock](../toolchain/tools-lock.md)); adding a tool there needs no change here unless it is a new kind.

## See

- [`check_tool`](../../../../pipeline/video_factory/doctor.py), [`diagnose`](../../../../pipeline/video_factory/doctor.py), [`report`](../../../../pipeline/video_factory/doctor.py), [`check_places`](../../../../pipeline/video_factory/doctor.py)
