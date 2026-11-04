# video-factory

Le Monteur vidéo de Code My Life : il fait les shorts de la chaîne Code My Life, de la prise à la publication, de façon déterministe et sans outil payant ([issue parapluie #1](https://github.com/code-my-life/video-factory/issues/1)).

Ce dépôt est public et ne contient que le moteur : le code de la commande `vf`, les gabarits, le design system et la liste des outils figés. **Aucun contenu de vidéo n'y entre.** Les scripts et les états vont dans le dépôt privé `code-my-life/video-content`, les prises et les rendus dans un magasin local (`~/studio/media`). Le contrôle « Aucun contenu » de la CI refuse tout média et tout dossier `videos/` suivi par git.

## La chaîne

1. Un script approuvé, dans `video-content`.
2. Le tournage à l'iPhone, le masque du robot appliqué.
3. `vf ingest`, puis `scan` (aucun visage), `blur` (le fond), `transcribe`, `align`, `cut`, `voice`, `compose` (HyperFrames), `master` et `qc`.
4. La publication.

Chaque étape inscrit dans l'état de la vidéo (`state.json`) l'empreinte de ses entrées et de ses sorties, la version de ses outils, ses paramètres et l'empreinte de son code : `vf status` dit ce qui est périmé, `vf run` ne refait que cela. Les mêmes entrées donnent le même master, image par image (`framemd5`). Le socle vient de [#2](https://github.com/code-my-life/video-factory/issues/2), la chaîne de [#4](https://github.com/code-my-life/video-factory/issues/4) ; son gabarit visuel est provisoire jusqu'au design system vidéo.

## Les guides

- [Les comptes de la marque](docs/comptes.md) : TikTok, YouTube et Instagram, à créer une fois.
- [Le tournage](docs/tournage.md) : les réglages de l'iPhone, le cadrage et les règles d'anonymat.
- [La publication à la main](docs/publication.md) : les champs de chaque plateforme, le crédit du robot et la conformité.

## Démarrer

Prérequis : Linux ou WSL 2, [uv](https://docs.astral.sh/uv/), git, Docker Desktop (intégration WSL) et un compilateur C et C++ (gcc, g++).

```bash
git clone https://github.com/code-my-life/video-factory.git
cd video-factory
uv sync
uv run vf doctor --install   # télécharge, vérifie et installe les outils figés
uv run vf doctor             # vérifie que tout est en place
uv run vf new ma-video       # crée videos/ma-video/ dans video-content
# écrire videos/ma-video/script.md, puis :
uv run vf ingest ma-video ~/prises/IMG_0001.MOV
uv run vf run ma-video       # jusqu'au master et à son contrôle
```

## Les commandes

| Commande | Effet |
| --- | --- |
| `uv run vf doctor` | Vérifie chaque outil de `toolchain/tools.lock.json` (présent, à sa version et à son empreinte SHA-256), le dépôt de contenu et le magasin des médias. Chaque écart nomme l'outil, l'écart et la commande qui répare. Code de sortie 1 au moindre écart. |
| `uv run vf doctor --install [outil …]` | Installe les outils nommés, ou tous, sous `~/.local/share/video-factory/tools`. Chaque téléchargement est vérifié par son empreinte avant tout usage. |
| `uv run vf new <id>` | Crée `videos/<id>/script.md` (le gabarit) et `videos/<id>/state.json` dans le dépôt de contenu, valides selon `schemas/`. Refuse un id qui existe déjà. |
| `uv run vf ingest <id> <prise …> [--voie <voie>]` | Range les prises dans le magasin des médias, par leur empreinte, et fait la copie de travail : recadrée et remise à l'endroit selon `mask/routes.json`, 30 images par seconde, BT.709, son à 48 kHz, sans aucune métadonnée. |
| `uv run vf ingest <id> --capture <nom> <fichier>` | Range une capture d'écran (PNG) ou un court extrait muet (MP4), nettoyé, sous le nom que le script lui donne par `[capture: <nom>]`. |
| `uv run vf run <id> [--refaire <étape …>]` | Passe les étapes (`scan`, `blur`, `transcribe`, `align`, `cut`, `voice`, `compose`, `master`, `qc`) qui n'ont jamais tourné ou sont périmées, puis donne le master 1440x2560 et l'export TikTok 1080x1920. Code 1 si `qc` refuse le master. |
| `uv run vf status <id>` | Dit, étape par étape, ce qui est à jour, périmé (et pourquoi) ou en attente. |

## Les outils figés

FFmpeg statique, whisper.cpp et son modèle large-v3-turbo, HyperFrames et son image de rendu (construite sur la machine, chaque couche figée, au même digest à chaque construction), les modèles MediaPipe de détection de visage et de segmentation (lancés par LiteRT), et ce qu'il faut pour les installer (CMake, Node.js). Chacun est figé par sa version et son empreinte dans [toolchain/tools.lock.json](toolchain/tools.lock.json) ; les paquets Python le sont dans `uv.lock`. Le gabarit provisoire embarque une police, Inter Bold ; celles du design system arriveront avec lui.

## Pour aller plus loin

- [AGENTS.md](AGENTS.md) : les règles et les commandes du dépôt.
- [docs/RUNBOOK.md](docs/RUNBOOK.md) : l'installation, les variables, la montée de version d'un outil.
- [docs/decisions/0001-chaine-du-monteur.md](docs/decisions/0001-chaine-du-monteur.md) : les décisions qui fondent la chaîne.
- [docs/decisions/0002-chaine-de-derush-et-de-rendu.md](docs/decisions/0002-chaine-de-derush-et-de-rendu.md) : comment chaque étape est faite, et ce qui reste provisoire.
- [docs/map/AGENTS.md](docs/map/AGENTS.md) : la carte du dépôt (ICM, en anglais).

## Licence et crédits

Le code est sous licence [MIT](LICENSE). Le modèle du robot et la police du gabarit sont crédités dans [CREDITS.md](CREDITS.md). Les outils figés gardent leur licence (FFmpeg en GPL pour le build statique de BtbN, whisper.cpp et son modèle en MIT, HyperFrames, LiteRT et les modèles MediaPipe en Apache 2.0) : aucun n'est redistribué ici, chacun se télécharge depuis sa source. Seule la police Inter Bold (SIL Open Font License 1.1) est dans le dépôt, avec sa licence.
