"""The media store (VF_MEDIA): every take and every output of a step, named by its SHA-256.

A file lives at « <sha256>.<ext> » and is made read-only once stored, so a name always means the same bytes; storing the
same bytes twice keeps the first copy. Steps work in a scratch folder inside the store (« .work/ »), so moving a result
in is one rename on the same file system.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from video_factory.hashing import sha256_file, tree_sha256

EXTENSION = re.compile(r"^[a-z0-9]+$")
WORK = ".work"


class StoreError(Exception):
    """A file is missing from the store or differs from its name."""


def name(digest: str, ext: str) -> str:
    if not EXTENSION.match(ext):
        raise StoreError(f"extension « {ext} » refusée : minuscules et chiffres")
    return f"{digest}.{ext}"


def ref(digest: str, ext: str) -> dict[str, str]:
    """What the state records for a stored file: its fingerprint and its name in the store."""
    return {"sha256": digest, "file": name(digest, ext)}


def path(root: Path, media: dict[str, str]) -> Path:
    return root / media["file"]


def put(root: Path, source: Path, ext: str, *, keep_source: bool = False) -> dict[str, str]:
    """Store a file under its SHA-256 and return its reference; the source is moved in, or copied when kept."""
    digest = sha256_file(source)
    target = root / name(digest, ext)
    if target.exists():
        if not keep_source:
            source.unlink()
        return ref(digest, ext)
    root.mkdir(parents=True, exist_ok=True)
    staged = root / WORK / f"{target.name}.part"
    staged.parent.mkdir(parents=True, exist_ok=True)
    if keep_source:
        shutil.copyfile(source, staged)
    else:
        shutil.move(source, staged)
    staged.chmod(0o444)
    staged.replace(target)
    return ref(digest, ext)


def put_tree(root: Path, folder: Path, ext: str) -> dict[str, str]:
    """Store a folder under the fingerprint of its tree (hashing.tree_sha256); the folder is moved in."""
    digest = tree_sha256(folder)
    target = root / name(digest, ext)
    if target.exists():
        writable(folder)
        shutil.rmtree(folder)
        return ref(digest, ext)
    for current, _dirs, files in os.walk(folder):
        for file in files:
            Path(current, file).chmod(0o444)
    root.mkdir(parents=True, exist_ok=True)
    folder.replace(target)
    return ref(digest, ext)


def problem(root: Path, media: dict[str, str], deep: bool = False) -> str | None:
    """Why a stored file or folder cannot be used: absent, or (deep) its content no longer matches its fingerprint."""
    target = path(root, media)
    if not target.exists():
        return f"{media['file']} absent du magasin"
    if deep:
        found = tree_sha256(target) if target.is_dir() else sha256_file(target)
        if found != media["sha256"]:
            return f"{media['file']} modifié dans le magasin"
    return None


@contextmanager
def scratch(root: Path, label: str) -> Iterator[Path]:
    """A scratch folder inside the store, removed afterwards whatever happens."""
    base = root / WORK
    base.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=f"{label}-", dir=base))
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def writable(folder: Path) -> None:
    """Make every file under folder writable again, so a scratch folder can be removed; a file that vanished meanwhile
    (a render still cleaning up) is skipped."""
    for current, _dirs, files in os.walk(folder):
        for file in files:
            with suppress(FileNotFoundError):
                Path(current, file).chmod(0o644)
