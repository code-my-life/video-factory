# ADR 0002 : la chaîne de dérush et de rendu

Date : 2026-11-04. Statut : accepté pour la mécanique ; le gabarit visuel est provisoire. Issue [#4](https://github.com/code-my-life/video-factory/issues/4).

## Contexte

Une prise tournée à l'iPhone, masque appliqué, doit donner par `vf run` un master 2K vertical et son export TikTok, conformes aux plateformes, sans aucune image du visage, et refaits à l'image près avec les mêmes entrées. Le design system vidéo n'est pas encore décidé : il viendra d'une issue Interface, après des maquettes validées par le propriétaire.

## Décisions

### L'état et les étapes

- Dix étapes : `ingest`, `scan`, `blur`, `transcribe`, `align`, `cut`, `voice`, `compose`, `master`, `qc`. Chacune inscrit dans `state.json` l'empreinte de chaque entrée, chaque sortie (rangée dans le magasin des médias sous `<empreinte>.<extension>`), la version de ses outils (ceux du lock, video-factory, les paquets Python), ses paramètres, l'empreinte des sources qui font son résultat, ses dates et sa durée.
- `schemas/state.schema.json` passe en version 2 (les sorties deviennent des références au magasin ; les prises, la voie et les captures entrent dans l'état). Un état de version 1 sans étape se relit et se réécrit en version 2 ; aucun n'en avait.
- Une étape est périmée quand une entrée, un paramètre, un outil ou son code a changé, ou qu'une sortie manque au magasin ; celles qui viennent après attendent. `vf run` refait les étapes périmées, puis celles qui en dépendent seulement si leurs propres entrées changent : une sortie identique arrête la cascade.

### Les modèles de MediaPipe, sur LiteRT

Le paquet `mediapipe` 1.x exige `libGLESv2.so.2` même sur CPU, absent de la machine et non installable sans droits d'administrateur. Les deux modèles figés (BlazeFace courte portée, Selfie Segmenter) tournent donc sur LiteRT (`ai-edge-litert` 2.3.0, Apache 2.0), le moteur que MediaPipe embarque, sur un seul fil d'exécution. Les pré- et post-traitements de MediaPipe sont réécrits et recoupés avec `mediapipe` 1.1.1, lancé une fois dans un conteneur jetable sur les images de test publiques de MediaPipe : les scores du détecteur sont ceux de MediaPipe à 0,01 près, les masques à 0,004 près en moyenne.

### Chaque étape

- `ingest` : la voie de tournage se lit dans `mask/routes.json` (son schéma : `schemas/routes.schema.json`). La voie `quicklook-screen` (1206x2622, en miroir) garde une zone 9:16 de 1206x2144, centrée à un pixel près (une coupe commence sur une ligne paire), marquée provisoire jusqu'à sa vérification contre les boutons de Quick Look sur une vraie prise (#3). Puis 30 images par seconde constantes, le son à 48 kHz, les couleurs en BT.709 SDR : un autre gamut (Display P3) est converti, HLG et PQ passent par un mappage de tons figé (Hable, crête nominale 100). Aucune métadonnée : seules les pistes vidéo et son passent, sans métadonnées ni chapitres, sans nom d'encodeur.
- `scan` : chaque image est lue en 144x256 et regardée par trois fenêtres (l'image entière en carré, son carré du haut, son carré du bas). Le seuil, 0,5, est provisoire et écrit à un seul endroit (`faces.THRESHOLD`) : son calibrage sur des prises étiquetées appartient à #3. Le rapport ne donne que des numéros d'image, des temps et des scores.
- `blur` : le masque de la personne (256x256, sans perte), un flou gaussien de sigma 18, la personne reposée par-dessus ; le résultat est encodé sans perte, pour que la personne ne perde rien à un second encodage.
- `transcribe` : whisper.cpp figé, `-l fr`, température 0 sans repli, faisceau 5, 8 fils, DTW `large.v3.turbo` (attention flash coupée, que DTW ne supporte pas), et une consigne fixe pleine d'hésitations, sans laquelle Whisper les efface. Un mot finit où DTW place la fin de son dernier jeton ; les pauses viennent du son (détection de silence de FFmpeg).
- `align` : programmation dynamique avec, en plus des correspondances, insertions et suppressions, la reprise (revenir dans la phrase en cours ou la précédente) et l'abandon d'une phrase. Le chemin le moins coûteux découpe la prise en tentatives ; la dernière tentative complète de chaque phrase est gardée. Le lexique des hésitations est dans `align.FILLERS`.
- `cut` : la liste de décision est sur la grille des échantillons à 48 kHz ; la vidéo montre, à chaque image, l'image source à l'écran à cet instant. Les silences de plus de 400 ms sont ramenés à 150 ms, les hésitations et les reprises retirées entières, les plages de `scan` retirées, ce qui précède le premier mot gardé et suit le dernier écarté. Les mots hors script restent, et sont listés. Toute coupe dans un mot gardé fait échouer l'étape, avec le mot et les images.
- `voice` : coupes avec des fondus de 4 ms, débruitage, égalisation, compression, la couleur « casque » (bande limitée, légère saturation, courte résonance), puis la sonie en deux passes à -14 LUFS et -2 dBTP.
- `compose` : HyperFrames 0.9.12, rendu en PNG dans son image figée, lancée par `vf` avec `docker run --network none`, l'utilisateur courant, et la télémétrie, la vérification et l'installation des mises à jour coupées. Rien de lourd ne s'écrit dans le conteneur : ses fichiers temporaires et les images extraites de la vidéo vont sur le disque de WSL (un dossier du magasin monté, `--frames-cache-dir off`), car le disque des conteneurs est celui de Docker Desktop, sur le disque C: déjà plein. Les animations ne dépendent que du numéro d'image (événement `hf-seek`), sans GSAP. Une seconde passe ne rend que le texte, blanc sur noir : la boîte de tout ce qui est écrit, image par image, est ce que `qc` tient à la zone sûre. Le fond musical est synthétisé en code, à graine fixe.
- `master` : depuis les PNG, H.264 High en BT.709, 30 images par seconde, AAC 48 kHz, drapeaux `bitexact`, sans métadonnées, sans le SEI de x264, en `faststart`, avec les `framemd5`. L'export TikTok part des mêmes PNG. La voix est posée à -3 dB sur chaque canal : deux canaux égaux se mesurent 3 LU plus fort selon ITU-R BS.1770.
- `qc` : durée, sonie et crête vraie, format de chaque fichier, zone sûre (15 % en haut, 35 % en bas, 6 % à gauche, 17,8 % à droite), plans face caméra à la moitié au plus, aucun visage sur aucune image du master, chaque échec nommant sa borne.

### Les plans et les captures

- Une annotation de plan en fin de ligne couvre toute la phrase ; à l'intérieur d'une ligne, le plan commence au mot qui la précède. Il dure jusqu'au début de la phrase suivante ou du plan suivant. Les parties d'un `[stat: …]` et les étapes d'un `[etapes: …]` se séparent par `|`.
- `[capture: <nom>]` montre une capture d'écran (PNG) ou un court extrait muet (MP4) versé par `vf ingest <id> --capture <nom> <fichier>`, nettoyé de ses métadonnées et rangé dans le magasin. Une capture fixe reçoit un lent zoom calculé à l'image ; un extrait est tenu sur sa dernière image ou coupé à la durée de son plan. Un plan de capture compte comme motion design pour la règle de la moitié. Une capture absente fait échouer `compose`, qui la nomme.

### La durée

Décision du propriétaire du 4 novembre 2026 : chaque vidéo dure de 61 à 65 s, à peine plus d'une minute, le seuil de TikTok Creator Rewards (l'issue disait de 61 à 90 s). Les deux bornes sont écrites une seule fois, dans `schemas/script.schema.json` (`duree_visee`), et `qc` les y lit.

### Le gabarit provisoire

Le rendu suit un gabarit volontairement neutre (`templates/composition/`) : une seule police, Inter Bold (OFL, licence à côté du fichier), du texte blanc, des plans sur fond noir, les sous-titres un mot à la fois en bas de la zone sûre, et aucune autre décision de style que la lisibilité et les zones sûres. Il sera remplacé par le design system vidéo.

### L'image de rendu

HyperFrames ne publie pas d'image : `toolchain/hyperframes/Dockerfile.render` en fige chaque couche (la base par son digest, les paquets Debian de snapshot.debian.org au 27 octobre 2026, chrome-headless-shell 152.0.7977.30, FFmpeg n8.0.1 de BtbN, HyperFrames depuis le même `package-lock.json` que l'installation de la machine). La construction est reproductible (`SOURCE_DATE_EPOCH`, horodatages réécrits, sans attestation) : deux constructions sans cache donnent le même digest, inscrit dans le lock et vérifié par `vf doctor`.

## Conséquences

- Les sorties s'accumulent dans le magasin des médias : rien ne s'y efface seul, et les images de `compose` y prennent plusieurs gigaoctets par rendu.
- Les tests qui font tourner FFmpeg et les modèles le font avec les outils figés ; la CI les installe. whisper.cpp et l'image de rendu ne tournent que sur la machine : deux rendus complets s'y comparent par `vf run <id> --refaire compose master`.
- Restent à trancher ailleurs : le calibrage du seuil de visage et la vérification du recadrage sur une vraie prise (#3), le design system vidéo (son issue), la vitesse de la chaîne sur une vraie prise (#4, critère C7).
