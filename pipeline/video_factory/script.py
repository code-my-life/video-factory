"""The body of script.md: the spoken text, one sentence per line, with its annotations in brackets.

- A full-frame shot is written after the word where it starts, or at the end of the line to cover the whole
  sentence: « [stat: …] », « [etapes: …] », « [code: …] » (motion design) or « [capture: <name>] » (a still or a short
  silent clip of a real screen, registered for the video under that name). The parts of a « stat » (the figure, then
  its caption) and the steps of « etapes » are separated by « | ».
- A punch-in is written after the word to stress: « [zoom] ».
- HTML comments are not spoken (the template's instructions live in one).

A showcase script (« genre: vitrine » in its front matter) has its own annotations instead, read by `vitrine.py`: they
place each line on its shots and add no spoken word, so the words and sentences read here are the same.

Each word keeps its written form, shown in the captions, and a normalized form compared with the transcript. A mark
of punctuation written apart stays with its word, so the captions keep it: a closing one (« code ! », « d'usine : »)
or a dash (« Et - voilà ») with the word before, an opening one (« « bien ») with the word after, separated by a
no-break space where French typography puts one (before « ! ? : ; » » and a dash, after « « »). A mark at the start of
a sentence (a dialogue dash) is dropped; an opening mark with no word after it on its line is refused.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace

from video_factory import frontmatter

COMMENT = re.compile(r"<!--.*?-->", re.S)
ANNOTATION = re.compile(r"\[(?P<kind>[a-z]+)(?:\s*:\s*(?P<content>[^\]]*))?\]")
SHOT_KINDS = ("stat", "etapes", "code", "capture")
FACE_CAMERA, VITRINE = "face-camera", "vitrine"
# The annotations of a showcase script, read by vitrine.py; « zoom » and the shots above belong to the face camera.
VITRINE_KINDS = ("plan", "jumeaux", "suite", "fin", "ton", "appel")
SEPARATOR = "|"
# Typographic apostrophes (right and left single quotation marks) and the backtick read as the straight apostrophe.
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'"})
# Inside a word only letters, digits, the apostrophe and the hyphen count; the rest is punctuation.
INNER = re.compile(r"[^\w'\-]+")
# Marks written apart: the high ones of French typography take a no-break space before them, the opening guillemet one
# after it; an opening mark goes with the word after it.
HIGH_MARKS = frozenset("!?:;»-\u2013\u2014")  # and the hyphen, en dash and em dash written apart, as dashes
OPENING = frozenset("«(\u201c\u2018")  # «, (, and the left double and single quotation marks
NO_BREAK = "\u00a0"


class ScriptError(ValueError):
    """The body breaks the annotation rules; the message names its line."""


@dataclass(frozen=True)
class Word:
    text: str
    norm: str
    sentence: int


@dataclass(frozen=True)
class Shot:
    kind: str
    content: str
    anchor: int  # index of the word the shot starts on

    def parts(self) -> list[str]:
        """The parts of the content, split on « | » (a stat's figure and caption, the steps of « etapes »)."""
        return [part.strip() for part in self.content.split(SEPARATOR) if part.strip()]


@dataclass(frozen=True)
class Zoom:
    anchor: int  # index of the word to stress


@dataclass(frozen=True)
class Script:
    words: tuple[Word, ...]
    sentences: tuple[tuple[int, int], ...]  # [first, last + 1) word indices of each sentence
    shots: tuple[Shot, ...]
    zooms: tuple[Zoom, ...]


def normalize(word: str) -> str:
    """The form compared with the transcript: NFC, lower case, straight apostrophes, no outer or inner punctuation."""
    text = unicodedata.normalize("NFC", word).translate(APOSTROPHES).lower()
    text = INNER.sub("", text)
    return text.strip("'-")


def body_lines(text: str) -> list[tuple[int, str]]:
    """(line number in script.md, text) of each spoken line of the body, comments removed."""
    _fields, body = frontmatter.split(text)
    offset = text[: len(text) - len(body)].count("\n")
    # Comments are blanked line for line, so the numbers stay those of the file.
    body = COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), body)
    return [(offset + number, line.strip()) for number, line in enumerate(body.split("\n"), 1) if line.strip()]


def genre_of(text: str) -> str:
    """The genre of a script.md text: « vitrine » for a showcase, else the face camera."""
    fields, _body = frontmatter.split(text)
    return VITRINE if fields.get("genre") == VITRINE else FACE_CAMERA


def parse(text: str) -> Script:
    """The words, sentences, shots and punch-ins of a script.md text."""
    vitrine = genre_of(text) == VITRINE
    words: list[Word] = []
    sentences: list[tuple[int, int]] = []
    shots: list[Shot] = []
    zooms: list[Zoom] = []
    for number, line in body_lines(text):
        first = len(words)
        position = 0
        pending: list[tuple[str, str, int]] = []  # shots of this line: kind, content, words said before it
        opening = ""  # opening marks waiting for their word, across the annotations
        for match in ANNOTATION.finditer(line):
            opening = add_words(line[position : match.start()], len(sentences), words, number, opening)
            anchor = len(words) - 1 if len(words) > first else first
            kind, content = match.group("kind"), (match.group("content") or "").strip()
            if vitrine:
                if kind not in VITRINE_KINDS:
                    raise ScriptError(f"ligne {number} : annotation « {match.group(0)} » inconnue dans une vitrine")
            elif kind == "zoom" and match.group("content") is None:
                zooms.append(Zoom(anchor))
            elif kind in SHOT_KINDS and content:
                pending.append((kind, content, len(words)))
            else:
                raise ScriptError(f"ligne {number} : annotation « {match.group(0)} » inconnue ou vide")
            position = match.end()
        opening = add_words(line[position:], len(sentences), words, number, opening)
        if opening:
            raise ScriptError(f"ligne {number} : « {opening.strip(NO_BREAK)} » n'ouvre aucun mot")
        if len(words) == first:
            raise ScriptError(f"ligne {number} : une annotation sans texte dit")
        for kind, content, before in pending:
            # At the end of the line, a shot covers the whole sentence; inside it, it starts on the word before it.
            anchor = first if before == len(words) else max(first, before - 1)
            shots.append(Shot(kind, content, anchor))
        sentences.append((first, len(words)))
    if not words:
        raise ScriptError("le script n'a aucun texte dit")
    return Script(tuple(words), tuple(sentences), tuple(shots), tuple(zooms))


def add_words(text: str, sentence: int, words: list[Word], number: int, opening: str = "") -> str:
    """Add the words of a stretch of a line; opening marks still waiting for a word are taken in and given back."""
    if "[" in text or "]" in text:
        raise ScriptError(f"ligne {number} : crochet sans annotation dans « {text.strip()} »")
    for token in text.split():
        norm = normalize(token)
        if norm:
            words.append(Word(f"{opening}{token}", norm, sentence))
            opening = ""
        elif token[0] in OPENING:
            opening += token + (NO_BREAK if token[-1] == "«" else "")
        elif words and words[-1].sentence == sentence:
            space = NO_BREAK if token[0] in HIGH_MARKS else ""
            words[-1] = replace(words[-1], text=f"{words[-1].text}{space}{token}")
    return opening
