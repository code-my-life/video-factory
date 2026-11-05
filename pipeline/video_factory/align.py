"""`align`: the transcript aligned on the script by dynamic programming, each spoken word labelled.

The alignment reads the transcript word by word and moves along the script. Besides matching, inserting and deleting a
word, and joining the pieces of a word whisper heard apart (« Factory » « Live » for « factory-live », then one word of
the document, from the start of its first piece to the end of its last), the speaker may restart (go back to an earlier
word of the current or the previous sentence) or abandon a sentence (jump to its end). The cheapest path splits the
transcript into attempts at each sentence; the last complete attempt of each sentence is kept, the other attempts are
retakes. Then each word is:
- « kept »: said in the kept attempt of its sentence, with the index of the script word it says;
- « retake »: said in another attempt, or between two attempts of the same sentence;
- « filler »: a hesitation of the French lexicon below, outside the script;
- « off_script »: any other word that is not in the script.

The document also gives each word of the script its time (« script_words »): the time of the spoken word kept for it,
its written form whatever whisper heard (« Cloud » said for « Claude »). A script word no spoken word was kept for
(whisper heard « les PR » as one word, « l'EPR ») shares the time around it: the gap between its neighbours, or else the
span of the neighbour that was heard longer than written, the one that swallowed it. A showcase's captions are read from
them.
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
# A word heard in pieces: two or three spoken words that, put end to end, are exactly the written word.
PIECES = (2, 3)


@dataclass
class Attempt:
    sentence: int
    matched: list[tuple[int, int]] = field(default_factory=list)  # (transcript index, script index)
    inserted: list[int] = field(default_factory=list)
    complete: bool = False

    def said(self) -> int:
        """How many words of the sentence this attempt said (a word heard in pieces counts once)."""
        return len({j for _i, j in self.matched})

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


def key(text: str) -> str:
    """A word as compared across its pieces: normalized, without hyphen or apostrophe."""
    return normalize(text).replace("-", "").replace("'", "")


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
    ("M", i, j), ("J", first_i, j, pieces), ("I", i), ("D", j), ("R", from_j, to_j), ("A", from_j, to_j)."""
    written = [word.norm for word in script.words]
    keys = [key(word) for word in written]
    count, length = len(spoken), len(written)
    joined = {(i, n): key("".join(spoken[i : i + n])) for n in PIECES for i in range(count - n + 1)}
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
                    for pieces in PIECES:
                        first = i - pieces
                        if first >= 0 and joined[first, pieces] == keys[j - 1] and cost[first][j - 1] + MATCH < best:
                            best, step = cost[first][j - 1] + MATCH, ("J", first, j - 1, pieces)
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
        if kind in ("M", "J"):
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
        if kind in ("M", "J", "D"):
            j = step[1] if kind == "D" else step[2]
            if current is None or current.sentence != sentences[j]:
                current = Attempt(sentences[j])
                found.append(current)
            if kind == "M":
                current.matched.append((step[1], j))
            elif kind == "J":
                current.matched.extend((i, j) for i in range(step[1], step[1] + step[3]))
            start, end = script.sentences[sentences[j]]
            if j + 1 == end:
                # Reaching the end counts as complete when at least half of the sentence was said.
                current.complete = 2 * current.said() >= end - start
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
    return False, attempt.said()


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


def script_times(aligned: Sequence[dict], script: Script) -> list[dict]:
    """The time of each script word, « said » when a spoken word was kept for it, shared with its neighbours if not."""
    times: list[list[float] | None] = [None] * len(script.words)
    heard: dict[int, str] = {}
    for word in aligned:
        if word["label"] == KEPT and word["script"] is not None:
            times[word["script"]] = [word["start"], word["end"]]
            heard[word["script"]] = word["text"]
    surplus = {j: len(key(text)) - len(key(script.words[j].text)) for j, text in heard.items()}
    said = [found is not None for found in times]
    index = 0
    while index < len(times):
        if times[index] is not None:
            index += 1
            continue
        end = index
        while end < len(times) and times[end] is None:
            end += 1
        share(times, index, end, surplus)
        index = end
    return [
        {
            "text": word.text,
            "start": round(span[0], 3),
            "end": round(span[1], 3),
            "said": known,
            "sentence": word.sentence,
        }
        for word, span, known in zip(script.words, times, said, strict=True)
    ]


def share(times: list[list[float] | None], first: int, end: int, surplus: dict[int, int]) -> None:
    """Times for the run [first, end) of unsaid script words: the gap between their neighbours, split evenly, or else
    the span of the neighbour heard longer than written (the word before them when both or neither were), split with
    it."""
    count = end - first
    before = times[first - 1] if first > 0 else None
    after = times[end] if end < len(times) else None
    low = before[1] if before else (after[0] if after else 0.0)
    high = after[0] if after else low
    if high - low >= 0.05 * count:
        step = (high - low) / count
        for k in range(count):
            times[first + k] = [low + k * step, low + (k + 1) * step]
        return
    if before is not None and after is not None and surplus.get(end, 0) > surplus.get(first - 1, 0):
        before = None
    if before is not None:
        start, stop = before
        step = (stop - start) / (count + 1)
        times[first - 1] = [start, start + step]
        for k in range(count):
            times[first + k] = [start + (k + 1) * step, start + (k + 2) * step]
        return
    if after is not None:
        start, stop = after
        step = (stop - start) / (count + 1)
        for k in range(count):
            times[first + k] = [start + k * step, start + (k + 1) * step]
        times[end] = [start + count * step, stop]
        return
    for k in range(count):
        times[first + k] = [0.0, 0.0]


def align(words: Sequence[dict], script: Script) -> dict:
    """The alignment document: each transcript word with its label (the pieces of a word heard apart joined into one),
    the script words never said, and the time of each script word."""
    spoken = [normalize(word["text"]) for word in words]
    labelled = labels(spoken, script)
    aligned: list[dict] = []
    for word, (label, index) in zip(words, labelled, strict=True):
        text = word["text"].strip()
        previous = aligned[-1] if aligned else None
        if label == KEPT and previous is not None and previous["label"] == KEPT and previous["script"] == index:
            # Only a join keeps two spoken words in a row for one script word: they are one word, said once.
            previous["text"], previous["end"] = f"{previous['text']} {text}", word["end"]
            continue
        aligned.append({"text": text, "start": word["start"], "end": word["end"], "label": label, "script": index})
    said = {index for label, index in labelled if label == KEPT}
    missing = [j for j in range(len(script.words)) if j not in said]
    return {"words": aligned, "missing": missing, "script_words": script_times(aligned, script)}
