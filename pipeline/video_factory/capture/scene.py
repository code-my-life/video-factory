"""The « camera follow » scene of a capture: a HyperFrames project written from templates/hyperframes/, checked by
`hyperframes check` and rendered in the pinned render image without the network, then measured.

The capture's frames become one lossless-looking clip (x264, as compose encodes its tracks); the camera path comes from
`camera`; the titles of the plan show while the followed element stands in their group, in the subtitle band. The
measures are the rules of the showcase videos, read on what was made, not assumed: how long each move lasts, the
smallest text of the app in the final image during the holds (from the sizes the driver read), and the tallest band
of the final frames left empty (a run of rows of one flat colour) outside the subtitle band.
"""

from __future__ import annotations

import json
import math
import shutil
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from video_factory import compose, media
from video_factory.capture import camera
from video_factory.paths import HYPERFRAMES_TEMPLATE
from video_factory.tools import Toolbox

TEMPLATE = "camera-follow"
FONT = "MonaSans-wght-latin.woff2"
FONT_LICENSE = "MonaSans-OFL.txt"
# The subtitle band of the showcase videos: compose's caption band (pixels of the 1440x2560 frame).
BAND = {"top": compose.CAPTION["top"], "height": compose.CAPTION["height"]}
EMPTY_TOLERANCE = 6  # grey levels: a row whose pixels all lie within this of each other is empty
MIN_TEXT = 26  # pixels: the smallest text of the app allowed in the final image during a hold
MAX_EMPTY_SHARE = 0.10  # of the frame's height: the tallest empty band allowed outside the subtitle band
MIN_CAMERA_SCALE = 1.6  # below this, a wide shot


class SceneError(Exception):
    """The scene cannot be made: the capture is incomplete, the project fails its check, or the render failed."""


def labels(track: Mapping[str, object], camera_doc: Mapping[str, object]) -> list[dict]:
    """The titles of the plan, each from the frame the followed element shows in its group to the next title."""
    names: Mapping[str, str] = camera_doc.get("labels", {})
    fps, frames = int(track["fps"]), track["frames"]
    seen = camera.groups(frames, str(camera_doc["follow"]), None)
    found: list[dict] = []
    current = None
    for index, group in enumerate(seen):
        if group is None or group == current:
            continue
        current = group
        if found and found[-1]["end"] is None:
            found[-1]["end"] = round(index / fps, 6)
        if group in names:
            found.append({"text": names[group], "group": group, "start": round(index / fps, 6), "end": None})
    duration = len(frames) / fps
    for label in found:
        label["end"] = label["end"] if label["end"] is not None else round(duration, 6)
    return found


def layers(copies: int, duration: str) -> str:
    return "\n".join(
        f'      <div id="cam-{k}" class="cam" data-layout-allow-overflow>\n'
        f'        <video id="capture-{k}" class="clip" src="assets/capture/capture.mp4" data-start="0" '
        f'data-duration="{duration}" data-track-index="0" muted playsinline></video>\n'
        "      </div>"
        for k in range(copies)
    )


def label_clips(found: Sequence[Mapping[str, object]]) -> str:
    return "\n".join(
        f'      <div id="label-{index}" class="label clip" data-start="{label["start"]:.6f}" '
        f'data-duration="{float(label["end"]) - float(label["start"]):.6f}" data-track-index="1">\n'
        f'        <div class="pill">{escape(str(label["text"]))}</div>\n'
        "      </div>"
        for index, label in enumerate(found)
    )


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CURSOR_LEAD = 0.9  # seconds before a click the cursor appears
CURSOR_TRAVEL = 0.6  # seconds it takes to reach its target
CURSOR_FROM = (200.0, 260.0)  # where it comes from, in frame pixels from its target
CURSOR_HEIGHT = 154  # pixels: 6 % of the frame's height


