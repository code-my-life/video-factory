"""The studio page (#7): a take sent from the phone is checked against the fingerprint the phone computed, stored by
vf ingest under that same fingerprint, and moves its card to Montage; the page's gestures are the board's unblocks."""

from __future__ import annotations

import hashlib
import http.client
import json
import shutil
import subprocess
import threading
import urllib.parse
from pathlib import Path

import pytest

from test_board import FakeVf
from video_factory import videos
from video_factory.paths import REPO_ROOT, SCRIPT_TEMPLATE, Places
from video_factory.studio.lanes import Jobs, Studio, capture_name
from video_factory.studio.page import server, staging, stem_of

NOW = "2026-11-04T14:00:00Z"
TAKE = bytes(range(256)) * 4099  # a little over 1 MiB, so it arrives in more than one chunk


@pytest.fixture
def page(tmp_path: Path, fake_board):
    content = tmp_path / "video-content"
    (content / ".git").mkdir(parents=True)
    places = Places(content=content, media=tmp_path / "media", tools=tmp_path / "tools")
    studio = Studio(
        board=fake_board,
        places=places,
        url="https://studio.example.ts.net:8448",
        vf=FakeVf(places, fake_board),
        jobs=Jobs(background=False),
        log=lambda _line: None,
    )
    videos.create(content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    card = fake_board.create("essai : une prise", "studio-tournage", "", "studio:essai")
    fake_board.schedule(card, "tourner")
    httpd = server(studio, "127.0.0.1", 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield studio, card, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def request(port: int, method: str, path: str, body: bytes = b"", headers: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read()


@pytest.mark.acceptance("une prise reçue garde son empreinte et fait avancer sa carte")
def test_a_received_take_keeps_its_fingerprint_and_moves_its_card(page):
    studio, card, port = page
    phone = hashlib.sha256(TAKE).hexdigest()
    status, body = request(port, "PUT", "/v/essai/prises/0", TAKE, {"X-Empreinte": phone, "X-Nom": "IMG_0042.MOV"})
    assert status == 200
    assert json.loads(body) == {"sha256": phone, "octets": len(TAKE)}
    status, body = request(port, "POST", "/v/essai/prises", b'{"count": 1}', {"Content-Type": "application/json"})
    assert status == 200, body
    stored = studio.places.media / f"{phone}.mov"
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == phone
    state = json.loads((studio.places.content / "videos" / "essai" / "state.json").read_text(encoding="utf-8"))
    assert state["takes"] == [{"sha256": phone, "file": f"{phone}.mov"}]
    assert studio.board.statuses(card) == ("studio-montage", "ready")
    assert not staging(studio, "essai").exists(), "the received copy is removed once stored"


def test_a_take_that_differs_from_the_phone_is_refused_and_not_kept(page):
    studio, card, port = page
    wrong = hashlib.sha256(b"autre chose").hexdigest()
    status, body = request(port, "PUT", "/v/essai/prises/0", TAKE, {"X-Empreinte": wrong})
    assert status == 422
    assert hashlib.sha256(TAKE).hexdigest() in json.loads(body)["message"]
    assert list(staging(studio, "essai").iterdir()) == []
    status, _body = request(port, "POST", "/v/essai/prises", b'{"count": 1}')
    assert status == 400
    assert studio.board.statuses(card) == ("studio-tournage", "scheduled")
    assert studio.vf.calls == []


def test_a_gesture_on_the_page_is_the_same_unblock_as_on_telegram(page):
    studio, card, port = page
    status, _body = request(
        port,
        "POST",
        "/v/essai/reponse",
        b"decision=refaire&note=plus+court",
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 303
    assert studio.board.calls[-1] == ("unblock", card, "refaire : plus court")
    status, _body = request(port, "GET", "/v/essai")
    assert status == 200
    status, _body = request(port, "GET", "/v/autre/media/../../etc/passwd")
    assert status == 404


def test_the_page_serves_its_files_and_a_health_answer(page):
    _studio, _card, port = page
    status, body = request(port, "GET", "/sante")
    assert status == 200
    assert json.loads(body)["board"] == "studio"
    status, body = request(port, "GET", "/static/sha256.js")
    assert status == 200
    assert b"Sha256" in body
    status, _body = request(port, "GET", "/static/../manifest.json")
    assert status == 404


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_the_phone_computes_the_same_fingerprint_as_the_server(tmp_path: Path):
    script = (
        "const Sha256 = require(process.argv[1]); const fs = require('fs');"
        "const data = fs.readFileSync(process.argv[2]); const hash = new Sha256();"
        "for (let i = 0; i < data.length; i += 100003) hash.update(data.subarray(i, i + 100003));"
        "process.stdout.write(hash.hex());"
    )
    for size in (0, 55, 56, 64, 1000, len(TAKE)):
        sample = tmp_path / f"{size}.bin"
        sample.write_bytes(TAKE[:size])
        found = subprocess.run(
            ["node", "-e", script, str(REPO_ROOT / "templates" / "studio" / "sha256.js"), str(sample)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert found == hashlib.sha256(TAKE[:size]).hexdigest()


def test_a_received_file_keeps_its_name_so_a_showcase_stores_each_rush_as_the_capture_its_script_names():
    assert stem_of("IMG 0042.MOV") == "img-0042"
    assert stem_of(urllib.parse.quote("Plan5-PR (prod).mp4")) == "plan5-pr-prod"
    assert stem_of("...") == "fichier"
    assert capture_name(Path("001-plan5-pr.mp4")) == "plan5-pr"
    assert capture_name(Path("plan1.mp4")) == "plan1"
