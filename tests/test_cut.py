"""cut: the edit decision list keeps the said words, shortens long pauses, drops fillers and retakes, and refuses to
cut inside a kept word."""

from __future__ import annotations

import pytest

from video_factory import align, cut
from video_factory import script as scripts

SCRIPT = """---
id: "essai"
titre: "Essai"
plateforme: tiktok
duree_visee: 75
---
Le code est simple.
Et il est rapide.
"""


def word(text: str, start: float, end: float, label: str = align.KEPT, index: int | None = 0) -> dict:
    return {"text": text, "start": start, "end": end, "label": label, "script": index}


def output_word(edl: dict, text: str) -> dict:
    return next(w for w in edl["words"] if w["text"] == text)


@pytest.mark.acceptance("un silence de plus de 400 ms est ramené à 150 ms")
def test_a_silence_over_400_ms_is_brought_down_to_150_ms():
    words = [word("le", 0.5, 0.8), word("code", 0.8, 1.2), word("est", 1.9, 2.1), word("simple", 2.1, 2.6)]
    edl = cut.decide(words, 5.0)
    gap = output_word(edl, "est")["start"] - output_word(edl, "code")["end"]
    assert gap == pytest.approx(0.150, abs=1 / cut.SAMPLE_RATE)
    # A pause of 400 ms or less stays as it is.
    short = [word("le", 0.5, 0.8), word("code", 1.2, 1.5)]
    kept = cut.decide(short, 5.0)
    assert output_word(kept, "code")["start"] - output_word(kept, "le")["end"] == pytest.approx(0.4, abs=1e-4)


@pytest.mark.acceptance("une phrase reprise garde sa dernière prise complète")
def test_a_repeated_sentence_keeps_its_last_complete_take():
    script = scripts.parse(SCRIPT)
    said = ["le", "code", "est", "le", "code", "est", "simple", "et", "il", "est", "rapide"]
    times = [(0.4 * k + 0.1, 0.4 * k + 0.4) for k in range(len(said))]
    transcript = [{"text": text, "start": start, "end": end} for text, (start, end) in zip(said, times, strict=True)]
    aligned = align.align(transcript, script)["words"]
    edl = cut.decide(aligned, 10.0)
    kept = [(w["text"], w["src_start"]) for w in edl["words"]]
    # The first, unfinished « le code est » is gone; the words of the video are those of the complete take.
    assert [text for text, _start in kept] == ["le", "code", "est", "simple", "et", "il", "est", "rapide"]
    assert kept[0][1] == pytest.approx(times[3][0])
    assert all(segment["src_start"] >= times[3][0] - cut.KEPT_SILENCE for segment in edl["segments"])


@pytest.mark.acceptance("une coupe à l'intérieur d'un mot gardé fait échouer l'étape")
def test_a_cut_inside_a_kept_word_fails_the_step():
    words = [word("le", 0.5, 0.8), word("code", 0.8, 1.4), word("simple", 1.5, 2.0)]
    # A segment ending inside a kept word is named, and decide refuses such a list.
    split = [{"src_start": 0.4, "src_end": 1.1, "out_start": 0.0}, {"src_start": 1.3, "src_end": 2.1, "out_start": 0.7}]
    assert cut.problems(split, words) == ["coupe dans le mot gardé « code » (0,80 s à 1,40 s)"]


def test_fillers_and_retakes_go_whole_and_off_script_words_stay():
    words = [
        word("le", 0.5, 0.8),
        word("euh", 0.8, 1.1, align.FILLER, None),
        word("code", 1.1, 1.5, align.KEPT, 1),
        word("vraiment", 1.5, 1.9, align.OFF_SCRIPT, None),
        word("simple", 1.9, 2.3, align.KEPT, 2),
    ]
    edl = cut.decide(words, 5.0)
    assert [w["text"] for w in edl["words"]] == ["le", "code", "vraiment", "simple"]
    # No pause around the filler: it goes exactly, the words around it touch.
    assert output_word(edl, "code")["start"] == pytest.approx(output_word(edl, "le")["end"], abs=1e-4)


def test_what_comes_before_the_first_kept_word_and_after_the_last_is_trimmed():
    words = [
        word("bon", 0.2, 0.5, align.OFF_SCRIPT, None),
        word("le", 1.5, 1.8),
        word("code", 1.8, 2.2, align.KEPT, 1),
        word("voilà", 3.0, 3.4, align.FILLER, None),
    ]
    edl = cut.decide(words, 5.0)
    assert edl["segments"][0]["src_start"] == pytest.approx(1.5 - cut.KEPT_SILENCE / 2)
    assert edl["segments"][-1]["src_end"] == pytest.approx(2.2 + cut.KEPT_SILENCE / 2)
    assert edl["frames"] == round(edl["duration"] * cut.FPS + 0.5 - 1e-9)


def test_nothing_kept_is_refused():
    with pytest.raises(cut.CutError, match="aucun mot gardé"):
        cut.decide([word("bon", 0.2, 0.5, align.OFF_SCRIPT, None)], 5.0)
