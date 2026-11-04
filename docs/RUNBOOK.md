# RUNBOOK

Installer video-factory, vérifier ses outils, créer une vidéo, monter un outil de version. Les règles du dépôt sont dans [AGENTS.md](../AGENTS.md).

## Prérequis

- Linux ou WSL 2 sur x86-64 : le lock est écrit pour `linux-x86_64`.
- [uv](https://docs.astral.sh/uv/) (0.12.3 en CI) et git.
- Docker Desktop, avec l'intégration WSL activée pour la distribution.
- gcc et g++, pour construire whisper.cpp (`build-essential` sur Ubuntu).
- Environ 3 Go de disque pour les outils, dont 1,6 Go pour le modèle de whisper.

## Installer

```bash
git clone https://github.com/code-my-life/video-factory.git
cd video-factory
uv sync
uv run vf doctor --install
uv run vf doctor
```

`uv sync` installe Python 3.12 et les dépendances aux versions de `uv.lock`. `vf doctor --install` installe tous les outils du lock, sauf ceux déjà en place ; `vf doctor --install whisper.cpp hyperframes` n'installe que ceux-là et ce dont ils dépendent (CMake pour whisper.cpp, Node.js pour HyperFrames). `vf doctor` sort avec le code 0 quand tout est en place, 1 sinon, et donne pour chaque écart la commande qui répare.

## Variables

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `VF_CONTENT` | `~/perso/video-content` | Le clone de `code-my-life/video-content` : les scripts et les états. |
| `VF_MEDIA` | `~/studio/media` | Le magasin des médias, `<sha256>.<ext>`. Sur le disque de WSL, jamais sous `/mnt/` : le disque C: est plein. |
| `VF_TOOLS` | `~/.local/share/video-factory/tools` | Les outils figés, un dossier par outil et par version. |

## Les outils figés

Chaque outil vit dans `$VF_TOOLS/<outil>/<version>/` ; deux versions ne s'écrasent jamais. Le téléchargement passe par un dossier de travail à côté et n'est mis en place qu'une fois vérifié, en un seul renommage.

| Outil | Ce que `vf doctor` vérifie |
| --- | --- |
| `ffmpeg`, `cmake`, `node` (archives) | L'empreinte de l'arbre extrait (`tree_sha256` : chaque fichier et chaque lien, ni dates ni droits) et la version que l'outil affiche. |
| `whisper-large-v3-turbo`, `mediapipe-face-detector`, `mediapipe-selfie-segmenter` (fichiers) | L'empreinte SHA-256 du fichier, qui fixe aussi sa version. |
| `whisper.cpp` (construit depuis ses sources) | L'archive du tag, vérifiée par son empreinte et par le commit qu'elle porte avant la construction ; `.vf-build.json` garde la source, les options de CMake et l'empreinte du binaire ; `whisper-cli --version`. |
| `hyperframes` (npm) | La version et l'empreinte du paquet installé, le `package-lock.json` utilisé, `hyperframes --version`, et la télémétrie coupée dans `~/.hyperframes/config.json`. |
| `hyperframes-render-base` (image Docker) | L'étiquette `node:22.23.4-bookworm-slim` pointe sur le digest figé. |

whisper.cpp est construit pour le CPU avec des options fixes (`GGML_NATIVE=OFF`, AVX2, FMA, F16C, BMI2), le même binaire quel que soit le processeur de la machine qui construit. HyperFrames s'installe par `npm ci --ignore-scripts` depuis `toolchain/hyperframes/package-lock.json`, une fois vérifié que ce fichier fige l'archive dont l'empreinte vient d'être contrôlée.

## HyperFrames

Le CLI ne tourne qu'avec l'environnement de son entrée du lock, que `vf` lui donne :

```bash
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1 HYPERFRAMES_NO_UPDATE_CHECK=1 \
  HYPERFRAMES_NO_AUTO_INSTALL=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_OPTIONAL_INSTALL=1
```

Sans `HYPERFRAMES_NO_UPDATE_CHECK=1`, une installation npm de HyperFrames se met à jour toute seule en arrière-plan : jamais `npx hyperframes`, jamais le CLI lancé sans ces variables. L'installation coupe aussi la télémétrie dans la configuration du CLI (`hyperframes telemetry disable`), au cas où.

Pour l'étape `compose` (#4), ce que fait `hyperframes render --docker` en 0.9.12 :

- aucune image n'est publiée : le CLI construit `hyperframes-renderer:<version>` sur la machine depuis le `Dockerfile.render` de son paquet, `FROM node:22.23.4-bookworm-slim`. Seule cette base est figée ici ; les paquets Debian, le chrome-headless-shell « stable » et les dépendances npm de l'image ne le sont pas ;
- le conteneur est lancé sans `--network none` et sans les variables de télémétrie : le rendu y enverrait sa télémétrie. `compose` doit donc lancer le conteneur lui-même, avec `--network none`, `HYPERFRAMES_NO_TELEMETRY=1` et `DO_NOT_TRACK=1`, sur une image figée.

## Une nouvelle vidéo

```bash
uv run vf new ma-video
cd ~/perso/video-content
git add videos/ma-video
git commit -m "ma-video : script et état"
git push
```

`vf new` refuse un id qui existe déjà et un id qui n'est pas fait de minuscules, de chiffres et de tirets. Le script et l'état sont valides selon `schemas/script.schema.json` et `schemas/state.schema.json` (version 1).

## Monter un outil de version

1. Télécharger le nouveau fichier dans un dossier vide, et calculer son empreinte (`sha256sum`). Une empreinte se calcule toujours sur le fichier téléchargé, jamais recopiée d'une page.
2. Pour une archive, calculer l'empreinte de l'arbre extrait :

   ```bash
   uv run python -I -c "import sys; from pathlib import Path; from video_factory.install import extract; from video_factory.hashing import tree_sha256; d = Path(sys.argv[2]); extract(Path(sys.argv[1]), d, 1); print(tree_sha256(d))" <archive> <dossier-vide>
   ```

3. Pour HyperFrames : changer la version dans `toolchain/hyperframes/package.json`, refaire le `package-lock.json` avec le npm figé (`PATH="$VF_TOOLS/node/v22.23.4/bin:$PATH" npm install --package-lock-only --ignore-scripts --no-audit --no-fund` dans `toolchain/hyperframes/`), et calculer `tree_sha256` sur l'archive npm comme au point 2. Vérifier aussi la base du nouveau `Dockerfile.render`.
4. Changer l'entrée de `toolchain/tools.lock.json` (version, adresse, `sha256`, `tree_sha256`, texte de version attendu), puis `uv run pytest`, `uv run vf doctor --install <outil>` et `uv run vf doctor`.
5. Ouvrir une PR de type Maintenance. Pour HyperFrames, avec les empreintes de rendu comparées (#4).

## Le contrôle « Aucun contenu »

`python3 scripts/check_no_content.py` lit l'index de git et refuse, en nommant chaque fichier :

- tout fichier sous un dossier `videos/` ;
- tout média (`.mov`, `.mp4`, `.m4v`, `.m4a`, `.wav`, `.heic`, `.heif`, `.mkv`, `.webm`, `.mp3`, `.aac`, `.flac`, `.caf`) hors de `tests/fixtures/` ;
- toute image `.png`, `.jpg` ou `.jpeg` hors de `design/` et de `tests/fixtures/` ;
- toute fixture de plus de 256 Kio.

`.gitignore` écarte déjà ces fichiers pour qu'ils ne soient pas ajoutés par mégarde ; `git add -f` passe outre, et la CI les arrête.

## CI et ruleset

- `ci.yml` : « Aucun contenu » et « Lint et tests (Python 3.12) », à chaque push sur toute branche et sur chaque PR.
- `conventions.yml` : « Conventions », le contrôle commun de code-my-life/.github (branche, titre, sections et issue typée).
- Ruleset « main » : PR obligatoire avec l'approbation du propriétaire (`CODEOWNERS`), fils de revue résolus, branche à jour, et les contrôles « Aucun contenu », « Lint et tests (Python 3.12) » et « Conventions / Branche, titre et texte de PR ». Ruleset « noms de branches » : une branche se nomme selon un type (`fix/`, `interface/`, `feat/`, `test/`, `chore/`, `docs/`), `dependabot/` ou `revert/`.
- Renommer un job de la CI bloque toutes les PR : le ruleset attend l'ancien nom. Changer les deux ensemble (`gh api repos/code-my-life/video-factory/rulesets`).

## Dépannage

| Message de `vf doctor` | Réparation |
| --- | --- |
| `docker introuvable` ou `Docker ne répond pas` | Démarrer Docker Desktop, activer l'intégration WSL, puis la commande donnée. |
| `construit depuis une autre source ou d'autres options` | Le lock a changé depuis la construction : `uv run vf doctor --install whisper.cpp`. |
| `installé depuis un autre toolchain/hyperframes/package-lock.json` | `uv run vf doctor --install hyperframes`. |
| `dépôt de contenu … absent` | `git clone https://github.com/code-my-life/video-content.git ~/perso/video-content`, ou régler `VF_CONTENT`. |
| `… est sur un disque Windows` | `export VF_MEDIA=~/studio/media`. |

Une construction de whisper.cpp qui échoue faute de compilateur demande `build-essential` (gcc, g++).
