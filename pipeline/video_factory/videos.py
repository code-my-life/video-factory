"""`vf new <id>`: a new video in the content clone, its script from the template and its state at schema version 2.

The files are built by pure functions, checked against the published schemas, and written only when both are valid;
an existing id is refused, so a video is never overwritten.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from video_factory import frontmatter, schemas
from video_factory.hashing import sha256_bytes
from video_factory.paths import SCRIPT_SCHEMA, STATE_SCHEMA
from video_factory.state import VERSION as STATE_VERSION

ID_FIELD = "{{id}}"
SCRIPT_NAME = "script.md"
STATE_NAME = "state.json"


class VideoError(Exception):
    """The video cannot be created; nothing was written."""


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def script_text(template: str, video_id: str) -> str:
    return template.replace(ID_FIELD, video_id)


def new_state(video_id: str, script_sha256: str, created_at: str) -> dict:
    """The state of a video nothing has been done to yet: its script's fingerprint, no take, no capture, no step."""
    return {
        "schema_version": STATE_VERSION,
        "id": video_id,
        "created_at": created_at,
        "script": {"path": SCRIPT_NAME, "sha256": script_sha256},
        "takes": [],
        "captures": {},
        "steps": {},
    }


def state_text(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def script_problems(text: str, video_id: str, schema_path: Path = SCRIPT_SCHEMA) -> list[str]:
    """What is wrong with a script.md text: its front matter against the schema, and its id against the folder."""
    try:
        fields, _body = frontmatter.split(text)
    except frontmatter.FrontMatterError as exc:
        return [f"en-tête : {exc}"]
    found = schemas.problems(fields, schema_path)
    if fields.get("id") != video_id:
        found.append(f"id : « {fields.get('id')} » au lieu de « {video_id} », le nom du dossier")
    return found


def build(video_id: str, template: str, created_at: str) -> tuple[str, str]:
    """(script.md, state.json) texts for a new video, both checked against their schemas."""
    if schemas.def_problems(video_id, STATE_SCHEMA, "video_id"):
        raise VideoError(f"id « {video_id} » refusé : minuscules, chiffres et tirets, 64 caractères au plus")
    script = script_text(template, video_id)
    found = script_problems(script, video_id)
    if found:
        raise VideoError("le gabarit donne un script invalide :\n" + "\n".join(f"- {line}" for line in found))
    state = new_state(video_id, sha256_bytes(script.encode()), created_at)
    found = schemas.problems(state, STATE_SCHEMA)
    if found:
        raise VideoError("état invalide :\n" + "\n".join(f"- {line}" for line in found))
    return script, state_text(state)


def create(content_root: Path, video_id: str, template: str, created_at: str) -> Path:
    """Write videos/<id>/script.md and state.json in the content clone; refuse an id that already exists."""
    if not (content_root / ".git").exists():
        raise VideoError(f"dépôt de contenu introuvable : {content_root} (variable VF_CONTENT)")
    script, state = build(video_id, template, created_at)
    folder = content_root / "videos" / video_id
    if folder.exists():
        raise VideoError(f"la vidéo « {video_id} » existe déjà : {folder}")
    folder.parent.mkdir(parents=True, exist_ok=True)
    staged = folder.with_name(f".{video_id}.new")
    try:
        staged.mkdir()
    except FileExistsError as exc:
        raise VideoError(f"création de « {video_id} » déjà en cours ou interrompue : {staged}") from exc
    try:
        (staged / SCRIPT_NAME).write_text(script, encoding="utf-8")
        (staged / STATE_NAME).write_text(state, encoding="utf-8")
        staged.rename(folder)
    except OSError as exc:
        raise VideoError(f"la vidéo « {video_id} » n'a pas pu être écrite dans {folder} : {exc}") from exc
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    return folder
