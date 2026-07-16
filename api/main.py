"""
API — Phase 5/6 : expose les agents et l'orchestrateur via HTTP,
pour un rendu visuel (dashboard) plutôt que des logs terminal.

Lancement :
    uvicorn api.main:app --reload --port 8000

Puis ouvrir http://localhost:8000 dans un navigateur.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re as regex_module

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from agents.sol_agent import safe_get_sol_data
from agents.climat_agent import safe_get_climat_data
from agents.ndvi_agent import safe_get_ndvi_data
from agents.topographie_agent import safe_get_topographie_data
from agents.accessibilite_agent import safe_get_accessibilite_data
from agents.orchestrator import enrichir_parcelle
from agents.scraper_agent import scraper_annonces, sauvegarder_annonces_json, DOSSIER_EXPORTS_PAR_DEFAUT

app = FastAPI(title="AKAL Multi-Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/")
def racine():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Agents individuels — utile pour tester/afficher un agent isolément
# ---------------------------------------------------------------------------

@app.get("/api/agents/sol")
def agent_sol(lat: float = Query(...), lon: float = Query(...)):
    resultat = safe_get_sol_data(lat, lon)
    if resultat is None:
        raise HTTPException(status_code=502, detail="Agent Sol : échec ou pas de données pour cette zone.")
    return resultat.model_dump(mode="json")


@app.get("/api/agents/climat")
def agent_climat(lat: float = Query(...), lon: float = Query(...)):
    resultat = safe_get_climat_data(lat, lon)
    if resultat is None:
        raise HTTPException(status_code=502, detail="Agent Climat : échec ou pas de données pour cette zone.")
    return resultat.model_dump(mode="json")


@app.get("/api/agents/ndvi")
def agent_ndvi(lat: float = Query(...), lon: float = Query(...)):
    resultat = safe_get_ndvi_data(lat, lon)
    if resultat is None:
        raise HTTPException(status_code=502, detail="Agent NDVI : échec ou pas de données pour cette zone.")
    return resultat.model_dump(mode="json")


@app.get("/api/agents/topographie")
def agent_topographie(lat: float = Query(...), lon: float = Query(...)):
    resultat = safe_get_topographie_data(lat, lon)
    if resultat is None:
        raise HTTPException(status_code=502, detail="Agent Topographie : échec ou pas de données pour cette zone.")
    return resultat.model_dump(mode="json")


@app.get("/api/agents/accessibilite")
def agent_accessibilite(lat: float = Query(...), lon: float = Query(...)):
    resultat = safe_get_accessibilite_data(lat, lon)
    if resultat is None:
        raise HTTPException(status_code=502, detail="Agent Accessibilité : échec ou pas de données pour cette zone.")
    return resultat.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Orchestrateur — enrichissement complet (5 agents en parallèle)
# ---------------------------------------------------------------------------

@app.get("/api/enrichir")
def enrichir(lat: float = Query(...), lon: float = Query(...)):
    metadata = enrichir_parcelle(lat, lon, verbose=False)
    return metadata.to_json_field()


# ---------------------------------------------------------------------------
# Scraper — annonces Avito (recherche + détail + images + champs basiques)
# ---------------------------------------------------------------------------

@app.get("/api/scraper")
def scraper(max_pages: int = Query(1, ge=1, le=5), telecharger_images: bool = Query(False)):
    categorie_url = "https://www.avito.ma/fr/maroc/terrain_agricole--%C3%A0_vendre"
    annonces = scraper_annonces(categorie_url, max_pages=max_pages, telecharger_les_images=telecharger_images)

    # Sauvegarde le JSON complet (texte non tronqué) AVANT de tronquer pour l'affichage
    _, nom_fichier = sauvegarder_annonces_json(annonces)

    # On tronque le texte brut dans la réponse API (juste utile en debug interne,
    # pas nécessaire à afficher intégralement dans le dashboard)
    for a in annonces:
        a["texte_brut"] = a["texte_brut"][:300] + "..."

    return {"count": len(annonces), "annonces": annonces, "fichier_export": nom_fichier}


@app.get("/api/scraper/export/{nom_fichier}")
def telecharger_export(nom_fichier: str):
    """Télécharge un export JSON complet précédemment sauvegardé par /api/scraper."""
    if not regex_module.fullmatch(r"annonces_\d{8}_\d{6}\.json", nom_fichier):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")

    chemin = os.path.join(DOSSIER_EXPORTS_PAR_DEFAUT, nom_fichier)
    if not os.path.isfile(chemin):
        raise HTTPException(status_code=404, detail="Fichier introuvable.")

    return FileResponse(chemin, media_type="application/json", filename=nom_fichier)


@app.get("/api/scraper/exports")
def lister_exports():
    """Liste tous les exports JSON déjà sauvegardés (pour historique)."""
    if not os.path.isdir(DOSSIER_EXPORTS_PAR_DEFAUT):
        return {"exports": []}
    fichiers = sorted(
        [f for f in os.listdir(DOSSIER_EXPORTS_PAR_DEFAUT) if f.endswith(".json")],
        reverse=True,
    )
    return {"exports": fichiers}


@app.get("/api/health")
def health():
    return {"status": "ok"}