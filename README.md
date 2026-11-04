# video-factory

Le Monteur vidéo de Code My Life : il fait les shorts de la chaîne Code My Life, de la prise à la publication, de façon déterministe et sans outil payant ([issue parapluie #1](https://github.com/code-my-life/video-factory/issues/1)).

Ce dépôt est public et ne contient que le moteur : le code de la commande `vf`, les gabarits, le design system et la liste des outils figés. **Aucun contenu de vidéo n'y entre.** Les scripts et les états vont dans le dépôt privé `code-my-life/video-content`, les prises et les rendus dans un magasin local (`~/studio/media`). Le contrôle « Aucun contenu » de la CI refuse tout média et tout dossier `videos/` suivi par git.

## La chaîne

1. Un script approuvé, dans `video-content`.
2. Le tournage à l'iPhone, le masque du robot appliqué.
3. `vf ingest`, puis `scan` (aucun visage), `blur` (le fond), `transcribe`, `align`, `cut`, `voice`, `compose` (HyperFrames), `master` et `qc`.
4. La publication.

Chaque étape inscrit dans l'état de la vidéo (`state.json`) l'empreinte de ses entrées et de ses sorties, la version de ses outils et ses paramètres. Ce socle ([#2](https://github.com/code-my-life/video-factory/issues/2)) livre `vf doctor` et `vf new` ; les étapes arrivent avec [#4](https://github.com/code-my-life/video-factory/issues/4).

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
```

## Les commandes

| Commande | Effet |
| --- | --- |
| `uv run vf doctor` | Vérifie chaque outil de `toolchain/tools.lock.json` (présent, à sa version et à son empreinte SHA-256), le dépôt de contenu et le magasin des médias. Chaque écart nomme l'outil, l'écart et la commande qui répare. Code de sortie 1 au moindre écart. |
| `uv run vf doctor --install [outil …]` | Installe les outils nommés, ou tous, sous `~/.local/share/video-factory/tools`. Chaque téléchargement est vérifié par son empreinte avant tout usage. |
| `uv run vf new <id>` | Crée `videos/<id>/script.md` (le gabarit) et `videos/<id>/state.json` dans le dépôt de contenu, valides selon `schemas/`. Refuse un id qui existe déjà. |

## Les outils figés

FFmpeg statique, whisper.cpp et son modèle large-v3-turbo, HyperFrames et la base de son image de rendu, les modèles MediaPipe de détection de visage et de segmentation, et ce qu'il faut pour les installer (CMake, Node.js). Chacun est figé par sa version et son empreinte dans [toolchain/tools.lock.json](toolchain/tools.lock.json). Les polices arriveront avec le design system.

## Pour aller plus loin

- [AGENTS.md](AGENTS.md) : les règles et les commandes du dépôt.
- [docs/RUNBOOK.md](docs/RUNBOOK.md) : l'installation, les variables, la montée de version d'un outil.
- [docs/decisions/0001-chaine-du-monteur.md](docs/decisions/0001-chaine-du-monteur.md) : les décisions qui fondent la chaîne.
- [docs/map/AGENTS.md](docs/map/AGENTS.md) : la carte du dépôt (ICM, en anglais).

## Licence et crédits

Le code est sous licence [MIT](LICENSE). Le modèle du robot est crédité dans [CREDITS.md](CREDITS.md). Les outils figés gardent leur licence (FFmpeg en GPL pour le build statique de BtbN, whisper.cpp et son modèle en MIT, HyperFrames et les modèles MediaPipe en Apache 2.0) : aucun n'est redistribué ici, chacun se télécharge depuis sa source.
