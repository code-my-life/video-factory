# ADR 0004 : le board Hermès « studio »

Date : 2026-11-04. Statut : accepté. Issue [#7](https://github.com/code-my-life/video-factory/issues/7).

## Contexte

La chaîne tourne par commandes, et rien ne prévient le propriétaire quand une vidéo l'attend. La software factory pilote déjà son travail sur un board Hermès, avec des voies de contrôle en code (ADR 0015 de hermes-software-factory) et la passerelle Telegram. Le dépôt de la factory ne doit pas changer pour autant, ni ses profils, plugins, crons et board, ni `~/.hermes/config.yaml`.

## Décisions

- **Un board « studio » dans le même Hermès**, déclaré par `hermes/manifest.json` et installé par `hermes/install.sh` (idempotent, `--uninstall` retire tout) : le board, le profil `studio-writer`, le service utilisateur `video-factory-studio.service` et la page sur le tailnet. Rien d'autre n'est écrit dans `~/.hermes`.
- **Une carte par vidéo, sa station est son assigné** : `studio-idee`, `studio-script`, `studio-approbation`, `studio-tournage`, `studio-montage`, `studio-revue`, `studio-publication` ; Publiée est la carte terminée. Aucun de ces noms n'est un profil : le dispatcher ne lance jamais rien sur une carte du studio, il la saute (`skipped_nonspawnable`). Le titre `<id> : <idée>` lie la carte à `videos/<id>/` de `video-content`.
- **La carte suit son `state.json`** : une vidéo qui existe entre au board à la station que son état prouve (qc passé : Revue ; prises versées : Montage ; script écrit : Approbation), et une carte en Tournage passe en Montage dès que l'état a ses prises, qu'elles viennent de la page ou de `vf ingest`.
- **Une carte n'est `running` que pendant le brouillon.** Une station qui attend le propriétaire, ou une voie en échec, met la carte en `scheduled` ; une voie en code travaille sur une carte `ready`, sans la réclamer. Ainsi une carte du studio n'occupe pas une des places de `kanban.max_in_progress` (un plafond de la machine, commun aux boards), et vram-release décharge le modèle local pendant un rendu. `blocked` n'est pas utilisé : factory-notify publierait un message de la factory pour chaque blocage, et deux blocages de même nature de suite envoient une carte en triage.
- **Un seul geste du propriétaire par station : débloquer la carte.** Sur Telegram, `/kanban --board studio unblock <carte>` ; sur la page, un bouton qui fait le même appel. Une raison qui commence par « refaire » renvoie la vidéo à la station d'avant (Script depuis Approbation, Montage depuis Revue), et la demande suit la carte. En Tournage, le geste est l'envoi des prises.
- **Aucun modèle dans une voie en code ni dans une barrière.** Idée lance `vf new`, Montage `vf run`, Publication `vf publish` ; la décision de chaque passe est une fonction pure (`studio/stations.py`), testée. Seule la station Script appelle un modèle : le service lance `hermes -p studio-writer chat --oneshot`, sans outil, réclame la carte pendant ce temps, puis garde le brouillon seulement s'il passe les règles en code : le schéma du script et son id, le lecteur de script de `align` et `compose`, 140 à 190 mots dits, aucun tiret cadratin.
- **`studio-writer` n'est pas lancé par le dispatcher** : `kanban.dispatch_profiles` (dans `~/.hermes/config.yaml`, réécrit par l'install de la factory) ne le nomme pas, et ce fichier n'est pas à video-factory. Le service lance donc le profil lui-même, une fois par brouillon.
- **Les messages passent par l'expéditeur de la passerelle** (`hermes send -t telegram:<TELEGRAM_CHAT_ID>`), à chaque station qui attend le propriétaire et à chaque échec d'une voie : la vidéo, ce qu'il y a à faire, la page de la vidéo et la commande qui répond.
- **La page des prises** est servie par `vf studio serve` sur 127.0.0.1 et publiée sur le tailnet seulement, en HTTPS, par `tailscale serve` (jamais Funnel), comme les autres services. Safari calcule l'empreinte SHA-256 de chaque prise sur le téléphone, par tranches (`templates/studio/sha256.js`), puis l'envoie avec elle ; le serveur la recalcule à la réception et refuse une prise différente. Une fois toutes les prises reçues, il lance `vf ingest`, puis fait passer la carte en Montage. Un bot Telegram ne télécharge pas plus de 20 Mo, une prise en pèse des centaines.
- **La publication reste à la main** : `vf publish <id>` vérifie que le master passe qc et range dans `VF_MEDIA/publication/<id>/` l'export TikTok, le master et la légende (le titre du script, puis le crédit du robot ; les mots-clés s'ajoutent à la publication). La page les donne au téléphone. Le geste « Publiée » termine la carte, avec le lien de la vidéo s'il est donné.
- **Aucun fichier comme canal** : le service ne parle à Hermès que par sa CLI (`hermes kanban --board studio …`, `hermes send`, `hermes -p studio-writer`), et lit sa sortie JSON, jamais sa base.

## Conséquences

- Le board « factory » ne change pas ; la preuve de la PR compare ses fichiers, ses profils, ses crons et sa configuration avant et après l'installation.
- Une carte créée par `/kanban create` sans `--assignee` prend l'assigné par défaut de la machine (`coordinator`), et la factory la traiterait : une vidéo s'ouvre par la page ou par `vf studio carte`.
- Les captures d'écran (`[capture: …]`) se versent encore par `vf ingest --capture` ; la page ne reçoit que les prises.
- La vue du board dans factory-live reste à faire, après sa maquette (#1).
