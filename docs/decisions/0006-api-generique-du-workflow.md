# ADR 0006 : l'API générique du workflow, pour factory-live

Date : 2026-11-05. Statut : accepté. Issue [#21](https://github.com/code-my-life/video-factory/issues/21).

## Contexte

factory-live montre chaque workflow avec un seul graphe, celui de la ligne d'usine du code, tiré d'une **fiche de workflow** (code-my-life/factory-live#29, son contrat `WorkflowSheet`). Décisions du propriétaire du 2026-11-05 : la fiche vit dans le dépôt du workflow, et factory-live lit chaque workflow par une **API générique**, pour qu'un changement du studio ne demande aucune PR dans factory-live. La page du studio ne servait que du HTML, le master et le geste.

## Décisions

- **La fiche** est `hermes/workflow.json`, au format `WorkflowSheet` de factory-live : l'élément `video`, les huit stations du manifeste avec leur nature (Script en `ai`, les voies en code en `script`, les stations du propriétaire en `owner`, Publiée en `end`), leur case dans une grille de 4 colonnes, les liens de la ligne, les retours « refaire » (Approbation vers Script, Revue vers Montage) et le fournisseur de Script. L'API la vérifie par les mêmes règles que factory-live avant de la servir ; un test la tient d'accord avec le manifeste.
- **L'API, version 1**, servie par `vf studio serve` (127.0.0.1:8448), en JSON, chaque réponse avec `"api": 1` :
  - `GET /api/workflow` : la fiche ;
  - `GET /api/items` : une entrée par carte d'une vidéo, ouverte ou publiée : `id`, `card`, `title` (celui du script), `station`, `state` (`running`, `waiting`, `failed`, `done`), `since`, `waits`, `failure` ;
  - `GET /api/items/<id>` : la même entrée, plus le script, les étapes de `vf run` (nom, durée, empreinte de chaque sortie) et les fichiers typés : `video` (le master et l'export TikTok, par la route `/v/<id>/media/<nom>` déjà servie en plages d'octets, à 30 images par seconde) et `words` ;
  - `GET /api/items/<id>/words` : les mots du master, `[{mot, debut, fin, garde}]` en secondes, dans le temps du master ;
  - `POST /api/items/<id>/gesture` (`decision` : `ok` ou `refaire`, `note`) : le même déblocage que la page et Telegram.
- **Les mots calés** sont ceux des sous-titres du master : le plan de `compose` les donne en images, dans le temps de sortie, à partir de la liste de `cut` (l'étape `align` les a calés sur la prise, `cut` les a portés dans le temps du montage). `garde` dit si le mot vient du script.
- Une carte en échec se reconnaît à la raison de son parcage (« … en échec : … », ADR 0004).

## Conséquences

- factory-live (#31 de son dépôt) ne lit ni le magasin ni `state.json` : un changement de leur forme ne touche que cette API.
- Un changement de la fiche (station, nature, case) se fait ici, sans PR dans factory-live.
- La page, le board et la chaîne ne changent pas.
