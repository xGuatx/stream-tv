#!/usr/bin/env python3
"""
Scraper de fallback avec recherche en temps réel sur des APIs publiques
"""

import asyncio
import aiohttp
import logging
import re
from typing import List, Dict
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class SimpleFallbackScraper:
    """Scraper de fallback utilisant des APIs publiques"""

    def __init__(self):
        self.session = None
        self.trackers = [
            'udp://tracker.opentrackr.org:1337/announce',
            'udp://open.stealth.si:80/announce',
            'udp://tracker.torrent.eu.org:451/announce',
            'udp://tracker.openbittorrent.com:6969/announce',
            'udp://exodus.desync.com:6969/announce',
        ]

    async def _get_session(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=20)
            connector = aiohttp.TCPConnector(ssl=False, limit=10)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json,text/html,*/*',
                }
            )
        return self.session

    def _build_magnet(self, info_hash: str, name: str) -> str:
        """Construit un magnet link avec trackers"""
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote_plus(name)}"
        for tracker in self.trackers:
            magnet += f"&tr={quote_plus(tracker)}"
        return magnet

    async def search_piratebay_api(self, query: str) -> List[Dict]:
        """Recherche via API PirateBay (apibay.org)"""
        results = []
        try:
            session = await self._get_session()
            # API publique PirateBay
            url = f"https://apibay.org/q.php?q={quote_plus(query)}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    if isinstance(data, list):
                        for item in data[:20]:
                            if item.get('id') == '0':  # Pas de résultats
                                continue

                            info_hash = item.get('info_hash', '')
                            name = item.get('name', '')

                            if info_hash and len(info_hash) == 40:
                                results.append({
                                    'title': name,
                                    'magnet': self._build_magnet(info_hash, name),
                                    'size': int(item.get('size', 0)),
                                    'seeders': int(item.get('seeders', 0)),
                                    'leechers': int(item.get('leechers', 0)),
                                    'source': 'TPB',
                                    'quality': self._extract_quality(name),
                                    'language': self._detect_language(name),
                                    'relevance_score': 80.0
                                })

                    logger.info(f"PirateBay API: {len(results)} results for '{query}'")

        except Exception as e:
            logger.debug(f"PirateBay API error: {e}")

        return results

    async def search_eztv_all_pages(self, query: str) -> List[Dict]:
        """Recherche EZTV en parcourant plusieurs pages"""
        results = []
        query_words = query.lower().split()

        try:
            session = await self._get_session()

            # Parcourir plusieurs pages pour trouver des correspondances
            for page in range(1, 6):  # 5 pages = 500 torrents
                try:
                    url = f"https://eztv.re/api/get-torrents?limit=100&page={page}"

                    async with session.get(url) as response:
                        if response.status != 200:
                            break

                        data = await response.json()
                        torrents = data.get('torrents', [])

                        if not torrents:
                            break

                        for torrent in torrents:
                            title = torrent.get('title', '').lower()

                            # Vérifier correspondance
                            if any(word in title for word in query_words):
                                magnet = torrent.get('magnet_url', '')
                                seeds = torrent.get('seeds', 0)

                                if magnet and seeds > 0:
                                    results.append({
                                        'title': torrent.get('title', ''),
                                        'magnet': magnet,
                                        'size': torrent.get('size_bytes', 0),
                                        'seeders': seeds,
                                        'leechers': torrent.get('peers', 0),
                                        'source': 'EZTV',
                                        'quality': self._extract_quality(torrent.get('title', '')),
                                        'language': self._detect_language(torrent.get('title', '')),
                                        'relevance_score': 85.0
                                    })

                        # Si on a assez de résultats, arrêter
                        if len(results) >= 15:
                            break

                except Exception as e:
                    logger.debug(f"EZTV page {page} error: {e}")
                    break

            logger.info(f"EZTV search: {len(results)} results for '{query}'")

        except Exception as e:
            logger.debug(f"EZTV search error: {e}")

        return results

    async def search_solidtorrents(self, query: str) -> List[Dict]:
        """Recherche via SolidTorrents API"""
        results = []
        try:
            session = await self._get_session()
            url = f"https://solidtorrents.to/api/v1/search?q={quote_plus(query)}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    for item in data.get('results', [])[:20]:
                        info_hash = item.get('infohash', '')
                        title = item.get('title', '')

                        if info_hash:
                            results.append({
                                'title': title,
                                'magnet': self._build_magnet(info_hash, title),
                                'size': item.get('size', 0),
                                'seeders': item.get('swarm', {}).get('seeders', 0),
                                'leechers': item.get('swarm', {}).get('leechers', 0),
                                'source': 'SolidTorrents',
                                'quality': self._extract_quality(title),
                                'language': self._detect_language(title),
                                'relevance_score': 82.0
                            })

                    logger.info(f"SolidTorrents: {len(results)} results for '{query}'")

        except Exception as e:
            logger.debug(f"SolidTorrents error: {e}")

        return results

    async def search_content(self, query: str, limit: int = 20) -> List[Dict]:
        """Recherche avec fallback sur plusieurs sources"""
        query_clean = query.strip()

        logger.info(f"Fallback search: '{query_clean}'")

        # Rechercher en parallèle sur plusieurs sources
        tasks = [
            self.search_piratebay_api(query_clean),
            self.search_eztv_all_pages(query_clean),
            self.search_solidtorrents(query_clean),
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Agréger les résultats
        all_results = []
        for results in results_lists:
            if isinstance(results, list):
                all_results.extend(results)

        # Dédupliquer par hash
        seen_hashes = set()
        unique_results = []

        for result in all_results:
            magnet = result.get('magnet', '')
            hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)

            if hash_match:
                torrent_hash = hash_match.group(1).lower()
                if torrent_hash not in seen_hashes:
                    seen_hashes.add(torrent_hash)
                    unique_results.append(result)

        # Trier par seeders
        unique_results.sort(key=lambda x: x.get('seeders', 0), reverse=True)

        logger.info(f"Fallback found {len(unique_results)} unique results for '{query_clean}'")

        return unique_results[:limit]

    def _extract_quality(self, title: str) -> str:
        """Extrait la qualité du titre"""
        if not title:
            return 'Unknown'

        title_upper = title.upper()

        patterns = [
            (r'2160[PI]|4K|UHD', '2160p'),
            (r'1080[PI]', '1080p'),
            (r'720[PI]', '720p'),
            (r'480[PI]', '480p'),
            (r'BLURAY|BLU-RAY|BDRIP', 'BluRay'),
            (r'WEB-?DL', 'WEB-DL'),
            (r'WEBRIP', 'WEBRip'),
            (r'HDTV', 'HDTV'),
            (r'DVDRIP', 'DVDRip'),
            (r'\bCAM\b', 'CAM'),
        ]

        for pattern, quality in patterns:
            if re.search(pattern, title_upper):
                return quality

        return 'Unknown'

    def _detect_language(self, title: str) -> str:
        """Détecte la langue du titre"""
        title_upper = title.upper()

        french_patterns = [
            (r'\bTRUEFRENCH\b', 'TRUEFRENCH'),
            (r'\bVFF\b', 'VFF'),
            (r'\bVF\b(?!R)', 'VF'),
            (r'\bVOSTFR\b', 'VOSTFR'),
            (r'\bFRENCH\b', 'FRENCH'),
            (r'\bMULTI\b', 'MULTI'),
        ]

        for pattern, lang in french_patterns:
            if re.search(pattern, title_upper):
                return lang

        return 'ENG'

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None


# Instance globale
simple_fallback_scraper = SimpleFallbackScraper()
