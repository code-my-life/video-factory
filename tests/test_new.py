"""vf new <id>: script.md from the template and state.json at schema version 1, both valid against the published
schemas; an existing id or a malformed one is refused and nothing is written."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_factory import cli, frontmatter, schemas, videos
from video_factory.hashing import sha256_file
from video_factory.paths import SCRIPT_SCHEMA, SCRIPT_TEMPLATE, STATE_SCHEMA

NOW = "2026-11-04T14:00:00Z"
TEMPLATE = SCRIPT_TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture
def content(tmp_path: Path) -> Path:
    root = tmp_path / "video-content"
    (root / ".git").mkdir(parents=True)
    return root


def test_vf_new_creates_a_script_and_a_state_valid_against_the_published_schemas(content):
    folder = videos.create(content, "essai", TEMPLATE, NOW)
    assert folder == content / "videos" / "essai"
    assert sorted(path.name for path in folder.iterdir()) == ["script.md", "state.json"]
    fields, _body = frontmatter.split((folder / "script.md").read_text(encoding="utf-8"))
    assert schemas.problems(fields, SCRIPT_SCHEMA) == []
    assert fields == {"id": "essai", "titre": "Titre à écrire", "plateforme": "tiktok", "duree_visee": 75}
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    assert schemas.problems(state, STATE_SCHEMA) == []
    assert state == {
        "schema_version": 1,
        "id": "essai",
        "created_at": NOW,
        "script": {"path": "script.md", "sha256": sha256_file(folder / "script.md")},
        "steps": {},
    }


def test_vf_new_refuses_an_existing_id_and_leaves_it_untouched(content):
    folder = videos.create(content, "essai", TEMPLATE, NOW)
    (folder / "script.md").write_text("texte réécrit", encoding="utf-8")
    with pytest.raises(videos.VideoError, match="existe déjà"):
        videos.create(content, "essai", TEMPLATE, "2026-11-05T09:00:00Z")
    assert (folder / "script.md").read_text(encoding="utf-8") == "texte réécrit"
    assert sorted(path.name for path in (content / "videos").iterdir()) == ["essai"]


@pytest.mark.parametrize("video_id", ["Essai", "../essai", "essai/x", "a_b", "-essai", "essai-", "", "x" * 65])
def test_vf_new_refuses_an_id_that_is_not_lowercase_letters_digits_and_hyphens(content, video_id):
    with pytest.raises(videos.VideoError, match="refusé"):
        videos.create(content, video_id, TEMPLATE, NOW)
    assert not (content / "videos").exists()


def test_vf_new_refuses_a_missing_content_clone(tmp_path):
    with pytest.raises(videos.VideoError, match="dépôt de contenu introuvable"):
        videos.create(tmp_path / "absent", "essai", TEMPLATE, NOW)


def test_an_id_starting_with_a_digit_stays_a_string_in_the_front_matter(content):
    folder = videos.create(content, "2026-bilan", TEMPLATE, NOW)
    fields, _body = frontmatter.split((folder / "script.md").read_text(encoding="utf-8"))
    assert fields["id"] == "2026-bilan"


def test_a_script_whose_id_differs_from_its_folder_is_invalid():
    script = videos.script_text(TEMPLATE, "autre")
    assert any("le nom du dossier" in line for line in videos.script_problems(script, "essai"))


def test_a_state_with_a_step_records_fingerprints_tools_and_parameters():
    state = videos.new_state("essai", "ab" * 32, NOW)
    state["steps"]["transcribe"] = {
        "inputs": {"voice": "cd" * 32},
        "outputs": {"words": "ef" * 32},
        "tools": {"whisper.cpp": "v1.9.5", "whisper-large-v3-turbo": "5359861c739e955e79d9a303bcbc70fb988958b1"},
        "params": {"language": "fr", "temperature": 0},
        "finished_at": NOW,
    }
    assert schemas.problems(state, STATE_SCHEMA) == []
    state["steps"]["montage"] = state["steps"]["transcribe"]
    assert schemas.problems(state, STATE_SCHEMA) != []


def test_the_vf_command_creates_the_video_then_refuses_it_a_second_time(content, monkeypatch, capsys):
    monkeypatch.setenv("VF_CONTENT", str(content))
    assert cli.main(["new", "essai"]) == 0
    out = capsys.readouterr().out
    assert "videos/essai/script.md" in out
    assert "videos/essai/state.json" in out
    assert cli.main(["new", "essai"]) == 1
    assert "la vidéo « essai » existe déjà" in capsys.readouterr().err
