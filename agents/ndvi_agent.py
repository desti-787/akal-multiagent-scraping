"""
Agent NDVI — Phase 3

Interroge la Statistical API de Sentinel Hub (Copernicus Data Space Ecosystem)
pour calculer le NDVI moyen sur une petite zone autour d'une coordonnée
(lat, lon), et renvoie un objet NdviData validé, conforme au contrat de
sortie défini en Phase 1 (config/schemas.py).

Nécessite un OAuth client Sentinel Hub (SENTINEL_HUB_CLIENT_ID /
SENTINEL_HUB_CLIENT_SECRET dans .env).

Limite connue (Phase 3) : en l'absence du polygone réel de la parcelle
(Parcelle.contour, encore nullable dans le schéma Django), on utilise une
petite zone tampon (~200m) autour du point comme approximation. À remplacer
par le vrai contour de la parcelle dès qu'il sera disponible.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
import os

from config.schemas import NdviData
from agents.utils import validate_coordinates

load_dotenv()

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
STATS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"

CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET")

# Demi-côté de la zone tampon autour du point, en degrés (~0.001° ≈ 110m à l'équateur)
BUFFER_DEG = 0.001

# Evalscript : calcule le NDVI, exclut les pixels sans donnée et les pixels d'eau (SCL == 6)
EVALSCRIPT_NDVI = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "data", bands: 1 },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(samples) {
  let ndvi = (samples.B08 - samples.B04) / (samples.B08 + samples.B04);
  let validMask = (samples.B08 + samples.B04 == 0) ? 0 : 1;
  let noWaterMask = (samples.SCL == 6) ? 0 : 1;
  return {
    data: [ndvi],
    dataMask: [samples.dataMask * validMask * noWaterMask]
  };
}
"""

# Cache simple du token en mémoire pour éviter une requête OAuth à chaque appel
_token_cache = {"access_token": None, "expires_at": 0}


class NdviAgentError(Exception):
    """Levée quand l'agent NDVI échoue après épuisement de ses tentatives."""


def _get_access_token(timeout: int = 10) -> str:
    """Récupère un token OAuth, en le réutilisant tant qu'il n'a pas expiré."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise NdviAgentError(
            "SENTINEL_HUB_CLIENT_ID / SENTINEL_HUB_CLIENT_SECRET absents du .env"
        )

    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = now + payload.get("expires_in", 300)
    return _token_cache["access_token"]


def _build_bbox(lat: float, lon: float) -> list:
    """Construit une petite zone tampon [minLon, minLat, maxLon, maxLat] autour du point."""
    return [lon - BUFFER_DEG, lat - BUFFER_DEG, lon + BUFFER_DEG, lat + BUFFER_DEG]


def _fetch_ndvi_stats(lat: float, lon: float, token: str, timeout: int) -> dict:
    now = datetime.now(timezone.utc)
    date_debut = now - timedelta(days=30)

    request_body = {
        "input": {
            "bounds": {
                "bbox": _build_bbox(lat, lon),
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": 50},
                }
            ],
        },
        "aggregation": {
            "timeRange": {
                "from": date_debut.strftime("%Y-%m-%dT00:00:00Z"),
                "to": now.strftime("%Y-%m-%dT23:59:59Z"),
            },
            "aggregationInterval": {"of": "P30D"},
            "evalscript": EVALSCRIPT_NDVI,
            "resx": 10,
            "resy": 10,
        },
    }

    response = requests.post(
        STATS_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=request_body,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json(), now.strftime("%Y-%m-%d")


def _extract_mean_ndvi(raw: dict) -> Optional[float]:
    """Extrait la valeur moyenne de NDVI de la réponse de la Statistical API."""
    try:
        intervalles = raw["data"]
        if not intervalles:
            return None
        bands = intervalles[0]["outputs"]["data"]["bands"]
        premiere_bande = next(iter(bands.values()))
        mean = premiere_bande["stats"]["mean"]
        return round(mean, 3) if mean is not None else None
    except (KeyError, IndexError, StopIteration, TypeError):
        return None


def get_ndvi_data(lat: float, lon: float, max_retries: int = 3, timeout: int = 20) -> NdviData:
    """
    Interroge Sentinel Hub et renvoie un NdviData validé pour (lat, lon).

    Retente jusqu'à `max_retries` fois avec backoff exponentiel en cas de
    timeout, erreur réseau/HTTP, ou réponse sans valeur exploitable
    (ex: zone entièrement nuageuse sur les 30 derniers jours).
    """
    validate_coordinates(lat, lon)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            token = _get_access_token(timeout=timeout)
            raw, date_image = _fetch_ndvi_stats(lat, lon, token, timeout=timeout)
            valeur = _extract_mean_ndvi(raw)

            if valeur is None and attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  Tentative {attempt}/{max_retries} : pas de valeur NDVI exploitable (nuages ?) — retry dans {wait}s...")
                time.sleep(wait)
                continue

            return NdviData(valeur_moyenne=valeur, date_image=date_image)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur HTTP Sentinel Hub (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)

    raise NdviAgentError(
        f"Échec de l'agent NDVI après {max_retries} tentatives pour ({lat}, {lon}) : {last_error}"
    )


def safe_get_ndvi_data(lat: float, lon: float, **kwargs) -> Optional[NdviData]:
    """
    Version "sûre" destinée à l'orchestrateur multi-agent : ne lève jamais
    d'exception, renvoie None en cas d'échec définitif.
    """
    try:
        return get_ndvi_data(lat, lon, **kwargs)
    except (ValueError, NdviAgentError) as e:
        print(f"❌ Agent NDVI : échec définitif pour ({lat}, {lon}) : {e}")
        return None