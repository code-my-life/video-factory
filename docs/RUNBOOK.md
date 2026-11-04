# RUNBOOK

Installer video-factory, vérifier ses outils, faire une vidéo de la prise au master, monter un outil de version. Les règles du dépôt sont dans [AGENTS.md](../AGENTS.md), les décisions de la chaîne dans [l'ADR 0002](decisions/0002-chaine-de-derush-et-de-rendu.md).

## Prérequis

- Linux ou WSL 2 sur x86-64 : le lock est écrit pour `linux-x86_64`.
- [uv](https://docs.astral.sh/uv/) (0.12.3 en CI) et git.
- Docker Desktop, avec l'intégration WSL activée pour la distribution.
- gcc et g++, pour construire whisper.cpp (`build-essential` sur Ubuntu).
- Environ 3 Go de disque pour les outils, dont 1,6 Go pour le modèle de whisper, et 1,5 Go pour l'image de rendu.
- De la place dans le magasin des médias : une prise de l'iPhone pèse environ 18 Mo pour 10 s, et chaque rendu de `compose` y laisse ses images (plusieurs gigaoctets pour une minute).

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
| `hyperframes-render` (image construite) | Le dossier `toolchain/hyperframes/` a l'empreinte du lock, et l'image `vf-hyperframes-render:0.9.12-1` a le digest figé (son manifeste, ou sa configuration dans l'ancien magasin de Docker). |

whisper.cpp est construit pour le CPU avec des options fixes (`GGML_NATIVE=OFF`, AVX2, FMA, F16C, BMI2), le même binaire quel que soit le processeur de la machine qui construit. HyperFrames s'installe par `npm ci --ignore-scripts` depuis `toolchain/hyperframes/package-lock.json`, une fois vérifié que ce fichier fige l'archive dont l'empreinte vient d'être contrôlée.

## HyperFrames

Le CLI ne tourne qu'avec l'environnement de son entrée du lock, que `vf` lui donne :

```bash
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1 HYPERFRAMES_NO_UPDATE_CHECK=1 \
  HYPERFRAMES_NO_AUTO_INSTALL=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_OPTIONAL_INSTALL=1
```

Sans `HYPERFRAMES_NO_UPDATE_CHECK=1`, une installation npm de HyperFrames se met à jour toute seule en arrière-plan : jamais `npx hyperframes`, jamais le CLI lancé sans ces variables. L'installation coupe aussi la télémétrie dans la configuration du CLI (`hyperframes telemetry disable`), au cas où.

`hyperframes render --docker` n'est jamais appelé : en 0.9.12, il construit son image depuis le `Dockerfile.render` de son paquet (paquets Debian, chrome-headless-shell « stable » et HyperFrames non figés), puis lance le conteneur sans `--network none` et sans les variables de télémétrie. À la place :

- `toolchain/hyperframes/Dockerfile.render` fige chaque couche : la base par son digest, les paquets Debian de snapshot.debian.org au 27 octobre 2026 (la date de la base), chrome-headless-shell 152.0.7977.30 (la version que HyperFrames 0.9.12 gère lui-même), FFmpeg n8.0.1 (celui de son Dockerfile), HyperFrames par `npm ci` depuis `toolchain/hyperframes/package-lock.json`. Les arguments de construction sont dans le lock (`build_args`), le Dockerfile n'a aucune valeur par défaut.
- `uv run vf doctor --install hyperframes-render` la construit (`docker buildx build`, sans attestation, horodatages réécrits à `SOURCE_DATE_EPOCH`, exportée en archive OCI puis chargée) et refuse une image d'un autre digest : la construction est reproductible, deux constructions sans cache donnent le même.
- `compose` lance le conteneur lui-même : `docker run --rm --network none`, sous l'utilisateur courant, avec les variables de l'entrée `hyperframes` du lock, le projet monté en lecture seule, l'image désignée par son identifiant vérifié. Rien de lourd ne s'écrit dans le conteneur : ses fichiers temporaires vont dans un dossier du magasin monté sur `/vf-work`, et les images extraites de la vidéo dans le dossier du rendu (`--frames-cache-dir off`). Le disque des conteneurs est celui de Docker Desktop, sur le disque C: : les gigaoctets d'images d'un rendu le rempliraient, et Docker Desktop tomberait avec lui (c'est arrivé au deuxième essai de bout en bout, le 4 novembre 2026).

## Une nouvelle vidéo

```bash
uv run vf new ma-video
cd ~/perso/video-content
git add videos/ma-video
git commit -m "ma-video : script et état"
git push
```

`vf new` refuse un id qui existe déjà et un id qui n'est pas fait de minuscules, de chiffres et de tirets. Le script et l'état sont valides selon `schemas/script.schema.json` et `schemas/state.schema.json` (version 2 ; un état de version 1 sans étape se relit en version 2).

## Le script

Une phrase par ligne, dans l'ordre où elle est dite ; un commentaire HTML n'est pas dit. `duree_visee` va de 61 à 65 s (décision du propriétaire du 4 novembre 2026, au lieu de 61 à 90 s dans #4) : ces deux bornes ne sont écrites que dans `schemas/script.schema.json`, et `qc` les y lit pour le master.

| Annotation | Effet |
| --- | --- |
| `[stat: 9 postes \| de l'issue à la mise en ligne]` | Plan plein cadre : le chiffre, puis sa légende. |
| `[etapes: Issue \| Brief \| Code]` | Plan plein cadre : les étapes apparaissent l'une après l'autre. |
| `[code: vf run ma-video]` | Plan plein cadre : le code s'écrit lettre à lettre. |
| `[capture: ligne]` | Plan plein cadre : la capture versée sous ce nom (image fixe avec un lent zoom, ou extrait muet). |
| `[zoom]` | Zoom d'insistance sur le mot qui précède, pendant ce mot et une seconde après. |

Un plan noté en fin de ligne couvre toute la phrase ; noté dans la ligne, il commence au mot qui le précède. Il dure jusqu'au début de la phrase suivante, ou du plan suivant. Les plans face caméra doivent faire la moitié de la durée au plus : `qc` refuse le master sinon.

## De la prise au master

```bash
uv run vf ingest ma-video --capture ligne ~/captures/ligne.png    # une fois par capture que le script appelle
uv run vf ingest ma-video ~/prises/IMG_0001.MOV                   # les prises, dans l'ordre ; --voie <voie> au besoin
uv run vf run ma-video
uv run vf status ma-video
```

- `vf ingest` range chaque prise telle quelle dans le magasin (`VF_MEDIA`, sous son empreinte), puis fait la copie de travail (étape `ingest`). Une capture est rangée après nettoyage (métadonnées et son retirés).
- `vf run` passe les étapes dans l'ordre et refait celles qui n'ont jamais tourné ou sont périmées ; une étape suivante n'est refaite que si ses entrées ont changé. Chaque étape inscrit son relevé dans `state.json` dès qu'elle finit. Code de sortie 1 si une étape échoue ou si `qc` refuse le master ; sinon `vf run` affiche où sont le master et l'export TikTok.
- `vf status` dit, pour chaque étape, « à jour », « périmée » (avec la raison : entrée, paramètres, outil, code de l'étape, sortie absente), « jamais passée » ou « en attente » (après une étape périmée), et rappelle les refus de `qc`.
- Puis commiter `state.json` dans `video-content` : il porte l'empreinte de chaque fichier du magasin.

| Étape | Lit | Écrit |
| --- | --- | --- |
| `ingest` | les prises, la voie | la copie de travail (MKV : H.264, PCM 24 bits), sa description |
| `scan` | la copie de travail | les images avec un visage et les plages à retirer (JSON, sans image) |
| `blur` | la copie de travail | la vidéo au fond flou (sans perte), le masque de la personne ; la netteté relevée (C6) |
| `transcribe` | la copie de travail | les mots, leurs temps, les silences |
| `align` | les mots, `script.md` | chaque mot gardé, reprise, hésitation ou hors script |
| `cut` | l'alignement, les visages | la liste de décision de montage |
| `voice` | la copie de travail, la liste | la voix à -14 LUFS (WAV) |
| `compose` | la vidéo floue, la liste, `script.md`, les captures | les images (PNG), le fond musical, le plan, les boîtes de texte |
| `master` | les images, la voix, la musique | le master 1440x2560, l'export TikTok 1080x1920, leurs `framemd5` |
| `qc` | le master, l'export, le plan, les boîtes de texte | le rapport de contrôle |

Tout est rangé dans le magasin sous `<empreinte>.<extension>` (les images de `compose` sous `<empreinte>.frames/`), en lecture seule. Rien ne s'efface seul : supprimer à la main les fichiers dont aucun `state.json` ne parle plus.

## Comparer deux rendus

```bash
uv run vf run ma-video --refaire compose master
```

refait le rendu et le master même à jour. `state.json` garde l'empreinte des fichiers `master_framemd5` et `tiktok_framemd5` : deux rendus des mêmes entrées doivent donner la même. Après une montée de version de HyperFrames, faire ce rendu sur une vidéo publiée et comparer.

## Ce qui reste provisoire

- Le gabarit de `compose` (`templates/composition/`) : une police (Inter Bold, OFL), du texte blanc, des plans sur fond noir, les sous-titres un mot à la fois. Il sera remplacé par le design system vidéo, après des maquettes validées.
- Le seuil du détecteur de visage, 0,5 (`faces.THRESHOLD`, à un seul endroit) : son calibrage sur des prises étiquetées appartient à #3.
- Le recadrage de la voie `quicklook-screen` dans `mask/routes.json`, à vérifier contre les boutons de Quick Look sur une vraie prise (#3).
- Le seuil de silence de `transcribe` (-40 dB), le lexique des hésitations (`align.FILLERS`), la couleur « casque » (`voice.HELMET`) : à régler sur les premières vraies prises.

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
| `hyperframes-render : … ne correspond pas au lock` | `toolchain/hyperframes/` a changé : reconstruire l'image (`uv run vf doctor --install hyperframes-render` refusera l'ancien digest et affichera le nouveau), puis reporter `context_sha256`, `sha256` et `config_sha256` dans le lock, par PR. |

| Message de `vf run` | Réparation |
| --- | --- |
| `aucune prise : vf ingest <id> <fichiers>` | Verser les prises. |
| `prise 1 : 1179x2556 au lieu de 1206x2622` | La prise ne vient pas de cette voie : `--voie`, ou une nouvelle voie dans `mask/routes.json`. |
| `capture absente : « ligne »` | `uv run vf ingest <id> --capture ligne <fichier>`. |
| `visage détecté de l'image … pendant le mot gardé « … »` | Le masque a lâché pendant une phrase gardée : la retourner, ou en garder une autre prise. |
| `qc refuse le master` | Chaque ligne nomme sa borne : durée, sonie, crête vraie, format, zone sûre, plans face caméra, visage (avec l'image et le temps). |

Une construction de whisper.cpp qui échoue faute de compilateur demande `build-essential` (gcc, g++).