def clicks(track: Mapping[str, object]) -> list[dict]:
    """The clicks and taps the scene draws: those of the filmed range with a target, cursor left on."""
    scenario = track.get("scenario", {"start": 0, "end": 0})
    found = []
    for action in track.get("actions", []):
        if action.get("do") not in ("click", "tap") or action.get("cursor", True) is False:
            continue
        rect = (action.get("result") or {}).get("rect")
        if not rect or not scenario["start"] <= float(action["ran_at"]) < scenario["end"]:
            continue
        found.append({"at": float(action["ran_at"]) - float(scenario["start"]), "point": camera.centre(rect)})
    return found


def cursor_states(track: Mapping[str, object], path: camera.Path) -> list[list[float] | None]:
    """The cursor at each frame of the scene, [x, y, opacity, press scale] in frame pixels, or None: it comes in
    from below right, eased, reaches the click's target, presses, holds, then fades; it rides the camera."""
    fps = int(track["fps"])
    states: list[list[float] | None] = [None] * len(path.poses)
    lead, travel = round(CURSOR_LEAD * fps), round(CURSOR_TRAVEL * fps)
    for click in clicks(track):
        frame = math.ceil(click["at"] * fps - 1e-6)
        for index in range(max(0, frame - lead), min(len(states), frame + 17)):
            scale, x, y = path.poses[index]
            tx, ty = x + scale * click["point"][0], y + scale * click["point"][1]
            moved = camera.ease(min(1.0, max(0.0, (index - (frame - lead) - 3) / travel)))
            done = 1 - (1 - moved) ** 2
            px, py = tx + CURSOR_FROM[0] * (1 - done), ty + CURSOR_FROM[1] * (1 - done)
            opacity = min(1.0, (index - (frame - lead) + 1) / 5)
            if index > frame + 10:
                opacity = max(0.0, 1 - (index - frame - 10) / 6)
            press = 0.86 if frame <= index < frame + 3 else 1.0
            states[index] = [round(px, 2), round(py, 2), round(opacity, 3), press]
    return states


def clip_scale(track: Mapping[str, object], camera_doc: Mapping[str, object]) -> float:
    """Pixels of the scene's clip per CSS pixel: the camera's scale, so a hold shows the clip pixel for pixel (the x3
    capture is resampled once, with Lanczos), never more than the capture has."""
    return min(float(track["scale"]), float(camera_doc["scale"]))


def config(track: Mapping[str, object], camera_doc: Mapping[str, object], path: camera.Path, found: list[dict]) -> dict:
    window, scale = track["window"], clip_scale(track, camera_doc)
    stage = track["stage"]
    frames = len(track["frames"])
    return {
        "fps": int(track["fps"]),
        "duration": frames / int(track["fps"]),
        "capture": {"width": round(window["width"] * scale), "height": round(window["height"] * scale), "dsf": scale},
        "stage": stage["rect"],
        "ground": stage["background"],
        "path": path.poses,
        "moving": [1 if moving else 0 for moving in path.moving()],
        "blur": camera_doc["blur"],
        "labels": [{"text": label["text"], "start": label["start"], "end": label["end"]} for label in found],
        "cursor": cursor_states(track, path),
        "cursor_height": CURSOR_HEIGHT,
        "band": BAND,
    }


def write_project(
    folder: Path,
    track: Mapping[str, object],
    camera_doc: Mapping[str, object],
    path: camera.Path,
    template: Path = HYPERFRAMES_TEMPLATE,
) -> dict:
    """index.html (the scene, its one root), the font and its licence; the clip and GSAP are placed afterwards."""
    found = labels(track, camera_doc)
    doc = config(track, camera_doc, path, found)
    duration = compose.seconds(len(track["frames"]))
    values = {
        "DURATION": duration,
        "LAYERS": layers(int(camera_doc["blur"]["copies"]), duration),
        "LABELS": label_clips(found),
        "CONFIG": compose.script_json(doc),
    }
    (folder / "assets" / "capture").mkdir(parents=True)
    (folder / "assets" / "fonts").mkdir(parents=True)
    scene_template = template / TEMPLATE
    page = compose.fill((scene_template / "index.html").read_text("utf-8"), values)
    (folder / "index.html").write_text(page, "utf-8")
    for name in (FONT, FONT_LICENSE):
        shutil.copyfile(scene_template / "assets" / "fonts" / name, folder / "assets" / "fonts" / name)
    return doc


