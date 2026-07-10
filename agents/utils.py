"""
Utilitaires partagés entre les agents (validation des coordonnées, etc.)
"""


def validate_coordinates(lat: float, lon: float) -> None:
    """Lève ValueError si les coordonnées sont hors des plages valides."""
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude invalide : {lat} (doit être entre -90 et 90)")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude invalide : {lon} (doit être entre -180 et 180)")