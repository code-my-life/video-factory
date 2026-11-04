# AGENTS.md

Règles et commandes de video-factory, pour les agents comme pour Claude Code. À lire avant toute modification.

## Ce que fait ce dépôt

video-factory est le Monteur vidéo de Code My Life : la commande `vf` fait les shorts de la chaîne, de la prise à la publication ([#1](https://github.com/code-my-life/video-factory/issues/1)). Le dépôt est public et ne porte que le moteur (code, gabarits, design system, outils figés), jamais un contenu de vidéo. Claude Code fait le travail ; la software factory ne fabrique pas ce dépôt.

## Commandes

| Besoin | Commande |
| --- | --- |
| Installer les dépendances | `uv sync` (Python 3.12, versions de `uv.lock`) |
| Vérifier les outils figés | `uv run vf doctor` |
| Installer les outils figés | `uv run vf doctor --install [outil …]` |
| Créer une vidéo | `uv run vf new <id>`, dans le dépôt de contenu (`VF_CONTENT`) |
| Verser une prise, une capture | `uv run vf ingest <id> <prise …>`, `uv run vf ingest <id> --capture <nom> <fichier>` |
| Faire le master, voir l'état | `uv run vf run <id>`, `uv run vf status <id>` |
| Lint | `uv run ruff check` et `uv run ruff format --check` |
| Tests | `uv run pytest` (les tests qui font tourner FFmpeg ou un modèle prennent les outils figés ; sans eux ils sont sautés, et en CI, où `VF_REQUIRE_TOOLS=1`, ils échouent) |
| Aucun contenu | `python3 scripts/check_no_content.py` |

La CI (`.github/workflows/ci.yml`) lance « Aucun contenu » et « Lint et tests (Python 3.12) » à chaque push, sur toute branche : un push sur ce dépôt public est public. « Conventions » vérifie chaque PR (branche, titre, sections, issue typée). `main` a un ruleset : PR obligatoire, approbation du propriétaire, ces trois contrôles verts. Installation et exploitation : [docs/RUNBOOK.md](docs/RUNBOOK.md). Décisions : `docs/decisions/`.

## Où sont les choses

`pipeline/video_factory/` (le paquet de `vf` et ses huit étapes), `toolchain/` (les outils figés et le `Dockerfile.render`), `schemas/` (les contrats publiés : état, script), `templates/` (le gabarit du script, et `templates/hyperframes/` : les gabarits du projet HyperFrames de `compose` et les blocs du registre, restylés à titre provisoire), `.claude/skills/` (le skill `video-factory` et quatre skills internes de HyperFrames, avec leur origine), `scripts/` (le contrôle « Aucun contenu »), `tests/`.

Carte du dépôt : [docs/map/AGENTS.md](docs/map/AGENTS.md).

## Règles

- Aucun contenu de vidéo ici : ni script, ni prise, ni rendu, ni état. Les scripts et les états vont dans `code-my-life/video-content` (privé), les médias dans le magasin local (`VF_MEDIA`, `~/studio/media` par défaut, sur le disque de WSL). Une fixture de test est synthétique et petite : sous `tests/fixtures/`, 256 Kio au plus.
- Tout outil externe passe par `toolchain/tools.lock.json` : version exacte, empreinte SHA-256 calculée sur le fichier téléchargé (jamais recopiée d'ailleurs), adresse de téléchargement, commande d'installation. `vf doctor --install` vérifie l'empreinte avant tout usage et installe sous `VF_TOOLS`, hors du dépôt. Une montée de version se fait par PR, avec ses nouvelles empreintes (RUNBOOK, « Monter un outil de version »).
- HyperFrames ne tourne qu'avec l'environnement de son entrée du lock : télémétrie, vérification et installation des mises à jour, skills et installations à la demande coupées. Jamais `npx hyperframes`, jamais le CLI lancé sans cet environnement : il se mettrait à jour tout seul. Le rendu et `hyperframes check` se font dans l'image figée `hyperframes-render`, lancée par `compose` avec `--network none` ; jamais `hyperframes render --docker`. `hyperframes add` (registre) ne sert qu'au développement, dans `templates/hyperframes/`, et sa sortie est commitée telle quelle avant d'être adaptée.
- Déterminisme : aucun visuel ne dépend d'autre chose que du temps de la timeline (ni minuterie, ni `Date`, ni horloge `requestAnimationFrame`, ni hasard sans graine) ; GSAP et les autres bibliothèques d'animation (Lottie, dotLottie, anime.js, Three.js) viennent du lock, copiés dans le projet par `compose` : aucune URL de CDN, aucune police téléchargée, et `hyperframes check` passe avant tout rendu (ADR 0003, skill `video-factory`) ; un encodeur a son nombre de fils fixé et les drapeaux `bitexact`. Une étape inscrit dans `state.json` tout ce qui fait son résultat : changer un paramètre, un outil ou le code d'une étape la rend périmée.
- La chaîne prend les prises telles que livrées, propres et cadrées en 9:16 : ni détection de visage, ni recadrage, ni flou du fond. `ingest` ne fait que les normaliser (30 images par seconde constantes, SDR BT.709, sans métadonnées).
- Bibliothèque standard d'abord. Une dépendance Python a sa version exacte dans `pyproject.toml` et dans `uv.lock`.
- Fonctions courtes, pures quand c'est possible. Les processus passent par un exécuteur que les tests remplacent ; les tests n'écrivent que dans leur dossier temporaire.
- Identifiants, commentaires, docstrings et noms de tests en anglais ; documentation et messages de `vf` en français. Aucun nom de personne ni tutoiement dans le code, les commentaires et les tests.
- Aucun tiret cadratin, nulle part : code, docs, commits, PR.
- Branches et PR selon le type de l'issue (ADR 0017 de hermes-software-factory) : `chore/<n°>-<sujet>` et `chore: …` pour une Maintenance, `feat/…` pour une Fonctionnalité, etc.

## Interdits

- Affaiblir un test, désactiver une règle de lint (ni `noqa`, ni exclusion de règle ou de fichier) pour passer.
- Suivre par git un média, un dossier `videos/` ou un fichier de `video-content`.
- Installer un outil sans empreinte vérifiée, ou ailleurs que sous `VF_TOOLS`.
- `git push --force`, commit de secrets (`.env`, jetons, clés).
