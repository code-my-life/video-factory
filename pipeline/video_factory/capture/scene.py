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
