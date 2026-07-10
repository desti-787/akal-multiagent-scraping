"""
Agent Topographie — Phase 3 (v2, sans dépendance GDAL)

Interroge l'API GlobalDEM d'OpenTopography pour une petite zone autour
d'une coordonnée (lat, lon), lit le raster GeoTIFF renvoyé avec `tifffile`
(pure Python, sans dépendance système GDAL), et en déduit l'altitude
(au centre) et la pente moyenne (%), conformément au contrat de sortie
défini en Phase 1 (config/schemas.py).

Note de conception : rasterio/GDAL permettent de lire les métadonnées
géographiques (CRS, transform) directement depuis le fichier, mais nécessitent
GDAL en dépendance système (lourd à installer, source de plusieurs frictions
d'installation sur macOS avec Python 3.14). Comme on connaît déjà précisément
la zone géographique demandée (on l'a nous-mêmes fournie dans la requête à
OpenTopography), on peut se contenter de lire les pixels bruts et recalculer
nous-mêmes la taille des pixels — plus simple, sans dépendance système.

Nécessite une clé API gratuite (OPENTOPOGRAPHY_API_KEY dans .env).
"""

import io
import time
import os
from typing import Optional

import numpy as np
import tifffile
import requests
from dotenv import load_dotenv

from config.schemas import TopographieData
from agents.utils import validate_coordinates

load_dotenv()

GLOBALDEM_URL = "https://portal.opentopography.org/API/globaldem"
API_KEY = os.getenv("OPENTOPOGRAPHY_API_KEY")

# Demi-côté de la zone téléchargée, en degrés (~0.0015° ≈ 165m à l'équateur)
BUFFER_DEG = 0.0015

# Seuil en dessous duquel une valeur est considérée comme "nodata"
# (le point le plus bas du Maroc est autour de -55m ; -1000 laisse une marge large et sûre)
SEUIL_NODATA = -1000

METRES_PAR_DEGRE_LAT = 111_320


class TopographieAgentError(Exception):
    """Levée quand l'agent Topographie échoue après épuisement de ses tentatives."""


def _fetch_dem(lat: float, lon: float, timeout: int) -> bytes:
    if not API_KEY:
        raise TopographieAgentError("OPENTOPOGRAPHY_API_KEY absent du .env")

    params = {
        "demtype": "COP30",  # Copernicus Global DSM 30m — bonne couverture Maroc
        "south": lat - BUFFER_DEG,
        "north": lat + BUFFER_DEG,
        "west": lon - BUFFER_DEG,
        "east": lon + BUFFER_DEG,
        "outputFormat": "GTiff",
        "API_Key": API_KEY,
    }
    response = requests.get(GLOBALDEM_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.content


def _calculer_altitude_et_pente(raster_bytes: bytes) -> tuple:
    """
    Lit le GeoTIFF en mémoire (pixels bruts uniquement, via tifffile) et calcule :
    - l'altitude au centre de la zone
    - la pente moyenne (%) sur la zone, via le gradient de l'altitude

    La taille des pixels en mètres est recalculée à partir de la zone qu'on a
    nous-mêmes demandée (BUFFER_DEG), pas lue depuis les métadonnées du fichier.
    """
    elevation = tifffile.imread(io.BytesIO(raster_bytes)).astype(float)
    elevation[elevation < SEUIL_NODATA] = np.nan

    if np.all(np.isnan(elevation)):
        return None, None

    hauteur, largeur = elevation.shape

    centre_y, centre_x = hauteur // 2, largeur // 2
    altitude = elevation[centre_y, centre_x]
    altitude = float(altitude) if not np.isnan(altitude) else float(np.nanmean(elevation))

    # Taille du pixel en degrés = (zone totale demandée) / (nombre de pixels)
    taille_pixel_deg = (2 * BUFFER_DEG) / hauteur
    taille_pixel_m = taille_pixel_deg * METRES_PAR_DEGRE_LAT

    dz_dy, dz_dx = np.gradient(elevation, taille_pixel_m)
    pente = np.sqrt(dz_dx**2 + dz_dy**2) * 100
    pente_moyenne = float(np.nanmean(pente))

    return round(altitude, 1), round(pente_moyenne, 1)


def get_topographie_data(lat: float, lon: float, max_retries: int = 3, timeout: int = 20) -> TopographieData:
    """
    Interroge OpenTopography et renvoie un TopographieData validé pour (lat, lon).

    Retente en cas de timeout, erreur réseau/HTTP, ou raster entièrement
    en nodata (ex: zone hors couverture du dataset choisi).
    """
    validate_coordinates(lat, lon)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            raster_bytes = _fetch_dem(lat, lon, timeout=timeout)
            altitude, pente = _calculer_altitude_et_pente(raster_bytes)

            if altitude is None and attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  Tentative {attempt}/{max_retries} : raster sans donnée exploitable — retry dans {wait}s...")
                time.sleep(wait)
                continue

            return TopographieData(altitude_m=altitude, pente_pct=pente)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur HTTP OpenTopography (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)
        except Exception as e:  # tifffile peut lever divers types d'erreurs selon le contenu reçu
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur de lecture du raster (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)

    raise TopographieAgentError(
        f"Échec de l'agent Topographie après {max_retries} tentatives pour ({lat}, {lon}) : {last_error}"
    )


def safe_get_topographie_data(lat: float, lon: float, **kwargs) -> Optional[TopographieData]:
    """
    Version "sûre" destinée à l'orchestrateur multi-agent : ne lève jamais
    d'exception, renvoie None en cas d'échec définitif.
    """
    try:
        return get_topographie_data(lat, lon, **kwargs)
    except (ValueError, TopographieAgentError) as e:
        print(f"❌ Agent Topographie : échec définitif pour ({lat}, {lon}) : {e}")
        return None