# -*- coding: utf-8 -*-
"""Statistiques DVF : nombre de ventes et prix au m2 des maisons et des appartements par commune et par année (avec valeurs publiées pour les EPCI, les départements et la France)."""
import time, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

BASE = 'https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/'
MENSUEL = BASE + 'stats_dvf.csv'
PERIODE = BASE + 'stats_whole_period.csv'
ANNEES = ['2022', '2023', '2024', '2025']          # années complètes du fichier mensuel (juillet 2021 à juin 2026)
P5 = '2021_2026'                                   # période glissante de 5 ans du fichier « statistiques totales »
TYPES = {'maison': 'maisons', 'appartement': 'appartements'}

SOURCE = {'ref': 'E7-50',
          'nom': 'Statistiques DVF - prix au m2 et nombre de ventes',
          'producteur': 'data.gouv.fr (Etalab) à partir de DVF (DGFiP)',
          'url': 'https://www.data.gouv.fr/datasets/statistiques-dvf',
          'telechargement': MENSUEL + ' ; ' + PERIODE,
          'millesime': 'octobre 2026 (ventes de juillet 2021 à juin 2026)',
          'licence': 'Licence ouverte 2.0'}

ARR = [str(c) for c in list(range(75101, 75121)) + list(range(69381, 69390)) + list(range(13201, 13217))]


def _dl(url, p, essais=8):
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=1800) as r:
                tmp = p.with_suffix(p.suffix + '.part')
                tmp.write_bytes(r.read())
                tmp.rename(p)
                return p
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def _annuel(m, cle):
    """Ventes annuelles (somme des mois) et prix annuel = moyenne des médianes mensuelles pondérée par les ventes du mois."""
    out = []
    for t, lib in TYPES.items():
        nb, med = f'nb_ventes_{t}', f'med_prix_m2_{t}'
        x = m[[cle, 'annee', nb, med]].copy()
        x['pond'] = x[nb].where(x[med].notna())
        x['prod'] = x['pond'] * x[med]
        g = x.groupby([cle, 'annee']).agg(n=(nb, 'sum'), pond=('pond', 'sum'), prod=('prod', 'sum'))
        g['prix'] = (g['prod'] / g['pond'].where(g['pond'] > 0)).round(0)
        for a in ANNEES:
            s = g.xs(a, level='annee') if a in g.index.get_level_values('annee') else g.iloc[0:0]
            out.append(s['n'].rename(f'dvf_ventes_{lib}_{a}'))
            out.append(s['prix'].rename(f'dvf_prix_m2_{lib}_{a}'))
            out.append(s['pond'].rename(f'_pond_{lib}_{a}'))
    return pd.concat(out, axis=1)


