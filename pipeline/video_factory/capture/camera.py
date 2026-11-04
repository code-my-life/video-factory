"""The camera that follows an element of a capture, in a 1440x2560 frame: where it looks at each frame, smoothed.

The followed element gives a target per frame: the centre of its visible copy, or of the copy that is arriving (the app
draws an issue in the box it is heading for as soon as it leaves the previous one), so the camera leaves with it. The
camera puts that target at its anchor in the frame, at its scale, and never lets its window leave the stage. It moves
only when its target has gone further than the dead zone, and then in one eased move of fixed duration from where it
is to where it should be: no spring, so no overshoot, and every move lasts exactly `move` seconds. Between moves it
holds still: those are the holds, where the interface acts and the text is read.

A camera pose is [scale, x, y]: output pixels per CSS pixel, and where the capture's CSS origin lands in the frame.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

FRAME_W, FRAME_H = 1440, 2560

Point = tuple[float, float]
Rect = Sequence[float]


@dataclass(frozen=True)
class Path:
    """A camera path: one pose per frame, the moves (first and last frame of each) and the frames it holds still."""

    poses: list[list[float]]
    centres: list[Point]
    moves: list[tuple[int, int]]

    def moving(self) -> list[bool]:
        """For each frame, whether the camera is between two different poses around it (the blur needs it)."""
        found = [False] * len(self.poses)
        for first, last in self.moves:
            for index in range(max(first, 0), min(last + 1, len(found))):
                found[index] = True
        return found

    def holds(self) -> list[int]:
        return [index for index, moving in enumerate(self.moving()) if not moving]


def centre(rect: Rect) -> Point:
    return (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2)


def pick(rows: Sequence[Mapping[str, object]], arriving: str | None) -> Mapping[str, object] | None:
    """The copy of the element the camera aims at: the one arriving, else the most visible one."""
    if arriving:
        coming = [row for row in rows if arriving in row.get("flags", [])]
        if coming:
            return coming[0]
    shown = [row for row in rows if float(row.get("opacity", 1)) > 0.5]
    return max(shown, key=lambda row: float(row.get("opacity", 1)), default=None)


def targets(frames: Sequence[Mapping[str, object]], follow: str, arriving: str | None) -> list[Point | None]:
    """The followed point of each frame (None where the element is nowhere to be seen)."""
    found: list[Point | None] = []
    for frame in frames:
        row = pick(frame["track"].get(follow, []), arriving)
        found.append(centre(row["rect"]) if row else None)
    return found


def groups(frames: Sequence[Mapping[str, object]], follow: str, arriving: str | None) -> list[str | None]:
    """The group (the station, for an issue) of the followed element at each frame, as the camera sees it."""
    found = []
    for frame in frames:
        row = pick(frame["track"].get(follow, []), arriving)
        found.append(row.get("group") if row else None)
    return found


def clamp_axis(low: float, size: float, stage_low: float, stage_size: float) -> float:
    """The start of a window of size along an axis, moved inside the stage; a window larger than the stage is
    centred on it."""
    if size >= stage_size:
        return stage_low + (stage_size - size) / 2
    return min(max(low, stage_low), stage_low + stage_size - size)


def aim(point: Point, scale: float, anchor: Mapping[str, float], stage: Rect) -> Point:
    """The centre of the window, in CSS pixels, that puts point at the anchor without leaving the stage."""
    width, height = FRAME_W / scale, FRAME_H / scale
    left = clamp_axis(point[0] - anchor["x"] * width, width, stage[0], stage[2])
    top = clamp_axis(point[1] - anchor["y"] * height, height, stage[1], stage[3])
    return (left + width / 2, top + height / 2)


def ease(progress: float) -> float:
    """Cubic ease-in-out on [0, 1]: monotonic, so a move never passes its end."""
    if progress <= 0:
        return 0.0
    if progress >= 1:
        return 1.0
    if progress < 0.5:
        return 4 * progress**3
    return 1 - (-2 * progress + 2) ** 3 / 2


def smooth(
    goals: Sequence[Point], fps: int, move: float, dead_zone: float
) -> tuple[list[Point], list[tuple[int, int]]]:
    """The camera's centre at each frame, and its moves: a new move starts when the goal leaves the dead zone around
    the current aim, from where the camera is, and reaches the goal in `move` seconds."""
    steps = max(1, round(move * fps))
    position = aim_point = goals[0]
    origin, started = position, None
    centres: list[Point] = []
    moves: list[tuple[int, int]] = []
    for index, goal in enumerate(goals):
        if math.dist(goal, aim_point) > dead_zone:
            origin, aim_point, started = position, goal, index
            moves.append((index, index + steps))
        if started is not None:
            done = ease((index - started) / steps)
            position = (origin[0] + (aim_point[0] - origin[0]) * done, origin[1] + (aim_point[1] - origin[1]) * done)
            if index - started >= steps:
                position, started = aim_point, None
        centres.append(position)
    return centres, merge(moves)


def merge(moves: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Moves that overlap (a goal that changed during a move) as one."""
    merged: list[tuple[int, int]] = []
    for first, last in moves:
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))
    return merged


def pose(centre_point: Point, scale: float) -> list[float]:
    return [
        round(scale, 4),
        round(FRAME_W / 2 - centre_point[0] * scale, 3),
        round(FRAME_H / 2 - centre_point[1] * scale, 3),
    ]


def path(track: Mapping[str, object], camera: Mapping[str, object]) -> Path:
    """The camera path of a capture: its track (positions per frame and the stage) and the plan's camera."""
    frames = track["frames"]
    stage = (
        track["stage"]["rect"] if track.get("stage") else [0, 0, track["window"]["width"], track["window"]["height"]]
    )
    points = targets(frames, str(camera["follow"]), camera.get("arriving"))
    known = [point for point in points if point is not None]
    if not known:
        raise ValueError(f"« {camera['follow']} » n'est visible sur aucune image")
    filled, last = [], known[0]
    for point in points:
        last = point or last
        filled.append(last)
    scale = float(camera["scale"])
    goals = [aim(point, scale, camera["anchor"], stage) for point in filled]
    centres, moves = smooth(goals, int(track["fps"]), float(camera["move"]), float(camera["dead_zone"]))
    return Path([pose(point, scale) for point in centres], centres, moves)


def window(centre_point: Point, scale: float) -> tuple[float, float, float, float]:
    """The CSS rectangle (left, top, right, bottom) the frame shows around a centre."""
    width, height = FRAME_W / scale, FRAME_H / scale
    return (
        centre_point[0] - width / 2,
        centre_point[1] - height / 2,
        centre_point[0] + width / 2,
        centre_point[1] + height / 2,
    )


def smallest_text(texts: Sequence[Sequence[float]], centre_point: Point, scale: float, stage: Rect) -> float | None:
    """The smallest text the frame shows, in output pixels: every text that crosses both the window and the stage
    (outside the stage the scene shows only its ground)."""
    left, top, right, bottom = window(centre_point, scale)
    left, top = max(left, stage[0]), max(top, stage[1])
    right, bottom = min(right, stage[0] + stage[2]), min(bottom, stage[1] + stage[3])
    sizes = [
        size * scale
        for x, y, width, height, size in texts
        if x < right and x + width > left and y < bottom and y + height > top
    ]
    return min(sizes, default=None)
