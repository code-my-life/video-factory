"""The `vf` command: `vf doctor [--install [TOOL ...]]` and `vf new <id>`. Its messages are in French, like its docs."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from video_factory import __version__, doctor, install, lock, paths, videos


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="vf", description="Monteur vidéo de Code My Life.")
    top.add_argument("--version", action="version", version=f"vf {__version__}")
    commands = top.add_subparsers(dest="command", required=True, metavar="commande")
    check = commands.add_parser(
        "doctor",
        help="vérifier les outils figés (toolchain/tools.lock.json) et les dossiers de travail",
        description="Vérifie chaque outil du lock : présent, à sa version et à son empreinte SHA-256.",
    )
    check.add_argument(
        "--install",
        nargs="*",
        metavar="outil",
        help="installer les outils nommés (tous, sans nom) après vérification de leurs empreintes",
    )
    new = commands.add_parser(
        "new",
        help="créer une vidéo dans le dépôt de contenu (script.md et state.json)",
        description="Crée videos/<id>/script.md et videos/<id>/state.json dans le dépôt de contenu (VF_CONTENT).",
    )
    new.add_argument("id", help="identifiant : minuscules, chiffres et tirets")
    return top


def run_doctor(names: list[str] | None, home: Path) -> int:
    try:
        pinned = lock.load(paths.LOCK_FILE)
    except lock.LockError as exc:
        print(f"vf doctor : {exc}", file=sys.stderr)
        return 1
    places = paths.places(os.environ, home)
    check = partial(
        doctor.check_tool,
        lock=pinned,
        places=places,
        run=doctor.run_command,
        base_env=os.environ,
        repo_root=paths.REPO_ROOT,
        user_home=home,
    )
    if names is not None:
        status = install.main_install(pinned, names, places, paths.REPO_ROOT, check)
        if status:
            return status
    results = doctor.diagnose(pinned, places, doctor.run_command, os.environ, paths.REPO_ROOT, home)
    text, status = doctor.report(results, paths.LOCK_FILE, places.tools)
    print(text)
    return status


def run_new(video_id: str, home: Path) -> int:
    places = paths.places(os.environ, home)
    template = paths.SCRIPT_TEMPLATE.read_text(encoding="utf-8")
    try:
        folder = videos.create(places.content, video_id, template, videos.utc_now())
    except videos.VideoError as exc:
        print(f"vf new : {exc}", file=sys.stderr)
        return 1
    relative = folder.relative_to(places.content)
    print(f"créé dans {places.content} :")
    print(f"  {relative / videos.SCRIPT_NAME}")
    print(f"  {relative / videos.STATE_NAME}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    home = Path.home()
    if args.command == "doctor":
        return run_doctor(args.install, home)
    return run_new(args.id, home)


if __name__ == "__main__":
    sys.exit(main())
