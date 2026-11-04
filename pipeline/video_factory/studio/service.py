"""`vf studio serve`: the page and the passes in one process, run by the user service that hermes/install.sh installs.

The studio is built from hermes/manifest.json (board, stations, port, brand positioning) and the environment:
`STUDIO_URL` is the page's address on the tailnet (written in the service by the install), `HERMES_BIN` the Hermès
command, and `VF_CONTENT`, `VF_MEDIA` the clone and the store, as for every `vf` command.
"""

from __future__ import annotations

import os
import signal
import threading
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

from video_factory import paths
from video_factory.studio import notify
from video_factory.studio.board import Board, BoardError, run_command
from video_factory.studio.lanes import Jobs, Studio
from video_factory.studio.page import server
from video_factory.studio.stations import load_manifest


def expand(value: str, home: Path) -> Path:
    return home / value[2:] if value.startswith("~/") else Path(value)


def build(env: Mapping[str, str], home: Path, *, background: bool = True, log: Callable[[str], None] = print) -> Studio:
    manifest = load_manifest()
    hermes = env.get("HERMES_BIN", "hermes")
    service = manifest["service"]
    url = env.get("STUDIO_URL") or f"http://{service['host']}:{service['port']}"
    target = notify.telegram_target(env, home)
    return Studio(
        board=Board(slug=manifest["board"]["slug"], hermes=hermes, run=run_command),
        places=paths.places(env, home),
        url=url,
        send=lambda text: notify.send(text, run_command, target, hermes),
        ask_writer=run_command,
        brand=expand(manifest["brand"], home),
        claim_ttl=int(manifest["claim_ttl_seconds"]),
        jobs=Jobs(background=background),
        log=log,
    )


def ticker(studio: Studio, every: float, stop: threading.Event) -> None:
    while not stop.wait(every):
        try:
            studio.tick()
        except (BoardError, OSError, ValueError) as exc:
            studio.log(f"passe : {exc}")


def stop_on_term(_signum: int, _frame: object) -> None:
    """systemd stops the service with SIGTERM: leave serve_forever as on Ctrl-C, so the stop is a clean exit."""
    raise KeyboardInterrupt


def serve(home: Path) -> int:
    manifest = load_manifest()
    service = manifest["service"]
    log = partial(print, flush=True)
    studio = build(os.environ, home, log=log)
    stop = threading.Event()
    threading.Thread(target=ticker, args=(studio, float(service["tick_seconds"]), stop), daemon=True).start()
    httpd = server(studio, service["host"], int(service["port"]))
    signal.signal(signal.SIGTERM, stop_on_term)
    log(f"studio : {studio.url} (local http://{service['host']}:{service['port']}), board {studio.board.slug}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        httpd.server_close()
    return 0
