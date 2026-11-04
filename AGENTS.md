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

`pipeline/video_factory/` (le paquet de `vf` et ses dix étapes), `toolchain/` (les outils figés et le `Dockerfile.render`), `schemas/` (les contrats publiés : état, script, voies), `mask/routes.json` (les voies de tournage), `templates/` (le gabarit du script et la composition provisoire), `scripts/` (le contrôle « Aucun contenu »), `tests/`.

Carte du dépôt : [docs/map/AGENTS.md](docs/map/AGENTS.md).

## Règles

- Aucun contenu de vidéo ici : ni script, ni prise, ni rendu, ni état. Les scripts et les états vont dans `code-my-life/video-content` (privé), les médias dans le magasin local (`VF_MEDIA`, `~/studio/media` par défaut, sur le disque de WSL). Une fixture de test est synthétique et petite : sous `tests/fixtures/`, 256 Kio au plus.
- Tout outil externe passe par `toolchain/tools.lock.json` : version exacte, empreinte SHA-256 calculée sur le fichier téléchargé (jamais recopiée d'ailleurs), adresse de téléchargement, commande d'installation. `vf doctor --install` vérifie l'empreinte avant tout usage et installe sous `VF_TOOLS`, hors du dépôt. Une montée de version se fait par PR, avec ses nouvelles empreintes (RUNBOOK, « Monter un outil de version »).
- HyperFrames ne tourne qu'avec l'environnement de son entrée du lock : télémétrie, vérification et installation des mises à jour, skills et installations à la demande coupées. Jamais `npx hyperframes`, jamais le CLI lancé sans cet environnement : il se mettrait à jour tout seul. Le rendu se fait dans l'image figée `hyperframes-render`, lancée par `compose` avec `--network none` ; jamais `hyperframes render --docker`.
- Déterminisme : aucun visuel ne dépend d'autre chose que du numéro d'image (ni minuterie, ni `Date`, ni hasard sans graine, ni GSAP) ; un encodeur a son nombre de fils fixé et les drapeaux `bitexact`. Une étape inscrit dans `state.json` tout ce qui fait son résultat : changer un paramètre, un outil ou le code d'une étape la rend périmée.
- Aucune image du visage ne sort : les rapports de `scan` et de `qc` ne donnent que des numéros d'image, des temps et des scores.
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
