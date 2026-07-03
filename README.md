# AKAL — Système multi-agent de data scraping

Système multi-agent chargé de la collecte et de l'enrichissement de données sur les terrains agricoles, dans le cadre du projet AKAL (Africa Centred Technology / SMII).

## Structure du projet

```
akal-multiagent-scraping/
├── agents/       # Un module par agent (sol, climat, ndvi, topographie, accessibilité...)
├── config/       # Configuration (settings, connexion DB)
├── tests/        # Tests unitaires par agent
├── docker/       # docker-compose PostgreSQL/PostGIS
├── .env.example  # Modèle de variables d'environnement (à copier en .env)
└── requirements.txt
```

## Setup

```bash
# 1. Cloner le repo
git clone <url-du-repo>
cd akal-multiagent-scraping

# 2. Créer l'environnement virtuel
python -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 3. Installer les dépendances
pip install -r requirements.txt --break-system-packages

# 4. Configurer les variables d'environnement
cp .env.example .env
# Remplir .env avec les vraies valeurs (clés API, etc.)

# 5. Lancer PostgreSQL/PostGIS via Docker
cd docker
docker compose up -d
```

## État d'avancement

- [x] Phase 0 — Cadrage
- [ ] Phase 1 — Fondations techniques (en cours)
- [ ] Phase 2 — Premier agent isolé (Sol via SoilGrids)
- [ ] Phase 3 — Réplication (Climat, NDVI, Topographie, Accessibilité)
- [ ] Phase 4 — Orchestration multi-agent
