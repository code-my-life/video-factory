# ADR 0007 : la vitrine dans la chaîne

Date : 2026-11-06. Statut : accepté. Issue [#28](https://github.com/code-my-life/video-factory/issues/28), critère C2 de [#1](https://github.com/code-my-life/video-factory/issues/1).

## Contexte

La vidéo 1 (« Ma factory code pendant que je vis ») a été montée le 5 novembre 2026 par quatre scripts écrits à la main, hors de la chaîne. Leurs réglages étaient des constantes : les instants de la voix, les plans, les corrections des mots mal entendus, les textes du bandeau et de l'écran de fin. #28 demande que la vidéo 1 se refasse par `vf run`, que la vidéo 2 se fasse de la même façon, et que chaque vidéo passe par le board « studio ».

## Décisions

- **Un genre de script, « vitrine »** (`genre: vitrine` dans l'en-tête). Chaque ligne est une réplique de la voix, placée sur ses plans par ses annotations : `[plan: …]`, `[jumeaux: …]`, `[suite: …]`, `[fin: …]`, `[appel: …]`, `[ton: …]`. L'en-tête porte les réglages de la vidéo : thème, bandeau, vignette, icône, écran de fin, légende, mots-clés, outil de la voix. Ce sont des choix révisables de chaque vidéo, jamais des constantes de la chaîne.
- **La voix est un fichier**, généré ou enregistré, rangé par `vf ingest --voix`. `transcribe` et `align` la calent comme une prise. L'alignement apprend à joindre les morceaux d'un mot (« Factory » « Live » pour « factory-live »). Il donne à chaque mot du script son instant, sous sa forme écrite.
- **Les étapes gardent leurs noms**. Une vitrine prend sa branche dans trois d'entre elles :
  - `cut` fait sa liste de décisions ;
  - `voice` place sa voix réplique par réplique ;
  - `compose` écrit et rend le projet de son thème.
  `master` et `qc` sont ceux de toute vidéo.
- **Les règles du montage sont du code, enregistré comme paramètres des étapes** :
  - la voix d'une réplique va d'un silence de `transcribe` au suivant, avec 60 ms avant et 120 ms après ;
  - les sous-titres vont par trois mots au plus, fermés après une ponctuation ou avant une pause de plus de 0,35 s ;
  - un mot de trois lettres au plus attend le suivant, et une réplique de quatre mots au plus reste entière.
  Elles sont écrites d'après le montage à la main de la vidéo 1, et le redonnent : les mêmes 51 groupes de sous-titres, les mêmes instants, la même page.
- **Les thèmes** sont des dossiers de `templates/hyperframes/themes/` : la page, la vignette, les icônes et les polices. `primer` (Primer et Mona Sans, l'apparence de factory-live) est celui de la vidéo 1.
- **La zone sûre vaut pour tout le texte d'une vitrine.** Refait par la chaîne, le bandeau de la vidéo 1 passait d'environ 80 px sous les boutons de TikTok pendant 2,4 s, et les lignes de l'écran de fin y entraient 4 images. Le 2026-11-06, le propriétaire a choisi de corriger le thème plutôt que d'en exempter le contrôle :
  - le bandeau est centré sur la zone sûre, son texte sur deux lignes au besoin ;
  - les lignes de l'écran de fin arrivent par le bas.
  La vidéo 1 change sur ces seuls passages, que le propriétaire revalide.
- **La publication** range la vignette, rendue par le Chromium figé. La légende dit que la voix est générée par IA quand le script nomme l'outil, et `vf publish` rappelle l'étiquette IA de chaque plateforme.
- **Le board** :
  - une vitrine est tournée quand sa voix et toutes les captures de son script sont rangées ;
  - la page des prises reçoit la voix (le fichier audio) et les rushs, chacun rangé sous le nom de son fichier.
- **L'API du studio reste en version 1.** Les mots du master viennent du plan de `compose`, comme pour une vidéo face caméra. La vignette reste hors de `files` (#29).

## Conséquences

- La vidéo 2 se fait sans code : un script, une voix, des captures.
- Changer une règle du montage ou un thème refait le montage des vitrines concernées : leur empreinte de code change.
- Pas de musique sous une vitrine pour l'instant : une piste muette en tient lieu.
- Une seule paire de jumeaux par vidéo.