def charger(cache: Path) -> list:
    d = cache / 'dvf_stats'
    pm = _dl(MENSUEL, d / 'stats_dvf.csv')
    pp = _dl(PERIODE, d / 'stats_whole_period.csv')
    num = [f'{a}_{t}' for t in TYPES for a in ('nb_ventes', 'med_prix_m2')]
    m = pd.read_csv(pm, dtype={'code_geo': str, 'annee_mois': str}, usecols=['code_geo', 'echelle_geo', 'annee_mois'] + num)
    m = m[m.echelle_geo.isin(['commune', 'epci', 'departement', 'nation'])]
    m['annee'] = m.annee_mois.str[:4]
    m = m[m.annee.isin(ANNEES)]
    # un EPCI à cheval sur deux départements figure deux fois avec les mêmes valeurs : on dédoublonne
    m = m.drop_duplicates(['echelle_geo', 'code_geo', 'annee_mois'])
    w = pd.read_csv(pp, dtype={'code_geo': str})
    w = w[w.echelle_geo.isin(['commune', 'epci', 'departement', 'nation'])].drop_duplicates(['echelle_geo', 'code_geo'])

    # Communes : on garde Paris, Lyon et Marseille entiers et on écarte leurs arrondissements (déjà inclus)
    mc = m[(m.echelle_geo == 'commune') & ~m.code_geo.isin(ARR)].copy()
    mc['CODGEO'] = geo.vers_cog2026(mc.code_geo).values
    mc = mc.dropna(subset=['CODGEO'])
    an = _annuel(mc, 'CODGEO')

    wc = w[(w.echelle_geo == 'commune') & ~w.code_geo.isin(ARR)].copy()
    wc['CODGEO'] = geo.vers_cog2026(wc.code_geo).values
    wc = wc.dropna(subset=['CODGEO'])
    per = []
    for t, lib in TYPES.items():
        nb, med = f'nb_ventes_whole_{t}', f'med_prix_m2_whole_{t}'
        x = wc[['CODGEO', nb, med]].copy()
        x['pond'] = x[nb].where(x[med].notna())
        x['prod'] = x['pond'] * x[med]
        g = x.groupby('CODGEO').agg(n=(nb, 'sum'), pond=('pond', 'sum'), prod=('prod', 'sum'))
        per += [g['n'].rename(f'dvf_ventes_{lib}_{P5}'), (g['prod'] / g['pond'].where(g['pond'] > 0)).round(0).rename(f'dvf_prix_m2_{lib}_{P5}')]
    per = pd.concat(per, axis=1)

    df = an.join(per, how='outer')
    df = df[[c for c in df.columns if not c.startswith('_pond')]]
    df.index.name = 'CODGEO'
    df = df.reset_index()
    # Les ventes à 0 sont des absences de vente (communes couvertes par DVF) : on ne garde pas de prix sans vente
    for c in [c for c in df.columns if c.startswith('dvf_ventes_')]:
        df[c] = df[c].fillna(0)
    for c in [c for c in df.columns if c.startswith('dvf_')]:
        df[c] = df[c].astype('float64')
    # DVF ne couvre pas l'Alsace-Moselle (livre foncier) ni Mayotte : valeurs inconnues, pas zéro
    hors = df.CODGEO.str[:2].isin(['57', '67', '68']) | df.CODGEO.str.startswith('976')
    df = df[~hors]

    # Valeurs publiées pour EPCI, départements et France (même méthode, mêmes fichiers)
    pub = {}
    for niv, ech in [('EPCI', 'epci'), ('DEP', 'departement'), ('FRANCE', 'nation')]:
        a = _annuel(m[m.echelle_geo == ech], 'code_geo')
        a = a[[c for c in a.columns if c.startswith('dvf_prix')]]
        b = w[w.echelle_geo == ech].set_index('code_geo')
        for t, lib in TYPES.items():
            a = a.join(b[f'med_prix_m2_whole_{t}'].rename(f'dvf_prix_m2_{lib}_{P5}'), how='outer')
        a.index.name = 'CODE'
        a = a.reset_index()
        if niv == 'FRANCE':
            a['CODE'] = 'FR'
        pub[niv] = a

    inds = []
    for a in ANNEES:
        for t, lib in TYPES.items():
            inds.append({'col': f'dvf_ventes_{lib}_{a}', 'libelle': f'Ventes de {lib} en {a}', 'unite': 'ventes',
                         'definition': f'Nombre de ventes de {lib} retenues dans les statistiques DVF en {a} (mutations à titre onéreux d\'un seul bien, hors Alsace-Moselle et Mayotte où DVF n\'existe pas).',
                         'agregation': 'somme', 'annee': a})
            inds.append({'col': f'dvf_prix_m2_{lib}_{a}', 'libelle': f'Prix médian au m2 des {lib} en {a}', 'unite': 'euros par m2',
                         'definition': f'Prix de vente au m2 de surface habitable des {lib} en {a} : moyenne des prix médians mensuels publiés, pondérée par le nombre de ventes de chaque mois (la source ne publie pas de médiane annuelle). Vide sans vente.',
                         'agregation': 'non_additif', 'poids': f'dvf_ventes_{lib}_{a}', 'annee': a})
    for t, lib in TYPES.items():
        inds.append({'col': f'dvf_ventes_{lib}_{P5}', 'libelle': f'Ventes de {lib} de juillet 2021 à juin 2026', 'unite': 'ventes',
                     'definition': f'Nombre de ventes de {lib} retenues dans les statistiques DVF sur les 5 ans allant de juillet 2021 à juin 2026.',
                     'agregation': 'somme', 'annee': '2021-2026'})
        inds.append({'col': f'dvf_prix_m2_{lib}_{P5}', 'libelle': f'Prix médian au m2 des {lib} de juillet 2021 à juin 2026', 'unite': 'euros par m2',
                     'definition': f'Prix médian de vente au m2 des {lib} sur les 5 ans allant de juillet 2021 à juin 2026, publié par la source (médiane vraie, plus robuste pour les petites communes).',
                     'agregation': 'non_additif', 'poids': f'dvf_ventes_{lib}_{P5}', 'annee': '2021-2026'})
    df = df[['CODGEO'] + [i['col'] for i in inds]]
    return [{'theme': 'marche', 'data': df, 'indicateurs': inds, 'publies': pub}]
