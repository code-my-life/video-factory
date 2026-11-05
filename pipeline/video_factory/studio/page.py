"""The studio page, served on 127.0.0.1 and published on the tailnet only by `tailscale serve` (HTTPS, never Funnel).

It lists the cards, shows what each station needs (the draft to approve, the master to review, the files and the
caption to post), receives the takes from Safari, and sends the owner's gestures to the board as unblocks: the same
gesture as the Telegram command. A take is streamed to the store's scratch folder while its SHA-256 is computed, and
refused unless it matches the fingerprint the phone computed before sending.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

from video_factory import __version__, frontmatter, publish, videos
from video_factory.paths import REPO_ROOT
from video_factory.studio import api
from video_factory.studio.board import BoardError
from video_factory.studio.lanes import Studio, tail
from video_factory.studio.stations import BY_KEY, READY_TO_POST, Card, last_park

STATIC = REPO_ROOT / "templates" / "studio"
STATIC_FILES = {"page.css": "text/css", "sha256.js": "text/javascript", "upload.js": "text/javascript"}
VIDEO_ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"
DIGEST = re.compile(r"^[0-9a-f]{64}$")
EXTENSION = re.compile(r"^[a-z0-9]{1,8}$")
CHUNK = 1024 * 1024
UPLOADS = "studio-upload"


def staging(studio: Studio, video_id: str) -> Path:
    return studio.places.media / ".work" / UPLOADS / video_id


def receive(stream, length: int, target: Path) -> str:
    """Write length bytes of stream to target and return their SHA-256."""
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    left = length
    with target.open("wb") as out:
        while left > 0:
            chunk = stream.read(min(CHUNK, left))
            if not chunk:
                raise OSError(f"envoi interrompu, {left} octets manquants")
            digest.update(chunk)
            out.write(chunk)
            left -= len(chunk)
    return digest.hexdigest()


def extension_of(name: str) -> str:
    found = Path(urllib.parse.unquote(name)).suffix.lower().lstrip(".")
    return found if EXTENSION.match(found) else "mov"


def stem_of(name: str) -> str:
    """The name of a received file without its extension, in lower case letters, digits and hyphens: a showcase stores
    a rush under it, as the capture its script names."""
    found = re.sub(r"[^a-z0-9]+", "-", Path(urllib.parse.unquote(name)).stem.lower()).strip("-")
    return found[:60].strip("-") or "fichier"


def layout(title: str, body: str) -> bytes:
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1, viewport-fit=cover'>"
        f"<title>{html.escape(title)}</title><link rel='stylesheet' href='/static/page.css'></head>"
        f"<body><main>{body}</main></body></html>"
    ).encode()


def chip(card: Card) -> str:
    station = card.station
    label = station.label if station else (card.assignee or "?")
    parked = last_park(card) or ""
    css = "echec" if " en échec" in parked else ("attend" if card.status == "scheduled" else "")
    return f"<span class='station {css}'>{html.escape(label)}</span>"


def answer_form(video_id: str, ok: str, redo: str | None) -> str:
    parts = [
        f"<form method='post' action='/v/{video_id}/reponse'>",
        "<input type='hidden' name='decision' value='ok'>",
        f"<button>{html.escape(ok)}</button></form>",
    ]
    if redo:
        parts += [
            f"<form method='post' action='/v/{video_id}/reponse'>",
            "<input type='hidden' name='decision' value='refaire'>",
            "<textarea name='note' rows='3' placeholder='Ce qui change'></textarea>",
            f"<button class='second'>{html.escape(redo)}</button></form>",
        ]
    return "".join(parts)


class Pages:
    """The HTML of each view, from the board and the content clone."""

    def __init__(self, studio: Studio) -> None:
        self.studio = studio

    def index(self) -> bytes:
        items = []
        for task in self.studio.board.listing():
            card = Card(task["id"], task.get("title") or "", task.get("status") or "", task.get("assignee"))
            if card.video is None:
                continue
            items.append(f"<li><a href='/v/{card.video}'>{html.escape(card.title)}</a>{chip(card)}</li>")
        cards = "".join(items) or "<li class='doux'>Aucune vidéo sur le board.</li>"
        return layout(
            "Studio",
            "<h1>Studio</h1><p class='doux'>Les vidéos du board « studio ».</p>"
            f"<ul class='cartes'>{cards}</ul>"
            "<h2>Nouvelle vidéo</h2><section><form method='post' action='/nouvelle'>"
            "<input type='text' name='id' placeholder='id : minuscules-et-tirets' required pattern='[a-z0-9-]+' "
            "autocapitalize='none'><p></p><input type='text' name='idee' placeholder='L&#39;idée en une phrase'>"
            "<button>Créer la carte</button></form></section>",
        )

    def script_title(self, video_id: str) -> str:
        try:
            text = (self.studio.folder(video_id) / videos.SCRIPT_NAME).read_text(encoding="utf-8")
            return str(frontmatter.split(text)[0].get("titre") or video_id)
        except (OSError, frontmatter.FrontMatterError):
            return video_id

    def video(self, video_id: str) -> bytes:
        card = self.studio.card_of_video(video_id)
        head = f"<h1>{html.escape(self.script_title(video_id))}</h1><p class='doux'>{video_id}</p>"
        if card is None:
            return layout(video_id, head + "<section>Aucune carte ouverte pour cette vidéo.</section>")
        head += f"<p>{chip(card)} <span class='doux'>{card.id} · {html.escape(card.status)}</span></p>"
        return layout(video_id, head + self.station_view(card, video_id))

    def station_view(self, card: Card, video_id: str) -> str:
        station = card.station.key if card.station else ""
        parked = last_park(card) or ""
        if card.status == "scheduled" and " en échec" in parked:
            return f"<section><p>{html.escape(parked)}</p>{answer_form(video_id, 'Réessayer', None)}</section>"
        if card.status != "scheduled":
            busy = {"montage": "Montage en cours : vf run.", "script": "studio-writer écrit le brouillon."}
            return f"<section class='doux'>{busy.get(station, 'Une voie travaille sur cette carte.')}</section>"
        if station == "approbation":
            script = html.escape(self.read_script(video_id))
            return (
                f"<section><h2>Brouillon</h2><pre>{script}</pre>"
                + answer_form(video_id, "Approuver", "Refaire le brouillon")
                + "</section>"
            )
        if station == "tournage":
            showcase = self.studio.is_showcase(video_id)
            title = "La voix et les rushs" if showcase else "Les prises"
            accept = "audio/*,video/*" if showcase else "video/*"
            hint = (
                "<p class='doux'>Le fichier audio est la voix ; chaque rush garde le nom que le script lui donne "
                "(« plan1.mp4 » pour [plan: plan1]).</p>"
                if showcase
                else ""
            )
            return (
                f"<section><h2>{title}</h2>{hint}<form id='prises' data-video='{video_id}'>"
                f"<input type='file' accept='{accept}' multiple required><br>"
                "<button>Envoyer</button></form><ol id='suivi'></ol></section>"
                "<script src='/static/sha256.js'></script><script src='/static/upload.js'></script>"
            )
        if station == "revue":
            return (
                f"<section><h2>Le master</h2><video src='/v/{video_id}/media/master' controls playsinline "
                "preload='metadata'></video>" + answer_form(video_id, "Valider", "Refaire le montage") + "</section>"
            )
        if station == "publication" and parked.startswith(READY_TO_POST):
            return self.publication_view(video_id)
        return f"<section>{html.escape(parked or 'En attente.')}</section>"

    def read_script(self, video_id: str) -> str:
        try:
            return (self.studio.folder(video_id) / videos.SCRIPT_NAME).read_text(encoding="utf-8")
        except OSError:
            return "(script.md introuvable)"

    def publication_view(self, video_id: str) -> str:
        caption = self.read_publication(video_id) or ""
        return (
            "<section><h2>À publier sur TikTok</h2>"
            f"<p><a href='/v/{video_id}/media/tiktok' download='{video_id}-tiktok.mp4'>Fichier TikTok (1080x1920)</a>"
            f" · <a href='/v/{video_id}/media/master' download='{video_id}-master.mp4'>Master (1440x2560)</a></p>"
            f"<textarea id='legende' rows='6' readonly>{html.escape(caption)}</textarea>"
            "<button class='second' onclick=\"navigator.clipboard.writeText("
            "document.getElementById('legende').value)\">Copier la légende</button>"
            f"<form method='post' action='/v/{video_id}/reponse'><input type='hidden' name='decision' value='ok'>"
            "<p></p><input type='url' name='note' placeholder='Lien de la vidéo publiée (facultatif)'>"
            "<button>Publiée</button></form></section>"
        )

    def read_publication(self, video_id: str) -> str | None:
        try:
            return (self.studio.places.media / publish.FOLDER / video_id / publish.CAPTION_NAME).read_text("utf-8")
        except OSError:
            return None

    def media_file(self, video_id: str, name: str) -> Path | None:
        if name not in publish.FILES:
            return None
        try:
            state = json.loads((self.studio.folder(video_id) / videos.STATE_NAME).read_text(encoding="utf-8"))
            ref = state["steps"]["master"]["outputs"][name]
        except (OSError, ValueError, KeyError):
            return None
        found = self.studio.places.media / ref["file"]
        return found if found.is_file() else None


def handler_for(studio: Studio) -> type[BaseHTTPRequestHandler]:
    pages = Pages(studio)

    class Handler(BaseHTTPRequestHandler):
        server_version = f"video-factory-studio/{__version__}"

        @override
        def log_message(self, fmt: str, *args: object) -> None:
            studio.log("page : " + fmt % args)

        def reply(self, status: int, body: bytes, kind: str = "text/html; charset=utf-8") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def reply_json(self, status: int, data: dict) -> None:
            self.reply(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def redirect(self, where: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", where)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def form(self) -> dict[str, str]:
            size = int(self.headers.get("Content-Length") or 0)
            fields = urllib.parse.parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
            return {key: values[-1] for key, values in fields.items()}

        @override
        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path.startswith("/api/"):
                self.api_get(path)
                return
            try:
                if path == "/":
                    self.reply(200, pages.index())
                elif path == "/sante":
                    self.reply_json(200, {"ok": True, "board": studio.board.slug, "version": __version__})
                elif (found := re.fullmatch(r"/static/([a-z0-9.]+)", path)) and found[1] in STATIC_FILES:
                    self.reply(200, (STATIC / found[1]).read_bytes(), STATIC_FILES[found[1]] + "; charset=utf-8")
                elif found := re.fullmatch(rf"/v/({VIDEO_ID})", path):
                    self.reply(200, pages.video(found[1]))
                elif found := re.fullmatch(rf"/v/({VIDEO_ID})/media/([a-z]+)", path):
                    self.stream(pages.media_file(found[1], found[2]))
                else:
                    self.reply(404, layout("Introuvable", "<h1>Introuvable</h1>"))
            except BoardError as exc:
                self.reply(502, layout("Board", f"<h1>Board injoignable</h1><pre>{html.escape(str(exc))}</pre>"))

        def api_get(self, path: str) -> None:
            """The generic workflow API (#21): JSON only, versioned, an error being a JSON message too."""
            try:
                if path == "/api/workflow":
                    self.reply_json(200, {"api": api.API_VERSION, "sheet": api.load_sheet()})
                elif path == "/api/items":
                    self.reply_json(200, {"api": api.API_VERSION, "items": api.items(studio)})
                elif found := re.fullmatch(rf"/api/items/({VIDEO_ID})", path):
                    self.reply_json(200, {"api": api.API_VERSION} | api.detail(studio, found[1]))
                elif found := re.fullmatch(rf"/api/items/({VIDEO_ID})/words", path):
                    self.reply_json(200, {"api": api.API_VERSION, "words": api.words(studio, found[1])})
                else:
                    self.reply_json(404, {"message": "route inconnue"})
            except api.ApiError as exc:
                self.reply_json(404, {"message": str(exc)})
            except BoardError as exc:
                self.reply_json(502, {"message": f"board injoignable : {exc}"})

        def api_gesture(self, video_id: str) -> None:
            size = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(size) or b"{}")
                decision, note = str(body.get("decision", "")), str(body.get("note") or "")
            except (ValueError, AttributeError):
                self.reply_json(400, {"message": "corps JSON attendu : decision et note"})
                return
            try:
                card = api.gesture(studio, video_id, decision, note)
            except api.ApiError as exc:
                self.reply_json(400, {"message": str(exc)})
                return
            except BoardError as exc:
                self.reply_json(409, {"message": str(exc)})
                return
            self.reply_json(200, {"api": api.API_VERSION, "card": card.id, "decision": decision})

        def stream(self, file: Path | None) -> None:
            """A stored file, with byte ranges: Safari plays a video only from ranges."""
            if file is None:
                self.reply(404, b"introuvable", "text/plain; charset=utf-8")
                return
            size = file.stat().st_size
            start, end = 0, size - 1
            found = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
            if found and (found[1] or found[2]):
                start = int(found[1]) if found[1] else max(0, size - int(found[2]))
                end = min(int(found[2]), size - 1) if found[1] and found[2] else size - 1
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with file.open("rb") as source:
                source.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = source.read(min(CHUNK, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        @override
        def do_PUT(self) -> None:
            found = re.fullmatch(rf"/v/({VIDEO_ID})/prises/(\d{{1,3}})", urllib.parse.urlsplit(self.path).path)
            phone = (self.headers.get("X-Empreinte") or "").lower()
            if found is None or not DIGEST.match(phone):
                self.reply_json(400, {"message": "envoi refusé : adresse ou empreinte du téléphone invalide"})
                return
            name = self.headers.get("X-Nom") or ""
            target = staging(studio, found[1]) / f"{int(found[2]):03d}-{stem_of(name)}.{extension_of(name)}"
            for old in target.parent.glob(f"{int(found[2]):03d}-*.*"):
                old.unlink()
            try:
                received = receive(self.rfile, int(self.headers.get("Content-Length") or 0), target)
            except (OSError, ValueError) as exc:
                target.unlink(missing_ok=True)
                self.reply_json(400, {"message": f"envoi refusé : {exc}"})
                return
            if received != phone:
                target.unlink(missing_ok=True)
                self.reply_json(422, {"message": f"empreinte reçue {received} ≠ téléphone {phone}", "sha256": received})
                return
            self.reply_json(200, {"sha256": received, "octets": target.stat().st_size})

        @override
        def do_POST(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if found := re.fullmatch(rf"/api/items/({VIDEO_ID})/gesture", path):
                self.api_gesture(found[1])
                return
            try:
                if path == "/nouvelle":
                    fields = self.form()
                    studio.open_card(fields.get("id", "").strip(), fields.get("idee", ""))
                    self.redirect(f"/v/{fields.get('id', '').strip()}")
                elif found := re.fullmatch(rf"/v/({VIDEO_ID})/reponse", path):
                    fields = self.form()
                    decision = "refaire" if fields.get("decision") == "refaire" else "ok"
                    note = fields.get("note", "").strip()
                    studio.answer(found[1], f"{decision} : {note}" if note else decision)
                    self.redirect(f"/v/{found[1]}")
                elif found := re.fullmatch(rf"/v/({VIDEO_ID})/prises", path):
                    self.finish_takes(found[1])
                else:
                    self.reply(404, layout("Introuvable", "<h1>Introuvable</h1>"))
            except BoardError as exc:
                self.reply(409, layout("Refusé", f"<h1>Refusé</h1><pre>{html.escape(str(exc))}</pre>"))

        def finish_takes(self, video_id: str) -> None:
            size = int(self.headers.get("Content-Length") or 0)
            try:
                count = int(json.loads(self.rfile.read(size) or b"{}").get("count", 0))
            except (ValueError, AttributeError):
                count = 0
            folder = staging(studio, video_id)
            files = sorted(folder.glob("*.*")) if folder.is_dir() else []
            if count < 1 or len(files) != count:
                self.reply_json(400, {"message": f"{len(files)} prise(s) reçue(s) pour {count} annoncée(s)"})
                return
            try:
                done = studio.takes_received(video_id, files)
            except BoardError as exc:
                self.reply_json(422, {"message": str(exc)})
                return
            if done.returncode != 0:
                self.reply_json(422, {"message": f"vf ingest refuse les prises : {tail(done)}"})
                return
            shutil.rmtree(folder, ignore_errors=True)
            if studio.facts(video_id).takes:
                message = f"{count} fichier(s) versé(s) : la carte passe en {BY_KEY['montage'].label}."
            else:
                message = f"{count} fichier(s) versé(s) ; il en manque encore au script : la carte reste au tournage."
            self.reply_json(200, {"message": message})

    return Handler


def server(studio: Studio, host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), handler_for(studio))
