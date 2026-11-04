# -*- coding: utf-8 -*-
"""Carte des loyers (ANIL, DGALN) : loyer d'annonce prédit au m2, charges comprises, des appartements et des maisons par commune."""
import time, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

BASE = 'https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/'
FICHIERS = {'appartements': BASE + '20251211-145010/pred-app-mef-dhup.csv',
            'app_t1t2': BASE + '20251211-144934/pred-app12-mef-dhup.csv',
            'app_t3plus': BASE + '20251211-144951/pred-app3-mef-dhup.csv',
            'maisons': BASE + '20251211-145039/pred-mai-mef-dhup.csv'}
GUIDE = BASE + '20251211-145105/guide-dutilisation-des-donnees.pdf'
AN = '2025'

SOURCE = {'ref': 'B2-loyers',
          'nom': "Carte des loyers - indicateurs de loyers d'annonce par commune en 2025",
          'producteur': 'ANIL et DGALN (annonces leboncoin et SeLoger)',
          'url': 'https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025',
          'telechargement': ' ; '.join(FICHIERS.values()),
          'millesime': '2025 (biens types mis en location au 3e trimestre 2025, annonces 2019 à 2025, communes au 1er janvier 2025)',
          'licence': 'Licence ouverte 2.0'}

LIB = {'appartements': ('des appartements', 'un appartement type de 52 m2 (toutes tailles)'),
       'app_t1t2': ('des appartements de 1 ou 2 pièces', 'un appartement type de 1 ou 2 pièces de 37 m2'),
       'app_t3plus': ('des appartements de 3 pièces ou plus', 'un appartement type de 3 pièces ou plus de 72 m2'),
       'maisons': ('des maisons', 'une maison type de 92 m2')}


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


def _wmean(v, w):
    """Moyenne pondérée par le nombre d'annonces ; moyenne simple si aucune annonce."""
    ok = v.notna()
    if not ok.any():
        return np.nan
    v, w = v[ok], w[ok]
    return float((v * w).sum() / w.sum()) if w.sum() > 0 else float(v.mean())


def charger(cache: Path) -> list:
    d = cache / 'loyers'
    _dl(GUIDE, d / 'guide-dutilisation-des-donnees.pdf')
    p = 'loyers_'
    blocs, inds = [], []
    for k, url in FICHIERS.items():
        x = pd.read_csv(_dl(url, d / url.rsplit('/', 1)[1]), sep=';', dtype=str, encoding='cp1252')
        for c in ['loypredm2', 'lwr.IPm2', 'upr.IPm2', 'nbobs_com']:
            x[c] = pd.to_numeric(x[c].str.replace(',', '.', regex=False), errors='coerce')
        x['CODGEO'] = geo.vers_cog2026(x.INSEE_C).values
        x = x.dropna(subset=['CODGEO'])
        x['nbobs_com'] = x['nbobs_com'].fillna(0)
        cols = {'loypredm2': f'{p}m2_{k}_{AN}', 'nbobs_com': f'{p}annonces_{k}_{AN}'}
        if k in ('appartements', 'maisons'):
            cols.update({'lwr.IPm2': f'{p}m2_{k}_bas_{AN}', 'upr.IPm2': f'{p}m2_{k}_haut_{AN}', 'TYPPRED': f'{p}niveau_prediction_{k}_{AN}'})
        multi = x.CODGEO.duplicated(keep=False)
        simple = x.loc[~multi, ['CODGEO'] + list(cols)].rename(columns=cols)
        lignes = []
        for code, g in x[multi].groupby('CODGEO'):   # arrondissements de Paris, Lyon, Marseille et communes fusionnées
            r = {'CODGEO': code, cols['nbobs_com']: g.nbobs_com.sum(), cols['loypredm2']: _wmean(g.loypredm2, g.nbobs_com)}
            if 'lwr.IPm2' in cols:
                r[cols['lwr.IPm2']] = _wmean(g['lwr.IPm2'], g.nbobs_com)
                r[cols['upr.IPm2']] = _wmean(g['upr.IPm2'], g.nbobs_com)
                r[cols['TYPPRED']] = g.sort_values('nbobs_com').TYPPRED.iloc[-1]
            lignes.append(r)
        blocs.append(pd.concat([simple, pd.DataFrame(lignes)], ignore_index=True).set_index('CODGEO'))
        lib, bien = LIB[k]
        inds += [
            {'col': cols['loypredm2'], 'libelle': f"Loyer d'annonce au m2 {lib} en {AN}", 'unite': 'euros par m2 et par mois',
             'definition': f"Loyer mensuel prédit, charges comprises, pour {bien}, non meublé, mis en location au 3e trimestre {AN}, estimé à partir des annonces leboncoin et SeLoger (modèle hédonique de l'ANIL). Pour Paris, Lyon et Marseille et les communes fusionnées, moyenne des valeurs publiées pondérée par le nombre d'annonces.",
             'agregation': 'non_additif', 'poids': cols['nbobs_com'], 'annee': AN},
            {'col': cols['nbobs_com'], 'libelle': f"Annonces observées {lib} ({AN})", 'unite': 'annonces',
             'definition': f"Nombre d'annonces de location {lib} observées dans la commune et utilisées pour estimer l'indicateur de loyer (carte des loyers {AN}). En dessous de 30, l'indicateur est peu fiable.",
             'agregation': 'somme', 'annee': AN},
        ]
        if 'lwr.IPm2' in cols:
            inds += [
                {'col': cols['lwr.IPm2'], 'libelle': f"Borne basse du loyer d'annonce au m2 {lib} en {AN}", 'unite': 'euros par m2 et par mois',
                 'definition': f"Borne inférieure de l'intervalle de prédiction à 95 % du loyer d'annonce au m2 {lib}.", 'agregation': 'non_additif', 'annee': AN},
                {'col': cols['upr.IPm2'], 'libelle': f"Borne haute du loyer d'annonce au m2 {lib} en {AN}", 'unite': 'euros par m2 et par mois',
                 'definition': f"Borne supérieure de l'intervalle de prédiction à 95 % du loyer d'annonce au m2 {lib}.", 'agregation': 'non_additif', 'annee': AN},
                {'col': cols['TYPPRED'], 'libelle': f"Niveau géographique de l'estimation du loyer {lib} ({AN})", 'unite': '',
                 'definition': "commune : estimation propre à la commune (au moins 100 annonces) ; epci : estimation faite sur l'intercommunalité ; maille : estimation faite sur un regroupement de communes voisines semblables (moins de 100 annonces).",
                 'agregation': 'texte'},
            ]
    df = pd.concat(blocs, axis=1).reset_index()
    for i in inds:
        if i['agregation'] != 'texte':
            df[i['col']] = df[i['col']].astype('float64')
            if i['agregation'] == 'non_additif':
                df[i['col']] = df[i['col']].round(2)
    df = df[['CODGEO'] + [i['col'] for i in inds]]
    return [{'theme': 'marche', 'data': df, 'indicateurs': inds}]
