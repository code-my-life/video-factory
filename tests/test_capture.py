"""vf capture: the capture plan and its refusals, the camera path, the scenario variant on the pinned commit, the
scene and its measures, and zip archives (the pinned Chromium ships as one)."""

from __future__ import annotations

import copy
import io
import json
import os
import re
import stat
import subprocess
import zipfile
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from video_factory import chain, compose, install, paths
from video_factory.capture import camera, demo, scene
from video_factory.capture import plan as capture_plan
from video_factory.capture.shoot import fingerprints, frame_count

PLAN = {
    "plan_version": 1,
    "name": "essai",
    "app": "factory-live",
    "device": "desktop",
    "window": {"width": 1440, "height": 1600},
    "scenario": {"start": 10, "end": 12},
    "actions": [{"at": 5, "do": "zoom", "scale": 1.2, "x": 700, "y": 500}],
    "stage": "main",
    "track": {"issue": {"selector": "[data-issue]", "group": "data-box", "flags": ["data-arriving"]}},
    "camera": {"follow": "issue", "arriving": "data-arriving", "scale": 2},
}


def refusal(plan: dict) -> str:
    with pytest.raises(capture_plan.PlanError) as caught:
        capture_plan.check(plan)
    return str(caught.value)


def changed(**edits) -> dict:
    plan = copy.deepcopy(PLAN)
    for dotted, value in edits.items():
        *parents, last = dotted.split("__")
        node = plan
        for part in parents:
            node = node[part]
        if value is None:
            del node[last]
        else:
            node[last] = value
    return plan


def test_a_valid_plan_gets_its_defaults():
    plan = capture_plan.check(copy.deepcopy(PLAN))
    assert (plan["scale"], plan["fps"], plan["texts"]) == (3, 30, True)
    assert plan["camera"]["move"] == 0.5
    assert plan["camera"]["blur"] == {"copies": 6, "shutter": 0.5}


@pytest.mark.acceptance("un plan de capture invalide est refusé avec le champ en cause")
@pytest.mark.parametrize(
    ("plan", "field"),
    [
        (changed(camera__scale=2.4), "camera.scale"),
        (changed(camera__move=1.0), "camera.move"),
        (changed(window=None), "window"),
        (changed(window__height=100), "window.height"),
        (changed(device="tablette"), "device"),
        (changed(scenario__end=8), "scenario.end"),
        (changed(camera__follow="autre"), "camera.follow"),
        (changed(camera__arriving="data-ailleurs"), "camera.arriving"),
        (changed(device="iphone"), "window"),
        (changed(fps=24), "fps"),
        (changed(track__issue__selector=""), "track.issue.selector"),
        (changed(actions=[{"at": 5, "do": "zoom", "scale": 9, "x": 1, "y": 1}]), "actions.0.scale"),
        (changed(actions=[{"at": 20, "do": "click", "selector": "button"}]), "actions.0.at"),
        (changed(couleur="rouge"), "couleur"),
        (changed(camera__cuts=[{"at": 11, "follow": "autre"}]), "camera.cuts.0.follow"),
        (changed(camera__cuts=[{"at": 11.5}, {"at": 11}]), "camera.cuts"),
        (changed(camera__cuts=[{"at": 11, "scale": 0.8}]), "camera.cuts.0.scale"),
        (changed(phone={"keys": [{"t": 0}]}), "phone"),
        (changed(actions=[{"at": 5, "do": "scroll", "selector": "main", "duration": 9}]), "actions.0.duration"),
    ],
)
def test_an_invalid_capture_plan_is_refused_with_the_field_at_fault(plan, field):
    assert f"« {field} »" in refusal(plan)


def test_the_plans_kept_in_the_repository_are_valid():
    plans = sorted((paths.VITRINE_DIR / "factory-live" / "plans").glob("*.json"))
    assert plans
    for path in plans:
        assert capture_plan.load(path)["app"] == "factory-live"
    assert capture_plan.load_source("factory-live").patch.is_file()


