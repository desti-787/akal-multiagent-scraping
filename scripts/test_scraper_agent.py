"""
Test de l'agent Scraper — Phase 5, Point 19

⚠️ Ce test envoie de vraies requêtes à avito.ma. Le périmètre (recherche +
détail) a été validé juridiquement pour ce projet — voir plan directeur.
Reste volontairement limité (peu de pages, délais entre requêtes) pour ne
pas surcharger le serveur.

Usage :
    python3 scripts/test_scraper_agent.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.scraper_agent import rechercher_urls_annonces, extraire_annonce_brute

CATEGORIE_URL = "https://www.avito.ma/fr/maroc/terrain_agricole--%C3%A0_vendre"


def test_recherche_urls():
    print("=== Test recherche d'annonces (1 page) ===\n")
    resultats = rechercher_urls_annonces(CATEGORIE_URL, max_pages=1)
    print(f"{len(resultats)} annonce(s) trouvée(s) :\n")
    for r in resultats[:5]:  # affiche juste les 5 premières pour lisibilité
        print(f"- {r['url']}")
        print(f"  Aperçu : {r['apercu_texte'][:100]}...\n")
    return resultats


def test_extraction_detail(resultats):
    if not resultats:
        print("Aucune URL à tester pour l'extraction détail.")
        return

    print("=== Test extraction d'une page de détail ===\n")
    premiere_url = resultats[0]["url"]
    print(f"URL testée : {premiere_url}\n")
    brute = extraire_annonce_brute(premiere_url)
    if brute:
        print("✅ Extraction réussie")
        print(f"Longueur du texte brut : {len(brute['texte_brut'])} caractères")
        print(f"Aperçu : {brute['texte_brut'][:300]}...\n")
    else:
        print("❌ Extraction échouée (voir logs ci-dessus)\n")


if __name__ == "__main__":
    resultats = test_recherche_urls()
    test_extraction_detail(resultats)
    print("🎉 Tests terminés.")