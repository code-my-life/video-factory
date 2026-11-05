"""A showcase (« vitrine »): its script read line by line with its shots, the text of its voice for ElevenLabs, and
each word of the script timed on the voice, whatever whisper heard."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from video_factory import align, cli, frontmatter, schemas, vitrine
from video_factory import script as scripts
from video_factory.paths import SCRIPT_SCHEMA, SCRIPT_VITRINE_TEMPLATE
from video_factory.vitrine import Banner, Cover, EndRow, Piece

HEADER = """---
id: "essai"
titre: "Essai"
plateforme: tiktok
duree_visee: 20
genre: vitrine
theme: primer
---
"""
FIRST_LINE = HEADER.count("\n") + 1  # the line number of the first line of the body

SCRIPT = (
    HEADER.replace(
        "theme: primer\n",
        "theme: primer\n"
        'bandeau: "Essaie la démo | Elle tourne dans ton navigateur | 6,5 | 2,4"\n'
        'vignette: "On dirait pas, | mais je *code*"\n'
        'vignette_image: "12,5"\n',
    )
    + "\n".join(
        [
            "<!-- not spoken -->",
            "[ton: chuckles] Coucou, je code ! [plan: ecran | depuis 0,3 | durée 4,6]",
            "Je vois tout sur factory-live ! [plan: telephone | durée 5 | voix 0,15]",
            "Pour les PR, je vois le diff. [jumeaux: rush-pr | depuis 29,5 | durée 4,5 | voix 0,3 | avant 0 362 "
            "| après 960 362 | taille 940 612 | volet 1,3 0,5]",
            "[ton: thoughtful] Je réponds, et la carte repart. [suite: voix 3,7]",
            "Je lis tout, mot pour mot ! [plan: fil | durée 1,15 | voix 0.4] [plan: fil | depuis 2,35 | durée 7,25]",
            "[ton: excited] Essaie [appel: play | Essaie la démo | lien en bio] la démo ! [fin: voix 0,4]",
        ]
    )
    + "\n"
)


def line_texts(found: vitrine.Vitrine) -> list[str]:
    return [" ".join(word.text for word in found.words[line.first : line.last]) for line in found.lines]


def test_a_showcase_script_reads_line_by_line_with_its_shots_and_its_settings():
    found = vitrine.parse(SCRIPT)
    assert (found.theme, found.duration) == ("primer", 20)
    assert found.banner == Banner("Essaie la démo", "Elle tourne dans ton navigateur", 6.5, 2.4)
    assert found.cover == Cover(("On dirait pas,", "mais je *code*"), 12.5)
    # The annotations add no spoken word; a mark written apart stays with its word.
    assert line_texts(found) == [
        "Coucou, je code\u00a0!",
        "Je vois tout sur factory-live\u00a0!",
        "Pour les PR, je vois le diff.",
        "Je réponds, et la carte repart.",
        "Je lis tout, mot pour mot\u00a0!",
        "Essaie la démo\u00a0!",
    ]
    first, phone, twins, goes_on, two_shots, end = found.lines
    assert [line.number for line in found.lines] == list(range(FIRST_LINE + 4, FIRST_LINE + 10))
    assert (first.pieces, first.voice, first.tones) == ((Piece("plan", "ecran", 0.3, 4.6),), 0.0, ((0, "chuckles"),))
    assert (phone.pieces, phone.voice) == ((Piece("plan", "telephone", 0.0, 5.0),), 0.15)
    assert twins.pieces == (Piece("jumeaux", "rush-pr", 29.5, 4.5, (0, 362), (960, 362), (940, 612), (1.3, 0.5)),)
    assert twins.voice == 0.3
    assert (goes_on.follows, goes_on.pieces, goes_on.voice) == (True, (), 3.7)
    assert goes_on.tones == ((goes_on.first, "thoughtful"),)
    assert two_shots.pieces == (Piece("plan", "fil", 0.0, 1.15), Piece("plan", "fil", 2.35, 7.25))
    assert two_shots.voice == 0.4
    assert (end.end_card, end.pieces, end.voice) == (True, (), 0.4)
    # The row of the end card is lit on the word before it, « Essaie ».
    assert end.rows == (EndRow("play", "Essaie la démo", "lien en bio", end.first),)
    assert found.words[end.rows[0].word].text == "Essaie"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            "Coucou tout le monde.",
            "ligne {0} : chaque réplique a des « plan » ou des « jumeaux », ou « suite », ou « fin »",
        ),
        ("Coucou. [suite: voix 1]", "ligne {0} : la première réplique ne peut pas être une « suite »"),
        ("Coucou. [plan: a]\nEssaie [appel: play | Démo | lien] la démo. [plan: b]", "ligne {1} : un « appel » se dit"),
        ("[appel: play | Démo | lien] Essaie. [fin]", "ligne {0} : « appel : icône | titre | texte », après le mot"),
        ("Le diff. [jumeaux: a | avant 0 0 | après 9 0 | taille 9 9]", "ligne {0} : des jumeaux sans « volet »"),
        ("Le diff. [jumeaux: a | avant 0 | après 9 0 | taille 9 9 | volet 1 1]", "ligne {0} : deux nombres attendus"),
        ("Coucou. [plan: a | durée 4s]", "ligne {0} : « 4s » n'est pas un nombre de secondes"),
        ("Coucou. [plan: a | vitesse 2]", "ligne {0} : réglage « vitesse » inconnu (permis : depuis, durée, voix)"),
        ("Coucou. [plan: a | durée 2 | durée 3]", "ligne {0} : réglage « durée » en double"),
        ("Coucou. [plan: a | voix 1] [plan: b | voix 2]", "ligne {0} : « voix » donnée deux fois"),
        ("Coucou. [plan: un plan]", "ligne {0} : le nom de la capture d'abord, sans espace"),
        ("Coucou. [plan: a] [zoom]", "ligne {0} : annotation « [zoom] » inconnue dans une vitrine"),
        ("Coucou. [plan: a] [ton: excited]", "ligne {0} : un « ton » se place avant un mot de sa réplique"),
    ],
)
def test_a_broken_showcase_line_is_refused_with_its_line_number(body, message):
    with pytest.raises(scripts.ScriptError, match=re.escape(message.format(FIRST_LINE, FIRST_LINE + 1))):
        vitrine.parse(HEADER + body + "\n")


def test_a_showcase_names_its_theme_and_its_duration_and_a_face_camera_script_is_not_a_showcase():
    without_theme = HEADER.replace("theme: primer\n", "")
    with pytest.raises(scripts.ScriptError, match="une vitrine nomme son thème"):
        vitrine.parse(without_theme + "Coucou. [plan: a]\n")
    fields, _body = frontmatter.split(without_theme)
    assert schemas.problems(fields, SCRIPT_SCHEMA) != []
    without_duration = HEADER.replace("duree_visee: 20\n", "")
    with pytest.raises(scripts.ScriptError, match="« duree_visee », la durée visée en secondes, manque"):
        vitrine.parse(without_duration + "Coucou. [plan: a]\n")
    with pytest.raises(scripts.ScriptError, match="n'est pas une vitrine"):
        vitrine.parse(HEADER.replace("genre: vitrine\n", "") + "Coucou.\n")


@pytest.mark.acceptance("vf voix écrit la voix réplique par réplique, avec ses tons et une pause entre les répliques")
def test_vf_voix_writes_the_voice_line_by_line_with_its_tones_and_a_pause_between_lines():
    found = vitrine.parse(SCRIPT)
    # Eleven v3: the tones and the pauses are tags; a line that opens on a tone needs no pause before it.
    assert vitrine.elevenlabs_text(found) == (
        "[chuckles] Coucou, je code ! [short pause] Je vois tout sur factory-live ! [short pause] "
        "Pour les PR, je vois le diff. [thoughtful] Je réponds, et la carte repart. [short pause] "
        "Je lis tout, mot pour mot ! [excited] Essaie la démo !\n"
    )
    # Eleven Multilingual v2 reads no tag: a 0.8 s break between lines, and no tone.
    assert vitrine.elevenlabs_text(found, "v2") == (
        "Coucou, je code !\n"
        '<break time="0.8s" />\n'
        "Je vois tout sur factory-live !\n"
        '<break time="0.8s" />\n'
        "Pour les PR, je vois le diff.\n"
        '<break time="0.8s" />\n'
        "Je réponds, et la carte repart.\n"
        '<break time="0.8s" />\n'
        "Je lis tout, mot pour mot !\n"
        '<break time="0.8s" />\n'
        "Essaie la démo !\n"
    )


def test_vf_new_vitrine_then_vf_voix_on_the_command_line(tmp_path: Path, monkeypatch, capsys):
    content = tmp_path / "video-content"
    (content / ".git").mkdir(parents=True)
    monkeypatch.setenv("VF_CONTENT", str(content))
    assert cli.main(["new", "essai", "--vitrine"]) == 0
    script_path = content / "videos" / "essai" / "script.md"
    text = script_path.read_text(encoding="utf-8")
    fields, _body = frontmatter.split(text)
    assert schemas.problems(fields, SCRIPT_SCHEMA) == []
    assert (fields["genre"], fields["theme"]) == ("vitrine", "primer")
    assert "{{id}}" in SCRIPT_VITRINE_TEMPLATE.read_text(encoding="utf-8")
    # A new showcase has no line yet: nothing to say.
    capsys.readouterr()
    assert cli.main(["voix", "essai"]) == 1
    assert "le script n'a aucun texte dit" in capsys.readouterr().err
    script_path.write_text(text + "[ton: excited] Coucou ! [plan: ecran]\nÀ bientôt. [fin]\n", encoding="utf-8")
    assert cli.main(["voix", "essai", "--modele", "v2"]) == 0
    written = (content / "videos" / "essai" / "voix-elevenlabs.txt").read_text(encoding="utf-8")
    assert written == 'Coucou !\n<break time="0.8s" />\nÀ bientôt.\n'
    assert written in capsys.readouterr().out


HEARD = (
    HEADER
    + """Je vois tout sur factory-live ! [plan: a]
