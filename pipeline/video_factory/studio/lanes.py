"""The studio's runner: each pass reads the board, decides every card's next move (stations.decide) and carries it out.

The code lanes call `vf` and nothing else: Idée runs `vf new`, Montage `vf run`, Publication `vf publish`. Only the
Script station calls a model, through the `studio-writer` profile, and only it claims its card while it works, so the
local model stays loaded for the draft and is released by vram-release as soon as no card runs. Long jobs run one at
a time beside the passes, so an answer of the owner is acted on while a master renders.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from video_factory import script, videos
from video_factory.paths import REPO_ROOT, SCRIPT_TEMPLATE, SCRIPT_VITRINE_TEMPLATE, Places
from video_factory.studio import notify, writer
from video_factory.studio.board import Board, BoardError
from video_factory.studio.stations import (
    BY_KEY,
    READY_TO_POST,
    REDO_NOTE,
    TITLE,
    Card,
    Facts,
    Plan,
    decide,
    facts_of,
    station_from_state,
    wants_redo,
)

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


def run_vf(args: Sequence[str]) -> subprocess.CompletedProcess:
    """`vf <args>` with the interpreter that runs the studio, from the checkout, with the same environment."""
    return subprocess.run(
        [sys.executable, "-m", "video_factory.cli", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def tail(done: subprocess.CompletedProcess, size: int = 400) -> str:
    """What a failed command said, from its last line of its own (« vf … ») when it has one, on a single line."""
    lines = (done.stderr or done.stdout or "").splitlines()
    own = [index for index, line in enumerate(lines) if line.startswith("vf ")]
    kept = lines[own[-1] :] if own else lines
    return " ".join(" ".join(kept).split())[-size:]


class Jobs:
    """One long job at a time, in the background (or inline, for tests); a card is never queued twice."""

    def __init__(self, background: bool = True) -> None:
        self.pool = ThreadPoolExecutor(max_workers=1) if background else None
        self.busy: set[str] = set()
        self.guard = threading.Lock()

    def submit(self, key: str, job: Callable[[], None]) -> bool:
        with self.guard:
            if key in self.busy:
                return False
            self.busy.add(key)

        def done() -> None:
            try:
                job()
            finally:
                with self.guard:
                    self.busy.discard(key)

        if self.pool is None:
            done()
        else:
            self.pool.submit(done)
        return True


# The audio files a showcase's voice may come in; any other received file is a capture.
AUDIO = frozenset({"mp3", "wav", "m4a", "aac", "flac", "ogg", "opus"})


def capture_name(file: Path) -> str:
    """The capture a received file is stored as: its name as sent, without its rank (« 001-plan1.mp4 » is « plan1 »)."""
    stem = file.stem.split("-", 1)[1] if re.match(r"^\d{3}-", file.stem) else file.stem
    return stem or file.stem


@dataclass
class Studio:
    board: Board
    places: Places
    url: str
    vf: Runner = run_vf
    send: Callable[[str], bool] = lambda _text: True
    ask_writer: Runner | None = None
    brand: Path | None = None
    claim_ttl: int = 1800
    jobs: Jobs = field(default_factory=Jobs)
    lock: threading.RLock = field(default_factory=threading.RLock)
    log: Callable[[str], None] = print

    # --- what the content clone says -------------------------------------------------------------------------------

    def folder(self, video_id: str) -> Path:
        return self.places.content / "videos" / video_id

    def template(self, video_id: str) -> str:
        return videos.script_text(SCRIPT_TEMPLATE.read_text(encoding="utf-8"), video_id)

    def templates(self, video_id: str) -> tuple[str, ...]:
        """The scripts `vf new` writes for this id, face camera and showcase: a script equal to one is unwritten."""
        showcase = videos.script_text(SCRIPT_VITRINE_TEMPLATE.read_text(encoding="utf-8"), video_id)
        return (self.template(video_id), showcase)

    def is_showcase(self, video_id: str) -> bool:
        try:
            text = (self.folder(video_id) / videos.SCRIPT_NAME).read_text(encoding="utf-8")
            return script.genre_of(text) == script.VITRINE
        except (OSError, ValueError):
            return False

    def facts(self, video_id: str) -> Facts:
        folder = self.folder(video_id)
        try:
            state = json.loads((folder / videos.STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return Facts()
        try:
            script = (folder / videos.SCRIPT_NAME).read_text(encoding="utf-8")
        except OSError:
            script = ""
        return facts_of(state, script in self.templates(video_id), script)

    # --- the passes ---------------------------------------------------------------------------------------------------

    def cards(self) -> list[Card]:
        """The open cards of the board; only a card a lane may act on is read with its events."""
        found = []
        for task in self.board.listing():
            card = Card(task["id"], task.get("title") or "", task.get("status") or "", task.get("assignee"))
            if card.station is None or card.video is None or card.status not in ("ready", "scheduled"):
                continue
            found.append(self.board.card(card.id) if card.status == "ready" else card)
        return found

    def tick(self) -> list[str]:
        done = []
        for card in self.cards():
            try:
                with self.lock:
                    plan = decide(card, self.facts(card.video or ""))
                    if plan.action != "wait" and self.apply(card, plan):
                        done.append(f"{card.id} {card.video} : {plan.action} {plan.to or plan.job or ''}".strip())
            except BoardError as exc:
                done.append(f"{card.id} : {exc}")
        for line in done:
            self.log(line)
        return done

    def apply(self, card: Card, plan: Plan) -> bool:
        """Carry the plan out; False when its job is already running for this card."""
        if plan.action == "move":
            self.move(card, plan.to or "", park=plan.park, note=plan.note)
        elif plan.action == "park":
            self.park(card.id, card.video or "", card.station.key, plan.note)
        elif plan.action == "complete":
            self.board.complete(card.id, f"Publiée. {plan.note}".strip())
        elif plan.action == "work":
            jobs = {"new": self.job_new, "write": self.job_write, "montage": self.job_montage}
            job = jobs.get(plan.job or "", self.job_publish)
            return self.jobs.submit(card.id, lambda: self.guarded(job, card, plan))
        return True

    def guarded(self, job: Callable[[Card, Plan], None], card: Card, plan: Plan) -> None:
        """A job that fails on the board is logged; the next pass decides again from what the board then says."""
        try:
            job(card, plan)
        except BoardError as exc:
            self.log(f"{card.id} {card.video} : {exc}")

    # --- moves --------------------------------------------------------------------------------------------------------

    def move(self, card: Card, to: str, *, park: bool = False, note: str = "") -> None:
        """Leave the station (an unblock, when parked), take the next lane, and park there if it waits for the owner."""
        if card.status == "scheduled":
            self.board.unblock(card.id)
        self.board.assign(card.id, BY_KEY[to].lane or "")
        if note and wants_redo(note):
            self.board.comment(card.id, REDO_NOTE + note)
        if park:
            self.park(card.id, card.video or "", to, note)

    def park(self, card_id: str, video_id: str, station: str, note: str = "", *, failed: bool = False) -> None:
        reason = f"{BY_KEY[station].label} en échec : {note}" if failed else (note or notify.ASK[station])
        self.board.schedule(card_id, reason)
        if not self.send(notify.message(station, video_id, card_id, self.url, note, failed=failed)):
            self.log(f"{card_id} : message Telegram non envoyé")

    def current(self, card: Card, station: str) -> Card | None:
        """The card as it is now, if it is still at that station and ready (the owner may have moved it)."""
        now = self.board.card(card.id)
        return now if now.station is not None and now.station.key == station and now.status == "ready" else None

    # --- the lanes ----------------------------------------------------------------------------------------------------

    def job_new(self, card: Card, _plan: Plan) -> None:
        done = self.vf(["new", card.video or ""])
        with self.lock:
            if self.current(card, "idee") is None:
                return
            if done.returncode != 0:
                self.park(card.id, card.video or "", "idee", tail(done), failed=True)
                return
            self.board.assign(card.id, BY_KEY["script"].lane or "")

    def brief(self, card: Card, redo: str) -> writer.Brief:
        video_id = card.video or ""
        found = TITLE.match(card.title)
        idea = found["idea"] if found else card.title

        def read(path: Path | None) -> str:
            try:
                return path.read_text(encoding="utf-8") if path else ""
            except OSError:
                return ""

        return writer.Brief(
            video_id=video_id,
            idea=idea,
            ideas=read(self.places.content / "idees.md"),
            brand=read(self.brand),
            template=self.template(video_id),
            current=read(self.folder(video_id) / videos.SCRIPT_NAME),
            redo=redo,
        )

    def job_write(self, card: Card, plan: Plan) -> None:
        with self.lock:
            if self.current(card, "script") is None:
                return
            self.board.claim(card.id, self.claim_ttl)
        try:
            if self.ask_writer is None:
                raise writer.WriterError("aucun profil studio-writer configuré")
            text = writer.draft(self.brief(card, plan.note), self.ask_writer)
            writer.write(self.folder(card.video or "") / videos.SCRIPT_NAME, text)
        except (writer.WriterError, OSError) as exc:
            with self.lock:
                self.park(card.id, card.video or "", "script", str(exc), failed=True)
            return
        with self.lock:
            self.board.schedule(card.id, "Brouillon écrit par studio-writer")
            self.board.assign(card.id, BY_KEY["approbation"].lane or "")
            self.park_notified(card, "approbation")

    def park_notified(self, card: Card, station: str) -> None:
        """Tell the owner about a card already parked (a running card is parked before it changes lanes)."""
        if not self.send(notify.message(station, card.video or "", card.id, self.url)):
            self.log(f"{card.id} : message Telegram non envoyé")

    def job_montage(self, card: Card, _plan: Plan) -> None:
        with self.lock:
            if self.current(card, "montage") is None:
                return
            self.board.comment(card.id, "Montage : vf run, sans modèle")
        done = self.vf(["run", card.video or ""])
        with self.lock:
            now = self.current(card, "montage")
            if now is None:
                return
            if done.returncode != 0:
                self.park(card.id, card.video or "", "montage", tail(done), failed=True)
                return
            self.move(now, "revue", park=True)

    def job_publish(self, card: Card, _plan: Plan) -> None:
        done = self.vf(["publish", card.video or ""])
        with self.lock:
            if self.current(card, "publication") is None:
                return
            if done.returncode != 0:
                self.park(card.id, card.video or "", "publication", tail(done), failed=True)
                return
            self.board.schedule(card.id, f"{READY_TO_POST} : fichiers et légende prêts")
            self.park_notified(card, "publication")

    # --- what the page asks for ---------------------------------------------------------------------------------------

    def open_card(self, video_id: str, idea: str) -> str:
        """The card of a video: a new idea starts at Idée, an existing video where its state says."""
        if TITLE.match(f"{video_id} : x") is None:
            raise BoardError(f"id « {video_id} » refusé : minuscules, chiffres et tirets")
        facts = self.facts(video_id)
        station = station_from_state(facts) if facts.exists else "idee"
        title = f"{video_id} : {idea.strip() or video_id}"
        body = f"Vidéo {video_id}, suivie par le board studio. Page : {self.url.rstrip('/')}/v/{video_id}"
        return self.board.create(title, BY_KEY[station].lane or "", body, f"studio:{video_id}")

    def card_of_video(self, video_id: str) -> Card | None:
        for task in self.board.listing():
            card = Card(task["id"], task.get("title") or "", task.get("status") or "", task.get("assignee"))
            if card.video == video_id and card.status != "done":
                return self.board.card(card.id)
        return None

    def answer(self, video_id: str, reason: str) -> Card:
        """The owner's gesture from the page: the same unblock as the Telegram command."""
        with self.lock:
            card = self.card_of_video(video_id)
            if card is None or card.status != "scheduled":
                raise BoardError(f"aucune carte de « {video_id} » n'attend de réponse")
            self.board.unblock(card.id, reason)
            return card

    def ingest_args(self, video_id: str, files: Sequence[Path]) -> list[str]:
        """What `vf ingest` gets from the received files: the takes of a face camera video; for a showcase, its voice
        (the audio file) and its captures, each under the name of its file (« plan1.mp4 » is the capture « plan1 »)."""
        if not self.is_showcase(video_id):
            return [str(file) for file in files]
        found: list[str] = []
        voices = [file for file in files if file.suffix.lower().lstrip(".") in AUDIO]
        if len(voices) > 1:
            raise BoardError(f"une seule voix par vitrine : {len(voices)} fichiers audio reçus")
        for file in files:
            if file in voices:
                found += ["--voix", str(file)]
            else:
                found += ["--capture", capture_name(file), str(file)]
        return found

    def takes_received(self, video_id: str, files: Sequence[Path]) -> subprocess.CompletedProcess:
        """`vf ingest` on the received files, then the card goes to Montage once the state proves the video shot: its
        takes, or a showcase's voice and every capture its script shows."""
        done = self.vf(["ingest", video_id, *self.ingest_args(video_id, files)])
        if done.returncode == 0:
            with self.lock:
                card = self.card_of_video(video_id)
                station = card.station if card is not None else None
                if station is not None and station.key == "tournage" and self.facts(video_id).takes:
                    self.move(card, "montage")
        return done