def step_track(points: list[tuple[float, float]], fps: int = 30) -> dict:
    """A track whose followed element stands at each given point, one frame per point, on a large stage."""
    frames = [
        {"track": {"issue": [{"rect": [x - 50, y - 20, 100, 40], "opacity": 1, "group": "a", "flags": []}]}}
        for x, y in points
    ]
    return {
        "fps": fps,
        "frames": frames,
        "window": {"width": 4000, "height": 4000},
        "stage": {"rect": [0, 0, 4000, 4000], "background": "rgb(0, 0, 0)"},
    }


CAMERA = {"follow": "issue", "scale": 2.0, "move": 0.5, "anchor": {"x": 0.5, "y": 0.4}, "dead_zone": 24}


@pytest.mark.acceptance("la trajectoire lissée ne dépasse jamais sa cible")
def test_the_smoothed_path_never_passes_its_target():
    # Two jumps, one back the other way, each held: the camera must reach each target without passing it.
    points = [(1000.0, 1200.0)] * 10 + [(1600.0, 1500.0)] * 40 + [(1300.0, 900.0)] * 40
    path = camera.path(step_track(points), CAMERA)
    goals = [camera.aim(point, 2.0, CAMERA["anchor"], [0, 0, 4000, 4000]) for point in points]
    for segment in ((0, 10), (10, 50), (50, 90)):
        start, end = path.centres[segment[0]], goals[segment[1] - 1]
        for centre in path.centres[segment[0] : segment[1]]:
            for axis in (0, 1):
                low, high = sorted((start[axis], end[axis]))
                assert low - 1e-9 <= centre[axis] <= high + 1e-9
        assert path.centres[segment[1] - 1] == pytest.approx(end)
    # Each move lasts the plan's half second, then the camera holds still.
    assert [round((last - first) / 30, 3) for first, last in path.moves] == [0.5, 0.5]
    assert scene.move_seconds(path, 30) == [{"start": 0.333, "seconds": 0.5}, {"start": 1.667, "seconds": 0.5}]


def test_a_retarget_during_a_move_still_never_passes_the_new_target():
    points = [(1000.0, 1000.0)] * 5 + [(2000.0, 1000.0)] * 6 + [(1500.0, 1000.0)] * 30
    path = camera.path(step_track(points), CAMERA)
    xs = [centre[0] for centre in path.centres]
    assert max(xs) < 2000.0
    assert xs[-1] == pytest.approx(1500.0)
    assert all(left <= right for left, right in pairwise(xs[:12]))


def test_a_small_drift_inside_the_dead_zone_does_not_move_the_camera():
    points = [(1000.0, 1000.0)] * 5 + [(1010.0, 1005.0)] * 20
    path = camera.path(step_track(points), CAMERA)
    assert path.moves == []
    assert len(set(map(tuple, path.poses))) == 1


def test_the_camera_follows_the_copy_that_is_arriving_and_never_leaves_the_stage():
    rows = [
        {"rect": [100, 100, 100, 40], "opacity": 0.9, "group": "brief", "flags": []},
        {"rect": [900, 100, 100, 40], "opacity": 0.0, "group": "implementation", "flags": ["data-arriving"]},
    ]
    assert camera.pick(rows, "data-arriving")["group"] == "implementation"
    assert camera.pick(rows, None)["group"] == "brief"
    stage = [200, 300, 1000, 900]
    cx, cy = camera.aim((210.0, 310.0), 2.0, {"x": 0.5, "y": 0.4}, stage)
    left, top, right, bottom = camera.window((cx, cy), 2.0)
    assert left >= stage[0]
    assert right <= stage[0] + stage[2]
    # The window (1280 tall) is taller than the stage (900): it is centred on it.
    assert (top + bottom) / 2 == pytest.approx(stage[1] + stage[3] / 2)


def test_the_smallest_text_counts_only_what_the_frame_shows_inside_the_stage():
    texts = [[100, 100, 50, 10, 12.0], [5000, 5000, 50, 10, 8.0], [700, 600, 80, 14, 14.4]]
    assert camera.smallest_text(texts, (500.0, 640.0), 2.0, [0, 0, 1440, 1600]) == pytest.approx(24.0)
    assert camera.smallest_text(texts, (500.0, 640.0), 2.0, [400, 0, 1040, 1600]) == pytest.approx(28.8)


