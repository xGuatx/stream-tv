import requests
import logging
import json
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import difflib
import urllib3

# Supprimer les warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

@dataclass
class Episode:
    """Represente un episode"""
    episode_number: int
    title: str
    overview: str
    air_date: Optional[str] = None
    runtime: Optional[int] = None
    still_path: Optional[str] = None
    
@dataclass  
class Season:
    """Represente une saison"""
    season_number: int
    name: str
    overview: str
    episode_count: int
    air_date: Optional[str] = None
    poster_path: Optional[str] = None
    episodes: List[Episode] = None
    
    def __post_init__(self):
        if self.episodes is None:
            self.episodes = []

@dataclass
class Series:
    """Represente une serie complete"""
    id: int
    name: str
    original_name: str
    overview: str
    first_air_date: str
    status: str
    genres: List[str]
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    seasons: List[Season] = None
    
    def __post_init__(self):
        if self.seasons is None:
            self.seasons = []

@dataclass
class Movie:
    """Represente un film"""
    id: int
    title: str
    original_title: str
    overview: str
    release_date: str
    runtime: Optional[int]
    genres: List[str]
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None

class CatalogService:
    """Service de catalogue utilisant TMDB pour les metadonnees"""
    
    def __init__(self, tmdb_api_key: str):
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"
        
    def _make_tmdb_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Fait une requete a l'API TMDB"""
        if params is None:
            params = {}
        params['api_key'] = self.tmdb_api_key
        
        url = f"{self.tmdb_base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=20, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Erreur TMDB API: {e}")
            return {}
    
    def search_series(self, query: str) -> List[Dict]:
        """Recherche des series par nom"""
        data = self._make_tmdb_request("search/tv", {"query": query, "language": "fr-FR"})
        results = []
        
        for item in data.get("results", []):
            # Score de pertinence
            title_similarity = max(
                difflib.SequenceMatcher(None, query.lower(), item.get("name", "").lower()).ratio(),
                difflib.SequenceMatcher(None, query.lower(), item.get("original_name", "").lower()).ratio()
            )
            
            results.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "original_name": item.get("original_name"),
                "overview": item.get("overview"),
                "first_air_date": item.get("first_air_date"),
                "poster_path": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
                "similarity_score": title_similarity,
                "type": "series"
            })
        
        # Tri par pertinence
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results
    
    def search_movies(self, query: str) -> List[Dict]:
        """Recherche des films par nom"""
        data = self._make_tmdb_request("search/movie", {"query": query, "language": "fr-FR"})
        results = []
        
        for item in data.get("results", []):
            # Score de pertinence
            title_similarity = max(
                difflib.SequenceMatcher(None, query.lower(), item.get("title", "").lower()).ratio(),
                difflib.SequenceMatcher(None, query.lower(), item.get("original_title", "").lower()).ratio()
            )
            
            results.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "original_title": item.get("original_title"),
                "overview": item.get("overview"),
                "release_date": item.get("release_date"),
                "poster_path": f"{self.image_base_url}{item.get('poster_path')}" if item.get('poster_path') else None,
                "similarity_score": title_similarity,
                "type": "movie"
            })
        
        # Tri par pertinence
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results
    
    def get_series_details(self, series_id: int) -> Optional[Series]:
        """Recupere les details complets d'une serie"""
        data = self._make_tmdb_request(f"tv/{series_id}", {"language": "fr-FR"})
        if not data:
            return None
            
        # Genres
        genres = [genre["name"] for genre in data.get("genres", [])]
        
        # Creation de l'objet serie
        series = Series(
            id=data.get("id"),
            name=data.get("name"),
            original_name=data.get("original_name"),
            overview=data.get("overview", ""),
            first_air_date=data.get("first_air_date", ""),
            status=data.get("status", ""),
            genres=genres,
            poster_path=f"{self.image_base_url}{data.get('poster_path')}" if data.get('poster_path') else None,
            backdrop_path=f"{self.image_base_url}{data.get('backdrop_path')}" if data.get('backdrop_path') else None
        )
        
        # Ajout des saisons
        for season_data in data.get("seasons", []):
            season = Season(
                season_number=season_data.get("season_number", 0),
                name=season_data.get("name", ""),
                overview=season_data.get("overview", ""),
                episode_count=season_data.get("episode_count", 0),
                air_date=season_data.get("air_date"),
                poster_path=f"{self.image_base_url}{season_data.get('poster_path')}" if season_data.get('poster_path') else None
            )
            series.seasons.append(season)
        
        return series
    
    def get_season_episodes(self, series_id: int, season_number: int) -> List[Episode]:
        """Recupere les episodes d'une saison"""
        data = self._make_tmdb_request(f"tv/{series_id}/season/{season_number}", {"language": "fr-FR"})
        episodes = []
        
        for ep_data in data.get("episodes", []):
            episode = Episode(
                episode_number=ep_data.get("episode_number", 0),
                title=ep_data.get("name", ""),
                overview=ep_data.get("overview", ""),
                air_date=ep_data.get("air_date"),
                runtime=ep_data.get("runtime"),
                still_path=f"{self.image_base_url}{ep_data.get('still_path')}" if ep_data.get('still_path') else None
            )
            episodes.append(episode)
        
        return episodes
    
    def get_movie_details(self, movie_id: int) -> Optional[Movie]:
        """Recupere les details d'un film"""
        data = self._make_tmdb_request(f"movie/{movie_id}", {"language": "fr-FR"})
        if not data:
            return None
            
        # Genres
        genres = [genre["name"] for genre in data.get("genres", [])]
        
        return Movie(
            id=data.get("id"),
            title=data.get("title"),
            original_title=data.get("original_title"),
            overview=data.get("overview", ""),
            release_date=data.get("release_date", ""),
            runtime=data.get("runtime"),
            genres=genres,
            poster_path=f"{self.image_base_url}{data.get('poster_path')}" if data.get('poster_path') else None,
            backdrop_path=f"{self.image_base_url}{data.get('backdrop_path')}" if data.get('backdrop_path') else None
        )
    
    def unified_search(self, query: str) -> Dict[str, List]:
        """Recherche unifiee : films et series"""
        return {
            "series": self.search_series(query),
            "movies": self.search_movies(query)
        }

