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
| `whisper-large-v3-turbo` (fichier) | L'empreinte SHA-256 du fichier, qui fixe aussi sa version. |
| `whisper.cpp` (construit depuis ses sources) | L'archive du tag, vérifiée par son empreinte et par le commit qu'elle porte avant la construction ; `.vf-build.json` garde la source, les options de CMake et l'empreinte du binaire ; `whisper-cli --version`. |
| `hyperframes` (npm) | La version et l'empreinte du paquet installé, le `package-lock.json` utilisé, `hyperframes --version`, et la télémétrie coupée dans `~/.hyperframes/config.json`. |
| `hyperframes-render-base` (image Docker) | L'étiquette `node:22.23.4-bookworm-slim` pointe sur le digest figé. |
| `hyperframes-render` (image construite) | Le dossier `toolchain/hyperframes/` a l'empreinte du lock, et l'image `vf-hyperframes-render:0.9.12-1` a le digest figé (son manifeste, ou sa configuration dans l'ancien magasin de Docker). |
| `node-24`, `chromium-headless-shell` (archives) | Comme les autres archives ; Chrome Headless Shell se livre en zip : l'installation n'en extrait que des fichiers ordinaires, sans lien ni chemin qui sorte du dossier, chacun avec son droit d'exécution. |
| `playwright` (npm) | Comme `hyperframes` : la version et l'empreinte de `playwright-core`, le `toolchain/playwright/package-lock.json` utilisé, `playwright-core --version`. Il ne télécharge aucun navigateur (`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`) : `vf capture` lance `chromium-headless-shell` par son chemin. |
| `gsap`, `lottie-web`, `dotlottie-web`, `animejs`, `three` (bibliothèques) | Chaque fichier copié, à son empreinte SHA-256, et rien d'autre dans le dossier. L'installation télécharge l'archive npm, vérifie son empreinte, puis n'en extrait que les fichiers nommés, chacun vérifié. GSAP est pris dans l'archive de HyperFrames 0.9.12 elle-même (`dist/vendor/npm/gsap@3.15.0/dist`) : la copie qu'il embarque. |

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

### Le projet de `compose`

`compose` écrit un vrai projet HyperFrames dans son dossier de travail, depuis `templates/hyperframes/` : `index.html` (la racine, 1440x2560, 30 images par seconde, la durée du montage, la prise dans un conteneur que les zooms agrandissent), une scène par plan du script sous `compositions/shot-<n>.html`, la piste de sous-titres `compositions/captions.html`, la police et les bibliothèques chargées par le projet, copiées depuis `VF_TOOLS` dans `assets/lib/` (GSAP toujours). Les plans `etapes` et `stat` et les sous-titres sont des blocs et un composant du registre de HyperFrames, installés comme source et restylés (voir ci-dessous). Puis, dans l'ordre :

1. `compose` refuse un projet qui charge quoi que ce soit hors de lui-même (une adresse de CDN, une police en ligne, un fichier absent), en nommant chaque fichier ;
2. `hyperframes check --json` tourne dans l'image figée, sans réseau ; une erreur arrête `compose` et la nomme (section, code, message, fichier). Les avertissements sont relevés dans le résumé de l'étape (`state.json`) ;
3. deux rendus : la passe vidéo, puis la passe texte (`texte.html`, gardée hors du projet, montée par-dessus `index.html`).

Le skill `video-factory` (`.claude/skills/video-factory/`) dit comment passer des annotations aux scènes, les zones sûres, le rendu sans réseau, les bibliothèques autorisées et leur livraison.

### Le registre

`hyperframes add` demande le réseau : il ne sert qu'au développement, jamais pendant un rendu. Dans `templates/hyperframes/`, avec le Node figé et les variables ci-dessus :

```bash
cd templates/hyperframes
PATH="$VF_TOOLS/node/v22.23.4/bin:$PATH" "$VF_TOOLS/hyperframes/0.9.12/node_modules/.bin/hyperframes" add <nom> --no-clipboard --json
```

`hyperframes.json` fige le registre au tag v0.9.12 (commit `1ff4cefd`), celui du CLI figé ; `add` inscrit l'élément dans `hyperframes.json` et l'empreinte de chaque fichier écrit dans `hyperframes.lock.json`. Le fichier installé est commité tel quel, puis adapté dans un second commit (sans CDN ni police en ligne, identifiants préfixés, données de `compose`, style sobre et provisoire), pour que git garde la source d'origine.

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
uv run vf ingest ma-video ~/prises/IMG_0001.MOV                   # les prises, dans l'ordre, propres et cadrées en 9:16
uv run vf run ma-video
uv run vf status ma-video
```

- `vf ingest` range chaque prise telle quelle dans le magasin (`VF_MEDIA`, sous son empreinte), puis fait la copie de travail (étape `ingest`). Une capture est rangée après nettoyage (métadonnées et son retirés).
- `vf run` passe les étapes dans l'ordre et refait celles qui n'ont jamais tourné ou sont périmées ; une étape suivante n'est refaite que si ses entrées ont changé. Chaque étape inscrit son relevé dans `state.json` dès qu'elle finit. Code de sortie 1 si une étape échoue ou si `qc` refuse le master ; sinon `vf run` affiche où sont le master et l'export TikTok.
- `vf status` dit, pour chaque étape, « à jour », « périmée » (avec la raison : entrée, paramètres, outil, code de l'étape, sortie absente), « jamais passée » ou « en attente » (après une étape périmée), et rappelle les refus de `qc`.
- Puis commiter `state.json` dans `video-content` : il porte l'empreinte de chaque fichier du magasin.

| Étape | Lit | Écrit |
| --- | --- | --- |
| `ingest` | les prises | la copie de travail (MKV : H.264, PCM 24 bits), au cadre de la prise, sa description |
| `transcribe` | la copie de travail | les mots, leurs temps, les silences |
| `align` | les mots, `script.md` | chaque mot gardé, reprise, hésitation ou hors script |
| `cut` | l'alignement | la liste de décision de montage |
| `voice` | la copie de travail, la liste | la voix à -14 LUFS (WAV) |
| `compose` | la copie de travail, la liste, `script.md`, les captures | les images (PNG), le fond musical, le plan, les boîtes de texte |
| `master` | les images, la voix, la musique | le master 1440x2560, l'export TikTok 1080x1920, leurs `framemd5` |
| `qc` | le master, l'export, le plan, les boîtes de texte | le rapport de contrôle |

Tout est rangé dans le magasin sous `<empreinte>.<extension>` (les images de `compose` sous `<empreinte>.frames/`), en lecture seule. Rien ne s'efface seul : supprimer à la main les fichiers dont aucun `state.json` ne parle plus.

## Comparer deux rendus

```bash
uv run vf run ma-video --refaire compose master
```

refait le rendu et le master même à jour. `state.json` garde l'empreinte des fichiers `master_framemd5` et `tiktok_framemd5` : deux rendus des mêmes entrées doivent donner la même. Après une montée de version de HyperFrames, faire ce rendu sur une vidéo publiée et comparer.

## Tourner un plan d'app (`vf capture`)

Les vidéos vitrine montrent la vraie app, jamais une maquette (#19, ADR 0005). Un plan se déclare en JSON (`schemas/capture-plan.schema.json`), sous `vitrine/<app>/plans/` :

```bash
uv run vf doctor --install node-24 playwright chromium-headless-shell
uv run vf capture vitrine/factory-live/plans/plan3-graphe.json
```

`vf capture` :

1. vérifie le plan (un plan refusé nomme chaque champ en cause) et la source de l'app (`vitrine/<app>/source.json`) ;
2. construit la démo dans `VF_MEDIA/vitrine/travail/<app>/<clé>/` (ou `--travail`) : le seul commit figé (`git fetch --depth 1`), la variante de scénario appliquée par `git apply` (refusée si elle ne s'ajuste plus), l'installation et le build de l'app avec le Node.js du lock. La clé dépend du commit, de la variante, du Node.js et des commandes : un build déjà fait sert tel quel. Le dépôt de l'app n'est jamais touché ;
3. pilote la démo avec Playwright et Chrome Headless Shell, horloge simulée, une milliseconde à la fois, et écrit dans `VF_MEDIA/vitrine/<plan>/` (ou `--sortie`) : `frames/f_000001.png`…, `track.json` (la boîte de chaque élément suivi à chaque image, la scène filmée, les gestes faits, la taille de chaque texte visible) et `empreintes.json` (l'empreinte de chaque image, de la trajectoire, et `all` sur le tout) ;
4. si le plan a une caméra (à l'ordinateur) : écrit la scène `scene/` depuis `templates/hyperframes/camera-follow/`, la vérifie (`hyperframes check --json`, dans l'image figée, sans réseau), la rend de même, en fait `<plan>.mp4` et écrit `mesures.json` : la durée réelle de chaque mouvement, le plus petit texte de l'app dans l'image finale pendant les tenues (26 px au moins), la plus haute bande vide hors de la bande des sous-titres (10 % de la hauteur au plus), le temps du rendu. `--sans-rendu` s'arrête après la vérification ;
5. si le plan a un téléphone (à l'iPhone, `phone`) : écrit la scène depuis `templates/hyperframes/phone/` (l'écran capturé dans un téléphone générique en 3D, un doigt sur chaque toucher, la notification avec l'icône de l'app), la vérifie, la rend et en fait `<plan>.mp4`.

`--scene-seule` garde la capture déjà faite (`track.json` et les images) et ne refait que la scène : pour régler une caméra, des poses ou un titre sans repasser les minutes de capture. Un geste qui échoue laisse `erreur.png`, la page telle qu'elle était.

Les gestes et la caméra (#22) :

- `click` (ordinateur) et `tap` (iPhone) relèvent le rectangle de leur cible : la scène y dessine un gros curseur (6 % de la hauteur du cadre), qui arrive, presse au clic et s'efface, ou un doigt. `"cursor": false` cache un geste (un second toucher au même instant, par exemple). Le sélecteur est celui de Playwright : `>> visible=true` prend le premier élément visible, `nav[aria-label="…"] >> text=…` cherche dans un conteneur.
- `scroll` fait défiler le conteneur qui défile autour de l'élément visé (sinon la page), sur l'horloge simulée, jusqu'à le placer à `offset` pixels du haut de la fenêtre ; avec `left`, de côté, son bord gauche à `left` pixels du bord gauche (le graphe de factory-live défile ainsi). Une page ne défile que jusqu'à son bas : un élément proche du bas reste plus bas que demandé (`result.to` dans `track.json` dit où la page s'est arrêtée).
- `camera.cuts` change la cible à un instant du scénario : un autre élément (`follow`), une autre échelle, une autre ancre, un mouvement de `move` secondes. `"hold": true` fige la caméra (pendant un défilement : on voit la page défiler) ; une échelle sous 1,6 ou `"fit"` (toute la scène) fait un plan large, que la règle des 26 px ne mesure pas.

Refaire un plan : relancer la même commande ; la ligne « capture : … images, empreinte … » donne l'empreinte de tout le plan (`all` de `empreintes.json`), et la comparer à celle d'une capture précédente dit s'il est refait à l'identique. **Ce n'est pas encore toujours le cas** (#19, « Ce qui n'est pas prouvé ») : deux captures du plan 3 ont la même trajectoire jusqu'à l'image 76, puis des écarts d'un dixième de pixel CSS au plus, et des images qui diffèrent de quelques centaines de pixels sur 20 millions (23 niveaux au plus), autour des indicateurs qui tournent et des animations de Motion ; deux captures d'un plan court (24 images) diffèrent de même. Ce qui reste lit encore un temps réel (une image de rendu de Chrome, un observateur de taille) ; le chercher, ne pas l'accepter comme normal.

Les plans de factory-live :

| Plan | Ce qu'il montre |
| --- | --- |
| `plan3-graphe` | La vidéo 1, plan 3 : claude-cockpit#73 glisse du brief au code puis à la gate, sur le graphe zoomé (zoom de l'app à 1,3), la caméra la suit à l'échelle 2, l'issue à mi-hauteur, au-dessus de la bande des sous-titres. Fenêtre 1440x1600, x3, 55,5 à 64,5 s du scénario. |
| `plan2-iphone` | La vidéo 1, plan 2 : le téléphone entre en 3D et se pose, la ligne d'usine sur l'iPhone, claude-cockpit#73 quitte le brief. 54,5 à 59,5 s. |
| `plan4-transcription` | La vidéo 1, plans 4 et 5 : clic sur claude-cockpit#73 à la gate, la caméra va vers le bas de la fenêtre, puis la page défile dans un cadre fixe jusqu'au run #187 (gate, nemotron), clic sur « Transcription », qui défile en direct. 64,5 à 76,5 s. Le montage n'en garde que le clic (0 à 1,15 s) puis, en coupe franche, la fiche en place (à partir de 2,35 s) ; le bandeau du plan 5 se pose dessus. |
| `plan6-debloquer` | La vidéo 1, plan 6 : sur l'iPhone, la notification du blocage de factory-live#2, le doigt l'ouvre, la question, « Débloquer » avec la réponse préremplie, le suivi jusqu'au run suivant #192. 72,5 à 84,5 s (la cause est corrigée à 72 s). |
| `plan7-recul` | La vidéo 1, plan 7 : factory-live#2 débloquée hors champ, zoom 1,3, le graphe défilé de côté jusqu'à la colonne de droite (le zoom de l'app part de la gauche), claude-cockpit#73 passe la CI de main et le déploiement, puis la caméra recule (échelle 1,5) et l'issue arrive à Terminé. 79 à 89 s. |
| `iphone-ligne` | L'iPhone : la ligne d'usine en 390x844, tactile, en x3, une seconde au départ de claude-cockpit#73 du brief. |
| `parcours-une-issue` | Le relevé de la variante : la station de claude-cockpit#73, deux images par seconde, de 0 à 95 s (intake, brief, implémentation, gate, revue, fusion, CI de main, déploiement, Terminé). |

La variante de factory-live (`vitrine/factory-live/scenario.patch`) se refait sur un nouveau commit dans une copie de travail de factory-live, jamais dans son dépôt : appliquer l'ancienne variante, corriger, vérifier (`npx tsc -b apps/web`, `npx vitest run`, `npx prettier --check`), puis `git diff > scenario.patch` et changer `commit` dans `source.json`.

### Le coût

Mesuré le 5 novembre 2026 sur le plan 3 (270 images, 9 s, fenêtre 1440x1600 en x3, machine de 16 fils, WSL 2) :

| Étape | Temps |
| --- | --- |
| Construction de la démo (`npm ci` et build, cache npm chaud) | 13 s, une fois par clé |
| Capture : 64,5 s de scénario pas à pas (1 ms), puis 270 images de 4320x4800 | 5 à 7 min (303 s, 365 s, 445 s sur trois captures) |
| Rendu de la scène sans flou (1 copie) | 26 s |
| Rendu avec le flou, 6 copies visibles à chaque image | 270 s, soit 10,5 fois le rendu sans flou |
| Rendu avec le flou, 6 copies seulement pendant les mouvements (le réglage retenu) | 150 s et 232 s sur deux rendus, soit 6 à 9 fois le rendu sans flou |

Le flou coûte parce que chaque copie est une couche de 2880x3200 à composer ; le cacher pendant les tenues (238 images sur 270) gagne de 15 à 45 % selon le rendu, et faire l'extrait à l'échelle de la caméra plutôt qu'en x3 (2,25 fois moins de pixels) a ramené un rendu de plusieurs dizaines de minutes à quelques minutes. Pour moins encore : moins de copies (4 au lieu de 6) ou un obturateur plus court, au prix d'un flou en marches d'escalier sur les mouvements rapides. Les PNG d'une capture pèsent environ 300 Mo, sur le disque de WSL.

## Une vitrine

Une vitrine montre une app : la voix, réplique par réplique, sur des plans de l'app (`vf capture`) et des rushs ([#28](https://github.com/code-my-life/video-factory/issues/28)).

```bash
uv run vf new ma-vitrine --vitrine   # le script, depuis templates/script-vitrine.md
# écrire les répliques, puis :
uv run vf voix ma-vitrine            # le texte à coller dans ElevenLabs (--modele v2 pour Multilingual v2)
uv run vf ingest ma-vitrine --voix ~/inbox/voix.mp3 --capture plan1 ~/inbox/plan1.mp4 --capture rush-pr ~/inbox/rush.mp4
uv run vf run ma-vitrine             # ingest, transcribe et align : chaque mot du script et son instant
uv run vf status ma-vitrine          # les fichiers rangés, puis les étapes
```

L'en-tête porte les réglages de la vidéo. Chacun est un choix de cette vidéo, révisable, jamais une constante de la chaîne :

| Champ | Effet |
| --- | --- |
| `genre: vitrine` | Le script est une vitrine (sans ce champ, une vidéo face caméra). |
| `theme: primer` | L'apparence des titres, des sous-titres, du bandeau et de l'écran de fin ; Primer, l'apparence de factory-live, pour la vidéo 1. Obligatoire. |
| `bandeau: "titre \| texte \| début \| durée"` | L'appel du milieu de la vidéo, en secondes de la vidéo. |
| `vignette: "ligne \| ligne avec un *mot*"` | Le texte de la vignette ; le mot entre astérisques prend la couleur d'accent. |
| `vignette_image: "52,95"` | La seconde de la vidéo dont l'image porte la vignette. |

Chaque ligne est une réplique, dans l'ordre où la voix la dit. Ses annotations la placent sur ses plans et n'ajoutent aucun mot dit :

| Annotation | Effet |
| --- | --- |
| `[plan: plan1 \| depuis 0,3 \| durée 4,6 \| voix 0,15]` | Un plan tiré de la capture rangée sous ce nom (un plan de `vf capture` ou un rush), depuis sa seconde `depuis`, pendant `durée` ; la réplique commence `voix` secondes après le début du plan. Plusieurs `plan` sur une ligne se suivent. |
| `[jumeaux: rush-pr \| … \| avant 0 362 \| après 960 362 \| taille 940 612 \| volet 1,3 0,5]` | Les jumeaux d'une PR dans un enregistrement d'écran : le volet « avant », puis le volet « après », de même taille, avec un balayage de l'un à l'autre (son début et sa durée, en secondes dans le plan). |
| `[suite: voix 3,7]` | La réplique continue dans le plan de la réplique d'avant. |
| `[fin: voix 0,4]` | La réplique se dit sur l'écran de fin, jusqu'à la durée visée. |
| `[appel: github \| titre \| texte]` | Une ligne de l'écran de fin, allumée quand la voix dit le mot qui précède. |
| `[ton: chuckles]` | Une indication de jeu pour ElevenLabs, avant le mot qui suit ; seul `vf voix` la lit. |

Les temps prennent une virgule ou un point. Une réplique a des `plan` ou des `jumeaux`, ou `suite`, ou `fin`. Une erreur nomme la ligne du fichier.

- **La voix** est un fichier, généré ou enregistré, rangé tel quel par `vf ingest --voix` (MP3 ou WAV). Sa copie de travail est la voix seule, en WAV 48 kHz mono, sans métadonnée. Un fichier sans piste son est refusé.
- **`vf voix`** écrit `videos/<id>/voix-elevenlabs.txt` dans `video-content` : les répliques dans l'ordre, avec leurs tons et `[short pause]` entre deux répliques pour Eleven v3 (pas de pause avant une réplique qui commence par un ton), ou une pause de 0,8 s sans ton pour Multilingual v2 (`--modele v2`). Si la voix générée s'écarte du texte, corriger le script : c'est lui que les sous-titres affichent.
- **Les rushs** se rangent comme les plans de `vf capture`, par `--capture <nom>` : nettoyés, sans son, à 30 images par seconde.
- **`align`** donne à chaque mot du script son instant dans la voix, sous sa forme écrite. Un mot mal entendu par whisper prend le texte du script (« Cloud » pour « Claude »), un mot entendu en morceaux prend le temps de ses morceaux (« Factory » « Live » pour « factory-live »), et un mot avalé (« l'EPR » pour « les PR ») partage le temps de son voisin.

## Ce qui reste provisoire

- Le style des gabarits de `compose` (`templates/hyperframes/`) : une police (Inter Bold, OFL), du texte blanc, des plans sur fond noir, les sous-titres par groupes de trois mots au plus sur un voile sombre. Les blocs du registre y sont restylés sobrement, sans charte : le style définitif viendra du design system vidéo, après des maquettes validées.
- Le montage d'une vitrine : `vf run` s'arrête après `align` jusqu'à la PR 2 de #28 (`compose` pour une vitrine, ses thèmes, la vignette dans `vf publish`).
- Le seuil de silence de `transcribe` (-40 dB), le lexique des hésitations (`align.FILLERS`), la couleur « casque » (`voice.HELMET`) : à régler sur les premières vraies prises.

## Le board « studio »

Le board Hermès « studio » suit chaque vidéo de l'idée à la publication, à côté du board « factory », dans le même Hermès (décisions : [ADR 0004](decisions/0004-board-studio.md)). Prérequis : Hermès installé et sa passerelle Telegram active, `tailscale` connecté au tailnet, `TELEGRAM_CHAT_ID` et `FREELLMAPI_API_KEY` dans `~/.hermes/.env`.

```bash
hermes/install.sh              # installe, ou remet à jour ce qui a changé ; relançable
hermes/install.sh --uninstall  # retire le service, la page du tailnet, le profil studio-writer et le board
```

L'install crée le board `studio`, installe le profil `studio-writer` (et copie sa clé `FREELLMAPI_API_KEY` de la racine), écrit et lance le service utilisateur `video-factory-studio.service` (`vf studio serve`, depuis ce clone, avec les `VF_*` de l'environnement de l'install), puis publie la page sur le tailnet : `https://<machine>.<tailnet>.ts.net:8448`, en HTTPS, jamais sur Internet. Elle ne touche ni à `~/.hermes/config.yaml`, ni à la factory. La désinstallation supprime le board et ses cartes ; les vidéos (`VF_CONTENT`) et le magasin (`VF_MEDIA`, dont `publication/`) restent.

### Les stations

| Station | Qui | Ce qui se passe | Le geste du propriétaire |
| --- | --- | --- | --- |
| Idée | voie en code | `vf new <id>` | Ouvrir la vidéo : la page (« Nouvelle vidéo ») ou `uv run vf studio carte <id> "l'idée"` |
| Script | `studio-writer` | Un brouillon de `script.md`, à partir de l'idée, de `idees.md` et du positionnement de la marque, gardé seulement s'il passe les règles en code | |
| Approbation | le propriétaire | Message Telegram | Approuver : `/kanban --board studio unblock <carte>`, ou le bouton de la page |
| Tournage | le propriétaire | Message Telegram | Envoyer les prises depuis la page, dans Safari (ou `vf ingest`) |
| Montage | voie en code | `vf run <id>`, sans modèle | |
| Revue | le propriétaire | Message Telegram, le master sur la page | Valider : `unblock`, ou le bouton |
| Publication | voie en code, puis le propriétaire | `vf publish <id>` range l'export TikTok, le master et la légende ; message Telegram | Publier à la main, puis « Publiée » : `unblock`, ou le bouton (avec le lien) |
| Publiée | | La carte est terminée | |

Pour refaire : `/kanban --board studio unblock <carte> --reason "refaire : ce qui change"`, ou le bouton « Refaire » de la page. Depuis Approbation, le brouillon est réécrit avec la demande ; depuis Revue, `vf run` repasse. Une voie en échec (un brouillon refusé, `vf run` ou `vf publish` qui échoue) laisse la carte à sa station, prévient sur Telegram avec la raison, et repart au déblocage.

Une vidéo qui existe déjà s'ouvre par `uv run vf studio carte <id>` : sa carte entre à la station que son `state.json` prouve. Ne pas ouvrir une carte par `/kanban create` sans `--assignee studio-idee` : elle irait à l'assigné par défaut de la factory.

### Le service

- `systemctl --user status video-factory-studio`, `journalctl --user -u video-factory-studio -f` : les passes (toutes les 20 s), les voies et les requêtes de la page.
- `uv run vf studio tick` : une passe au premier plan, pour voir ce que chaque carte ferait.
- La page répond sur `http://127.0.0.1:8448/sante` ; `tailscale serve status` montre sa publication sur le port 8448.
- Les captures d'écran d'une vidéo (`[capture: …]`) se versent encore par `uv run vf ingest <id> --capture <nom> <fichier>`.

### L'API du workflow, pour factory-live

Le service sert aussi l'API générique du workflow (ADR 0006), en JSON :

| Besoin | Commande |
| --- | --- |
| La fiche du studio | `curl -s 127.0.0.1:8448/api/workflow` (source : `hermes/workflow.json`) |
| Les vidéos et leur état | `curl -s 127.0.0.1:8448/api/items` |
| Une vidéo, ses étapes et ses fichiers | `curl -s 127.0.0.1:8448/api/items/<id>` |
| Les mots du master | `curl -s 127.0.0.1:8448/api/items/<id>/words` |
| Le geste du propriétaire | `POST /api/items/<id>/gesture` avec `{"decision": "ok" \| "refaire", "note": "…"}` |

Changer une station ou sa place dans le graphe de factory-live : modifier `hermes/workflow.json` (le test `tests/test_api.py` vérifie qu'elle suit le manifeste et le contrat de factory-live).

## Monter un outil de version

1. Télécharger le nouveau fichier dans un dossier vide, et calculer son empreinte (`sha256sum`). Une empreinte se calcule toujours sur le fichier téléchargé, jamais recopiée d'une page.
2. Pour une archive, calculer l'empreinte de l'arbre extrait :

   ```bash
   uv run python -I -c "import sys; from pathlib import Path; from video_factory.install import extract; from video_factory.hashing import tree_sha256; d = Path(sys.argv[2]); extract(Path(sys.argv[1]), d, 1); print(tree_sha256(d))" <archive> <dossier-vide>
   ```

3. Pour HyperFrames : changer la version dans `toolchain/hyperframes/package.json`, refaire le `package-lock.json` avec le npm figé (`PATH="$VF_TOOLS/node/v22.23.4/bin:$PATH" npm install --package-lock-only --ignore-scripts --no-audit --no-fund` dans `toolchain/hyperframes/`), et calculer `tree_sha256` sur l'archive npm comme au point 2. Vérifier aussi la base du nouveau `Dockerfile.render`.
4. Changer l'entrée de `toolchain/tools.lock.json` (version, adresse, `sha256`, `tree_sha256`, texte de version attendu), puis `uv run pytest`, `uv run vf doctor --install <outil>` et `uv run vf doctor`.
5. Pour une bibliothèque (`kind: library`) : calculer l'empreinte de l'archive npm et celle de chaque fichier extrait (`tar -xzf <archive> -O package/<chemin> | sha256sum`). Pour GSAP, reprendre l'archive de la nouvelle version de HyperFrames et le dossier `dist/vendor/npm/gsap@<version>/dist` qu'elle porte.
6. Ouvrir une PR de type Maintenance. Pour HyperFrames, avec les empreintes de rendu comparées (#4).

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
| `gsap : gsap.min.js : empreinte … au lieu de …` (ou une autre bibliothèque) | La copie installée a changé : `uv run vf doctor --install gsap`. |
| `vf capture : … la variante scenario.patch ne s'applique pas` | Le commit de `source.json` et la variante ne vont plus ensemble : refaire la variante sur ce commit (« Tourner un plan d'app »). |
| `vf capture : … champ « … »` | Le plan est refusé : corriger le champ nommé (`schemas/capture-plan.schema.json`). |
| `hyperframes-render : … ne correspond pas au lock` | `toolchain/hyperframes/` a changé : reconstruire l'image (`uv run vf doctor --install hyperframes-render` refusera l'ancien digest et affichera le nouveau), puis reporter `context_sha256`, `sha256` et `config_sha256` dans le lock, par PR. |

| Message de `vf run` | Réparation |
| --- | --- |
| `aucune prise : vf ingest <id> <fichiers>` | Verser les prises. |
| `prise 1 : 1206x2622, pas en 9:16 ; recadrer la prise avant de la verser` | Recadrer la prise en 9:16 (par exemple 1206x2144), puis la verser à nouveau. |
| `capture absente : « ligne »` | `uv run vf ingest <id> --capture ligne <fichier>`. |
| `hyperframes check refuse le projet :` suivi des erreurs | Chaque ligne nomme la section (`lint`, `runtime`, `layout`, `contrast`…), le code de la règle et le fichier : corriger le gabarit de `templates/hyperframes/` (skill `video-factory`). |
| `le projet ne doit charger que ses propres fichiers` | Un gabarit charge une adresse de CDN, une police en ligne ou un fichier absent : la ligne nomme le fichier et l'adresse. |
| `bibliothèque hors du lock : …` | Une scène charge `assets/lib/<nom>/` sans entrée `library` au lock : l'ajouter, ou retirer le chargement. |
| `qc refuse le master` | Chaque ligne nomme sa borne : durée, sonie, crête vraie, format, zone sûre, plans face caméra. |

Une construction de whisper.cpp qui échoue faute de compilateur demande `build-essential` (gcc, g++).
