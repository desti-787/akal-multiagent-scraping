"""
Agent Climat — Phase 3

Interroge l'API historique Open-Meteo pour une coordonnée (lat, lon) et
renvoie un objet ClimatData validé (précipitations annuelles, température
moyenne), conforme au contrat de sortie défini en Phase 1 (config/schemas.py).

Utilise la dernière année calendaire complète comme référence (ex: en 2026,
utilise les données de 2025) pour avoir un jeu de données annuel homogène.

Même logique de robustesse que l'agent Sol : validation, retry avec backoff
exponentiel, et gestion des réponses "vides" (toutes valeurs nulles) comme
un échec transitoire à retenter plutôt qu'un résultat valide.
"""

import time
from datetime import datetime
from typing import Optional

import requests

from config.schemas import ClimatData
from agents.utils import validate_coordinates

CLIMAT_URL = "https://archive-api.open-meteo.com/v1/archive"


class ClimatAgentError(Exception):
    """Levée quand l'agent Climat échoue après épuisement de ses tentatives."""


def _annee_reference() -> int:
    """Dernière année calendaire complète (ex: en 2026, renvoie 2025)."""
    return datetime.now().year - 1


def _fetch_open_meteo(lat: float, lon: float, timeout: int) -> dict:
    annee = _annee_reference()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{annee}-01-01",
        "end_date": f"{annee}-12-31",
        "daily": "temperature_2m_mean,precipitation_sum",
        "timezone": "auto",
    }
    response = requests.get(CLIMAT_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _agreger_climat(raw: dict) -> tuple[Optional[float], Optional[float]]:
    """
    Agrège les séries journalières en indicateurs annuels :
    - précipitation annuelle = somme des précipitations journalières
    - température moyenne = moyenne des températures moyennes journalières
    Ignore les valeurs manquantes (None) dans les séries.
    """
    try:
        daily = raw["daily"]
        precipitations = [v for v in daily.get("precipitation_sum", []) if v is not None]
        temperatures = [v for v in daily.get("temperature_2m_mean", []) if v is not None]
    except (KeyError, TypeError):
        return None, None

    precip_annuelle = round(sum(precipitations), 1) if precipitations else None
    temp_moyenne = round(sum(temperatures) / len(temperatures), 1) if temperatures else None

    return precip_annuelle, temp_moyenne


def get_climat_data(lat: float, lon: float, max_retries: int = 3, timeout: int = 15) -> ClimatData:
    """
    Interroge Open-Meteo et renvoie un ClimatData validé pour (lat, lon).

    Retente jusqu'à `max_retries` fois avec backoff exponentiel en cas de
    timeout, erreur réseau, ou réponse "vide" (toutes valeurs nulles).
    Lève ClimatAgentError si tout échoue. Lève ValueError immédiatement
    si les coordonnées sont invalides.
    """
    validate_coordinates(lat, lon)

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = _fetch_open_meteo(lat, lon, timeout=timeout)
            precip_annuelle, temp_moyenne = _agreger_climat(raw)

            if precip_annuelle is None and temp_moyenne is None and attempt < max_retries:
                wait = 2 ** attempt
                print(f"⚠️  Tentative {attempt}/{max_retries} : réponse vide de Open-Meteo — retry dans {wait}s...")
                time.sleep(wait)
                continue

            return ClimatData(precip_annuelle_mm=precip_annuelle, temp_moyenne_c=temp_moyenne)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Erreur HTTP Open-Meteo (tentative {attempt}/{max_retries}) : {e} — retry dans {wait}s...")
            time.sleep(wait)

    raise ClimatAgentError(
        f"Échec de l'agent Climat après {max_retries} tentatives pour ({lat}, {lon}) : {last_error}"
    )


def safe_get_climat_data(lat: float, lon: float, **kwargs) -> Optional[ClimatData]:
    """
    Version "sûre" destinée à l'orchestrateur multi-agent : ne lève jamais
    d'exception, renvoie None en cas d'échec définitif.
    """
    try:
        return get_climat_data(lat, lon, **kwargs)
    except (ValueError, ClimatAgentError) as e:
        print(f"❌ Agent Climat : échec définitif pour ({lat}, {lon}) : {e}")
        return None