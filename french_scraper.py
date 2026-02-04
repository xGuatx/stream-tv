"""
French Torrent Scraper - Optimisé pour le contenu francophone
Inspiré de torrentio-scraper avec sources françaises spécialisées
"""

import asyncio
import aiohttp
import json
import logging
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FrenchLanguageType(Enum):
    """Types de versions françaises avec priorité"""
    TRUEFRENCH = "TRUEFRENCH"      # Doublage professionnel haute qualité
    VFF = "VFF"                     # Version Française France
    VFQ = "VFQ"                     # Version Française Québec
    VF = "VF"                       # Version Française générique
    VOSTFR = "VOSTFR"              # VO Sous-titrée Français
    SUBFRENCH = "SUBFRENCH"        # Sous-titres français
    MULTI = "MULTI"                # Multi-audio (inclut souvent FR)
    FRENCH = "FRENCH"              # Générique français
    UNKNOWN = "UNKNOWN"            # Pas de version française détectée


@dataclass
class LanguageInfo:
    """Information détaillée sur la langue d'un torrent"""
    french_type: FrenchLanguageType
    is_french: bool
    is_dubbed: bool          # Doublé en français
    is_subbed: bool          # Sous-titré en français
    confidence: float        # Score de confiance 0-1
    original_language: str   # Langue originale si détectable


class FrenchLanguageDetector:
    """Détecteur avancé de langues françaises pour torrents"""

    # Patterns de détection avec priorité
    FRENCH_PATTERNS = [
        # TRUEFRENCH - Plus haute qualité
        (r'\bTRUEFRENCH\b', FrenchLanguageType.TRUEFRENCH, 1.0, True, False),
        (r'\bFRENCH\.?PROPER\b', FrenchLanguageType.TRUEFRENCH, 0.95, True, False),

        # VFF - Version Française France
        (r'\bVFF\b', FrenchLanguageType.VFF, 0.95, True, False),
        (r'\bFR\.?FR\b', FrenchLanguageType.VFF, 0.9, True, False),

        # VFQ - Version Française Québec
        (r'\bVFQ\b', FrenchLanguageType.VFQ, 0.9, True, False),
        (r'\bQUEBEC\b', FrenchLanguageType.VFQ, 0.85, True, False),

        # VF - Version Française générique
        (r'\bVF\b(?!R)', FrenchLanguageType.VF, 0.85, True, False),
        (r'\bVOF\b', FrenchLanguageType.VF, 0.85, True, False),  # Version Originale Française

        # VOSTFR - Sous-titré français
        (r'\bVOSTFR\b', FrenchLanguageType.VOSTFR, 0.9, False, True),
        (r'\bVOST\.FR\b', FrenchLanguageType.VOSTFR, 0.9, False, True),
        (r'\bST\.?FR\b', FrenchLanguageType.VOSTFR, 0.85, False, True),
        (r'\bSUBFRENCH\b', FrenchLanguageType.SUBFRENCH, 0.85, False, True),
        (r'\bSUB\.?FR\b', FrenchLanguageType.SUBFRENCH, 0.8, False, True),

        # MULTI - Multi-audio
        (r'\bMULTi\b', FrenchLanguageType.MULTI, 0.75, True, False),
        (r'\bMULTI\.?LANG\b', FrenchLanguageType.MULTI, 0.75, True, False),
        (r'\bML\b', FrenchLanguageType.MULTI, 0.6, True, False),

        # FRENCH générique
        (r'\bFRENCH\b', FrenchLanguageType.FRENCH, 0.7, True, False),
        (r'\bFR\b', FrenchLanguageType.FRENCH, 0.5, True, False),
        (r'[\[\(]FR[\]\)]', FrenchLanguageType.FRENCH, 0.6, True, False),
    ]

    # Patterns négatifs (indiquent que ce n'est PAS français)
    NON_FRENCH_PATTERNS = [
        r'\bENG(?:LISH)?\b',
        r'\bITA(?:LIAN)?\b',
        r'\bGER(?:MAN)?\b',
        r'\bSPA(?:NISH)?\b',
        r'\bPOR(?:TUGUESE)?\b',
        r'\bRUS(?:SIAN)?\b',
        r'\bJAP(?:ANESE)?\b',
        r'\bKOR(?:EAN)?\b',
        r'\bCHI(?:NESE)?\b',
    ]

    @classmethod
    def detect(cls, title: str) -> LanguageInfo:
        """Détecte la langue française dans un titre de torrent"""
        title_upper = title.upper()

        # Chercher le meilleur match français
        best_match = None
        best_confidence = 0.0
        is_dubbed = False
        is_subbed = False

        for pattern, lang_type, confidence, dubbed, subbed in cls.FRENCH_PATTERNS:
            if re.search(pattern, title_upper, re.IGNORECASE):
                if confidence > best_confidence:
                    best_match = lang_type
                    best_confidence = confidence
                    is_dubbed = dubbed
                    is_subbed = subbed

        # Vérifier les patterns négatifs (réduisent la confiance si pas de pattern français explicite)
        if best_confidence < 0.8:
            for neg_pattern in cls.NON_FRENCH_PATTERNS:
                if re.search(neg_pattern, title_upper):
                    best_confidence *= 0.5
                    break

        # Détecter la langue originale
        original_lang = "Unknown"
        if re.search(r'\bEN(?:G(?:LISH)?)?\b', title_upper):
            original_lang = "English"
        elif re.search(r'\bJAP|JPN\b', title_upper):
            original_lang = "Japanese"

        return LanguageInfo(
            french_type=best_match or FrenchLanguageType.UNKNOWN,
            is_french=best_match is not None,
            is_dubbed=is_dubbed,
            is_subbed=is_subbed,
            confidence=best_confidence,
            original_language=original_lang
        )

    @classmethod
    def get_french_priority_score(cls, lang_info: LanguageInfo) -> int:
        """Retourne un score de priorité pour les versions françaises (plus haut = meilleur)"""
        priority_map = {
            FrenchLanguageType.TRUEFRENCH: 100,
            FrenchLanguageType.VFF: 95,
            FrenchLanguageType.VFQ: 90,
            FrenchLanguageType.VF: 85,
            FrenchLanguageType.MULTI: 70,
            FrenchLanguageType.FRENCH: 65,
            FrenchLanguageType.VOSTFR: 60,
            FrenchLanguageType.SUBFRENCH: 55,
            FrenchLanguageType.UNKNOWN: 0,
        }
        base_score = priority_map.get(lang_info.french_type, 0)
        return int(base_score * lang_info.confidence)


