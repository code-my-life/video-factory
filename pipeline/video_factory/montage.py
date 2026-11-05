"""The montage of a showcase (« vitrine », #28): its voice placed line by line on its shots, its captions, its banner
and its end card, written as one HyperFrames project in the look of its theme.

- The time line: the shots of each line one after the other, from its captures (`[plan: …]`, `[jumeaux: …]`), then
  the end card until the target duration. A line's voice is heard « voix » seconds after the start of its shot (the
  shot of the line before for a « suite », the end card for « fin »).
- The voice of a line is its stretch of the voice file: from the end of the silence before its first word to the start
  of the silence after its last one, both found by `transcribe`. PAD_IN and PAD_OUT of the voice are kept around it,
  faded in and out like the voice step's cuts.
- The captions are the words of the script at the time `align` gives them, in groups of CAPTION_WORDS words at most,
  closed after a mark of punctuation or before a real pause (CAPTION_PAUSE). A short word alone waits for the next
  one, and a line of WHOLE_LINE words or fewer is one group. A group stays CAPTION_HOLD after its last word, until the
  next one opens.
- A row of the end card is lit when the voice says the word before its « appel ».
- The theme (`templates/hyperframes/themes/<theme>/`) is a choice of the script: its page (`index.html`), its icons
  (`icons.json`), its fonts and its cover (`cover.html`).

These rules reproduce video 1 as validated on 2026-11-05: its montage was written by hand from them.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from video_factory import compose, media, vitrine, voice
from video_factory.paths import HYPERFRAMES_TEMPLATE
from video_factory.vitrine import Piece, Vitrine

THEMES = HYPERFRAMES_TEMPLATE / "themes"
FPS, WIDTH, HEIGHT = compose.FPS, compose.WIDTH, compose.HEIGHT
PAD_IN, PAD_OUT = 0.06, 0.12  # seconds of the voice kept before and after a line's stretch of speech
CAPTION_WORDS = 3  # words at most in a caption group
CAPTION_PAUSE = 0.35  # seconds: a real pause closes a group; whisper leaves shorter gaps inside a breath
CAPTION_HOLD = 0.5  # seconds a group stays after its last word, unless the next one opens
SHORT_WORD = 3  # characters: a word this short, alone in its group, waits for the next one
WHOLE_LINE = 4  # words: a line this short is shown whole
CLOSING = re.compile(r"[,.!:;?]$")
TWIN_MARGIN = 0.1  # seconds of the recording kept after a twins shot
# The text pass: the same page with only its text, white on black, so that every lit pixel is written text.
TEXT_PASS_STYLE = """<style>
      #root *, #root *::before, #root *::after { background: transparent !important;
        border-color: transparent !important; outline-color: transparent !important; box-shadow: none !important;
        text-shadow: none !important; filter: none !important; color: #fff !important;
        -webkit-text-fill-color: #fff !important; -webkit-text-stroke: 0 !important; }
      html, body, #root { background: #000 !important; }
      #root img, #root video, #root canvas, #root svg { opacity: 0 !important; }
    </style>
"""


class MontageError(Exception):
    """The montage cannot be made from this script and these files; the message says why."""


@dataclass(frozen=True)
class Shot:
    start: float  # seconds of the video
    end: float
    piece: Piece | None  # None for the end card


@dataclass(frozen=True)
class Spoken:
    """The voice of one line on the video's time line: its stretch of the voice file, heard from « at »."""

    line: int
    source_start: float
    source_end: float
    at: float