def encode_capture(ffmpeg: Path, frames_folder: Path, fps: int, size: tuple[int, int], output: Path) -> None:
    """The capture's PNG frames as one clip at the scene's size, encoded as compose encodes its tracks (bit-exact,
    fixed threads)."""
    pattern = frames_folder / "f_%06d.png"
    filters = f"scale={size[0]}:{size[1]}:flags=lanczos,{media.BT709}"
    args = ["-framerate", str(fps), "-start_number", "1", "-i", pattern, "-vf", filters]
    media.ffmpeg(ffmpeg, [*args, *compose.encode_args(output)], "capture, extrait")


def move_seconds(path: camera.Path, fps: int) -> list[dict]:
    """Each move: when it starts and how long the camera actually travels (frames whose pose changes)."""
    found = []
    for first, last in path.moves:
        changing = [
            index
            for index in range(first, min(last + 1, len(path.poses)))
            if index > 0 and path.poses[index] != path.poses[index - 1]
        ]
        if changing:
            found.append({"start": round(first / fps, 3), "seconds": round(len(changing) / fps, 3)})
    return found


def hold_text(track: Mapping[str, object], path: camera.Path) -> dict:
    """The smallest text of the app in the final image, over the frames where the camera holds still."""
    stage = track["stage"]["rect"]
    sets = track["text_sets"]
    smallest, where = None, None
    for index in path.holds():
        if path.poses[index][0] < MIN_CAMERA_SCALE - 1e-6:
            continue  # a wide shot (« fit ») shows the whole stage, its texts are not read
        frame = track["frames"][index]
        size = camera.smallest_text(sets[frame["texts"]], path.centres[index], path.poses[index][0], stage)
        if size is not None and (smallest is None or size < smallest):
            smallest, where = size, index
    return {
        "smallest_px": round(smallest, 2) if smallest is not None else None,
        "frame": where,
        "holds": len(path.holds()),
        "frames": len(path.poses),
    }


def empty_rows(pixels: np.ndarray, band: Mapping[str, int] = BAND) -> int:
    """The tallest run of empty rows (one flat colour) of a grey frame, the subtitle band left out."""
    flat = (pixels.max(axis=1).astype(int) - pixels.min(axis=1).astype(int)) <= EMPTY_TOLERANCE
    flat[band["top"] : band["top"] + band["height"]] = False
    longest = run = 0
    for row in flat:
        run = run + 1 if row else 0
        longest = max(longest, run)
    return longest


def empty_band(ffmpeg: Path, frames_folder: Path) -> dict:
    """The tallest empty band over all rendered frames, in pixels and as a share of the height."""
    pattern = frames_folder / "frame_%06d.png"
    sequence = ["-framerate", str(compose.FPS), "-start_number", "1"]
    tallest, where = 0, None
    width, height = compose.WIDTH, compose.HEIGHT
    for index, pixels in enumerate(media.frames(ffmpeg, pattern, width, height, "null", "gray", sequence)):
        found = empty_rows(pixels)
        if found > tallest:
            tallest, where = found, index
    return {"rows": tallest, "share": round(tallest / height, 4), "frame": where}


def encode_video(ffmpeg: Path, frames_folder: Path, output: Path) -> None:
    pattern = frames_folder / "frame_%06d.png"
    args = ["-framerate", str(compose.FPS), "-start_number", "1", "-i", pattern, "-vf", media.BT709]
    media.ffmpeg(ffmpeg, [*args, *compose.encode_args(output)], "scène, vidéo")


