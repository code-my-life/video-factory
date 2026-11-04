---
type: object
cluster: barriers
universe: live
paths:
  - tests/
hits:
  - .github/workflows/ci.yml
---

# tests

The pytest suite: one file per module or step, and the no-content check (`test_no_content.py`); `conftest.py` builds throwaway git repositories and archives, gives the pinned tools (`tools` fixture) and draws synthetic media (a drawn face, textured frames). The acceptance tests of an issue carry its exact test name in `@pytest.mark.acceptance("…")`.

## Why this shape

Tests touch nothing outside their temporary directory: the doctor gets recorded answers instead of processes, the installer gets an opener instead of the network, whisper's output is recorded, and git repositories and media are built on the fly with the pinned FFmpeg. A test that needs a pinned tool is skipped without it, and fails in CI (`VF_REQUIRE_TOOLS=1`); the render-twice test runs only where the render image is built. `tests/fixtures/` is the only place a small synthetic media file may live (none is needed yet).

## If you change this

- **Hits:** the "Lint et tests (Python 3.12)" job of the [workflows](workflows.md); a test is never weakened to pass.
- **Does not hit:** the installed tools, which tests read under `VF_TOOLS` but never change; no test reads the network.

## See

- [`make_repo`](../../../../tests/conftest.py), [`tar_bytes`](../../../../tests/conftest.py)