def timeline(vitrine: Vitrine, lengths: Mapping[str, float]) -> tuple[list[Shot], list[float]]:
    """The shots in order, the end card last, and for each line the start of the shot its voice is counted from. A piece
    without « durée » runs to the end of its capture (lengths, in seconds)."""
    shots: list[Shot] = []
    starts: list[float] = []
    clock = 0.0
    for line in vitrine.lines:
        if line.follows:
            starts.append(starts[-1])
            continue
        starts.append(clock)
        for piece in line.pieces:
            if piece.length is not None:
                length = piece.length
            elif piece.capture in lengths:
                length = lengths[piece.capture] - piece.start
            else:
                raise MontageError(f"ligne {line.number} : la durée de la capture « {piece.capture} » est inconnue")
            if length <= 0:
                raise MontageError(f"ligne {line.number} : « {piece.capture} » ne dure plus après {piece.start} s")
            end = round(clock + length, 6)
            shots.append(Shot(clock, end, piece))
            clock = end
    if vitrine.lines and vitrine.lines[-1].end_card:
        if clock >= vitrine.duration:
            raise MontageError(f"l'écran de fin commencerait à {clock} s, après la durée visée ({vitrine.duration} s)")
        shots.append(Shot(clock, float(vitrine.duration), None))
    elif abs(clock - vitrine.duration) > 1e-6:
        raise MontageError(f"les plans durent {clock} s au lieu des {vitrine.duration} s visées, sans écran de fin")
    if sum(1 for shot in shots if shot.piece is not None and shot.piece.kind == "jumeaux") > 1:
        raise MontageError("une seule paire de jumeaux par vidéo pour l'instant")
    return shots, starts


def spoken(
    vitrine: Vitrine, starts: Sequence[float], words: Sequence[dict], silences: Sequence[Sequence[float]], length: float
) -> list[Spoken]:
    """Each line's stretch of the voice: from the end of the last silence that begins before its first word (the start
    of the voice otherwise) to the start of the first silence that ends after its last word (the end of the voice
    otherwise), never over the words of the lines around it; heard « voix » seconds after the start of its shot."""
    found = []
    lines = vitrine.lines
    for index, line in enumerate(lines):
        first, last = words[line.first]["start"], words[line.last - 1]["end"]
        start = min(max((end for begin, end in silences if begin < first), default=0.0), first)
        end = max(min((begin for begin, end in silences if end > last), default=length), last)
        if index > 0:
            start = max(start, words[lines[index - 1].last - 1]["end"])
        if index + 1 < len(lines):
            end = min(end, words[lines[index + 1].first]["start"])
        found.append(Spoken(index, round(start, 3), round(end, 3), round(starts[index] + line.voice, 6)))
    return found


def placed_words(vitrine: Vitrine, lines: Sequence[Spoken], words: Sequence[dict]) -> list[dict]:
    """Each word of the script in its written form, at its time in the video (seconds), with its line."""
    found = []
    for placed in lines:
        line = vitrine.lines[placed.line]
        for index in range(line.first, line.last):
            word = words[index]
            found.append(
                {
                    "text": vitrine.words[index].text,
                    "start": placed.at + word["start"] - placed.source_start,
                    "end": placed.at + word["end"] - placed.source_start,
                    "line": placed.line,
                    "script": index,
                }
            )
    return found


def caption_groups(vitrine: Vitrine, placed: Sequence[dict]) -> list[dict]:
    """The caption groups, each with its text, its time (seconds) and its first and last word."""
    short = {index for index, line in enumerate(vitrine.lines) if line.last - line.first <= WHOLE_LINE}
    groups: list[list[int]] = []
    for position, word in enumerate(placed):
        current = groups[-1] if groups else None
        if current is None:
            closed = True
        elif word["line"] in short or placed[current[0]]["line"] in short:
            closed = placed[current[0]]["line"] != word["line"]
        else:
            last = placed[current[-1]]
            lone = len(current) == 1 and len(last["text"]) <= SHORT_WORD
            closed = (
                len(current) >= CAPTION_WORDS
                or CLOSING.search(last["text"]) is not None
                or (word["start"] - last["end"] > CAPTION_PAUSE and not lone)
            )
        if closed:
            groups.append([position])
        else:
            current.append(position)
    found = []
    for index, group in enumerate(groups):
        start, end = placed[group[0]]["start"], placed[group[-1]]["end"] + CAPTION_HOLD
        if index + 1 < len(groups):
            end = min(end, placed[groups[index + 1][0]]["start"])
        text = " ".join(placed[position]["text"] for position in group)
        found.append(
            {"start": round(start, 3), "end": round(end, 3), "text": text, "first": group[0], "last": group[-1]}
        )
    return found


def row_times(vitrine: Vitrine, lines: Sequence[Spoken], words: Sequence[dict]) -> list[float]:
    """The time of the video at which each row of the end card is lit: the start of the word before its « appel »."""
    if not lines:
        return []
    placed = lines[-1]
    rows = vitrine.lines[placed.line].rows
    return [round(placed.at + words[row.word]["start"] - placed.source_start, 3) for row in rows]


