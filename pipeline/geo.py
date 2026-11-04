# -*- coding: utf-8 -*-
"""Géographie commune de la base : communes au 1er janvier 2026 (COG), passage des anciens codes, appartenances.
Sources : Insee (COG 2026, zones d'emploi 2020, EPCI), ANCT (territoires d'industrie)."""
import io, zipfile, urllib.request, functools
from pathlib import Path
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
CACHE = RACINE / 'cache'
COG = 'https://www.insee.fr/fr/statistiques/fichier/8740222/{}'
FICHIERS = {
    'insee/v_commune_2026.csv': COG.format('v_commune_2026.csv'),
    'insee/v_mvt_commune_2026.csv': COG.format('v_mvt_commune_2026.csv'),
    'insee/v_departement_2026.csv': COG.format('v_departement_2026.csv'),
    'insee/v_region_2026.csv': COG.format('v_region_2026.csv'),
    'insee/ZE2020_au_01-01-2026.zip': 'https://www.insee.fr/fr/statistiques/fichier/4652957/ZE2020_au_01-01-2026.zip',
    'insee/EPCI_au_01-01-2026.zip': 'https://www.insee.fr/fr/statistiques/fichier/2510634/EPCI_au_01-01-2026.zip',
    # ANCT, programme Territoires d'industrie 2023-2027, « Liste des communes couvertes 2023-2027 (COG 2026) »
    # (https://www.data.gouv.fr/datasets/programme-territoires-dindustrie, ressource mise à jour le 21 août 2026)
    'anct/ti_2023_2027_communes_cog.csv': 'https://static.data.gouv.fr/resources/programme-territoires-dindustrie/20260821-093025/liste-ti-com2025-20260206.csv',
}

def fichier(rel):
    """Télécharge une fois (fichier temporaire puis renommage, plusieurs essais) et renvoie le chemin local."""
    import time
    p = CACHE / rel
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + '.part')
        for k in range(6):
            try:
                with urllib.request.urlopen(FICHIERS[rel], timeout=600) as r:
                    tmp.write_bytes(r.read())
                tmp.replace(p)
                break
            except Exception:
                if k == 5: raise
                time.sleep(10 * (k + 1))
    return p

def _xlsx_zip(z, feuille):
    with zipfile.ZipFile(z) as zf:
        n = [i for i in zf.namelist() if i.lower().endswith('.xlsx')][0]
        return pd.read_excel(io.BytesIO(zf.read(n)), sheet_name=feuille, header=5, dtype=str, engine='calamine')

@functools.lru_cache(maxsize=1)
def _passage():
    cog = pd.read_csv(fichier('insee/v_commune_2026.csv'), dtype=str)
    mvt = pd.read_csv(fichier('insee/v_mvt_commune_2026.csv'), dtype=str)
    actifs = frozenset(cog.loc[cog.TYPECOM == 'COM', 'COM'])
    mp = dict(cog.loc[cog.TYPECOM.isin(['ARM', 'COMD', 'COMA']) & cog.COMPARENT.notna(), ['COM', 'COMPARENT']].values)
    for a, b in mvt[(mvt.DATE_EFF >= '1990-01-01') & (mvt.TYPECOM_AP == 'COM') & (mvt.COM_AV != mvt.COM_AP)][['COM_AV', 'COM_AP']].values:
        if a not in actifs and a not in mp:
            mp[a] = b
    return actifs, mp

def vers_cog2026(codes):
    """Convertit des codes communes (anciens, arrondissements de Paris, Lyon, Marseille, communes déléguées) en codes COG 2026.
    Attention : une source qui donne à la fois la ville entière et ses arrondissements doit écarter les arrondissements avant, sinon double compte.
    Renvoie une Series de même index ; NaN si le code est inconnu."""
    actifs, mp = _passage()
    def f(c):
        if c is None or (isinstance(c, float) and c != c): return None
        if isinstance(c, float) and c.is_integer(): c = str(int(c))
        c = str(c).strip()
        c = c.zfill(5) if c.isdigit() else c
        n = 0
        while c not in actifs and c in mp and n < 10:
            c = mp[c]; n += 1
        return c if c in actifs else None
    s = pd.Series(codes)
    u = {c: f(c) for c in s.dropna().unique()}
    return s.map(u)

@functools.lru_cache(maxsize=1)
def referentiel():
    """Une ligne par commune 2026 : CODGEO, LIBGEO, DEP, REG, ZE2020, LIBZE2020, EPCI, LIBEPCI, id_ti, lib_ti."""
    ze = _xlsx_zip(fichier('insee/ZE2020_au_01-01-2026.zip'), 'Composition_communale')[['CODGEO', 'LIBGEO', 'ZE2020', 'LIBZE2020', 'DEP', 'REG']]
    ep = _xlsx_zip(fichier('insee/EPCI_au_01-01-2026.zip'), 'Composition_communale')[['CODGEO', 'EPCI', 'LIBEPCI']]
    ref = ze.merge(ep, on='CODGEO', how='left')
    # Territoires d'industrie : fichier téléchargé comme les autres (il n'était lu que s'il se trouvait déjà dans le cache,
    # ce qui faisait échouer l'assemblage sur une machine neuve).
    ti = pd.read_csv(fichier('anct/ti_2023_2027_communes_cog.csv'), dtype=str)
    ti['CODGEO'] = vers_cog2026(ti.insee_com).values
    ti = ti.dropna(subset=['CODGEO']).drop_duplicates('CODGEO')[['CODGEO', 'id_ti', 'lib_ti']]
    ref = ref.merge(ti, on='CODGEO', how='left')
    return ref

def libelles_niveaux():
    reg = pd.read_csv(fichier('insee/v_region_2026.csv'), dtype=str).set_index('REG').LIBELLE
    dep = pd.read_csv(fichier('insee/v_departement_2026.csv'), dtype=str).set_index('DEP').LIBELLE
    return reg, dep
