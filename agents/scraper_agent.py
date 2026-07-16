"""
Agent Scraper — Phase 5, Point 19

Collecte les annonces de terrains agricoles sur Avito (recherche + détail),
périmètre validé juridiquement (voir plan directeur, section risques).

Principes de collecte responsable appliqués, indépendamment de la validation
juridique du périmètre :
- Respect du robots.txt du site, vérifié dynamiquement à l'exécution (pas
  figé dans le code : le site peut faire évoluer ses règles).
- User-Agent identifiable (pas d'usurpation de navigateur).
- Requêtes espacées (rate limiting), pour ne pas surcharger le serveur.
- Ce module se contente de COLLECTER le texte brut des annonces. La
  structuration (titre, prix, surface, culture...) est déléguée à l'agent
  Extractor (Point 20), qui utilise un LLM justement parce que le HTML brut
  d'un site peut changer de structure sans préavis — un texte brut + LLM
  est plus robuste que des sélecteurs CSS figés.

Limite connue : les sélecteurs/URL ci-dessous sont basés sur la structure
observée d'Avito au moment du développement. Si le site change sa structure
HTML, le motif de reconnaissance des liens d'annonces (_RE_LIEN_ANNONCE)
devra être mis à jour.
"""

import time
import re
import os
import json
from datetime import datetime
import urllib.robotparser
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.avito.ma"
HEADERS = {
    "User-Agent": "AKAL-MultiAgent-Scraping/1.0 (projet stage EIGSI - collecte validee juridiquement)"
}

# Reconnaît les liens de pages de détail d'annonce, ex:
# /fr/azemmour/terrains_et_fermes/Terrain_agricole_..._57989189.htm
_RE_LIEN_ANNONCE = re.compile(r"/terrains_et_fermes/.+_\d+\.htm$")

# Reconnaît les URLs des vraies photos d'annonces (hébergées sur le CDN d'Avito),
# ex: https://content.avito.ma/classifieds/images/10147610840?t=images
_RE_IMAGE_URL = re.compile(r"https://content\.avito\.ma/classifieds/images/\d+(\?t=images)?")

DOSSIER_IMAGES_PAR_DEFAUT = "data/images"
DOSSIER_EXPORTS_PAR_DEFAUT = "data/exports"

# Extraction de champs basiques sans LLM (gratuit) — couvre les cas structurés
# et prévisibles ; les nuances fines (type de culture précis, statut foncier
# détaillé) restent du ressort de l'agent Extractor LLM (Point 20).
_RE_PRIX_MENSUEL = re.compile(r"[\d\s]+DH\s*/\s*mois")
_RE_PRIX = re.compile(r"([\d][\d\s]{2,})\s*DH(?!\s*/\s*mois)")
_RE_SURFACE_LABELISEE = re.compile(r"(?:Superficie|Surface totale|Surface)\D{0,10}([\d][\d\s]*)\s*m[²2]", re.IGNORECASE)
_RE_SURFACE = re.compile(r"([\d][\d\s]*)\s*m[²2]")
_CATEGORIES_CONNUES = ["Agricole", "Villa", "Immeuble", "Local", "Bureau", "Appartement"]

DELAI_ENTRE_REQUETES_S = 3.0  # ménage le serveur d'Avito entre chaque requête

# Cache du robots.txt (un seul chargement par session, pas un re-fetch à chaque URL)
_robots_parser: Optional[urllib.robotparser.RobotFileParser] = None


class ScraperAgentError(Exception):
    """Levée en cas d'échec réseau après épuisement des tentatives."""


def _get_robots_parser() -> urllib.robotparser.RobotFileParser:
    global _robots_parser
    if _robots_parser is None:
        _robots_parser = urllib.robotparser.RobotFileParser()
        # On récupère le contenu via `requests` (gère correctement les certificats
        # SSL via certifi) plutôt que via `parser.read()` qui utilise urllib en
        # interne et peut échouer sur macOS (certificats système non configurés
        # avec les installations Python.org).
        try:
            response = requests.get(urljoin(BASE_URL, "/robots.txt"), headers=HEADERS, timeout=10)
            response.raise_for_status()
            _robots_parser.parse(response.text.splitlines())
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Impossible de récupérer robots.txt ({e}) — prudence : aucune requête ne sera autorisée.")
            _robots_parser.parse(["User-agent: *", "Disallow: /"])  # repli prudent : tout bloquer
    return _robots_parser


