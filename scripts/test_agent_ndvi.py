"""
Test de l'agent NDVI — Phase 3

Usage :
    python3 scripts/test_agent_ndvi.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ndvi_agent import get_ndvi_data, safe_get_ndvi_data, NdviAgentError

# Mêmes zones agricoles rurales validées pour Sol et Climat (Phase 2-3)
ZONES_TEST = [
    ("Plaine agricole du Saïss (près Meknès)", 34.05, -5.60),
    ("Plaine agricole du Gharb (près Kénitra)", 34.15, -6.35),
    ("Vallée agricole du Souss (près Agadir)", 30.30, -9.40),
    ("Plaine agricole de la Chaouia (près Settat)", 32.95, -7.50),
]


def test_zones_reelles():
    print("=== Test agent NDVI — coordonnées réelles au Maroc ===\n")
    for nom, lat, lon in ZONES_TEST:
        print(f"📍 {nom} ({lat}, {lon})")
        try:
            ndvi = get_ndvi_data(lat, lon)
            print(f"   NDVI moyen : {ndvi.valeur_moyenne}")
            print(f"   Date image : {ndvi.date_image}")
            print("   ✅ OK\n")
        except NdviAgentError as e:
            print(f"   ❌ Échec : {e}\n")


def test_coordonnees_invalides():
    print("=== Test gestion d'erreurs — coordonnées invalides ===\n")
    cas_invalides = [
        ("Latitude hors limites", 200, -5.5473),
        ("Longitude hors limites", 33.8935, 500),
    ]
    for nom, lat, lon in cas_invalides:
        print(f"🔍 {nom} ({lat}, {lon})")
        try:
            get_ndvi_data(lat, lon)
            print("   ⚠️  Aucune erreur levée — problème !\n")
        except ValueError as e:
            print(f"   ✅ Erreur bien détectée : {e}\n")


def test_mode_sans_exception():
    print("=== Test version 'safe' (pour l'orchestrateur) ===\n")
    resultat = safe_get_ndvi_data(999, 999)
    if resultat is None:
        print("✅ safe_get_ndvi_data renvoie bien None au lieu de planter\n")
    else:
        print("⚠️  Résultat inattendu\n")


if __name__ == "__main__":
    test_zones_reelles()
    test_coordonnees_invalides()
    test_mode_sans_exception()
    print("🎉 Tests terminés.")