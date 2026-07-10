"""
Agent Accessibilité — Phase 3

Interroge l'API Overpass (OpenStreetMap) pour calculer la distance entre
une coordonnée (lat, lon) et la route la plus proche, ainsi que la ville/
village le plus proche, conformément au contrat de sortie défini en
Phase 1 (config/schemas.py).

Contrairement aux agents précédents, la recherche élargit progressivement
son rayon si rien n'est trouvé (une zone rurale isolée peut légitimement
n'avoir aucune route taguée à 5km, sans que ce soit une erreur) — logique
distincte du retry réseau classique (timeout, erreur HTTP), géré séparément.
"""

import time
import math
from typing import Optional, List, Tuple

import requests

from config.schemas import AccessibiliteData
from agents.utils import validate_coordinates

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "AKAL-MultiAgent-Scraping/1.0 (projet stage EIGSI - contact: originalshop@github)"}

# Rayons de recherche progressifs, en mètres
RAYONS_ROUTE_M = [5_000, 15_000, 40_000]
RAYONS_VILLE_M = [20_000, 50_000, 100_000]


class AccessibiliteAgentError(Exception):
    """Levée quand l'agent Accessibilité échoue après épuisement de ses tentatives réseau."""


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance à vol d'oiseau entre deux points (formule de Haversine)."""
    r = 6371.0  # rayon terrestre moyen, km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _query_overpass(query: str, timeout: int) -> dict:
    response = requests.post(OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _distance_route_km(lat: float, lon: float, timeout: int) -> Optional[float]:
    """Élargit progressivement le rayon jusqu'à trouver une route, ou abandonne."""
    for rayon in RAYONS_ROUTE_M:
        query = f"""
        [out:json][timeout:25];
        way(around:{rayon},{lat},{lon})["highway"];
        out geom;
        """
        data = _query_overpass(query, timeout)
        elements = data.get("elements", [])
        if not elements:
            continue

        distances = [
            _haversine_km(lat, lon, pt["lat"], pt["lon"])
            for way in elements
            for pt in way.get("geometry", [])
        ]
        if distances:
            return round(min(distances), 2)

    return None


def _distance_ville_km(lat: float, lon: float, timeout: int) -> Optional[float]:
    """Élargit progressivement le rayon jusqu'à trouver une ville/village, ou abandonne."""
    for rayon in RAYONS_VILLE_M:
        query = f"""
        [out:json][timeout:25];
        (
          node(around:{rayon},{lat},{lon})["place"~"city|town|village"];
          way(around:{rayon},{lat},{lon})["place"~"city|town|village"];
        );
        out center;
        """
        data = _query_overpass(query, timeout)
        elements = data.get("elements", [])
        if not elements:
            continue

        distances = []
        for el in elements:
            if el["type"] == "node":
                distances.append(_haversine_km(lat, lon, el["lat"], el["lon"]))
            elif "center" in el:
                distances.append(_haversine_km(lat, lon, el["center"]["lat"], el["center"]["lon"]))

        if distances:
            return round(min(distances), 2)

    return None


def get_accessibilite_data(lat: float, lon: float, max_retries: int = 3, timeout: int = 25) -> AccessibiliteData:
    """
    Interroge Overpass et renvoie un AccessibiliteData validé pour (lat, lon).

    Retente en cas de timeout/erreur réseau/HTTP (max_retries, backoff exponentiel).
    Si aucune route ou ville n'est trouvée même après élargissement du rayon
    de recherche, renvoie une valeur None pour ce champ (absence légitime de
    donnée OSM à proximité, pas une erreur du pipeline).
    """
    validate_coordinates(lat, lon)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            distance_route = _distance_route_km(lat, lon, timeout=timeout)
            time.sleep(1.5)  # ménage l'instance publique Overpass entre les deux requêtes
            distance_ville = _distance_ville_km(lat, lon, timeout=timeout)
            return AccessibiliteData(
                distance_route_km=distance_route,
                distance_ville_km=distance_ville,
            )

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur HTTP Overpass (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)

    raise AccessibiliteAgentError(
        f"Échec de l'agent Accessibilité après {max_retries} tentatives pour ({lat}, {lon}) : {last_error}"
    )


def safe_get_accessibilite_data(lat: float, lon: float, **kwargs) -> Optional[AccessibiliteData]:
    """
    Version "sûre" destinée à l'orchestrateur multi-agent : ne lève jamais
    d'exception, renvoie None en cas d'échec définitif.
    """
    try:
        return get_accessibilite_data(lat, lon, **kwargs)
    except (ValueError, AccessibiliteAgentError) as e:
        print(f"❌ Agent Accessibilité : échec définitif pour ({lat}, {lon}) : {e}")
        return None