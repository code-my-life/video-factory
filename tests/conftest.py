"""Shared helpers: throwaway git repositories and archives built in the test's temporary directory."""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path

import pytest

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git(repository: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(repository), **GIT_IDENTITY},
    )
    return done.stdout


@pytest.fixture
def make_repo(tmp_path: Path):
    """A git repository holding the given files ({relative path: bytes}), all added to the index."""

    def build(files: dict[str, bytes], name: str = "repo") -> Path:
        repository = tmp_path / name
        repository.mkdir()
        git(repository, "init", "-q")
        for relative, content in files.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if files:
            git(repository, "add", "--force", "--", *files)
        return repository

    return build


def tar_bytes(members: dict[str, bytes], top: str = "pkg-1.0", pax: dict[str, str] | None = None) -> bytes:
    """A gzipped tar archive whose files sit under one top directory, like a release archive."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT, pax_headers=pax or {}) as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(content)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()
