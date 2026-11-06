"""The stations of a video on the studio board, and the decision of what comes next, as pure functions.

A card's station is its assignee: one lane name per station, none of them a profile the dispatcher may spawn. Its
status says whether it waits: `scheduled` while the owner has to act (or after a failed lane, until the owner retries),
`ready` when a lane has work or the owner has just answered with an unblock, `running` only while `studio-writer`
writes a draft, `done` once published. A card never runs while it waits for a person or for `vf run`, so it neither
holds a dispatch slot nor keeps the local model loaded.

The owner answers by unblocking the card, from Telegram (`/kanban --board studio unblock <card>`) or from the page;
a reason starting with « refaire » sends the video back to the station before.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from video_factory import script, vitrine
from video_factory.paths import REPO_ROOT

MANIFEST = REPO_ROOT / "hermes" / "manifest.json"
TITLE = re.compile(r"^(?P<id>[a-z0-9]+(?:-[a-z0-9]+)*) : (?P<idea>.+)$", re.DOTALL)
UNBLOCK_PREFIX = "UNBLOCK:"
READY_TO_POST = "Prête à publier"
REDO = "refaire"
REDO_NOTE = "Demande du propriétaire : "


@dataclass(frozen=True)
class Station:
    key: str
    label: str
    lane: str | None
    kind: str  # « code », « writer », « owner » or « end »


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stations(manifest: dict) -> tuple[Station, ...]:
    return tuple(Station(item["key"], item["label"], item["lane"], item["kind"]) for item in manifest["stations"])


STATIONS = stations(load_manifest())
BY_KEY = {station.key: station for station in STATIONS}
BY_LANE = {station.lane: station for station in STATIONS if station.lane}


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict
    at: int


@dataclass(frozen=True)
class Comment:
    author: str
    body: str
    at: int


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    status: str
    assignee: str | None
    events: tuple[Event, ...] = ()
    comments: tuple[Comment, ...] = ()

    @property
    def video(self) -> str | None:
        found = TITLE.match(self.title)
        return found["id"] if found else None

    @property
    def station(self) -> Station | None:
        if self.status == "done":
            return BY_KEY["publiee"]
        return BY_LANE.get(self.assignee or "")


@dataclass(frozen=True)
class Facts:
    """What the state of a video says, as far as the board cares."""

    exists: bool = False
    script_is_template: bool = True
    takes: bool = False
    qc_passed: bool = False


@dataclass(frozen=True)
class Plan:
    """What to do with a card: « wait », « work » (job), « move » (to, park), « park » or « complete »."""

    action: str
    to: str | None = None
    park: bool = False
    job: str | None = None
    note: str = ""
    extra: dict = field(default_factory=dict)


WAIT = Plan("wait")


def showcase_shot(state: dict, script_text: str) -> bool:
    """A showcase is shot when its voice is stored and every capture its script shows is too."""
    try:
        names = vitrine.captures(vitrine.parse(script_text))
    except ValueError:
        return False
    return "voix" in state and all(name in state.get("captures", {}) for name in names)


def facts_of(state: dict | None, script_is_template: bool, script_text: str = "") -> Facts:
    """The board's view of a state.json (None when the video does not exist yet) and of its script: the takes of a
    face camera video, or the voice and the captures of a showcase, stored and ingested."""
    if state is None:
        return Facts()
    steps = state.get("steps", {})
    qc = steps.get("qc", {}).get("summary", {})
    try:
        showcase = bool(script_text) and script.genre_of(script_text) == script.VITRINE
    except ValueError:
        showcase = False
    shot = showcase_shot(state, script_text) if showcase else bool(state.get("takes"))
    return Facts(
        exists=True,
        script_is_template=script_is_template,
        takes=shot and "ingest" in steps,
        qc_passed=bool(qc.get("passed")),
    )


def station_from_state(facts: Facts) -> str:
    """Where a video that already exists enters the board: the furthest station its state proves."""
    if facts.qc_passed:
        return "revue"
    if facts.takes:
        return "montage"
    if facts.exists and not facts.script_is_template:
        return "approbation"
    return "script"


def since_arrival(card: Card) -> tuple[Event, ...]:
    """The events after the card reached its current station (its last assignment, or its creation)."""
    last = 0
    for index, event in enumerate(card.events):
        if event.kind in ("assigned", "created"):
            last = index
    return card.events[last + 1 :]


def arrival_time(card: Card) -> int:
    times = [event.at for event in card.events if event.kind in ("assigned", "created")]
    return times[-1] if times else 0


def owner_answer(card: Card) -> str | None:
    """The owner's answer at this station: None while the card was not unblocked since it arrived, else the reason
    given with the unblock (empty when none)."""
    if not any(event.kind == "unblocked" for event in since_arrival(card)):
        return None
    since = arrival_time(card)
    reasons = [
        comment.body[len(UNBLOCK_PREFIX) :].strip()
        for comment in card.comments
        if comment.body.startswith(UNBLOCK_PREFIX) and comment.at >= since
    ]
    return reasons[-1] if reasons else ""


def plain(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(char for char in folded if not unicodedata.combining(char))


def wants_redo(answer: str) -> bool:
    return plain(answer).startswith(REDO)


def redo_request(card: Card) -> str:
    """What the owner asked when he sent the video back to this station, from the note left on arrival."""
    since = arrival_time(card)
    notes = [c.body[len(REDO_NOTE) :] for c in card.comments if c.body.startswith(REDO_NOTE) and c.at >= since]
    return notes[-1] if notes else ""


def last_park(card: Card) -> str | None:
    """The reason of the last time the card was parked at its station, if it was."""
    parked = [event for event in since_arrival(card) if event.kind == "scheduled"]
    return str(parked[-1].payload.get("reason") or "") if parked else None


def decide(card: Card, facts: Facts) -> Plan:
    """The next move of a card, from its station, its status, its events and the state of its video."""
    station = card.station
    if station is None or card.video is None or card.status not in ("ready", "scheduled"):
        return WAIT
    if station.key == "tournage" and facts.takes:
        return Plan("move", to="montage", note="prises versées")
    if card.status == "scheduled":
        return WAIT
    answer = owner_answer(card)
    if station.key == "idee":
        if not facts.exists:
            return Plan("work", job="new")
        if facts.script_is_template:
            return Plan("move", to="script")
        target = station_from_state(facts)
        return Plan("move", to=target, park=BY_KEY[target].kind == "owner")
    if station.key == "script":
        return Plan("work", job="write", note=redo_request(card))
    if station.key == "montage":
        return Plan("work", job="montage")
    if station.key == "publication":
        if answer is not None and (last_park(card) or "").startswith(READY_TO_POST):
            return Plan("complete", note=answer)
        return Plan("work", job="publish")
    return owner_station(station.key, answer)


def owner_station(key: str, answer: str | None) -> Plan:
    if answer is None:
        return Plan("park")
    if key == "tournage":
        return Plan("park", note="aucune prise versée : les envoyer par la page")
    back, forward = {"approbation": ("script", "tournage"), "revue": ("montage", "publication")}[key]
    if wants_redo(answer):
        return Plan("move", to=back, note=answer)
    return Plan("move", to=forward, park=BY_KEY[forward].kind == "owner")