def _url_autorisee(url: str) -> bool:
    """Vérifie le robots.txt avant toute requête — jamais contourné, même
    si le périmètre légal global a été validé pour ce projet."""
    parser = _get_robots_parser()
    return parser.can_fetch(HEADERS["User-Agent"], url)


def _requete(url: str, timeout: int, max_retries: int = 3) -> Optional[requests.Response]:
    if not _url_autorisee(url):
        print(f"⛔ URL exclue par robots.txt, ignorée : {url}")
        return None

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️  Tentative {attempt}/{max_retries} échouée ({type(e).__name__}) — retry dans {wait}s...")
            time.sleep(wait)

    raise ScraperAgentError(f"Échec de la requête vers {url} après {max_retries} tentatives : {last_error}")


def rechercher_urls_annonces(categorie_url: str, max_pages: int = 1, timeout: int = 20) -> List[Dict[str, str]]:
    """
    Parcourt les pages de résultats de recherche et renvoie la liste des
    annonces trouvées : [{"url": ..., "apercu_texte": ...}, ...]

    apercu_texte = texte brut du lien (contient souvent déjà titre/prix/
    surface tels qu'affichés dans la liste de résultats).
    """
    resultats: List[Dict[str, str]] = []
    urls_vues = set()

    for page in range(1, max_pages + 1):
        url_page = categorie_url if page == 1 else f"{categorie_url}?o={page}"
        response = _requete(url_page, timeout=timeout)
        if response is None:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for lien in soup.find_all("a", href=True):
            href = lien["href"]
            if not _RE_LIEN_ANNONCE.search(href):
                continue

            url_absolue = urljoin(BASE_URL, href)
            if url_absolue in urls_vues:
                continue
            urls_vues.add(url_absolue)

            resultats.append({
                "url": url_absolue,
                "apercu_texte": lien.get_text(separator=" ", strip=True),
            })

        if page < max_pages:
            time.sleep(DELAI_ENTRE_REQUETES_S)

    return resultats


def _extraire_images(soup: BeautifulSoup) -> List[str]:
    """
    Extrait les URLs des vraies photos d'une annonce (galerie + og:image),
    en excluant les icônes/logos/placeholders du site.
    """
    urls = []

    # 1. Balise og:image (souvent la photo de couverture, fiable)
    meta_og = soup.find("meta", property="og:image")
    if meta_og and meta_og.get("content"):
        if _RE_IMAGE_URL.match(meta_og["content"]):
            urls.append(meta_og["content"])

    # 2. Toutes les images de la galerie
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if _RE_IMAGE_URL.match(src) and src not in urls:
            urls.append(src)

    return urls


def _extraire_champs_bases(soup: BeautifulSoup, texte_brut: str) -> Dict:
    """
    Extraction de champs structurés basiques, sans LLM (gratuit) :
    titre, prix, surface, catégorie, statut "titré".
    Approche par règles/regex — moins nuancée qu'un LLM mais fiable sur
    les champs bien formatés (prix, surface), et sans coût d'API.
    """
    titre = None
    meta_titre = soup.find("meta", property="og:title")
    if meta_titre and meta_titre.get("content"):
        titre = meta_titre["content"].split(" - ")[0].strip()

    prix_dh = None
    if "non spécifié" not in texte_brut.lower() and "demander le prix" not in texte_brut.lower():
        for match in _RE_PRIX.finditer(texte_brut):
            candidat = match.group(0)
            if _RE_PRIX_MENSUEL.search(texte_brut[match.start():match.start() + len(candidat) + 15]):
                continue
            prix_dh = int(re.sub(r"\s", "", match.group(1)))
            break

    surface_m2 = None
    match_surface = _RE_SURFACE_LABELISEE.search(texte_brut) or _RE_SURFACE.search(texte_brut)
    if match_surface:
        surface_m2 = int(re.sub(r"\s", "", match_surface.group(1)))

    categorie = next((cat for cat in _CATEGORIES_CONNUES if cat in texte_brut), None)
    titre_foncier = "titré" in texte_brut.lower() or "titre" in texte_brut.lower()

    return {
        "titre": titre,
        "prix_dh": prix_dh,
        "surface_m2": surface_m2,
        "categorie": categorie,
        "titre_foncier": titre_foncier,
    }


