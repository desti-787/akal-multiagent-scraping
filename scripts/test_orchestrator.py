"""
Test de l'orchestrateur multi-agent — Phase 4

Usage :
    python3 scripts/test_orchestrator.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import enrichir_parcelle
import agents.orchestrator as orch

ZONES_TEST = [
    ("Plaine agricole du Saïss (près Meknès)", 34.05, -5.60),
    ("Vallée agricole du Souss (près Agadir)", 30.30, -9.40),
]


def test_orchestration_complete():
    print("=== Test orchestrateur — enrichissement complet (5 agents en parallèle) ===\n")
    for nom, lat, lon in ZONES_TEST:
        print(f"📍 {nom} ({lat}, {lon})")
        metadata = enrichir_parcelle(lat, lon)
        print("\nJSON final (prêt pour Parcelle.metadata) :")
        print(json.dumps(metadata.to_json_field(), indent=2, ensure_ascii=False))
        print("\n" + "=" * 60 + "\n")


def test_resilience_echec_partiel():
    """
    Simule un agent en échec systématique (sans dépendre de la disponibilité
    réseau réelle) pour prouver que le pipeline continue malgré tout.
    """
    print("=== Test résilience — un agent en échec ne bloque pas les autres ===\n")

    original_ndvi = orch.AGENTS["ndvi"]
    orch.AGENTS["ndvi"] = lambda lat, lon, **kw: None  # simule Sentinel Hub down

    try:
        metadata = enrichir_parcelle(34.05, -5.60)
        assert metadata.ndvi is None, "ndvi aurait dû être None"

        print(f"   sol présent      : {metadata.sol is not None}")
        print(f"   climat présent   : {metadata.climat is not None}")
        print(f"   ndvi présent     : {metadata.ndvi is not None} (doit être False, échec simulé)")
        print(f"   topographie présent : {metadata.topographie is not None}")
        print(f"   accessibilité présent : {metadata.accessibilite is not None}")
        print("\n✅ Le pipeline a bien continué malgré l'échec simulé de l'agent NDVI\n")
    finally:
        orch.AGENTS["ndvi"] = original_ndvi  # remet l'agent réel en place


if __name__ == "__main__":
    test_orchestration_complete()
    test_resilience_echec_partiel()
    print("🎉 Tests terminés.")