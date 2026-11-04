#!/usr/bin/env python3
"""The « no content » check of video-factory: git tracks no video content in this public repository.

It fails, and names each file, when the git index holds:
- a file under a directory named videos/, where video-content keeps the scripts and states of the videos;
- a media file (a take, a voice, a render) outside tests/fixtures/;
- an image (png, jpg) outside design/ and tests/fixtures/;
- a file under tests/fixtures/ larger than FIXTURE_CAP: fixtures are small and synthetic.

Standard library only, so the runner's Python is enough: `python3 scripts/check_no_content.py [repository]`.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

MEDIA = frozenset(
    {".mov", ".mp4", ".m4v", ".m4a", ".wav", ".heic", ".heif", ".mkv", ".webm", ".mp3", ".aac", ".flac", ".caf"}
)
IMAGES = frozenset({".png", ".jpg", ".jpeg"})
FIXTURES = "tests/fixtures/"
DESIGN = "design/"
FIXTURE_CAP = 256 * 1024
GITLINK = "160000"


def tracked(repository: Path) -> list[tuple[str, int]]:
    """(path, size in bytes) of every file in the git index, sizes read from the blobs git stores."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--stage"], cwd=repository, capture_output=True, check=True
    ).stdout.decode("utf-8", "surrogateescape")
    entries = []
    for record in filter(None, listing.split("\0")):
        meta, path = record.split("\t", 1)
        mode, blob, _stage = meta.split(" ")
        if mode != GITLINK:
            entries.append((path, blob))
    query = "".join(f"{blob}\n" for _path, blob in entries)
    sizes = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectsize)"],
        cwd=repository,
        input=query.encode(),
        capture_output=True,
        check=True,
    ).stdout.decode()
    return [
        (path, int(size) if size.isdigit() else disk_size(repository / path))
        for (path, _blob), size in zip(entries, sizes.splitlines(), strict=True)
    ]


def disk_size(path: Path) -> int:
    """The size of the checked-out file, for a blob missing from a partial clone."""
    return path.stat().st_size if path.is_file() else 0


def problem(path: str, size: int) -> str | None:
    """Why a tracked file is video content, or None when it may stay."""
    pure = PurePosixPath(path)
    extension = pure.suffix.lower()
    in_fixtures = path.startswith(FIXTURES)
    if any(part.lower() == "videos" for part in pure.parts[:-1]):
        return "dans un dossier videos/ : les scripts et les états vont dans video-content"
    if extension in MEDIA and not in_fixtures:
        return f"média {extension} : les prises et les rendus vont dans le magasin local (VF_MEDIA)"
    if extension in IMAGES and not (in_fixtures or path.startswith(DESIGN)):
        return f"image {extension} hors de design/ et de tests/fixtures/"
    if in_fixtures and size > FIXTURE_CAP:
        return f"fixture de {size} octets, au-delà de {FIXTURE_CAP} : une fixture est petite et synthétique"
    return None


def problems(entries: Iterable[tuple[str, int]]) -> list[tuple[str, str]]:
    found = ((path, problem(path, size)) for path, size in entries)
    return [(path, why) for path, why in found if why]


def annotation(path: str, why: str) -> str:
    """A GitHub Actions error annotation on the file, escaped as workflow commands require."""

    def data(text: str) -> str:
        return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    def prop(text: str) -> str:
        return data(text).replace(":", "%3A").replace(",", "%2C")

    return f"::error file={prop(path)},title={prop('Aucun contenu')}::{data(f'{path} : {why}')}"


def main(argv: list[str]) -> int:
    repository = Path(argv[0]) if argv else Path.cwd()
    entries = tracked(repository)
    found = problems(entries)
    if not found:
        print(f"Aucun contenu : {len(entries)} fichiers suivis, aucun contenu de vidéo.")
        return 0
    print(f"Aucun contenu : {len(found)} fichier(s) refusé(s) sur {len(entries)} suivis.")
    for path, why in found:
        print(annotation(path, why))
        print(f"- {path} : {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