class FrenchTorrentScraper:
    """Scraper optimisé pour sources françaises"""

    def __init__(self):
        self.session = None
        self.language_detector = FrenchLanguageDetector()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]

        # Trackers optimisés pour torrents français
        self.french_trackers = [
            'udp://tracker.opentrackr.org:1337/announce',
            'udp://open.stealth.si:80/announce',
            'udp://tracker.torrent.eu.org:451/announce',
            'udp://tracker.openbittorrent.com:6969/announce',
            'udp://opentracker.i2p.rocks:6969/announce',
            'udp://open.demonii.com:1337/announce',
            'udp://exodus.desync.com:6969/announce',
            'udp://tracker.moeking.me:6969/announce',
        ]

    async def _get_session(self):
        """Session HTTP optimisée"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(
                limit=30,
                verify_ssl=False,
                use_dns_cache=True,
                ttl_dns_cache=300
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': self.user_agents[0],
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }
            )
        return self.session

    def _build_magnet(self, info_hash: str, title: str) -> str:
        """Construit un lien magnet avec trackers français"""
        magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote_plus(title)}"
        for tracker in self.french_trackers:
            magnet += f"&tr={quote_plus(tracker)}"
        return magnet

    async def search_torrent9(self, query: str) -> List[Dict]:
        """
        Scrape Torrent9 - Source française principale
        Structure: Parsing HTML des résultats de recherche
        """
        results = []
        domains = [
            "https://www.torrent9.fm",
            "https://www.torrent9.gg",
            "https://www.torrent9.site",
            "https://torrent9.to",
        ]

        for domain in domains:
            try:
                session = await self._get_session()
                search_url = f"{domain}/recherche/{quote_plus(query)}"

                async with session.get(search_url) as response:
                    if response.status != 200:
                        continue

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Chercher les lignes de résultats dans le tableau
                    rows = soup.select('table.table tbody tr')

                    for row in rows[:30]:  # Limite 30 résultats
                        try:
                            # Extraire le titre et le lien
                            title_elem = row.select_one('a')
                            if not title_elem:
                                continue

                            title = title_elem.get_text(strip=True)
                            detail_url = title_elem.get('href', '')

                            # Extraire seeders/leechers
                            cells = row.select('td')
                            seeders = 0
                            leechers = 0
                            size = "Unknown"

                            if len(cells) >= 3:
                                # Format typique: Nom | Taille | Seeders | Leechers
                                try:
                                    size = cells[1].get_text(strip=True) if len(cells) > 1 else "Unknown"
                                    seeders = int(cells[2].get_text(strip=True)) if len(cells) > 2 else 0
                                    leechers = int(cells[3].get_text(strip=True)) if len(cells) > 3 else 0
                                except (ValueError, IndexError):
                                    pass

                            # Récupérer le magnet depuis la page de détails
                            magnet = await self._get_torrent9_magnet(domain, detail_url)

                            if magnet and seeders > 0:
                                # Analyser la langue
                                lang_info = self.language_detector.detect(title)

                                results.append({
                                    'title': title,
                                    'magnet': magnet,
                                    'size': self._parse_size(size),
                                    'size_str': size,
                                    'seeders': seeders,
                                    'leechers': leechers,
                                    'source': 'Torrent9',
                                    'quality': self._extract_quality(title),
                                    'language': lang_info.french_type.value,
                                    'is_french': lang_info.is_french,
                                    'french_priority': self.language_detector.get_french_priority_score(lang_info),
                                    'is_dubbed': lang_info.is_dubbed,
                                    'is_subbed': lang_info.is_subbed,
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing Torrent9 row: {e}")
                            continue

                    if results:
                        logger.info(f"Torrent9: {len(results)} results from {domain}")
                        break

            except Exception as e:
                logger.debug(f"Torrent9 domain {domain} failed: {e}")
                continue

        return results

    async def _get_torrent9_magnet(self, domain: str, detail_path: str) -> Optional[str]:
        """Récupère le magnet depuis la page de détails Torrent9"""
        try:
            if not detail_path:
                return None

            url = urljoin(domain, detail_path)
            session = await self._get_session()

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                html = await response.text()

                # Chercher le lien magnet
                magnet_match = re.search(r'href="(magnet:\?[^"]+)"', html)
                if magnet_match:
                    return magnet_match.group(1)

                # Alternative: chercher le hash dans la page
                hash_match = re.search(r'["\']([a-fA-F0-9]{40})["\']', html)
                if hash_match:
                    info_hash = hash_match.group(1)
                    # Extraire le titre de la page
                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                    title = title_match.group(1) if title_match else "Unknown"
                    return self._build_magnet(info_hash, title)

        except Exception as e:
            logger.debug(f"Failed to get magnet from {detail_path}: {e}")

        return None

    async def search_yggtorrent_public(self, query: str) -> List[Dict]:
        """
        Recherche sur des miroirs/proxies YggTorrent publics
        Note: YggTorrent officiel nécessite un compte
        """
        results = []

        # Proxies et miroirs connus (peuvent changer)
        mirrors = [
            "https://www2.yggtorrent.fi",
            "https://www3.yggtorrent.qa",
            "https://ww1.yggtorrent.life",
        ]

        for mirror in mirrors:
            try:
                session = await self._get_session()
                search_url = f"{mirror}/engine/search"
                params = {
                    'name': query,
                    'do': 'search',
                }

                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        continue

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Parser les résultats selon la structure YGG
                    rows = soup.select('table.table tr')

                    for row in rows[1:25]:  # Skip header, limite 25
                        try:
                            cols = row.select('td')
                            if len(cols) < 5:
                                continue

                            title_elem = cols[1].select_one('a')
                            if not title_elem:
                                continue

                            title = title_elem.get_text(strip=True)

                            # Extraire infos
                            size = cols[2].get_text(strip=True) if len(cols) > 2 else "Unknown"
                            seeders = int(cols[3].get_text(strip=True)) if len(cols) > 3 else 0
                            leechers = int(cols[4].get_text(strip=True)) if len(cols) > 4 else 0

                            # Chercher magnet ou hash
                            magnet_elem = row.select_one('a[href^="magnet:"]')
                            if magnet_elem:
                                magnet = magnet_elem.get('href')
                            else:
                                continue

                            lang_info = self.language_detector.detect(title)

                            results.append({
                                'title': title,
                                'magnet': magnet,
                                'size': self._parse_size(size),
                                'size_str': size,
                                'seeders': seeders,
                                'leechers': leechers,
                                'source': 'YggTorrent',
                                'quality': self._extract_quality(title),
                                'language': lang_info.french_type.value,
                                'is_french': lang_info.is_french,
                                'french_priority': self.language_detector.get_french_priority_score(lang_info),
                                'is_dubbed': lang_info.is_dubbed,
                                'is_subbed': lang_info.is_subbed,
                            })

                        except Exception as e:
                            logger.debug(f"Error parsing YGG row: {e}")
                            continue

                    if results:
                        logger.info(f"YggTorrent: {len(results)} results from {mirror}")
                        break

            except Exception as e:
                logger.debug(f"YggTorrent mirror {mirror} failed: {e}")
                continue

        return results

    async def search_1337x_french(self, query: str) -> List[Dict]:
        """
        Recherche 1337x avec filtrage pour contenu français
        1337x a souvent du contenu multi-langue
        """
        results = []
        mirrors = [
            "https://1337x.to",
            "https://1337x.st",
            "https://1337x.gd",
            "https://1337x.ws",
        ]

        # Variantes de recherche pour cibler le français
        search_queries = [
            f"{query} FRENCH",
            f"{query} VOSTFR",
            f"{query} VF",
            f"{query} MULTI",
            query,  # Recherche originale en dernier
        ]

        for mirror in mirrors:
            for search_query in search_queries:
                try:
                    session = await self._get_session()
                    search_url = f"{mirror}/search/{quote_plus(search_query)}/1/"

                    async with session.get(search_url) as response:
                        if response.status != 200:
                            continue

                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        rows = soup.select('table.table-list tbody tr')

                        for row in rows[:15]:  # Limite par variante
                            try:
                                # Nom du torrent
                                name_elem = row.select_one('td.name a:nth-child(2)')
                                if not name_elem:
                                    continue

                                title = name_elem.get_text(strip=True)
                                detail_link = name_elem.get('href', '')

                                # Seeders/Leechers
                                seeds_elem = row.select_one('td.seeds')
                                leech_elem = row.select_one('td.leeches')
                                size_elem = row.select_one('td.size')

                                seeders = int(seeds_elem.get_text(strip=True)) if seeds_elem else 0
                                leechers = int(leech_elem.get_text(strip=True)) if leech_elem else 0
                                size_text = size_elem.get_text(strip=True) if size_elem else "Unknown"

                                if seeders == 0:
                                    continue

                                # Détecter la langue
                                lang_info = self.language_detector.detect(title)

                                # Récupérer le magnet depuis la page de détails
                                magnet = await self._get_1337x_magnet(mirror, detail_link)

                                if magnet:
                                    results.append({
                                        'title': title,
                                        'magnet': magnet,
                                        'size': self._parse_size(size_text),
                                        'size_str': size_text,
                                        'seeders': seeders,
                                        'leechers': leechers,
                                        'source': '1337x',
                                        'quality': self._extract_quality(title),
                                        'language': lang_info.french_type.value,
                                        'is_french': lang_info.is_french,
                                        'french_priority': self.language_detector.get_french_priority_score(lang_info),
                                        'is_dubbed': lang_info.is_dubbed,
                                        'is_subbed': lang_info.is_subbed,
                                    })

                            except Exception as e:
                                logger.debug(f"Error parsing 1337x row: {e}")
                                continue

                        if results:
                            break  # Sortir de la boucle search_queries

                except Exception as e:
                    logger.debug(f"1337x search failed: {e}")
                    continue

            if results:
                logger.info(f"1337x French: {len(results)} results from {mirror}")
                break

        return results

    async def _get_1337x_magnet(self, domain: str, detail_path: str) -> Optional[str]:
        """Récupère le magnet depuis la page de détails 1337x"""
        try:
            if not detail_path:
                return None

            url = urljoin(domain, detail_path)
            session = await self._get_session()

            async with session.get(url) as response:
                if response.status != 200:
                    return None

                html = await response.text()

                # Chercher le lien magnet
                magnet_match = re.search(r'href="(magnet:\?[^"]+)"', html)
                if magnet_match:
                    return magnet_match.group(1)

        except Exception as e:
            logger.debug(f"Failed to get magnet from 1337x {detail_path}: {e}")

        return None

    async def search_rarbg_french(self, query: str) -> List[Dict]:
        """
        RARBG/RARBGMirror - Bonne source multi-langue
        Note: RARBG officiel est fermé, on utilise des miroirs/API
        """
        results = []

        # API publiques RARBG-like
        api_urls = [
            "https://torrentapi.org/pubapi_v2.php",
        ]

        for api_url in api_urls:
            try:
                session = await self._get_session()

                # Obtenir un token d'abord
                token_resp = await session.get(api_url, params={'get_token': 'get_token', 'app_id': 'streamtv'})
                if token_resp.status != 200:
                    continue

                token_data = await token_resp.json()
                token = token_data.get('token')

                if not token:
                    continue

                # Attendre un peu (rate limiting de l'API)
                await asyncio.sleep(2.1)

                # Rechercher
                params = {
                    'mode': 'search',
                    'search_string': query,
                    'token': token,
                    'format': 'json_extended',
                    'app_id': 'streamtv',
                    'limit': 25,
                }

                async with session.get(api_url, params=params) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()
                    torrents = data.get('torrent_results', [])

                    for torrent in torrents:
                        title = torrent.get('title', '')
                        magnet = torrent.get('download', '')

                        if not magnet or not title:
                            continue

                        lang_info = self.language_detector.detect(title)

                        results.append({
                            'title': title,
                            'magnet': magnet,
                            'size': torrent.get('size', 0),
                            'size_str': self._format_size(torrent.get('size', 0)),
                            'seeders': torrent.get('seeders', 0),
                            'leechers': torrent.get('leechers', 0),
                            'source': 'RARBG',
                            'quality': self._extract_quality(title),
                            'language': lang_info.french_type.value,
                            'is_french': lang_info.is_french,
                            'french_priority': self.language_detector.get_french_priority_score(lang_info),
                            'is_dubbed': lang_info.is_dubbed,
                            'is_subbed': lang_info.is_subbed,
                        })

                    if results:
                        logger.info(f"RARBG: {len(results)} results")
                        break

            except Exception as e:
                logger.debug(f"RARBG API failed: {e}")
                continue

        return results

    async def search_all_french(self, query: str, prefer_french: bool = True) -> List[Dict]:
        """
        Recherche complète sur toutes les sources françaises

        Args:
            query: Terme de recherche
            prefer_french: Si True, priorise les résultats en français
        """
        logger.info(f"French search starting: '{query}' (prefer_french={prefer_french})")

        # Exécuter toutes les recherches en parallèle
        tasks = [
            self.search_torrent9(query),
            self.search_1337x_french(query),
            self.search_rarbg_french(query),
        ]

        # Ajouter YGG si disponible (souvent bloqué)
        # tasks.append(self.search_yggtorrent_public(query))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Agréger les résultats
        all_results = []
        source_stats = {}

        for results in results_lists:
            if isinstance(results, list):
                all_results.extend(results)
                for r in results:
                    source = r.get('source', 'Unknown')
                    source_stats[source] = source_stats.get(source, 0) + 1

        # Dédupliquer par hash
        unique_results = self._deduplicate(all_results)

        # Calculer les scores
        for result in unique_results:
            result['relevance_score'] = self._calculate_score(result, query, prefer_french)

        # Trier par score de pertinence
        if prefer_french:
            # Trier d'abord par français, puis par score
            unique_results.sort(
                key=lambda x: (
                    x.get('is_french', False),
                    x.get('french_priority', 0),
                    x.get('relevance_score', 0),
                    x.get('seeders', 0)
                ),
                reverse=True
            )
        else:
            unique_results.sort(
                key=lambda x: (x.get('relevance_score', 0), x.get('seeders', 0)),
                reverse=True
            )

        logger.info(f"French search completed: {len(unique_results)} results from {source_stats}")
        return unique_results[:50]

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Déduplique les résultats par hash de torrent"""
        seen_hashes = set()
        unique = []

        for result in results:
            magnet = result.get('magnet', '')
            hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)

            if hash_match:
                torrent_hash = hash_match.group(1).lower()
                if torrent_hash not in seen_hashes:
                    seen_hashes.add(torrent_hash)
                    unique.append(result)
            else:
                # Garder quand même si pas de hash détectable
                unique.append(result)

        return unique

    def _calculate_score(self, result: Dict, query: str, prefer_french: bool) -> float:
        """Calcule un score de pertinence avancé"""
        score = 0.0
        title = result.get('title', '').lower()
        query_lower = query.lower()

        # Correspondance titre (30%)
        query_words = query_lower.split()
        matches = sum(1 for word in query_words if word in title)
        score += (matches / len(query_words)) * 30 if query_words else 0

        # Qualité seeders (25%)
        seeders = result.get('seeders', 0)
        if seeders >= 100:
            score += 25
        elif seeders >= 50:
            score += 20
        elif seeders >= 20:
            score += 15
        elif seeders >= 5:
            score += 10
        elif seeders >= 1:
            score += 5

        # Qualité vidéo (20%)
        quality_scores = {
            'UHD': 20, '2160p': 20, '4k': 20,
            '1080p': 18, 'BluRay': 17,
            '720p': 14, 'WEB-DL': 15,
            'HDTV': 12, 'WEBRip': 13,
            '480p': 8, 'DVDRip': 7,
            'CAM': 2, 'TS': 1
        }
        quality = result.get('quality', '').upper()
        for q, s in quality_scores.items():
            if q.upper() in quality:
                score += s
                break

        # Bonus français (25% si prefer_french)
        if prefer_french and result.get('is_french', False):
            french_priority = result.get('french_priority', 0)
            score += (french_priority / 100) * 25

        # Bonus source fiable
        source_scores = {
            'Torrent9': 5,
            'YggTorrent': 5,
            '1337x': 4,
            'RARBG': 4,
        }
        score += source_scores.get(result.get('source', ''), 0)

        return min(score, 100.0)

    def _extract_quality(self, title: str) -> str:
        """Extrait la qualité vidéo du titre"""
        if not title:
            return 'Unknown'

        title_upper = title.upper()

        quality_patterns = [
            (r'2160[PI]', '2160p'), (r'4K', '4K'), (r'UHD', 'UHD'),
            (r'1080[PI]', '1080p'), (r'1080', '1080p'),
            (r'720[PI]', '720p'), (r'720', '720p'),
            (r'480[PI]', '480p'),
            (r'BLURAY|BLU-RAY|BDRIP|BD-RIP', 'BluRay'),
            (r'WEB-?DL', 'WEB-DL'),
            (r'WEBRIP|WEB-?RIP', 'WEBRip'),
            (r'HDTV', 'HDTV'),
            (r'DVDRIP|DVD-?RIP', 'DVDRip'),
            (r'HDCAM', 'HDCam'),
            (r'\bCAM\b', 'CAM'),
            (r'\bTS\b|TELESYNC', 'TeleSync'),
        ]

        for pattern, quality in quality_patterns:
            if re.search(pattern, title_upper):
                return quality

        return 'Unknown'

    def _parse_size(self, size_str: str) -> int:
        """Parse une taille en bytes"""
        if not size_str or size_str == "Unknown":
            return 0

        try:
            size_str = size_str.upper().strip()
            multipliers = {
                'TB': 1024**4, 'TIO': 1024**4,
                'GB': 1024**3, 'GIO': 1024**3, 'GO': 1024**3,
                'MB': 1024**2, 'MIO': 1024**2, 'MO': 1024**2,
                'KB': 1024, 'KIO': 1024, 'KO': 1024,
            }

            for suffix, mult in multipliers.items():
                if suffix in size_str:
                    num = float(re.sub(r'[^\d.]', '', size_str.replace(suffix, '')))
                    return int(num * mult)

            return int(float(re.sub(r'[^\d.]', '', size_str)))
        except:
            return 0

    def _format_size(self, size_bytes: int) -> str:
        """Formate une taille en bytes vers une chaîne lisible"""
        if size_bytes == 0:
            return "Unknown"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(size_bytes) < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0

        return f"{size_bytes:.1f} PB"

    async def close(self):
        """Ferme la session HTTP"""
        if self.session:
            await self.session.close()
            self.session = None


# Instance globale
french_scraper = FrenchTorrentScraper()
