"""vf publish <id>: the TikTok export, the master and the caption of a master that passed qc, ready to post by hand."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_factory import cli, montage, publish, store, videos
from video_factory.paths import SCRIPT_TEMPLATE

NOW = "2026-11-04T14:00:00Z"


@pytest.fixture
def video(tmp_path: Path, monkeypatch):
    content, media = tmp_path / "content", tmp_path / "media"
    (content / ".git").mkdir(parents=True)
    monkeypatch.setenv("VF_CONTENT", str(content))
    monkeypatch.setenv("VF_MEDIA", str(media))
    folder = videos.create(content, "essai", SCRIPT_TEMPLATE.read_text(encoding="utf-8"), NOW)
    outputs = {}
    for name, data in {"master": b"master", "tiktok": b"tiktok"}.items():
        source = tmp_path / f"{name}.mp4"
        source.write_bytes(data)
        outputs[name] = store.put(media, source, "mp4")
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    state["steps"] = {"master": record(outputs, {}), "qc": record({}, {"passed": True})}
    return folder, media, state


def record(outputs: dict, summary: dict) -> dict:
    """A step as the chain writes it in state.json, valid against the schema."""
    return {
        "inputs": {},
        "outputs": outputs,
        "tools": {},
        "params": {},
        "code": "0" * 64,
        "summary": summary,
        "started_at": NOW,
        "finished_at": NOW,
        "seconds": 1.0,
    }


def test_publish_prepares_the_files_and_the_caption(video, capsys):
    folder, media, state = video
    (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert cli.main(["publish", "essai"]) == 0
    out = media / "publication" / "essai"
    assert (out / "tiktok.mp4").read_bytes() == b"tiktok"
    assert (out / "master.mp4").read_bytes() == b"master"
    assert (out / "legende.txt").read_text(encoding="utf-8") == f"Titre à écrire\n\n{publish.ROBOT_CREDIT}\n"
    assert "prêt à publier à la main" in capsys.readouterr().out
    assert cli.main(["publish", "essai"]) == 0, "running it again replaces the same files"


def test_publish_refuses_a_master_that_qc_refused_or_that_is_missing(video):
    _folder, media, state = video
    state["steps"]["qc"]["summary"]["passed"] = False
    assert publish.problems(state, media) == ["qc refuse le master : vf status"]
    del state["steps"]["qc"]
    (media / state["steps"]["master"]["outputs"]["tiktok"]["file"]).chmod(0o644)
    (media / state["steps"]["master"]["outputs"]["tiktok"]["file"]).unlink()
    found = publish.problems(state, media)
    assert found[0] == "qc n'est pas passé : vf run"
    assert found[1].startswith("sortie tiktok de master : ")
    with pytest.raises(publish.PublishError):
        publish.prepare(state, "", media)


SHOWCASE = """---
id: "essai"
titre: "Essai"
plateforme: tiktok
duree_visee: 20
genre: vitrine
theme: primer
vignette: "On dirait pas, | mais je *code* <vite>"
vignette_image: "12,5"
---
Coucou. [plan: a]
"""


@pytest.mark.acceptance("la vignette porte le texte du script")
def test_the_cover_carries_the_text_of_the_script(video):
    _folder, media, state = video
    ready = publish.prepare(state, SHOWCASE, media)
    assert ready.cover == publish.Cover(("On dirait pas,", "mais je *code* <vite>"), 12.5, "primer")
    page = publish.cover_page(montage.theme_folder(ready.cover.theme), ready.cover.lines)
    # Each line of the vignette is a line of the cover, the word between asterisks in the accent colour, escaped.
    assert (
        '<div class="title" id="title"><div>On dirait pas,</div><div>mais je <em>code</em> &lt;vite&gt;</div></div>'
        in page
    )
    assert "{{" not in page
    # A face camera script asks for no cover.
    assert publish.prepare(state, SHOWCASE.replace("genre: vitrine\n", ""), media).cover is None


def test_an_ai_voice_is_said_in_the_caption_and_the_ai_label_is_recalled(video, capsys):
    folder, media, state = video
    (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
    script = (folder / "script.md").read_text(encoding="utf-8")
    fields = 'legende: "Des agents codent pour moi."\nmots_cles: "#ia #opensource"\nvoix_ia: ElevenLabs\n---'
    (folder / "script.md").write_text(script.replace("---", fields, 2).replace(fields, "---", 1), encoding="utf-8")
    assert cli.main(["publish", "essai"]) == 0
    caption = (media / "publication" / "essai" / "legende.txt").read_text(encoding="utf-8")
    assert caption == (
        "Des agents codent pour moi.\n\nVoix générée par IA (ElevenLabs).\n\n"
        f"{publish.ROBOT_CREDIT}\n\n#ia #opensource\n"
    )
    assert (
        "Étiquette IA à activer sur TikTok, YouTube et Instagram : voix générée par ElevenLabs"
        in capsys.readouterr().out
    )


def test_a_cover_the_script_no_longer_asks_for_is_removed(video):
    _folder, media, state = video
    folder = media / "publication" / "essai"
    folder.mkdir(parents=True)
    (folder / publish.COVER_NAME).write_bytes(b"ancienne vignette")
    publish.write(publish.prepare(state, SHOWCASE.replace("genre: vitrine\n", ""), media), media, "essai")
    assert not (folder / publish.COVER_NAME).exists()
