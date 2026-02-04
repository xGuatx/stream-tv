#!/usr/bin/env python3
"""
StreamTV Production - Application de Streaming Torrent
Version finale avec streaming reel fonctionnel
"""

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, Response
import os
import logging
import subprocess
import shutil
import time
from typing import Optional, Dict
from collections import OrderedDict
from dotenv import load_dotenv

from tmdb_service import CatalogService
from production_scraper import production_scraper
from simple_fallback_scraper import simple_fallback_scraper
from real_streaming_service import real_streaming_service

# Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Services
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
catalog_service = CatalogService(TMDB_API_KEY) if TMDB_API_KEY else None

# FastAPI App
app = FastAPI(
    title="StreamTV Production",
    description="Moteur de recherche et streaming torrent",
    version="2.0.0-production"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def home():
    """Interface web StreamTV Production"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>StreamTV - Streaming & Torrents</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #0c0c0c, #1a1a1a); color: #fff; min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { font-size: 2.5rem; color: #e50914; text-shadow: 0 0 20px rgba(229, 9, 20, 0.5); }
        .header p { color: #ccc; margin: 10px 0; font-size: 1rem; }
        .search-section { background: rgba(255,255,255,0.05); border-radius: 15px; padding: 25px; margin-bottom: 25px; }
        .search-row { display: flex; gap: 10px; align-items: center; }
        .search-input { flex: 1; padding: 14px 18px; font-size: 16px; border: none; border-radius: 10px; background: rgba(255,255,255,0.1); color: #fff; }
        .search-input:focus { outline: none; box-shadow: 0 0 15px rgba(229, 9, 20, 0.3); }
        .btn { padding: 14px 22px; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: 600; transition: all 0.3s; white-space: nowrap; }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none !important; }
        .btn-primary { background: linear-gradient(45deg, #e50914, #ff6b6b); color: white; }
        .btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 15px rgba(0,0,0,0.3); }
        .search-options { display: flex; gap: 20px; margin-top: 15px; align-items: center; justify-content: center; flex-wrap: wrap; }
        .checkbox-label { color: #888; font-size: 14px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
        .checkbox-label input { width: 16px; height: 16px; }
        .results { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; margin-top: 20px; }
        .item { background: rgba(255,255,255,0.08); border-radius: 12px; padding: 15px; transition: all 0.3s; border: 1px solid rgba(255,255,255,0.1); position: relative; }
        .item:hover { box-shadow: 0 15px 30px rgba(0,0,0,0.3); }
        .item img { width: 100%; height: 200px; object-fit: cover; border-radius: 8px; margin-bottom: 12px; }
        .item h3 { color: #e50914; margin-bottom: 8px; font-size: 1.1rem; }
        .item p { font-size: 0.85rem; color: #aaa; margin-bottom: 12px; }
        .item-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .rating { background: #FF9800; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .btn-small { padding: 8px 14px; font-size: 13px; }

        /* Torrent results inline */
        .torrent-section { margin-top: 15px; background: rgba(0,0,0,0.4); border-radius: 10px; overflow: hidden; }
        .torrent-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 15px; background: rgba(229,9,20,0.2); cursor: pointer; }
        .torrent-header h4 { color: #e50914; font-size: 14px; }
        .torrent-toggle { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; padding: 5px; }
        .torrent-list { max-height: 400px; overflow-y: auto; }
        .torrent-list.collapsed { display: none; }
        .torrent-item { padding: 12px 15px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .torrent-item:last-child { border-bottom: none; }
        .torrent-item:hover { background: rgba(255,255,255,0.05); }
        .torrent-title { color: #fff; font-size: 13px; margin-bottom: 6px; word-break: break-word; }
        .torrent-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 12px; margin-bottom: 8px; }
        .torrent-meta .seeders { color: #4CAF50; font-weight: bold; }
        .torrent-meta .size { color: #2196F3; }
        .badge { padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; }
        .badge-quality { background: #FF9800; color: white; }
        .badge-lang { background: #607D8B; color: white; }
        .badge-vf { background: #2196F3; }
        .badge-vostfr { background: #9C27B0; }
        .badge-multi { background: #009688; }
        .badge-french { background: #3F51B5; }
        .torrent-actions { display: flex; gap: 6px; }
        .btn-xs { padding: 5px 10px; font-size: 11px; border-radius: 4px; }
        .btn-stream-xs { background: linear-gradient(45deg, #e50914, #ff6b6b); color: white; }
        .btn-magnet-xs { background: #4CAF50; color: white; }

        /* Player inline */
        .player-section { margin-top: 15px; background: #000; border-radius: 10px; overflow: hidden; }
        .player-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; background: rgba(229,9,20,0.3); }
        .player-header span { color: #fff; font-size: 13px; }
        .player-close { background: #666; border: none; color: white; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .player-content { position: relative; }
        .player-content video { width: 100%; max-height: 300px; background: #000; }
        .player-status { padding: 10px 15px; background: rgba(0,0,0,0.8); font-size: 12px; color: #888; }
        .progress-bar { height: 4px; background: #333; border-radius: 2px; margin-top: 8px; }
        .progress-fill { height: 100%; background: linear-gradient(45deg, #e50914, #ff6b6b); border-radius: 2px; width: 0%; transition: width 0.3s; }

        /* Loading */
        .loading { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: #fff; animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Scrollbar */
        .torrent-list::-webkit-scrollbar { width: 6px; }
        .torrent-list::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
        .torrent-list::-webkit-scrollbar-thumb { background: #e50914; border-radius: 3px; }
    </style>
    <!-- HLS.js pour streaming professionnel -->
    <!-- Streaming direct + transcodage arriere-plan -->
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>StreamTV</h1>
            <p>Streaming torrent instantane - Recherchez, trouvez, regardez</p>
        </div>

        <div class="search-section">
            <div class="search-row">
                <input type="text" id="searchInput" class="search-input" placeholder="Rechercher un film ou une serie..." onkeypress="if(event.key==='Enter') searchContent()">
                <button id="searchBtn" class="btn btn-primary" onclick="searchContent()">Rechercher</button>
            </div>
            <div class="search-options">
                <label class="checkbox-label">
                    <input type="checkbox" id="preferFrench" checked>
                    Prioriser VF/VOSTFR
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="directSearch">
                    Recherche directe (sans catalogue)
                </label>
            </div>
        </div>

        <div id="results" class="results"></div>
    </div>

    <script>
        // Protection anti-spam
        let isSearching = false;
        let searchCache = {};
        let activeStreams = {};

        async function searchContent() {
            if (isSearching) return;

            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            const directSearch = document.getElementById('directSearch').checked;

            if (directSearch) {
                await searchTorrentsForCard(null, query);
                return;
            }

            isSearching = true;
            const btn = document.getElementById('searchBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span>Recherche...';

            try {
                const response = await fetch('/api/search?query=' + encodeURIComponent(query));
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();
                displayCatalogResults(data);
            } catch (error) {
                console.error('Erreur:', error);
                alert('Erreur lors de la recherche');
            } finally {
                isSearching = false;
                btn.disabled = false;
                btn.textContent = 'Rechercher';
            }
        }

        function displayCatalogResults(data) {
            const results = document.getElementById('results');
            results.innerHTML = '';

            // Combiner et trier par ordre alphabetique
            const allItems = [];

            data.results.movies.forEach(m => allItems.push({type: 'movie', data: m, title: m.title}));
            data.results.series.forEach(s => allItems.push({type: 'series', data: s, title: s.name}));

            allItems.sort((a, b) => a.title.localeCompare(b.title));

            allItems.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'item';
                div.id = 'card-' + index;

                if (item.type === 'movie') {
                    const m = item.data;
                    div.innerHTML = createCardHTML(index, m.poster_path, m.title, m.release_date, m.overview, m.vote_average);
                } else {
                    const s = item.data;
                    div.innerHTML = createCardHTML(index, s.poster_path, s.name, s.first_air_date, s.overview, s.vote_average);
                }

                results.appendChild(div);
            });

            if (allItems.length === 0) {
                results.innerHTML = '<p style="text-align:center;color:#888;grid-column:1/-1;">Aucun resultat trouve</p>';
            }
        }

        function createCardHTML(index, poster, title, date, overview, rating) {
            const year = date ? date.split('-')[0] : 'N/A';
            const desc = overview ? overview.substring(0, 100) + '...' : 'Pas de description';
            const safeTitle = title.replace(/"/g, '&quot;');

            return '<img src="' + (poster || '/placeholder-poster.svg') + '" alt="' + safeTitle + '" onerror="this.src=\\'/placeholder-poster.svg\\'"/>' +
                '<h3>' + title + ' (' + year + ')</h3>' +
                '<p>' + desc + '</p>' +
                '<div class="item-actions">' +
                    '<span class="rating">' + (rating || 'N/A') + '/10</span>' +
                    '<button class="btn btn-primary btn-small" id="torrent-btn-' + index + '" onclick="searchTorrentsForCard(' + index + ', \\'' + safeTitle + '\\')">Chercher Torrents</button>' +
                '</div>' +
                '<div id="torrent-container-' + index + '"></div>' +
                '<div id="player-container-' + index + '"></div>';
        }

        async function searchTorrentsForCard(cardIndex, title) {
            const btnId = cardIndex !== null ? 'torrent-btn-' + cardIndex : null;
            const containerId = cardIndex !== null ? 'torrent-container-' + cardIndex : null;

            // Anti-spam: verifier si deja en cours
            const cacheKey = (cardIndex !== null ? cardIndex : 'direct') + '-' + title;
            if (searchCache[cacheKey] === 'loading') return;

            // Si resultats deja affiches, toggle visibility
            if (containerId) {
                const container = document.getElementById(containerId);
                if (container && container.innerHTML) {
                    const list = container.querySelector('.torrent-list');
                    if (list) {
                        list.classList.toggle('collapsed');
                        return;
                    }
                }
            }

            searchCache[cacheKey] = 'loading';

            const btn = btnId ? document.getElementById(btnId) : document.getElementById('searchBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span>...';
            }

            try {
                const preferFrench = document.getElementById('preferFrench').checked;
                const url = '/api/torrents/search?query=' + encodeURIComponent(title) + '&limit=20&prefer_french=' + preferFrench;

                const response = await fetch(url);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();

                if (data.torrents && data.torrents.length > 0) {
                    // Trier par ordre alphabetique
                    data.torrents.sort((a, b) => a.title.localeCompare(b.title));

                    if (containerId) {
                        displayTorrentsInCard(containerId, data.torrents, title, cardIndex);
                    } else {
                        displayTorrentsGlobal(data.torrents, title);
                    }
                    searchCache[cacheKey] = 'done';
                } else {
                    alert('Aucun torrent trouve pour: ' + title);
                    searchCache[cacheKey] = null;
                }
            } catch (error) {
                console.error('Erreur:', error);
                alert('Erreur recherche torrents');
                searchCache[cacheKey] = null;
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Chercher Torrents';
                }
            }
        }

        function displayTorrentsInCard(containerId, torrents, title, cardIndex) {
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = '<div class="torrent-section">' +
                '<div class="torrent-header" onclick="toggleTorrentList(' + cardIndex + ')">' +
                    '<h4>' + torrents.length + ' torrents trouves</h4>' +
                    '<button class="torrent-toggle" id="toggle-' + cardIndex + '">−</button>' +
                '</div>' +
                '<div class="torrent-list" id="list-' + cardIndex + '">' +
                    torrents.map((t, i) => createTorrentItemHTML(t, cardIndex, i)).join('') +
                '</div>' +
            '</div>';
        }

        function displayTorrentsGlobal(torrents, title) {
            const results = document.getElementById('results');
            results.innerHTML = '<div class="item" style="grid-column: 1/-1;">' +
                '<h3 style="color:#e50914;margin-bottom:15px;">Resultats pour: ' + title + '</h3>' +
                '<div class="torrent-list" style="max-height:none;">' +
                    torrents.map((t, i) => createTorrentItemHTML(t, 'global', i)).join('') +
                '</div>' +
            '</div>';
        }

        // Stockage global des donnees torrents pour eviter les problemes d'echappement
        const torrentDataStore = {};

        function createTorrentItemHTML(t, cardIndex, torrentIndex) {
            const size = t.size ? (t.size / 1e9).toFixed(1) + ' GB' : (t.size_str || 'N/A');
            const langClass = getLangClass(t.language);

            // Stocker les donnees du torrent avec une cle unique
            const torrentKey = cardIndex + '_' + torrentIndex;
            torrentDataStore[torrentKey] = {
                magnet: t.magnet,
                title: t.title
            };

            return '<div class="torrent-item">' +
                '<div class="torrent-title">' + t.title + '</div>' +
                '<div class="torrent-meta">' +
                    '<span class="seeders">' + (t.seeders || 0) + ' seeds</span>' +
                    '<span class="size">' + size + '</span>' +
                    '<span class="badge badge-quality">' + (t.quality || 'HD') + '</span>' +
                    '<span class="badge ' + langClass + '">' + (t.language || 'ENG') + '</span>' +
                '</div>' +
                '<div class="torrent-actions">' +
                    '<button class="btn btn-xs btn-stream-xs" onclick="streamFromStore(\\'' + torrentKey + '\\', \\'' + cardIndex + '\\')">Streamer</button>' +
                    '<button class="btn btn-xs btn-magnet-xs" onclick="copyMagnetFromStore(\\'' + torrentKey + '\\')">Copier Magnet</button>' +
                '</div>' +
            '</div>';
        }

        function streamFromStore(torrentKey, cardIndex) {
            const data = torrentDataStore[torrentKey];
            if (data) {
                startStreamingInline(data.magnet, data.title, cardIndex);
            } else {
                alert('Erreur: donnees du torrent non trouvees');
            }
        }

        function copyMagnetFromStore(torrentKey) {
            const data = torrentDataStore[torrentKey];
            if (data) {
                copyMagnet(data.magnet);
            } else {
                alert('Erreur: magnet non trouve');
            }
        }

        function getLangClass(lang) {
            const map = {
                'VF': 'badge-vf', 'VFF': 'badge-vf', 'VFQ': 'badge-vf',
                'VOSTFR': 'badge-vostfr', 'SUBFRENCH': 'badge-vostfr',
                'MULTI': 'badge-multi',
                'FRENCH': 'badge-french', 'TRUEFRENCH': 'badge-french'
            };
            return map[lang] || 'badge-lang';
        }

        function toggleTorrentList(cardIndex) {
            const list = document.getElementById('list-' + cardIndex);
            const toggle = document.getElementById('toggle-' + cardIndex);
            if (list && toggle) {
                list.classList.toggle('collapsed');
                toggle.textContent = list.classList.contains('collapsed') ? '+' : '−';
            }
        }

        async function startStreamingInline(magnet, title, cardIndex) {
            const containerId = cardIndex === 'global' ? 'player-container-global' : 'player-container-' + cardIndex;
            let container = document.getElementById(containerId);

            // Si pas de container, creer un global
            if (!container) {
                const results = document.getElementById('results');
                const div = document.createElement('div');
                div.id = containerId;
                div.style.gridColumn = '1/-1';
                results.prepend(div);
                container = div;
            }

            // Afficher loading
            container.innerHTML = '<div class="player-section">' +
                '<div class="player-header">' +
                    '<span><span class="loading"></span>Demarrage: ' + title.substring(0, 40) + '...</span>' +
                    '<button class="player-close" onclick="stopStreaming(\\'' + containerId + '\\')">Fermer</button>' +
                '</div>' +
                '<div class="player-status">Connexion au reseau torrent...</div>' +
            '</div>';

            try {
                const response = await fetch('/api/streaming/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({magnet: magnet, title: title})
                });

                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();

                if (data.success) {
                    activeStreams[containerId] = data.info_hash;
                    showPlayer(containerId, data.info_hash, title, magnet);
                } else {
                    throw new Error(data.error || 'Erreur demarrage');
                }
            } catch (error) {
                console.error('Erreur streaming:', error);
                container.innerHTML = '<div class="player-section">' +
                    '<div class="player-header" style="background:rgba(255,0,0,0.3);">' +
                        '<span>Erreur: ' + error.message + '</span>' +
                        '<button class="player-close" onclick="this.closest(\\'.player-section\\').remove()">Fermer</button>' +
                    '</div>' +
                '</div>';
            }
        }

        // ==========================================
        // STREAMING DIRECT - Simple et fiable
        // ==========================================
        let transcodeStatus = {};  // infoHash -> {started, ready}
        const magnetStore = {};  // infoHash -> magnet link

        function showPlayer(containerId, infoHash, title, magnet) {
            const container = document.getElementById(containerId);
            if (!container) return;

            // Stocker le magnet pour acces ulterieur sans problemes d'echappement
            magnetStore[infoHash] = magnet;

            const directUrl = '/api/streaming/video/' + infoHash;
            const transcodedUrl = '/api/streaming/transcode/' + infoHash;

            container.innerHTML = '<div class="player-section">' +
                '<div class="player-header">' +
                    '<span>' + title.substring(0, 50) + '</span>' +
                    '<div style="display:flex;gap:8px;align-items:center;">' +
                        '<button class="btn-xs" style="background:#FF9800;color:white;" onclick="copyMagnetByHash(\\'' + infoHash + '\\')" title="Pour VLC">Magnet</button>' +
                        '<button class="player-close" onclick="stopStreaming(\\'' + containerId + '\\')">X</button>' +
                    '</div>' +
                '</div>' +
                '<div class="player-info" id="player-info-' + infoHash + '" style="background:rgba(33,150,243,0.2);padding:8px 15px;font-size:11px;color:#64B5F6;">' +
                    '<span class="loading"></span>Connexion...' +
                '</div>' +
                '<div class="player-content">' +
                    '<video id="video-' + infoHash + '" controls preload="auto" style="display:none;" playsinline></video>' +
                '</div>' +
                '<div class="player-status" id="status-' + infoHash + '">' +
                    '<div class="progress-bar"><div class="progress-fill" id="progress-' + infoHash + '"></div></div>' +
                '</div>' +
            '</div>';

            // Attendre que le fichier soit pret puis lancer
            waitAndPlay(infoHash, directUrl, transcodedUrl);
        }

        function copyMagnetByHash(infoHash) {
            const magnet = magnetStore[infoHash];
            if (magnet) {
                copyMagnet(magnet);
            } else {
                alert('Magnet non trouve');
            }
        }

        function waitAndPlay(infoHash, directUrl, transcodedUrl) {
            const info = document.getElementById('player-info-' + infoHash);
            const video = document.getElementById('video-' + infoHash);
            let transcodeStarted = false;

            const checkReady = async () => {
                try {
                    // Verifier le statut du torrent
                    const response = await fetch('/api/streaming/status/' + infoHash);
                    if (!response.ok) {
                        if (info) info.innerHTML = '<span class="loading"></span>Connexion aux pairs...';
                        setTimeout(checkReady, 1000);
                        return;
                    }

                    const data = await response.json();
                    const progress = document.getElementById('progress-' + infoHash);
                    const pct = data.progress || 0;
                    if (progress) progress.style.width = pct + '%';

                    // Quand le fichier est pret, lancer le transcodage
                    if (data.can_stream && data.ready_file && !transcodeStarted) {
                        transcodeStarted = true;
                        if (info) {
                            info.style.background = 'rgba(255,152,0,0.2)';
                            info.style.color = '#FFB74D';
                            info.innerHTML = '<span class="loading"></span>Transcodage audio... 0%';
                        }

                        // Lancer le transcodage
                        fetch('/api/streaming/transcode/start/' + infoHash, {method: 'POST'})
                            .then(r => r.json())
                            .then(d => { transcodeStatus[infoHash] = {started: true, ready: false, progress: 0}; })
                            .catch(() => {});
                    }

                    // Verifier la progression du transcodage
                    if (transcodeStarted) {
                        try {
                            const tRes = await fetch('/api/streaming/transcode/progress/' + infoHash);
                            const tData = await tRes.json();
                            const transcodeProgress = tData.progress || 0;

                            // Mettre a jour l'affichage de progression
                            if (tData.status === 'transcoding') {
                                if (info) {
                                    info.innerHTML = '<span class="loading"></span>Transcodage audio: ' + transcodeProgress + '%';
                                }
                            }

                            // Transcodage termine a 100% - lancer la lecture
                            if (tData.status === 'ready') {
                                transcodeStatus[infoHash] = {started: true, ready: true, progress: 100};

                                if (info) {
                                    info.style.background = 'rgba(76,175,80,0.2)';
                                    info.style.color = '#81C784';
                                    info.innerHTML = 'Lecture en cours';
                                }

                                // Lancer la video transcodee
                                video.src = transcodedUrl;
                                video.style.display = 'block';
                                video.play().catch(() => {});
                                return; // Stop polling
                            }
                        } catch (e) {}
                    }

                    // Continuer le polling tant que le transcodage n'est pas termine
                    setTimeout(checkReady, 2000);
                } catch (e) {
                    setTimeout(checkReady, 2000);
                }
            };
            checkReady();
        }

        function formatTime(seconds) {
            if (!seconds || isNaN(seconds)) return '0:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return mins + ':' + (secs < 10 ? '0' : '') + secs;
        }

        function switchToTranscoded(infoHash, transcodedUrl) {
            const video = document.getElementById('video-' + infoHash);
            const info = document.getElementById('player-info-' + infoHash);
            if (!video) return;

            const currentTime = video.currentTime;
            const wasPlaying = !video.paused;

            video.src = transcodedUrl;
            video.currentTime = currentTime;

            if (wasPlaying) {
                video.play().catch(() => {});
            }

            if (info) {
                info.style.background = 'rgba(76,175,80,0.2)';
                info.style.color = '#81C784';
                info.textContent = 'Lecture avec son AAC - Seeking instantane';
            }
        }

        function copyMagnet(magnet) {
            navigator.clipboard.writeText(magnet).then(() => {
                alert('Magnet copie!\\n\\nPour VLC: Media > Ouvrir un flux reseau > Coller');
            }).catch(() => {
                prompt('Copiez ce magnet:', magnet);
            });
        }

        function openInVLC(streamUrl, magnet) {
            // Copier le magnet directement (plus fiable)
            navigator.clipboard.writeText(magnet).then(() => {
                alert('Magnet copie dans le presse-papier!\\n\\nOuvrez VLC > Media > Ouvrir un flux reseau\\nCollez le magnet et cliquez Lire');
            }).catch(() => {
                // Fallback: essayer protocole vlc://
                const link = document.createElement('a');
                link.href = 'vlc://' + streamUrl;
                link.click();
            });
        }

        function startStatusPolling(infoHash) {
            const poll = async () => {
                try {
                    const response = await fetch('/api/streaming/status/' + infoHash);
                    if (!response.ok) return;

                    const data = await response.json();
                    const progress = document.getElementById('progress-' + infoHash);
                    const status = document.getElementById('status-' + infoHash);
                    const video = document.getElementById('video-' + infoHash);

                    if (progress) progress.style.width = (data.progress || 0) + '%';
                    if (status) status.firstChild.textContent = 'Progression: ' + (data.progress || 0) + '% - ' + (data.can_stream ? 'Pret!' : 'Buffering...');

                    if (data.can_stream && data.progress >= 1 && video) {
                        video.style.display = 'block';
                        if (video.readyState === 0) video.load();
                    }

                    if (data.progress < 100) {
                        setTimeout(poll, 2000);
                    }
                } catch (e) {
                    console.error('Poll error:', e);
                }
            };
            poll();
        }

        function stopStreaming(containerId) {
            const infoHash = activeStreams[containerId];
            if (infoHash) {
                fetch('/api/streaming/stop/' + infoHash, {method: 'DELETE'}).catch(() => {});
                delete activeStreams[containerId];
                delete transcodeStatus[infoHash];
            }
            const container = document.getElementById(containerId);
            if (container) container.innerHTML = '';
        }

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            Object.values(activeStreams).forEach(hash => {
                fetch('/api/streaming/stop/' + hash, {method: 'DELETE'}).catch(() => {});
            });
        });
    </script>
</body>
</html>
    """

@app.get("/api/search")
async def search_content(query: str = Query(..., description="Terme de recherche")):
    """Recherche catalogue TMDB"""
    if not catalog_service:
        return {"query": query, "results": {"movies": [], "series": []}}
    
    try:
        results = catalog_service.unified_search(query)
        return {"query": query, "results": results}
    except Exception as e:
        logger.error(f"Erreur recherche TMDB: {e}")
        return {"query": query, "results": {"movies": [], "series": []}}

@app.get("/api/torrents/search")
async def search_torrents(
    query: str = Query(...),
    limit: int = Query(20),
    prefer_french: bool = Query(True, description="Prioriser les résultats en français")
):
    """Recherche torrents production avec support français avancé"""
    try:
        # Essayer le scraper principal avec support français
        torrents = await production_scraper.search_all_production(query, prefer_french=prefer_french)
        quality_torrents = [t for t in torrents if t.get('seeders', 0) >= 1]

        # Si pas de resultats, utiliser le fallback
        if not quality_torrents:
            logger.info(f"Fallback search pour: '{query}'")
            fallback_torrents = await simple_fallback_scraper.search_content(query, limit)
            quality_torrents.extend(fallback_torrents)

        # Compter les résultats français
        french_count = sum(1 for t in quality_torrents if t.get('is_french', False))

        return {
            "query": query,
            "torrents": quality_torrents[:limit],
            "total_found": len(quality_torrents),
            "french_count": french_count,
            "prefer_french": prefer_french,
            "source": "production_scraper_with_french"
        }
    except Exception as e:
        logger.error(f"Erreur recherche torrents: {e}")
        # En cas d'erreur, essayer uniquement le fallback
        try:
            fallback_torrents = await simple_fallback_scraper.search_content(query, limit)
            return {
                "query": query,
                "torrents": fallback_torrents[:limit],
                "total_found": len(fallback_torrents),
                "french_count": 0,
                "source": "fallback_only"
            }
        except Exception as fallback_error:
            logger.error(f"Erreur fallback: {fallback_error}")
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/torrents/french")
async def search_french_torrents(query: str = Query(...), limit: int = Query(20)):
    """Recherche torrents uniquement en français"""
    try:
        torrents = await production_scraper.search_french_only(query)
        quality_torrents = [t for t in torrents if t.get('seeders', 0) >= 1]

        return {
            "query": query,
            "torrents": quality_torrents[:limit],
            "total_found": len(quality_torrents),
            "all_french": True,
            "source": "french_scraper"
        }
    except Exception as e:
        logger.error(f"Erreur recherche française: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/streaming/start")
async def start_streaming(request: Request):
    """Demarre le streaming d'un torrent"""
    try:
        data = await request.json()
        magnet = data.get('magnet')
        title = data.get('title', 'Unknown')
        
        if not magnet:
            raise HTTPException(status_code=400, detail="Magnet link requis")
        
        info_hash = real_streaming_service.start_download(magnet, title)
        
        if not info_hash:
            raise HTTPException(status_code=400, detail="Impossible de demarrer le telechargement")
        
        return {
            "success": True,
            "info_hash": info_hash,
            "message": f"Streaming demarre: {title}"
        }
    
    except Exception as e:
        logger.error(f"Erreur start streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/streaming/status/{info_hash}")
async def get_streaming_status(info_hash: str):
    """Status du streaming"""
    info = real_streaming_service.get_streaming_info(info_hash)
    if not info:
        raise HTTPException(status_code=404, detail="Torrent non trouve")
    return info

@app.delete("/api/streaming/stop/{info_hash}")
async def stop_streaming(info_hash: str):
    """Arrete et nettoie un streaming"""
    try:
        success = real_streaming_service.stop_torrent(info_hash)
        if success:
            return {"success": True, "message": "Streaming arrete et nettoye"}
        else:
            raise HTTPException(status_code=404, detail="Torrent non trouve")
    except Exception as e:
        logger.error(f"Erreur stop streaming: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/streaming/seek/{info_hash}")
async def seek_streaming(info_hash: str, request: Request):
    """Configure seeking temps reel pour un streaming"""
    try:
        data = await request.json()
        position = data.get('position', 0)  # Position entre 0.0 et 1.0
        
        # Configurer les priorites pour le seeking
        success = real_streaming_service.set_piece_priorities_for_seeking(info_hash, position)
        
        if success:
            # Verifier la disponibilite immediate
            availability = real_streaming_service.get_piece_availability(info_hash, position)
            return {
                "success": True, 
                "message": f"Seeking configure a {position*100:.1f}%",
                "availability": availability,
                "immediate_playback": availability.get("available", False)
            }
        else:
            raise HTTPException(status_code=404, detail="Torrent non trouve ou metadonnees non disponibles")
    except Exception as e:
        logger.error(f"Erreur seeking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/streaming/availability/{info_hash}")
async def check_availability(info_hash: str, position: float = Query(0.0, description="Position (0.0-1.0)")):
    """Verifie la disponibilite des pieces pour une position donnee"""
    try:
        availability = real_streaming_service.get_piece_availability(info_hash, position)
        return {
            "success": True,
            "info_hash": info_hash,
            "position": position,
            **availability
        }
    except Exception as e:
        logger.error(f"Erreur verification disponibilite: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/streaming/watch/{info_hash}", response_class=HTMLResponse)
async def watch_streaming(info_hash: str):
    """Page de lecture streaming"""
    info = real_streaming_service.get_streaming_info(info_hash)
    if not info:
        raise HTTPException(status_code=404, detail="Torrent non trouve")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>StreamTV - {info['title']}</title>
        <meta charset="UTF-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ background: #000; color: #fff; font-family: Arial, sans-serif; }}
            .container {{ width: 100vw; height: 100vh; display: flex; flex-direction: column; }}
            .header {{ background: #1a1a1a; padding: 15px; display: flex; justify-content: space-between; align-items: center; }}
            .player {{ flex: 1; position: relative; display: flex; align-items: center; justify-content: center; }}
            .loading {{ text-align: center; }}
            .progress {{ width: 400px; height: 8px; background: #333; border-radius: 4px; margin: 20px auto; }}
            .progress-bar {{ height: 100%; background: linear-gradient(45deg, #e50914, #ff6b6b); border-radius: 4px; width: 0%; transition: width 0.3s; }}
            video {{ width: 100%; height: 100%; }}
            .close-btn {{ background: #e50914; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>{info['title']}</h2>
                <button class="close-btn" onclick="window.close()"> Fermer</button>
            </div>
            
            <div class="player">
                <div id="loading" class="loading">
                    <h2>Preparation du streaming...</h2>
                    <p>{info['title']}</p>
                    <div class="progress">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    <p id="status">Connexion aux peers...</p>
                </div>
                
                <video id="player" controls style="display:none;" preload="metadata">
                    <source src="/api/streaming/video/{info_hash}" type="video/mp4">
                    Votre navigateur ne supporte pas la lecture video.
                </video>
            </div>
        </div>
        
        <script>
            const infoHash = '{info_hash}';
            let checkInterval;
            let player = null;
            
            // Nettoyage automatique quand la fenetre se ferme
            window.addEventListener('beforeunload', function() {{
                stopStreaming();
            }});
            
            // Nettoyage automatique quand l'utilisateur navigue ailleurs
            window.addEventListener('pagehide', function() {{
                stopStreaming();
            }});
            
            function stopStreaming() {{
                fetch(`/api/streaming/stop/${{infoHash}}`, {{ method: 'DELETE' }})
                .then(() => console.log('Streaming nettoye'))
                .catch(() => console.log('Erreur nettoyage'));
            }}
            
            let seekingTimeout = null;
            let lastSeekTime = 0;
            
            function onVideoSeeking() {{
                const video = document.getElementById('player');
                if (!video || !video.duration) return;
                
                const position = video.currentTime / video.duration;
                const now = Date.now();
                
                // ANTI-SPAM: eviter les seeking trop frequents (debouncing)
                if (now - lastSeekTime < 300) {{
                    console.log('Seeking ignore (anti-spam)');
                    return;
                }}
                lastSeekTime = now;
                
                // Annuler le timeout precedent
                if (seekingTimeout) {{
                    clearTimeout(seekingTimeout);
                }}
                
                console.log(`Seeking vers ${{(position*100).toFixed(1)}}%`);
                document.getElementById('status').textContent = `Navigation vers ${{(position*100).toFixed(1)}}%...`;
                
                // Delai pour eviter les seeking multiples rapides
                seekingTimeout = setTimeout(() => {{
                    fetch(`/api/streaming/seek/${{infoHash}}`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ position: position }})
                    }})
                    .then(r => r.json())
                    .then(data => {{
                        console.log(`Position ${{(position*100).toFixed(1)}}% configuree`);
                        
                        if (data.immediate_playback) {{
                            document.getElementById('status').textContent = `Pret ${{(position*100).toFixed(1)}}%`;
                        }} else {{
                            document.getElementById('status').textContent = `Chargement ${{(position*100).toFixed(1)}}%...`;
                        }}
                    }})
                    .catch(err => {{
                        console.log('Erreur seeking:', err);
                        document.getElementById('status').textContent = `Erreur position ${{(position*100).toFixed(1)}}%`;
                    }});
                }}, 150); // 150ms de delai
            }}
            
            function onVideoSeeked() {{
                console.log('Seeking termine');
                document.getElementById('status').textContent = ' Lecture en cours';
            }}
            
            function checkStatus() {{
                fetch(`/api/streaming/status/${{infoHash}}`)
                .then(r => r.json())
                .then(data => {{
                    const progress = data.progress || 0;
                    document.getElementById('progressBar').style.width = progress + '%';
                    document.getElementById('status').textContent = 
                        `Streaming: ${{progress}}% mis en cache - ${{data.can_stream ? 'Lecture disponible!' : 'Preparation...'}}`; 
                    
                    // Demarrage IMMEDIAT des 1% si metadonnees disponibles
                    if (data.can_stream && progress >= 1) {{
                        document.getElementById('loading').style.display = 'none';
                        const videoElement = document.getElementById('player');
                        videoElement.style.display = 'block';
                        
                        // Ajouter listeners pour seeking optimise avec gestion robuste
                        videoElement.addEventListener('seeking', onVideoSeeking);
                        videoElement.addEventListener('seeked', onVideoSeeked);
                        
                        // Eviter les rechargements intempestifs
                        videoElement.addEventListener('error', function(e) {{
                            console.log('Erreur video:', e);
                            document.getElementById('status').textContent = 'Erreur de lecture - Tentative de recuperation...';
                            
                            // Tentative de recuperation apres 2 secondes
                            setTimeout(() => {{
                                console.log('Tentative de recuperation...');
                                videoElement.load();
                            }}, 2000);
                        }});
                        
                        // Gerer la mise en pause/lecture pour eviter le retour au debut
                        videoElement.addEventListener('pause', function() {{
                            console.log('Video en pause');
                            document.getElementById('status').textContent = 'En pause';
                        }});
                        
                        videoElement.addEventListener('play', function() {{
                            console.log('Reprise de la lecture');
                            document.getElementById('status').textContent = 'Lecture en cours';
                        }});
                        
                        // Charger la video SEULEMENT au debut (pas lors des seeking)
                        if (!videoElement.src || videoElement.readyState === 0) {{
                            console.log('Initialisation du lecteur video');
                            videoElement.load();
                        }}
                        
                        clearInterval(checkInterval);
                    }}
                }})
                .catch(() => console.log('Status check error'));
            }}
            
            checkInterval = setInterval(checkStatus, 2000);
            checkStatus();
        </script>
    </body>
    </html>
    """

def get_video_content_type(file_path: str) -> str:
    """Detecte le Content-Type correct selon l'extension du fichier"""
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.wmv': 'video/x-ms-wmv',
        '.flv': 'video/x-flv',
        '.m4v': 'video/x-m4v',
    }
    return content_types.get(ext, 'video/mp4')

@app.get("/api/streaming/video/{info_hash}")
async def stream_video(info_hash: str, request: Request):
    """Stream du fichier video avec support HTTP Range pour seeking"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Fichier video non disponible")

    # Taille du fichier
    file_size = os.path.getsize(video_path)
    content_type = get_video_content_type(video_path)

    # Headers Range
    range_header = request.headers.get('Range')

    if range_header:
        # Parse Range header (ex: "bytes=0-1023")
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else file_size - 1
            end = min(end, file_size - 1)

            content_length = end - start + 1

            def generate_range():
                with open(video_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                generate_range(),
                status_code=206,  # Partial Content
                headers={
                    'Content-Type': content_type,
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(content_length),
                    'Content-Range': f'bytes {start}-{end}/{file_size}'
                }
            )
        except (ValueError, IndexError):
            # Range header malforme, retourner le fichier complet
            pass

    # Stream complet si pas de Range header
    def generate_full():
        with open(video_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        generate_full(),
        headers={
            'Content-Type': content_type,
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size)
        }
    )

# Gestionnaire de transcodage fichier avec progression reelle
class FileTranscodeManager:
    def __init__(self, max_concurrent: int = 2, cache_dir: str = "/tmp/streamtv_transcoded"):
        self.jobs: Dict[str, dict] = {}  # info_hash -> job info
        self.max_concurrent = max_concurrent
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def get_video_duration(self, video_path: str) -> float:
        """Obtient la duree de la video avec ffprobe"""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except:
            return 0

    def cancel_for_client(self, client_id: str):
        """Annule les jobs du client"""
        for info_hash, job in list(self.jobs.items()):
            if job.get('client_id') == client_id and not job.get('completed'):
                self._kill_job(info_hash)

    def _kill_job(self, info_hash: str):
        """Tue un job en cours"""
        if info_hash in self.jobs:
            job = self.jobs[info_hash]
            proc = job.get('process')
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except:
                    proc.kill()

    def get_active_count(self) -> int:
        """Compte les transcodages actifs"""
        return sum(1 for j in self.jobs.values()
                   if not j.get('completed') and not j.get('error'))

    def is_ready(self, info_hash: str) -> bool:
        """Verifie si le transcodage est termine"""
        if info_hash not in self.jobs:
            return False
        job = self.jobs[info_hash]
        # Verifier si process termine
        proc = job.get('process')
        if proc and proc.poll() is not None:
            if proc.returncode == 0:
                job['completed'] = True
            else:
                job['error'] = True
        return job.get('completed', False)

    def start_transcode(self, info_hash: str, source_path: str, client_id: str) -> dict:
        """Demarre le transcodage complet en arriere-plan"""
        # Annuler ancien job du client
        self.cancel_for_client(client_id)

        # Deja termine?
        if self.is_ready(info_hash):
            return {"status": "ready", "progress": 100}

        # Deja en cours?
        if info_hash in self.jobs and not self.jobs[info_hash].get('error'):
            job = self.jobs[info_hash]
            if job.get('process') and job['process'].poll() is None:
                job['client_id'] = client_id
                return {"status": "transcoding", "progress": job.get('progress', 0)}

        # Limite atteinte?
        if self.get_active_count() >= self.max_concurrent:
            return {"status": "busy", "message": "Serveur occupe"}

        # Obtenir duree source
        duration = self.get_video_duration(source_path)

        # Fichier sortie
        output_path = os.path.join(self.cache_dir, f"{info_hash}_aac.mp4")
        progress_path = os.path.join(self.cache_dir, f"{info_hash}_progress.txt")

        # Supprimer anciens fichiers
        for f in [output_path, progress_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

        # Commande ffmpeg avec progression (optimisee)
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-hide_banner',
            '-threads', '0',           # Utiliser tous les CPU cores
            '-hwaccel', 'auto',        # Auto-detect acceleration si disponible
            '-i', source_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ac', '2',
            '-threads', '0',           # Aussi pour l'encodage
            '-movflags', '+faststart',
            '-progress', progress_path,
            '-f', 'mp4',
            output_path
        ]

        logger.info(f"Demarrage transcodage complet: {info_hash}")

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        self.jobs[info_hash] = {
            'process': process,
            'client_id': client_id,
            'output_path': output_path,
            'progress_path': progress_path,
            'source_path': source_path,
            'duration': duration,
            'progress': 0,
            'completed': False,
            'error': False
        }

        return {"status": "started", "duration": duration}

    def get_progress(self, info_hash: str) -> dict:
        """Obtient la progression du transcodage"""
        if info_hash not in self.jobs:
            return {"status": "not_found"}

        job = self.jobs[info_hash]

        if job.get('error'):
            return {"status": "error"}

        # Verifier si vraiment termine (process termine + fichier valide)
        if self.is_ready(info_hash):
            output_path = job.get('output_path')
            if output_path and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                # Verifier que le fichier a une taille raisonnable (> 1MB)
                if size > 1024 * 1024:
                    return {
                        "status": "ready",
                        "progress": 100,
                        "size_mb": round(size / 1024 / 1024, 1)
                    }
            # Si fichier pas pret, continuer a afficher transcoding
            job['completed'] = False

        # Lire progression depuis fichier ffmpeg
        progress_path = job.get('progress_path')
        progress = 0
        current_time = 0

        if progress_path and os.path.exists(progress_path):
            try:
                with open(progress_path, 'r') as f:
                    content = f.read()
                    # Chercher out_time_ms ou out_time
                    for line in content.split('\n'):
                        if line.startswith('out_time_ms='):
                            current_time = int(line.split('=')[1]) / 1000000  # microsecondes -> secondes
                        elif line.startswith('out_time='):
                            # Format HH:MM:SS.ms
                            time_str = line.split('=')[1].strip()
                            if ':' in time_str:
                                parts = time_str.split(':')
                                if len(parts) == 3:
                                    h, m, s = parts
                                    current_time = int(h) * 3600 + int(m) * 60 + float(s)

                    duration = job.get('duration', 0)
                    if duration > 0 and current_time > 0:
                        progress = min(99, int((current_time / duration) * 100))
            except:
                pass

        job['progress'] = progress

        # Taille actuelle
        output_path = job.get('output_path')
        size = os.path.getsize(output_path) if output_path and os.path.exists(output_path) else 0

        return {
            "status": "transcoding",
            "progress": progress,
            "size_mb": round(size / 1024 / 1024, 1),
            "current_time": round(current_time, 1),
            "duration": round(job.get('duration', 0), 1)
        }

    def get_transcoded_path(self, info_hash: str) -> Optional[str]:
        """Retourne le chemin si pret"""
        if self.is_ready(info_hash):
            return self.jobs[info_hash].get('output_path')
        return None

    def get_transcoded_path_progressive(self, info_hash: str) -> Optional[str]:
        """Retourne le chemin meme si transcodage en cours (pour streaming progressif)"""
        if info_hash not in self.jobs:
            return None
        output_path = self.jobs[info_hash].get('output_path')
        if output_path and os.path.exists(output_path):
            return output_path
        return None

    def get_safe_size(self, info_hash: str) -> int:
        """Retourne la taille safe a lire (evite les derniers bytes en cours d'ecriture)"""
        if info_hash not in self.jobs:
            return 0
        output_path = self.jobs[info_hash].get('output_path')
        if not output_path or not os.path.exists(output_path):
            return 0
        # Laisser une marge de 1MB pour eviter de lire des donnees incompletes
        actual_size = os.path.getsize(output_path)
        if self.is_ready(info_hash):
            return actual_size  # Fichier complet
        return max(0, actual_size - 1024 * 1024)  # 1MB de marge

    def cleanup_old(self, max_jobs: int = 5):
        """Nettoie les anciens jobs"""
        completed = [(h, j) for h, j in self.jobs.items() if j.get('completed')]
        if len(completed) > max_jobs:
            for info_hash, job in completed[:-max_jobs]:
                output = job.get('output_path')
                progress = job.get('progress_path')
                for f in [output, progress]:
                    if f and os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
                del self.jobs[info_hash]

# Instance globale
transcode_manager = FileTranscodeManager(max_concurrent=2)

# ============================================
# AUDIO CHUNKS - Audio instantané avec seeking
# ============================================

class ChunkedAudioManager:
    """Gestionnaire d'audio par chunks pour seeking instantané"""

    def __init__(self, chunk_duration: int = 90, cache_dir: str = "/tmp/streamtv_audio_chunks", max_cache_size: int = 20):
        self.chunk_duration = chunk_duration  # 90 secondes par chunk
        self.cache_dir = cache_dir
        self.max_cache_size = max_cache_size  # Max chunks en cache par vidéo
        self.cache: Dict[str, OrderedDict] = {}  # info_hash -> OrderedDict[chunk_id, bytes]
        self.video_durations: Dict[str, float] = {}
        self.active_processes: Dict[str, subprocess.Popen] = {}
        os.makedirs(cache_dir, exist_ok=True)

    def get_video_duration(self, video_path: str, info_hash: str) -> float:
        """Obtient la durée de la vidéo avec ffprobe"""
        if info_hash in self.video_durations:
            return self.video_durations[info_hash]
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip())
            self.video_durations[info_hash] = duration
            return duration
        except:
            return 0

    def get_chunk_count(self, info_hash: str) -> int:
        """Retourne le nombre total de chunks pour une vidéo"""
        duration = self.video_durations.get(info_hash, 0)
        if duration <= 0:
            return 0
        return int(duration // self.chunk_duration) + 1

    def get_cache_key(self, info_hash: str, chunk_id: int) -> str:
        return f"{info_hash}:{chunk_id}"

    def get_chunk_file_path(self, info_hash: str, chunk_id: int) -> str:
        """Chemin du fichier cache pour un chunk audio"""
        return os.path.join(self.cache_dir, f"{info_hash}_audio_{chunk_id}.aac")

    def is_chunk_cached(self, info_hash: str, chunk_id: int) -> bool:
        """Vérifie si un chunk est en cache (mémoire ou disque)"""
        # Vérifier cache mémoire
        if info_hash in self.cache and chunk_id in self.cache[info_hash]:
            return True
        # Vérifier cache disque
        chunk_path = self.get_chunk_file_path(info_hash, chunk_id)
        return os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 100

    def get_cached_chunk(self, info_hash: str, chunk_id: int) -> Optional[bytes]:
        """Récupère un chunk depuis le cache"""
        # Cache mémoire
        if info_hash in self.cache and chunk_id in self.cache[info_hash]:
            # Move to end (LRU)
            self.cache[info_hash].move_to_end(chunk_id)
            return self.cache[info_hash][chunk_id]

        # Cache disque
        chunk_path = self.get_chunk_file_path(info_hash, chunk_id)
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 100:
            try:
                with open(chunk_path, 'rb') as f:
                    data = f.read()
                # Mettre en cache mémoire
                self._add_to_memory_cache(info_hash, chunk_id, data)
                return data
            except:
                pass
        return None

    def _add_to_memory_cache(self, info_hash: str, chunk_id: int, data: bytes):
        """Ajoute au cache mémoire avec gestion LRU"""
        if info_hash not in self.cache:
            self.cache[info_hash] = OrderedDict()

        self.cache[info_hash][chunk_id] = data
        self.cache[info_hash].move_to_end(chunk_id)

        # Limiter la taille du cache
        while len(self.cache[info_hash]) > self.max_cache_size:
            self.cache[info_hash].popitem(last=False)

    def transcode_chunk(self, info_hash: str, video_path: str, chunk_id: int) -> Optional[bytes]:
        """Transcode un chunk audio (90s) - très rapide (~1-2 sec)"""
        # Vérifier cache d'abord
        cached = self.get_cached_chunk(info_hash, chunk_id)
        if cached:
            return cached

        # Calculer les temps
        start_time = chunk_id * self.chunk_duration
        duration = self.get_video_duration(video_path, info_hash)

        if start_time >= duration:
            return None

        actual_duration = min(self.chunk_duration, duration - start_time)
        chunk_path = self.get_chunk_file_path(info_hash, chunk_id)

        # FFmpeg: extraire SEULEMENT l'audio, transcoder en AAC
        # -ss avant -i = seek rapide (keyframe-based)
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-ss', str(start_time),
            '-i', video_path,
            '-t', str(actual_duration),
            '-vn',  # Pas de vidéo - audio seulement!
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ac', '2',
            '-f', 'adts',  # Format AAC brut (streaming-friendly)
            chunk_path
        ]

        logger.info(f"Audio chunk {chunk_id}: {start_time:.0f}s-{start_time + actual_duration:.0f}s")

        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=30)

            if result.returncode == 0 and os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 100:
                with open(chunk_path, 'rb') as f:
                    audio_data = f.read()

                # Mettre en cache mémoire
                self._add_to_memory_cache(info_hash, chunk_id, audio_data)

                logger.info(f"Audio chunk {chunk_id} prêt: {len(audio_data)} bytes")
                return audio_data
            else:
                stderr = result.stderr.decode() if result.stderr else ""
                logger.error(f"Erreur audio chunk {chunk_id}: {stderr[:200]}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout audio chunk {chunk_id}")
            return None
        except Exception as e:
            logger.error(f"Exception audio chunk {chunk_id}: {e}")
            return None

    def prefetch_chunks(self, info_hash: str, video_path: str, current_chunk: int, count: int = 2):
        """Précharge les chunks suivants en arrière-plan (non-bloquant)"""
        import threading

        def prefetch_worker():
            for i in range(1, count + 1):
                next_chunk = current_chunk + i
                if not self.is_chunk_cached(info_hash, next_chunk):
                    duration = self.video_durations.get(info_hash, 0)
                    if next_chunk * self.chunk_duration < duration:
                        self.transcode_chunk(info_hash, video_path, next_chunk)

        thread = threading.Thread(target=prefetch_worker, daemon=True)
        thread.start()

    def cleanup_old_chunks(self, info_hash: str, current_chunk: int, keep_range: int = 5):
        """Nettoie les anciens fichiers de chunks"""
        try:
            for f in os.listdir(self.cache_dir):
                if f.startswith(f"{info_hash}_audio_") and f.endswith(".aac"):
                    try:
                        chunk_num = int(f.replace(f"{info_hash}_audio_", "").replace(".aac", ""))
                        if abs(chunk_num - current_chunk) > keep_range:
                            os.remove(os.path.join(self.cache_dir, f))
                            # Aussi retirer du cache mémoire
                            if info_hash in self.cache and chunk_num in self.cache[info_hash]:
                                del self.cache[info_hash][chunk_num]
                    except:
                        pass
        except:
            pass

    def get_info(self, info_hash: str, video_path: str) -> dict:
        """Retourne les infos pour le frontend"""
        duration = self.get_video_duration(video_path, info_hash)
        chunk_count = int(duration // self.chunk_duration) + 1 if duration > 0 else 0

        return {
            "info_hash": info_hash,
            "total_duration": duration,
            "chunk_duration": self.chunk_duration,
            "chunk_count": chunk_count,
            "duration_formatted": f"{int(duration//60)}:{int(duration%60):02d}"
        }

# Instance globale audio chunks
audio_chunk_manager = ChunkedAudioManager(chunk_duration=90, max_cache_size=10)

# Gestionnaire de transcodage par chunks
class ChunkTranscodeManager:
    def __init__(self, chunk_duration: int = 60, cache_dir: str = "/tmp/streamtv_chunks"):
        self.chunk_duration = chunk_duration  # Duree d'un chunk en secondes
        self.cache_dir = cache_dir
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.video_durations: Dict[str, float] = {}
        os.makedirs(cache_dir, exist_ok=True)

    def get_video_duration(self, video_path: str, info_hash: str) -> float:
        """Obtient la duree avec ffprobe"""
        if info_hash in self.video_durations:
            return self.video_durations[info_hash]
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip())
            self.video_durations[info_hash] = duration
            return duration
        except:
            return 0

    def get_chunk_path(self, info_hash: str, chunk_index: int) -> str:
        """Chemin du fichier chunk"""
        return os.path.join(self.cache_dir, f"{info_hash}_chunk_{chunk_index}.mp4")

    def is_chunk_ready(self, info_hash: str, chunk_index: int) -> bool:
        """Verifie si un chunk est pret"""
        chunk_path = self.get_chunk_path(info_hash, chunk_index)
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 10000:
            return True
        return False

    def cancel_for_client(self, client_id: str):
        """Annule le transcodage en cours"""
        if client_id in self.active_processes:
            proc = self.active_processes[client_id]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except:
                    proc.kill()
            del self.active_processes[client_id]

    def transcode_chunk(self, info_hash: str, video_path: str, start_time: float, client_id: str) -> dict:
        """Transcode un chunk de video"""
        # Annuler ancien transcodage du client
        self.cancel_for_client(client_id)

        # Calculer l'index du chunk
        chunk_index = int(start_time // self.chunk_duration)
        chunk_start = chunk_index * self.chunk_duration
        chunk_path = self.get_chunk_path(info_hash, chunk_index)

        # Si deja pret, retourner
        if self.is_chunk_ready(info_hash, chunk_index):
            return {
                "status": "ready",
                "chunk_index": chunk_index,
                "chunk_path": chunk_path,
                "start_time": chunk_start,
                "duration": self.chunk_duration
            }

        # Obtenir duree totale
        total_duration = self.get_video_duration(video_path, info_hash)
        actual_chunk_duration = min(self.chunk_duration, total_duration - chunk_start)

        if actual_chunk_duration <= 0:
            return {"status": "error", "message": "Position hors limites"}

        # Supprimer ancien fichier partiel
        if os.path.exists(chunk_path):
            try:
                os.remove(chunk_path)
            except:
                pass

        # Commande ffmpeg pour transcoder le chunk
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-ss', str(chunk_start),
            '-i', video_path,
            '-t', str(actual_chunk_duration),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ac', '2',
            '-movflags', '+faststart',
            '-f', 'mp4',
            chunk_path
        ]

        logger.info(f"Transcodage chunk {chunk_index} ({chunk_start}s-{chunk_start+actual_chunk_duration}s) pour {info_hash}")

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        self.active_processes[client_id] = process

        # Attendre la fin (chunk = rapide, ~2-5 secondes)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            return {"status": "error", "message": "Timeout transcodage"}

        if process.returncode == 0 and os.path.exists(chunk_path):
            return {
                "status": "ready",
                "chunk_index": chunk_index,
                "chunk_path": chunk_path,
                "start_time": chunk_start,
                "duration": actual_chunk_duration,
                "total_duration": total_duration
            }
        else:
            stderr = process.stderr.read().decode() if process.stderr else ""
            logger.error(f"Erreur transcodage chunk: {stderr[:200]}")
            return {"status": "error", "message": "Erreur ffmpeg"}

    def cleanup_old_chunks(self, info_hash: str, keep_around: int = None, max_chunks: int = 10):
        """Nettoie les anciens chunks"""
        try:
            chunks = []
            for f in os.listdir(self.cache_dir):
                if f.startswith(f"{info_hash}_chunk_") and f.endswith(".mp4"):
                    path = os.path.join(self.cache_dir, f)
                    # Extraire l'index
                    idx = int(f.split("_chunk_")[1].replace(".mp4", ""))
                    chunks.append((idx, path, os.path.getmtime(path)))

            # Garder les chunks autour de la position actuelle
            if keep_around is not None and len(chunks) > max_chunks:
                chunks.sort(key=lambda x: abs(x[0] - keep_around))
                to_remove = chunks[max_chunks:]
                for idx, path, _ in to_remove:
                    try:
                        os.remove(path)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Erreur cleanup chunks: {e}")

# Instance globale
chunk_manager = ChunkTranscodeManager(chunk_duration=60)

# ============================================
# HLS STREAMING - Solution professionnelle
# ============================================
from concurrent.futures import ThreadPoolExecutor
import threading

class HLSManager:
    """Gestionnaire HLS avec transcodage parallèle et pré-buffering"""

    def __init__(self, segment_duration: int = 10, cache_dir: str = "/tmp/streamtv_hls"):
        self.segment_duration = segment_duration
        self.cache_dir = cache_dir
        self.video_info: Dict[str, dict] = {}
        self.transcoding_segments: Dict[str, set] = {}  # info_hash -> set of segment indices being transcoded
        self.segment_locks: Dict[str, threading.Lock] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)  # 4 transcodes parallèles
        os.makedirs(cache_dir, exist_ok=True)

    def _get_lock(self, info_hash: str) -> threading.Lock:
        if info_hash not in self.segment_locks:
            self.segment_locks[info_hash] = threading.Lock()
        return self.segment_locks[info_hash]

    def get_video_info(self, info_hash: str, video_path: str) -> dict:
        """Obtient les infos de la video"""
        if info_hash in self.video_info:
            return self.video_info[info_hash]

        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=15)
            duration = float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Erreur ffprobe: {e}")
            duration = 0

        num_segments = int(duration // self.segment_duration) + (1 if duration % self.segment_duration > 0 else 0)

        info = {
            'duration': duration,
            'num_segments': num_segments,
            'segment_duration': self.segment_duration,
            'video_path': video_path
        }
        self.video_info[info_hash] = info
        self.transcoding_segments[info_hash] = set()

        logger.info(f"HLS info: {info_hash[:8]}... {duration:.0f}s, {num_segments} segments")
        return info

    def generate_playlist(self, info_hash: str, video_path: str) -> str:
        """Génère le fichier playlist .m3u8"""
        info = self.get_video_info(info_hash, video_path)
        duration = info['duration']
        num_segments = info['num_segments']
        seg_duration = self.segment_duration

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{seg_duration}",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
        ]

        for i in range(num_segments):
            seg_len = duration - (i * seg_duration) if i == num_segments - 1 else seg_duration
            lines.append(f"#EXTINF:{seg_len:.3f},")
            lines.append(f"segment_{i}.ts")

        lines.append("#EXT-X-ENDLIST")
        return "\n".join(lines)

    def get_segment_path(self, info_hash: str, segment_index: int) -> str:
        segment_dir = os.path.join(self.cache_dir, info_hash)
        os.makedirs(segment_dir, exist_ok=True)
        return os.path.join(segment_dir, f"segment_{segment_index}.ts")

    def is_segment_ready(self, info_hash: str, segment_index: int) -> bool:
        path = self.get_segment_path(info_hash, segment_index)
        return os.path.exists(path) and os.path.getsize(path) > 1000

    def _transcode_one_segment(self, info_hash: str, segment_index: int, video_path: str,
                                start_time: float, actual_duration: float) -> Optional[str]:
        """Transcode un segment (appelé dans un thread)"""
        segment_path = self.get_segment_path(info_hash, segment_index)

        # Double-check si déjà prêt
        if self.is_segment_ready(info_hash, segment_index):
            return segment_path

        # -ss AVANT -i = seek rapide (keyframe-based)
        # Simple et rapide - priorité à la réactivité
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-ss', str(start_time),  # AVANT -i = seek rapide!
            '-i', video_path,
            '-t', str(actual_duration),
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
            '-f', 'mpegts',
            '-mpegts_copyts', '1',
            segment_path
        ]

        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and os.path.exists(segment_path) and os.path.getsize(segment_path) > 500:
                return segment_path
            else:
                # Retry avec re-encodage si copy échoue
                ffmpeg_cmd_retry = [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-ss', str(start_time),
                    '-i', video_path,
                    '-t', str(actual_duration),
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
                    '-f', 'mpegts',
                    segment_path
                ]
                result = subprocess.run(ffmpeg_cmd_retry, capture_output=True, timeout=30)
                if result.returncode == 0 and os.path.exists(segment_path):
                    return segment_path
                return None
        except Exception as e:
            logger.error(f"Erreur segment {segment_index}: {e}")
            return None
        finally:
            # Retirer de la liste des segments en cours
            if info_hash in self.transcoding_segments:
                self.transcoding_segments[info_hash].discard(segment_index)

    def transcode_segment(self, info_hash: str, segment_index: int) -> Optional[str]:
        """Transcode un segment et pré-transcode les suivants"""
        if info_hash not in self.video_info:
            return None

        info = self.video_info[info_hash]
        video_path = info['video_path']
        duration = info['duration']
        seg_duration = self.segment_duration
        num_segments = info['num_segments']

        # Si segment déjà prêt, retourner immédiatement
        if self.is_segment_ready(info_hash, segment_index):
            # Pré-transcoder les 5 segments suivants (20s d'avance)
            self._prefetch_segments(info_hash, segment_index + 1, 5)
            return self.get_segment_path(info_hash, segment_index)

        start_time = segment_index * seg_duration
        if start_time >= duration:
            return None
        actual_duration = min(seg_duration, duration - start_time)

        # Marquer comme en cours de transcodage
        if info_hash not in self.transcoding_segments:
            self.transcoding_segments[info_hash] = set()

        # Attendre si ce segment est déjà en cours de transcodage
        max_wait = 10  # Max 10s d'attente
        waited = 0
        while segment_index in self.transcoding_segments.get(info_hash, set()) and waited < max_wait:
            time.sleep(0.3)
            waited += 0.3
            if self.is_segment_ready(info_hash, segment_index):
                return self.get_segment_path(info_hash, segment_index)

        # Transcoder ce segment
        self.transcoding_segments[info_hash].add(segment_index)
        logger.info(f"HLS: Segment {segment_index} ({start_time:.0f}s)")

        result = self._transcode_one_segment(info_hash, segment_index, video_path, start_time, actual_duration)

        # Pré-transcoder les 5 segments suivants (20s d'avance)
        self._prefetch_segments(info_hash, segment_index + 1, 5)

        return result

    def _prefetch_segments(self, info_hash: str, start_index: int, count: int):
        """Pré-transcode plusieurs segments en arrière-plan"""
        if info_hash not in self.video_info:
            return

        info = self.video_info[info_hash]
        video_path = info['video_path']
        duration = info['duration']
        seg_duration = self.segment_duration
        num_segments = info['num_segments']

        for i in range(count):
            seg_idx = start_index + i
            if seg_idx >= num_segments:
                break
            if self.is_segment_ready(info_hash, seg_idx):
                continue
            if seg_idx in self.transcoding_segments.get(info_hash, set()):
                continue

            start_time = seg_idx * seg_duration
            actual_duration = min(seg_duration, duration - start_time)

            self.transcoding_segments[info_hash].add(seg_idx)
            self.executor.submit(
                self._transcode_one_segment,
                info_hash, seg_idx, video_path, start_time, actual_duration
            )

    def cleanup_old_segments(self, info_hash: str, current_segment: int, keep_range: int = 20):
        """Nettoie les anciens segments (garde current ± keep_range)"""
        try:
            segment_dir = os.path.join(self.cache_dir, info_hash)
            if not os.path.exists(segment_dir):
                return

            for f in os.listdir(segment_dir):
                if f.startswith("segment_") and f.endswith(".ts"):
                    idx = int(f.replace("segment_", "").replace(".ts", ""))
                    if abs(idx - current_segment) > keep_range:
                        try:
                            os.remove(os.path.join(segment_dir, f))
                        except:
                            pass
        except:
            pass

