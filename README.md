# StreamTV

Application de streaming torrent avec lecture instantanee directement dans le navigateur.

## Fonctionnalites

### Streaming Torrent

- Lecture video instantanee des torrents (demarre des 1-2% telecharge)
- Seeking en temps reel avec priorisation intelligente des pieces
- Support des formats MKV, MP4, AVI, WebM
- Transcodage audio AAC en arriere-plan pour compatibilite navigateur

### Catalogue TMDB

- Recherche unifiee de films et series via l'API TMDB
- Affiches, synopsis, notes et dates de sortie
- Interface moderne et responsive

### Recherche de Torrents

- Agregation multi-sources (1337x, YTS, EZTV, TorrentGalaxy, etc.)
- Support prioritaire du francais (VF, VOSTFR, MULTI, TRUEFRENCH)
- Tri par seeders et qualite
- Detection automatique de la qualite (720p, 1080p, 4K, etc.)

### Lecteur Integre

- Lecteur HTML5 natif avec controles complets
- Barre de progression du telechargement en temps reel
- Transcodage audio automatique pour les codecs non supportes (AC3, DTS)
- Option de copie du lien magnet pour VLC

## Installation

### Prerequis

- Docker et Docker Compose
- Cle API TMDB (gratuite sur themoviedb.org)

### Demarrage Rapide

```bash
# Cloner le projet
git clone <repo-url>
cd streamTV

# Configurer les variables d'environnement
cp .env.example .env
# Editer .env avec votre cle TMDB_API_KEY

# Lancer l'application
docker-compose up -d

# Acceder a l'interface
# http://localhost:8000
```

### Configuration .env

```bash
# Cle API TMDB (obligatoire pour le catalogue)
TMDB_API_KEY=votre_cle_api_tmdb
```

## Utilisation

### Interface Web

1. Ouvrir http://localhost:8000
2. Rechercher un film ou une serie
3. Cliquer sur "Chercher Torrents" pour trouver les sources
4. Cliquer sur "Streamer" pour lancer la lecture

### Options de Recherche

- **Prioriser VF/VOSTFR** : Trie les resultats francais en premier
- **Recherche directe** : Recherche de torrents sans passer par le catalogue

### Lecture Video

1. La video demarre des que suffisamment de donnees sont disponibles
2. Le transcodage audio demarre automatiquement en arriere-plan
3. Quand le bouton "Activer le son" apparait, cliquez dessus pour activer l'audio AAC
4. Le seeking fonctionne a tout moment

## Architecture

```
streamTV/
  main_production.py         # Application principale FastAPI + Frontend
  real_streaming_service.py  # Service de streaming torrent (libtorrent)
  tmdb_service.py           # Service catalogue TMDB
  production_scraper.py     # Scraper multi-sources avec support francais
  simple_fallback_scraper.py # Scraper de secours
  french_scraper.py         # Scraper specialise sources francaises
  docker-compose.yml        # Configuration Docker
  Dockerfile               # Image Docker
  requirements.txt         # Dependances Python
```

## API REST

### Catalogue

```bash
# Recherche films et series
GET /api/search?query=inception

# Reponse
{
  "query": "inception",
  "results": {
    "movies": [...],
    "series": [...]
  }
}
```

### Torrents

```bash
# Recherche torrents
GET /api/torrents/search?query=inception&limit=20&prefer_french=true

# Recherche francais uniquement
GET /api/torrents/french?query=inception
```

### Streaming

```bash
# Demarrer un stream
POST /api/streaming/start
Body: {"magnet": "magnet:?xt=...", "title": "Film"}

# Status du stream
GET /api/streaming/status/{info_hash}

# Stream video
GET /api/streaming/video/{info_hash}

# Arreter un stream
DELETE /api/streaming/stop/{info_hash}
```

### Transcodage

```bash
# Demarrer transcodage audio
POST /api/streaming/transcode/start/{info_hash}

# Progression
GET /api/streaming/transcode/progress/{info_hash}

# Stream transcode
GET /api/streaming/transcode/{info_hash}
```

## Specifications Techniques

### Streaming

- Bibliotheque : libtorrent 2.x
- Buffer initial : 2 MB avant lecture
- Priorisation : Pieces sequentielles + seeking intelligent
- Ports : 6881-6891 TCP/UDP

### Transcodage

- Outil : FFmpeg
- Audio : AAC 128kbps stereo
- Video : Copy (pas de re-encodage)
- Format : MP4 avec faststart

### Performance

- Demarrage lecture : 5-30 secondes selon les seeders
- Transcodage audio : Temps reel (1x vitesse lecture)
- Seeking : Instantane sur fichier transcode
- Memoire : ~200 MB par stream actif

## Ports Utilises

| Port | Protocole | Usage |
|------|-----------|-------|
| 8000 | TCP | Interface web et API |
| 6881-6891 | TCP/UDP | Connexions BitTorrent |

## Depannage

### La video ne demarre pas

- Verifier que le torrent a des seeders
- Attendre que la barre de progression atteigne au moins 2%
- Essayer un autre torrent avec plus de seeders

### Pas de son

- Attendre que le transcodage soit termine (progression affichee)
- Cliquer sur le bouton "Activer le son" quand il apparait
- Les codecs AC3/DTS ne sont pas supportes nativement par les navigateurs

### Erreur de connexion

- Verifier que les ports 6881-6891 sont ouverts
- Verifier que Docker est bien demarre
- Consulter les logs : `docker-compose logs -f`

### Lecture saccadee

- Le torrent n'a peut-etre pas assez de seeders
- La connexion internet est peut-etre insuffisante
- Essayer un torrent de qualite inferieure (720p au lieu de 1080p)

## Commandes Docker

```bash
# Demarrer
docker-compose up -d

# Arreter
docker-compose down

# Voir les logs
docker-compose logs -f

# Reconstruire
docker-compose build --no-cache

# Status
docker-compose ps
```

## Limitations

- Certains codecs audio (AC3, DTS, TrueHD) necessitent un transcodage
- Le transcodage prend du temps pour les longs fichiers
- Les sous-titres integres ne sont pas encore supportes
- La lecture simultanee de plusieurs streams peut saturer la bande passante

## Licence

MIT License - Voir le fichier LICENSE pour plus de details.

## Avertissement

Cette application est destinee a un usage personnel et educatif. L'utilisateur est responsable du respect des lois locales concernant le telechargement et le streaming de contenus proteges par le droit d'auteur.
