"""
Test de l'agent Accessibilité — Phase 3

Usage :
    python3 scripts/test_agent_accessibilite.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.accessibilite_agent import (
    get_accessibilite_data,
    safe_get_accessibilite_data,
    AccessibiliteAgentError,
)

# Mêmes zones agricoles rurales validées pour les 4 agents précédents
ZONES_TEST = [
    ("Plaine agricole du Saïss (près Meknès)", 34.05, -5.60),
    ("Plaine agricole du Gharb (près Kénitra)", 34.15, -6.35),
    ("Vallée agricole du Souss (près Agadir)", 30.30, -9.40),
    ("Plaine agricole de la Chaouia (près Settat)", 32.95, -7.50),
]


def test_zones_reelles():
    print("=== Test agent Accessibilité — coordonnées réelles au Maroc ===\n")
    for nom, lat, lon in ZONES_TEST:
        print(f"📍 {nom} ({lat}, {lon})")
        try:
            acces = get_accessibilite_data(lat, lon)
            print(f"   Distance route la plus proche : {acces.distance_route_km} km")
            print(f"   Distance ville la plus proche : {acces.distance_ville_km} km")
            print("   ✅ OK\n")
        except AccessibiliteAgentError as e:
            print(f"   ❌ Échec : {e}\n")
        time.sleep(3)  # ménage l'instance publique Overpass entre chaque zone


def test_coordonnees_invalides():
    print("=== Test gestion d'erreurs — coordonnées invalides ===\n")
    cas_invalides = [
        ("Latitude hors limites", 200, -5.5473),
        ("Longitude hors limites", 33.8935, 500),
    ]
    for nom, lat, lon in cas_invalides:
        print(f"🔍 {nom} ({lat}, {lon})")
        try:
            get_accessibilite_data(lat, lon)
            print("   ⚠️  Aucune erreur levée — problème !\n")
        except ValueError as e:
            print(f"   ✅ Erreur bien détectée : {e}\n")


def test_mode_sans_exception():
    print("=== Test version 'safe' (pour l'orchestrateur) ===\n")
    resultat = safe_get_accessibilite_data(999, 999)
    if resultat is None:
        print("✅ safe_get_accessibilite_data renvoie bien None au lieu de planter\n")
    else:
        print("⚠️  Résultat inattendu\n")


if __name__ == "__main__":
    test_zones_reelles()
    test_coordonnees_invalides()
    test_mode_sans_exception()
    print("🎉 Tests terminés.")