# YouTube → TikTok Converter — Guide d'installation

Déploiement sur Proxmox / Docker avec exposition via Cloudflare Tunnel.

---

## Prérequis

- Docker + Docker Compose installés sur le container Proxmox
- Un domaine configuré dans Cloudflare
- `cloudflared` installé sur le serveur

---

## Étape 1 — Cloner / copier les fichiers

Copiez tout le dossier du projet sur votre serveur, par exemple dans `/opt/yt-tiktok/`.

```bash
# Sur le serveur Proxmox (dans le container Docker)
mkdir -p /opt/yt-tiktok
cd /opt/yt-tiktok
# Copiez les fichiers ici (scp, git clone, etc.)
```

---

## Étape 2 — Générer les clés VAPID (notifications push)

Les clés VAPID sont requises pour les notifications push Safari iOS.

```bash
cd /opt/yt-tiktok
python3 generate_keys.py
```

Sortie attendue :
```
Add these to your .env file:
VAPID_PRIVATE_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
VAPID_PUBLIC_KEY=Bxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Si Python 3 n'est pas installé localement, générez les clés depuis un container temporaire :
> ```bash
> docker run --rm python:3.11-slim pip install cryptography -q && python3 -c "..."
> ```
> Ou exécutez le script après avoir lancé le container (voir étape 4).

---

## Étape 3 — Créer le fichier .env

```bash
cp .env.example .env
nano .env  # ou vim .env
```

Remplissez **toutes** les valeurs :

```env
VAPID_PRIVATE_KEY=<clé privée générée à l'étape 2>
VAPID_PUBLIC_KEY=<clé publique générée à l'étape 2>
VAPID_CLAIMS_EMAIL=votre@email.com

# Laisser les valeurs par défaut pour Docker
DB_PATH=/data/app.db
DATA_DIR=/data
FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
```

> **Important** : ne commitez jamais `.env` dans git (il est dans `.gitignore` si vous en avez un).

---

## Étape 4 — Construire et lancer avec Docker Compose

```bash
cd /opt/yt-tiktok

# Build de l'image
docker compose build

# Lancer en arrière-plan
docker compose up -d

# Vérifier que le container tourne
docker compose ps

# Suivre les logs en temps réel
docker compose logs -f converter
```

L'application écoute sur `http://localhost:8000`.

Testez le healthcheck :
```bash
curl http://localhost:8000/api/health
# → {"status":"ok"}
```

---

## Étape 5 — Configurer Cloudflare Tunnel

### 5a. Installer cloudflared (si pas déjà fait)

```bash
# Debian/Ubuntu
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install cloudflared
```

### 5b. Créer et configurer le tunnel

```bash
# Authentification Cloudflare (ouvre un lien dans le navigateur)
cloudflared tunnel login

# Créer le tunnel
cloudflared tunnel create yt-tiktok

# Notez l'UUID du tunnel affiché (ex: a1b2c3d4-...)
```

### 5c. Fichier de configuration du tunnel

Créez `/etc/cloudflared/config.yml` :

```yaml
tunnel: <UUID-DU-TUNNEL>
credentials-file: /root/.cloudflared/<UUID-DU-TUNNEL>.json

ingress:
  - hostname: votre-domaine.com
    service: http://localhost:8000
  - service: http_status:404
```

### 5d. Route DNS et démarrage

```bash
# Créer l'entrée DNS dans Cloudflare
cloudflared tunnel route dns yt-tiktok votre-domaine.com

# Lancer le tunnel (test)
cloudflared tunnel run yt-tiktok

# Installer comme service systemd (démarrage automatique)
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
```

### 5e. Vérification

Ouvrez `https://votre-domaine.com` sur votre iPhone Safari.  
L'application doit s'afficher et les notifications push fonctionner (iOS 16.4+).

> **Note HTTPS** : Cloudflare Tunnel fournit automatiquement le certificat TLS.  
> Web Push sur Safari iOS **exige** HTTPS — le tunnel gère cela nativement.

---

## Mise à jour de l'application

```bash
cd /opt/yt-tiktok
# Modifiez les fichiers souhaités
docker compose build
docker compose up -d
```

---

## Commandes utiles

```bash
# Logs en direct
docker compose logs -f converter

# Redémarrage rapide
docker compose restart converter

# Arrêt complet
docker compose down

# Arrêt + suppression des données (DESTRUCTIF)
docker compose down -v

# Shell dans le container
docker compose exec converter bash

# Mettre à jour yt-dlp (sans rebuild)
docker compose exec converter pip install -U yt-dlp

# Voir l'espace disque utilisé par les vidéos
docker compose exec converter du -sh /data/
```

---

## Dépannage

### "yt-dlp download error"
- Vérifiez que la vidéo est accessible publiquement
- Mettez à jour yt-dlp : `docker compose exec converter pip install -U yt-dlp`
- Consultez les logs : `docker compose logs converter`

### "FFmpeg failed"
- Vérifiez les logs pour voir la commande FFmpeg exacte
- La police DejaVu doit être installée : `docker compose exec converter fc-list | grep DejaVu`

### Notifications push non reçues
- Vérifiez que VAPID_PRIVATE_KEY et VAPID_PUBLIC_KEY sont bien renseignées dans `.env`
- L'application doit être servie en **HTTPS** (Cloudflare Tunnel le garantit)
- iOS 16.4+ requis — vérifiez la version iOS
- Accordez la permission dans les Réglages iOS → Safari → [votre domaine] → Notifications

### Les fichiers ne sont pas supprimés après 24h
- Le nettoyage automatique tourne toutes les heures
- Forcez un nettoyage : redémarrez le container (`docker compose restart converter`)

---

## Statistiques d'utilisation

L'application enregistre automatiquement dans `/data/stats.json` :
- le nombre total de vidéos YouTube traitées avec succès
- le nombre total de segments créés

### Consulter les stats

**Via l'API (depuis n'importe où) :**
```bash
curl https://your-domain.com/api/stats
# ou en local :
curl http://localhost:8000/api/stats
```

Réponse exemple :
```json
{
  "videos_processed": 14,
  "segments_created": 31,
  "last_updated": "2026-04-17T10:23:45Z"
}
```

**Lire directement le fichier sur le serveur :**
```bash
cat /opt/yumsCUT/data/stats.json
```

**Suivre en temps réel dans les logs systemd :**
```bash
sudo journalctl -u yumsCUT -f | grep "DONE"
```

> Les stats sont persistées dans `/data/stats.json` et survivent aux redémarrages du service.
> Elles ne comptent que les jobs terminés avec succès (pas les annulations ni les erreurs).

---

## Architecture des données

```
/data/
├── app.db                    ← Base SQLite (jobs, files, sessions, push)
└── users/
    └── {session_id}/
        └── {job_id}/
            ├── source.mp4    ← Supprimé après encodage
            ├── titre_partie_01_sur_03.mp4
            ├── titre_partie_02_sur_03.mp4
            └── titre_partie_03_sur_03.mp4
```

Les fichiers encodés sont conservés **24 heures** puis supprimés automatiquement.
