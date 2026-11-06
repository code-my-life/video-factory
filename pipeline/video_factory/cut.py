"""`cut`: the edit decision list of a video, from the aligned words.

The video keeps the words that are said once and for all: the kept words and the words outside the script, from the
first kept word to the last. Between two of them, a pause longer than MAX_SILENCE, or one that held a filler or a
retake, is brought down to KEPT_SILENCE (half of it after the first word, half before the next). A cut never falls
inside a kept word: the step refuses the list rather than cut one. The pieces of a word whisper heard apart (« Factory »
« Live » kept for « factory-live », marked « joined » by align) are cut like two words, a long pause between them
shortened too, then listed as one said word, so the captions show it once.

Times are seconds on the sample grid of the voice (48 kHz); a segment may start between two frames, and the video
shows, at each output frame, the source frame on screen at that instant (`source_frames`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise

from video_factory.align import FILLER, KEPT, OFF_SCRIPT, RETAKE

MAX_SILENCE = 0.400
KEPT_SILENCE = 0.150
SAMPLE_RATE = 48000
FPS = 30
EPSILON = 1e-6


class CutError(Exception):
    """The decision list would cut inside a kept word, or there is nothing to keep."""


def on_grid(seconds: float, up: bool) -> float:
    """seconds moved to the 48 kHz sample grid, up or down, so a boundary never moves into a word."""
    samples = seconds * SAMPLE_RATE
    snapped = math.ceil(samples - EPSILON) if up else math.floor(samples + EPSILON)
    return snapped / SAMPLE_RATE


def retained(words: Sequence[dict]) -> list[dict]:
    """The words the video says: kept and off-script words, from the first kept word to the last."""
    kept = [index for index, word in enumerate(words) if word["label"] == KEPT]
    if not kept:
        raise CutError("aucun mot gardé : l'alignement n'a trouvé aucun mot du script dans la prise")
    return [word for word in words[kept[0] : kept[-1] + 1] if word["label"] in (KEPT, OFF_SCRIPT)]


def pause_cuts(words: Sequence[dict], said: Sequence[dict]) -> list[tuple[float, float]]:
    """The parts of the gaps between said words that go. A gap that held a filler or a retake loses them whole and
    keeps at most half of KEPT_SILENCE of the pause on each side; a pause longer than MAX_SILENCE keeps KEPT_SILENCE."""
    removed = [word for word in words if word["label"] in (FILLER, RETAKE)]
    cuts = []
    half = KEPT_SILENCE / 2
    for before, after in pairwise(said):
        gap_start, gap_end = before["end"], after["start"]
        inside = [word for word in removed if word["start"] < gap_end and word["end"] > gap_start]
        if inside:
            first = max(gap_start, min(word["start"] for word in inside))
            last = min(gap_end, max(word["end"] for word in inside))
            start = gap_start + min(half, first - gap_start)
            end = gap_end - min(half, gap_end - last)
        elif gap_end - gap_start > MAX_SILENCE:
            start, end = gap_start + half, gap_end - half
        else:
            continue
        if end > start:
            cuts.append((start, end))
    return cuts


def merge(intervals: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def seconds(value: float) -> str:
    return f"{value:.2f} s".replace(".", ",")


def segments_of(keep: Sequence[tuple[float, float]]) -> list[dict]:
    found, position = [], 0.0
    for start, end in keep:
        found.append({"src_start": start, "src_end": end, "out_start": round(position, 9)})
        position += end - start
    return found


def keep_intervals(span: tuple[float, float], cuts: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """span minus the cuts, boundaries on the sample grid (kept parts grow by less than a sample, never shrink)."""
    keep, position = [], span[0]
    for start, end in merge(cuts):
        if end <= span[0] or start >= span[1]:
            continue
        if start > position:
            keep.append((position, start))
        position = max(position, end)
    if position < span[1]:
        keep.append((position, span[1]))
    snapped = [(on_grid(start, up=False), on_grid(end, up=True)) for start, end in keep]
    return merge(snapped)


def output_time(segments: Sequence[dict], source: float) -> float:
    for segment in segments:
        if segment["src_start"] - EPSILON <= source <= segment["src_end"] + EPSILON:
            return segment["out_start"] + source - segment["src_start"]
    raise CutError(f"{seconds(source)} n'est dans aucun segment gardé")


def problems(segments: Sequence[dict], said: Sequence[dict]) -> list[str]:
    """Every said word lies whole inside one kept segment; a word split or shortened by a cut is named."""
    found = []
    for word in said:
        inside = any(
            segment["src_start"] - EPSILON <= word["start"] and word["end"] <= segment["src_end"] + EPSILON
            for segment in segments
        )
        if not inside:
            where = f"{seconds(word['start'])} à {seconds(word['end'])}"
            found.append(f"coupe dans le mot gardé « {word['text']} » ({where})")
    return found


def decide(words: Sequence[dict], duration: float) -> dict:
    """The decision list: kept source segments, their place in the output, and each said word in output time."""
    said = retained(words)
    half = KEPT_SILENCE / 2
    span = (max(0.0, said[0]["start"] - half), min(duration, said[-1]["end"] + half))
    segments = segments_of(keep_intervals(span, pause_cuts(words, said)))
    found = problems(segments, said)
    if found:
        raise CutError("\n".join(found))
    total = sum(segment["src_end"] - segment["src_start"] for segment in segments)
    return {
        "fps": FPS,
        "sample_rate": SAMPLE_RATE,
        "duration": round(total, 9),
        "frames": math.ceil(total * FPS - EPSILON),
        "segments": segments,
        "words": said_words(said, segments),
    }


def said_words(said: Sequence[dict], segments: list[dict]) -> list[dict]:
    """Each said word in source and output time; a piece joined to the word before it (align) extends that word."""
    found: list[dict] = []
    for word in said:
        end = round(output_time(segments, word["end"]), 6)
        if word.get("joined") and found:
            found[-1] |= {"text": f"{found[-1]['text']} {word['text']}", "src_end": word["end"], "end": end}
            continue
        found.append(
            {
                "text": word["text"],
                "label": word["label"],
                "script": word["script"],
                "src_start": word["start"],
                "src_end": word["end"],
                "start": round(output_time(segments, word["start"]), 6),
                "end": end,
            }
        )
    return found


def source_frames(edl: dict) -> list[int]:
    """For each output frame, the source frame on screen at that instant of the kept source."""
    found, fps = [], edl["fps"]
    segments = edl["segments"]
    index = 0
    for frame in range(edl["frames"]):
        moment = frame / fps
        while index + 1 < len(segments) and moment >= segments[index + 1]["out_start"] - EPSILON:
            index += 1
        segment = segments[index]
        source = min(segment["src_start"] + moment - segment["out_start"], segment["src_end"] - EPSILON)
        found.append(math.floor(source * fps + EPSILON))
    return found
