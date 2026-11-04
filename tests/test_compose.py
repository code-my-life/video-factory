"""compose: the plan of the page (shots, captions, punch-ins), the page itself, and what the text pass measures."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from conftest import ffmpeg, pinned_toolbox
from video_factory import align, compose, cut, master, media, music
from video_factory import script as scripts
from video_factory.hashing import sha256_bytes
from video_factory.tools import Toolbox, ToolError

SCRIPT = """---
id: "essai"
titre: "Essai"
plateforme: tiktok
duree_visee: 63
---
Le code est simple. [capture: ligne]
Il est rapide [stat: 9 postes | de l'idée à la mise en ligne] pour tous.
On le lance d'une commande. [code: vf run <id>]
Et on recommence. [zoom]
"""


def edl_of(text: str) -> tuple[scripts.Script, dict]:
    script = scripts.parse(text)
    said = [word.norm for word in script.words]
    words = [{"text": t, "start": 0.5 * k + 0.1, "end": 0.5 * k + 0.45} for k, t in enumerate(said)]
    return script, cut.decide(align.align(words, script)["words"], [], 30.0)


CAPTURES = {"ligne": {"sha256": "ab" * 32, "file": f"{'ab' * 32}.png", "kind": "image", "source_sha256": "cd" * 32}}


def test_a_capture_the_video_has_not_registered_stops_compose_and_is_named():
    script, edl = edl_of(SCRIPT)
    with pytest.raises(compose.ComposeError, match="capture absente : « ligne » ; à verser par vf ingest"):
        compose.plan(edl, script, {})


def test_a_shot_at_the_end_of_a_line_covers_its_sentence_and_one_inside_starts_on_the_word_before():
    script, edl = edl_of(SCRIPT)
    plan = compose.plan(edl, script, CAPTURES)
    shots = {shot["kind"]: shot for shot in plan["shots"]}
    first_of: dict[str, int] = {}
    for word in edl["words"]:
        first_of.setdefault(word["text"], compose.frame_of(word["start"]))
    assert shots["capture"]["start"] == first_of["le"]
    assert shots["capture"]["end"] == first_of["il"]
    assert shots["capture"]["still"] is True
    assert shots["stat"]["start"] == first_of["rapide"]
    assert shots["stat"]["parts"] == ["9 postes", "de l'idée à la mise en ligne"]
    assert shots["code"]["parts"] == ["vf run <id>"]
    shot_frames = sum(shot["end"] - shot["start"] for shot in plan["shots"])
    assert plan["camera_frames"] == plan["frames"] - shot_frames


def test_captions_show_the_written_words_and_the_punch_in_starts_on_its_word():
    script, edl = edl_of(SCRIPT)
    plan = compose.plan(edl, script, CAPTURES)
    assert [word["text"] for word in plan["words"]][:4] == ["Le", "code", "est", "simple."]
    assert all(word["end"] > word["start"] for word in plan["words"])
    recommence = next(w for w in edl["words"] if w["text"] == "recommence")
    assert plan["zooms"] == [
        {
            "start": compose.frame_of(recommence["start"]),
            "end": min(edl["frames"], compose.frame_of(recommence["end"] + 1.0)),
        }
    ]


def fake_toolbox(tmp_path: Path, files: dict[str, bytes] | None = None) -> Toolbox:
    """A lock with one library, GSAP, installed under tmp_path with the given files (its pinned ones by default)."""
    pinned = {"gsap.min.js": b"/*! GSAP */", "CustomEase.min.js": b"/*! CustomEase */"}
    entry = {
        "name": "gsap",
        "kind": "library",
        "version": "3.15.0",
        "files": {name: {"path": f"package/{name}", "sha256": sha256_bytes(data)} for name, data in pinned.items()},
    }
    folder = tmp_path / "tools" / "gsap" / "3.15.0"
    folder.mkdir(parents=True)
    for name, data in (files or pinned).items():
        (folder / name).write_bytes(data)
    return Toolbox({"tools": [entry]}, tmp_path / "tools")


def written(tmp_path: Path, text: str = SCRIPT) -> tuple[dict, Path]:
    script, edl = edl_of(text)
    plan = compose.plan(edl, script, CAPTURES)
    project = tmp_path / "project"
    compose.write_project(project, plan)
    compose.ship_libraries(project, fake_toolbox(tmp_path))
    return plan, project


def hosts_of(page: str) -> dict[str, dict[str, str]]:
    """The scene hosts of a root page: id → its data-* attributes."""
    found = {}
    for tag in re.findall(r"<div [^>]*data-composition-src=[^>]*>", page):
        attributes = dict(re.findall(r'(data-[a-z-]+|id)="([^"]*)"', tag))
        found[attributes["id"]] = attributes
    return found


@pytest.mark.acceptance("le projet produit monte une scène par plan du script")
def test_the_project_mounts_one_scene_per_shot_of_the_script(tmp_path):
    plan, project = written(tmp_path)
    page = (project / "index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="main"' in page and 'data-width="1440"' in page and 'data-height="2560"' in page
    assert 'data-fps="30"' in page and f'data-duration="{plan["frames"] / 30:.6f}"' in page
    hosts = hosts_of(page)
    shots = [host for name, host in hosts.items() if name.startswith("shot-")]
    assert [host["data-composition-id"] for host in shots] == [f"shot-{k}" for k in range(len(plan["shots"]))]
    assert len(shots) == len(scripts.parse(SCRIPT).shots) == 3
    for index, (host, shot) in enumerate(zip(shots, plan["shots"], strict=True)):
        assert host["data-start"] == f"{shot['start'] / 30:.6f}"
        assert host["data-duration"] == f"{(shot['end'] - shot['start']) / 30:.6f}"
        scene = (project / host["data-composition-src"]).read_text(encoding="utf-8")
        assert f'data-composition-id="shot-{index}"' in scene
        assert "window.__timelines[ID] = tl" in scene and f'var ID = "shot-{index}"' in scene
        assert "{{" not in scene
    # One captions track, the take in the wrapper the punch-ins scale, and only the root in the project.
    assert [host["data-track-kind"] for host in hosts.values()].count("captions") == 1
    assert '<div id="camera-wrap"><video id="camera" class="clip" src="assets/camera.mp4"' in page
    assert sorted(path.name for path in project.glob("*.html")) == ["index.html"]
    assert "vf run \\u003cid>" in (project / "compositions" / "shot-2.html").read_text(encoding="utf-8")
    assert (project / "assets" / "fonts" / "Inter-Bold.woff2").is_file()
    assert (project / "assets" / "lib" / "gsap" / "gsap.min.js").read_bytes() == b"/*! GSAP */"


@pytest.mark.acceptance("le projet produit ne contient aucune URL de CDN")
def test_the_project_holds_no_cdn_url_and_loads_only_its_own_files(tmp_path):
    plan, project = written(tmp_path)
    compose.write_text_root(tmp_path / "texte.html", plan)
    (project / "assets" / "camera.mp4").write_bytes(b"take")
    (project / "assets" / "captures" / "0.png").write_bytes(b"still")
    assert compose.outside_references(project) == []
    assert compose.missing_files(project) == []
    texts = [path.read_text(encoding="utf-8") for path in compose.text_files(project)]
    texts.append((tmp_path / "texte.html").read_text(encoding="utf-8"))
    for text in texts:
        assert not re.search(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//", text)
        assert all(host not in text for host in compose.CDN_HOSTS)
    # The check sees a CDN anywhere, and a page loading anything from outside, as the registry items do as installed.
    upstream = (compose.HYPERFRAMES_TEMPLATE / "components" / "caption-highlight.html").read_text(encoding="utf-8")
    scene = project / "compositions" / "captions.html"
    scene.write_text(
        upstream.replace(
            "<style>", '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script><style>', 1
        ),
        encoding="utf-8",
    )
    (project / "compositions" / "shot-0.html").write_text(
        '<link href="//fonts.example.org/a.css" rel="stylesheet" />', encoding="utf-8"
    )
    found = compose.outside_references(project)
    assert "compositions/captions.html : cdn.jsdelivr.net" in found
    assert "compositions/captions.html : https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js" in found
    assert "compositions/shot-0.html : //fonts.example.org/a.css" in found


REFUSED = {
    "ok": False,
    "lint": {
        "ok": False,
        "findings": [
            {
                "code": "gsap_animates_clip_element",
                "severity": "error",
                "message": "GSAP animates a .clip element.",
                "sourceFile": "compositions/shot-1.html",
            },
            {"code": "line_unread", "severity": "warning", "message": "short", "sourceFile": "index.html"},
        ],
    },
    "audio": {"ok": True, "findings": [{"code": "audio_none", "severity": "info", "message": "no sound"}]},
}


@pytest.mark.acceptance("un projet que check refuse arrête compose avec l'erreur")
def test_a_project_the_check_refuses_stops_compose_with_the_error(tmp_path):
    calls = []

    def checker(argv):
        calls.append(argv)
        return 1, "Checking…\n" + json.dumps(REFUSED)

    command = compose.check_command("sha256:" + "ab" * 32, {"DO_NOT_TRACK": "1"}, tmp_path / "p", tmp_path / "w")
    with pytest.raises(compose.ComposeError) as refused:
        compose.check_project(command, checker)
    assert str(refused.value) == (
        "hyperframes check refuse le projet :\n"
        "- lint : gsap_animates_clip_element : GSAP animates a .clip element. (compositions/shot-1.html)"
    )
    assert calls[0][calls[0].index("--network") + 1] == "none"
    assert calls[0][-3:] == ["check", "/project", "--json"]
    passed = {"ok": True, "lint": {"findings": REFUSED["lint"]["findings"][1:]}}
    assert compose.check_project(command, lambda _argv: (0, json.dumps(passed))) == passed
    assert compose.check_warnings(passed) == ["line_unread"]
    with pytest.raises(compose.ComposeError, match="n'a pas rendu de rapport"):
        compose.check_project(command, lambda _argv: (1, "Error: no browser"))


def test_a_library_the_lock_does_not_pin_or_a_copy_with_another_fingerprint_is_refused(tmp_path):
    _plan, project = written(tmp_path)
    (project / "compositions" / "shot-0.html").write_text('<script src="assets/lib/lodash/lodash.js"></script>')
    with pytest.raises(compose.ComposeError, match="bibliothèque hors du lock : lodash"):
        compose.ship_libraries(project, fake_toolbox(tmp_path / "other"))
    tampered = fake_toolbox(tmp_path / "tampered", {"gsap.min.js": b"/*! GSAP */", "CustomEase.min.js": b"x"})
    with pytest.raises(ToolError, match=r"gsap : CustomEase\.min\.js n'a pas l'empreinte du lock"):
        tampered.library("gsap")


def test_caption_groups_close_at_a_sentence_end_a_pause_or_three_words_and_never_overlap():
    script = scripts.parse(SCRIPT)
    said = [word.norm for word in script.words]
    words = [{"text": t, "start": 0.4 * k + 0.1, "end": 0.4 * k + 0.45} for k, t in enumerate(said)]
    edl = cut.decide(align.align(words, script)["words"], [], 30.0)
    plan = compose.plan(edl, script, CAPTURES)
    words = [plan["words"][g["first"] : g["last"] + 1] for g in plan["groups"]]
    assert [[w["text"] for w in group] for group in words][:3] == [
        ["Le", "code", "est"],
        ["simple."],
        ["Il", "est", "rapide"],
    ]
    assert plan["groups"][0]["first"] == 0 and plan["groups"][-1]["last"] == len(plan["words"]) - 1
    for current, following in pairwise(plan["groups"]):
        assert current["last"] + 1 == following["first"]
        assert current["start"] < current["end"] <= following["start"]
    paused = [dict(word, start=word["start"] + (0.3 if k == 1 else 0)) for k, word in enumerate(edl["words"])]
    regrouped = compose.plan_groups(edl | {"words": paused}, script)
    assert (regrouped[0]["first"], regrouped[0]["last"]) == (0, 0)


def test_a_stat_counts_up_a_leading_whole_number_and_shows_any_other_figure_as_written():
    assert compose.stat_config(["9 postes", "de l'issue", "à la mise en ligne"]) == {
        "value": 9,
        "figure": "9 postes",
        "label": "postes",
        "caption": "de l'issue à la mise en ligne",
    }
    assert compose.stat_config(["x10"])["value"] is None
    assert compose.stat_config(["2,5 s"])["value"] is None


def test_the_safe_zone_is_the_strictest_of_the_three_platforms():
    assert compose.safe_box(1080, 1920) == pytest.approx((64.8, 288.0, 887.76, 1248.0))
    left, top, right, bottom = compose.safe_box()
    for place in (compose.CAPTION, compose.SHOT):
        assert place["left"] >= left and place["top"] >= top
        assert place["left"] + place["width"] <= right and place["top"] + place["height"] <= bottom


def test_the_text_pass_gives_the_box_of_the_text_on_each_frame(tools, tmp_path):
    box = tools("ffmpeg")
    frames = tmp_path / "frames"
    frames.mkdir()
    for index in range(4):
        picture = np.zeros((256, 144, 3), np.uint8)
        if index >= 1:
            picture[100:120, 20:90] = 255
        if index == 3:
            picture[200, 10] = 7
        path = tmp_path / f"{index}.rgb"
        path.write_bytes(picture.tobytes())
        ffmpeg(
            box,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "144x256",
            "-i",
            path,
            frames / f"frame_{index + 1:06d}.png",
        )
    assert compose.text_runs(box.ffmpeg, frames, 144, 256) == [[1, 2, 20, 100, 90, 120], [3, 3, 10, 100, 90, 201]]


def render_image():
    """The id of the pinned render image when it is built on this machine; the test that needs it is skipped otherwise
    (the CI does not build it: two renders are compared on the machine, see the RUNBOOK)."""
    if shutil.which("docker") is None:
        pytest.skip("docker absent")
    tool = pinned_toolbox().entry("hyperframes-render")
    done = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", tool["image"]], capture_output=True, text=True
    )
    if done.returncode != 0 or done.stdout.strip() not in {
        f"sha256:{tool['sha256']}",
        f"sha256:{tool['config_sha256']}",
    }:
        pytest.skip(f"image de rendu {tool['image']} absente : uv run vf doctor --install hyperframes-render")
    return done.stdout.strip()


@pytest.mark.acceptance("deux rendus des mêmes entrées donnent les mêmes empreintes framemd5 du master")
def test_two_renders_of_the_same_project_give_the_same_master_framemd5_without_the_network(tools, tmp_path):
    """The whole compose then master path, twice, in the pinned image: the project passes its check, each pass renders
    with --network none, and the two masters have the same framemd5 lines and bytes."""
    box = tools("ffmpeg")
    image = render_image()
    frames = 45
    script, edl = edl_of(SCRIPT.replace(" [capture: ligne]", ""))
    plan = compose.plan(edl, script, {})
    project = tmp_path / "project"
    compose.write_project(project, plan)
    plan["frames"] = frames
    (project / "index.html").write_text(
        re.sub(r'data-duration="[0-9.]+"', f'data-duration="{frames / 30:.6f}"', (project / "index.html").read_text()),
    )
    compose.ship_libraries(project, box)
    camera = project / "assets" / "camera.mp4"
    source = f"testsrc2=size=1206x2144:rate=30:duration={frames / 30}"
    ffmpeg(box, "-f", "lavfi", "-i", source, *compose.encode_args(camera)[:-1], camera)
    assert compose.outside_references(project) == [] and compose.missing_files(project) == []
    environment = dict(box.entry("hyperframes")["env"])
    work = tmp_path / "work"
    work.mkdir()
    compose.check_project(compose.check_command(image, environment, project, work))
    voice = tmp_path / "voice.wav"
    ffmpeg(box, "-f", "lavfi", "-i", f"sine=f=220:sample_rate=48000:duration={frames / 30}", "-ac", "1", voice)
    bed = tmp_path / "music.wav"
    music.write(bed, music.bed(frames / 30))
    found = []
    for run in ("a", "b"):
        output = tmp_path / run
        output.mkdir()
        media.run(compose.render_command(image, environment, project, output, work), "rendu")
        rendered = compose.rendered(output, frames)
        target, digest = output / "master.mp4", output / "master.framemd5"
        media.ffmpeg(box.ffmpeg, master.command(rendered, voice, bed, frames, "master", target), "master")
        media.ffmpeg(box.ffmpeg, master.framemd5_command(target, digest), "framemd5")
        found.append((digest.read_text().splitlines(), target.read_bytes()))
        shutil.rmtree(rendered)
    assert found[0] == found[1]
    assert sum(1 for line in found[0][0] if line.startswith("0,")) == frames


def test_the_render_runs_offline_and_writes_nothing_heavy_inside_the_container(tmp_path):
    environment = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    command = compose.render_command("sha256:" + "ab" * 32, environment, tmp_path / "p", tmp_path / "o", tmp_path / "w")
    assert command[command.index("--network") + 1] == "none"
    assert "HYPERFRAMES_NO_TELEMETRY=1" in command and "DO_NOT_TRACK=1" in command
    assert "TMPDIR=/vf-work" in command and "HOME=/vf-work" in command
    assert f"{tmp_path / 'w'}:/vf-work" in command and f"{tmp_path / 'p'}:/project:ro" in command
    assert command[command.index("--frames-cache-dir") + 1] == "off"
    assert command[command.index("--user") + 1].count(":") == 1


def test_the_text_pass_mounts_its_root_over_the_project_index(tmp_path):
    command = compose.render_command("img", {}, tmp_path / "p", tmp_path / "o", tmp_path / "w", tmp_path / "texte.html")
    assert f"{tmp_path / 'texte.html'}:/project/index.html:ro" in command
    plan, _project = written(tmp_path)
    compose.write_text_root(tmp_path / "texte.html", plan)
    page = (tmp_path / "texte.html").read_text(encoding="utf-8")
    assert "camera.mp4" not in page and "color: #fff !important" in page
    assert hosts_of(page).keys() == hosts_of((tmp_path / "project" / "index.html").read_text(encoding="utf-8")).keys()
