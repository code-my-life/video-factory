"""The body of script.md: one sentence per line, words in written and normalized form, and the annotations."""

from __future__ import annotations

import pytest

from video_factory import script as scripts

HEAD = '---\nid: "essai"\ntitre: "Essai"\nplateforme: tiktok\nduree_visee: 63\n---\n'


def test_sentences_words_and_comments():
    found = scripts.parse(HEAD + "<!-- consigne\nsur deux lignes -->\nL\u2019IA écrit, vite.\n\nEt « bien ».\n")
    assert [w.text for w in found.words] == ["L\u2019IA", "écrit,", "vite.", "Et", "«\u00a0bien\u00a0»."]
    assert [w.norm for w in found.words] == ["l'ia", "écrit", "vite", "et", "bien"]
    assert found.sentences == ((0, 3), (3, 5))


def test_a_mark_written_apart_stays_with_its_word_for_the_captions():
    found = scripts.parse(HEAD + "Je pisse du code ! Une ligne d'usine : le brief, ( vite ).\n")
    assert [w.text for w in found.words][3:] == [
        "code\u00a0!",
        "Une",
        "ligne",
        "d'usine\u00a0:",
        "le",
        "brief,",
        "(vite).",
    ]
    assert [w.norm for w in found.words][3:7] == ["code", "une", "ligne", "d'usine"]


def test_a_shot_at_the_end_of_a_line_covers_the_sentence_and_a_shot_inside_starts_on_the_word_before():
    found = scripts.parse(HEAD + "Un deux trois. [etapes: A | B | C]\nQuatre cinq [stat: 9 | postes] six.\n")
    assert [(s.kind, s.anchor, s.parts()) for s in found.shots] == [
        ("etapes", 0, ["A", "B", "C"]),
        ("stat", 4, ["9", "postes"]),
    ]


def test_captures_code_and_punch_ins():
    found = scripts.parse(HEAD + "Voici l'écran. [capture: ligne]\nTape ceci [zoom] vite. [code: vf run <id>]\n")
    assert [(s.kind, s.content, s.anchor) for s in found.shots] == [("capture", "ligne", 0), ("code", "vf run <id>", 2)]
    assert [z.anchor for z in found.zooms] == [3]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("Un mot [inconnu: x].\n", "ligne 7 : annotation « [inconnu: x] » inconnue ou vide"),
        ("Un mot [stat:].\n", "ligne 7 : annotation « [stat:] » inconnue ou vide"),
        ("[zoom]\n", "ligne 7 : une annotation sans texte dit"),
        ("Un [mot.\n", "ligne 7 : crochet sans annotation"),
        ("<!-- rien -->\n", "le script n'a aucun texte dit"),
    ],
)
def test_a_broken_annotation_is_refused_with_its_line(body, message):
    with pytest.raises(scripts.ScriptError, match=message.replace("[", r"\[").replace("]", r"\]")):
        scripts.parse(HEAD + body)