# Instance globale HLS
hls_manager = HLSManager(segment_duration=6)  # 6s = équilibre qualité/réactivité

# ============================================
# ENDPOINTS HLS
# ============================================

@app.get("/api/hls/{info_hash}/playlist.m3u8")
async def hls_playlist(info_hash: str):
    """Retourne le playlist HLS M3U8"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    playlist = hls_manager.generate_playlist(info_hash, video_path)

    return Response(
        content=playlist,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Content-Type": "application/vnd.apple.mpegurl",
            "Cache-Control": "no-cache"
        }
    )

@app.get("/api/hls/{info_hash}/segment_{segment_index}.ts")
async def hls_segment(info_hash: str, segment_index: int):
    """Retourne un segment HLS (transcode si nécessaire)"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    # S'assurer que les infos sont chargées
    hls_manager.get_video_info(info_hash, video_path)

    # Transcoder le segment
    segment_path = hls_manager.transcode_segment(info_hash, segment_index)

    if not segment_path or not os.path.exists(segment_path):
        raise HTTPException(status_code=500, detail="Erreur transcodage segment")

    # Nettoyer les anciens segments
    hls_manager.cleanup_old_segments(info_hash, segment_index)

    # Streamer le segment
    file_size = os.path.getsize(segment_path)

    def generate():
        with open(segment_path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        generate(),
        media_type="video/mp2t",
        headers={
            "Content-Type": "video/mp2t",
            "Content-Length": str(file_size),
            "Cache-Control": "max-age=3600"
        }
    )

