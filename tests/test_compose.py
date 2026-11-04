"""compose: the plan of the page (shots, captions, punch-ins), the page itself, and what the text pass measures."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from conftest import ffmpeg, pinned_toolbox
from video_factory import align, compose, cut, media
from video_factory import script as scripts

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


def test_the_page_of_each_pass_has_the_media_it_needs_and_safe_data(tmp_path):
    script, edl = edl_of(SCRIPT)
    plan = compose.plan(edl, script, CAPTURES)
    compose.write_project(tmp_path, plan)
    video_page = (tmp_path / "index.html").read_text(encoding="utf-8")
    text_page = (tmp_path / "texte.html").read_text(encoding="utf-8")
    assert 'src="assets/camera.mp4"' in video_page and 'id="capture-0"' in video_page
    assert "camera.mp4" not in text_page and 'id="capture-0"' not in text_page
    assert "vf run \\u003cid>" in video_page and "<id>" not in video_page.split('id="vf-data"')[1]
    assert f'data-duration="{plan["frames"] / 30:.6f}"' in video_page
    assert (tmp_path / "assets" / "fonts" / "Inter-Bold.woff2").is_file()
    assert (tmp_path / "assets" / "fonts" / "OFL.txt").is_file()


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


def test_two_renders_of_the_same_page_give_the_same_frames_without_the_network(tools, tmp_path):
    box = tools("ffmpeg")
    image = render_image()
    script, edl = edl_of(SCRIPT.replace(" [capture: ligne]", ""))
    plan = compose.plan(edl, script, {})
    plan["frames"] = edl["frames"] = 24
    project = tmp_path / "project"
    compose.write_project(project, plan)
    camera = project / "assets" / "camera.mp4"
    ffmpeg(
        box,
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1206x2144:rate=30:duration=0.8",
        *compose.encode_args(camera)[:-1],
        camera,
    )
    environment = dict(box.entry("hyperframes")["env"])
    found = []
    for run in ("a", "b"):
        output, work = tmp_path / run, tmp_path / f"{run}-work"
        output.mkdir()
        work.mkdir()
        media.run(compose.render_command(image, environment, project, output, "index.html", work), "rendu")
        frames = compose.rendered(output, 24)
        found.append([path.read_bytes() for path in sorted(frames.iterdir())])
    assert found[0] == found[1]


def test_the_render_runs_offline_and_writes_nothing_heavy_inside_the_container(tmp_path):
    environment = {"HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    command = compose.render_command(
        "sha256:" + "ab" * 32, environment, tmp_path / "p", tmp_path / "o", "index.html", tmp_path / "w"
    )
    assert command[command.index("--network") + 1] == "none"
    assert "HYPERFRAMES_NO_TELEMETRY=1" in command and "DO_NOT_TRACK=1" in command
    assert "TMPDIR=/vf-work" in command and "HOME=/vf-work" in command
    assert f"{tmp_path / 'w'}:/vf-work" in command and f"{tmp_path / 'p'}:/project:ro" in command
    assert command[command.index("--frames-cache-dir") + 1] == "off"
    assert command[command.index("--user") + 1].count(":") == 1
