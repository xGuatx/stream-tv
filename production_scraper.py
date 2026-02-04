"""
Production Torrent Scraper - Version complete pour streaming
Optimise pour les grands titres populaires + Support français avancé
"""

import asyncio
import aiohttp
import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import quote_plus, unquote_plus
import base64
from datetime import datetime

# Import du scraper français
try:
    from french_scraper import french_scraper, FrenchLanguageDetector, FrenchLanguageType
    FRENCH_SCRAPER_AVAILABLE = True
except ImportError:
    FRENCH_SCRAPER_AVAILABLE = False
    french_scraper = None
    FrenchLanguageDetector = None

logger = logging.getLogger(__name__)

class ProductionTorrentScraper:
    """Scraper production pour grands titres"""
    
    def __init__(self):
        self.session = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
    async def _get_session(self):
        """Session HTTP production"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=25)
            connector = aiohttp.TCPConnector(
                limit=20,
                verify_ssl=False,
                use_dns_cache=True,
                ttl_dns_cache=300
            )
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': self.user_agents[0],
                    'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,fr-FR;q=0.8,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
        return self.session

    async def search_yts_production(self, query: str) -> List[Dict]:
        """YTS optimise pour grands titres"""
        results = []
        yts_domains = [
            "https://yts.mx",
            "https://yts.lt", 
            "https://yts.ag",
            "https://yts.am",
            "https://yts.torrentbay.st"
        ]
        
        for domain in yts_domains:
            try:
                session = await self._get_session()
                api_url = f"{domain}/api/v2/list_movies.json"
                
                # Recherche avec plusieurs parametres pour plus de resultats
                searches = [
                    {'query_term': query, 'limit': 50, 'sort_by': 'seeds'},
                    {'query_term': query, 'limit': 50, 'sort_by': 'download_count'},
                    {'query_term': query, 'limit': 50, 'sort_by': 'like_count'}
                ]
                
                for params in searches:
                    try:
                        async with session.get(api_url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                movies = data.get('data', {}).get('movies', [])
                                
                                for movie in movies:
                                    if not self._is_relevant_movie(movie, query):
                                        continue
                                        
                                    torrents = movie.get('torrents', [])
                                    for torrent in torrents:
                                        hash_value = torrent.get('hash')
                                        if hash_value and torrent.get('seeds', 0) > 0:
                                            
                                            movie_title = movie.get('title_long', movie.get('title', ''))
                                            quality = torrent.get('quality', 'Unknown')
                                            
                                            # Trackers optimises pour performance
                                            trackers = [
                                                'udp://tracker.openbittorrent.com:80',
                                                'udp://tracker.opentrackr.org:1337',
                                                'udp://tracker.torrent.eu.org:451',
                                                'udp://opentracker.i2p.rocks:6969',
                                                'udp://tracker.internetwarriors.net:1337',
                                                'udp://9.rarbg.com:2810/announce',
                                                'udp://exodus.desync.com:6969',
                                                'udp://explodie.org:6969'
                                            ]
                                            
                                            magnet = f"magnet:?xt=urn:btih:{hash_value}&dn={quote_plus(movie_title + ' ' + quality)}"
                                            for tracker in trackers:
                                                magnet += f"&tr={quote_plus(tracker)}"
                                            
                                            results.append({
                                                'title': f"{movie_title} ({movie.get('year', 'N/A')}) [{quality}]",
                                                'magnet': magnet,
                                                'size': torrent.get('size_bytes', 0),
                                                'seeders': torrent.get('seeds', 0),
                                                'leechers': torrent.get('peers', 0),
                                                'source': 'YTS',
                                                'quality': quality,
                                                'language': 'ENG',
                                                'year': movie.get('year', 0),
                                                'rating': movie.get('rating', 0),
                                                'runtime': movie.get('runtime', 0)
                                            })
                                
                                if results:
                                    logger.info(f"YTS Production: {len(results)} results from {domain}")
                                    break
                                    
                    except Exception as e:
                        logger.debug(f"YTS search params failed: {e}")
                        continue
                
                if results:
                    break
                    
            except Exception as e:
                logger.debug(f"YTS domain {domain} failed: {e}")
                continue
        
        return results

    async def search_eztv_production(self, query: str) -> List[Dict]:
        """EZTV optimise pour series"""
        results = []
        eztv_mirrors = [
            "https://eztv.re",
            "https://eztv.io", 
            "https://eztv.wf",
            "https://eztv.tf"
        ]
        
        for mirror in eztv_mirrors:
            try:
                session = await self._get_session()
                
                # Recherche par page pour plus de resultats
                for page in range(1, 4):  # 3 premieres pages
                    try:
                        api_url = f"{mirror}/api/get-torrents"
                        params = {
                            'limit': 100,
                            'page': page
                        }
                        
                        async with session.get(api_url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                torrents = data.get('torrents', [])
                                
                                # Filtrer par pertinence
                                query_words = query.lower().split()
                                for torrent in torrents:
                                    title = torrent.get('title', '').lower()
                                    
                                    # Verifier pertinence
                                    if not any(word in title for word in query_words):
                                        continue
                                    
                                    magnet_url = torrent.get('magnet_url')
                                    if magnet_url and torrent.get('seeds', 0) > 0:
                                        results.append({
                                            'title': torrent.get('title', ''),
                                            'magnet': magnet_url,
                                            'size': torrent.get('size_bytes', 0),
                                            'seeders': torrent.get('seeds', 0),
                                            'leechers': torrent.get('peers', 0),
                                            'source': 'EZTV',
                                            'quality': self._extract_quality(torrent.get('title', '')),
                                            'language': 'ENG',
                                            'date_released': torrent.get('date_released_unix', 0)
                                        })
                                
                                if len(results) > 50:  # Limite pour eviter trop de resultats
                                    break
                                    
                    except Exception as e:
                        logger.debug(f"EZTV page {page} failed: {e}")
                        continue
                
                if results:
                    logger.info(f"EZTV Production: {len(results)} results from {mirror}")
                    break
                    
            except Exception as e:
                logger.debug(f"EZTV mirror {mirror} failed: {e}")
                continue
        
        return results

    async def search_1337x_fallback(self, query: str) -> List[Dict]:
        """1337x comme fallback pour titres non trouves"""
        results = []
        mirrors = [
            "https://1337x.to",
            "https://1337x.st",
            "https://www.1377x.to"
        ]
        
        for mirror in mirrors:
            try:
                session = await self._get_session()
                
                # Recherche simple
                search_url = f"{mirror}/search/{quote_plus(query)}/1/"
                
                async with session.get(search_url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        
                        # Parsing basique pour extraire les informations
                        # Note: Pour une vraie production, il faudrait un parsing HTML complet
                        magnet_links = re.findall(r'href="(magnet:\?[^"]+)"', html_content)
                        titles = re.findall(r'<a href="/torrent/[^"]+">([^<]+)</a>', html_content)
                        
                        for i, (title, magnet) in enumerate(zip(titles[:10], magnet_links[:10])):
                            if query.lower() in title.lower():
                                # Extraction basique des seeders depuis HTML
                                seeders = self._extract_seeders_from_html(html_content, i)
                                
                                results.append({
                                    'title': title,
                                    'magnet': magnet,
                                    'size': 0,  # Non disponible facilement
                                    'seeders': seeders,
                                    'leechers': 0,
                                    'source': '1337x',
                                    'quality': self._extract_quality(title),
                                    'language': self._detect_language(title)
                                })
                        
                        if results:
                            logger.info(f"1337x Fallback: {len(results)} results from {mirror}")
                            break
                            
            except Exception as e:
                logger.debug(f"1337x mirror {mirror} failed: {e}")
                continue
        
        return results

    def _is_relevant_movie(self, movie: dict, query: str) -> bool:
        """Verifie si le film correspond a la recherche"""
        title = movie.get('title', '').lower()
        title_long = movie.get('title_long', '').lower()
        query_lower = query.lower()
        
        # Correspondance exacte ou partielle
        query_words = query_lower.split()
        title_words = (title + ' ' + title_long).split()
        
        # Au moins 70% des mots de la requete doivent etre dans le titre
        matches = sum(1 for qword in query_words if any(qword in tword for tword in title_words))
        relevance = matches / len(query_words)
        
        return relevance >= 0.5  # Au moins 50% de correspondance

    def _extract_quality(self, title: str) -> str:
        """Extraction qualite optimisee"""
        if not title:
            return 'Unknown'
        
        title_lower = title.lower()
        
        # Ordre de priorite pour la qualite
        quality_patterns = [
            ('2160p', 'UHD'), ('4k', 'UHD'), ('uhd', 'UHD'),
            ('1080p', '1080p'), ('1080i', '1080i'),
            ('720p', '720p'), ('720i', '720i'),
            ('480p', '480p'), ('360p', '360p'),
            ('bluray', 'BluRay'), ('blu-ray', 'BluRay'),
            ('web-dl', 'WEB-DL'), ('webdl', 'WEB-DL'), ('webrip', 'WEBRip'),
            ('hdtv', 'HDTV'), ('hdcam', 'HDCam'),
            ('dvdrip', 'DVDRip'), ('dvd', 'DVD'),
            ('cam', 'CAM'), ('ts', 'TeleSync')
        ]
        
        for pattern, quality in quality_patterns:
            if pattern in title_lower:
                return quality
        
        return 'Unknown'

    def _detect_language(self, title: str) -> str:
        """Detection langue optimisee avec support français avancé"""
        title_lower = title.lower()
        title_upper = title.upper()

        # Utiliser le détecteur français avancé si disponible
        if FRENCH_SCRAPER_AVAILABLE and FrenchLanguageDetector:
            lang_info = FrenchLanguageDetector.detect(title)
            if lang_info.is_french:
                return lang_info.french_type.value

        # Détection française manuelle améliorée
        french_patterns = [
            (r'\bTRUEFRENCH\b', 'TRUEFRENCH'),
            (r'\bVFF\b', 'VFF'),
            (r'\bVFQ\b', 'VFQ'),
            (r'\bVF\b(?!R)', 'VF'),
            (r'\bVOSTFR\b', 'VOSTFR'),
            (r'\bSUBFRENCH\b', 'SUBFRENCH'),
            (r'\bMULTI\b', 'MULTI'),
            (r'\bFRENCH\b', 'FRENCH'),
        ]

        for pattern, lang in french_patterns:
            if re.search(pattern, title_upper):
                return lang

        # Autres langues
        if any(term in title_lower for term in ['spanish', 'latino', 'esp', 'castellano']):
            return 'ESP'
        elif any(term in title_lower for term in ['german', 'deutsch', 'ger']):
            return 'GER'
        elif any(term in title_lower for term in ['italian', 'ita']):
            return 'ITA'
        elif any(term in title_lower for term in ['russian', 'rus']):
            return 'RUS'
        elif any(term in title_lower for term in ['portuguese', 'por', 'dublado']):
            return 'POR'
        else:
            return 'ENG'

    def _get_french_priority(self, language: str) -> int:
        """Retourne la priorité pour les versions françaises (plus haut = meilleur)"""
        priority_map = {
            'TRUEFRENCH': 100,
            'VFF': 95,
            'VFQ': 90,
            'VF': 85,
            'MULTI': 70,
            'FRENCH': 65,
            'VOSTFR': 60,
            'SUBFRENCH': 55,
        }
        return priority_map.get(language, 0)

    def _extract_seeders_from_html(self, html: str, index: int) -> int:
        """Extraction seeders depuis HTML (basique)"""
        # Pattern basique - a ameliorer selon la structure HTML reelle
        seeders_matches = re.findall(r'(\d+)</td>.*?Seeders', html)
        if seeders_matches and index < len(seeders_matches):
            return int(seeders_matches[index])
        return 0

    async def search_series_specialized(self, query: str) -> List[Dict]:
        """Recherche specialisee pour series avec patterns avances"""
        results = []
        
        # Nettoyer et normaliser la requete pour les series
        normalized_query = self._normalize_series_query(query)
        
        # Rechercher avec differentes variantes
        search_variants = self._generate_series_variants(normalized_query)
        
        for variant in search_variants:
            try:
                # Utiliser EZTV avec la variante
                variant_results = await self.search_eztv_production(variant)
                results.extend(variant_results)
                
                if len(results) >= 20:  # Limite pour eviter trop de resultats
                    break
                    
            except Exception as e:
                logger.debug(f"Series search variant failed: {variant} - {e}")
                continue
        
        return results

    def _normalize_series_query(self, query: str) -> str:
        """Normalise la requete serie"""
        # Supprimer les mots inutiles et normaliser
        query = re.sub(r'\b(streaming|torrent|download|watch)\b', '', query.lower())
        query = re.sub(r'\s+', ' ', query).strip()
        return query

    def _generate_series_variants(self, query: str) -> List[str]:
        """Genere les variantes de recherche pour series"""
        variants = [query]
        
        # Detecter et convertir les patterns saison/episode
        season_ep_match = re.search(r's(\d+)e(\d+)', query.lower())
        if season_ep_match:
            season, episode = season_ep_match.groups()
            base_query = re.sub(r's\d+e\d+', '', query).strip()
            
            # Ajouter differentes variantes
            variants.extend([
                f"{base_query} season {season} episode {episode}",
                f"{base_query} {season}x{episode.zfill(2)}",
                f"{base_query} s{season.zfill(2)}e{episode.zfill(2)}"
            ])
        
        return variants[:5]  # Limite le nombre de variantes

    async def search_all_production(self, query: str, prefer_french: bool = True) -> List[Dict]:
        """
        Recherche production complete avec support français avancé

        Args:
            query: Terme de recherche
            prefer_french: Si True, priorise les résultats en français
        """
        logger.info(f"Production search starting: '{query}' (prefer_french={prefer_french})")

        # Executer toutes les recherches en parallele
        tasks = [
            self.search_yts_production(query),
            self.search_eztv_production(query),
        ]

        # Ajouter recherches specialisees pour series (detection automatique)
        series_patterns = ['s01e01', 'season', 'episode', r's\d+e\d+', 'saison', 'épisode']
        if any(re.search(pattern, query.lower()) for pattern in series_patterns):
            # Recherche specialisee series
            tasks.append(self.search_series_specialized(query))

        # Ajouter 1337x en fallback pour toutes les recherches (diversification des sources)
        tasks.append(self.search_1337x_fallback(query))

        # Ajouter sources françaises si disponibles
        french_results = []
        if FRENCH_SCRAPER_AVAILABLE and french_scraper:
            try:
                french_results = await french_scraper.search_all_french(query, prefer_french)
                logger.info(f"French scraper returned {len(french_results)} results")
            except Exception as e:
                logger.warning(f"French scraper failed: {e}")

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Agreger resultats
        all_results = []
        source_stats = {}

        source_names = ['YTS', 'EZTV', 'Series_Specialized', '1337x']

        for i, results in enumerate(results_lists):
            if isinstance(results, list):
                all_results.extend(results)
                source_name = source_names[i] if i < len(source_names) else f'Source_{i}'
                source_stats[source_name] = len(results)
            else:
                logger.warning(f"Source {i} failed: {results}")

        # Ajouter les résultats français
        if french_results:
            all_results.extend(french_results)
            for r in french_results:
                source = r.get('source', 'French')
                source_stats[source] = source_stats.get(source, 0) + 1

        # Deduplication et tri avance avec support français
        unique_results = self._deduplicate_and_rank(all_results, query, prefer_french)

        logger.info(f"Production search completed: {len(unique_results)} quality results from {source_stats}")
        return unique_results[:50]  # Top 50 resultats

    async def search_french_only(self, query: str) -> List[Dict]:
        """Recherche uniquement sur les sources françaises"""
        if not FRENCH_SCRAPER_AVAILABLE or not french_scraper:
            logger.warning("French scraper not available, falling back to standard search")
            return await self.search_all_production(query, prefer_french=True)

        try:
            results = await french_scraper.search_all_french(query, prefer_french=True)

            # Filtrer pour ne garder que les résultats français
            french_only = [r for r in results if r.get('is_french', False)]

            if not french_only:
                logger.info("No French results found, returning all results with French priority")
                return results

            return french_only
        except Exception as e:
            logger.error(f"French-only search failed: {e}")
            return []

    def _deduplicate_and_rank(self, results: List[Dict], query: str, prefer_french: bool = True) -> List[Dict]:
        """Deduplication et classement avance avec support français"""
        # Deduplication par magnet
        seen_magnets = set()
        unique_results = []

        for result in results:
            magnet = result.get('magnet', '')
            # Extraire hash du magnet pour comparaison
            hash_match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
            if hash_match:
                torrent_hash = hash_match.group(1).lower()
                if torrent_hash not in seen_magnets:
                    seen_magnets.add(torrent_hash)
                    unique_results.append(result)
            else:
                # Garder les résultats sans hash détectable
                unique_results.append(result)

        # Scoring avance
        for result in unique_results:
            score = self._calculate_relevance_score(result, query, prefer_french)
            result['relevance_score'] = score

            # Ajouter informations françaises si pas déjà présentes
            if 'is_french' not in result:
                lang = result.get('language', 'ENG')
                result['is_french'] = lang in ['TRUEFRENCH', 'VFF', 'VFQ', 'VF', 'VOSTFR', 'SUBFRENCH', 'MULTI', 'FRENCH']
                result['french_priority'] = self._get_french_priority(lang)

        # Tri par score de pertinence avec priorité française
        if prefer_french:
            # D'abord les français, puis par score, puis par seeders
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
            # Tri standard par score puis seeders
            unique_results.sort(
                key=lambda x: (x.get('relevance_score', 0), x.get('seeders', 0)),
                reverse=True
            )

        return unique_results

    def _calculate_relevance_score(self, result: Dict, query: str, prefer_french: bool = True) -> float:
        """Score de pertinence avance avec support français"""
        score = 0.0
        title = result.get('title', '').lower()
        query_lower = query.lower()

        # Correspondance de titre (30% - réduit pour faire place au bonus français)
        query_words = query_lower.split()
        title_matches = sum(1 for word in query_words if word in title)
        title_score = (title_matches / len(query_words)) * 30 if query_words else 0
        score += title_score

        # Qualite seeders (25%)
        seeders = result.get('seeders', 0)
        if seeders >= 100:
            seeders_score = 25
        elif seeders >= 50:
            seeders_score = 20
        elif seeders >= 20:
            seeders_score = 16
        elif seeders >= 10:
            seeders_score = 12
        elif seeders >= 5:
            seeders_score = 8
        elif seeders >= 1:
            seeders_score = 4
        else:
            seeders_score = 0
        score += seeders_score

        # Qualite video (20%)
        quality = result.get('quality', '').lower()
        quality_scores = {
            'uhd': 20, '2160p': 20, '4k': 20,
            '1080p': 18, 'bluray': 17,
            '720p': 15, 'web-dl': 16,
            'hdtv': 12, 'webrip': 13,
            '480p': 8, 'dvdrip': 7,
            'hdcam': 4,
            'cam': 2, 'ts': 1, 'telesync': 1
        }
        for q, s in quality_scores.items():
            if q in quality:
                score += s
                break
        else:
            score += 5  # Score par défaut si qualité inconnue

        # Bonus français (20% si prefer_french est True)
        if prefer_french:
            language = result.get('language', 'ENG')
            french_priority = result.get('french_priority', 0)

            # Si pas de french_priority, la calculer
            if french_priority == 0:
                french_priority = self._get_french_priority(language)

            # Le bonus est proportionnel à la priorité française (max 20 points)
            if french_priority > 0:
                score += (french_priority / 100) * 20

        # Bonus source fiable (5%)
        source = result.get('source', '')
        source_scores = {
            'Torrent9': 5,      # Source française prioritaire
            'YggTorrent': 5,    # Source française
            'YTS': 4,
            'EZTV': 4,
            '1337x': 3,
            'RARBG': 3,
        }
        score += source_scores.get(source, 2)

        return min(score, 100.0)  # Max 100 points

    async def close(self):
        """Fermer session"""
        if self.session:
            await self.session.close()

# Instance globale production
production_scraper = ProductionTorrentScraper()