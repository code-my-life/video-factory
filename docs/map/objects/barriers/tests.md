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

The pytest suite: one file per module (`test_doctor.py`, `test_install.py`, `test_lock.py`, `test_new.py`, `test_frontmatter.py`, `test_schemas.py`, `test_hashing.py`, `test_paths.py`) and the no-content check (`test_no_content.py`); `conftest.py` builds throwaway git repositories and archives.

## Why this shape

Tests touch nothing outside their temporary directory: the doctor gets recorded answers instead of processes, the installer gets an opener instead of the network, and git repositories are built on the fly. `tests/fixtures/` is the only place a small synthetic media file may live.

## If you change this

- **Hits:** the "Lint et tests (Python 3.12)" job of the [workflows](workflows.md); a test is never weakened to pass.
- **Does not hit:** the installed tools: no test reads `VF_TOOLS` or the network.

## See

- [`make_repo`](../../../../tests/conftest.py), [`tar_bytes`](../../../../tests/conftest.py)
