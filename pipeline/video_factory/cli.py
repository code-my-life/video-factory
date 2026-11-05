"""The `vf` command: `vf doctor`, `vf new`, `vf ingest`, `vf voix`, `vf status`, `vf run`, `vf publish`, `vf studio`
and `vf capture`. Its messages are in French, like its docs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from video_factory import (
    __version__,
    chain,
    compose,
    doctor,
    install,
    lock,
    media,
    paths,
    publish,
    state,
    videos,
    vitrine,
)
from video_factory.capture import demo as capture_demo
from video_factory.capture import plan as capture_plan
from video_factory.capture import scene as capture_scene
from video_factory.capture import shoot as capture_shoot
from video_factory.context import StepError, Video
from video_factory.studio import board as studio_board
from video_factory.studio import service
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
    new.add_argument("--vitrine", action="store_true", help="une vitrine : la voix sur des plans d'app et des rushs")
    take = commands.add_parser(
        "ingest",
        help="verser les prises d'une vidéo (puis faire sa copie de travail) ou ses captures d'écran",
        description="Range chaque prise dans le magasin des médias, par son empreinte, et fait la copie de travail ; "
        "ou range une capture (image PNG ou court extrait MP4) sous le nom que le script lui donne.",
    )
    take.add_argument("id", help="identifiant de la vidéo")
    take.add_argument("files", nargs="*", type=Path, metavar="fichier", help="les prises, dans l'ordre")
    take.add_argument("--voix", type=Path, metavar="fichier", help="la voix d'une vitrine (fichier audio)")
    take.add_argument(
        "--capture",
        nargs=2,
        action="append",
        default=[],
        metavar=("nom", "fichier"),
        help="une capture appelée par [capture: <nom>] dans le script",
    )
    voice = commands.add_parser(
        "voix",
        help="le texte de la voix d'une vitrine, à coller dans ElevenLabs",
        description="Écrit videos/<id>/voix-elevenlabs.txt depuis le script : les répliques dans l'ordre, avec leurs "
        "indications de jeu ([ton: …]) et une pause entre elles. « v3 » pour Eleven v3 (étiquettes), « v2 » pour "
        "Eleven Multilingual v2 (pauses de 0,8 s, sans étiquette).",
    )
    voice.add_argument("id", help="identifiant de la vidéo")
    voice.add_argument("--modele", choices=vitrine.MODELS, default="v3", help="le modèle d'ElevenLabs (défaut : v3)")
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
    out = commands.add_parser(
        "publish",
        help="préparer la publication à la main : le fichier TikTok, le master et la légende",
        description="Vérifie que le master passe qc, puis range dans VF_MEDIA/publication/<id>/ l'export TikTok, "
        "le master et la légende (le crédit du robot compris). Ne publie rien.",
    )
    out.add_argument("id", help="identifiant de la vidéo")
    board = commands.add_parser("studio", help="le board Hermès « studio » : la page des prises et les voies")
    actions = board.add_subparsers(dest="action", required=True, metavar="action")
    actions.add_parser("serve", help="servir la page (127.0.0.1) et faire avancer les cartes, sans fin")
    actions.add_parser("tick", help="une seule passe sur les cartes du board, au premier plan")
    card = actions.add_parser("carte", help="ouvrir la carte d'une vidéo (nouvelle idée, ou vidéo qui existe)")
    card.add_argument("id", help="identifiant de la vidéo")
    card.add_argument("idee", nargs="?", default="", help="l'idée en une phrase")
    shot = commands.add_parser(
        "capture",
        help="tourner un plan d'app : la démo pilotée à horloge simulée, image par image, et sa caméra qui suit",
        description="Construit la démo de l'app du plan (vitrine/<app>/, au commit figé, avec sa variante de "
        "scénario), la pilote avec Playwright à horloge simulée selon le plan, écrit les images, la position des "
        "éléments suivis et leurs empreintes ; si le plan a une caméra, écrit la scène HyperFrames « caméra qui "
        "suit », la vérifie, la rend sans réseau et la mesure.",
    )
    shot.add_argument("plan", type=Path, help="le plan de capture (JSON, schemas/capture-plan.schema.json)")
    shot.add_argument("--sortie", type=Path, help="le dossier du plan tourné (défaut : VF_MEDIA/vitrine/<nom du plan>)")
    shot.add_argument("--travail", type=Path, help="où construire la démo (défaut : VF_MEDIA/vitrine/travail)")
    shot.add_argument("--sans-rendu", action="store_true", help="écrire et vérifier la scène sans la rendre")
    shot.add_argument(
        "--scene-seule", action="store_true", help="garder la capture faite (track.json), ne refaire que la scène"
    )
    return top


def run_publish(video_id: str, home: Path) -> int:
    places = paths.places(os.environ, home)
    folder = places.content / "videos" / video_id
    try:
        loaded = state.load(folder / videos.STATE_NAME)
        script = (folder / videos.SCRIPT_NAME).read_text(encoding="utf-8")
        ready = publish.prepare(loaded, script, places.media)
    except (state.StateError, OSError) as exc:
        print(f"vf publish : {exc}", file=sys.stderr)
        return 1
    except publish.PublishError as exc:
        print("vf publish : pas encore publiable", file=sys.stderr)
        for line in str(exc).splitlines():
            print(f"  {line}", file=sys.stderr)
        return 1
    out = publish.write(ready, places.media, video_id)
    print(f"vf publish : prêt à publier à la main, dans {out}")
    for name in publish.FILES.values():
        print(f"  {name}")
    print(f"  {publish.CAPTION_NAME} :")
    for line in ready.caption.splitlines():
        print(f"    {line}")
    return 0


def run_studio(args: argparse.Namespace, home: Path) -> int:
    if args.action == "serve":
        return service.serve(home)
    studio = service.build(os.environ, home, background=False)
    try:
        if args.action == "tick":
            studio.tick()
            return 0
        card = studio.open_card(args.id, args.idee)
    except studio_board.BoardError as exc:
        print(f"vf studio : {exc}", file=sys.stderr)
        return 1
    print(f"carte {card} : {args.id}")
    return 0


def run_capture(args: argparse.Namespace, home: Path) -> int:
    places = paths.places(os.environ, home)
    try:
        pinned = lock.load(paths.LOCK_FILE)
        doc = capture_plan.load(args.plan)
        source = capture_plan.load_source(doc["app"])
    except (lock.LockError, capture_plan.PlanError) as exc:
        print(f"vf capture : {exc}", file=sys.stderr)
        return 1
    toolbox = Toolbox(pinned, places.tools)
    out = args.sortie or places.media / "vitrine" / doc["name"]
    work = args.travail or places.media / "vitrine" / "travail"
    try:
        built = capture_demo.build(source, toolbox, work)
        print(f"démo : {built}")
        if args.scene_seule and (out / "track.json").is_file():
            print("capture : gardée, seule la scène est refaite")
        else:
            found = capture_shoot.shoot(doc, source, toolbox, built, out)
            print(f"capture : {len(found['frames'])} images, empreinte {found['all']}")
        if "camera" in doc or "phone" in doc:
            track = json.loads((out / "track.json").read_text(encoding="utf-8"))
            if "camera" in doc:
                measures = capture_scene.make(out, track, doc["camera"], toolbox, render=not args.sans_rendu)
            else:
                measures = capture_scene.make_phone(out, track, doc["phone"], toolbox, built, not args.sans_rendu)
            print(json.dumps(measures, indent=2, ensure_ascii=False))
    except (
        capture_demo.DemoError,
        capture_shoot.ShootError,
        capture_scene.SceneError,
        compose.ComposeError,
        ToolError,
        media.MediaError,
        ValueError,
    ) as exc:
        print(f"vf capture : {exc}", file=sys.stderr)
        return 1
    print(f"vf capture : {out}")
    return 0


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


def run_new(video_id: str, home: Path, showcase: bool = False) -> int:
    places = paths.places(os.environ, home)
    template = (paths.SCRIPT_VITRINE_TEMPLATE if showcase else paths.SCRIPT_TEMPLATE).read_text(encoding="utf-8")
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
    if not args.files and not args.capture and args.voix is None:
        print("vf ingest : aucune prise, voix ni capture à verser", file=sys.stderr)
        return 1
    video = open_video(args.id, home)
    for name, file in args.capture:
        stored = chain.register_capture(video, name.strip(), Path(file))
        print(f"capture « {name.strip()} » : {stored['kind']}, {stored['file']}")
    if args.voix is not None:
        stored = chain.register_voice(video, args.voix)
        print(f"voix : {stored['file']}")
        chain.run_step(video, chain.BY_NAME["ingest"], say)
    if args.files:
        chain.register_takes(video, args.files)
        for take in video.state["takes"]:
            print(f"prise : {take['file']}")
        chain.run_step(video, chain.BY_NAME["ingest"], say)
    return 0


def run_voice(video_id: str, model: str, home: Path) -> int:
    places = paths.places(os.environ, home)
    script_path = places.content / "videos" / video_id / videos.SCRIPT_NAME
    try:
        text = vitrine.elevenlabs_text(vitrine.parse(script_path.read_text(encoding="utf-8")), model)
    except (OSError, ValueError) as exc:
        print(f"vf voix : {exc}", file=sys.stderr)
        return 1
    target = script_path.with_name("voix-elevenlabs.txt")
    target.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"\nécrit dans {target}")
    return 0


def media_lines(video: Video) -> list[str]:
    """The files of a video in the store: its voice, its takes and its captures, by name."""
    found = []
    if "voix" in video.state:
        found.append(f"  voix           {video.state['voix']['file']}")
    for number, take in enumerate(video.state["takes"], 1):
        found.append(f"  prise {number:<8d} {take['file']}")
    for name, capture in sorted(video.state["captures"].items()):
        kind = "image" if capture["kind"] == "image" else "extrait"
        found.append(f"  {kind} {name:<20s} {capture['file']}")
    return found


def run_status(video_id: str, home: Path) -> int:
    video = open_video(video_id, home)
    files = media_lines(video)
    if files:
        print("fichiers rangés :")
        print("\n".join(files))
        print("étapes :")
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
        return run_new(args.id, home, args.vitrine)
    if args.command == "voix":
        return run_voice(args.id, args.modele, home)
    if args.command == "publish":
        return run_publish(args.id, home)
    if args.command == "studio":
        return run_studio(args, home)
    if args.command == "capture":
        return run_capture(args, home)
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
