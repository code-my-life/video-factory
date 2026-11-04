# ADR 0001 : la chaîne du Monteur vidéo

Date : 2026-11-04. Statut : accepté (décisions du propriétaire, issue parapluie [#1](https://github.com/code-my-life/video-factory/issues/1)).

## Contexte

Code My Life n'a pas de chaîne vidéo. Il faut une chaîne qui fasse ses shorts, de la prise à la publication :

- **La prise** : un selfie tourné à l'iPhone 16 Pro, la tête couverte par le masque du robot, et la voix du propriétaire.
- **La monétisation** visée en premier : TikTok, avec Creator Rewards.
- **Les règles** : déterministe partout où c'est possible, aucun outil payant, un design system et des gabarits pour l'uniformité d'une vidéo à l'autre.
- **L'ordre** : d'abord une première vidéo publiée, ensuite le pilotage par un kanban Hermès et l'observation dans factory-live.

Claude Code fait le travail. La software factory ne fabrique pas ce dépôt.

## Décision

Les décisions du propriétaire, le 4 novembre 2026 :

- **Chaîne** : Code My Life. Aucun compte n'existe encore. Français d'abord, anglais ensuite.
- **Monétisation** : TikTok Creator Rewards (10 000 abonnés, 100 000 vues sur 30 jours, un compte personnel, des vidéos d'une minute ou plus). YouTube Shorts et Instagram Reels reçoivent les mêmes vidéos.
- **Prise** : sa voix, et un selfie face caméra en plan poitrine ou en gros plan. Le robot est un masque posé sur la tête au tournage, sur l'iPhone même, pas un personnage à part entière. Le fond reste réel, flouté.
- **Montage** : les plans face caméra font la moitié de la vidéo au plus, le reste est du motion design. Le master est en 2K vertical (1440x2560), livré tel quel à YouTube et à Instagram, et en 1080x1920 à TikTok.
- **Voix** : une légère couleur « casque », calculée en code.
- **Moteur de composition** : HyperFrames.
- **Masque** : une solution gratuite qui existe déjà, pour lui seul. La voie privilégiée est Reality Composer avec AR Quick Look, à valider d'abord par un test sur le téléphone ; une app iOS sur mesure seulement si rien ne convient ([#3](https://github.com/code-my-life/video-factory/issues/3)).
- **Publication** : la première vidéo à la main sur les trois plateformes, Postiz au lot P2.
- **Dépôts** : `video-factory`, public, ne contient jamais aucun contenu de vidéo ; les scripts et les états vont dans `video-content`, privé ; les médias restent dans un magasin local.
- **Pilotage** : un board « studio » dans le même Hermès, après la première vidéo.

La chaîne, dans l'ordre :

1. Script approuvé (`video-content`).
2. Tournage à l'iPhone, masque appliqué.
3. `vf ingest`.
4. `scan` (aucun visage).
5. `blur` (le fond).
6. `transcribe`.
7. `align`.
8. `cut`.
9. `voice` (couleur « casque », sonie).
10. `compose` (HyperFrames).
11. `master`.
12. `qc`.
13. Publication.

Chaque étape inscrit l'empreinte de ses entrées et de ses sorties dans l'état de la vidéo. Une étape non déterministe produit une entrée figée et hachée : le brouillon du LLM, la prise. Aucune image du visage ne peut sortir : un détecteur indépendant passe sur la prise et sur chaque image du master.

## Ce que l'étude a pris, laissé et adapté

- **Pris** :
  - chaque état visuel est une fonction pure du temps (ni minuterie, ni `Date`, ni `Math.random`), l'aléa a une graine, le rendu a un cache par tranches ;
  - le dérush d'une prise parlée (silences, vitesse), le lexique des hésitations et l'alignement forcé ;
  - un état par vidéo, vérifié contre les fichiers qui prouvent chaque étape ; cet état deviendra la carte du kanban ;
  - des barrières dures : pas d'export sans légende ni hors de la sonie, aucun mot gardé coupé, le contrôle final (format, durée, -14 LUFS, crête à -1 dBTP au plus) ;
  - les effets notés dans le script et calés sur le mot.
- **Laissé** : les outils payants, les polices de macOS, le détourage par Apple Vision, l'étalonnage par LUT, GSAP (sa licence a une clause d'usage interdit) et tout chargement depuis un CDN au rendu, la voix de synthèse, Pixabay.
- **Adapté** : le LLM ne réécrit pas la vidéo à chaque fois, il propose un brouillon de script, relu.

Les outils retenus :

- **HyperFrames** (Apache 2.0) : version figée, rendu dans son image Docker, télémétrie coupée, sans description d'images par Gemini ni skill « Pro » payante ; les animations passent par CSS, WAAPI ou un adaptateur `seekFrame`, sans GSAP.
- **FFmpeg** : un binaire figé, un master en H.264 High en BT.709, la sonie en deux passes, les drapeaux `bitexact`, une empreinte par image. Pas de NVENC pour le master.
- **whisper.cpp** : le transcrit et le calage des mots, sur CPU, à température 0 et sans repli, aligné sur le script.
- **Le robot** : « Rank 3 Police Unit » de nikvili, sous CC BY 4.0 sur Sketchfab ; seul le fichier de Sketchfab est pris (la page Gumroad de l'artiste interdit l'usage commercial du projet Blender complet). Crédit dans `CREDITS.md`.
- **Le masque à l'iPhone** : l'ancre « Face » de Reality Composer et d'AR Quick Look, gratuits et intégrés à iOS, avec le fichier ancré écrit par `usd-core` sur le PC ; le fond est flouté sur le PC.

## Conséquences

- Le dépôt public ne porte que le moteur. Un contrôle de la CI (« Aucun contenu ») refuse tout média et tout dossier `videos/` suivi par git ; les scripts et les états vivent dans `video-content`, les médias dans `~/studio/media` (`VF_MEDIA`), sur le disque de WSL, car le disque C: est plein à 99 %.
- Chaque outil externe est figé par sa version et son empreinte dans `toolchain/tools.lock.json`, vérifié par `vf doctor`. Toute montée de version passe par une PR ; pour HyperFrames, pré-1.0, avec les empreintes de rendu comparées.
- Repris de la software factory : l'identité de l'App `code-my-life-factory` pour les PR, le contrôle Conventions de code-my-life/.github avec les types d'issues et de PR, la carte ICM (code-my-life/hermes-software-factory#24) et le ruleset sur `main`. Au lot P2 : les voies de contrôle en code, la passerelle Telegram et la sonde de factory-live.
- Lots : P1 produit les vidéos (#2 à #5, le design system vidéo, la marque dans cv-site) ; P2 pilote et observe (#6 à #8, la vue du board dans factory-live) ; P3 étend (#9, #10, la version anglaise). Aucun fichier de hermes-software-factory ne change avant le lot P2.
- Risques suivis : la licence du robot (un mail à l'artiste est conseillé), la perte du suivi du masque quand la tête tourne vite (la barrière coupe ces images), HyperFrames qui change chaque jour, le seuil de YouTube pour les nouvelles chaînes à partir du 1er février 2027, et l'originalité exigée par YouTube (le gabarit n'est que le cadre de marque).
