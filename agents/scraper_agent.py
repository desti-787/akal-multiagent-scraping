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


def extraire_annonce_brute(url: str, timeout: int = 20) -> Optional[Dict[str, str]]:
    """
    Récupère le texte brut (nettoyé) d'une page de détail d'annonce.
    Ne structure rien : cette étape est déléguée à l'agent Extractor (Point 20).
    """
    response = _requete(url, timeout=timeout)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    for balise in soup(["script", "style", "nav", "footer", "header"]):
        balise.decompose()

    texte = soup.get_text(separator=" ", strip=True)
    return {"url": url, "texte_brut": texte}


def scraper_annonces(categorie_url: str, max_pages: int = 1, timeout: int = 20) -> List[Dict[str, str]]:
    """
    Pipeline complet : recherche les URLs d'annonces, puis récupère le texte
    brut de chaque page de détail, avec un délai entre chaque requête.
    """
    urls_annonces = rechercher_urls_annonces(categorie_url, max_pages=max_pages, timeout=timeout)
    print(f"🔍 {len(urls_annonces)} annonce(s) trouvée(s) sur {max_pages} page(s) de résultats.\n")

    annonces_brutes = []
    for item in urls_annonces:
        time.sleep(DELAI_ENTRE_REQUETES_S)
        try:
            brute = extraire_annonce_brute(item["url"], timeout=timeout)
            if brute:
                annonces_brutes.append(brute)
        except ScraperAgentError as e:
            print(f"❌ Échec sur {item['url']} : {e}")

    return annonces_brutes