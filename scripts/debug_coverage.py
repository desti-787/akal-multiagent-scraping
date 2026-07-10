"""
Diagnostic de couverture SoilGrids — teste plusieurs points
pour distinguer un vrai trou de couverture régional d'un souci ponctuel.
"""

import sys
sys.path.insert(0, ".")

from agents.sol_agent import get_sol_data

POINTS_TEST = [
    ("Référence Pays-Bas (connu fonctionnel)", 52.0, 5.0),
    ("Nairobi, Kenya (référence Afrique)", -1.2864, 36.8172),
    ("Meknès, Maroc (exact)", 33.8935, -5.5473),
    ("Meknès, Maroc (+0.1 lat)", 33.9935, -5.5473),
    ("Meknès, Maroc (-0.1 lat)", 33.7935, -5.5473),
    ("Rabat, Maroc (centre-ville)", 34.0209, -6.8416),
    ("Marrakech, Maroc", 31.6295, -7.9811),
]

for nom, lat, lon in POINTS_TEST:
    sol = get_sol_data(lat, lon)
    statut = "✅" if sol.ph is not None else "❌ (None)"
    print(f"{statut} {nom} ({lat}, {lon}) — pH: {sol.ph}")