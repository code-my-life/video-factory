"""Fingerprints: SHA-256 of a file or of a whole tree, and the SHA-512 integrity string that npm lockfiles carry."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

CHUNK = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def tree_lines(root: Path, skip: frozenset[str] = frozenset()) -> list[str]:
    """One line per file under root, sorted by relative path: « path NUL sha256 » for a regular file, « path NUL ->
    target » for a symbolic link (never followed). Directories, modes and timestamps do not count, so the same archive
    extracted twice gives the same lines. Names in skip (vf's own stamp files at the top) are left out."""
    entries = []
    for current, _dirnames, filenames in root.walk(follow_symlinks=False):
        # Without following links, a link to a directory is listed with the files: it is recorded, never entered.
        for name in filenames:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if relative in skip:
                continue
            if path.is_symlink():
                entries.append((relative, f"->{path.readlink().as_posix()}"))
            elif path.is_file():
                entries.append((relative, sha256_file(path)))
    return [f"{relative}\0{value}\n" for relative, value in sorted(entries)]


def tree_sha256(root: Path, skip: frozenset[str] = frozenset()) -> str:
    """One SHA-256 for a whole tree: the SHA-256 of its sorted tree_lines."""
    return sha256_bytes("".join(tree_lines(root, skip)).encode())


def npm_integrity(path: Path) -> str:
    """The « sha512-<base64> » string npm writes in package-lock.json for a tarball."""
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return "sha512-" + base64.b64encode(digest.digest()).decode()