Pour les PR, je vois le diff. [plan: b]
Plus d'aller-retour dans Claude. [plan: c]
"""
)


def whisper(said: str, gaps: dict[int, float] | None = None) -> list[dict]:
    """Words as whisper gives them, 0.4 s each, one after the other; gaps adds a silence before the word at an index."""
    words, clock = [], 0.0
    for index, text in enumerate(said.split()):
        clock += (gaps or {}).get(index, 0.0)
        words.append({"text": text, "start": round(clock, 3), "end": round(clock + 0.4, 3)})
        clock += 0.4
    return words


def timed(said: str, gaps: dict[int, float] | None = None) -> dict[str, tuple[float, float, bool]]:
    script = scripts.parse(HEARD)
    found = align.align(whisper(said, gaps), script)["script_words"]
    assert [word["text"] for word in found] == [word.text for word in script.words]
    return {word["text"]: (word["start"], word["end"], word["said"]) for word in found}


@pytest.mark.acceptance("un mot mal entendu prend le texte du script")
def test_a_misheard_word_takes_the_text_of_the_script():
    found = timed("Je vois tout sur Factory Live! Pour l'EPR, je vois le diff. Plus d'aller-retour dans Cloud.")
    # « Cloud » said for « Claude »: the caption reads « Claude. », at the time of « Cloud. ».
    assert found["Claude."] == (6.0, 6.4, True)
    # « factory-live » heard in two pieces takes the time of both.
    assert found["factory-live\u00a0!"] == (1.6, 2.4, True)
    # « les PR » heard as one word, « l'EPR »: the two words of the script share its time, and one of them was not
    # heard as such.
    assert found["les"][:2] == (2.8, 3.0)
    assert found["PR,"][:2] == (3.0, 3.2)
    assert [said for _start, _end, said in found.values()].count(False) == 1


def test_a_word_whisper_left_out_takes_the_silence_where_it_was_said():
    found = timed("Je vois tout sur factory-live! Pour PR, je vois le diff. Plus d'aller-retour dans Claude.", {6: 0.3})
    assert found["Pour"][:2] == (2.0, 2.4)
    assert found["les"] == (2.4, 2.7, False)
    assert found["PR,"] == (2.7, 3.1, True)


def test_two_tones_before_one_word_are_both_said_in_their_order():
    found = vitrine.parse(HEADER + "[ton: thoughtful] [ton: whispers] Bonjour. [plan: a]\n")
    assert vitrine.elevenlabs_text(found) == "[thoughtful] [whispers] Bonjour.\n"
