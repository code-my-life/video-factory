#!/usr/bin/env bash
# Installe le board « studio » de video-factory dans le Hermès de la machine, à côté du board « factory » ; avec
# --uninstall, retire tout ce que ce script a installé. Idempotent : relancé, il ne refait que ce qui manque ou a changé.
#
# Ce qu'il installe, et rien d'autre (hermes/manifest.json) :
#   - le board « studio » (hermes kanban boards create) ;
#   - le profil studio-writer (hermes profile install), et son .env : les clés de manifest.json copiées de la racine ;
#   - le service utilisateur video-factory-studio.service : `vf studio serve`, la page sur 127.0.0.1 et les voies ;
#   - la publication de la page sur le tailnet, en HTTPS, par `tailscale serve` (jamais Funnel).
# Il ne touche ni à ~/.hermes/config.yaml, ni aux profils, plugins, crons et board de la factory.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
HH="${HERMES_HOME:-$HOME/.hermes}"
MANIFEST="$HERE/manifest.json"
log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

manifest() { python3 - "$MANIFEST" "$@" <<'PYX'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for key in sys.argv[2:]:
    value = value[key]
print("\n".join(map(str, value)) if isinstance(value, (list, dict)) else value)
PYX
}

HERMES="$(command -v "${HERMES_BIN:-hermes}" || true)"
[ -n "$HERMES" ] || die "hermes introuvable (HERMES_BIN)"
BOARD="$(manifest board slug)"
UNIT="$(manifest service unit)"
HOST="$(manifest service host)"
PORT="$(manifest service port)"
HTTPS_PORT="$(manifest service https_port)"
UNIT_FILE="$HOME/.config/systemd/user/$UNIT"

board_exists() { "$HERMES" kanban boards list --json 2>/dev/null | python3 -c '
import json, sys
boards = json.load(sys.stdin)
boards = boards.get("boards", boards) if isinstance(boards, dict) else boards
sys.exit(0 if any(b.get("slug") == sys.argv[1] for b in boards) else 1)' "$BOARD"; }
profile_exists() { [ -d "$HH/profiles/$1" ]; }
served() { tailscale serve status --json 2>/dev/null | python3 -c '
import json, sys
try:
    tcp = json.load(sys.stdin).get("TCP") or {}
except ValueError:
    tcp = {}
sys.exit(0 if sys.argv[1] in tcp else 1)' "$HTTPS_PORT"; }

uninstall() {
  if [ -f "$UNIT_FILE" ]; then
    systemctl --user disable --now "$UNIT" >/dev/null 2>&1 || true
    rm -f "$UNIT_FILE"
    systemctl --user daemon-reload
    log "service $UNIT retiré"
  fi
  if command -v tailscale >/dev/null 2>&1 && served; then
    tailscale serve --https="$HTTPS_PORT" off >/dev/null && log "tailscale serve :$HTTPS_PORT retiré"
  fi
  for profile in $(manifest profiles); do
    if profile_exists "$profile"; then "$HERMES" profile delete "$profile" -y >/dev/null && log "profil $profile retiré"; fi
  done
  if board_exists; then "$HERMES" kanban boards rm "$BOARD" --delete >/dev/null && log "board $BOARD supprimé"; fi
  log "studio retiré ; les vidéos (VF_CONTENT) et le magasin (VF_MEDIA, dont publication/) restent"
}

install() {
  command -v uv >/dev/null 2>&1 || die "uv introuvable"
  command -v tailscale >/dev/null 2>&1 || die "tailscale introuvable"
  local uv; uv="$(command -v uv)"

  # 1. Le board, à côté de « factory ».
  if board_exists; then log "board $BOARD présent"
  else
    "$HERMES" kanban boards create "$BOARD" --name "$(manifest board name)" \
      --description "$(manifest board description)" --icon "$(manifest board icon)" >/dev/null
    log "board $BOARD créé"
  fi

  # 2. Le profil studio-writer, et les clés de son .env copiées de la racine (jamais écrites ailleurs).
  for profile in $(manifest profiles); do
    # After an uninstall, Hermès keeps a tombstone of the deleted profile and refuses to install it again until it is
    # created anew: `profile create` lifts the tombstone, then the distribution is installed over it.
    if [ -e "$HH/profiles/.deleted/$profile" ] && ! profile_exists "$profile"; then
      "$HERMES" profile create "$profile" --no-alias --no-skills >/dev/null
    fi
    "$HERMES" profile install "$HERE/$(manifest profiles "$profile" path)" --name "$profile" -y --force >/dev/null
    local env_file="$HH/profiles/$profile/.env"
    touch "$env_file"; chmod 600 "$env_file"
    for key in $(manifest profiles "$profile" env_from_root); do
      if ! grep -q "^$key=" "$env_file"; then
        if grep -q "^$key=" "$HH/.env" 2>/dev/null; then grep "^$key=" "$HH/.env" >> "$env_file"
        else warn "$key absente de $HH/.env : $profile ne pourra pas joindre son modèle"; fi
      fi
    done
    log "profil $profile"
  done

  # 3. Le service : la page et les voies, depuis ce clone.
  local dns url
  dns="$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
  url="https://$dns:$HTTPS_PORT"
  mkdir -p "$(dirname "$UNIT_FILE")"
  local wanted; wanted="$(mktemp)"
  {
    echo "# Installé par $HERE/install.sh : à retirer par install.sh --uninstall, jamais à la main."
    echo "[Unit]"
    echo "Description=video-factory : board Hermès « studio », page des prises et voies"
    echo "After=network-online.target"
    echo
    echo "[Service]"
    echo "WorkingDirectory=$REPO"
    echo "ExecStart=$uv run --project $REPO --frozen vf studio serve"
    echo "Environment=PATH=$(dirname "$HERMES"):$(dirname "$uv"):/usr/local/bin:/usr/bin:/bin"
    echo "Environment=HERMES_BIN=$HERMES"
    echo "Environment=STUDIO_URL=$url"
    for var in VF_CONTENT VF_MEDIA VF_TOOLS; do
      [ -n "${!var:-}" ] && echo "Environment=$var=${!var}"
    done
    echo "Restart=on-failure"
    echo "RestartSec=10"
    echo
    echo "[Install]"
    echo "WantedBy=default.target"
  } > "$wanted"
  if cmp -s "$wanted" "$UNIT_FILE" 2>/dev/null; then
    rm -f "$wanted"; log "service $UNIT inchangé"
    systemctl --user enable --now "$UNIT" >/dev/null 2>&1
  else
    mv "$wanted" "$UNIT_FILE"
    systemctl --user daemon-reload
    systemctl --user enable "$UNIT" >/dev/null 2>&1
    systemctl --user restart "$UNIT"
    log "service $UNIT (re)lancé"
  fi

  # 4. La page sur le tailnet seulement, en HTTPS.
  if served; then log "tailscale serve :$HTTPS_PORT présent"
  else tailscale serve --bg --https="$HTTPS_PORT" "http://$HOST:$PORT" >/dev/null && log "tailscale serve :$HTTPS_PORT"; fi

  # 5. La page répond.
  for _ in $(seq 1 30); do
    if curl -fsS "http://$HOST:$PORT/sante" >/dev/null 2>&1; then log "studio prêt : $url"; return 0; fi
    sleep 1
  done
  die "la page ne répond pas sur http://$HOST:$PORT/sante : journalctl --user -u $UNIT"
}

case "${1:-}" in
  "") install ;;
  --uninstall) uninstall ;;
  *) die "usage : hermes/install.sh [--uninstall]" ;;
esac
