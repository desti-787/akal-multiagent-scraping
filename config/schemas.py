"""
Contrat de sortie — Phase 1, Point 3

Définit précisément la structure JSON que chaque agent (Sol, Climat, NDVI,
Topographie, Accessibilité) doit produire avant insertion dans le champ
Parcelle.metadata (JSONField) du schéma Django réel.

Chaque bloc est optionnel au niveau de ParcelleMetadata : si un agent échoue
(API indisponible, coordonnées hors couverture...), les autres blocs restent
utilisables plutôt que de faire échouer tout le pipeline.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Bloc SOL — Agent Sol (SoilGrids)
# ---------------------------------------------------------------------------

class TextureData(BaseModel):
    sable_pct: float = Field(..., ge=0, le=100, description="% de sable")
    limon_pct: float = Field(..., ge=0, le=100, description="% de limon")
    argile_pct: float = Field(..., ge=0, le=100, description="% d'argile")


class SolData(BaseModel):
    ph: Optional[float] = Field(None, ge=0, le=14, description="pH du sol (0-5cm)")
    carbone_organique_g_kg: Optional[float] = Field(None, ge=0, description="Carbone organique, g/kg")
    texture: Optional[TextureData] = None
    source: str = "SoilGrids"
    collecte_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Bloc CLIMAT — Agent Climat (Open-Meteo / NASA POWER)
# ---------------------------------------------------------------------------

class ClimatData(BaseModel):
    precip_annuelle_mm: Optional[float] = Field(None, ge=0, description="Précipitations moyennes annuelles, mm")
    temp_moyenne_c: Optional[float] = Field(None, ge=-30, le=60, description="Température moyenne, °C")
    source: str = "Open-Meteo"
    collecte_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Bloc NDVI — Agent NDVI (Sentinel Hub)
# ---------------------------------------------------------------------------

class NdviData(BaseModel):
    valeur_moyenne: Optional[float] = Field(None, ge=-1, le=1, description="Indice NDVI moyen sur la parcelle")
    date_image: Optional[str] = Field(None, description="Date de l'image satellite utilisée (YYYY-MM-DD)")
    source: str = "Sentinel Hub"
    collecte_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Bloc TOPOGRAPHIE — Agent Topographie (OpenTopography / SRTM)
# ---------------------------------------------------------------------------

class TopographieData(BaseModel):
    altitude_m: Optional[float] = Field(None, description="Altitude, mètres")
    pente_pct: Optional[float] = Field(None, ge=0, description="Pente moyenne, %")
    source: str = "OpenTopography"
    collecte_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Bloc ACCESSIBILITÉ — Agent Accessibilité (OSM Overpass)
# ---------------------------------------------------------------------------

class AccessibiliteData(BaseModel):
    distance_route_km: Optional[float] = Field(None, ge=0, description="Distance à la route la plus proche, km")
    distance_ville_km: Optional[float] = Field(None, ge=0, description="Distance à la ville/marché le plus proche, km")
    source: str = "OSM Overpass"
    collecte_le: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Modèle englobant — ce qui atterrit réellement dans Parcelle.metadata
# ---------------------------------------------------------------------------

class ParcelleMetadata(BaseModel):
    """
    Structure complète du champ Parcelle.metadata (JSONField).
    Tous les blocs sont optionnels : un agent qui échoue ne bloque pas
    l'insertion des données des autres agents.
    """
    version_schema: str = "1.0"
    sol: Optional[SolData] = None
    climat: Optional[ClimatData] = None
    ndvi: Optional[NdviData] = None
    topographie: Optional[TopographieData] = None
    accessibilite: Optional[AccessibiliteData] = None

    @field_validator("version_schema")
    @classmethod
    def check_version(cls, v: str) -> str:
        if not v:
            raise ValueError("version_schema ne peut pas être vide")
        return v

    def to_json_field(self) -> dict:
        """Sérialise proprement pour insertion dans le JSONField Django (dates en ISO)."""
        return self.model_dump(mode="json", exclude_none=True)