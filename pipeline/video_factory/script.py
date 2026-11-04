"""The body of script.md: the spoken text, one sentence per line, with its annotations in brackets.

- A full-frame shot is written after the word where it starts, or at the end of the line to cover the whole
  sentence: « [stat: …] », « [etapes: …] », « [code: …] » (motion design) or « [capture: <name>] » (a still or a short
  silent clip of a real screen, registered for the video under that name). The parts of a « stat » (the figure, then
  its caption) and the steps of « etapes » are separated by « | ».
- A punch-in is written after the word to stress: « [zoom] ».
- HTML comments are not spoken (the template's instructions live in one).

Each word keeps its written form, shown in the captions, and a normalized form compared with the transcript.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from video_factory import frontmatter

COMMENT = re.compile(r"<!--.*?-->", re.S)
ANNOTATION = re.compile(r"\[(?P<kind>[a-z]+)(?:\s*:\s*(?P<content>[^\]]*))?\]")
SHOT_KINDS = ("stat", "etapes", "code", "capture")
SEPARATOR = "|"
# Typographic apostrophes (right and left single quotation marks) and the backtick read as the straight apostrophe.
APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "`": "'"})
# Inside a word only letters, digits, the apostrophe and the hyphen count; the rest is punctuation.
INNER = re.compile(r"[^\w'\-]+")


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


def parse(text: str) -> Script:
    """The words, sentences, shots and punch-ins of a script.md text."""
    words: list[Word] = []
    sentences: list[tuple[int, int]] = []
    shots: list[Shot] = []
    zooms: list[Zoom] = []
    for number, line in body_lines(text):
        first = len(words)
        position = 0
        pending: list[tuple[str, str, int]] = []  # shots of this line: kind, content, words said before it
        for match in ANNOTATION.finditer(line):
            add_words(line[position : match.start()], len(sentences), words, number)
            anchor = len(words) - 1 if len(words) > first else first
            kind, content = match.group("kind"), (match.group("content") or "").strip()
            if kind == "zoom" and match.group("content") is None:
                zooms.append(Zoom(anchor))
            elif kind in SHOT_KINDS and content:
                pending.append((kind, content, len(words)))
            else:
                raise ScriptError(f"ligne {number} : annotation « {match.group(0)} » inconnue ou vide")
            position = match.end()
        add_words(line[position:], len(sentences), words, number)
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


def add_words(text: str, sentence: int, words: list[Word], number: int) -> None:
    if "[" in text or "]" in text:
        raise ScriptError(f"ligne {number} : crochet sans annotation dans « {text.strip()} »")
    for token in text.split():
        norm = normalize(token)
        if norm:
            words.append(Word(token, norm, sentence))