def shot_document(shot: Shot) -> dict:
    piece = shot.piece
    if piece is None:
        return {"start": shot.start, "end": shot.end, "kind": "fin"}
    found = {"start": shot.start, "end": shot.end, "kind": piece.kind, "capture": piece.capture, "from": piece.start}
    if piece.kind == "jumeaux":
        found |= {
            "before": list(piece.before),
            "after": list(piece.after),
            "size": list(piece.size),
            "wipe": list(piece.wipe),
            "labels": list(piece.labels),
        }
    return found


def decide(
    vitrine: Vitrine,
    words: Sequence[dict],
    silences: Sequence[Sequence[float]],
    length: float,
    lengths: Mapping[str, float],
) -> dict:
    """The decision list of a showcase: its shots, each line's voice, its words, captions and end card rows. words are
    the script words of `align` (seconds of the voice), silences and length those of `transcribe`."""
    shots, starts = timeline(vitrine, lengths)
    lines = spoken(vitrine, starts, words, silences, length)
    placed = placed_words(vitrine, lines, words)
    banner = vitrine.banner
    end = shots[-1] if shots and shots[-1].piece is None else None
    return {
        "genre": "vitrine",
        "duration": float(vitrine.duration),
        "frames": round(vitrine.duration * FPS),
        "shots": [shot_document(shot) for shot in shots],
        "spoken": [asdict(line) for line in lines],
        "words": [
            {
                "text": word["text"],
                "label": "kept",
                "script": word["script"],
                "start": round(word["start"], 6),
                "end": round(word["end"], 6),
            }
            for word in placed
        ],
        "groups": caption_groups(vitrine, placed),
        "rows": row_times(vitrine, lines, words),
        "banner": [banner.start, round(banner.start + banner.length, 6)] if banner else None,
        "end": [end.start, end.end] if end else None,
    }


# --- the voice --------------------------------------------------------------------------------------------------------


def voice_command(source: Path, lines: Sequence[dict], duration: float, output: Path) -> list[str | Path]:
    """The ffmpeg arguments of the voice on the video's time line: each line's stretch with PAD_IN and PAD_OUT, faded
    in and out, delayed to its place, all mixed without normalization into one mono track of the video's length."""
    chains, labels = [], []
    for index, line in enumerate(lines):
        start, end, at = line["source_start"], line["source_end"], line["at"]
        cut_start, cut_end = max(0.0, start - PAD_IN), end + PAD_OUT
        delay = round((at - (start - cut_start)) * 1000)
        if delay < 0:
            raise MontageError(f"réplique {index + 1} : sa voix commencerait avant le début de la vidéo")
        length = cut_end - cut_start
        fades = f"afade=t=in:d={voice.FADE},afade=t=out:st={length - voice.FADE:.3f}:d={voice.FADE}"
        chains.append(
            f"[0:a]atrim={cut_start:.3f}:{cut_end:.3f},asetpts=PTS-STARTPTS,aresample={media.SAMPLE_RATE},"
            f"{fades},adelay={delay}[l{index}]"
        )
        labels.append(f"[l{index}]")
    mix = f"{''.join(labels)}amix=inputs={len(lines)}:normalize=0,apad,atrim=0:{duration}[v]"
    graph = ";".join([*chains, mix])
    return [
        "-i",
        source,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-ac",
        "1",
        "-c:a",
        "pcm_s24le",
        *media.BITEXACT,
        output,
    ]


# --- the page -----------------------------------------------------------------------------------------------------


def theme_folder(name: str, root: Path = THEMES) -> Path:
    """The folder of a theme; an unknown theme is refused with the known ones."""
    folder = root / name
    if not (folder / "index.html").is_file():
        known = sorted(path.name for path in root.iterdir() if (path / "index.html").is_file()) if root.is_dir() else []
        raise MontageError(f"thème « {name} » inconnu ; thèmes : {', '.join(known) or 'aucun'}")
    return folder


def theme_icons(theme: Path) -> dict:
    return json.loads((theme / "icons.json").read_text(encoding="utf-8"))["icons"]