# Fonction utilitaire pour generer les requetes de recherche torrent
def generate_torrent_queries(series: Series, season_number: int = None, episode_number: int = None) -> List[str]:
    """Genere des requetes optimisees pour la recherche torrent"""
    queries = []
    
    # Noms de base
    base_names = [series.name]
    if series.original_name != series.name:
        base_names.append(series.original_name)
    
    for name in base_names:
        if season_number is not None:
            if episode_number is not None:
                # Episode specifique
                queries.extend([
                    f"{name} S{season_number:02d}E{episode_number:02d}",
                    f"{name} Season {season_number} Episode {episode_number}",
                    f"{name} {season_number}x{episode_number:02d}"
                ])
            else:
                # Saison complete
                queries.extend([
                    f"{name} S{season_number:02d}",
                    f"{name} Season {season_number}",
                    f"{name} Saison {season_number}"
                ])
        else:
            # Serie complete
            queries.extend([
                name,
                f"{name} Complete",
                f"{name} Integral"
            ])
    
    return queries

def generate_movie_queries(movie: Movie) -> List[str]:
    """Genere des requetes optimisees pour la recherche de film"""
    queries = []
    
    # Annee du film
    year = ""
    if movie.release_date:
        try:
            year = movie.release_date.split("-")[0]
        except:
            pass
    
    # Noms de base
    base_names = [movie.title]
    if movie.original_title != movie.title:
        base_names.append(movie.original_title)
    
    for name in base_names:
        queries.append(name)
        if year:
            queries.append(f"{name} {year}")
            queries.append(f"{name} ({year})")
    
    return queries