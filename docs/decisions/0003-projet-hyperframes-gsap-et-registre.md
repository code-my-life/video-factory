# ADR 0003 : un vrai projet HyperFrames, GSAP livré, le registre et les skills

Date : 2026-11-04. Statut : accepté ; le style des gabarits reste provisoire. Issue [#14](https://github.com/code-my-life/video-factory/issues/14). Remplace, dans l'[ADR 0002](0002-chaine-de-derush-et-de-rendu.md), le rendu « sans GSAP » et la page unique de `compose`.

## Contexte

HyperFrames est bâti sur GSAP : chaque scène y est une timeline GSAP en pause, enregistrée dans `window.__timelines`, et la plupart des blocs du registre chargent GSAP. La chaîne de #4 l'avait écarté, et `compose` écrivait une seule page animée par son propre script : ni scènes, ni piste de sous-titres, ni `check`, ni registre. Le rendu de HyperFrames, lui, va chercher sur jsDelivr un GSAP qu'il ne trouve pas dans le projet, alors que `compose` rend sans réseau.

## Décisions

- **GSAP est autorisé**, la clause de sa licence n'interdisant que de bâtir un outil concurrent de Webflow. La copie que HyperFrames 0.9.12 embarque (GSAP 3.15.0 avec CustomEase et MotionPathPlugin) est une entrée du lock, de type `library` : l'archive npm de HyperFrames vérifiée par son empreinte, puis chaque fichier vérifié à son tour. `vf doctor` contrôle chaque copie installée. `compose` la copie dans `assets/lib/gsap/` de chaque projet, et la racine la charge par un chemin local : le compilateur de HyperFrames ne réécrit vers jsDelivr qu'un GSAP introuvable, il n'y a donc plus rien à réécrire.
- **Les autres bibliothèques** suivent le protocole de HyperFrames et la même livraison : lottie-web 5.13.0, @lottiefiles/dotlottie-web 0.81.0 (module et WASM), anime.js 4.5.0, Three.js 0.186.1, chacune en entrée `library` du lock, copiée par `compose` seulement si une page charge `assets/lib/<nom>/`. CSS, WAAPI et canvas ne demandent rien. Une bibliothèque hors du lock arrête `compose`.
- **`compose` écrit un vrai projet** : `index.html`, seule racine (1440x2560, 30 images par seconde, la durée du montage), qui monte la prise dans un conteneur que les zooms agrandissent, une scène par plan (`compositions/shot-<n>.html`, une timeline en pause enregistrée sous son id) et une seule piste de sous-titres (`compositions/captions.html`, des groupes de trois mots au plus, un seul visible à la fois). La passe texte de `qc` garde sa racine hors du projet (`texte.html`, montée sur `index.html` au rendu) : un projet n'a qu'une racine, `check` le refuse sinon.
- **Aucune adresse hors du projet** : `compose` refuse une adresse de CDN ou de police en ligne, un `src`, un `href` ou un `url()` absolu, un fichier absent ; un test le contrôle.
- **`hyperframes check --json` passe avant tout rendu**, dans l'image figée et sans réseau ; une erreur arrête `compose` et la nomme. Les avertissements sont relevés dans `state.json`.
- **Le registre** : les éléments sont installés par `hyperframes add` au développement seulement (il demande le réseau), dans `templates/hyperframes/`, depuis le registre figé au tag v0.9.12 (celui du CLI figé). Le fichier installé est commité tel quel, puis restylé dans un second commit ; `hyperframes.lock.json` garde l'empreinte d'origine. Trois éléments servent : `mk-specs-list` (plans `etapes`), `mk-progress-stat` (plans `stat`) et `caption-highlight` (sous-titres). Les plans `code` et `capture` sont écrits à la main.
- **Le style reste provisoire et sobre** : une police (Inter Bold), du blanc sur noir, un voile sombre sous les sous-titres, aucune couleur de marque inventée. Le style définitif viendra du design system vidéo.
- **Les skills** : `motion-doctrine`, `captions-overlay`, `seam-craft` et `cut-the-curve` sont copiés du dépôt de HyperFrames au commit 2679bcd (Apache 2.0, licence et origine dans chaque dossier, tirets cadratins remplacés) ; le skill `video-factory` dit comment passer d'un script annoté aux scènes, les zones sûres, le rendu sans réseau, la livraison des bibliothèques et l'ajout d'un élément du registre. Les chemins de HeyGen de `media-use` (payants) n'en font pas partie.

## Conséquences

- Le déterminisme tient : les animations sont des timelines en pause, cherchées par HyperFrames image par image ; deux rendus des mêmes entrées donnent les mêmes empreintes `framemd5` du master.
- L'image de rendu ne change pas : les bibliothèques vivent dans le projet, pas dans l'image.
- Une montée de HyperFrames emporte celle de GSAP (l'entrée `gsap` pointe sur la même archive) et demande de revoir les éléments du registre au nouveau tag.
- Les étapes avant `compose`, `master` et `qc` ne changent pas.