@app.get("/api/hls/{info_hash}/info")
async def hls_info(info_hash: str):
    """Retourne les infos HLS de la video"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    info = hls_manager.get_video_info(info_hash, video_path)

    return {
        "info_hash": info_hash,
        "duration": info['duration'],
        "duration_formatted": f"{int(info['duration']//60)}:{int(info['duration']%60):02d}",
        "num_segments": info['num_segments'],
        "segment_duration": info['segment_duration']
    }

# ============================================
# FIN HLS
# ============================================

# ============================================
# AUDIO CHUNKS ENDPOINTS - Audio instantané
# ============================================

@app.get("/api/audio/chunk/{info_hash}/{chunk_id}")
async def get_audio_chunk(info_hash: str, chunk_id: int, request: Request):
    """Retourne un chunk audio de 90 secondes (transcodé à la demande)"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    # Transcoder le chunk (très rapide: ~1-2 sec pour 90s d'audio)
    audio_data = audio_chunk_manager.transcode_chunk(info_hash, video_path, chunk_id)

    if not audio_data:
        raise HTTPException(status_code=500, detail="Erreur transcodage audio")

    # Précharger les 2 chunks suivants en arrière-plan
    audio_chunk_manager.prefetch_chunks(info_hash, video_path, chunk_id, count=2)

    # Nettoyer les vieux chunks (garder ±5 autour du courant)
    audio_chunk_manager.cleanup_old_chunks(info_hash, chunk_id, keep_range=5)

    return Response(
        content=audio_data,
        media_type="audio/aac",
        headers={
            "Content-Type": "audio/aac",
            "Content-Length": str(len(audio_data)),
            "X-Chunk-Id": str(chunk_id),
            "X-Chunk-Duration": str(audio_chunk_manager.chunk_duration),
            "X-Chunk-Start": str(chunk_id * audio_chunk_manager.chunk_duration),
            "Cache-Control": "max-age=3600"  # Cache 1h
        }
    )

