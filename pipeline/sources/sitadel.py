# -*- coding: utf-8 -*-
"""Construction neuve (Sitadel, SDES) : logements autorisés et commencés par commune et par année, par type,
et construction actuelle (moyenne 2023-2025 du département, série estimée, répartie selon les communes en 2021-2023)."""
import gzip, shutil, time, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
import geo

DIDO = 'https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/{}/csv?millesime=2026-10&withColumnName=true&withColumnDescription=false&withColumnUnit=false&ANNEE=gte:2012'
COMM_ID, DEP_ID = '9c90a880-4ba0-49b4-b99d-d7dd6c810dd0', 'd264957b-c6d2-4efa-bf5e-6a8da836550a'
SOURCE = {'ref': 'B1-02', 'nom': 'Sit@del2 - logements autorisés et commencés (séries annuelles communales en date réelle ; séries mensuelles départementales estimées)',
          'producteur': 'SDES', 'url': 'https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datasets/6513ee3a3b05e5cd969c270f',
          'telechargement': DIDO.format(COMM_ID), 'millesime': 'Millésime 2026-10', 'licence': 'Licence ouverte 2.0'}
TYPES = {'Individuel pur': 'indiv_pur', 'Individuel groupe': 'indiv_groupe', 'Collectif': 'collectif', 'Residence': 'residence'}

def _get(url, dst, gz=False):
    dst = Path(dst)
    if dst.exists(): return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + '.part')
    for k in range(5):
        try:
            with urllib.request.urlopen(url, timeout=900) as r, (gzip.open(tmp, 'wb') if gz else open(tmp, 'wb')) as f:
                shutil.copyfileobj(r, f)
            tmp.replace(dst); return dst
        except Exception:
            time.sleep(10 * (k + 1))
    raise RuntimeError(f'téléchargement impossible : {url}')

