"""`vf publish <id>`: the files and the caption of a video whose master passed qc, ready to be posted by hand.

Publication is manual for now (docs/publication.md): this prepares `VF_MEDIA/publication/<id>/` with the TikTok
export, the master and the caption, and checks nothing is missing. It never posts anything.

The caption is the script's « legende » (its title otherwise), a line saying the voice was generated when « voix_ia »
names the tool, the robot credit, then the script's « mots_cles ». An AI voice also prints the reminder to switch on
each platform's AI label: AI is always shown, never hidden (docs/publication.md). A showcase with a « vignette » gets
its cover: the frame of the TikTok export at « vignette_image » under the text of the vignette, in its theme's
`cover.html`, rendered by the pinned Chromium.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from video_factory import compose, frontmatter, media, montage, store, vitrine
from video_factory.tools import Toolbox

FOLDER = "publication"
CAPTION_NAME = "legende.txt"
FILES = {"tiktok": "tiktok.mp4", "master": "master.mp4"}
# The credit the helmet's licence asks for, word for word as docs/publication.md gives it.
ROBOT_CREDIT = (
    "Robot : « Rank 3 Police Unit » de nikvili (Sketchfab), CC BY 4.0, modifié. "
    "sketchfab.com/3d-models/rank-3-police-unit-d7698f6a7acf49c68ff0a50c5a1b1d52"
)


COVER_NAME = "couverture.png"
COVER_SIZE = (1080, 1920)
AI_LINE = "Voix générée par IA ({tool})."
AI_REMINDER = "Étiquette IA à activer sur TikTok, YouTube et Instagram : voix générée par {tool} (docs/publication.md)."
EMPHASIS = re.compile(r"\*([^*]+)\*")
DRIVER = """
const {{ chromium }} = require({playwright});
(async () => {{
  const browser = await chromium.launch({{
    executablePath: {chromium},
    args: ["--disable-gpu", "--force-color-profile=srgb"],
  }});
  const page = await browser.newPage({{ viewport: {{ width: {width}, height: {height} }}, deviceScaleFactor: 1 }});
  await page.goto({url});
  await page.waitForSelector("body[data-ready]");
  await page.screenshot({{ path: {out}, type: "png" }});
  await browser.close();
}})();
"""


class PublishError(Exception):
    """The video cannot be published yet; the message says why."""


@dataclass(frozen=True)
class Cover:
    lines: tuple[str, ...]
    at: float  # the second of the TikTok export whose frame carries it
    theme: str


@dataclass(frozen=True)
class Publication:
    caption: str
    sources: dict[str, Path]
    cover: Cover | None = None
    reminders: tuple[str, ...] = ()


def caption(fields: dict) -> str:
    """The sentence of the subject (« legende », or the title), the AI voice when there is one, the robot credit, and
    the keywords (« mots_cles ») when the script gives them."""
    parts = [str(fields.get("legende") or fields["titre"])]
    if fields.get("voix_ia"):
        parts.append(AI_LINE.format(tool=fields["voix_ia"]))
    parts.append(ROBOT_CREDIT)
    if fields.get("mots_cles"):
        parts.append(str(fields["mots_cles"]))
    return "\n\n".join(parts) + "\n"


def cover_of(script_text: str) -> Cover | None:
    """The cover a showcase asks for: the lines of its « vignette » on the frame at « vignette_image »."""
    fields, _body = frontmatter.split(script_text)
    if fields.get("genre") != "vitrine" or "vignette" not in fields:
        return None
    try:
        showcase = vitrine.parse(script_text)
    except ValueError as exc:
        raise PublishError(f"script.md : {exc}") from exc
    if showcase.cover is None or showcase.cover.at is None:
        raise PublishError("la vignette n'a pas d'image : vignette_image, la seconde de la vidéo qui la porte")
    return Cover(showcase.cover.lines, showcase.cover.at, showcase.theme)


def emphasized(line: str) -> str:
    """A line of the vignette as HTML: escaped, a word between asterisks in <em>."""
    return EMPHASIS.sub(lambda match: f"<em>{match.group(1)}</em>", html.escape(line, quote=False))


def cover_page(theme: Path, lines: Sequence[str]) -> str:
    """The theme's cover page with the lines of the vignette, a word between asterisks in the accent colour."""
    rows = "".join(f"<div>{emphasized(line)}</div>" for line in lines)
    return compose.fill((theme / "cover.html").read_text(encoding="utf-8"), {"LINES": rows})


def render_cover(toolbox: Toolbox, cover: Cover, tiktok: Path, work: Path, out: Path) -> Path:
    """The cover rendered at 1080x1920 by the pinned Chromium, without the network, into out."""
    theme = montage.theme_folder(cover.theme)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    media.ffmpeg(toolbox.ffmpeg, ["-ss", f"{cover.at}", "-i", tiktok, "-frames:v", "1", work / "frame.png"], "vignette")
    shutil.copytree(theme / "fonts", work / "fonts")
    (work / "index.html").write_text(cover_page(theme, cover.lines), encoding="utf-8")
    width, height = COVER_SIZE
    script = DRIVER.format(
        playwright=json.dumps(str(toolbox.home("playwright") / "node_modules" / "playwright-core")),
        chromium=json.dumps(str(toolbox.file("chromium-headless-shell", "chrome-headless-shell"))),
        width=width,
        height=height,
        url=json.dumps((work / "index.html").as_uri()),
        out=json.dumps(str(out)),
    )
    (work / "driver.js").write_text(script, encoding="utf-8")
    done = subprocess.run(
        [str(toolbox.file("node", "bin/node")), str(work / "driver.js")], capture_output=True, check=False
    )
    if done.returncode != 0 or not out.is_file():
        raise PublishError("vignette : le rendu a échoué\n" + done.stderr.decode(errors="replace")[-2000:])
    return out


def problems(state: dict, media: Path) -> list[str]:
    qc = state.get("steps", {}).get("qc")
    found = []
    if qc is None:
        found.append("qc n'est pas passé : vf run")
    elif not qc.get("summary", {}).get("passed"):
        found.append("qc refuse le master : vf status")
    outputs = state.get("steps", {}).get("master", {}).get("outputs", {})
    for name in FILES:
        if name not in outputs:
            found.append(f"sortie {name} de master absente : vf run")
            continue
        why = store.problem(media, outputs[name])
        if why:
            found.append(f"sortie {name} de master : {why}")
    return found


def prepare(state: dict, script_text: str, media: Path) -> Publication:
    found = problems(state, media)
    if found:
        raise PublishError("\n".join(found))
    fields, _body = frontmatter.split(script_text)
    outputs = state["steps"]["master"]["outputs"]
    sources = {name: store.path(media, outputs[name]) for name in FILES}
    reminders = (AI_REMINDER.format(tool=fields["voix_ia"]),) if fields.get("voix_ia") else ()
    return Publication(caption(fields), sources, cover_of(script_text), reminders)


def link(source: Path, target: Path) -> None:
    """A hard link to the stored file (same file system), or a copy when the link is refused."""
    target.unlink(missing_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def write(publication: Publication, media: Path, video_id: str) -> Path:
    folder = media / FOLDER / video_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, source in publication.sources.items():
        link(source, folder / FILES[name])
    (folder / CAPTION_NAME).write_text(publication.caption, encoding="utf-8")
    return folder