def test_an_empty_band_is_measured_outside_the_subtitle_band():
    frame = np.full((2560, 1440), 9, dtype=np.uint8)
    frame[:, ::40] = 200  # a column every 40 px: no row is flat
    frame[100:400, :] = 9  # 300 flat rows
    frame[1424:1644, :] = 9  # the subtitle band, flat but reserved
    assert scene.empty_rows(frame) == 300


def test_titles_follow_the_group_of_the_followed_element():
    frames = []
    for group in ["brief"] * 30 + [None] * 3 + ["implementation"] * 30 + ["gate:failfirst"] * 30:
        rows = [] if group is None else [{"rect": [0, 0, 10, 10], "opacity": 1, "group": group, "flags": []}]
        frames.append({"track": {"issue": rows}})
    track = {"fps": 30, "frames": frames}
    found = scene.labels(track, {"follow": "issue", "labels": {"brief": "Le brief", "gate:failfirst": "La gate"}})
    assert [(label["text"], label["start"], label["end"]) for label in found] == [
        ("Le brief", 0.0, 33 / 30),
        ("La gate", 63 / 30, 93 / 30),
    ]


def timed_track(points: list[tuple[float, float]], start: float = 10.0) -> dict:
    """step_track with the scenario time of each frame, as the driver writes it."""
    track = step_track(points)
    for index, frame in enumerate(track["frames"]):
        frame["t"] = start + index / 30
    track["scenario"] = {"start": start, "end": start + len(points) / 30}
    return track


def test_a_cut_moves_the_camera_to_another_element_in_one_move():
    track = timed_track([(1000.0, 1000.0)] * 60)
    for frame in track["frames"]:
        frame["track"]["other"] = [{"rect": [2950, 2980, 100, 40], "opacity": 1, "group": None, "flags": []}]
    doc = CAMERA | {"cuts": [{"at": 11, "follow": "other", "move": 0.6}]}
    path = camera.path(track, doc)
    assert path.moves == [(30, 48)]
    assert path.centres[29] == pytest.approx(camera.aim((1000, 1000), 2.0, CAMERA["anchor"], [0, 0, 4000, 4000]))
    assert path.centres[-1] == pytest.approx(camera.aim((3000, 3000), 2.0, CAMERA["anchor"], [0, 0, 4000, 4000]))


def test_a_wide_cut_shows_the_whole_stage_and_its_texts_are_not_measured():
    track = timed_track([(1000.0, 1000.0)] * 90)
    track["stage"]["rect"] = [0, 0, 1000, 800]
    doc = CAMERA | {"cuts": [{"at": 11, "scale": "fit", "move": 1.0}]}
    path = camera.path(track, doc)
    assert path.poses[-1][0] == pytest.approx(1.44)  # 1440 / 1000: the stage's width fills the frame
    assert camera.window(path.centres[-1], 1.44)[0] == pytest.approx(0)
    track["text_sets"] = [[[700, 400, 50, 10, 4]]]
    for frame in track["frames"]:
        frame["texts"] = 0
    measured = scene.hold_text(track, path)
    assert measured["smallest_px"] == pytest.approx(8.0)  # 4 px at scale 2, before the cut; the wide shot is left out


def test_a_hold_keeps_the_camera_still_while_its_target_moves():
    points = [(1000.0, 1000.0)] * 30 + [(1000.0, 1000.0 - 20 * index) for index in range(30)]
    doc = CAMERA | {"cuts": [{"at": 10.9, "hold": True}]}
    path = camera.path(timed_track(points), doc)
    assert len({tuple(centre) for centre in path.centres}) == 1


def test_the_cursor_comes_in_presses_on_the_click_and_rides_the_camera():
    track = timed_track([(1000.0, 1000.0)] * 60)
    track["actions"] = [
        {"do": "click", "ran_at": 11.0, "result": {"rect": [990, 990, 20, 20]}},
        {"do": "click", "ran_at": 11.5, "cursor": False, "result": {"rect": [0, 0, 10, 10]}},
        {"do": "click", "ran_at": 5.0, "result": {"rect": [0, 0, 10, 10]}},
    ]
    path = camera.path(track, CAMERA)
    states = scene.cursor_states(track, path)
    assert states[0] is None and states[59] is None
    scale, x, y = path.poses[30]
    assert states[30][:2] == pytest.approx([x + scale * 1000, y + scale * 1000])
    assert states[30][3] == 0.86 and states[34][3] == 1.0
    assert states[5][0] > states[30][0]  # it came from the right