def charger(cache):
    c = Path(cache) / 'sitadel'
    fc = _get(DIDO.format(COMM_ID), c / 'sitadel_communes_annuel_2012_2025.csv.gz', gz=True)
    fd = _get(DIDO.format(DEP_ID), c / 'sitadel_dep_mensuel_estime.csv')
    s = pd.read_csv(fc, sep=';', dtype={'COMM': str, 'ANNEE': int})
    s['CODGEO'] = geo.vers_cog2026(s.COMM).values
    s = s.dropna(subset=['CODGEO'])
    g = s.groupby(['CODGEO', 'ANNEE', 'TYPE_LGT'])[['LOG_AUT', 'LOG_COM']].sum(min_count=1).reset_index()
    last_com = int(g.loc[g.LOG_COM.notna() & (g.LOG_COM > 0), 'ANNEE'].max())
    last_aut = int(g.loc[g.LOG_AUT.notna() & (g.LOG_AUT > 0), 'ANNEE'].max())
    ref = geo.referentiel()[['CODGEO', 'DEP']]
    out = ref[['CODGEO']].copy()
    inds = []
    def add(col, ser, lib, defi, annee, agr='somme', **kw):
        out[col] = out.CODGEO.map(ser)
        d = {'col': col, 'libelle': lib, 'unite': 'logements', 'definition': defi + ' Source : SDES, Sitadel, données brutes en date réelle.', 'agregation': agr, 'annee': annee}
        d.update(kw); inds.append(d)
    tous = g[g.TYPE_LGT == 'Tous Logements'].set_index(['ANNEE', 'CODGEO'])
    for a in range(2012, last_com + 1):
        add(f'sit_commences_{a}', tous.loc[a].LOG_COM if a in tous.index.levels[0] else pd.Series(dtype=float), f'Logements commencés en {a}', f'Logements mis en chantier en {a}, tous types.', str(a))
    for a in range(2012, last_aut + 1):
        add(f'sit_autorises_{a}', tous.loc[a].LOG_AUT if a in tous.index.levels[0] else pd.Series(dtype=float), f'Logements autorisés en {a}', f'Logements autorisés (permis délivrés) en {a}, tous types.', str(a))
    for t, k in TYPES.items():
        sub = g[g.TYPE_LGT == t].set_index(['ANNEE', 'CODGEO'])
        for a in range(last_com - 3, last_com + 1):
            add(f'sit_commences_{k}_{a}', sub.loc[a].LOG_COM if a in sub.index.levels[0] else pd.Series(dtype=float), f'Logements commencés en {a}, {t.lower()}', f'Logements mis en chantier en {a}, type {t.lower()}.', str(a))
        for a in range(last_aut - 2, last_aut + 1):
            add(f'sit_autorises_{k}_{a}', sub.loc[a].LOG_AUT if a in sub.index.levels[0] else pd.Series(dtype=float), f'Logements autorisés en {a}, {t.lower()}', f'Logements autorisés en {a}, type {t.lower()}.', str(a))
    y3 = list(range(last_aut - 2, last_aut + 1))
    out['sit_autorises_3ans'] = out[[f'sit_autorises_{a}' for a in y3]].sum(axis=1, min_count=1)
    out['sit_autorises_maisons_3ans'] = out[[f'sit_autorises_{k}_{a}' for k in ('indiv_pur', 'indiv_groupe') for a in y3]].sum(axis=1, min_count=1)
    inds += [{'col': 'sit_autorises_3ans', 'libelle': f'Logements autorisés {y3[0]}-{y3[-1]}', 'unite': 'logements', 'definition': f'Total des logements autorisés sur {y3[0]}-{y3[-1]}.', 'agregation': 'somme', 'annee': f'{y3[0]}-{y3[-1]}'},
             {'col': 'sit_autorises_maisons_3ans', 'libelle': f'Maisons autorisées {y3[0]}-{y3[-1]}', 'unite': 'logements', 'definition': f'Logements individuels (purs et groupés) autorisés sur {y3[0]}-{y3[-1]}.', 'agregation': 'somme', 'annee': f'{y3[0]}-{y3[-1]}'},
             {'col': 'sit_part_maisons_autorises', 'libelle': f'Part des maisons dans les logements autorisés {y3[0]}-{y3[-1]}', 'unite': '%', 'definition': 'Maisons autorisées / logements autorisés, sur trois ans (indicateur PRO2).', 'agregation': 'ratio', 'num': 'sit_autorises_maisons_3ans', 'den': 'sit_autorises_3ans', 'facteur': 100, 'annee': f'{y3[0]}-{y3[-1]}'}]
    out['sit_part_maisons_autorises'] = 100 * out.sit_autorises_maisons_3ans / out.sit_autorises_3ans
    # construction actuelle
    w = out[['sit_commences_2021', 'sit_commences_2022', 'sit_commences_2023']].sum(axis=1, min_count=1) / 3
    d = pd.read_csv(fd, sep=';', dtype={'DEPARTEMENT_CODE': str})
    d = d[d.TYPE_LGT == 'Tous Logements']
    est = d[d.ANNEE.between(2023, 2025)].groupby('DEPARTEMENT_CODE').LOG_COM.sum() / 3
    dep = out.CODGEO.map(ref.set_index('CODGEO').DEP)
    sw = w.groupby(dep).transform('sum')
    act = w * dep.map(est) / sw
    sans = dep.map(est).isna() | (sw == 0)
    act[sans] = w[sans]
    out['sit_commences_moy_2021_2023'] = w
    out['sit_construction_actuelle'] = act
    inds += [{'col': 'sit_commences_moy_2021_2023', 'libelle': 'Logements commencés par an, moyenne 2021-2023', 'unite': 'logements par an', 'definition': 'Moyenne annuelle des mises en chantier 2021-2023, données communales brutes.', 'agregation': 'somme', 'annee': '2021-2023'},
             {'col': 'sit_construction_actuelle', 'libelle': 'Construction actuelle (mises en chantier par an, 2023-2025)', 'unite': 'logements par an',
              'definition': "Moyenne 2023-2025 des mises en chantier du département (série estimée du SDES), répartie entre les communes selon leurs mises en chantier 2021-2023. Mayotte : données communales 2021-2023.", 'agregation': 'somme', 'annee': '2023-2025'}]
    return [{'theme': 'construction', 'data': out, 'indicateurs': inds}]
