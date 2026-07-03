"""
Script de test — Phase 1, Point 2
Vérifie que PostGIS tourne bien et qu'une requête géospatiale simple fonctionne.

Usage :
    python3 scripts/test_postgis.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://akal_user:akal_password@localhost:5544/akal_db"
)


def test_connection():
    """Vérifie la connexion de base à PostgreSQL."""
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        version = result.scalar()
        print("✅ Connexion PostgreSQL réussie")
        print(f"   {version}\n")
        return engine


def test_postgis_extension(engine):
    """Vérifie que l'extension PostGIS est bien active."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT PostGIS_version();"))
        postgis_version = result.scalar()
        print("✅ Extension PostGIS active")
        print(f"   {postgis_version}\n")


def test_geospatial_query(engine):
    """
    Requête géospatiale simple : calcule la distance en km
    entre deux points réels au Maroc (Meknès et Fès).
    """
    query = text("""
        SELECT ST_Distance(
            ST_SetSRID(ST_MakePoint(:lon_a, :lat_a), 4326)::geography,
            ST_SetSRID(ST_MakePoint(:lon_b, :lat_b), 4326)::geography
        ) / 1000 AS distance_km;
    """)

    with engine.connect() as conn:
        result = conn.execute(
            query,
            {"lon_a": -5.5473, "lat_a": 33.8935, "lon_b": -4.9998, "lat_b": 34.0331},
        )
        distance_km = result.scalar()
        print("✅ Requête géospatiale réussie")
        print(f"   Distance Meknès → Fès : {distance_km:.2f} km\n")


if __name__ == "__main__":
    print("=== Test PostGIS — Phase 1, Point 2 ===\n")
    try:
        engine = test_connection()
        test_postgis_extension(engine)
        test_geospatial_query(engine)
        print("🎉 Tous les tests sont passés — la base est prête pour la Phase 2.")
    except Exception as e:
        print(f"❌ Erreur : {e}")
        print("\nVérifie que le conteneur Docker tourne bien : docker compose ps")