def test_the_phone_scene_draws_each_tap_and_the_notification(tmp_path):
    track = timed_track([(100.0, 100.0)] * 30) | {"plan": "essai", "scale": 3}
    track["actions"] = [{"do": "tap", "ran_at": 10.5, "result": {"rect": [100, 200, 40, 20]}}]
    phone = capture_plan.check(
        changed(
            device="iphone",
            window={"width": 390, "height": 844},
            camera=None,
            stage=None,
            phone={
                "keys": [{"t": 0, "ry": -20}, {"t": 1, "scale": 2.2}],
                "notification": {"at": 0.2, "title": "A <b>", "text": "B"},
            },
        )
    )["phone"]
    assert phone["keys"][1] == {"t": 1, "scale": 2.2, "rx": 0.0, "ry": -20, "rz": 0.0, "y": 0.0}
    config = scene.write_phone(tmp_path / "scene", track, phone, None)
    page = (tmp_path / "scene" / "index.html").read_text(encoding="utf-8")
    assert "{{" not in page and "A &lt;b&gt;" in page
    assert config["taps"] == [{"at": 0.5, "x": 120.0, "y": 210.0}]
    assert compose.outside_references(tmp_path / "scene") == []


def test_the_scene_is_written_whole_and_loads_only_its_own_files(tmp_path):
    points = [(1000.0, 1200.0)] * 10 + [(1600.0, 1500.0)] * 20
    track = step_track(points) | {"scale": 3, "plan": "essai"}
    for frame in track["frames"]:
        frame["track"]["issue"][0]["group"] = "brief"
    doc = CAMERA | {"blur": {"copies": 3, "shutter": 0.5}, "labels": {"brief": "Le <brief>"}}
    path = camera.path(track, doc)
    config = scene.write_project(tmp_path / "scene", track, doc, path)
    page = (tmp_path / "scene" / "index.html").read_text(encoding="utf-8")
    assert "{{" not in page
    assert page.count('src="assets/capture/capture.mp4"') == 3
    assert "Le &lt;brief&gt;" in page
    assert compose.outside_references(tmp_path / "scene") == []
    assert (tmp_path / "scene" / "assets" / "fonts" / scene.FONT).is_file()
    assert config["moving"].count(1) == 16  # one move of 15 frames, and the frame it starts on
    # The clip is made at the camera's scale (2), not the capture's (3): a hold shows it pixel for pixel.
    assert config["capture"] == {"width": 8000, "height": 8000, "dsf": 2.0}


def test_the_capture_scene_is_left_out_of_compose_and_its_fingerprint():
    assert chain.TEMPLATE
    assert not any("camera-follow" in name or "MonaSans" in name for name in chain.TEMPLATE)
    assert not any("/phone/" in name for name in chain.TEMPLATE)


def test_two_captures_are_identical_when_their_fingerprints_match(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name / "frames").mkdir(parents=True)
        for index in (1, 2):
            (tmp_path / name / "frames" / f"f_{index:06d}.png").write_bytes(b"image %d" % index)
        (tmp_path / name / "track.json").write_text("{}")
    first, second = fingerprints(tmp_path / "a", 2), fingerprints(tmp_path / "b", 2)
    assert first["all"] == second["all"]
    (tmp_path / "b" / "frames" / "f_000002.png").write_bytes(b"other")
    assert fingerprints(tmp_path / "b", 2)["all"] != first["all"]
    assert frame_count({"scenario": {"start": 55.5, "end": 64.5}, "fps": 30}) == 270


# --- the scenario variant on the pinned commit -----------------------------------------------------------------------

SHORTCUT_STEP = re.compile(r"at: ([0-9.]+),\s*run: \(state, now\) => \{(.*?)\n      \},\n    \}", re.S)
STATION = re.compile(r"patchIssue\(state, KEYS\.shortcut, \{[^}]*?station: '([a-z]+)'", re.S)