def icon_svg(icons: Mapping[str, dict], name: str, size: int) -> str:
    if name not in icons:
        raise MontageError(f"icône « {name} » absente du thème ; icônes : {', '.join(sorted(icons))}")
    found = icons[name]
    box = found["size"]
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {box} {box}" aria-hidden="true">'
        f'<path fill="{found["colour"]}" d="{found["path"]}"/></svg>'
    )


def clip(element_id: str, start: float, end: float, track: int, inner: str, cls: str = "") -> str:
    return (
        f'<div id="{element_id}" class="clip {cls}" data-start="{start:.6f}" data-duration="{end - start:.6f}" '
        f'data-track-index="{track}">{inner}</div>'
    )


def video_clip(element_id: str, src: str, start: float, end: float, media_start: float, track: int, cls: str) -> str:
    return (
        f'<video id="{element_id}" class="clip {cls}" src="{src}" data-start="{start:.6f}" '
        f'data-duration="{end - start:.6f}" data-media-start="{media_start:.6f}" data-track-index="{track}" '
        "muted playsinline></video>"
    )


def shot_parts(index: int, shot: dict) -> list[str]:
    start, end = shot["start"], shot["end"]
    if shot["kind"] == "plan":
        src = f"assets/captures/{shot['capture']}.mp4"
        return [video_clip(f"shot-{index}", src, start, end, shot["from"], 0, "shot")]
    if shot["kind"] != "jumeaux":
        return []
    before, after = (html.escape(label) for label in shot["labels"])
    tags = (
        '<div class="twin-line"></div>'
        f'<div class="tag" id="tag-avant">{before}</div>'
        f'<div class="tag" id="tag-apres">{after}</div>'
    )
    return [
        clip(f"shot-{index}", start, end, 0, "", "twins-ground"),
        video_clip("twin-avant", f"assets/captures/{shot['capture']}-avant.mp4", start, end, 0, 3, "twin"),
        video_clip("twin-apres", f"assets/captures/{shot['capture']}-apres.mp4", start, end, 0, 4, "twin"),
        clip("twin-tags", start, end, 5, tags),
    ]


def end_card(vitrine: Vitrine, icons: Mapping[str, dict]) -> str:
    image = '<img src="assets/icon.png" alt="" />' if vitrine.icon else ""
    card = vitrine.end_card
    brand = f'<div class="brand" id="brand">{image}<span>{html.escape(card.name)}</span></div>' if card else ""
    badge = ""
    if card and card.badge:
        mark = icon_svg(icons, card.badge_icon, 44) if card.badge_icon else ""
        badge = f'<div class="badge" id="badge">{mark}<span>{html.escape(card.badge)}</span></div>'
    rows = "".join(
        f'<div class="row" id="row-{index}"><div class="row-icon">{icon_svg(icons, row.icon, 70)}</div>'
        f'<div><div class="row-title">{html.escape(row.title)}</div>'
        f'<div class="row-sub">{html.escape(row.text)}</div></div></div>'
        for index, row in enumerate(vitrine.lines[-1].rows)
    )
    return f'<div class="end">{brand}{badge}<div class="rows">{rows}</div></div>'


def page(theme: Path, vitrine: Vitrine, edl: dict) -> str:
    """The root of the project: the shots, the twins, the banner, the end card and the captions, each a clip of the
    theme's page, and the times its timeline reads."""
    icons = theme_icons(theme)
    parts = [part for index, shot in enumerate(edl["shots"]) for part in shot_parts(index, shot)]
    banner = vitrine.banner
    if banner and edl["banner"]:
        image = '<img src="assets/icon.png" alt="" />' if vitrine.icon else ""
        card = (
            f'<div class="cta-card">{image}'
            f'<div><div class="cta-title">{html.escape(banner.title)}</div>'
            f'<div class="cta-sub">{html.escape(banner.text)}</div></div></div>'
        )
        parts.append(clip("cta", edl["banner"][0], edl["banner"][1], 1, card))
    if edl["end"]:
        parts.append(clip("end", edl["end"][0], edl["end"][1], 1, end_card(vitrine, icons)))
    for index, group in enumerate(edl["groups"]):
        text = f'<div class="cap-text">{html.escape(group["text"])}</div>'
        parts.append(clip(f"cap-{index}", group["start"], group["end"], 2, text, "cap"))
    twins = next((shot for shot in edl["shots"] if shot["kind"] == "jumeaux"), None)
    config = {
        "cta": edl["banner"],
        "end": edl["end"],
        "captions": len(edl["groups"]),
        "twins": {"start": twins["start"], "wipe": twins["wipe"]} if twins else None,
        "rows": edl["rows"],
    }
    values = {
        "DURATION": f"{edl['duration']:.6f}",
        "BODY": "\n      ".join(parts),
        "CONFIG": compose.script_json(config),
    }
    return compose.fill((theme / "index.html").read_text(encoding="utf-8"), values)


