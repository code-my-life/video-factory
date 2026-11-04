"""`voice`: the voice of the video, cut by the decision list, cleaned, coloured, then brought to -14 LUFS.

Each kept segment of the take's sound is cut on the 48 kHz sample grid, with 4 ms fades at its ends so no cut clicks.
Then a fixed chain: a high-pass and a denoiser, an equaliser (less mud, more presence), a compressor, and the « casque »
colour: a band limited to the voice, a light saturation, and a short resonance like the inside of a helmet. Last, the
loudness in two passes (FFmpeg's loudnorm, measured then applied linearly) to -14 LUFS integrated with the true peak at
-2 dBTP, which leaves room under the -1 dBTP bound for the music and the AAC encoder.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from video_factory import media

FADE = 0.004
TARGET_LUFS = -14.0
TARGET_PEAK = -2.0
TARGET_LRA = 11.0
CLEAN = [
    "highpass=f=80",
    "afftdn=nr=10:nf=-45",
    "equalizer=f=250:t=q:w=1:g=-2",
    "equalizer=f=3500:t=q:w=1:g=3",
    "acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2",
]
# The « casque » colour: a fixed chain, light by design.
HELMET = [
    "highpass=f=170",
    "lowpass=f=6500",
    "volume=4dB",
    "asoftclip=type=tanh",
    "volume=-4dB",
    "aecho=in_gain=1:out_gain=0.85:delays=3.1|5.3:decays=0.16|0.09",
    "equalizer=f=1800:t=q:w=2:g=2",
]
LOUDNORM_JSON = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


def cut_graph(segments: list[dict], sample_rate: int = media.SAMPLE_RATE) -> str:
    """The filter graph that keeps the segments of input 0's sound, in order, with short fades, as [cut]."""
    parts = []
    for index, segment in enumerate(segments):
        start = round(segment["src_start"] * sample_rate)
        end = round(segment["src_end"] * sample_rate)
        length = (end - start) / sample_rate
        fade = min(FADE, length / 2)
        parts.append(
            f"[0:a:0]atrim=start_sample={start}:end_sample={end},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade:.6f},afade=t=out:st={length - fade:.6f}:d={fade:.6f}[s{index}]"
        )
    labels = "".join(f"[s{index}]" for index in range(len(segments)))
    return ";".join(parts) + f";{labels}concat=n={len(segments)}:v=0:a=1[cut]"


def coloured_command(work: Path, segments: list[dict], output: Path) -> list[str | Path]:
    """The cut voice, cleaned and coloured, as 32-bit float WAV before the loudness passes."""
    chain = ",".join([*CLEAN, *HELMET])
    graph = f"{cut_graph(segments)};[cut]{chain}[out]"
    return [
        "-i",
        work,
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        *media.BITEXACT,
        "-ar",
        str(media.SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_f32le",
        output,
    ]


def loudnorm(measured: dict | None = None) -> str:
    base = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_PEAK}:LRA={TARGET_LRA}:print_format=json"
    if measured is None:
        return base
    return (
        f"{base}:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )


def parse_loudnorm(report: str) -> dict:
    found = LOUDNORM_JSON.findall(report)
    if not found:
        raise media.MediaError("loudnorm : aucune mesure dans la sortie de FFmpeg")
    return json.loads(found[-1])


def measure(ffmpeg: Path, source: Path) -> dict:
    report = media.ffmpeg(ffmpeg, ["-i", source, "-af", loudnorm(), "-f", "null", "-"], "voice, mesure", "info")
    return parse_loudnorm(report)


def normalize(ffmpeg: Path, source: Path, measured: dict, output: Path) -> dict:
    """The second pass: the measured gain applied (linear when the true peak allows it), resampled to 48 kHz, 24-bit."""
    args = [
        "-i",
        source,
        "-af",
        f"{loudnorm(measured)},aresample={media.SAMPLE_RATE}",
        *media.BITEXACT,
        *media.NO_METADATA,
        "-ar",
        str(media.SAMPLE_RATE),
        "-ac",
        "1",
        "-c:a",
        "pcm_s24le",
        output,
    ]
    return parse_loudnorm(media.ffmpeg(ffmpeg, args, "voice, sonie", "info"))
