"""Telegram messages to the owner, through the Hermès gateway's own sender (`hermes send`), and their texts.

A message goes out when a card parks at a station that waits for the owner, or when a lane fails. It names the video,
what to do, the page of the video on the tailnet and the Telegram command that answers.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from video_factory.studio.stations import BY_KEY

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]
ASK = {
    "approbation": "Le brouillon du script est prêt : le relire, puis l'approuver.",
    "tournage": "Script approuvé : tourner, puis envoyer les prises depuis la page.",
    "revue": "Le master passe qc : le regarder, puis le valider.",
    "publication": (
        "Prête à publier : le fichier TikTok et la légende sont sur la page. Publier à la main, puis confirmer."
    ),
}
REDO = {"approbation": "refaire le brouillon", "revue": "refaire le montage"}


def message(station: str, video_id: str, card_id: str, url: str, note: str = "", failed: bool = False) -> str:
    label = BY_KEY[station].label
    lines = [f"🎬 Studio · {video_id} · {label}"]
    if failed:
        lines.append(f"{label} en échec : {note}" if note else f"{label} en échec.")
        lines.append("Corriger, puis débloquer pour réessayer.")
    else:
        lines.append(ASK.get(station, label))
        if note:
            lines.append(note)
    lines.append(f"Page : {url.rstrip('/')}/v/{video_id}")
    if station != "tournage" or failed:
        lines.append(f"/kanban --board studio unblock {card_id}")
    if station in REDO and not failed:
        lines.append(f'/kanban --board studio unblock {card_id} --reason "refaire : ce qui change"  ({REDO[station]})')
    return "\n".join(lines)


def env_value(name: str, env: Mapping[str, str], dotenv: Path) -> str:
    """A variable from the environment, else from the root .env of Hermès (read, never written)."""
    if env.get(name):
        return env[name]
    try:
        lines = dotenv.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        key, sep, value = line.partition("=")
        if sep and key.strip() == name:
            return value.strip().strip("\"'")
    return ""


def telegram_target(env: Mapping[str, str], home: Path) -> str:
    root = Path(env.get("HERMES_ROOT_HOME") or home / ".hermes")
    chat = env_value("TELEGRAM_CHAT_ID", env, root / ".env")
    return f"telegram:{chat}" if chat else "telegram"


def send(text: str, run: Runner, target: str, hermes: str = "hermes") -> bool:
    done = run([hermes, "send", "-t", target, text])
    return done.returncode == 0
