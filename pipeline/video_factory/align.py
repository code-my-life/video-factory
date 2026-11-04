"""`align`: the transcript aligned on the script by dynamic programming, each spoken word labelled.

The alignment reads the transcript word by word and moves along the script. Besides matching, inserting and deleting a
word, the speaker may restart (go back to an earlier word of the current or the previous sentence) or abandon a
sentence (jump to its end). The cheapest path splits the transcript into attempts at each sentence; the last complete
attempt of each sentence is kept, the other attempts are retakes. Then each word is:
- « kept »: said in the kept attempt of its sentence, with the index of the script word it says;
- « retake »: said in another attempt, or between two attempts of the same sentence;
- « filler »: a hesitation of the French lexicon below, outside the script;
- « off_script »: any other word that is not in the script.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from video_factory.script import Script, normalize

KEPT, RETAKE, FILLER, OFF_SCRIPT = "kept", "retake", "filler", "off_script"

# French hesitations and verbal tics, as normalized words; a phrase is a tuple of words. A lexicon word that the
# script itself says is matched like any other word: only words outside the script become fillers.
FILLERS: tuple[tuple[str, ...], ...] = (
    ("euh",),
    ("euuh",),
    ("heu",),
    ("hum",),
    ("hmm",),
    ("hm",),
    ("mmh",),
    ("mh",),
    ("bah",),
    ("ben",),
    ("beh",),
    ("hein",),
    ("bon",),
    ("voilà",),
    ("bref",),
    ("genre",),
    ("quoi",),
    ("du", "coup"),
    ("en", "fait"),
    ("tu", "vois"),
    ("tu", "sais"),
    ("je", "veux", "dire"),
    ("on", "va", "dire"),
)
FILLER_WORDS = frozenset(word for phrase in FILLERS for word in phrase)

# Costs of the path. A restart is cheaper than one inserted word, so a stutter or a repeated phrase reads as a retake;
# abandoning a sentence is cheaper than deleting its remaining words, so an unfinished attempt reads as one.
MATCH = 0.0
NEAR = 0.4
SUBSTITUTE = 1.0
INSERT = 1.0
INSERT_FILLER = 0.5
DELETE = 1.0
RESTART = 0.9
ABANDON = 0.6


@dataclass
class Attempt:
    sentence: int
    matched: list[tuple[int, int]] = field(default_factory=list)  # (transcript index, script index)
    inserted: list[int] = field(default_factory=list)
    complete: bool = False

    def first(self) -> int | None:
        spoken = [i for i, _j in self.matched] + self.inserted
        return min(spoken) if spoken else None

    def last(self) -> int | None:
        spoken = [i for i, _j in self.matched] + self.inserted
        return max(spoken) if spoken else None


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def substitution(spoken: str, written: str) -> float:
    """Equal words cost nothing; close spellings (a transcription slip) cost less than unrelated words."""
    if spoken == written:
        return MATCH
    if edit_distance(spoken, written) <= max(1, len(written) // 3):
        return NEAR
    return SUBSTITUTE


def sentence_of(script: Script) -> list[int]:
    return [word.sentence for word in script.words]


def path(spoken: Sequence[str], script: Script) -> list[tuple]:
    """The cheapest sequence of operations reading every spoken word and reaching the end of the script:
    ("M", i, j), ("I", i), ("D", j), ("R", from_j, to_j), ("A", from_j, to_j)."""
    written = [word.norm for word in script.words]
    count, length = len(spoken), len(written)
    sentences = script.sentences
    inf = float("inf")
    cost = [[inf] * (length + 1) for _ in range(count + 1)]
    back: list[list[tuple | None]] = [[None] * (length + 1) for _ in range(count + 1)]
    cost[0][0] = 0.0
    for i in range(count + 1):
        row, here = cost[i], back[i]
        if i > 0:
            above, word = cost[i - 1], spoken[i - 1]
            insert = INSERT_FILLER if word in FILLER_WORDS else INSERT
            for j in range(length + 1):
                best, step = above[j] + insert, ("I", i - 1, j)
                if j > 0:
                    candidate = above[j - 1] + substitution(word, written[j - 1])
                    if candidate <= best:
                        best, step = candidate, ("M", i - 1, j - 1)
                row[j], here[j] = best, step
        for j in range(1, length + 1):
            if row[j - 1] + DELETE < row[j]:
                row[j], here[j] = row[j - 1] + DELETE, ("D", j - 1)
        for start, end in sentences:
            for j in range(start + 1, end):
                if row[j] + ABANDON < row[end]:
                    row[end], here[end] = row[j] + ABANDON, ("A", j, end)
        relax_restarts(row, here, sentences)
    return backtrack(back, count, length)


def relax_restarts(row: list[float], here: list[tuple | None], sentences: Sequence[tuple[int, int]]) -> None:
    """A restart goes back to any earlier word of the current sentence or of the one before it."""
    for index, (start, end) in enumerate(sentences):
        reach = sentences[index + 1][1] if index + 1 < len(sentences) else end
        best, source = float("inf"), None
        for j in range(reach, start - 1, -1):
            if source is not None and best + RESTART < row[j]:
                row[j], here[j] = best + RESTART, ("R", source, j)
            if row[j] < best:
                best, source = row[j], j


def backtrack(back: list[list[tuple | None]], count: int, length: int) -> list[tuple]:
    steps, i, j = [], count, length
    while (i, j) != (0, 0):
        step = back[i][j]
        if step is None:
            raise AssertionError(f"alignment path broken at ({i}, {j})")
        steps.append(step)
        kind = step[0]
        if kind == "M":
            i, j = step[1], step[2]
        elif kind == "I":
            i = step[1]
        elif kind == "D":
            j = step[1]
        else:
            j = step[1]
    steps.reverse()
    return steps


def attempts(steps: Sequence[tuple], script: Script) -> tuple[list[Attempt], list[int]]:
    """The attempts at each sentence along the path, and the spoken words read outside any attempt."""
    sentences = sentence_of(script)
    found: list[Attempt] = []
    outside: list[int] = []
    current: Attempt | None = None
    for step in steps:
        kind = step[0]
        if kind in ("M", "D"):
            j = step[2] if kind == "M" else step[1]
            if current is None or current.sentence != sentences[j]:
                current = Attempt(sentences[j])
                found.append(current)
            if kind == "M":
                current.matched.append((step[1], j))
            start, end = script.sentences[sentences[j]]
            if j + 1 == end:
                # Reaching the end counts as complete when at least half of the sentence was said.
                current.complete = 2 * len(current.matched) >= end - start
                current = None
        elif kind == "I":
            (current.inserted if current is not None else outside).append(step[1])
        else:
            current = None
    return found, outside


def labels(spoken: Sequence[str], script: Script) -> list[tuple[str, int | None]]:
    """(label, script index) of each spoken word, the script index set for kept words only."""
    found, outside = attempts(path(spoken, script), script)
    chosen: dict[int, Attempt] = {}
    for attempt in found:
        best = chosen.get(attempt.sentence)
        if best is None or rank(attempt) >= rank(best):
            chosen[attempt.sentence] = attempt
    result: list[tuple[str, int | None]] = [(OFF_SCRIPT, None)] * len(spoken)
    for attempt in found:
        kept = chosen[attempt.sentence] is attempt
        for i, j in attempt.matched:
            result[i] = (KEPT, j) if kept else (RETAKE, None)
        for i in attempt.inserted:
            result[i] = (OFF_SCRIPT, None) if kept else (RETAKE, None)
    for i in outside:
        if between_attempts_of_one_sentence(i, found):
            result[i] = (RETAKE, None)
    return mark_fillers(spoken, result)


def rank(attempt: Attempt) -> tuple[bool, int]:
    """Any complete attempt beats an incomplete one, and complete attempts tie with each other, so the last complete
    one wins (attempts are compared in order with >=); without a complete attempt, the one with the most words said."""
    if attempt.complete:
        return True, 0
    return False, len(attempt.matched)


def between_attempts_of_one_sentence(index: int, found: Sequence[Attempt]) -> bool:
    before = [a for a in found if (a.last() is not None and a.last() < index)]
    after = [a for a in found if (a.first() is not None and a.first() > index)]
    if not before or not after:
        return False
    previous = max(before, key=lambda a: a.last() or 0)
    following = min(after, key=lambda a: a.first() or 0)
    return previous.sentence == following.sentence


def mark_fillers(spoken: Sequence[str], result: list[tuple[str, int | None]]) -> list[tuple[str, int | None]]:
    """Words of the lexicon that are not kept become fillers; phrases are matched longest first."""
    phrases = sorted(FILLERS, key=len, reverse=True)
    i = 0
    while i < len(spoken):
        width = 1
        for phrase in phrases:
            window = range(i, i + len(phrase))
            if tuple(spoken[i : i + len(phrase)]) == phrase and all(result[k][0] != KEPT for k in window):
                for k in window:
                    result[k] = (FILLER, None)
                width = len(phrase)
                break
        i += width
    return result


def align(words: Sequence[dict], script: Script) -> dict:
    """The alignment document: each transcript word with its label, and per sentence what was kept or missed."""
    spoken = [normalize(word["text"]) for word in words]
    labelled = labels(spoken, script)
    aligned = [
        {
            "text": word["text"].strip(),
            "start": word["start"],
            "end": word["end"],
            "label": label,
            "script": index,
        }
        for word, (label, index) in zip(words, labelled, strict=True)
    ]
    said = {index for label, index in labelled if label == KEPT}
    missing = [j for j in range(len(script.words)) if j not in said]
    return {"words": aligned, "missing": missing}
