"""
Exemple d'utilisation du contrat de sortie — Phase 1, Point 3

Simule ce que fera un agent réel en Phase 2 : construire son bloc de données,
le valider via pydantic, puis l'assembler dans ParcelleMetadata avant de
l'insérer (plus tard) dans Parcelle.metadata.

Usage :
    python3 scripts/example_metadata.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.schemas import SolData, TextureData, ClimatData, ParcelleMetadata


def simulate_agent_sol():
    """Simule la sortie de l'agent Sol (ce qu'on codera réellement en Phase 2)."""
    return SolData(
        ph=7.2,
        carbone_organique_g_kg=12.4,
        texture=TextureData(sable_pct=45, limon_pct=30, argile_pct=25),
    )


def simulate_agent_climat():
    """Simule la sortie de l'agent Climat."""
    return ClimatData(precip_annuelle_mm=380, temp_moyenne_c=19.5)


def simulate_agent_ndvi_failed():
    """Simule un agent NDVI qui échoue (API indisponible) — renvoie None."""
    return None


if __name__ == "__main__":
    print("=== Contrat de sortie — exemple de fiche terrain enrichie ===\n")

    # Chaque agent produit son bloc indépendamment
    sol = simulate_agent_sol()
    climat = simulate_agent_climat()
    ndvi = simulate_agent_ndvi_failed()  # ex: SentinelHub down, pas bloquant

    # Assemblage — même si NDVI a échoué, le reste est utilisable
    metadata = ParcelleMetadata(sol=sol, climat=climat, ndvi=ndvi)

    print("✅ Validation pydantic réussie\n")
    print(json.dumps(metadata.to_json_field(), indent=2, ensure_ascii=False))

    # Démonstration : que se passe-t-il si une donnée est invalide ?
    print("\n=== Test de validation (donnée invalide volontaire) ===\n")
    try:
        SolData(ph=25)  # pH impossible, doit être entre 0 et 14
    except Exception as e:
        print(f"✅ Erreur bien détectée par pydantic : {e}")