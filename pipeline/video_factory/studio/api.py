"""The studio's generic workflow API, version 1 (#21): what factory-live reads to draw and follow the studio with its
standard graph, without knowing the media store or `state.json` (factory-live#29, #30, #31).

- the sheet: `hermes/workflow.json`, in factory-live's `WorkflowSheet` format, checked here by the same rules;
- the items: one per card, its station and how it stands (running, waiting for the owner, failed, done);
- an item's detail: its script, the steps of `vf run` and its typed files (video, words);
- the words: the master's captions, each said word in output time, kept from the script or not;
- the gesture: the owner's « ok » or « refaire », the same unblock as the page and Telegram.

Everything here is read from the board and the content clone; nothing is written but by the gesture.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from video_factory import frontmatter, videos
from video_factory.paths import REPO_ROOT
from video_factory.studio.lanes import Studio
from video_factory.studio.stations import Card, arrival_time, last_park

API_VERSION = 1
SHEET = REPO_ROOT / "hermes" / "workflow.json"
KINDS = ("ai", "script", "github", "owner", "end")
EDGE_KINDS = ("line", "return", "branch", "fan")
MODELS_KEY = "models"
FAILED = " en échec"
# The master's files factory-live plays, and their frame rate (`compose.FPS`).
VIDEOS = ("master", "tiktok")
FPS = 30
DECISIONS = ("ok", "refaire")


class ApiError(Exception):
    """A request the API refuses: what was asked does not exist, or cannot be done."""


# --- the sheet --------------------------------------------------------------------------------------------------------


def sheet_problem(sheet: dict) -> str | None:
    """The first rule of factory-live's `WorkflowSheet` (`packages/contracts/src/workflow.ts`) the sheet breaks."""
    if not isinstance(sheet.get("item"), dict) or not sheet["item"].get("type"):
        return "item : type manquant"
    groups = {group["key"] for group in sheet.get("groups", [])}
    stations: dict[str, dict] = {}
    cells: dict[tuple[int, int], str] = {}
    for station in sheet.get("stations", []):
        key = station.get("key")
        if not key or key == MODELS_KEY:
            return f"station sans clé ou de clé réservée : {key!r}"
        if key in stations:
            return f"station en double : {key}"
        if station.get("kind") not in KINDS:
            return f"station {key} : nature inconnue {station.get('kind')!r}"
        cell = (station.get("col"), station.get("row"))
        if not all(isinstance(value, int) and value >= 0 for value in cell):
            return f"station {key} : case invalide {cell}"
        if cell in cells:
            return f"stations {cells[cell]} et {key} sur la même case {cell}"
        cells[cell] = key
        stations[key] = station
    for edge in sheet.get("edges", []):
        if edge.get("kind") not in EDGE_KINDS:
            return f"lien {edge} : nature inconnue"
        for end in ("from", "to"):
            if edge.get(end) not in stations and edge.get(end) not in groups:
                return f"lien {edge.get('from')} -> {edge.get('to')} : station inconnue {edge.get(end)!r}"
    for key in sheet.get("models", []):
        if key not in stations:
            return f"models : station inconnue {key}"
    return None


def load_sheet(path: Path = SHEET) -> dict:
    sheet = json.loads(path.read_text(encoding="utf-8"))
    problem = sheet_problem(sheet)
    if problem:
        raise ApiError(f"fiche du workflow invalide : {problem}")
    return sheet


# --- the items --------------------------------------------------------------------------------------------------------


def iso(seconds: int) -> str | None:
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if seconds else None


def standing(card: Card) -> tuple[str, str | None]:
    """How a card stands for factory-live, and what it waits for or why it failed."""
    if card.status == "done":
        return "done", None
    if card.status == "running" or card.status == "ready":
        return "running", None
    parked = last_park(card) or ""
    if FAILED in parked:
        return "failed", parked
    return "waiting", parked or None


def script_title(studio: Studio, video_id: str) -> str:
    try:
        text = (studio.folder(video_id) / videos.SCRIPT_NAME).read_text(encoding="utf-8")
        return str(frontmatter.split(text)[0].get("titre") or video_id)
    except (OSError, frontmatter.FrontMatterError):
        return video_id


