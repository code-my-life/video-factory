"""The Script station: the `studio-writer` profile drafts script.md, and code checks the draft before it is kept.

The model only writes text. Its draft is accepted by rules, never by another model: the front matter follows the
script schema with the video's id, the spoken text is long enough for 61 to 65 s and not longer, and no em dash is
written. A refused draft leaves script.md as it was.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from video_factory import script, videos

PROFILE = "studio-writer"
# About 2.6 words a second, like the first script (162 words for about 63 s), with room on both sides.
WORDS = (140, 190)
EM_DASH = "\u2014"
FENCE = re.compile(r"^```[a-z]*\s*$", re.MULTILINE)
CLOSING = re.compile(r"(?:\n---\s*)+$")

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


class WriterError(Exception):
    """No acceptable draft: the profile failed, or its draft breaks a rule."""


@dataclass(frozen=True)
class Brief:
    video_id: str
    idea: str
    ideas: str
    brand: str
    template: str
    current: str = ""
    redo: str = ""


def prompt(brief: Brief) -> str:
    parts = [
        f"Écris le brouillon du script de la vidéo « {brief.video_id} ».",
        f"Idée : {brief.idea}",
        "Rends le fichier script.md entier, et rien d'autre : l'en-tête entre deux lignes « --- », puis le texte dit.",
        f'En-tête : id: "{brief.video_id}", titre entre guillemets, plateforme: tiktok, duree_visee de 61 à 65.',
        f"Texte dit : une phrase par ligne, de {WORDS[0]} à {WORDS[1]} mots en tout (61 à 65 secondes), "
        "annotations entre crochets comme dans le gabarit ([stat: …], [etapes: …], [code: …], [capture: …], [zoom]).",
        "Aucun tiret cadratin. Chaque affirmation doit être vraie et vérifiable ; rien d'inventé.",
        "## Gabarit",
        brief.template,
        "## Liste des idées (idees.md)",
        brief.ideas or "(vide)",
        "## Positionnement de la marque",
        brief.brand or "(non fourni)",
    ]
    if brief.redo:
        parts += ["## Script actuel, à refaire", brief.current, "## Demande du propriétaire", brief.redo]
    return "\n\n".join(parts) + "\n"


def extract(answer: str) -> str:
    """The script.md in the model's answer: code fences dropped, from the first « --- » line on."""
    text = FENCE.sub("", answer).strip()
    start = text.find("---")
    text = text[start:] if start >= 0 else text
    # A model often closes the file with a second fence line; the body must not end on one.
    return CLOSING.sub("", text.strip()).strip() + "\n"


def problems(text: str, video_id: str) -> list[str]:
    """Every rule the draft breaks: the schema and the id, the parser that align and compose use, the length."""
    found = videos.script_problems(text, video_id)
    if found:
        return found
    try:
        words = len(script.parse(text).words)
    except script.ScriptError as exc:
        return [f"texte dit : {exc}"]
    if not WORDS[0] <= words <= WORDS[1]:
        found.append(f"texte dit : {words} mots, attendu de {WORDS[0]} à {WORDS[1]}")
    if EM_DASH in text:
        found.append("tiret cadratin dans le brouillon")
    return found


def draft(brief: Brief, run: Runner, hermes: str = "hermes") -> str:
    """Ask the profile once, without tools, and return the draft if it passes every rule."""
    done = run([hermes, "-p", PROFILE, "chat", "--oneshot", "-Q", "-q", prompt(brief)])
    if done.returncode != 0:
        why = (done.stderr or done.stdout or "").strip()[-300:]
        raise WriterError(f"{PROFILE} a échoué ({done.returncode}) : {why}")
    text = extract(done.stdout)
    found = problems(text, brief.video_id)
    if found:
        raise WriterError("brouillon refusé : " + " ; ".join(found))
    return text


def write(script_path: Path, text: str) -> None:
    staged = script_path.with_name(f".{script_path.name}.new")
    staged.write_text(text, encoding="utf-8")
    staged.replace(script_path)
