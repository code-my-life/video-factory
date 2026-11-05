"""The studio board (#7): a card per video follows its stations and its state.json, the owner acts once at each station
that waits for him, the code lanes call vf and never a model, and only studio-writer drafts a script."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from video_factory import store, videos
from video_factory.paths import SCRIPT_TEMPLATE, SCRIPT_VITRINE_TEMPLATE, Places
from video_factory.studio import notify, writer
from video_factory.studio.board import Board, card_of
from video_factory.studio.lanes import Jobs, Studio
from video_factory.studio.stations import (
    BY_KEY,
    STATIONS,
    Card,
    Comment,
    Event,
    Facts,
    decide,
    load_manifest,
    owner_answer,
    station_from_state,
)

NOW = "2026-11-04T14:00:00Z"
SPOKEN = " ".join(["Chaque", "idée", "devient", "une", "vidéo", "sur", "le", "board", "du", "studio."] * 16)


def script_for(video_id: str, spoken: str = SPOKEN) -> str:
    return f'---\nid: "{video_id}"\ntitre: "Le board du studio"\nplateforme: tiktok\nduree_visee: 63\n---\n\n{spoken}\n'


def done(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeVf:
    """`vf` as the lanes call it: new, ingest and run write what the real commands write in state.json."""

    def __init__(self, places: Places, board, fail_run: bool = False) -> None:
        self.places, self.board, self.fail_run = places, board, fail_run
        self.calls: list[list[str]] = []
        self.status_during_run: list[tuple[str, str]] = []

    def state_path(self, video_id: str) -> Path:
        return self.places.content / "videos" / video_id / videos.STATE_NAME

    def update(self, video_id: str, change) -> None:
        path = self.state_path(video_id)
        state = json.loads(path.read_text(encoding="utf-8"))
        change(state)
        path.write_text(json.dumps(state), encoding="utf-8")

    def ingest(self, state: dict, files: list[str]) -> None:
        """Takes as given, a showcase's voice after --voix, a capture after --capture <name>; then the ingest step."""
        media, takes = self.places.media, []
        while files:
            item = files.pop(0)
            if item == "--voix":
                state["voix"] = store.put(media, Path(files.pop(0)), "mp3", keep_source=True)
            elif item == "--capture":
                name, file = files.pop(0), Path(files.pop(0))
                found = store.put(media, file, "mp4", keep_source=True)
                state.setdefault("captures", {})[name] = found | {"kind": "video", "source_sha256": found["sha256"]}
            else:
                takes.append(store.put(media, Path(item), "mov", keep_source=True))
        if takes:
            state["takes"] = takes
        if takes or "voix" in state:
            state["steps"] = {"ingest": {}}

    def __call__(self, args: Sequence[str]) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        verb, video_id, *rest = args
        if verb == "new":
            videos.create(self.places.content, video_id, SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
        elif verb == "ingest":
            self.update(video_id, lambda state: self.ingest(state, list(rest)))
        elif verb == "run":
            self.status_during_run += [self.board.statuses(card) for card in self.board.tasks]
            if self.fail_run:
                return done(returncode=1, stderr="qc refuse le master")
            self.update(video_id, lambda state: state["steps"].update(qc={"summary": {"passed": True}}))
        return done()


class FakeWriter:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def __call__(self, argv: Sequence[str]) -> subprocess.CompletedProcess:
        assert argv[:5] == ["hermes", "-p", "studio-writer", "chat", "--oneshot"]
        self.prompts.append(argv[-1])
        return done(f"```markdown\n{self.answer}```\n")


@pytest.fixture
def places(tmp_path: Path) -> Places:
    content = tmp_path / "video-content"
    (content / ".git").mkdir(parents=True)
    (content / "idees.md").write_text("# Idées\n\n- Le board du studio\n", encoding="utf-8")
    return Places(content=content, media=tmp_path / "media", tools=tmp_path / "tools")


@pytest.fixture
def studio(places: Places, fake_board):
    sent: list[str] = []

    def send(text: str) -> bool:
        sent.append(text)
        return True

    made = Studio(
        board=fake_board,
        places=places,
        url="https://studio.example.ts.net:8448",
        vf=FakeVf(places, fake_board),
        send=send,
        ask_writer=FakeWriter(script_for("essai")),
        jobs=Jobs(background=False),
        log=lambda _line: None,
    )
    made.sent = sent
    return made


def take(tmp_path: Path, content: bytes = b"une prise") -> Path:
    path = tmp_path / "IMG_0001.MOV"
    path.write_bytes(content)
    return path


def station(board, card_id: str) -> str:
    card = board.card(card_id)
    return f"{card.station.key}/{card.status}"


def test_the_manifest_declares_the_eight_stations_and_lanes_that_are_not_profiles():
    manifest = load_manifest()
    assert [item.key for item in STATIONS] == [
        "idee",
        "script",
        "approbation",
        "tournage",
        "montage",
        "revue",
        "publication",
        "publiee",
    ]
    lanes = [item.lane for item in STATIONS if item.lane]
    assert len(set(lanes)) == 7
    assert all(lane.startswith("studio-") for lane in lanes)
    assert set(manifest["profiles"]) == {"studio-writer"}
    assert "studio-writer" not in lanes, "the dispatcher must never spawn the writer on its own"


def test_a_video_goes_from_idea_to_published_with_one_gesture_at_each_station_that_waits(studio, tmp_path):
    board = studio.board
    card = studio.open_card("essai", "présenter le board du studio")
    assert station(board, card) == "idee/ready"
    studio.tick()  # vf new
    assert station(board, card) == "script/ready"
    studio.tick()  # studio-writer drafts, code checks the draft
    assert station(board, card) == "approbation/scheduled"
    board.unblock(card)  # gesture 1: approve
    studio.tick()
    assert station(board, card) == "tournage/scheduled"
    assert studio.takes_received("essai", [take(tmp_path)]).returncode == 0  # gesture 2: the takes, from the page
    assert station(board, card) == "montage/ready"
    studio.tick()  # vf run
    assert station(board, card) == "revue/scheduled"
    board.unblock(card)  # gesture 3: the master is good
    studio.tick()
    assert station(board, card) == "publication/ready"
    studio.tick()  # vf publish
    assert station(board, card) == "publication/scheduled"
    board.unblock(card, "https://www.tiktok.com/@codemylife/video/1")  # gesture 4: posted by hand
    studio.tick()
    assert board.card(card).station.key == "publiee"
    assert [call for call in studio.vf.calls if call[0] != "ingest"] == [
        ["new", "essai"],
        ["run", "essai"],
        ["publish", "essai"],
    ]
    asked = [text.splitlines()[0] for text in studio.sent]
    assert asked == [
        "🎬 Studio · essai · Approbation",
        "🎬 Studio · essai · Tournage",
        "🎬 Studio · essai · Revue",
        "🎬 Studio · essai · Publication",
    ]
    assert all("https://studio.example.ts.net:8448/v/essai" in text for text in studio.sent)
    script = (studio.places.content / "videos" / "essai" / "script.md").read_text(encoding="utf-8")
    assert script == script_for("essai")


@pytest.mark.acceptance("une carte suit l'état de sa vidéo")
def test_a_card_follows_the_state_of_its_video(studio, places, tmp_path):
    board = studio.board
    # A video that already exists enters the board where its state.json says.
    assert station_from_state(Facts()) == "script"
    assert station_from_state(Facts(exists=True, script_is_template=False)) == "approbation"
    assert station_from_state(Facts(exists=True, script_is_template=False, takes=True)) == "montage"
    assert station_from_state(Facts(exists=True, takes=True, qc_passed=True)) == "revue"
    videos.create(places.content, "deja", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    (places.content / "videos" / "deja" / "script.md").write_text(script_for("deja"), encoding="utf-8")
    card = studio.open_card("deja", "")
    assert board.card(card).assignee == BY_KEY["approbation"].lane
    studio.tick()
    assert station(board, card) == "approbation/scheduled"
    board.unblock(card)
    studio.tick()
    assert station(board, card) == "tournage/scheduled"
    # Takes ingested from the command line, not from the page: the next pass sees them in state.json.
    studio.vf(["ingest", "deja", str(take(tmp_path))])
    studio.tick()
    assert station(board, card) == "montage/ready"
    # The owner unblocking Tournage without any take keeps the card there, and says why.
    videos.create(places.content, "autre", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    (places.content / "videos" / "autre" / "script.md").write_text(script_for("autre"), encoding="utf-8")
    other = studio.open_card("autre", "")
    studio.tick()
    board.unblock(other)
    studio.tick()
    board.unblock(other)
    studio.tick()
    assert station(board, other) == "tournage/scheduled"
    assert "aucune prise versée" in studio.sent[-1]


def test_refaire_sends_the_video_back_with_the_owners_words(studio):
    board = studio.board
    card = studio.open_card("essai", "présenter le board")
    studio.tick()
    studio.tick()
    board.unblock(card, "refaire : plus court, une seule capture")
    studio.tick()
    assert station(board, card) == "script/ready"
    studio.tick()
    assert station(board, card) == "approbation/scheduled"
    assert "plus court, une seule capture" in studio.ask_writer.prompts[-1]
    assert "plus court" not in studio.ask_writer.prompts[0]


@pytest.mark.acceptance("la voie Montage n'appelle aucun modèle")
def test_the_montage_lane_calls_no_model(studio, tmp_path):
    board = studio.board
    card = studio.open_card("essai", "présenter le board")
    studio.tick()
    studio.tick()
    board.unblock(card)
    studio.tick()
    studio.takes_received("essai", [take(tmp_path)])
    prompts, calls = len(studio.ask_writer.prompts), len(board.calls)

    def no_model(argv):
        raise AssertionError(f"a model was asked during Montage: {argv}")

    studio.ask_writer = no_model
    studio.tick()
    assert station(board, card) == "revue/scheduled"
    assert studio.vf.calls[-1] == ["run", "essai"]
    assert prompts == 1
    montage = board.calls[calls:]
    assert not any(call[0] == "claim" for call in montage), "a Montage card never runs: no dispatch slot, no GPU"
    assert studio.vf.status_during_run == [("studio-montage", "ready")]


def test_a_failed_montage_waits_at_montage_and_an_unblock_retries(studio, tmp_path):
    board = studio.board
    studio.vf.fail_run = True
    card = studio.open_card("essai", "x")
    studio.tick()
    studio.tick()
    board.unblock(card)
    studio.tick()
    studio.takes_received("essai", [take(tmp_path)])
    studio.tick()
    assert station(board, card) == "montage/scheduled"
    assert "Montage en échec : qc refuse le master" in studio.sent[-1]
    studio.vf.fail_run = False
    board.unblock(card)
    studio.tick()
    assert station(board, card) == "revue/scheduled"


def test_a_draft_that_breaks_a_rule_is_refused_and_the_script_is_kept(studio, places):
    studio.ask_writer = FakeWriter(script_for("essai", "Trop court."))
    card = studio.open_card("essai", "x")
    studio.tick()
    before = (places.content / "videos" / "essai" / "script.md").read_text(encoding="utf-8")
    studio.tick()
    assert station(studio.board, card) == "script/scheduled"
    assert "2 mots, attendu de 140 à 190" in studio.sent[-1]
    assert (places.content / "videos" / "essai" / "script.md").read_text(encoding="utf-8") == before


def test_writer_rules():
    assert writer.problems(script_for("essai"), "essai") == []
    assert writer.problems(script_for("autre"), "essai") == ["id : « autre » au lieu de « essai », le nom du dossier"]
    assert writer.problems(script_for("essai", SPOKEN + " \u2014 oui"), "essai") == ["tiret cadratin dans le brouillon"]
    alone = script_for("essai", "[etapes: un | deux]\n" + SPOKEN)
    assert writer.problems(alone, "essai") == ["texte dit : ligne 8 : une annotation sans texte dit"]
    assert writer.extract("Voici :\n```markdown\n" + script_for("essai") + "---\n```") == script_for("essai")


def test_owner_answer_is_the_unblock_since_the_card_arrived():
    arrived = (Event("created", {}, 1), Event("assigned", {"assignee": "studio-revue"}, 5))
    parked = (*arrived, Event("scheduled", {}, 6))
    assert owner_answer(Card("t", "essai : x", "scheduled", "studio-revue", parked)) is None
    old = (Event("created", {}, 1), Event("unblocked", {}, 2), *arrived[1:])
    assert owner_answer(Card("t", "essai : x", "ready", "studio-revue", old)) is None
    answered = Card(
        "t",
        "essai : x",
        "ready",
        "studio-revue",
        (*parked, Event("unblocked", {}, 7)),
        (Comment("user", "UNBLOCK: refaire : le son", 7), Comment("user", "UNBLOCK: avant", 2)),
    )
    assert owner_answer(answered) == "refaire : le son"
    assert decide(answered, Facts(exists=True)).to == "montage"


def test_a_card_that_is_not_a_studio_lane_or_not_a_video_is_left_alone():
    assert decide(Card("t", "essai : x", "ready", "coordinator"), Facts()).action == "wait"
    assert decide(Card("t", "Pas une vidéo", "ready", "studio-idee"), Facts()).action == "wait"
    assert decide(Card("t", "essai : x", "running", "studio-script"), Facts()).action == "wait"


def test_the_message_names_the_page_and_the_telegram_command():
    text = notify.message("revue", "essai", "t_1234", "https://h.ts.net:8448/")
    assert text.splitlines() == [
        "🎬 Studio · essai · Revue",
        notify.ASK["revue"],
        "Page : https://h.ts.net:8448/v/essai",
        "/kanban --board studio unblock t_1234",
        '/kanban --board studio unblock t_1234 --reason "refaire : ce qui change"  (refaire le montage)',
    ]
    assert notify.telegram_target({"TELEGRAM_CHAT_ID": "42"}, Path("/nowhere")) == "telegram:42"
    assert notify.telegram_target({}, Path("/nowhere")) == "telegram"


def test_the_board_is_driven_through_the_hermes_cli_on_the_studio_board():
    seen: list[list[str]] = []

    def run(argv):
        seen.append(list(argv))
        return done("{}")

    board = Board(hermes="hermes", run=run)
    board.unblock("t_1", "refaire : x")
    board.schedule("t_1", "attente")
    assert seen == [
        ["hermes", "kanban", "--board", "studio", "unblock", "t_1", "--reason", "refaire : x"],
        ["hermes", "kanban", "--board", "studio", "schedule", "t_1", "attente"],
    ]
    shown = {
        "task": {"id": "t_1", "title": "essai : x", "status": "ready", "assignee": "studio-tournage"},
        "comments": [{"author": "default", "body": "UNBLOCK: ok", "created_at": 9}],
        "events": [{"kind": "assigned", "payload": {"assignee": "studio-tournage"}, "created_at": 8}],
    }
    card = card_of(shown)
    assert (card.video, card.station.key, card.events[0].kind, card.comments[0].body) == (
        "essai",
        "tournage",
        "assigned",
        "UNBLOCK: ok",
    )


def test_a_failed_command_is_reported_from_its_own_last_message():
    from video_factory.studio.lanes import tail

    noisy = done(returncode=1, stderr="INFO: delegate\nvf run : qc refuse le master\n  durée : 6,00 s\n")
    assert tail(noisy) == "vf run : qc refuse le master durée : 6,00 s"
    assert tail(done(returncode=1, stderr="Traceback\nboom")) == "Traceback boom"


@pytest.mark.acceptance("une vitrine passe du Tournage au Montage quand sa voix et ses rushs sont rangés")
def test_a_showcase_goes_from_shooting_to_montage_once_its_voice_and_its_rushes_are_stored(studio, tmp_path):
    board = studio.board
    folder = videos.create(studio.places.content, "vitrine", SCRIPT_VITRINE_TEMPLATE.read_text(encoding="utf-8"), NOW)
    lines = "Coucou. [plan: plan1 | durée 30]\nÀ bientôt. [plan: rush-pr | durée 32]\n"
    (folder / "script.md").write_text((folder / "script.md").read_text(encoding="utf-8") + lines, encoding="utf-8")
    card = studio.open_card("vitrine", "")
    studio.tick()  # the written script waits for the owner's approval
    assert station(board, card) == "approbation/scheduled"
    board.unblock(card)
    studio.tick()
    assert station(board, card) == "tournage/scheduled"
    files = {name: tmp_path / name for name in ("voix.mp3", "000-plan1.mp4", "001-rush-pr.mp4")}
    for name, path in files.items():
        path.write_bytes(name.encode())
    # The voice alone: the rushes the script shows are still missing, the card waits.
    assert studio.takes_received("vitrine", [files["voix.mp3"]]).returncode == 0
    assert studio.vf.calls[-1] == ["ingest", "vitrine", "--voix", str(files["voix.mp3"])]
    assert station(board, card) == "tournage/scheduled"
    # The rushes, each stored under the name of its file: the video is shot, the card goes to Montage.
    assert studio.takes_received("vitrine", [files["000-plan1.mp4"], files["001-rush-pr.mp4"]]).returncode == 0
    assert studio.vf.calls[-1][2:] == ["--capture", "plan1", str(files["000-plan1.mp4"]), "--capture", "rush-pr",
                                       str(files["001-rush-pr.mp4"])]  # fmt: skip
    assert station(board, card) == "montage/ready"
