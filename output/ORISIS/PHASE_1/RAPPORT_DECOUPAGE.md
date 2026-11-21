# OSIRIS – Rapport de découpage (Phase 1)

## Livrables
| Fichier | Contenu |
|---|---|
| `OSIRIS_DECOUPAGE_VALIDATION.mp4` | Montage de validation, 2 min 24 s (144,4 s), 1080×1920 (9:16), 30 i/s, H.264 CRF 18, AAC 48 kHz stéréo 192 kb/s, piste de sous-titres FR intégrée (désactivable) |
| `OSIRIS_DECOUPAGE.srt` | Sous-titres recalés sur le montage (94 répliques) |
| `edl.json` | Liste de montage (points d'entrée/sortie par rush), réutilisée en Phase 2 |

Aucun motion design, aucune incrustation graphique. Les rushes originaux n'ont pas été modifiés.

## Sources vérifiées
- 7 rushes H.264 720×1280, 30 i/s, AAC mono 44,1 kHz – 168,8 s au total. Tous lisibles (décodés par FFprobe et FFmpeg).
- La numérotation ne comprend pas de « O5 », mais le texte reste continu : rien ne manque dans la narration.
- La transcription PDF et le SRT fournis ont servi de texte de référence. Le bandeau « TurboScribe » a été retiré.

## Analyse
Les rushes ont été transcrits mot à mot (Whisper, horodatage par mot) et confrontés au texte de référence. Chaque rush correspond à une seule prise continue : il n'y a pas de doublon ni de prise alternative à départager. La sélection porte donc sur le nettoyage des débuts et fins de chaque rush, le resserrement des hésitations et la qualité des raccords.

## Ordre narratif retenu
| # | Rush | Contenu | Entrée → sortie (s) | Coupes internes |
|---|---|---|---|---|
| 1 | Osiris intro | Accroche « Jésus s'appelait Issa… » | 1,78 → 13,83 | — |
| 2 | Osiris 1 | Mythe d'Osiris, Seth, Isis, Anubis, Horus | 1,58 → 45,25 | 34,28–34,55 · 41,55–42,40 · 43,60–43,80 (hésitations) |
| 3 | O2 | Pharaon vivant = Horus, pharaon mort = Osiris | 1,76 → 17,83 | 12,35–12,88 (blanc « passer … par ») |
| 4 | O3 | Culte : pain, bière/vin, « corps et sang » | 1,99 → 22,41 | 10,95–11,15 · 14,65–15,08 |
| 5 | O4 | Qui était Issa ? | 2,08 → 12,82 | — |
| 6 | O6 | Parallèles avec Jésus, puis mise en garde | 1,77 → 26,42 | 15,48–15,85 · 17,30–17,85 |
| 7 | O fin | Démenti et conclusion | 1,43 → 21,80 | 19,78–20,00 |

Au total, 24,4 s ont été retirées : environ 1,5 à 2 s de silence en tête et 1 à 2 s en queue de chaque rush, plus 10 blancs ou hésitations au milieu des phrases.

## Choix de montage
- **Rythme** : 0,15 s de respiration avant la première syllabe et 0,25 à 0,4 s après la dernière. On obtient environ 0,4 s entre deux phrases et un rythme soutenu adapté au format vertical. Les pauses expressives ont été conservées : les pauses de ponctuation sous 0,5 s et la pause qui précède « Mais ne vous fâchez pas », réduite à 0,5 s.
- **Raccords image** : le cadre est identique d'un rush à l'autre. Chaque coupe interne alterne entre plan normal et léger recadrage serré à 110 %, ce qui masque le jump cut. Il s'agit d'un recadrage fixe, pas d'une animation.
- **Raccords son** : fondu de 20 ms en entrée et de 30 ms en sortie à chaque coupe (pas de clic), filtre passe-haut à 80 Hz, compression douce (2,5:1) et normalisation à -14 LUFS (mesure finale : -14,6 LUFS intégrés, LRA 2,8 LU).
- **Sous-titres** : le texte vient du SRT fourni (orthographe corrigée par rapport à la reconnaissance automatique : « Seth », « Horus », « féconder »…). Les sous-titres sont recalés au mot près sur le montage et découpés en lignes de 26 à 32 caractères maximum, coupées sur la ponctuation ou les pauses.

## Contrôles effectués
- Décodage intégral sans erreur. Les pistes vidéo et audio durent toutes les deux 144,4 s (synchronisation OK).
- Contrôle visuel des images de part et d'autre des 15 coupes.
- Transcription du montage final comparée au texte de référence : 87,5 % de correspondance mot à mot. Les écarts viennent uniquement de la reconnaissance automatique (noms propres) ; il n'y a aucune phrase manquante.

## À noter pour la validation
- Une articulation un peu rapide sur « se faire féconder » (rush Osiris 1, ~44 s du montage) : c'est la seule prise disponible.
- La légère différence de lumière entre les rushes (tournés à des moments différents) sera harmonisée à l'étalonnage en Phase 2.
