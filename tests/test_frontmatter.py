"""The script front matter: a strict subset of YAML that reads the same way here and in any YAML reader."""

from __future__ import annotations

import pytest

from video_factory import frontmatter


def test_rendered_fields_read_back_to_the_same_values():
    fields = {"id": "2026-bilan", "titre": "Pourquoi : la suite « vraie »", "plateforme": "tiktok", "duree_visee": 61}
    text = frontmatter.render(fields) + "Le texte dit.\n"
    assert frontmatter.split(text) == (fields, "Le texte dit.\n")


def test_a_bare_word_a_whole_number_and_a_quoted_text_are_read():
    text = '---\nid: essai\nduree_visee: 90\ntitre: "Un titre, avec : deux points"\n---\ncorps\n'
    fields, body = frontmatter.split(text)
    assert fields == {"id": "essai", "duree_visee": 90, "titre": "Un titre, avec : deux points"}
    assert body == "corps\n"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("id: essai\n", "ligne 1"),
        ("---\nid: essai\n", "sans « --- » de fin"),
        ("---\nid: essai\nid: autre\n---\n", "en double"),
        ("---\nid essai\n---\n", "« clé: valeur » attendu"),
        ("---\nplateforme: yes\n---\n", "ambiguë"),
        ("---\nduree_visee: 75.5\n---\n", "valeur « 75.5 »"),
        ("---\nid: 2026-11-04\n---\n", "valeur « 2026-11-04 »"),
        ('---\ntitre: "ouvert\n---\n', "mal formée"),
        ("---\ntitre: un titre # commentaire\n---\n", "valeur"),
    ],
)
def test_anything_outside_the_subset_is_an_error_that_names_its_line(text, message):
    with pytest.raises(frontmatter.FrontMatterError, match=message):
        frontmatter.split(text)


def test_a_yaml_keyword_or_a_digit_first_text_is_written_between_quotes():
    assert frontmatter.render_value("tiktok") == "tiktok"
    assert frontmatter.render_value("yes") == '"yes"'
    assert frontmatter.render_value("2026-bilan") == '"2026-bilan"'
    assert frontmatter.render_value("Titre à écrire") == '"Titre à écrire"'
