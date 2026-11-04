# -*- coding: utf-8 -*-
"""Taux de couverture de l'accueil du jeune enfant (Cnaf) : places d'accueil formel pour 100 enfants de moins de 3 ans, communes de plus de 10 000 habitants, EPCI, départements, régions et France."""
import time, shutil, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

AN = '2023'
ODS = 'https://data.caf.fr/api/explore/v2.1/catalog/datasets/{}/exports/csv?delimiter=%3B'
JEUX = {'COM': 'txcouv_pe_com', 'EPCI': 'txcouv_pe_epci', 'DEP': 'txcouv_pe_dep', 'REG': 'txcouv_pe_reg', 'FRANCE': 'txcouv_pe_nat'}
CODES = {'COM': 'numcom', 'EPCI': 'numepci', 'DEP': 'numdep', 'REG': 'numregi', 'FRANCE': None}
SUFFIXES = {'COM': 'com', 'EPCI': 'epci', 'DEP': 'dep', 'REG': 'reg', 'FRANCE': 'nat'}
# variable de la source -> (nom de colonne, libellé, précision)
TAUX = [('txcouv', 'aje_txcouv_global', "Taux de couverture global de l'accueil du jeune enfant",
         "toutes les places d'accueil formel : établissements d'accueil du jeune enfant, école dès 2 ans, assistants maternels et salariés à domicile"),
        ('txcouv_eaje', 'aje_txcouv_eaje', "Taux de couverture par les établissements d'accueil du jeune enfant",
         "places en établissements d'accueil du jeune enfant (crèches, multi-accueils, micro-crèches)"),
        ('txcouv_ind', 'aje_txcouv_individuel', "Taux de couverture par l'accueil individuel",
         "places chez les assistants maternels et emplois de salariés à domicile"),
        ('txcouv_am_ind', 'aje_txcouv_assmat', "Taux de couverture par les assistants maternels",
         "places chez les assistants maternels"),
        ('txcouv_gad_ind', 'aje_txcouv_domicile', "Taux de couverture par la garde à domicile",
         "enfants gardés par un salarié à domicile"),
        ('txcouv_prescol', 'aje_txcouv_prescol', "Taux de couverture par la scolarisation à 2 ans",
         "enfants de 2 ans scolarisés à l'école maternelle")]

SOURCE = {'ref': 'E7-18',
          'nom': "Taux de couverture d'accueil du jeune enfant (communes de plus de 10 000 habitants, EPCI, départements, régions, France)",
          'producteur': 'Caisse nationale des allocations familiales (Cnaf), Observatoire national de la petite enfance',
          'url': 'https://www.data.gouv.fr/datasets/taux-de-couverture-daccueil-du-jeune-enfant-communal',
          'telechargement': ' ; '.join(ODS.format(j) for j in JEUX.values()),
          'millesime': f'{AN} (offre théorique en décembre {AN})',
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=10):
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


def _lire(cache, niv):
    d = pd.read_csv(_telecharger(ODS.format(JEUX[niv]), Path(cache) / 'accueil_enfant' / f'{JEUX[niv]}.csv'),
                    sep=';', dtype=str, encoding='utf-8-sig')
    d = d[d.annee == AN].copy()
    suf = SUFFIXES[niv]
    res = pd.DataFrame({'CODE': d[CODES[niv]].values if CODES[niv] else 'FR'}, index=d.index)
    for var, col, _, _ in TAUX:
        res[f'{col}_{AN}'] = pd.to_numeric(d[f'{var}_{suf}'].str.replace(',', '.', regex=False), errors='coerce')
    return res.reset_index(drop=True)


def charger(cache: Path) -> list:
    com = _lire(cache, 'COM')
    com['CODGEO'] = geo.vers_cog2026(com.CODE).values
    com = com.dropna(subset=['CODGEO'])               # Saint-Barthélemy et Saint-Martin
    # taux sans effectifs : on ne garde que les communes 2026 issues d'une seule commune publiée
    # (Paris, Lyon et Marseille ne sont publiées que par arrondissement et restent vides)
    n = com.CODGEO.map(com.CODGEO.value_counts())
    out = com[n == 1].drop(columns='CODE').reset_index(drop=True)
    out['CODGEO'] = out.CODGEO.astype(str)
    cols = [c for c in out.columns if c != 'CODGEO']
    out = out[['CODGEO'] + cols]

    ref = geo.referentiel()
    publies = {}
    for niv, valides in (('EPCI', set(ref.EPCI.dropna())), ('DEP', set(ref.DEP.dropna())), ('REG', set(ref.REG.dropna())), ('FRANCE', {'FR'})):
        p = _lire(cache, niv)
        if niv in ('DEP', 'REG'):
            p['CODE'] = p.CODE.str.zfill(2)
        publies[niv] = p[p.CODE.isin(valides)].drop_duplicates('CODE').reset_index(drop=True)

    base = (f" Nombre de places offertes pour 100 enfants de moins de 3 ans, offre théorique en décembre {AN}"
            " (une place peut être vacante ou partagée entre plusieurs enfants). Publié pour les communes de plus de 10 000 habitants ;"
            " valeurs publiées par la Cnaf pour les EPCI (périmètres 2023 encore valides en 2026), départements, régions et France ;"
            " pas de moyenne recalculée faute d'effectifs.")
    ind = [{'col': f'{col}_{AN}', 'libelle': f'{lib} en {AN}', 'unite': 'places pour 100 enfants de moins de 3 ans',
            'definition': f"Capacité d'accueil : {prec}." + base, 'agregation': 'non_additif', 'annee': AN}
           for _, col, lib, prec in TAUX]
    return [{'theme': 'equipements', 'data': out, 'indicateurs': ind, 'publies': publies}]