@app.get("/api/audio/info/{info_hash}")
async def get_audio_info(info_hash: str):
    """Retourne les infos audio pour le frontend"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    info = audio_chunk_manager.get_info(info_hash, video_path)
    return info

@app.get("/api/audio/status/{info_hash}")
async def get_audio_status(info_hash: str, chunk_id: int = 0):
    """Vérifie si un chunk audio est prêt"""
    is_cached = audio_chunk_manager.is_chunk_cached(info_hash, chunk_id)
    return {
        "info_hash": info_hash,
        "chunk_id": chunk_id,
        "is_ready": is_cached,
        "chunk_duration": audio_chunk_manager.chunk_duration
    }

# ============================================
# FIN AUDIO CHUNKS
# ============================================

@app.post("/api/streaming/transcode/start/{info_hash}")
async def start_transcode(info_hash: str, request: Request):
    """Demarre le transcodage complet en arriere-plan"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Fichier video non disponible")

    if not shutil.which('ffmpeg'):
        raise HTTPException(status_code=500, detail="ffmpeg non disponible")

    client_id = request.client.host if request.client else "unknown"
    transcode_manager.cleanup_old()

    result = transcode_manager.start_transcode(info_hash, video_path, client_id)
    return result

@app.get("/api/streaming/transcode/progress/{info_hash}")
async def get_transcode_progress(info_hash: str):
    """Retourne la progression du transcodage"""
    return transcode_manager.get_progress(info_hash)