def summary(studio: Studio, card: Card) -> dict:
    state, note = standing(card)
    video_id = card.video or ""
    return {
        "id": video_id,
        "card": card.id,
        "title": script_title(studio, video_id),
        "station": card.station.key if card.station else None,
        "state": state,
        "since": iso(arrival_time(card)),
        "waits": note if state == "waiting" else None,
        "failure": note if state == "failed" else None,
    }


def items(studio: Studio) -> list[dict]:
    """One entry per card of a video, open or published, read with its events."""
    found = []
    for task in studio.board.listing():
        card = Card(task["id"], task.get("title") or "", task.get("status") or "", task.get("assignee"))
        if card.video is None or card.station is None:
            continue
        found.append(summary(studio, studio.board.card(card.id)))
    return found


def card_of(studio: Studio, video_id: str) -> Card:
    for task in studio.board.listing():
        card = Card(task["id"], task.get("title") or "", task.get("status") or "", task.get("assignee"))
        if card.video == video_id:
            return studio.board.card(card.id)
    raise ApiError(f"aucune carte pour la vidéo « {video_id} »")


def read_state(studio: Studio, video_id: str) -> dict:
    try:
        return json.loads((studio.folder(video_id) / videos.STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def files_of(video_id: str, steps: dict) -> list[dict]:
    """The typed files factory-live can show: the master's videos once made, and their words once composed."""
    found = [
        {"kind": "video", "name": name, "url": f"/v/{video_id}/media/{name}", "fps": FPS}
        for name in VIDEOS
        if name in steps.get("master", {}).get("outputs", {})
    ]
    if "plan" in steps.get("compose", {}).get("outputs", {}):
        found.append({"kind": "words", "name": "words", "url": f"/api/items/{video_id}/words", "follows": "master"})
    return found


def detail(studio: Studio, video_id: str) -> dict:
    card = card_of(studio, video_id)
    state = read_state(studio, video_id)
    steps = state.get("steps", {})
    try:
        script = (studio.folder(video_id) / videos.SCRIPT_NAME).read_text(encoding="utf-8")
    except OSError:
        script = None
    return summary(studio, card) | {
        "script": script,
        "steps": [
            {
                "name": name,
                "status": "done",
                "seconds": step.get("seconds"),
                "outputs": {key: ref.get("sha256") for key, ref in step.get("outputs", {}).items()},
            }
            for name, step in steps.items()
        ],
        "files": files_of(video_id, steps),
    }


def stored_json(studio: Studio, steps: dict, step: str, name: str) -> dict:
    ref = steps.get(step, {}).get("outputs", {}).get(name)
    if not ref:
        raise ApiError(f"pas encore de sortie « {name} » de l'étape {step}")
    return json.loads((studio.places.media / ref["file"]).read_text(encoding="utf-8"))


def words(studio: Studio, video_id: str) -> list[dict]:
    """The master's words in output time (seconds): each one as the captions show it, kept from the script or said
    outside it. `compose` wrote them in frames from `cut`'s list, in the same order."""
    steps = read_state(studio, video_id).get("steps", {})
    plan = stored_json(studio, steps, "compose", "plan")
    labels = [word["label"] for word in stored_json(studio, steps, "cut", "edl")["words"]]
    return [
        {
            "mot": word["text"],
            "debut": round(word["start"] / FPS, 3),
            "fin": round(word["end"] / FPS, 3),
            "garde": index < len(labels) and labels[index] == "kept",
        }
        for index, word in enumerate(plan["words"])
    ]


def gesture(studio: Studio, video_id: str, decision: str, note: str = "") -> Card:
    """The owner's gesture: « ok » or « refaire » with a reason, the same unblock as the page and Telegram."""
    if decision not in DECISIONS:
        raise ApiError(f"décision inconnue « {decision} » : ok ou refaire")
    note = note.strip()
    return studio.answer(video_id, f"{decision} : {note}" if note else decision)
