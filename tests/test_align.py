"""align: the transcript aligned on the script; each spoken word kept, retake, filler or off-script."""

from __future__ import annotations

import pytest

from video_factory import align
from video_factory import script as scripts

SCRIPT = """---
id: "essai"
titre: "Essai"
plateforme: tiktok
duree_visee: 75
---
<!-- not spoken -->
Le code est simple.
Et il est rapide [stat: 90 % | des cas] pour tous.
"""


def labelled(said: str) -> list[tuple[str, str, int | None]]:
    words = [{"text": text, "start": 0.3 * k, "end": 0.3 * k + 0.2} for k, text in enumerate(said.split())]
    aligned = align.align(words, scripts.parse(SCRIPT))["words"]
    return [(w["text"], w["label"], w["script"]) for w in aligned]


@pytest.mark.acceptance("l'alignement marque les hésitations, les reprises et les mots hors script")
def test_alignment_marks_fillers_retakes_and_off_script_words():
    said = "bon on y va le code est euh le code est simple et il est vraiment rapide du coup pour tous"
    found = labelled(said)
    assert found[0] == ("bon", "filler", None)
    assert found[1:4] == [("on", "off_script", None), ("y", "off_script", None), ("va", "off_script", None)]
    assert [label for _text, label, _index in found[4:8]] == ["retake", "retake", "retake", "filler"]
    assert found[8:12] == [("le", "kept", 0), ("code", "kept", 1), ("est", "kept", 2), ("simple", "kept", 3)]
    assert ("vraiment", "off_script", None) in found
    assert [label for text, label, _index in found if text in ("du", "coup")] == ["filler", "filler"]
    assert [index for _text, label, index in found if label == "kept"] == list(range(10))


def test_a_clean_reading_keeps_every_word_in_order():
    found = labelled("le code est simple et il est rapide pour tous")
    assert [(label, index) for _text, label, index in found] == [("kept", k) for k in range(10)]


def test_a_stutter_and_a_restart_into_the_previous_sentence_are_retakes():
    stutter = labelled("le le code est simple et il est rapide pour tous")
    assert stutter[0][1:] == ("retake", None)
    assert stutter[1][1:] == ("kept", 0)
    restart = labelled("le code est simple et il est le code est simple et il est rapide pour tous")
    assert [label for _text, label, _index in restart[:7]] == ["retake"] * 7
    assert [index for _text, label, index in restart if label == "kept"] == list(range(10))


def test_a_complete_take_followed_by_an_unfinished_one_keeps_the_complete_one():
    found = labelled("le code est simple le code et il est rapide pour tous")
    assert [index for _text, label, index in found[:4]] == [0, 1, 2, 3]
    assert [label for _text, label, _index in found[4:6]] == ["retake", "retake"]


def test_chatter_between_two_takes_of_a_sentence_is_part_of_the_retake():
    found = labelled("le code est attendez je reprends le code est simple et il est rapide pour tous")
    assert [label for _text, label, _index in found[:6]] == ["retake"] * 6


def test_a_lexicon_word_the_script_says_is_kept():
    script = scripts.parse(SCRIPT.replace("Le code est simple.", "Bon, le code est simple."))
    said = "bon le code est simple et il est rapide pour tous"
    words = [{"text": t, "start": 0.0, "end": 0.1} for t in said.split(" ")]
    aligned = align.align(words, script)["words"]
    assert (aligned[0]["label"], aligned[0]["script"]) == ("kept", 0)


def test_missing_script_words_are_listed():
    said = "le code simple et il est rapide pour tous"
    words = [{"text": t, "start": 0.0, "end": 0.1} for t in said.split(" ")]
    assert align.align(words, scripts.parse(SCRIPT))["missing"] == [2]


def test_a_word_heard_in_pieces_is_one_kept_word_with_the_time_of_its_pieces():
    said = ["le", "co", "de", "est", "simple"]
    words = [{"text": t, "start": 0.5 * k, "end": 0.5 * k + 0.4} for k, t in enumerate(said)]
    found = align.align(words, scripts.parse(SCRIPT))
    assert found["words"][1] == {"text": "co de", "start": 0.5, "end": 1.4, "label": "kept", "script": 1}
    assert [word["script"] for word in found["words"]] == [0, 1, 2, 3]
    assert found["script_words"][1] == {"text": "code", "start": 0.5, "end": 1.4, "said": True, "sentence": 0}
