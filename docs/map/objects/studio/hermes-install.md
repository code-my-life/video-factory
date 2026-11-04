---
type: object
cluster: studio
universe: live
paths:
  - hermes/
hits:
  - docs/RUNBOOK.md
---

# hermes install

`hermes/manifest.json` (board, stations and lanes, the `studio-writer` profile, the service's port, the brand positioning), `hermes/profiles/studio-writer/` (the profile distribution) and `hermes/install.sh`, idempotent, which installs the board, the profile, the user service and the tailnet publication, and removes them all with `--uninstall`.

## Why this shape

video-factory declares and installs its own board, so the factory's repository and configuration stay untouched; everything goes through Hermès's CLI and `tailscale serve`.

## If you change this

- **Hits:** the machine's Hermès (a new board, a new profile), `~/.config/systemd/user/video-factory-studio.service`, the tailnet's port 8448.
- **Does not hit:** `~/.hermes/config.yaml`, the factory's profiles, plugins, crons and board.

## See

- [`install.sh`](../../../../hermes/install.sh), [`manifest.json`](../../../../hermes/manifest.json)
