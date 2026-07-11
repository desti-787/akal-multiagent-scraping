"""
Orchestrateur multi-agent — Phase 4

Appelle les 5 agents (Sol, Climat, NDVI, Topographie, Accessibilité) en
parallèle pour une coordonnée donnée, et assemble leurs résultats dans un
ParcelleMetadata unique, prêt pour insertion dans Parcelle.metadata.

Principe de résilience : chaque agent est appelé via sa version "safe_"
(qui ne lève jamais d'exception, renvoie None en cas d'échec). Un agent en
échec n'empêche donc jamais les autres d'aboutir — le champ correspondant
est simplement absent du JSON final plutôt que de faire échouer tout le
pipeline.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.schemas import ParcelleMetadata
from agents.sol_agent import safe_get_sol_data
from agents.climat_agent import safe_get_climat_data
from agents.ndvi_agent import safe_get_ndvi_data
from agents.topographie_agent import safe_get_topographie_data
from agents.accessibilite_agent import safe_get_accessibilite_data

# Registre des agents : nom -> fonction "safe_" correspondante.
# Un dict plutôt qu'une liste en dur permet de patcher facilement un agent
# lors des tests (voir scripts/test_orchestrator.py, test de résilience).
AGENTS = {
    "sol": safe_get_sol_data,
    "climat": safe_get_climat_data,
    "ndvi": safe_get_ndvi_data,
    "topographie": safe_get_topographie_data,
    "accessibilite": safe_get_accessibilite_data,
}


def enrichir_parcelle(lat: float, lon: float, verbose: bool = True) -> ParcelleMetadata:
    """
    Orchestre l'appel aux 5 agents en parallèle pour une coordonnée donnée,
    et assemble les résultats dans un ParcelleMetadata unique.

    Un agent qui échoue (renvoie None) n'empêche pas les autres d'aboutir :
    le champ correspondant reste simplement absent du JSON final.
    """
    resultats = {}
    debut = time.time()

    with ThreadPoolExecutor(max_workers=len(AGENTS)) as executor:
        futures = {executor.submit(fn, lat, lon): nom for nom, fn in AGENTS.items()}
        for future in as_completed(futures):
            nom = futures[future]
            try:
                resultats[nom] = future.result()
            except Exception as e:
                # Filet de sécurité : safe_get_* ne devrait jamais lever,
                # mais on protège quand même l'orchestrateur d'un bug inattendu
                # dans un agent (erreur de programmation, pas juste un échec réseau).
                if verbose:
                    print(f"⚠️  Agent '{nom}' a levé une exception inattendue : {e}")
                resultats[nom] = None

    duree = time.time() - debut

    if verbose:
        reussites = [nom for nom, val in resultats.items() if val is not None]
        echecs = [nom for nom, val in resultats.items() if val is None]
        print(f"\n=== Orchestration terminée en {duree:.1f}s ===")
        print(f"✅ Réussis ({len(reussites)}/{len(AGENTS)}) : {', '.join(reussites) or 'aucun'}")
        if echecs:
            print(f"❌ Échoués ({len(echecs)}/{len(AGENTS)}) : {', '.join(echecs)}")

    return ParcelleMetadata(
        sol=resultats.get("sol"),
        climat=resultats.get("climat"),
        ndvi=resultats.get("ndvi"),
        topographie=resultats.get("topographie"),
        accessibilite=resultats.get("accessibilite"),
    )