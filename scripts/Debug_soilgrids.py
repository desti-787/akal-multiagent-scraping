"""
Script de diagnostic — inspecte la réponse brute de SoilGrids
pour vérifier que la structure JSON correspond à ce que le parser attend.

Usage :
    python3 scripts/debug_soilgrids.py
"""

import json
import requests

SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Vallée du Souss (Agadir) — celle qui a renvoyé des valeurs None
lat, lon = 30.4278, -9.5981

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

print(f"Requête pour ({lat}, {lon})...\n")
response = requests.get(SOILGRIDS_URL, params=params, timeout=15)
print(f"Status code : {response.status_code}\n")

data = response.json()
print(json.dumps(data, indent=2)[:3000])  # limite l'affichage aux 3000 premiers caractères