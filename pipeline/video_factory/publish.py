"""`vf publish <id>`: the files and the caption of a video whose master passed qc, ready to be posted by hand.

Publication is manual for now (docs/publication.md): this prepares `VF_MEDIA/publication/<id>/` with the TikTok
export, the master and the caption, and checks nothing is missing. It never posts anything.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from video_factory import frontmatter, store

FOLDER = "publication"
CAPTION_NAME = "legende.txt"
FILES = {"tiktok": "tiktok.mp4", "master": "master.mp4"}
# The credit the helmet's licence asks for, word for word as docs/publication.md gives it.
ROBOT_CREDIT = (
    "Robot : « Rank 3 Police Unit » de nikvili (Sketchfab), CC BY 4.0, modifié. "
    "sketchfab.com/3d-models/rank-3-police-unit-d7698f6a7acf49c68ff0a50c5a1b1d52"
)


class PublishError(Exception):
    """The video cannot be published yet; the message says why."""


@dataclass(frozen=True)
class Publication:
    caption: str
    sources: dict[str, Path]


def caption(title: str) -> str:
    """The sentence of the subject (the script's title), then the robot credit; the keywords are added by hand."""
    return f"{title}\n\n{ROBOT_CREDIT}\n"


def problems(state: dict, media: Path) -> list[str]:
    qc = state.get("steps", {}).get("qc")
    found = []
    if qc is None:
        found.append("qc n'est pas passé : vf run")
    elif not qc.get("summary", {}).get("passed"):
        found.append("qc refuse le master : vf status")
    outputs = state.get("steps", {}).get("master", {}).get("outputs", {})
    for name in FILES:
        if name not in outputs:
            found.append(f"sortie {name} de master absente : vf run")
            continue
        why = store.problem(media, outputs[name])
        if why:
            found.append(f"sortie {name} de master : {why}")
    return found


def prepare(state: dict, script_text: str, media: Path) -> Publication:
    found = problems(state, media)
    if found:
        raise PublishError("\n".join(found))
    fields, _body = frontmatter.split(script_text)
    outputs = state["steps"]["master"]["outputs"]
    return Publication(caption(str(fields["titre"])), {name: store.path(media, outputs[name]) for name in FILES})


def link(source: Path, target: Path) -> None:
    """A hard link to the stored file (same file system), or a copy when the link is refused."""
    target.unlink(missing_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def write(publication: Publication, media: Path, video_id: str) -> Path:
    folder = media / FOLDER / video_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, source in publication.sources.items():
        link(source, folder / FILES[name])
    (folder / CAPTION_NAME).write_text(publication.caption, encoding="utf-8")
    return folder
