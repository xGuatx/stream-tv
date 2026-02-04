#!/usr/bin/env python3
"""
Service de Streaming Reel avec libtorrent
Telecharge et stream en temps reel les torrents
"""

import libtorrent as lt
import os
import time
import threading
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = "/tmp/streamtv_torrents"
os.makedirs(CACHE_DIR, exist_ok=True)

class RealStreamingService:
    """Service de streaming torrent reel avec libtorrent"""

    def __init__(self):
        # Configuration avancee de la session pour meilleure connexion aux peers
        settings = {
            'user_agent': 'StreamTV/1.0 libtorrent/2.0',
            'listen_interfaces': '0.0.0.0:6881,[::]:6881',
            'enable_dht': True,
            'enable_lsd': True,  # Local Service Discovery
            'enable_upnp': True,
            'enable_natpmp': True,
            'dht_bootstrap_nodes': 'router.bittorrent.com:6881,router.utorrent.com:6881,dht.transmissionbt.com:6881,dht.aelitis.com:6881',
            'announce_to_all_tiers': True,
            'announce_to_all_trackers': True,
            'aio_threads': 4,
            'checking_mem_usage': 256,
        }

        self.session = lt.session(settings)

        # Ajouter des DHT bootstrap nodes supplementaires
        try:
            self.session.add_dht_node(('router.bittorrent.com', 6881))
            self.session.add_dht_node(('router.utorrent.com', 6881))
            self.session.add_dht_node(('dht.transmissionbt.com', 6881))
            logger.info("DHT bootstrap nodes ajoutes")
        except Exception as e:
            logger.warning(f"Erreur ajout DHT nodes: {e}")

        self.active_torrents: Dict[str, Dict] = {}
        self.download_progress: Dict[str, int] = {}
        
    def extract_info_hash(self, magnet_link: str) -> Optional[str]:
        """Extrait l'info hash d'un magnet link"""
        try:
            start = magnet_link.find('btih:') + 5
            end = magnet_link.find('&', start)
            if end == -1:
                end = len(magnet_link)
            return magnet_link[start:end][:40].upper()
        except:
            return None
    
    def start_download(self, magnet_link: str, title: str = "Unknown") -> Optional[str]:
        """Demarre le telechargement d'un torrent"""
        info_hash = self.extract_info_hash(magnet_link)
        if not info_hash:
            logger.error(f"Impossible d'extraire l'info hash de: {magnet_link[:100]}...")
            return None
        
        if info_hash in self.active_torrents:
            logger.info(f"Torrent deja en cours: {title}")
            return info_hash
        
        try:
            # Parametres du torrent
            params = {
                'save_path': CACHE_DIR,
                'storage_mode': lt.storage_mode_t(1),  # sparse mode
            }
            
            # Ajouter le torrent
            handle = lt.add_magnet_uri(self.session, magnet_link, params)
            
            self.active_torrents[info_hash] = {
                'handle': handle,
                'title': title,
                'magnet': magnet_link,
                'status': 'downloading',
                'files': [],
                'ready_file': None
            }
            
            self.download_progress[info_hash] = 0
            
            # Demarrer le monitoring en arriere-plan
            monitor_thread = threading.Thread(
                target=self._monitor_torrent, 
                args=(info_hash,),
                daemon=True
            )
            monitor_thread.start()
            
            logger.info(f"Torrent ajoute: {title} ({info_hash})")
            return info_hash
            
        except Exception as e:
            logger.error(f"Erreur ajout torrent {title}: {e}")
            return None
    
    def _monitor_torrent(self, info_hash: str):
        """Monitore le progres d'un torrent avec optimisation acces instantane"""
        torrent_info = self.active_torrents[info_hash]
        handle = torrent_info['handle']
        
        logger.info(f"Monitoring torrent: {torrent_info['title']}")
        
        while True:
            try:
                status = handle.status()
                
                # Mise a jour du progres
                progress = int(status.progress * 100)
                self.download_progress[info_hash] = progress
                
                # Check si on a les metadonnees
                if status.has_metadata and not torrent_info['files']:
                    torrent_info['files'] = [f for f in handle.torrent_file().files()]
                    logger.info(f"Metadonnees recues: {len(torrent_info['files'])} fichiers")
                    
                    # IMMEDIATEMENT configurer les priorites pour acces instantane
                    self._setup_instant_access_priorities(info_hash)
                
                # Streaming pret des 1% si on a les metadonnees (acces instantane)
                if progress >= 1 and status.has_metadata and torrent_info['status'] == 'downloading':
                    video_file = self._find_video_file(info_hash)
                    if video_file:
                        torrent_info['status'] = 'streaming'
                        torrent_info['ready_file'] = video_file
                        logger.info(f"Streaming instantane a {progress}%: {video_file}")
                
                # Check si termine
                if status.is_seeding or progress >= 100:
                    torrent_info['status'] = 'completed'
                    logger.info(f"Telechargement termine: {torrent_info['title']}")
                    break
                
                # Log periodique
                if progress % 10 == 0 and progress > 0:
                    logger.info(f" {torrent_info['title']}: {progress}% - {status.num_peers} peers")
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Erreur monitoring {info_hash}: {e}")
                break

    def _setup_instant_access_priorities(self, info_hash: str):
        """Configure les priorites pour acces instantane a toutes les positions"""
        try:
            if info_hash not in self.active_torrents:
                return False
            
            handle = self.active_torrents[info_hash]['handle']
            
            if not handle.status().has_metadata:
                return False
            
            ti = handle.torrent_file()
            total_pieces = ti.num_pieces()
            
            # Strategie d'acces instantane: pre-charger des echantillons repartis
            priorities = [2] * total_pieces  # Priorite normale par defaut
            
            # 1. TRES HAUTE PRIORITE : Debut du fichier (0-5% - metadonnees critiques)
            start_critical = min(50, total_pieces // 20)  # 5% ou 50 pieces max
            for piece in range(start_critical):
                priorities[piece] = 7  # Maximum
                handle.set_piece_deadline(piece, 500)  # 500ms deadline
            
            # 2. HAUTE PRIORITE : Points strategiques pour acces aleatoire
            # Tous les 10% du fichier = points d'acces rapide
            sample_points = [int(total_pieces * i / 10) for i in range(1, 10)]  # 10%, 20%, ... 90%
            
            for point in sample_points:
                if 0 <= point < total_pieces:
                    # 5 pieces autour de chaque point d'echantillon
                    for offset in range(-2, 3):
                        piece_idx = point + offset
                        if 0 <= piece_idx < total_pieces:
                            priorities[piece_idx] = 6  # Haute priorite
                            handle.set_piece_deadline(piece_idx, 2000)  # 2s deadline
            
            # 3. PRIORITE ELEVEE : Points intermediaires (5%, 15%, 25%, etc.)
            intermediate_points = [int(total_pieces * i / 20) for i in range(1, 20, 2)]  # 5%, 15%, 25%...
            
            for point in intermediate_points:
                if 0 <= point < total_pieces:
                    # 2 pieces autour de chaque point intermediaire
                    for offset in range(-1, 2):
                        piece_idx = point + offset
                        if 0 <= piece_idx < total_pieces:
                            priorities[piece_idx] = max(priorities[piece_idx], 5)
            
            handle.prioritize_pieces(priorities)
            
            logger.info(f"Acces instantane configure: {start_critical} pieces critiques + {len(sample_points)} points d'acces")
            return True
            
        except Exception as e:
            logger.error(f"Erreur configuration acces instantane: {e}")
            return False
    
    def _find_video_file(self, info_hash: str) -> Optional[str]:
        """Trouve le fichier video principal dans le torrent"""
        torrent_info = self.active_torrents[info_hash]
        
        if not torrent_info['files']:
            return None
        
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        largest_video = None
        largest_size = 0
        
        for file_info in torrent_info['files']:
            file_path = file_info.path
            file_size = file_info.size
            
            # Check si c'est un fichier video
            if any(file_path.lower().endswith(ext) for ext in video_extensions):
                if file_size > largest_size:
                    largest_size = file_size
                    largest_video = os.path.join(CACHE_DIR, file_path)
        
        return largest_video
    
    def get_streaming_info(self, info_hash: str) -> Optional[Dict]:
        """Retourne les infos de streaming pour un torrent"""
        if info_hash not in self.active_torrents:
            return None
        
        torrent_info = self.active_torrents[info_hash]
        progress = self.download_progress.get(info_hash, 0)
        
        return {
            'info_hash': info_hash,
            'title': torrent_info['title'],
            'status': torrent_info['status'],
            'progress': progress,
            'ready_file': torrent_info.get('ready_file'),
            'can_stream': torrent_info['status'] in ['streaming', 'completed']
        }
    
    def get_video_path(self, info_hash: str) -> Optional[str]:
        """Retourne le chemin du fichier video pour streaming"""
        if info_hash not in self.active_torrents:
            return None
        
        torrent_info = self.active_torrents[info_hash]
        
        # Si le torrent est pret pour le streaming
        if torrent_info['status'] in ['streaming', 'completed']:
            return torrent_info.get('ready_file')
        
        return None
    
    def stop_torrent(self, info_hash: str) -> bool:
        """Arrete et nettoie un torrent specifique"""
        try:
            if info_hash not in self.active_torrents:
                return False
            
            torrent_info = self.active_torrents[info_hash]
            handle = torrent_info['handle']
            
            # Arreter le torrent
            self.session.remove_torrent(handle, lt.options_t.delete_files)
            
            # Nettoyer les references
            del self.active_torrents[info_hash]
            if info_hash in self.download_progress:
                del self.download_progress[info_hash]
            
            # Supprimer fichiers cache
            try:
                import shutil
                cache_dir = os.path.join(CACHE_DIR, f"torrent_{info_hash}")
                if os.path.exists(cache_dir):
                    shutil.rmtree(cache_dir)
            except Exception as e:
                logger.warning(f"Erreur suppression cache: {e}")
            
            logger.info(f" Torrent arrete et nettoye: {torrent_info['title']}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur arret torrent {info_hash}: {e}")
            return False
    
    def set_piece_priorities_for_seeking(self, info_hash: str, seek_position: float):
        """Configure les priorites de telechargement pour le seeking INSTANTANE"""
        try:
            if info_hash not in self.active_torrents:
                return False
            
            torrent_info = self.active_torrents[info_hash]
            handle = torrent_info['handle']
            
            if not handle.status().has_metadata:
                return False
            
            # Calculer les pieces necessaires pour la position demandee
            ti = handle.torrent_file()
            piece_length = ti.piece_length()
            total_size = ti.total_size()
            
            # Position en bytes
            seek_bytes = int(seek_position * total_size)
            seek_piece = seek_bytes // piece_length
            
            # STRATEGIE ULTRA-AGRESSIVE pour acces instantane
            priorities = [1] * ti.num_pieces()  # Tres basse priorite par defaut
            
            # 1. ZONE ULTRA-CRITIQUE (instantane) : 3 pieces autour + deadline immediate
            ultra_critical_start = max(0, seek_piece - 1)
            ultra_critical_end = min(ti.num_pieces(), seek_piece + 2)
            for piece in range(ultra_critical_start, ultra_critical_end):
                priorities[piece] = 7  # Maximum
                handle.set_piece_deadline(piece, 100)  # 100ms SEULEMENT!
            
            # 2. ZONE CRITIQUE (buffer proche) : 15 pieces autour
            critical_start = max(0, seek_piece - 7)
            critical_end = min(ti.num_pieces(), seek_piece + 8)
            for piece in range(critical_start, critical_end):
                if piece not in range(ultra_critical_start, ultra_critical_end):
                    priorities[piece] = 6
                    handle.set_piece_deadline(piece, 500)  # 500ms
            
            # 3. ZONE BUFFER (lecture continue) : 50 pieces apres
            buffer_end = min(ti.num_pieces(), seek_piece + 50)
            for piece in range(critical_end, buffer_end):
                priorities[piece] = 5
                handle.set_piece_deadline(piece, 2000)  # 2s
            
            # 4. MAINTENIR points d'acces strategiques (systeme existant)
            # Conserver les points d'acces 10%, 20%, etc. avec priorite moderee
            sample_points = [int(ti.num_pieces() * i / 10) for i in range(1, 10)]
            for point in sample_points:
                if 0 <= point < ti.num_pieces():
                    priorities[point] = max(priorities[point], 4)
            
            # 5. TOUJOURS maintenir debut du fichier (metadonnees video)
            for piece in range(min(20, ti.num_pieces())):
                priorities[piece] = max(priorities[piece], 6)
            
            handle.prioritize_pieces(priorities)
            
            logger.info(f"SEEKING INSTANTANE: piece {seek_piece} (ultra: {ultra_critical_start}-{ultra_critical_end}, critique: {critical_start}-{critical_end})")
            return True
            
        except Exception as e:
            logger.error(f"Erreur priorites seeking: {e}")
            return False

    def get_piece_availability(self, info_hash: str, seek_position: float = 0.0) -> Dict:
        """Retourne la disponibilite des pieces pour une position donnee (optimise acces instantane)"""
        try:
            if info_hash not in self.active_torrents:
                return {"available": False, "pieces_ready": 0, "total_pieces": 0}
            
            handle = self.active_torrents[info_hash]['handle']
            
            if not handle.status().has_metadata:
                return {"available": False, "pieces_ready": 0, "total_pieces": 0}
            
            ti = handle.torrent_file()
            total_pieces = ti.num_pieces()
            
            # Position en pieces
            seek_piece = int(seek_position * total_pieces)
            
            # ULTRA-CRITIQUE : juste 3 pieces autour (minimum pour demarrer)
            ultra_critical_start = max(0, seek_piece - 1)
            ultra_critical_end = min(total_pieces, seek_piece + 2)
            
            ultra_pieces_ready = 0
            for piece in range(ultra_critical_start, ultra_critical_end):
                if handle.have_piece(piece):
                    ultra_pieces_ready += 1
            
            ultra_pieces_needed = ultra_critical_end - ultra_critical_start
            ultra_availability = ultra_pieces_ready / ultra_pieces_needed if ultra_pieces_needed > 0 else 0
            
            # ELARGIE : zone plus large pour info supplementaire
            extended_start = max(0, seek_piece - 5)
            extended_end = min(total_pieces, seek_piece + 15)
            
            extended_pieces_ready = 0
            for piece in range(extended_start, extended_end):
                if handle.have_piece(piece):
                    extended_pieces_ready += 1
            
            extended_pieces_needed = extended_end - extended_start
            extended_availability = extended_pieces_ready / extended_pieces_needed if extended_pieces_needed > 0 else 0
            
            # CRITERES D'ACCES INSTANTANE :
            # - Si on a au moins 1 piece ultra-critique => IMMEDIAT
            # - OU si on a 30% des pieces etendues => RAPIDE 
            instant_access = (
                ultra_pieces_ready >= 1 or  # Au moins 1 piece critique
                extended_availability >= 0.3  # Ou 30% de la zone etendue
            )
            
            return {
                "available": instant_access,
                "pieces_ready": ultra_pieces_ready,
                "total_pieces": ultra_pieces_needed,
                "seek_piece": seek_piece,
                "availability_ratio": ultra_availability,
                "extended_pieces_ready": extended_pieces_ready,
                "extended_total": extended_pieces_needed,
                "extended_ratio": extended_availability,
                "instant_access_reason": (
                    "ultra_critical" if ultra_pieces_ready >= 1 
                    else "extended_zone" if extended_availability >= 0.3 
                    else "not_ready"
                )
            }
            
        except Exception as e:
            logger.error(f"Erreur verification disponibilite: {e}")
            return {"available": False, "pieces_ready": 0, "total_pieces": 0}

    def cleanup_old_torrents(self):
        """Nettoie les anciens torrents (garde les 5 plus recents)"""
        try:
            if len(self.active_torrents) > 5:  # Reduit de 10 a 5
                # Supprimer les plus anciens
                to_remove = list(self.active_torrents.keys())[:-5]
                for info_hash in to_remove:
                    self.stop_torrent(info_hash)
        except Exception as e:
            logger.error(f"Erreur nettoyage: {e}")

# Instance globale
real_streaming_service = RealStreamingService()