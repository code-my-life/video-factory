"""state.json and the chain: a step is stale when one of its inputs changed, the steps after it wait, and vf run redoes
only those (and among them, only the ones whose own inputs come out different)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from video_factory import chain, faces, lock, state, store, videos
from video_factory.context import Video
from video_factory.hashing import sha256_bytes
from video_factory.paths import LOCK_FILE, SCRIPT_TEMPLATE, Places
from video_factory.tools import Toolbox

SCRIPT = SCRIPT_TEMPLATE.read_text(encoding="utf-8").replace("{{id}}", "essai") + "Le code est simple.\n"
OUTPUTS = {
    "ingest": {"work": "mkv", "probe": "json"},
    "scan": {"faces": "json"},
    "blur": {"video": "mkv", "mask": "mkv"},
    "transcribe": {"transcript": "json"},
    "align": {"alignment": "json"},
    "cut": {"edl": "json"},
    "voice": {"voice": "wav"},
    "compose": {"frames": "frames", "music": "wav", "plan": "json", "text": "json"},
    "master": {"master": "mp4", "tiktok": "mp4", "master_framemd5": "framemd5", "tiktok_framemd5": "framemd5"},
    "qc": {"report": "json"},
}


def fake_run(name: str):
    """A run that needs no tool: each output is a function of the step's inputs alone."""

    def run(video: Video, scratch: Path):
        inputs = chain.BY_NAME[name].inputs(video)
        made = {}
        for output, ext in OUTPUTS[name].items():
            path = scratch / f"{output}.{ext}"
            if ext == "frames":
                path.mkdir()
                (path / "frame_000001.png").write_text(json.dumps([name, output, inputs], sort_keys=True))
            else:
                path.write_text(json.dumps([name, output, inputs], sort_keys=True))
            made[output] = (path, ext)
        summary = {"duration": 70.0, "passed": True, "failed": []}
        return chain.steps.Result(made, summary)

    return run


@pytest.fixture
def video(tmp_path: Path, monkeypatch) -> Video:
    content, media = tmp_path / "content", tmp_path / "media"
    (content / ".git").mkdir(parents=True)
    folder = videos.create(content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), "2026-11-04T14:00:00Z")
    (folder / "script.md").write_text(SCRIPT, encoding="utf-8")
    take = tmp_path / "prise.mov"
    take.write_bytes(b"une prise")
    places = Places(content=content, media=media, tools=tmp_path / "tools")
    found = Video.open(places, "essai", Toolbox(lock.load(LOCK_FILE), places.tools))
    found.state["takes"] = [store.put(media, take, "mov", keep_source=True)]
    found.save()
    fakes = tuple(dataclasses.replace(step, run=fake_run(step.name)) for step in chain.STEPS)
    monkeypatch.setattr(chain, "STEPS", fakes)
    monkeypatch.setattr(chain, "BY_NAME", {step.name: step for step in fakes})
    chain.run(found, say=lambda _line: None)
    return found


def labels(video: Video) -> dict[str, str]:
    return {found.step: found.label for found in chain.status(video)}


def finished(video: Video) -> dict[str, str]:
    return {name: record["finished_at"] + str(record["seconds"]) for name, record in video.state["steps"].items()}


@pytest.mark.acceptance("une entrée modifiée rend son étape et celles qui en dépendent périmées")
def test_a_changed_input_makes_its_step_and_the_steps_after_it_stale(video):
    assert set(labels(video).values()) == {chain.UP_TO_DATE}
    video.script_path.write_text(SCRIPT.replace("simple", "très simple"), encoding="utf-8")
    found = {status.step: status for status in chain.status(video)}
    assert found["align"].label == chain.STALE
    assert found["align"].reasons == ("entrée « script » modifié",)
    assert found["compose"].label == chain.STALE
    for name in ("cut", "voice", "master", "qc"):
        assert found[name].label == chain.WAITING
    for name in ("ingest", "scan", "blur", "transcribe"):
        assert found[name].label == chain.UP_TO_DATE
    # vf run redoes those steps and no other, as state.json records.
    before = finished(video)
    ran = chain.run(video, say=lambda _line: None)
    assert ran == ["align", "cut", "voice", "compose", "master", "qc"]
    after = finished(video)
    assert {name for name in after if after[name] != before[name]} <= set(ran)
    assert all(after[name] == before[name] for name in ("ingest", "scan", "blur", "transcribe"))
    assert set(labels(video).values()) == {chain.UP_TO_DATE}
    assert state.problems(json.loads((video.folder / "state.json").read_text(encoding="utf-8"))) == []


def test_a_changed_parameter_redoes_the_steps_that_use_it_and_not_the_steps_whose_inputs_stay_the_same(
    video, monkeypatch
):
    monkeypatch.setattr(faces, "THRESHOLD", 0.7)
    found = {status.step: status for status in chain.status(video)}
    assert found["scan"].reasons == ("paramètres modifiés",)
    assert found["qc"].reasons == ("paramètres modifiés",)
    assert found["cut"].label == chain.WAITING
    # scan gives the same output again, so cut and the steps after it are not redone; qc reads the threshold too.
    assert chain.run(video, say=lambda _line: None) == ["scan", "qc"]


def test_a_missing_output_makes_its_step_stale(video):
    media = video.output_ref("voice", "voice")
    path = store.path(video.media, media)
    path.chmod(0o644)
    path.unlink()
    found = {status.step: status for status in chain.status(video)}
    assert found["voice"].reasons == (f"{media['file']} absent du magasin",)


def test_a_version_1_state_without_steps_moves_to_version_2(tmp_path):
    old = {
        "schema_version": 1,
        "id": "essai",
        "created_at": "2026-11-04T14:00:00Z",
        "script": {"path": "script.md", "sha256": sha256_bytes(b"x")},
        "steps": {},
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    assert state.load(path) == old | {"schema_version": 2, "takes": [], "captures": {}}
    path.write_text(json.dumps(old | {"steps": {"ingest": {}}}), encoding="utf-8")
    with pytest.raises(state.StateError, match="version 1 avec des étapes"):
        state.load(path)


def test_a_state_that_breaks_its_schema_is_never_written(tmp_path):
    path = tmp_path / "state.json"
    with pytest.raises(state.StateError, match="ne suit pas son schéma"):
        state.save(path, {"schema_version": 2})
    assert not path.exists()


def test_the_vf_command_names_what_is_missing(tmp_path, monkeypatch, capsys):
    from video_factory import cli

    content = tmp_path / "content"
    (content / ".git").mkdir(parents=True)
    monkeypatch.setenv("VF_CONTENT", str(content))
    monkeypatch.setenv("VF_MEDIA", str(tmp_path / "media"))
    assert cli.main(["status", "absente"]) == 1
    assert "vidéo « absente » introuvable" in capsys.readouterr().err
    assert cli.main(["new", "essai"]) == 0
    assert cli.main(["ingest", "essai"]) == 1
    assert "aucune prise ni capture" in capsys.readouterr().err
    assert cli.main(["run", "essai"]) == 1
    assert "aucune prise : vf ingest essai <fichiers>" in capsys.readouterr().err
    assert cli.main(["status", "essai"]) == 0
    assert "jamais passée  ingest" in capsys.readouterr().out
