# -*- coding: utf-8 -*-
"""LOVAC : logements vacants du parc privé par commune (vacance totale et vacance de plus de 2 ans) et parc privé total."""
import time, urllib.request
from pathlib import Path
import pandas as pd
import geo

BASE = 'https://static.data.gouv.fr/resources/logements-vacants-du-parc-prive-par-commune-departement-region-france/'
URL = BASE + '20260625-163627/lovac-opendata-communes26.csv'
META = BASE + '20260625-162628/lovac-opendata-metadonnees26.csv'

SOURCE = {'ref': 'P2-006',
          'nom': 'LOVAC - logements vacants du parc privé par commune',
          'producteur': 'DGALN, Cerema (données DGFiP 1767 bis Com et Fichiers fonciers)',
          'url': 'https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region-france',
          'telechargement': URL,
          'millesime': 'LOVAC 2026 (juin 2026), séries 2024 à 2026',
          'licence': 'Licence ouverte 2.0'}

# millésime LOVAC -> date de situation (métadonnées de la source)
DATES = {'24': '1er janvier 2023', '25': '1er janvier 2024', '26': '1er janvier 2025'}


def _dl(url, p, essais=8):
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                p.write_bytes(r.read())
                return p
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def _somme_stricte(df, cle, cols):
    """Somme par commune 2026 ; vide si une des anciennes communes regroupées est sous secret."""
    s = df.groupby(cle)[cols].sum(min_count=1)
    manque = df[cols].isna().groupby(df[cle]).any()
    return s.mask(manque)


def charger(cache: Path) -> list:
    d = cache / 'lovac'
    p = _dl(URL, d / 'lovac-opendata-communes26.csv')
    _dl(META, d / 'lovac-opendata-metadonnees26.csv')
    raw = pd.read_csv(p, sep=';', dtype=str, encoding='cp1252')
    src = {}
    for m in DATES:
        src[f'pp_vacant_{m}'] = f'lovac_vacants_20{m}'
        src[f'pp_vacant_plus_2ans_{m}'] = f'lovac_vacants_2ans_20{m}'
        if f'ff_pp_total_{m}' in raw.columns:
            src[f'ff_pp_total_{m}'] = f'lovac_parc_prive_20{m}'
    x = raw[['CODGEO_26'] + list(src)].rename(columns=src)
    cols = list(src.values())
    for c in cols:   # 's' = secret statistique (moins de 11 logements) -> vide
        x[c] = pd.to_numeric(x[c].str.replace(r'\s', '', regex=True), errors='coerce')
    x['CODGEO'] = geo.vers_cog2026(x.CODGEO_26).values
    x = x.dropna(subset=['CODGEO'])
    df = _somme_stricte(x, 'CODGEO', cols).reset_index()

    inds = []
    for m, dt in DATES.items():
        a = f'20{m}'
        if f'lovac_parc_prive_{a}' in df.columns:
            inds.append({'col': f'lovac_parc_prive_{a}', 'libelle': f'Logements du parc privé (LOVAC {a})', 'unite': 'logements',
                         'definition': f'Nombre de logements du parc privé au {dt} selon les Fichiers fonciers (millésime LOVAC {a}). Vide si secret statistique.',
                         'agregation': 'somme', 'annee': a})
        inds.append({'col': f'lovac_vacants_{a}', 'libelle': f'Logements vacants du parc privé (LOVAC {a})', 'unite': 'logements',
                     'definition': f'Nombre de logements privés vacants au {dt}, toutes durées de vacance, selon le fichier fiscal 1767 bis Com (millésime LOVAC {a}). Vide si secret statistique (moins de 11 logements) ; les totaux additionnés sous-estiment donc un peu le nombre réel.',
                     'agregation': 'somme', 'annee': a})
        inds.append({'col': f'lovac_vacants_2ans_{a}', 'libelle': f'Logements vacants depuis plus de 2 ans du parc privé (LOVAC {a})', 'unite': 'logements',
                     'definition': f'Nombre de logements privés vacants depuis plus de deux ans au {dt} (vacance structurelle, millésime LOVAC {a}). Vide si secret statistique (moins de 11 logements).',
                     'agregation': 'somme', 'annee': a})
        if f'lovac_parc_prive_{a}' in df.columns:
            for k, lib, num in [('', 'Taux de vacance du parc privé', f'lovac_vacants_{a}'),
                                ('_2ans', 'Taux de vacance de plus de 2 ans du parc privé', f'lovac_vacants_2ans_{a}')]:
                col = f'lovac_taux_vacance{k}_{a}'
                df[col] = df[num] / df[f'lovac_parc_prive_{a}'].where(df[f'lovac_parc_prive_{a}'] > 0) * 100
                inds.append({'col': col, 'libelle': f'{lib} (LOVAC {a})', 'unite': '%',
                             'definition': f'Logements privés vacants{" depuis plus de 2 ans" if k else ""} rapportés au parc privé total, au {dt}.',
                             'agregation': 'ratio', 'num': num, 'den': f'lovac_parc_prive_{a}', 'facteur': 100, 'annee': a})
    df = df[['CODGEO'] + [i['col'] for i in inds]]
    for c in df.columns[1:]:
        df[c] = df[c].astype('float64')
    return [{'theme': 'logement', 'data': df, 'indicateurs': inds}]
