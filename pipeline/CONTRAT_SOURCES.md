# Contrat d'un module de source

Chaque source publique entre dans la base par un module Python `pipeline/sources/<nom>.py` (nom en minuscules, sans accent).

```python
# -*- coding: utf-8 -*-
"""Une phrase : ce que la source apporte à la base."""
from pathlib import Path
import pandas as pd
import geo   # pipeline/geo.py : geo.vers_cog2026(codes) -> codes communes 2026 ; geo.referentiel() -> communes 2026

SOURCE = {'ref': 'E7-50',                      # référence du catalogue des sources (Tableau_sources v2), ou 'B2-xx' si nouvelle
          'nom': 'Statistiques DVF - prix au m2 et nombre de ventes',
          'producteur': 'DGALN / Cerema (données DGFiP)',
          'url': 'https://www.data.gouv.fr/datasets/statistiques-dvf',      # page de présentation
          'telechargement': 'https://...',     # adresse exacte du fichier utilisé
          'millesime': '2025 (ventes 2020-2025)',
          'licence': 'Licence ouverte 2.0'}

def charger(cache: Path) -> list:
    """Télécharge (dans cache/<nom>/, une seule fois) et renvoie une liste de blocs."""
    ...
    return [{
        'theme': 'marche',          # territoire, population, logement, construction, besoins, marche, revenus, emploi, equipements, risques_energie
        'data': df,                 # une ligne par commune 2026 : colonne CODGEO (texte, 5 caractères) + colonnes d'indicateurs
        'indicateurs': [
            {'col': 'dvf_ventes_maisons_2024', 'libelle': 'Ventes de maisons en 2024', 'unite': 'ventes',
             'definition': 'Nombre de mutations à titre onéreux de maisons, année 2024.', 'agregation': 'somme', 'annee': '2024'},
            {'col': 'dvf_prix_m2_maisons_2024', 'libelle': 'Prix médian au m2 des maisons en 2024', 'unite': 'euros par m2',
             'definition': '...', 'agregation': 'non_additif', 'poids': 'dvf_ventes_maisons_2024', 'annee': '2024'},
            {'col': 'part_x', 'libelle': '...', 'unite': '%', 'definition': '...', 'agregation': 'ratio',
             'num': 'col_numerateur', 'den': 'col_denominateur', 'facteur': 100, 'annee': '2023'},
            {'col': 'zonage_abc', 'libelle': 'Zone ABC', 'unite': '', 'definition': '...', 'agregation': 'texte'},
        ],
        'publies': {'EPCI': df_epci, 'DEP': df_dep, 'REG': df_reg, 'FRANCE': df_fr},   # facultatif : valeurs publiées par la source
    }]
```

Règles :

1. Codes communes : toujours passer par `geo.vers_cog2026()` ; si plusieurs anciennes communes tombent dans une commune 2026, additionner les effectifs (ou recalculer les taux à partir des effectifs). Aucune ligne hors des 34 875 communes 2026, aucun doublon.
2. `agregation` : `somme` (effectif, s'additionne de la commune à la France), `ratio` (taux recalculé à chaque niveau = somme(num) / somme(den) x facteur ; num et den doivent être des colonnes du bloc), `non_additif` (médiane, prix, indice : valeur publiée par la source quand elle existe pour le niveau, sinon moyenne pondérée par `poids` si donné, sinon vide), `texte` (catégorie à la commune, par exemple zone ABC).
3. Pour une catégorie (zonage), ajouter aussi des colonnes 0/1 en `somme` (nombre de communes dans la catégorie) quand c'est utile.
4. `publies` : DataFrame avec colonne `CODE` (code du niveau, géographie la plus récente possible) et les mêmes colonnes `non_additif` ; clés possibles 'EPCI', 'DEP', 'REG', 'ZE2020', 'FRANCE' (code 'FR').
5. Libellés et définitions en français simple, sans tiret cadratin. Unités explicites. Noms de colonnes : préfixe court de la source + sujet + année, en minuscules, sans accent.
6. Données ouvertes seulement, sans compte ni clé. Si une source exige une inscription, est payante ou refuse le téléchargement, la laisser de côté et le signaler.
7. Test : `cd pipeline && python3 tester_source.py <nom>` doit afficher CONTRAT RESPECTÉ. Les sorties vont dans `cache/sorties/`.