def extraire_annonce_brute(url: str, timeout: int = 20) -> Optional[Dict]:
    """
    Récupère le texte brut (nettoyé), les URLs des photos, et des champs
    structurés basiques (sans LLM) d'une page de détail d'annonce.
    Les nuances fines (culture précise, statut foncier détaillé) restent
    déléguées à l'agent Extractor LLM (Point 20).
    """
    response = _requete(url, timeout=timeout)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    images = _extraire_images(soup)

    for balise in soup(["script", "style", "nav", "footer", "header"]):
        balise.decompose()

    texte = soup.get_text(separator=" ", strip=True)
    champs = _extraire_champs_bases(soup, texte)

    return {"url": url, "texte_brut": texte, "images": images, **champs}


def telecharger_images(images: List[str], annonce_id: str, dossier: str = DOSSIER_IMAGES_PAR_DEFAUT,
                        timeout: int = 20) -> List[str]:
    """
    Télécharge les images d'une annonce sur disque, dans dossier/annonce_id/.
    Renvoie la liste des chemins locaux des fichiers effectivement téléchargés.
    Respecte le même délai entre requêtes que le reste du scraper.
    """
    dossier_annonce = os.path.join(dossier, annonce_id)
    os.makedirs(dossier_annonce, exist_ok=True)

    chemins_locaux = []
    for i, url_image in enumerate(images, start=1):
        try:
            response = requests.get(url_image, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Échec du téléchargement de l'image {url_image} : {e}")
            continue

        chemin = os.path.join(dossier_annonce, f"{i}.jpg")
        with open(chemin, "wb") as f:
            f.write(response.content)
        chemins_locaux.append(chemin)
        time.sleep(1.0)  # ménage le CDN entre chaque image

    return chemins_locaux


def _extraire_id_annonce(url: str) -> str:
    """Extrait l'identifiant numérique d'une annonce depuis son URL (ex: ..._57769101.htm -> '57769101')."""
    match = re.search(r"_(\d+)\.htm$", url)
    return match.group(1) if match else "inconnu"


def scraper_annonces(categorie_url: str, max_pages: int = 1, timeout: int = 20,
                      telecharger_les_images: bool = False) -> List[Dict]:
    """
    Pipeline complet : recherche les URLs d'annonces, puis récupère le texte
    brut et les images de chaque page de détail, avec un délai entre chaque
    requête. Si telecharger_les_images=True, sauvegarde aussi les photos sur
    disque (dans data/images/{id_annonce}/).
    """
    urls_annonces = rechercher_urls_annonces(categorie_url, max_pages=max_pages, timeout=timeout)
    print(f"🔍 {len(urls_annonces)} annonce(s) trouvée(s) sur {max_pages} page(s) de résultats.\n")

    annonces_brutes = []
    for item in urls_annonces:
        time.sleep(DELAI_ENTRE_REQUETES_S)
        try:
            brute = extraire_annonce_brute(item["url"], timeout=timeout)
            if not brute:
                continue

            if telecharger_les_images and brute["images"]:
                annonce_id = _extraire_id_annonce(brute["url"])
                brute["images_locales"] = telecharger_images(brute["images"], annonce_id)

            annonces_brutes.append(brute)
        except ScraperAgentError as e:
            print(f"❌ Échec sur {item['url']} : {e}")

    return annonces_brutes


def sauvegarder_annonces_json(annonces: List[Dict], dossier: str = DOSSIER_EXPORTS_PAR_DEFAUT) -> tuple:
    """
    Sauvegarde la liste complète des annonces scrapées dans un fichier JSON
    horodaté (data/exports/annonces_YYYYMMDD_HHMMSS.json), pour livrer un
    export tangible des données collectées.

    Renvoie (chemin_complet, nom_fichier).
    """
    os.makedirs(dossier, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom_fichier = f"annonces_{horodatage}.json"
    chemin = os.path.join(dossier, nom_fichier)

    export = {
        "date_export": datetime.now().isoformat(),
        "nombre_annonces": len(annonces),
        "annonces": annonces,
    }

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)

    return chemin, nom_fichier