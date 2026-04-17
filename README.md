# YumsCUT

Convertisseur YouTube → TikTok/Reels/Shorts.

Collez une URL YouTube — YumsCUT télécharge la vidéo, la reformate en portrait 9:16 avec fond flouté, et la découpe automatiquement en segments de 3 minutes maximum, prêts à publier.

---

## Fonctionnalités

- Découpe automatique en segments ≤ 3 min (format TikTok/Reels/Shorts)
- Portrait 9:16 avec fond flouté (letterbox intelligent)
- Titre de la vidéo et numéro de partie incrustés en texte
- Téléchargement direct depuis l'interface web
- Interface mobile-friendly (PWA)
- Statistiques d'utilisation
- Annulation de traitement en cours

---

## Prérequis

| Logiciel | Version minimale | Lien |
|---|---|---|
| Python | 3.10+ | https://www.python.org/downloads/ |
| ffmpeg | 4.x+ | https://www.gyan.dev/ffmpeg/builds/ |
| yt-dlp | installé automatiquement | — |

> **Windows** : lors de l'installation de Python, cochez impérativement **"Add Python to PATH"**.

---

## Installation Windows (recommandée)

### Étape 1 — Installer Python

Téléchargez Python 3.10 ou supérieur depuis https://www.python.org/downloads/

> Cochez **"Add Python to PATH"** sur l'écran d'installation.

### Étape 2 — Installer ffmpeg

**Option A — Avec winget (Windows 11, recommandé) :**
Ouvrez le Terminal Windows et tapez :
```
winget install Gyan.FFmpeg
```

**Option B — Manuellement :**
1. Téléchargez la version `ffmpeg-release-essentials.zip` depuis https://www.gyan.dev/ffmpeg/builds/
2. Décompressez l'archive (par exemple dans `C:\ffmpeg\`)
3. Ajoutez `C:\ffmpeg\bin` à votre variable d'environnement `PATH`

### Étape 3 — Télécharger YumsCUT

Téléchargez la dernière version : **[YumsCUT.zip](https://github.com/trueYums/YumsCUT/releases/latest/download/YumsCUT.zip)**

Décompressez l'archive où vous voulez.

### Étape 4 — Lancer le setup

Dans le dossier décompressé, double-cliquez sur **`setup.bat`**.

Le script va :
- Créer un environnement Python isolé
- Installer toutes les dépendances automatiquement
- Générer les clés de configuration
- Ouvrir le fichier `.env` dans le Bloc-notes pour que vous puissiez remplir vos informations

### Étape 5 — Remplir le fichier .env

Dans le Bloc-notes qui s'ouvre, remplacez :
- `REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS` (×2) par les clés affichées dans la fenêtre du setup
- `votre@email.com` par votre adresse e-mail

Sauvegardez (`Ctrl+S`) et fermez le Bloc-notes.

### Étape 6 — Lancer l'application

Double-cliquez sur **`start.bat`**.

Le navigateur s'ouvre automatiquement sur l'interface YumsCUT.

---

## Utilisation quotidienne

| Action | Comment faire |
|---|---|
| **Lancer YumsCUT** | Double-cliquez sur `start.bat` |
| **Utiliser l'app** | Le navigateur s'ouvre tout seul — sinon allez sur `http://VOTRE-IP:2309` |
| **Garder YumsCUT actif** | **Minimisez** la fenêtre noire (terminal) — ne la fermez pas |
| **Arrêter YumsCUT** | Fermez la fenêtre noire du terminal |
| **Relancer** | Double-cliquez sur `start.bat` (ferme l'ancienne instance automatiquement) |

> L'adresse exacte est affichée dans la fenêtre du terminal au démarrage.  
> Elle ressemble à `http://192.168.1.X:2309` — utilisez cette adresse depuis n'importe quel appareil de votre réseau (téléphone, tablette, autre PC).

---

## Installation Linux / macOS

```bash
# 1. Installer les dépendances système
# Ubuntu/Debian :
sudo apt install python3 python3-venv ffmpeg

# macOS (avec Homebrew) :
brew install python ffmpeg

# 2. Cloner le dépôt
git clone https://github.com/trueYums/YumsCUT.git
cd YumsCUT

# 3. Créer l'environnement Python
python3 -m venv venv
source venv/bin/activate

# 4. Installer les dépendances Python
pip install -r requirements.txt
pip install -U yt-dlp

# 5. Générer les clés VAPID
python generate_keys.py

# 6. Créer le fichier .env
cp .env.example .env
# Éditez .env et renseignez les clés VAPID générées à l'étape précédente

# 7. Lancer l'application
uvicorn main:app --host 0.0.0.0 --port 2309
```

Ouvrez ensuite `http://localhost:2309` dans votre navigateur.

---

## Configuration (.env)

| Variable | Description |
|---|---|
| `VAPID_PRIVATE_KEY` | Clé privée pour les notifications push (générée par `generate_keys.py`) |
| `VAPID_PUBLIC_KEY` | Clé publique pour les notifications push |
| `VAPID_CLAIMS_EMAIL` | Votre adresse e-mail (requise par le protocole Web Push) |
| `DB_PATH` | Chemin vers la base de données SQLite |
| `DATA_DIR` | Dossier de stockage des vidéos traitées |
| `FONT_PATH` | Chemin vers une police TrueType pour les incrustations texte |

> Ne partagez jamais votre fichier `.env` — il contient vos clés privées.

---

## Statistiques d'utilisation

Consultez le nombre de vidéos traitées et de segments créés :

```
http://VOTRE-IP:2309/api/stats
```

Réponse :
```json
{
  "videos_processed": 14,
  "segments_created": 31,
  "last_updated": "2026-04-17T10:23:45Z"
}
```

Les statistiques sont stockées dans `data/stats.json` et persistent entre les redémarrages.

---

## Démarrage automatique (optionnel)

Pour que YumsCUT démarre automatiquement à l'ouverture de session Windows :

1. Appuyez sur `Win+R`, tapez `taskschd.msc` et validez
2. Cliquez sur **Créer une tâche**
3. Onglet **Général** : nom = `YumsCUT`
4. Onglet **Déclencheurs** : Nouveau → Au démarrage de session
5. Onglet **Actions** : Nouveau → Programme = chemin vers `venv\Scripts\uvicorn.exe`, Arguments = `main:app --host 0.0.0.0 --port 2309`, Démarrer dans = dossier du projet
6. Cliquez OK

---

## Désinstallation

Double-cliquez sur **`uninstall.bat`** dans le dossier de l'application.

Le script va vous demander confirmation, arrêter YumsCUT s'il est en cours d'exécution, puis supprimer tous les fichiers de l'application.

---

## Déploiement sur serveur

Pour déployer sur un VPS ou un serveur Proxmox avec accès depuis internet via Cloudflare Tunnel, consultez [INSTALL.md](INSTALL.md).

---

## Licence

Usage personnel et privé uniquement. Voir [LICENSE](LICENSE).

© 2026 Yums — https://github.com/trueYums
