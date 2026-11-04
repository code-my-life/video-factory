"""`scan`: every frame of the working copy through the face detector; the frames with a face are to be removed.

The report gives frame numbers, times and scores, never an image. Consecutive frames with a face form a range, widened
by MARGIN frames on each side (the detector can miss the first or last frame of a slipping mask); `cut` removes the
ranges, and refuses when one falls inside a kept word.
"""

from __future__ import annotations

from pathlib import Path

from video_factory import faces, media

MARGIN = 3  # frames added before and after each range with a face


def frame_scores(ffmpeg: Path, video: Path, detector: faces.Detector) -> list[float]:
    """The face score of each frame, read at 144x256."""
    scale = f"scale={faces.WIDTH}:{faces.HEIGHT}:flags=area"
    return [detector.score(frame) for frame in media.frames(ffmpeg, video, faces.WIDTH, faces.HEIGHT, scale)]


def ranges(flagged: list[int], count: int, margin: int = MARGIN) -> list[tuple[int, int]]:
    """Runs of flagged frame numbers, each widened by margin and kept within [0, count), merged when they touch."""
    merged: list[tuple[int, int]] = []
    for frame in flagged:
        first, last = max(0, frame - margin), min(count - 1, frame + margin)
        if merged and first <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))
    return merged


def report(scores: list[float], threshold: float = faces.THRESHOLD, fps: int = media.FPS) -> dict:
    """The scan report: each frame with a face (number, time, score), and the ranges to remove (frames, seconds)."""
    flagged = [frame for frame, score in enumerate(scores) if score >= threshold]
    return {
        "threshold": threshold,
        "frames": len(scores),
        "faces": [
            {"frame": frame, "time": round(frame / fps, 3), "score": round(scores[frame], 4)} for frame in flagged
        ],
        "ranges": [
            {"first_frame": first, "last_frame": last, "start": first / fps, "end": (last + 1) / fps}
            for first, last in ranges(flagged, len(scores))
        ],
    }
