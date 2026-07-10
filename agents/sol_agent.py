"""
Agent Sol — Phase 2, Point 1

Interroge l'API SoilGrids (ISRIC) pour une coordonnée (lat, lon) et renvoie
un objet SolData validé (pH, carbone organique, texture), conforme au
contrat de sortie défini en Phase 1 (config/schemas.py).

Gère : validation des coordonnées, timeout, retry avec backoff exponentiel,
et un échec "propre" qui ne bloque pas le reste du pipeline multi-agent.
"""

import time
from typing import Optional

import requests

from config.schemas import SolData, TextureData
from agents.utils import validate_coordinates

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Facteurs de conversion officiels SoilGrids (les valeurs brutes sont
# multipliées par 10 pour rester en entiers) — cf. documentation ISRIC.
CONVERSION_FACTORS = {
    "phh2o": 10,   # valeur brute / 10 = pH
    "soc": 10,     # valeur brute / 10 = g/kg
    "clay": 10,    # valeur brute / 10 = %
    "sand": 10,    # valeur brute / 10 = %
    "silt": 10,    # valeur brute / 10 = %
}


class SolAgentError(Exception):
    """Levée quand l'agent Sol échoue après épuisement de ses tentatives."""


def _fetch_soilgrids(lat: float, lon: float, timeout: int) -> dict:
    params = [
        ("lon", lon),
        ("lat", lat),
        ("property", "phh2o"),
        ("property", "soc"),
        ("property", "clay"),
        ("property", "sand"),
        ("property", "silt"),
        ("depth", "0-5cm"),
        ("value", "mean"),
    ]
    response = requests.get(SOILGRIDS_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _extract_value(data: dict, property_name: str) -> Optional[float]:
    """Extrait et convertit la valeur 'mean' d'une propriété du JSON SoilGrids."""
    try:
        for layer in data["properties"]["layers"]:
            if layer["name"] == property_name:
                raw_value = layer["depths"][0]["values"]["mean"]
                if raw_value is None:
                    return None
                factor = CONVERSION_FACTORS.get(property_name, 1)
                return round(raw_value / factor, 2)
    except (KeyError, IndexError, TypeError):
        return None
    return None


def get_sol_data(lat: float, lon: float, max_retries: int = 3, timeout: int = 10) -> SolData:
    """
    Interroge SoilGrids et renvoie un SolData validé pour (lat, lon).

    Retente jusqu'à `max_retries` fois avec backoff exponentiel (2s, 4s, 8s...)
    en cas de timeout ou d'erreur réseau. Lève SolAgentError si tout échoue.
    Lève ValueError immédiatement si les coordonnées sont invalides (pas de retry,
    ça ne sert à rien de réessayer une coordonnée impossible).
    """
    validate_coordinates(lat, lon)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = _fetch_soilgrids(lat, lon, timeout=timeout)

            ph = _extract_value(raw, "phh2o")
            soc = _extract_value(raw, "soc")
            sand = _extract_value(raw, "sand")
            silt = _extract_value(raw, "silt")
            clay = _extract_value(raw, "clay")

            # SoilGrids répond parfois 200 OK avec des valeurs "mean": null
            # partout (service dégradé), sans lever d'erreur HTTP. On traite
            # ce cas comme un échec transitoire à retenter, sauf à la dernière tentative.
            toutes_valeurs_vides = all(v is None for v in (ph, soc, sand, silt, clay))
            if toutes_valeurs_vides and attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  Tentative {attempt}/{max_retries} : réponse vide (null) de SoilGrids — retry dans {wait}s...")
                time.sleep(wait)
                continue

            texture = None
            if None not in (sand, silt, clay):
                texture = TextureData(sable_pct=sand, limon_pct=silt, argile_pct=clay)

            return SolData(ph=ph, carbone_organique_g_kg=soc, texture=texture)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur HTTP SoilGrids (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)

    raise SolAgentError(
        f"Échec de l'agent Sol après {max_retries} tentatives pour ({lat}, {lon}) : {last_error}"
    )


def safe_get_sol_data(lat: float, lon: float, **kwargs) -> Optional[SolData]:
    """
    Version "sûre" destinée à l'orchestrateur multi-agent (Phase 4) :
    ne lève jamais d'exception, renvoie None en cas d'échec définitif
    (coordonnées invalides ou API injoignable après retries), pour ne
    pas bloquer les autres agents.
    """
    try:
        return get_sol_data(lat, lon, **kwargs)
    except (ValueError, SolAgentError) as e:
        print(f"❌ Agent Sol : échec définitif pour ({lat}, {lon}) : {e}")
        return None