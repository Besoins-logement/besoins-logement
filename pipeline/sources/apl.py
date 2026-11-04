# -*- coding: utf-8 -*-
"""Accessibilité potentielle localisée (APL) aux médecins généralistes par commune (DREES) : offre de consultations accessible par habitant."""
import time, shutil, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

AN = '2024'
URL = ('https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets/'
       '530_l-accessibilite-potentielle-localisee-apl/attachments/indicateur_d_apl_aux_medecins_generalistes_xlsx')
SEUIL = 2.5      # consultations par an et par habitant : seuil usuel de sous-densité en médecine générale

SOURCE = {'ref': 'E7-15',
          'nom': "Accessibilité potentielle localisée (APL) aux médecins généralistes",
          'producteur': 'DREES (données Cnam SNDS et Insee)',
          'url': 'https://data.drees.solidarites-sante.gouv.fr/explore/dataset/530_l-accessibilite-potentielle-localisee-apl/',
          'telechargement': URL,
          'millesime': f'APL {AN} (activité des médecins {AN}, populations municipales 2022), feuille « APL {AN} »',
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=8):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dest)
            return dest
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def charger(cache: Path) -> list:
    xl = _telecharger(URL, Path(cache) / 'apl' / 'indicateur_apl_medecins_generalistes.xlsx')
    d = pd.read_excel(xl, sheet_name=f'APL {AN}', header=None, dtype=str, engine='calamine').iloc[10:, :8]
    d.columns = ['code', 'lib', 'apl', 'apl65', 'apl62', 'apl60', 'pop_std', 'pop']
    d = d[d.code.notna()]
    for c in ['apl', 'apl65', 'pop_std', 'pop']:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d['CODGEO'] = geo.vers_cog2026(d.code).values
    d = d.dropna(subset=['CODGEO'])
    d['pop_sous_seuil'] = np.where(d.apl.notna(), np.where(d.apl < SEUIL, d['pop'], 0.0), np.nan)
    # regroupement des anciennes communes : APL moyen pondéré par la population standardisée (méthode DREES)
    for c in ['apl', 'apl65']:
        d[c + '_x'] = d[c] * d.pop_std
    g = d.groupby('CODGEO')
    out = g[['pop_std', 'pop', 'pop_sous_seuil', 'apl_x', 'apl65_x']].sum(min_count=1)
    w = d.pop_std.where(d.apl.notna()).groupby(d.CODGEO).sum(min_count=1)
    w65 = d.pop_std.where(d.apl65.notna()).groupby(d.CODGEO).sum(min_count=1)
    out['apl'] = out.apl_x / w
    out['apl65'] = out.apl65_x / w65
    seul = g.size() == 1                       # commune sans regroupement : valeur publiée telle quelle
    pub = d.drop_duplicates('CODGEO').set_index('CODGEO')
    out.loc[seul, 'apl'] = pub.loc[seul[seul].index, 'apl']
    out.loc[seul, 'apl65'] = pub.loc[seul[seul].index, 'apl65']
    out = out.replace([np.inf, -np.inf], np.nan)
    out = out.rename(columns={'apl': f'apl_mg_{AN}', 'apl65': f'apl_mg_65ans_{AN}', 'pop_std': f'apl_pop_standardisee_{AN}',
                              'pop': f'apl_pop_{AN}', 'pop_sous_seuil': f'apl_pop_sous_2_5_{AN}'})
    out[f'apl_part_pop_sous_2_5_{AN}'] = out[f'apl_pop_sous_2_5_{AN}'] / out[f'apl_pop_{AN}'] * 100
    out = out.reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    champ = (" Champ : médecins généralistes libéraux (y compris certains modes d'exercice particulier) et salariés des centres de santé ;"
             " l'offre tient compte des médecins des communes voisines (jusqu'à 20 minutes) et des besoins selon l'âge des habitants.")
    ind = [
        {'col': f'apl_mg_{AN}', 'libelle': f'Accessibilité potentielle localisée aux médecins généralistes en {AN}',
         'unite': 'consultations par an et par habitant standardisé',
         'definition': f"Nombre de consultations ou visites de médecine générale accessibles en {AN} par habitant, compte tenu de l'offre de la commune et des communes proches et de la structure par âge de la population." + champ
                       + " Au-dessus de la commune : moyenne pondérée par la population standardisée, comme le recommande la DREES.",
         'agregation': 'non_additif', 'poids': f'apl_pop_standardisee_{AN}', 'annee': AN},
        {'col': f'apl_mg_65ans_{AN}', 'libelle': f'Accessibilité potentielle localisée aux médecins généralistes de 65 ans ou moins en {AN}',
         'unite': 'consultations par an et par habitant standardisé',
         'definition': f"Même indicateur en ne comptant que l'offre des médecins généralistes âgés de 65 ans ou moins, ce qui anticipe les départs en retraite, année {AN}."
                       + " Au-dessus de la commune : moyenne pondérée par la population standardisée.",
         'agregation': 'non_additif', 'poids': f'apl_pop_standardisee_{AN}', 'annee': AN},
        {'col': f'apl_pop_standardisee_{AN}', 'libelle': f"Population standardisée pour la médecine générale (APL {AN})", 'unite': 'habitants standardisés',
         'definition': "Population municipale 2022 pondérée par la consommation moyenne de soins de médecine générale de chaque tranche d'âge (calcul DREES). Sert de poids pour l'APL moyen.",
         'agregation': 'somme', 'annee': AN},
        {'col': f'apl_pop_{AN}', 'libelle': f"Population prise en compte pour l'APL {AN}", 'unite': 'habitants',
         'definition': "Population municipale 2022 utilisée par la DREES pour l'APL. Sert de dénominateur à la part de la population sous le seuil.",
         'agregation': 'somme', 'annee': AN},
        {'col': f'apl_pop_sous_2_5_{AN}', 'libelle': f"Population des communes où l'APL aux médecins généralistes est inférieure à 2,5 en {AN}", 'unite': 'habitants',
         'definition': f"Population municipale 2022 des communes dont l'APL aux médecins généralistes {AN} est inférieure à 2,5 consultations par an et par habitant, seuil usuel de sous-densité médicale (calculé sur les communes publiées par la DREES avant regroupement).",
         'agregation': 'somme', 'annee': AN},
        {'col': f'apl_part_pop_sous_2_5_{AN}', 'libelle': f"Part de la population dont l'APL aux médecins généralistes est inférieure à 2,5 en {AN}", 'unite': '%',
         'definition': f"Population des communes dont l'APL aux médecins généralistes {AN} est inférieure à 2,5 consultations par an et par habitant, divisée par la population totale.",
         'agregation': 'ratio', 'num': f'apl_pop_sous_2_5_{AN}', 'den': f'apl_pop_{AN}', 'facteur': 100, 'annee': AN},
    ]
    out = out[['CODGEO'] + [x['col'] for x in ind]]
    return [{'theme': 'equipements', 'data': out, 'indicateurs': ind}]
