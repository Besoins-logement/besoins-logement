# -*- coding: utf-8 -*-
"""Accès générique aux jeux de données Insee Melodi (catalogue, téléchargement Parquet ou CSV, lecture filtrée)."""
import json, time, urllib.request, zipfile, io
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.compute as pc

API = 'https://api.insee.fr/melodi'

def _get(url, timeout=900, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1: raise
            time.sleep(5 * (k + 1))

def catalogue(ds):
    return json.loads(_get(f'{API}/catalog/{ds}', timeout=120))

def _urls(o, keys=('accessURL', 'accessURLParquet', 'downloadURL')):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in keys and isinstance(v, str): out.append((k, v))
            out += _urls(v, keys)
    elif isinstance(o, list):
        for v in o: out += _urls(v, keys)
    return out

def telecharger(ds, cache):
    """Renvoie (chemin local, format, métadonnées du catalogue). Préférence au Parquet."""
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    cat = catalogue(ds)
    urls = _urls(cat)
    pq_url = next((u for k, u in urls if k == 'accessURLParquet'), None)
    csv_url = next((u for k, u in urls if k == 'accessURL' and u.endswith('_CSV_FR')), None)
    if pq_url:
        dst = cache / f'{ds}.parquet'
        if not dst.exists():
            dst.write_bytes(_get(pq_url))
        return dst, 'parquet', cat
    dst = cache / f'{ds}_CSV_FR.zip'
    if not dst.exists():
        dst.write_bytes(_get(csv_url))
    return dst, 'csv', cat

def lire(ds, cache, geo_objects=('COM',), colonnes=None):
    """Lit les observations du jeu pour les niveaux géographiques demandés (codes Melodi : COM, EPCI, DEP, REG, ZE2020, FRANCE...)."""
    path, fmt, cat = telecharger(ds, cache)
    if fmt == 'parquet':
        t = pq.read_table(path)
        if 'GEO_OBJECT' in t.column_names:
            t = t.filter(pc.is_in(pc.cast(t['GEO_OBJECT'], 'string'), value_set=__import__('pyarrow').array(list(geo_objects))))
        df = t.to_pandas()
        for c in df.columns:
            if str(df[c].dtype) == 'category': df[c] = df[c].astype(str)
        meta = None
    else:
        with zipfile.ZipFile(path) as zf:
            dn = [n for n in zf.namelist() if n.endswith('_data.csv')][0]
            mn = [n for n in zf.namelist() if n.endswith('_metadata.csv')]
            parts = []
            for ch in pd.read_csv(zf.open(dn), sep=';', dtype=str, chunksize=500_000):
                parts.append(ch[ch.GEO_OBJECT.isin(geo_objects)])
            df = pd.concat(parts)
            df['OBS_VALUE'] = pd.to_numeric(df.OBS_VALUE.str.replace(',', '.'), errors='coerce')
            meta = pd.read_csv(zf.open(mn[0]), sep=';', dtype=str) if mn else None
    return df, meta, cat

def libelles(ds, cache):
    """Libellés des modalités (COD_VAR, COD_MOD -> LIB_MOD) depuis le zip CSV (téléchargé si besoin, petit fichier de métadonnées)."""
    cache = Path(cache)
    cat = catalogue(ds)
    csv_url = next((u for k, u in _urls(cat) if k == 'accessURL' and u.endswith('_CSV_FR')), None)
    dst = cache / f'{ds}_CSV_FR.zip'
    if not dst.exists():
        dst.write_bytes(_get(csv_url))
    with zipfile.ZipFile(dst) as zf:
        mn = [n for n in zf.namelist() if n.endswith('_metadata.csv')][0]
        return pd.read_csv(zf.open(mn), sep=';', dtype=str)
