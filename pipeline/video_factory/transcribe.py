"""`transcribe`: the words of the take and their times, by whisper.cpp at its pinned version and model, on CPU.

whisper-cli runs in French at temperature 0 without fallback, with a fixed beam, a fixed number of threads and DTW
token timestamps (the preset of large-v3-turbo); flash attention is off, as DTW needs the attention weights. A fixed
prompt full of hesitations keeps them in the transcript (Whisper drops them otherwise), so `align` can find them.

A word ends where DTW puts the end of its last token, and starts where the word before it ended. The pauses come from
the sound itself: FFmpeg's silence detection splits the take into stretches of speech, and each word is held inside the
stretch where most of it lies, starting with the stretch when it is its first word and ending with it when its last.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from video_factory import media

LANGUAGE = "fr"
THREADS = 8
BEAM = 5
DTW_PRESET = "large.v3.turbo"
PROMPT = "Euh, alors, euh, bon, hum, ben, voilà."
SILENCE_DB = -40
SILENCE_MIN = 0.06
SPECIAL = re.compile(r"^\[_.*\]$|^<\|.*\|>$")
SPEECH = re.compile(r"\w")
SILENCE_START = re.compile(r"silence_start: (-?[0-9.]+)")
SILENCE_END = re.compile(r"silence_end: (-?[0-9.]+)")

Runner = Callable[[list[str]], None]


def audio_command(work: Path, output: Path) -> list[str | Path]:
    """The ffmpeg arguments for the 16 kHz mono WAV whisper reads."""
    return ["-i", work, "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", *media.BITEXACT, output]


def whisper_command(cli: Path, model: Path, audio: Path, output_base: Path) -> list[str]:
    """whisper-cli with every setting that changes its result written out."""
    return [
        str(cli),
        "-m",
        str(model),
        "-f",
        str(audio),
        "-l",
        LANGUAGE,
        "-tp",
        "0",
        "-nf",
        "-bs",
        str(BEAM),
        "-bo",
        str(BEAM),
        "-t",
        str(THREADS),
        "-nfa",
        "-dtw",
        DTW_PRESET,
        "--prompt",
        PROMPT,
        "-ojf",
        "-of",
        str(output_base),
        "-np",
    ]


def run_whisper(argv: list[str]) -> None:
    media.run(argv, "whisper-cli")


def silences(ffmpeg: Path, audio: Path, duration: float) -> list[tuple[float, float]]:
    """The silences of the audio (below SILENCE_DB for SILENCE_MIN or more), as (start, end) in seconds; a silence
    still running at the end closes at duration."""
    report = media.ffmpeg(
        ffmpeg,
        ["-i", audio, "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN}", "-f", "null", "-"],
        "détection des silences",
        loglevel="info",
    )
    starts = [max(0.0, float(value)) for value in SILENCE_START.findall(report)]
    ends = [float(value) for value in SILENCE_END.findall(report)]
    if len(ends) < len(starts):
        ends.append(duration)
    return [(round(start, 6), round(end, 6)) for start, end in zip(starts, ends, strict=True)]


def tokens_to_words(document: dict) -> list[dict]:
    """The words of whisper's full JSON: tokens joined at each leading space, punctuation kept with its word, each
    word with the DTW end of its last spoken token and the start of its segment."""
    words: list[dict] = []
    for segment in document.get("transcription", []):
        segment_start = segment["offsets"]["from"] / 1000
        first_of_segment = True
        for token in segment.get("tokens", []):
            text = token["text"]
            if SPECIAL.match(text.strip()) or not text:
                continue
            spoken = bool(SPEECH.search(text))
            if text.startswith(" ") or not words:
                if not spoken and words:
                    words[-1]["text"] += text.strip()
                    continue
                words.append({"text": text.strip(), "end": None, "p": [], "segment": segment_start})
                words[-1]["first"] = first_of_segment
                first_of_segment = False
            else:
                words[-1]["text"] += text
            if spoken:
                timestamp = token.get("t_dtw", -1)
                words[-1]["end"] = timestamp / 100 if timestamp >= 0 else token["offsets"]["to"] / 1000
                words[-1]["p"].append(token["p"])
    return [word for word in words if word["end"] is not None and SPEECH.search(word["text"])]


def speech_stretches(silent: Sequence[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    stretches, position = [], 0.0
    for start, end in silent:
        if start > position:
            stretches.append((position, start))
        position = max(position, end)
    if position < duration:
        stretches.append((position, duration))
    return stretches


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def place(raw: Sequence[dict], silent: Sequence[tuple[float, float]], duration: float) -> list[dict]:
    """Start and end of each word: DTW ends, starts at the previous end, then held in their stretch of speech."""
    stretches = speech_stretches(silent, duration) or [(0.0, duration)]
    spans = []
    previous = 0.0
    for word in raw:
        start = word["segment"] if word.get("first") else previous
        end = max(word["end"], start + 0.01)
        spans.append((start, min(end, duration)))
        previous = end
    homes = [max(range(len(stretches)), key=lambda k: (overlap(span, stretches[k]), -k)) for span in spans]
    placed = []
    for index, (word, (start, end)) in enumerate(zip(raw, spans, strict=True)):
        home = stretches[homes[index]]
        if index == 0 or homes[index - 1] != homes[index]:
            start = home[0]
        if index + 1 == len(raw) or homes[index + 1] != homes[index]:
            end = home[1]
        start, end = max(start, home[0]), min(end, home[1])
        if end <= start:
            end = min(home[1], start + 0.02)
        probabilities = word["p"]
        placed.append(
            {
                "text": word["text"],
                "start": round(start, 3),
                "end": round(end, 3),
                "p": round(sum(probabilities) / len(probabilities), 4) if probabilities else 0.0,
            }
        )
    return placed


def transcript(document: dict, silent: Sequence[tuple[float, float]], duration: float) -> dict:
    """The transcript the chain keeps: placed words, the silences, and the duration of the take."""
    return {
        "words": place(tokens_to_words(document), silent, duration),
        "silences": [[start, end] for start, end in silent],
        "duration": duration,
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
