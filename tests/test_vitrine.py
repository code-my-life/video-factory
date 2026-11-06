"""A showcase (« vitrine »): its script read line by line with its shots, the text of its voice for ElevenLabs, and
each word of the script timed on the voice, whatever whisper heard."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from video_factory import align, cli, frontmatter, montage, schemas, vitrine
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
            "| après 960 362 | taille 940 612 | volet 1,3 0,5 | étiquettes Avant · sans la PR / Après · PR #37]",
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
    assert twins.pieces == (
        Piece(
            "jumeaux",
            "rush-pr",
            29.5,
            4.5,
            (0, 362),
            (960, 362),
            (940, 612),
            (1.3, 0.5),
            ("Avant · sans la PR", "Après · PR #37"),
        ),
    )
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
        (
            "Le diff. [jumeaux: a | avant 0 | après 9 0 | taille 9 9 | volet 1 1 | étiquettes A / B]",
            "ligne {0} : deux nombres",
        ),
        (
            "Le diff. [jumeaux: a | avant 0 0 | après 9 0 | taille 9 9 | volet 1 1]",
            "ligne {0} : des jumeaux sans « étiquettes »",
        ),
        (
            "Le diff. [jumeaux: a | avant 0 0 | après 9 0 | taille 9 9 | volet 1 1 | étiquettes A]",
            "étiquettes <avant> / <après>",
        ),
        (
            "Coucou. [plan: a]\nÀ bientôt. [fin]\nEncore. [plan: b]",
            "ligne {1} : seule la dernière réplique se dit sur l'écran",
        ),
        ("Coucou. [plan: a | durée 4s]", "ligne {0} : « 4s » n'est pas un nombre de secondes"),
        ("Coucou. [plan: a | vitesse 2]", "ligne {0} : réglage « vitesse » inconnu (permis : depuis, durée, voix)"),
        ("Coucou. [plan: a | durée 2 | durée 3]", "ligne {0} : réglage « durée » en double"),
        ("Coucou. [plan: a | voix 1] [plan: b | voix 2]", "ligne {0} : « voix » donnée deux fois"),
        ("Coucou. [plan: un plan]", "ligne {0} : « un plan » : le nom de la capture d'abord, en minuscules"),
        ("Coucou. [plan: Plan_1]", "ligne {0} : « Plan_1 » : le nom de la capture d'abord, en minuscules"),
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


MONTAGE = (
    HEADER.replace("duree_visee: 20", "duree_visee: 12")
    + "Un deux trois. [plan: ecran | durée 4 | voix 0,5]\n"
    + "Quatre cinq. [suite: voix 2,5]\n"
    + "Six sept huit. [plan: rush | depuis 1 | durée 3]\n"
    + "Neuf dix. [fin: voix 0,4]\n"
)


def montage_of(text: str, said: list[tuple[str, float, float]], silences: list[list[float]], length: float) -> dict:
    words = [{"text": text, "start": start, "end": end} for text, start, end in said]
    return montage.decide(vitrine.parse(text), words, silences, length, {})


@pytest.mark.acceptance("une réplique est placée sur son plan avec son décalage")
def test_a_line_is_placed_on_its_shot_with_its_offset():
    said = [("Un", 0.2, 0.5), ("deux", 0.5, 0.8), ("trois.", 0.8, 1.2), ("Quatre", 2.0, 2.4), ("cinq.", 2.4, 2.9)]
    said += [("Six", 4.0, 4.3), ("sept", 4.3, 4.6), ("huit.", 4.6, 5.0), ("Neuf", 6.0, 6.3), ("dix.", 6.3, 6.8)]
    silences = [[1.2, 2.0], [2.9, 4.0], [5.0, 6.0]]
    edl = montage_of(MONTAGE, said, silences, 7.0)
    assert [(shot["start"], shot["end"], shot["kind"]) for shot in edl["shots"]] == [
        (0.0, 4.0, "plan"),
        (4.0, 7.0, "plan"),
        (7.0, 12.0, "fin"),
    ]
    # Each line's stretch of the voice runs from the silence before it to the silence after it, and is heard « voix »
    # seconds after its shot starts: its own, the one before for a « suite », the end card for « fin ».
    assert [(s["source_start"], s["source_end"], s["at"]) for s in edl["spoken"]] == [
        (0.0, 1.2, 0.5),
        (2.0, 2.9, 2.5),
        (4.0, 5.0, 4.0),
        (6.0, 7.0, 7.4),
    ]
    # Each word follows its line: « Quatre », said 2,0 s into the voice, is heard 2,5 s into the video.
    assert [(w["text"], w["start"]) for w in edl["words"]][3:6] == [("Quatre", 2.5), ("cinq.", 2.9), ("Six", 4.0)]
    graph = montage.voice_command(Path("voix.wav"), edl["spoken"], edl["duration"], Path("out.wav"))[3]
    assert [int(delay) for delay in re.findall(r"adelay=(\d+)", graph)] == [500, 2440, 3940, 7340]
    assert "atrim=0:12.0[v]" in graph


@pytest.mark.acceptance("les sous-titres se coupent aux vraies pauses et un mot court ne reste jamais seul")
def test_captions_are_cut_at_real_pauses_and_a_short_word_never_stays_alone():
    text = (
        HEADER
        + "Je vois et puis tout le reste du code. [plan: a | durée 15]\nC'est fini, vraiment. [plan: b | durée 5]\n"
    )
    said = [("Je", 0.0, 0.2), ("vois", 0.2, 0.5), ("et", 1.0, 1.2), ("puis", 1.9, 2.2), ("tout", 2.2, 2.5)]
    said += [("le", 2.5, 2.6), ("reste", 2.6, 3.0), ("du", 3.0, 3.1), ("code.", 3.1, 3.5)]
    said += [("C'est", 4.0, 4.3), ("fini,", 4.3, 4.6), ("vraiment.", 4.6, 5.0)]
    found = montage.decide(vitrine.parse(text), [{"text": t, "start": s, "end": e} for t, s, e in said], [], 5.0, {})
    assert [group["text"] for group in found["groups"]] == [
        "Je vois",  # a pause of 0,5 s (over 0,35 s) closes it
        "et puis tout",  # « et » alone waits for the next word, across the pause
        "le reste du",  # three words at most
        "code.",
        "C'est fini, vraiment.",  # a line of four words or fewer is shown whole
    ]
    # A group stays half a second after its last word, until the next one opens.
    assert [(group["start"], group["end"]) for group in found["groups"]][:2] == [(0.0, 1.0), (1.0, 2.5)]


def test_an_unknown_theme_is_refused_with_the_known_ones(tmp_path: Path):
    with pytest.raises(montage.MontageError, match="thème « néon » inconnu ; thèmes : primer"):
        montage.theme_folder("néon")
    with pytest.raises(montage.MontageError, match="thèmes : aucun"):
        montage.theme_folder("primer", tmp_path)


@pytest.mark.acceptance("le thème et la voix viennent du script, pas du code")
def test_the_theme_and_the_voice_come_from_the_script_not_from_the_code(tmp_path: Path):
    # The theme is the folder the script names: another folder, another page, without a line of code.
    other = tmp_path / "themes" / "sobre"
    shutil.copytree(montage.theme_folder("primer"), other)
    template = (other / "index.html").read_text(encoding="utf-8")
    (other / "index.html").write_text(template.replace("--accent: #4493f8;", "--accent: #ff8c00;"), encoding="utf-8")
    said = [("Un", 0.2, 0.5), ("deux", 0.5, 0.8), ("trois.", 0.8, 1.2), ("Quatre", 2.0, 2.4), ("cinq.", 2.4, 2.9)]
    said += [("Six", 4.0, 4.3), ("sept", 4.3, 4.6), ("huit.", 4.6, 5.0), ("Neuf", 6.0, 6.3), ("dix.", 6.3, 6.8)]
    for theme, accent in (("primer", "#4493f8"), ("sobre", "#ff8c00")):
        showcase = vitrine.parse(MONTAGE.replace("theme: primer", f"theme: {theme}"))
        folder = montage.theme_folder(showcase.theme, tmp_path / "themes" if theme == "sobre" else montage.THEMES)
        edl = montage_of(MONTAGE, said, [[1.2, 2.0], [2.9, 4.0], [5.0, 6.0]], 7.0)
        assert f"--accent: {accent};" in montage.page(folder, showcase, edl)
    # The voice is the file the video registered (vf ingest --voix): the montage only names it.
    graph = montage.voice_command(Path("autre-voix.wav"), edl["spoken"], edl["duration"], Path("out.wav"))
    assert graph[:2] == ["-i", Path("autre-voix.wav")]


def test_the_voice_of_a_line_keeps_its_padding_only_where_there_is_room():
    # The voice opens on a silence and the first line starts with the video: no padding before it. The next two lines
    # have no silence between them: neither takes the other's speech.
    text = (
        HEADER.replace("duree_visee: 20", "duree_visee: 12")
        + "Un deux. [plan: a | durée 6]\nTrois quatre. [suite: voix 2]\nCinq. [fin]\n"
    )
    said = [("Un", 0.5, 0.8), ("deux.", 0.8, 1.2), ("Trois", 1.2, 1.5), ("quatre.", 1.5, 1.9), ("Cinq.", 3.0, 3.4)]
    words = [{"text": t, "start": a, "end": b} for t, a, b in said]
    edl = montage.decide(vitrine.parse(text), words, [[0.0, 0.5], [1.9, 3.0]], 3.6, {})
    assert [(s["source_start"], s["source_end"], s["at"]) for s in edl["spoken"]] == [
        (0.5, 1.2, 0.0),
        (1.2, 1.9, 2.0),
        (3.0, 3.6, 6.0),
    ]
    graph = montage.voice_command(Path("voix.wav"), edl["spoken"], edl["duration"], Path("out.wav"))[3]
    assert re.findall(r"atrim=([0-9.]+):([0-9.]+),", graph) == [
        ("0.500", "1.200"),
        ("1.200", "2.020"),
        ("2.940", "3.720"),
    ]
    assert [int(delay) for delay in re.findall(r"adelay=(\d+)", graph)] == [0, 2000, 5940]


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (
            "Un deux. [plan: a | durée 6]\nTrois quatre. [suite: voix 0,5]\nCinq. [fin]\n",
            "après le début de la réplique",
        ),
        (
            "Un deux. [plan: a | durée 6]\nTrois quatre. [suite: voix 2]\nCinq. [fin: voix 5,9]\n",
            "après la fin de la vidéo",
        ),
    ],
)
def test_a_line_whose_voice_would_overlap_the_next_one_or_end_after_the_video_is_refused(lines, message):
    said = [("Un", 0.5, 0.8), ("deux.", 0.8, 1.2), ("Trois", 1.2, 1.5), ("quatre.", 1.5, 1.9), ("Cinq.", 3.0, 3.4)]
    words = [{"text": t, "start": a, "end": b} for t, a, b in said]
    text = HEADER.replace("duree_visee: 20", "duree_visee: 12") + lines
    with pytest.raises(montage.MontageError, match=message):
        montage.decide(vitrine.parse(text), words, [[0.0, 0.5], [1.9, 3.0]], 3.6, {})