def make(
    out: Path, track: Mapping[str, object], camera_doc: Mapping[str, object], toolbox: Toolbox, render: bool = True
) -> dict:
    """The scene of a capture in out/scene/: written, checked, rendered to out/<plan>.mp4 and measured."""
    if int(track["fps"]) != compose.FPS:
        raise SceneError(f"la scène se rend à {compose.FPS} images par seconde, la capture en a {track['fps']}")
    path = camera.path(track, camera_doc)
    project, work, rendered = out / "scene", out / "scene-work", out / "scene-render"
    for folder in (project, work, rendered):
        if folder.exists():
            shutil.rmtree(folder)
    work.mkdir(parents=True)
    rendered.mkdir(parents=True)
    doc = write_project(project, track, camera_doc, path)
    compose.ship_libraries(project, toolbox)
    size = (doc["capture"]["width"], doc["capture"]["height"])
    encode_capture(
        toolbox.ffmpeg, out / "frames", int(track["fps"]), size, project / "assets" / "capture" / "capture.mp4"
    )
    outside = compose.outside_references(project) + [f"absent : {name}" for name in compose.missing_files(project)]
    if outside:
        raise SceneError("la scène ne doit charger que ses propres fichiers :\n" + "\n".join(f"- {o}" for o in outside))
    image = toolbox.image("hyperframes-render")
    environment = dict(toolbox.entry("hyperframes")["env"])
    report = compose.check_project(compose.check_command(image, environment, project, work))
    (out / "check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    measures: dict = {
        "check": {
            "ok": report.get("ok"),
            "errors": compose.check_errors(report),
            "warnings": compose.check_warnings(report),
        },
        "camera": {
            "scale": camera_doc["scale"],
            "move_setting": camera_doc["move"],
            "moves": move_seconds(path, int(track["fps"])),
        },
        "texts": hold_text(track, path) | {"minimum_px": MIN_TEXT},
        "blur": dict(camera_doc["blur"]),
    }
    if render:
        started = time.monotonic()
        media.run(compose.render_command(image, environment, project, rendered, work), "rendu de la scène")
        measures["render_seconds"] = round(time.monotonic() - started, 1)
        frames = compose.rendered(rendered, len(path.poses))
        measures["empty"] = empty_band(toolbox.ffmpeg, frames) | {"maximum_share": MAX_EMPTY_SHARE}
        encode_video(toolbox.ffmpeg, frames, out / f"{track['plan']}.mp4")
    (out / "mesures.json").write_text(json.dumps(measures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return measures


PHONE_TEMPLATE = "phone"
PHONE_SLICES = 6  # the phone's edge: slices behind its body, 6 capture pixels apart
NOTE_CENTRE = 70  # CSS pixels of the screen: the middle of the notification, where its tap lands
APP_ICON = "icons/icon-192.png"  # in the built demo: the app's own icon, on its notification


def taps(track: Mapping[str, object]) -> list[dict]:
    """The taps the phone scene draws, when (seconds of the plan) and where (CSS pixels of the screen)."""
    return [
        {"at": round(click["at"], 6), "x": round(click["point"][0], 2), "y": round(click["point"][1], 2)}
        for click in clicks(track)
    ]


def note_html(note: Mapping[str, object] | None, icon: bool) -> str:
    if not note:
        return ""
    picture = '<img src="assets/icon.png" alt="" />' if icon else '<div class="icon"></div>'
    return (
        f'{picture}<div><div class="head"><span>{escape(str(note["app"]))}</span><span>maintenant</span></div>'
        f'<div class="title">{escape(str(note["title"]))}</div>'
        f'<div class="text">{escape(str(note["text"]))}</div></div>'
    )


def write_phone(folder: Path, track: Mapping[str, object], phone: Mapping[str, object], icon: Path | None) -> dict:
    """index.html of the phone scene, its font and the app's icon; the clip and GSAP are placed afterwards."""
    frames = len(track["frames"])
    note = phone.get("notification")
    doc = {
        "fps": int(track["fps"]),
        "duration": frames / int(track["fps"]),
        "keys": [dict(key) for key in phone["keys"]],
        "taps": taps(track),
        "notification": ({"at": note["at"], "centre": NOTE_CENTRE} if note else None),
    }
    duration = compose.seconds(frames)
    values = {
        "DURATION": duration,
        "LAYERS": "\n".join('        <div class="slice"></div>' for _ in range(PHONE_SLICES)),
        "NOTE": note_html(note, icon is not None),
        "CONFIG": compose.script_json(doc),
    }
    (folder / "assets" / "capture").mkdir(parents=True)
    (folder / "assets" / "fonts").mkdir(parents=True)
    page = compose.fill((HYPERFRAMES_TEMPLATE / PHONE_TEMPLATE / "index.html").read_text("utf-8"), values)
    (folder / "index.html").write_text(page, "utf-8")
    for name in (FONT, FONT_LICENSE):
        shutil.copyfile(HYPERFRAMES_TEMPLATE / TEMPLATE / "assets" / "fonts" / name, folder / "assets" / "fonts" / name)
    if icon is not None:
        shutil.copyfile(icon, folder / "assets" / "icon.png")
    return doc


def make_phone(
    out: Path,
    track: Mapping[str, object],
    phone: Mapping[str, object],
    toolbox: Toolbox,
    demo: Path | None = None,
    render: bool = True,
) -> dict:
    """The phone scene of an iPhone capture in out/scene/: written, checked, rendered to out/<plan>.mp4."""
    if int(track["fps"]) != compose.FPS:
        raise SceneError(f"la scène se rend à {compose.FPS} images par seconde, la capture en a {track['fps']}")
    project, work, rendered = out / "scene", out / "scene-work", out / "scene-render"
    for folder in (project, work, rendered):
        if folder.exists():
            shutil.rmtree(folder)
    work.mkdir(parents=True)
    rendered.mkdir(parents=True)
    icon = demo / APP_ICON if demo is not None and (demo / APP_ICON).is_file() else None
    doc = write_phone(project, track, phone, icon)
    compose.ship_libraries(project, toolbox)
    window, scale = track["window"], int(track["scale"])
    size = (window["width"] * 3, window["height"] * 3)
    if scale != 3:
        raise SceneError("la scène téléphone se fait d'une capture en x3")
    encode_capture(toolbox.ffmpeg, out / "frames", doc["fps"], size, project / "assets" / "capture" / "capture.mp4")
    outside = compose.outside_references(project) + [f"absent : {name}" for name in compose.missing_files(project)]
    if outside:
        raise SceneError("la scène ne doit charger que ses propres fichiers :\n" + "\n".join(f"- {o}" for o in outside))
    image = toolbox.image("hyperframes-render")
    environment = dict(toolbox.entry("hyperframes")["env"])
    report = compose.check_project(compose.check_command(image, environment, project, work))
    (out / "check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    smallest = min(float(key["scale"]) for key in phone["keys"])
    measures: dict = {
        "check": {
            "ok": report.get("ok"),
            "errors": compose.check_errors(report),
            "warnings": compose.check_warnings(report),
        },
        "phone": {"smallest_scale": smallest, "taps": len(doc["taps"])},
    }
    if render:
        started = time.monotonic()
        media.run(compose.render_command(image, environment, project, rendered, work), "rendu de la scène")
        measures["render_seconds"] = round(time.monotonic() - started, 1)
        frames = compose.rendered(rendered, len(track["frames"]))
        encode_video(toolbox.ffmpeg, frames, out / f"{track['plan']}.mp4")
    (out / "mesures.json").write_text(json.dumps(measures, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return measures
