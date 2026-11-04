# Crédits

Le robot dont le masque couvre la tête dans les vidéos :

- "Rank 3 Police Unit" de nikvili (Sketchfab), CC BY 4.0, modifié
  - Modèle : https://sketchfab.com/3d-models/rank-3-police-unit-d7698f6a7acf49c68ff0a50c5a1b1d52
  - Licence : https://creativecommons.org/licenses/by/4.0/

La police du gabarit provisoire de `compose` :

- Inter Bold, de The Inter Project Authors (Rasmus Andersson), SIL Open Font License 1.1, non modifiée
  - Source : https://github.com/rsms/inter, version 4.1
  - Licence : `templates/hyperframes/assets/fonts/OFL.txt`

Les blocs et composants du registre HyperFrames, restylés pour le gabarit provisoire de `compose` :

- `mk-specs-list`, `mk-progress-stat` (blocs) et `caption-highlight` (composant), de HeyGen, Inc. (HyperFrames), Apache 2.0, modifiés
  - Source : https://github.com/heygen-com/hyperframes, registre au tag v0.9.12 (commit 1ff4cefd40c8dad98127fc78e8761c1ac62053dd) ; empreintes des fichiers d'origine dans `templates/hyperframes/hyperframes.lock.json`
  - Licence : https://www.apache.org/licenses/LICENSE-2.0

Les skills internes de HyperFrames copiés dans `.claude/skills/` (`motion-doctrine`, `captions-overlay`, `seam-craft`, `cut-the-curve`) :

- de HeyGen, Inc., Apache 2.0, au commit 2679bcdee71aa0b1d706fd845f399fa07fc2c48f ; seuls les tirets cadratins sont remplacés ; licence et origine dans chaque dossier (`LICENSE`, `ORIGIN.md`)

Les bibliothèques que `compose` copie dans un projet (jamais dans ce dépôt : installées sous `VF_TOOLS` par `vf doctor --install`) :

- GSAP 3.15.0 (la copie qu'embarque HyperFrames 0.9.12), GreenSock, licence standard sans frais : https://gsap.com/standard-license
- lottie-web 5.13.0, @lottiefiles/dotlottie-web 0.81.0, anime.js 4.5.0, Three.js 0.186.1 : MIT, leur licence copiée avec elles
