"""A showcase video (« vitrine »): the voice over, line by line, on shots of a real app and of the owner's rushes.

Its script.md has « genre: vitrine » and the settings of this video in its front matter, never constants of the chain
(each one is a choice of the video, open to change):
- « theme »: the look of the titles, captions, banner and end card (a folder of templates/hyperframes/themes/);
- « bandeau »: the call to action in the middle, « title | text | start | length », in seconds of the video;
- « vignette »: the text of the cover, its lines split by « | », one word between asterisks in the accent colour;
- « vignette_image »: the second of the video whose picture carries the cover;
- « icone »: the capture of the app's icon, shown on the banner and the end card;
- « ecran_fin »: the end card's name, then its badge and the badge's icon, « name | badge | icon ».

Each line of the body is one line of the voice. Its annotations place it on its shots and add no spoken word:
- « [plan: <capture> | depuis <s> | durée <s> | voix <s>] »: a shot from a capture of the video (a plan filmed by
  `vf capture`, or a rush), from its second « depuis », for « durée » seconds; the line's voice starts « voix »
  seconds after the shot starts. Several « plan » on one line follow each other, the voice counted from the first.
- « [jumeaux: <capture> | depuis <s> | durée <s> | voix <s> | avant <x> <y> | après <x> <y> | taille <w> <h> |
  volet <s> <s> | étiquettes <before> / <after>] »: the PR twins of a screen recording, the panes at « avant »
  (before) and « après » (after), both « taille », shown in turn under their labels, a wipe from the first to the
  second at « volet » (start, length) seconds into the shot.
- « [suite: voix <s>] »: the line goes on in the shot of the line before, its voice « voix » seconds after its start.
- « [fin: voix <s>] »: the end card, until the target duration of the video; only the last line.
- « [appel: <icon> | <title> | <text>] »: a row of the end card, lit when the voice says the word before it.
- « [ton: <tag>] »: a delivery tag of the voice generator (ElevenLabs), said before the next word: for `vf voix`.

Times are seconds, with a decimal comma or point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from video_factory import frontmatter, script
from video_factory.script import ANNOTATION, ScriptError

NUMBER = re.compile(r"^[0-9]+(?:[.,][0-9]+)?$")
# A capture's name, as the studio page also writes it from the name of a received file.
CAPTURE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?$")
SEPARATOR = "|"
PIECES = ("plan", "jumeaux")
MODELS = ("v3", "v2")
PAUSE_V2 = '<break time="0.8s" />'
PAUSE_V3 = "[short pause]"


@dataclass(frozen=True)
class Piece:
    """One shot of a line: a stretch of a capture, or the PR twins of a screen recording."""

    kind: str  # « plan » or « jumeaux »
    capture: str
    start: float = 0.0  # second of the capture where the shot starts
    length: float | None = None  # seconds shown; None: to the end of the capture
    before: tuple[int, int] | None = None  # twins: top left corner of the « before » pane, capture pixels
    after: tuple[int, int] | None = None
    size: tuple[int, int] | None = None  # twins: width and height of each pane
    wipe: tuple[float, float] | None = None  # twins: start and length of the wipe, seconds into the shot
    labels: tuple[str, str] | None = None  # twins: the label of each pane


@dataclass(frozen=True)
class EndRow:
    icon: str
    title: str
    text: str
    word: int  # index of the script word the row is lit on


@dataclass(frozen=True)
class Line:
    number: int  # line of script.md
    first: int  # index of its first script word
    last: int  # index past its last script word
    pieces: tuple[Piece, ...]  # its own shots; empty for « suite » and « fin »
    follows: bool  # « suite »: it goes on in the shot of the line before
    end_card: bool  # « fin »: it is said on the end card
    voice: float  # seconds after the start of its shot (or of the shot it goes on in) where its voice starts
    tones: tuple[tuple[int, str], ...]  # (script word index said after the tag, tag)
    rows: tuple[EndRow, ...]


@dataclass(frozen=True)
class Banner:
    title: str
    text: str
    start: float
    length: float


@dataclass(frozen=True)
class Cover:
    lines: tuple[str, ...]
    at: float | None


@dataclass(frozen=True)
class EndCard:
    name: str
    badge: str | None
    badge_icon: str | None


@dataclass(frozen=True)
class Vitrine:
    theme: str
    duration: int  # the target duration of the video, the end of the end card
    lines: tuple[Line, ...]
    words: tuple[script.Word, ...]
    banner: Banner | None
    cover: Cover | None
    icon: str | None = None  # the capture of the app's icon
    end_card: EndCard | None = None


def seconds(value: str, where: str) -> float:
    if not NUMBER.match(value.strip()):
        raise ScriptError(f"{where} : « {value} » n'est pas un nombre de secondes")
    return float(value.strip().replace(",", "."))


def pair(values: list[str], where: str, kind=int) -> tuple:
    if len(values) != 2:
        raise ScriptError(f"{where} : deux nombres attendus")
    try:
        return tuple(kind(value.replace(",", ".")) for value in values)
    except ValueError as exc:
        raise ScriptError(f"{where} : deux nombres attendus") from exc


def options(parts: list[str], allowed: set[str], where: str) -> dict[str, list[str]]:
    """« key value… » parts of an annotation, each key once; « durée » and « après » also read without accents."""
    found: dict[str, list[str]] = {}
    aliases = {"duree": "durée", "apres": "après", "etiquettes": "étiquettes"}
    for part in parts:
        words = part.split()
        if not words:
            continue
        key = aliases.get(words[0], words[0])
        if key not in allowed:
            raise ScriptError(f"{where} : réglage « {words[0]} » inconnu (permis : {', '.join(sorted(allowed))})")
        if key in found:
            raise ScriptError(f"{where} : réglage « {key} » en double")
        if len(words) < 2:
            raise ScriptError(f"{where} : réglage « {key} » sans valeur")
        found[key] = words[1:]
    return found


def piece(kind: str, content: str, where: str) -> tuple[Piece, float | None]:
    parts = [part.strip() for part in content.split(SEPARATOR)]
    capture = parts[0]
    if not CAPTURE_NAME.match(capture):
        raise ScriptError(f"{where} : « {capture} » : le nom de la capture d'abord, en minuscules, chiffres et tirets")
    twins = {"avant", "après", "taille", "volet", "étiquettes"}
    allowed = {"depuis", "durée", "voix"} | (twins if kind == "jumeaux" else set())
    found = options(parts[1:], allowed, where)
    start = seconds(found["depuis"][0], where) if "depuis" in found else 0.0
    length = seconds(found["durée"][0], where) if "durée" in found else None
    voice = seconds(found["voix"][0], where) if "voix" in found else None
    if kind == "plan":
        return Piece(kind, capture, start, length), voice
    for key in ("avant", "après", "taille", "volet", "étiquettes"):
        if key not in found:
            raise ScriptError(f"{where} : des jumeaux sans « {key} »")
    wipe = pair(found["volet"], where, float)
    labels = tuple(part.strip() for part in " ".join(found["étiquettes"]).split(" / "))
    if len(labels) != 2 or not all(labels):
        raise ScriptError(f"{where} : « étiquettes <avant> / <après> » attendu")
    return (
        Piece(
            kind,
            capture,
            start,
            length,
            pair(found["avant"], where),
            pair(found["après"], where),
            pair(found["taille"], where),
            wipe,
            labels,
        ),
        voice,
    )


def banner(raw: str) -> Banner:
    parts = [part.strip() for part in raw.split(SEPARATOR)]
    if len(parts) != 4:
        raise ScriptError("bandeau : « titre | texte | début | durée » attendu")
    return Banner(parts[0], parts[1], seconds(parts[2], "bandeau"), seconds(parts[3], "bandeau"))


def icon_of(fields: dict) -> str | None:
    if "icone" not in fields:
        return None
    name = str(fields["icone"])
    if not CAPTURE_NAME.match(name):
        raise ScriptError(f"icone : « {name} » : le nom d'une capture, en minuscules, chiffres et tirets")
    return name


def end_card_of(raw: str) -> EndCard:
    parts = [part.strip() for part in raw.split(SEPARATOR)]
    if not parts[0] or len(parts) > 3:
        raise ScriptError("ecran_fin : « nom | badge | icône du badge » attendu, le nom d'abord")
    parts += [""] * (3 - len(parts))
    return EndCard(parts[0], parts[1] or None, parts[2] or None)


def parse(text: str) -> Vitrine:
    """The showcase of a script.md text; a script of another genre, or a broken line, is refused with its line."""
    fields, _body = frontmatter.split(text)
    if script.genre_of(text) != script.VITRINE:
        raise ScriptError("ce script n'est pas une vitrine (« genre: vitrine » dans l'en-tête)")
    theme = fields.get("theme")
    if not isinstance(theme, str) or not theme:
        raise ScriptError("en-tête : une vitrine nomme son thème (« theme: … »)")
    duration = fields.get("duree_visee")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ScriptError("en-tête : « duree_visee », la durée visée en secondes, manque ou n'est pas un nombre entier")
    words = script.parse(text).words
    lines: list[Line] = []
    count = 0
    for number, raw in script.body_lines(text):
        where = f"ligne {number}"
        first = count
        position = 0
        pieces: list[Piece] = []
        follows = end_card = False
        voice: float | None = None
        tones: list[tuple[int, str]] = []
        rows: list[EndRow] = []
        for match in ANNOTATION.finditer(raw):
            count += len(spoken(raw[position : match.start()]))
            kind, content = match.group("kind"), (match.group("content") or "").strip()
            if kind in PIECES:
                made, offset = piece(kind, content, where)
                if offset is not None:
                    if voice is not None:
                        raise ScriptError(f"{where} : « voix » donnée deux fois")
                    voice = offset
                pieces.append(made)
            elif kind in ("suite", "fin"):
                found = options([content], {"voix"}, where) if content else {}
                if "voix" in found:
                    voice = seconds(found["voix"][0], where)
                follows, end_card = follows or kind == "suite", end_card or kind == "fin"
            elif kind == "ton":
                if not content:
                    raise ScriptError(f"{where} : « ton » sans étiquette")
                tones.append((count, content))
            elif kind == "appel":
                parts = [part.strip() for part in content.split(SEPARATOR)]
                if len(parts) != 3 or not all(parts) or count == first:
                    raise ScriptError(f"{where} : « appel : icône | titre | texte », après le mot qui l'allume")
                rows.append(EndRow(parts[0], parts[1], parts[2], count - 1))
            position = match.end()
        count += len(spoken(raw[position:]))
        if any(index >= count for index, _tag in tones):
            raise ScriptError(f"{where} : un « ton » se place avant un mot de sa réplique")
        if sum((bool(pieces), follows, end_card)) != 1:
            raise ScriptError(f"{where} : chaque réplique a des « plan » ou des « jumeaux », ou « suite », ou « fin »")
        if follows and not lines:
            raise ScriptError(f"{where} : la première réplique ne peut pas être une « suite »")
        if rows and not end_card:
            raise ScriptError(f"{where} : un « appel » se dit sur l'écran de fin (« fin »)")
        lines.append(
            Line(number, first, count, tuple(pieces), follows, end_card, voice or 0.0, tuple(tones), tuple(rows))
        )
    if count != len(words):
        raise ScriptError("les mots des répliques ne sont pas ceux du script")
    for line in lines[:-1]:
        if line.end_card:
            raise ScriptError(f"ligne {line.number} : seule la dernière réplique se dit sur l'écran de fin (« fin »)")
    cover = None
    if "vignette" in fields:
        at = seconds(str(fields["vignette_image"]), "vignette_image") if "vignette_image" in fields else None
        cover = Cover(tuple(part.strip() for part in str(fields["vignette"]).split(SEPARATOR)), at)
    return Vitrine(
        theme=theme,
        duration=duration,
        lines=tuple(lines),
        words=words,
        banner=banner(str(fields["bandeau"])) if "bandeau" in fields else None,
        cover=cover,
        icon=icon_of(fields),
        end_card=end_card_of(str(fields["ecran_fin"])) if "ecran_fin" in fields else None,
    )


def captures(vitrine: Vitrine) -> list[str]:
    """The captures a showcase shows: those of its shots, and its icon."""
    names = {piece.capture for line in vitrine.lines for piece in line.pieces}
    return sorted(names | ({vitrine.icon} if vitrine.icon else set()))


def spoken(text: str) -> list[str]:
    """The spoken words of a stretch of a line, as script.py counts them."""
    return [token for token in text.split() if script.normalize(token)]


def elevenlabs_text(vitrine: Vitrine, model: str = "v3") -> str:
    """The text to paste in ElevenLabs: the lines in order, with their delivery tags for « v3 » (Eleven v3, whose
    pauses are tags too) or a 0.8 s break between lines for « v2 » (Eleven Multilingual v2, which reads no tag). The
    no-break spaces of the captions' typography become plain spaces: the generator reads words, not layout."""
    if model not in MODELS:
        raise ValueError(f"modèle « {model} » : v3 ou v2")
    said = []
    for line in vitrine.lines:
        tags: dict[int, list[str]] = {}
        for index, tag in line.tones if model == "v3" else ():
            tags.setdefault(index, []).append(tag)
        parts = []
        for index in range(line.first, line.last):
            parts.extend(f"[{tag}]" for tag in tags.get(index, ()))
            parts.append(vitrine.words[index].text.replace(script.NO_BREAK, " "))
        said.append((line, " ".join(parts)))
    if model == "v2":
        return f"\n{PAUSE_V2}\n".join(text for _line, text in said) + "\n"
    out = said[0][1]
    for line, text in said[1:]:
        opens_on_a_tag = bool(line.tones) and line.tones[0][0] == line.first
        out += (" " if opens_on_a_tag else f" {PAUSE_V3} ") + text
    return out + "\n"
