# OSIRIS – Phase 2 : motion design

## Livrables
| Fichier | Contenu |
|---|---|
| `OSIRIS_FINAL.mp4` | Film final 1080×1920 (9:16), 30 i/s, H.264 + AAC 48 kHz stéréo, 2 min 27 s, -14 LUFS, piste de sous-titres FR intégrée (désactivable) + sous-titres karaoké incrustés |
| `OSIRIS_FINAL.srt` | Sous-titres (identiques à la Phase 1, recalés au mot près) |
| `OSIRIS_AFTER_EFFECTS_2022.jsx` | Script ExtendScript (ES3) qui reconstruit tout le projet dans After Effects 2022 et enregistre `OSIRIS_FINAL.aep` |
| `media/` | Tous les médias nécessaires à la reconstruction (voir ci-dessous) |
| `src/` | Chaîne de fabrication reproductible (Python + FFmpeg) |

### Fichier `.aep`
Le format `.aep` est un format binaire propriétaire d'Adobe. On ne peut le créer qu'avec After Effects, qui n'est pas disponible dans l'environnement de fabrication (Linux). Le script JSX le **génère automatiquement** : il construit le projet complet, l'ajoute à la file de rendu, puis l'enregistre sous `OSIRIS_FINAL.aep` à côté du script.

## Reconstruire le projet dans After Effects 2022
1. Installer les polices de `media/fonts/` (Cinzel et Montserrat, licence OFL), puis redémarrer After Effects.
2. Dans *Préférences > Scripts et expressions*, cocher « Autoriser les scripts à écrire des fichiers et à accéder au réseau ».
3. Lancer *Fichier > Scripts > Exécuter le fichier de script…* et choisir `OSIRIS_AFTER_EFFECTS_2022.jsx`. Le dossier `media/` doit rester à côté du script.
4. Le script crée :
   - `OSIRIS_FINAL` (composition principale) ;
   - 39 précompositions de scènes (`Sxx_…`), en plans 2.5D avec caméra (zoom 1800 px) ;
   - 32 précompositions de titres animés (`TXT_…`) : texte modifiable, approche animée, lueur ;
   - `SOUS_TITRES` : 94 calques de texte, avec un animateur « Mot actif » qui colore en or le mot prononcé ;
   - les éclairs lumineux (dégradé radial en mode Addition), le grain (Bruit), les fondus et les 3 pistes audio.

   Une alerte de fin liste les éventuels avertissements (police absente, média manquant…).

## Contenu de `media/`
| Dossier | Contenu |
|---|---|
| `aroll/AROLL_GRADED.mp4` | Face caméra monté (EDL de la Phase 1), étalonné, couleurs harmonisées entre les rushes |
| `broll/` | 18 plans vidéo recadrés : sous-titres anglais et badges retirés |
| `stills/` | 9 illustrations nettoyées et agrandies |
| `graphics/` | Graphismes créés : cartes (Égypte en éclats, trajet Égypte → Israël, Afrique), icônes pain/bière/vin, loupe, cartes encadrées, ornements, symboles, vignettage, fond papyrus |
| `audio/` | `VOICE_STEM.wav`, `MUSIC.wav` (musique originale, déjà atténuée sous la voix) et `SFX.wav` (bruitages + ambiances), aux niveaux finaux : voix + musique + effets = mixage final ; `VOICE.wav` = voix montée avant mixage |
| `fonts/` | Cinzel, Montserrat (licence SIL OFL) |

## Vérifications effectuées
- `OSIRIS_FINAL.mp4` : décodage complet sans erreur ; vidéo et audio durent chacun 147,4 s ; -14,1 LUFS intégrés, crête -1,5 dBTP ; aucun noir ni silence parasite.
- Contrôle visuel d'une image au milieu de chaque scène et au milieu de chaque transition. Toutes les coupes de la Phase 1 sont couvertes par un plan B-roll ou par un fondu.
- `OSIRIS_AFTER_EFFECTS_2022.jsx` : analyse syntaxique ES3 stricte (dialecte ExtendScript) et exécution complète sur un modèle objet After Effects simulé (`src/tests/ae_mock_test.js`) : 86 compositions, 465 calques, 4 294 images clés, 0 avertissement.
- Le script n'a pas pu être exécuté dans un After Effects réel (logiciel absent de l'environnement de fabrication).

## Chaîne de fabrication (`src/`)
Les commandes se lancent depuis la racine du dépôt, dans cet ordre :
```
python3 output/ORISIS/PHASE_2/src/timeline.py        # spec unique du montage (data/timeline.json)
python3 output/ORISIS/PHASE_2/src/prep_media.py      # A-roll étalonné, B-roll, illustrations
python3 output/ORISIS/PHASE_2/src/make_graphics.py   # cartes, icônes, fonds
python3 output/ORISIS/PHASE_2/src/make_audio.py      # musique, sons, mixage
python3 output/ORISIS/PHASE_2/src/render.py OUT.mp4  # rendu image (4 processus)
python3 output/ORISIS/PHASE_2/src/make_jsx.py        # script After Effects
node    output/ORISIS/PHASE_2/src/tests/ae_mock_test.js output/ORISIS/PHASE_2/OSIRIS_AFTER_EFFECTS_2022.jsx
```
Le rendu (`render.py`) et le script AE (`make_jsx.py`) lisent la **même** spécification. Le rendu utilise la même projection de caméra qu'AE, et les animations complexes sont transférées dans AE sous forme d'images clés calculées.
