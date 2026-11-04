# Le tournage

Une prise est un enregistrement de l'écran de l'iPhone 16 Pro pendant qu'AR Quick Look pose le casque du robot sur la tête, avec la voix au micro. Cette voie a été retenue par le test du 4 novembre 2026 (#3) : le déclencheur de Quick Look enregistre sans son, l'enregistrement d'écran garde la voix.

## Réglages de l'iPhone, une fois

- **L'enregistrement d'écran dans le Centre de contrôle** : appui long dans le Centre de contrôle, puis « Ajouter une commande », puis « Enregistrement de l'écran ».
- **Le micro de l'enregistrement d'écran** : dans le Centre de contrôle, appui long sur le bouton d'enregistrement, puis « Micro » activé. Le réglage reste d'une prise à l'autre.
- **Un mode de concentration « Tournage »** (Réglages, puis Concentration) qui coupe toutes les notifications : une notification apparaîtrait dans la prise.
- **Le fichier du casque** (`helmet-face.usdz`) enregistré dans l'app Fichiers, sous « Sur mon iPhone ».

## Avant chaque prise

1. Active le mode « Tournage ».
2. Ouvre le casque depuis Fichiers : AR Quick Look démarre la caméra avant et pose le casque sur ta tête.
3. Vérifie le casque, de face puis tête tournée à gauche et à droite : il couvre la tête, les cheveux et les oreilles.
4. Ouvre le Centre de contrôle et lance l'enregistrement d'écran : il démarre après trois secondes.
5. Dis tout le script, phrase par phrase.
6. Arrête l'enregistrement par la pastille rouge en haut de l'écran.

Le haut et le bas de l'écran (la pastille, les boutons de Quick Look) sont retirés par `vf ingest`, qui recadre la prise en 9:16. L'image de l'enregistrement est en miroir : `vf ingest` la remet à l'endroit.

## Le cadrage

- **Plan poitrine ou gros plan**, le téléphone à bout de bras, à hauteur des yeux.
- **La tête dans le tiers haut de l'écran** : le bas de l'image reçoit les sous-titres.
- **Une lumière de face**, douce : le suivi du visage d'ARKit décroche dans le contre-jour.

## Les règles d'anonymat, et leur raison

- **Rien de reconnaissable derrière toi.** Le fond est flouté par la chaîne, mais un flou n'efface pas toujours un objet, une affiche ou une fenêtre.
- **Aucun reflet** : ni lunettes, ni vitre, ni écran derrière toi. Un reflet peut montrer ton visage hors du casque.
- **Les mains sous le menton.** Une main passée devant le visage fait disparaître le casque (test du 4 novembre 2026) : le visage paraît.
- **Pas de rotation brusque de la tête.** Le suivi décroche, et le casque se décale ou disparaît.
- **Aucun nom, aucune adresse, aucun écran personnel** dans le champ.

La chaîne coupe toute image où son détecteur trouve un visage, mais ces règles évitent d'en perdre au montage.

## Une phrase ratée

Redis la phrase entière. Le dérush garde la dernière prise complète de chaque phrase, et retire les hésitations et les silences.

## Les captures d'écran pour les plans `[capture: …]`

Un script peut montrer un vrai écran, par exemple la démo de factory-live (https://code-my-life.github.io/factory-live/demo/). Chaque capture est un enregistrement d'écran de 5 à 8 s, **micro coupé**, de la démo plutôt que de l'outil réel : aucune donnée réelle n'apparaît.

## Envoyer la prise

1. Envoie la prise et les captures au PC avec LocalSend, dans `~/studio/inbox`.
2. Range-les dans la vidéo : `uv run vf ingest <id> <fichier>` pour la prise.

La prise ne quitte jamais le PC : elle va dans le magasin local des médias, jamais dans un dépôt.