@app.get("/api/streaming/transcode/{info_hash}")
async def stream_transcoded(info_hash: str, request: Request):
    """Stream le fichier transcode (son + seeking) - supporte streaming progressif"""
    # Utiliser le path progressif (permet streaming pendant transcodage)
    transcoded_path = transcode_manager.get_transcoded_path_progressive(info_hash)

    if not transcoded_path or not os.path.exists(transcoded_path):
        raise HTTPException(status_code=404, detail="Transcodage non demarre")

    # Utiliser la taille safe pour eviter de lire des donnees incompletes
    safe_size = transcode_manager.get_safe_size(info_hash)
    if safe_size <= 0:
        raise HTTPException(status_code=503, detail="Transcodage en cours, reessayez")

    range_header = request.headers.get('Range')

    if range_header:
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else safe_size - 1
            # Limiter au safe_size
            end = min(end, safe_size - 1)
            if start >= safe_size:
                # Demande au-dela de ce qui est disponible
                raise HTTPException(status_code=416, detail="Range non disponible")
            content_length = end - start + 1

            def generate_range():
                with open(transcoded_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                generate_range(),
                status_code=206,
                headers={
                    'Content-Type': 'video/mp4',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(content_length),
                    'Content-Range': f'bytes {start}-{end}/{safe_size}'
                }
            )
        except (ValueError, IndexError):
            pass

    def generate_full():
        with open(transcoded_path, 'rb') as f:
            bytes_read = 0
            while bytes_read < safe_size:
                chunk = f.read(min(8192, safe_size - bytes_read))
                if not chunk:
                    break
                bytes_read += len(chunk)
                yield chunk

    return StreamingResponse(
        generate_full(),
        headers={
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size)
        }
    )

