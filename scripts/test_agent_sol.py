"""
Test de l'agent Sol — Phase 2, Points 2 et 3

Teste l'agent sur des coordonnées réelles de zones agricoles marocaines,
puis vérifie que la gestion d'erreurs (coordonnées invalides) fonctionne.

Usage :
    python3 scripts/test_agent_sol.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.sol_agent import get_sol_data, safe_get_sol_data, SolAgentError

# Coordonnées réelles de zones agricoles au Maroc
ZONES_TEST = [
    ("Plaine agricole du Saïss (rural, près Meknès)", 34.05, -5.60),
    ("Plaine agricole du Gharb (rural, près Kénitra)", 34.15, -6.35),
    ("Vallée agricole du Souss (rural, près Agadir)", 30.30, -9.40),
    ("Plaine agricole de la Chaouia (rural, près Settat)", 32.95, -7.50),
]



def test_zones_reelles():
    print("=== Test agent Sol — coordonnées réelles au Maroc ===\n")
    for nom, lat, lon in ZONES_TEST:
        print(f"📍 {nom} ({lat}, {lon})")
        try:
            sol = get_sol_data(lat, lon)
            print(f"   pH : {sol.ph}")
            print(f"   Carbone organique : {sol.carbone_organique_g_kg} g/kg")
            if sol.texture:
                print(f"   Texture : sable={sol.texture.sable_pct}% "
                      f"limon={sol.texture.limon_pct}% argile={sol.texture.argile_pct}%")
            else:
                print("   Texture : non disponible")
            print("   ✅ OK\n")
        except SolAgentError as e:
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
            get_sol_data(lat, lon)
            print("   ⚠️  Aucune erreur levée — problème, ça aurait dû échouer !\n")
        except ValueError as e:
            print(f"   ✅ Erreur bien détectée : {e}\n")


def test_mode_sans_exception():
    print("=== Test version 'safe' (pour l'orchestrateur) ===\n")
    resultat = safe_get_sol_data(999, 999)  # coordonnées invalides
    if resultat is None:
        print("✅ safe_get_sol_data renvoie bien None au lieu de planter\n")
    else:
        print("⚠️  Résultat inattendu\n")


if __name__ == "__main__":
    test_zones_reelles()
    test_coordonnees_invalides()
    test_mode_sans_exception()
    print("🎉 Tests terminés.")