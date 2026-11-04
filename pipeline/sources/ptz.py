# -*- coding: utf-8 -*-
"""Prêts à taux zéro (PTZ) émis par commune et par année, logements neufs et anciens, montant total et moyen (base SGFGAS, 2017 à 2021)."""
import time, urllib.request
from pathlib import Path
import pandas as pd
import geo

URL = 'https://static.data.gouv.fr/resources/base-de-donnees-ptz-prets-a-taux-zero/20220412-162011/opendataptz2022.csv'
DICO = 'https://static.data.gouv.fr/resources/base-de-donnees-ptz-prets-a-taux-zero/20220412-162222/ptz-dico-opendata-2022.doc'
ANNEES = ['2017', '2018', '2019', '2020', '2021']

SOURCE = {'ref': 'E1-01',
          'nom': 'Base de données PTZ (prêts à taux zéro)',
          'producteur': 'Ministère chargé du logement (données SGFGAS)',
          'url': 'https://www.data.gouv.fr/datasets/base-de-donnees-ptz-prets-a-taux-zero',
          'telechargement': URL,
          'millesime': '2022 (prêts émis de 1995 à 2021, données arrêtées au 31 mars 2022)',
          'licence': 'Licence ouverte'}

SECRET = ("La commune n'est publiée que pour les groupes d'au moins 11 prêts (même année, même commune, même type) : "
          "vide si la commune n'a aucun groupe publié, valeur minimale sinon. Environ la moitié des prêts n'ont pas de commune, "
          "les sommes par territoire sous-estiment donc fortement le total réel.")


def _dl(url, p, essais=8):
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=1800) as r:
                tmp = p.with_suffix(p.suffix + '.part')
                tmp.write_bytes(r.read())
                tmp.replace(p)
                return p
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def charger(cache: Path) -> list:
    d = cache / 'ptz'
    p = _dl(URL, d / 'opendataptz2022.csv')
    _dl(DICO, d / 'ptz-dico-opendata-2022.doc')
    x = pd.read_csv(p, dtype=str, encoding='latin-1', usecols=['an', 'type', 'cins', 'vtpz'])
    x = x[x.an.isin(ANNEES) & x.cins.notna()].copy()
    x['vtpz'] = pd.to_numeric(x.vtpz, errors='coerce')
    x['CODGEO'] = geo.vers_cog2026(x.cins).values
    x = x.dropna(subset=['CODGEO'])
    x['neuf'] = (x.type == '1').astype(int)
    x['ancien'] = (x.type == '0').astype(int)
    g = x.groupby(['CODGEO', 'an']).agg(neuf=('neuf', 'sum'), ancien=('ancien', 'sum'), nb=('vtpz', 'size'), montant=('vtpz', 'sum'))
    out = []
    for a in ANNEES:
        s = g.xs(a, level='an') if a in g.index.get_level_values('an') else g.iloc[0:0]
        s = s.rename(columns=lambda c: f'ptz_{c}_{a}')
        # un type sans prêt publié est sous secret (0 à 10 prêts) : vide plutôt que 0
        for t in ('neuf', 'ancien'):
            s[f'ptz_{t}_{a}'] = s[f'ptz_{t}_{a}'].where(s[f'ptz_{t}_{a}'] > 0)
        out.append(s)
    df = pd.concat(out, axis=1)
    df.index.name = 'CODGEO'
    df = df.reset_index()

    inds = []
    for a in ANNEES:
        df[f'ptz_montant_moyen_{a}'] = df[f'ptz_montant_{a}'] / df[f'ptz_nb_{a}'].where(df[f'ptz_nb_{a}'] > 0)
        inds += [
            {'col': f'ptz_nb_{a}', 'libelle': f'Prêts à taux zéro émis en {a} (commune publiée)', 'unite': 'prêts',
             'definition': f'Nombre de PTZ émis en {a} pour un logement de la commune, neuf et ancien confondus. ' + SECRET,
             'agregation': 'somme', 'annee': a},
            {'col': f'ptz_neuf_{a}', 'libelle': f'Prêts à taux zéro émis en {a} pour un logement neuf', 'unite': 'prêts',
             'definition': f'Nombre de PTZ émis en {a} pour l\'achat ou la construction d\'un logement neuf. ' + SECRET,
             'agregation': 'somme', 'annee': a},
            {'col': f'ptz_ancien_{a}', 'libelle': f'Prêts à taux zéro émis en {a} pour un logement ancien', 'unite': 'prêts',
             'definition': f'Nombre de PTZ émis en {a} pour l\'achat d\'un logement ancien (avec travaux, ou parc social vendu à ses occupants). ' + SECRET,
             'agregation': 'somme', 'annee': a},
            {'col': f'ptz_montant_{a}', 'libelle': f'Montant total des prêts à taux zéro émis en {a}', 'unite': 'euros',
             'definition': f'Somme des montants des PTZ émis en {a} dont la commune est publiée. ' + SECRET,
             'agregation': 'somme', 'annee': a},
            {'col': f'ptz_montant_moyen_{a}', 'libelle': f'Montant moyen d\'un prêt à taux zéro émis en {a}', 'unite': 'euros par prêt',
             'definition': f'Montant total des PTZ émis en {a} divisé par leur nombre (prêts dont la commune est publiée).',
             'agregation': 'ratio', 'num': f'ptz_montant_{a}', 'den': f'ptz_nb_{a}', 'facteur': 1, 'annee': a},
        ]
    df = df[['CODGEO'] + [i['col'] for i in inds]]
    for c in df.columns[1:]:
        df[c] = df[c].astype('float64')
    return [{'theme': 'marche', 'data': df, 'indicateurs': inds}]