@app.delete("/api/streaming/transcode/cancel")
async def cancel_transcode(request: Request):
    """Annule le transcodage en cours"""
    client_id = request.client.host if request.client else "unknown"
    transcode_manager.cancel_for_client(client_id)
    return {"status": "cancelled"}

# === STREAMING PAR CHUNKS (SON + SEEKING) ===

@app.get("/api/streaming/chunk/{info_hash}")
async def get_chunk(info_hash: str, request: Request, t: float = 0):
    """Transcode et stream un chunk de 60s a partir de la position t"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    client_id = request.client.host if request.client else "unknown"

    # Transcoder le chunk (bloquant mais rapide ~2-5s pour 60s de video)
    result = chunk_manager.transcode_chunk(info_hash, video_path, t, client_id)

    if result["status"] != "ready":
        raise HTTPException(status_code=500, detail=result.get("message", "Erreur"))

    chunk_path = result["chunk_path"]
    file_size = os.path.getsize(chunk_path)

    # Support Range requests pour seeking dans le chunk
    range_header = request.headers.get('Range')

    if range_header:
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if range_match[1] else file_size - 1
            end = min(end, file_size - 1)
            content_length = end - start + 1

            def generate_range():
                with open(chunk_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        data = f.read(chunk_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            return StreamingResponse(
                generate_range(),
                status_code=206,
                headers={
                    'Content-Type': 'video/mp4',
                    'Accept-Ranges': 'bytes',
                    'Content-Length': str(content_length),
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'X-Chunk-Start': str(result["start_time"]),
                    'X-Chunk-Duration': str(result["duration"]),
                    'X-Total-Duration': str(result.get("total_duration", 0))
                }
            )
        except:
            pass

    def generate_full():
        with open(chunk_path, 'rb') as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                yield data

    return StreamingResponse(
        generate_full(),
        headers={
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'X-Chunk-Start': str(result["start_time"]),
            'X-Chunk-Duration': str(result["duration"]),
            'X-Total-Duration': str(result.get("total_duration", 0))
        }
    )

@app.get("/api/streaming/chunk/info/{info_hash}")
async def get_chunk_info(info_hash: str):
    """Retourne les infos pour le streaming par chunks"""
    video_path = real_streaming_service.get_video_path(info_hash)

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video non disponible")

    duration = chunk_manager.get_video_duration(video_path, info_hash)
    chunk_count = int(duration // chunk_manager.chunk_duration) + 1

    return {
        "info_hash": info_hash,
        "total_duration": duration,
        "chunk_duration": chunk_manager.chunk_duration,
        "chunk_count": chunk_count,
        "duration_formatted": f"{int(duration//60)}:{int(duration%60):02d}"
    }

# Endpoints utilitaires
@app.get("/favicon.ico")
async def favicon():
    return Response(content=b'', media_type='image/x-icon')

@app.get("/placeholder-poster.svg")
async def placeholder_poster():
    """Placeholder SVG pour les posters manquants"""
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="450" viewBox="0 0 300 450" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="300" height="450" fill="#1a1a1a"/>
  <rect x="10" y="10" width="280" height="430" stroke="#333" stroke-width="2" fill="none"/>
  <text x="150" y="200" text-anchor="middle" fill="#666" font-family="Arial, sans-serif" font-size="24"></text>
  <text x="150" y="250" text-anchor="middle" fill="#666" font-family="Arial, sans-serif" font-size="14">Pas d'image</text>
  <text x="150" y="280" text-anchor="middle" fill="#666" font-family="Arial, sans-serif" font-size="12">disponible</text>
</svg>"""
    return Response(content=svg_content, media_type="image/svg+xml")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Demarrage StreamTV Production")
    logger.info("Streaming reel avec libtorrent active")
    logger.info("Interface: http://localhost:8000")
    
    
    uvicorn.run(
        "main_production:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Production mode
        log_level="info"
    )