def shortcut_journey(app: Path) -> list[str]:
    """The stations of claude-cockpit#73 in the variant: its first one, then each one a step of the scenario gives
    it, in the order of their time."""
    initial = (app / "apps/web/src/demo/initial.ts").read_text(encoding="utf-8")
    summary = initial[initial.index("key: KEYS.shortcut,") :]
    first = re.search(r"station: '([a-z]+)'", summary).group(1)
    script = (app / "apps/web/src/demo/script.ts").read_text(encoding="utf-8")
    steps = sorted(
        (float(at), station) for at, body in SHORTCUT_STEP.findall(script) for station in STATION.findall(body)
    )
    return [first, *(station for _at, station in steps)]


@pytest.mark.acceptance("la variante de scénario s'applique au commit figé")
def test_the_scenario_variant_applies_to_the_pinned_commit(tmp_path):
    source = capture_plan.load_source("factory-live")
    target = tmp_path / "factory-live"
    try:
        demo.fetch(str(source.doc["repository"]), str(source.doc["commit"]), target, quiet_run)
    except demo.DemoError as exc:
        if os.environ.get("VF_REQUIRE_TOOLS") == "1":
            pytest.fail(f"commit figé de factory-live inaccessible : {exc}")
        pytest.skip(f"commit figé de factory-live inaccessible : {exc}")
    demo.apply_variant(target, source.patch, quiet_run)
    assert shortcut_journey(target) == [
        "intake",
        "brief",
        "implementation",
        "gate",
        "review",
        "merge",
        "ci",
        "deploy",
        "done",
    ]


def quiet_run(argv, cwd, env, what):
    done = subprocess.run(list(argv), cwd=cwd, env=dict(env), capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise demo.DemoError(f"{what} : {done.stderr.strip()[-300:]}")


def test_a_variant_that_does_not_fit_stops_the_build(tmp_path, make_repo):
    repository = make_repo({"a.txt": b"one\n"})
    subprocess.run(
        ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "a"],
        check=True,
        capture_output=True,
    )
    patch = tmp_path / "variant.patch"
    patch.write_text("--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-two\n+three\n")
    with pytest.raises(demo.DemoError, match="ne s'applique pas"):
        demo.apply_variant(repository, patch, quiet_run)
    assert (repository / "a.txt").read_text() == "one\n"


def test_a_build_is_keyed_by_everything_it_depends_on(tmp_path):
    folder = tmp_path / "factory-live"
    folder.mkdir()
    (folder / "scenario.patch").write_text("x")
    doc = json.loads((paths.VITRINE_DIR / "factory-live" / "source.json").read_text(encoding="utf-8"))
    source = capture_plan.Source(folder, doc)
    key = demo.build_key(source, "v24.22.1")
    (folder / "scenario.patch").write_text("y")
    assert demo.key_digest(demo.build_key(source, "v24.22.1")) != demo.key_digest(key)
    assert demo.key_digest(demo.build_key(source, "v24.22.2")) != demo.key_digest(key)


# --- the pinned Chromium ships as a zip ------------------------------------------------------------------------------


def zip_bytes(members: dict[str, tuple[bytes, int]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, (content, mode) in members.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            bundle.writestr(info, content)
    return buffer.getvalue()


def test_a_zip_is_extracted_without_its_top_folder_with_its_executable_bits(tmp_path):
    archive = tmp_path / "shell.zip"
    archive.write_bytes(zip_bytes({"top/run": (b"#!/bin/sh\n", 0o100755), "top/data/x.pak": (b"x", 0o100644)}))
    install.extract(archive, tmp_path / "out", 1)
    assert (tmp_path / "out" / "run").stat().st_mode & stat.S_IXUSR
    assert (tmp_path / "out" / "data" / "x.pak").read_bytes() == b"x"


@pytest.mark.parametrize(
    "members",
    [{"top/../../evil": (b"x", 0o100644)}, {"/etc/evil": (b"x", 0o100644)}, {"top/link": (b"/etc", 0o120777)}],
)
def test_a_zip_member_that_escapes_or_links_is_refused(tmp_path, members):
    archive = tmp_path / "bad.zip"
    archive.write_bytes(zip_bytes(members))
    with pytest.raises(install.InstallError):
        install.extract(archive, tmp_path / "out", 1)
    assert not (tmp_path / "evil").exists()
