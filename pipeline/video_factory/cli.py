"""The `vf` command: `vf doctor`, `vf new`, `vf ingest`, `vf status` and `vf run`. Its messages are in French, like
its docs."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from video_factory import __version__, chain, doctor, install, lock, media, paths, videos
from video_factory.context import StepError, Video
from video_factory.tools import Toolbox, ToolError


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
    take = commands.add_parser(
        "ingest",
        help="verser les prises d'une vidéo (puis faire sa copie de travail) ou ses captures d'écran",
        description="Range chaque prise dans le magasin des médias, par son empreinte, et fait la copie de travail ; "
        "ou range une capture (image PNG ou court extrait MP4) sous le nom que le script lui donne.",
    )
    take.add_argument("id", help="identifiant de la vidéo")
    take.add_argument("files", nargs="*", type=Path, metavar="fichier", help="les prises, dans l'ordre")
    take.add_argument(
        "--capture",
        nargs=2,
        action="append",
        default=[],
        metavar=("nom", "fichier"),
        help="une capture appelée par [capture: <nom>] dans le script",
    )
    show = commands.add_parser("status", help="dire, étape par étape, ce qui est à jour et ce qui est à refaire")
    show.add_argument("id", help="identifiant de la vidéo")
    chain_run = commands.add_parser(
        "run", help="refaire les étapes jamais passées ou périmées, puis celles dont les entrées ont changé"
    )
    chain_run.add_argument("id", help="identifiant de la vidéo")
    chain_run.add_argument(
        "--refaire",
        nargs="+",
        default=[],
        choices=[step.name for step in chain.STEPS],
        metavar="étape",
        help="refaire ces étapes même à jour (par exemple compose master, pour comparer deux rendus)",
    )
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
    only = lock.requirement_order(pinned, names) if names else None
    results = doctor.diagnose(pinned, places, doctor.run_command, os.environ, paths.REPO_ROOT, home, only)
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


def open_video(video_id: str, home: Path) -> Video:
    places = paths.places(os.environ, home)
    try:
        pinned = lock.load(paths.LOCK_FILE)
    except lock.LockError as exc:
        raise StepError(str(exc)) from exc
    return Video.open(places, video_id, Toolbox(pinned, places.tools))


def run_ingest(args: argparse.Namespace, home: Path) -> int:
    if not args.files and not args.capture:
        print("vf ingest : aucune prise ni capture à verser", file=sys.stderr)
        return 1
    video = open_video(args.id, home)
    for name, file in args.capture:
        stored = chain.register_capture(video, name.strip(), Path(file))
        print(f"capture « {name.strip()} » : {stored['kind']}, {stored['file']}")
    if args.files:
        chain.register_takes(video, args.files)
        for take in video.state["takes"]:
            print(f"prise : {take['file']}")
        chain.run_step(video, chain.BY_NAME["ingest"], say)
    return 0


def run_status(video_id: str, home: Path) -> int:
    video = open_video(video_id, home)
    for found in chain.status(video):
        print(f"  {found.label:14s} {found.step}")
        for reason in found.reasons:
            print(f"                 {reason}")
    qc = video.state["steps"].get("qc")
    if qc is not None and not qc["summary"].get("passed", False):
        print("\nqc : master refusé")
        for message in qc["summary"].get("failed", []):
            print(f"  {message}")
    return 0


def say(line: str) -> None:
    print(line, flush=True)


def run_chain(video_id: str, again: list[str], home: Path) -> int:
    video = open_video(video_id, home)
    chain.run(video, again, say)
    qc = video.state["steps"]["qc"]["summary"]
    if not qc["passed"]:
        print("vf run : qc refuse le master", file=sys.stderr)
        for message in qc["failed"]:
            print(f"  {message}", file=sys.stderr)
        return 1
    print("vf run : le master passe qc")
    print(f"  master (YouTube, Instagram) : {video.output('master', 'master')}")
    print(f"  export TikTok               : {video.output('master', 'tiktok')}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    home = Path.home()
    if args.command == "doctor":
        return run_doctor(args.install, home)
    if args.command == "new":
        return run_new(args.id, home)
    try:
        if args.command == "ingest":
            return run_ingest(args, home)
        if args.command == "status":
            return run_status(args.id, home)
        return run_chain(args.id, args.refaire, home)
    except (StepError, ToolError, media.MediaError) as exc:
        print(f"vf {args.command} : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
