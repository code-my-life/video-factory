"""The studio's generic workflow API (#21): the sheet factory-live draws, the items it follows, the words of a
master and the owner's gesture, all served by `vf studio serve` in JSON."""

from __future__ import annotations

import hashlib
import http.client
import json
import threading
from pathlib import Path

import pytest

from test_board import FakeVf
from video_factory import frontmatter, videos
from video_factory.paths import SCRIPT_TEMPLATE, Places
from video_factory.studio import api
from video_factory.studio.lanes import Jobs, Studio
from video_factory.studio.page import server
from video_factory.studio.stations import STATIONS, load_manifest

NOW = "2026-11-04T14:00:00Z"
# The manifest's kinds of work, as the sheet names them for factory-live.
KIND_OF = {"code": "script", "writer": "ai", "owner": "owner", "end": "end"}


@pytest.fixture
def served(tmp_path: Path, fake_board):
    content = tmp_path / "video-content"
    (content / ".git").mkdir(parents=True)
    places = Places(content=content, media=tmp_path / "media", tools=tmp_path / "tools")
    places.media.mkdir()
    studio = Studio(
        board=fake_board,
        places=places,
        url="https://studio.example.ts.net:8448",
        vf=FakeVf(places, fake_board),
        jobs=Jobs(background=False),
        log=lambda _line: None,
    )
    httpd = server(studio, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield studio, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def call(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = json.dumps(body).encode() if body is not None else b""
    connection.request(method, path, body=data, headers={"Content-Type": "application/json"})
    response = connection.getresponse()
    return response.status, json.loads(response.read() or b"{}")


def store(studio: Studio, document: dict) -> dict:
    """A JSON output put in the media store as a step would: named by its fingerprint."""
    data = json.dumps(document).encode()
    digest = hashlib.sha256(data).hexdigest()
    (studio.places.media / f"{digest}.json").write_bytes(data)
    return {"sha256": digest, "file": f"{digest}.json"}


def with_steps(studio: Studio, video_id: str, steps: dict) -> None:
    path = studio.folder(video_id) / videos.STATE_NAME
    state = json.loads(path.read_text(encoding="utf-8"))
    state["steps"] = steps
    path.write_text(json.dumps(state), encoding="utf-8")


@pytest.mark.acceptance("la fiche du studio suit le contrat de factory-live")
def test_the_studio_sheet_follows_factory_live_contract(served):
    _studio, port = served
    status, body = call(port, "GET", "/api/workflow")
    assert status == 200 and body["api"] == 1
    sheet = body["sheet"]
    assert api.sheet_problem(sheet) is None
    assert sheet["item"]["type"] == "video"
    # The eight stations of the board, in its order, each with the kind of work the manifest gives it.
    assert [(s["key"], s["kind"]) for s in sheet["stations"]] == [(s.key, KIND_OF[s.kind]) for s in STATIONS]
    assert [s["label"] for s in sheet["stations"]] == [s["label"] for s in load_manifest()["stations"]]
    returns = {(e["from"], e["to"]) for e in sheet["edges"] if e["kind"] == "return"}
    assert returns == {("approbation", "script"), ("revue", "montage")}
    assert sheet["models"] == ["script"]
    # The rules of factory-live's contract are the ones this API checks.
    broken = json.loads(json.dumps(sheet))
    broken["stations"][1]["col"], broken["stations"][1]["row"] = 0, 0
    assert "même case" in (api.sheet_problem(broken) or "")
    broken = json.loads(json.dumps(sheet))
    broken["edges"].append({"from": "revue", "to": "nulle-part", "kind": "line"})
    assert "station inconnue" in (api.sheet_problem(broken) or "")


@pytest.mark.acceptance("les vidéos et leurs étapes viennent de leur état et de leur carte")
def test_videos_and_their_steps_come_from_their_state_and_card(served, fake_board):
    studio, port = served
    script = SCRIPT_TEMPLATE.read_text(encoding="utf-8")
    videos.create(studio.places.content, "essai", script, NOW)
    videos.create(studio.places.content, "rendu", script, NOW)
    waiting = fake_board.create("essai : une prise", "studio-tournage", "", "studio:essai")
    fake_board.schedule(waiting, "Tourner les plans : envoyer les prises")
    failed = fake_board.create("rendu : un rendu", "studio-montage", "", "studio:rendu")
    fake_board.schedule(failed, "Montage en échec : compose refuse le projet")
    master = store(studio, {"fake": "mp4"})
    with_steps(studio, "rendu", {"ingest": {"seconds": 8.0, "outputs": {"work": master}}})

    status, body = call(port, "GET", "/api/items")
    assert status == 200
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["essai"] | {"since": None} == {
        "id": "essai",
        "card": waiting,
        "title": frontmatter.split(script)[0]["titre"],
        "station": "tournage",
        "state": "waiting",
        "since": None,
        "waits": "Tourner les plans : envoyer les prises",
        "failure": None,
    }
    assert by_id["rendu"]["state"] == "failed"
    assert by_id["rendu"]["failure"] == "Montage en échec : compose refuse le projet"

    status, detail = call(port, "GET", "/api/items/rendu")
    assert status == 200
    assert detail["script"] == (studio.folder("rendu") / videos.SCRIPT_NAME).read_text(encoding="utf-8")
    assert detail["steps"] == [
        {"name": "ingest", "status": "done", "seconds": 8.0, "outputs": {"work": master["sha256"]}}
    ]
    assert detail["files"] == []  # no master yet, so nothing to play
    assert call(port, "GET", "/api/items/inconnue")[0] == 404


@pytest.mark.acceptance("les mots calés d'une vidéo montée sont servis")
def test_the_words_of_a_composed_video_are_served(served, fake_board):
    studio, port = served
    videos.create(studio.places.content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    fake_board.create("essai : une vidéo montée", "studio-revue", "", "studio:essai")
    edl = store(studio, {"words": [{"label": "kept", "text": "bonjour"}, {"label": "off_script", "text": "euh"}]})
    plan = store(
        studio,
        {"words": [{"text": "Bonjour", "start": 0, "end": 15}, {"text": "euh", "start": 30, "end": 36}]},
    )
    master = store(studio, {"fake": "mp4"})
    with_steps(
        studio,
        "essai",
        {
            "cut": {"seconds": 1.0, "outputs": {"edl": edl}},
            "compose": {"seconds": 60.0, "outputs": {"plan": plan}},
            "master": {"seconds": 30.0, "outputs": {"master": master, "tiktok": master}},
        },
    )
    _status, detail = call(port, "GET", "/api/items/essai")
    assert [f["kind"] for f in detail["files"]] == ["video", "video", "words"]
    assert detail["files"][0] == {"kind": "video", "name": "master", "url": "/v/essai/media/master", "fps": 30}
    status, body = call(port, "GET", detail["files"][2]["url"])
    assert status == 200
    # Output time, in seconds, as the master shows them: the captions' frames at 30 per second.
    assert body["words"] == [
        {"mot": "Bonjour", "debut": 0.0, "fin": 0.5, "garde": True},
        {"mot": "euh", "debut": 1.0, "fin": 1.2, "garde": False},
    ]


@pytest.mark.acceptance("le geste de l'API débloque la carte comme la page")
def test_the_api_gesture_unblocks_the_card_like_the_page(served, fake_board):
    studio, port = served
    videos.create(studio.places.content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    card = fake_board.create("essai : à revoir", "studio-revue", "", "studio:essai")
    fake_board.schedule(card, "Regarder le master")
    status, body = call(port, "POST", "/api/items/essai/gesture", {"decision": "refaire", "note": "le son"})
    assert status == 200 and body["card"] == card
    assert fake_board.statuses(card) == ("studio-revue", "ready")
    assert fake_board.tasks[card]["comments"][-1].body == "UNBLOCK: refaire : le son"


def test_the_api_refuses_an_unknown_decision(served, fake_board):
    studio, port = served
    videos.create(studio.places.content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    card = fake_board.create("essai : à revoir", "studio-revue", "", "studio:essai")
    fake_board.schedule(card, "Regarder le master")
    status, body = call(port, "POST", "/api/items/essai/gesture", {"decision": "peut-etre"})
    assert status == 400 and "décision inconnue" in body["message"]
    assert fake_board.statuses(card) == ("studio-revue", "scheduled")