def text_root(page_html: str) -> str:
    """The root of the text pass: the same page with only its text, white on black."""
    if page_html.count("</head>") != 1:
        raise MontageError("thème : la page doit avoir un seul </head>")
    return page_html.replace("</head>", TEXT_PASS_STYLE + "  </head>", 1)


# --- the project --------------------------------------------------------------------------------------------------


def encode(ffmpeg: Path, source: Path, target: Path, filters: str, before: Sequence[str] = ()) -> None:
    """A capture re-encoded for the render: H.264 at 30 fps, BT.709, no sound, as compose encodes its tracks."""
    args = [*before, "-i", source, "-an", "-vf", f"{filters},{media.BT709}", *compose.encode_args(target)]
    media.ffmpeg(ffmpeg, args, target.name)


def place_captures(ffmpeg: Path, ffprobe: Path, project: Path, edl: dict, files: Mapping[str, Path]) -> None:
    """The captures of the shots in assets/captures/: a capture already at the size and rate of the video as it is,
    another one brought to 1440x2560 at 30 fps (it must be in 9:16); the twins cropped from their recording."""
    folder = project / "assets" / "captures"
    folder.mkdir(parents=True, exist_ok=True)
    for shot in edl["shots"]:
        if shot["kind"] == "plan":
            target = folder / f"{shot['capture']}.mp4"
            if target.exists():
                continue
            source = files[shot["capture"]]
            found = media.summary(media.probe(ffprobe, source))
            if (found["width"], found["height"], found["frame_rate"]) == (WIDTH, HEIGHT, str(FPS)):
                shutil.copyfile(source, target)
            elif found["width"] * 16 != found["height"] * 9:
                raise MontageError(f"plan « {shot['capture']} » : {found['width']}x{found['height']}, pas en 9:16")
            else:
                encode(ffmpeg, source, target, f"fps={FPS},scale={WIDTH}:{HEIGHT}:flags=lanczos")
        elif shot["kind"] == "jumeaux":
            width, height = shot["size"]
            length = shot["end"] - shot["start"] + TWIN_MARGIN
            seek = ["-ss", f"{shot['from']:.3f}", "-t", f"{length:.3f}"]
            for side, (x, y) in (("avant", shot["before"]), ("apres", shot["after"])):
                crop = f"fps={FPS},crop={width}:{height}:{x}:{y},scale={WIDTH}:-2:flags=lanczos"
                encode(ffmpeg, files[shot["capture"]], folder / f"{shot['capture']}-{side}.mp4", crop, seek)


def write_project(
    tools_ffmpeg: Path,
    tools_ffprobe: Path,
    project: Path,
    theme: Path,
    vitrine: Vitrine,
    edl: dict,
    files: Mapping[str, Path],
) -> str:
    """The HyperFrames project of a showcase: its page, its captures, the app's icon and the theme's fonts. Returns the
    page, from which the text pass is made."""
    project.mkdir(parents=True, exist_ok=True)
    document = page(theme, vitrine, edl)
    (project / "index.html").write_text(document, encoding="utf-8")
    place_captures(tools_ffmpeg, tools_ffprobe, project, edl, files)
    shutil.copytree(theme / "fonts", project / "assets" / "fonts")
    if vitrine.icon:
        shutil.copyfile(files[vitrine.icon], project / "assets" / "icon.png")
    return document


def used_captures(showcase: Vitrine) -> list[str]:
    """The captures a showcase shows: its shots' and its icon."""
    return vitrine.captures(showcase)
