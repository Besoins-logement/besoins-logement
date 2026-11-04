# -*- coding: utf-8 -*-
"""Emploi salarié privé par commune (Urssaf) : établissements employeurs et effectifs salariés au 31 décembre de 2015 à 2025, total et industrie."""
import time, shutil, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import geo

JEU = 'etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last'
API = f'https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/{JEU}/exports/csv?'
ANNEES = list(range(2015, 2026))
REGIONS = ['01', '02', '03', '04', '11', '24', '27', '28', '32', '44', '52', '53', '75', '76', '84', '93', '94']   # pas de Mayotte dans la source
INDUSTRIE = 'GS1 Industrie'      # grand secteur Urssaf = sections B à E de la NAF (industries extractives, manufacturières, énergie, eau et déchets)


def _url(reg):
    sel = ','.join(f'sum(effectifs_salaries_{a}) as eff_{a},sum(nombre_d_etablissements_{a}) as etab_{a}' for a in ANNEES)
    return API + urllib.parse.urlencode({'select': 'code_commune,grand_secteur_d_activite,' + sel,
                                         'where': f"code_region='{reg}'",
                                         'group_by': 'code_commune,grand_secteur_d_activite', 'delimiter': ';'})


SOURCE = {'ref': 'E4-02',
          'nom': "Nombre d'établissements employeurs et effectifs salariés du secteur privé, par commune et code APE (au 31 décembre depuis 2006)",
          'producteur': 'Urssaf Caisse nationale',
          'url': f'https://open.urssaf.fr/explore/dataset/{JEU}/',
          'telechargement': _url('{code_region}') + ' (une requête d\'agrégation par région)',
          'millesime': 'effectifs au 31 décembre 2015 à 2025 (mise à jour mai 2026)',
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=10):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=900) as r, open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dest)
            return dest
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def charger(cache: Path) -> list:
    rep = Path(cache) / 'urssaf'
    df = pd.concat([pd.read_csv(_telecharger(_url(r), rep / f'urssaf_commune_secteur_reg{r}.csv'), sep=';',
                                dtype={'code_commune': str}, encoding='utf-8-sig') for r in REGIONS], ignore_index=True)
    df['CODGEO'] = geo.vers_cog2026(df.code_commune).values
    df = df.dropna(subset=['CODGEO'])
    cols = [f'{v}_{a}' for a in ANNEES for v in ('eff', 'etab')]
    df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
    tot = df.groupby('CODGEO')[cols].sum(min_count=1)
    ind = df[df.grand_secteur_d_activite == INDUSTRIE].groupby('CODGEO')[cols].sum(min_count=1)
    ind = ind.reindex(tot.index).fillna(0)        # commune sans établissement industriel connu : zéro
    tot.columns = [f'urssaf_{c.replace("eff", "salaries").replace("etab", "etablissements")}' for c in cols]
    ind.columns = [f'urssaf_{c.replace("eff", "salaries_industrie").replace("etab", "etablissements_industrie")}' for c in cols]
    out = tot.join(ind)
    out['urssaf_part_salaries_industrie_2025'] = out.urssaf_salaries_industrie_2025 / out.urssaf_salaries_2025 * 100
    out = out.replace([np.inf, -np.inf], np.nan).reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    champ = (" Champ Urssaf : établissements employeurs du secteur privé relevant du régime général, localisés dans la commune,"
             " hors particuliers employeurs ; l'emploi agricole relevant de la MSA n'est pas couvert.")
    indic = []
    for a in ANNEES:
        indic += [
            {'col': f'urssaf_salaries_{a}', 'libelle': f'Salariés du secteur privé au 31 décembre {a}', 'unite': 'salariés',
             'definition': f"Effectif salarié des établissements employeurs du secteur privé au 31 décembre {a}, tous secteurs d'activité." + champ,
             'agregation': 'somme', 'annee': str(a)},
            {'col': f'urssaf_etablissements_{a}', 'libelle': f'Établissements employeurs du secteur privé au 31 décembre {a}', 'unite': 'établissements',
             'definition': f"Nombre d'établissements du secteur privé employant au moins un salarié au 31 décembre {a}, tous secteurs d'activité." + champ,
             'agregation': 'somme', 'annee': str(a)},
            {'col': f'urssaf_salaries_industrie_{a}', 'libelle': f"Salariés de l'industrie au 31 décembre {a}", 'unite': 'salariés',
             'definition': f"Effectif salarié des établissements du secteur privé dont l'activité principale relève de l'industrie (sections B à E de la NAF : industries extractives, manufacturières, énergie, eau et déchets) au 31 décembre {a}." + champ,
             'agregation': 'somme', 'annee': str(a)},
            {'col': f'urssaf_etablissements_industrie_{a}', 'libelle': f"Établissements employeurs de l'industrie au 31 décembre {a}", 'unite': 'établissements',
             'definition': f"Nombre d'établissements employeurs du secteur privé dont l'activité principale relève de l'industrie (sections B à E de la NAF) au 31 décembre {a}." + champ,
             'agregation': 'somme', 'annee': str(a)},
        ]
    indic.append({'col': 'urssaf_part_salaries_industrie_2025', 'libelle': "Part de l'industrie dans l'emploi salarié privé au 31 décembre 2025", 'unite': '%',
                  'definition': "Salariés de l'industrie (sections B à E de la NAF) divisés par l'ensemble des salariés du secteur privé, au 31 décembre 2025." + champ,
                  'agregation': 'ratio', 'num': 'urssaf_salaries_industrie_2025', 'den': 'urssaf_salaries_2025', 'facteur': 100, 'annee': '2025'})
    out = out[['CODGEO'] + [d['col'] for d in indic]]
    return [{'theme': 'emploi', 'data': out, 'indicateurs': indic}]
