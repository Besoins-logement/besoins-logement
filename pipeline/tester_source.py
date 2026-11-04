# -*- coding: utf-8 -*-
"""Teste un module de pipeline/sources : python tester_source.py <nom_module>.
Vérifie le contrat (codes communes 2026, pas de doublon, colonnes numériques documentées) et enregistre la sortie dans cache/sorties."""
import sys, json, importlib, time
from pathlib import Path
import pandas as pd, numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo

THEMES = {'territoire', 'population', 'menages', 'profils', 'economie', 'logement', 'construction', 'besoins', 'marche', 'revenus', 'emploi', 'equipements', 'risques_energie'}
AGR = {'somme', 'ratio', 'non_additif', 'texte'}
nom = sys.argv[1]
t0 = time.time()
mod = importlib.import_module(f'sources.{nom}')
blocs = mod.charger(geo.CACHE)
actifs, _ = geo._passage()
out = geo.CACHE / 'sorties'; out.mkdir(exist_ok=True)
ok = True
for i, b in enumerate(blocs):
    df, inds = b['data'], b['indicateurs']
    assert b['theme'] in THEMES, f"thème inconnu {b['theme']}"
    assert 'CODGEO' in df.columns, 'colonne CODGEO absente'
    bad = (~df.CODGEO.isin(actifs)).sum(); dup = df.CODGEO.duplicated().sum()
    cols = [c for c in df.columns if c != 'CODGEO']
    doc = {d['col'] for d in inds}
    nodoc = [c for c in cols if c not in doc]; absent = [c for c in doc if c not in cols]
    for d in inds:
        assert d.get('agregation') in AGR, f"agrégation inconnue pour {d['col']}"
        if d['agregation'] == 'ratio': assert d.get('num') in cols and d.get('den') in cols, f"ratio mal défini {d['col']}"
        assert d['col'] in df.columns, f"colonne documentée absente {d['col']}"
        if d['agregation'] != 'texte': assert pd.api.types.is_numeric_dtype(df[d['col']]), f"colonne non numérique {d['col']}"
        if d.get('poids'): assert d['poids'] in df.columns, f"poids absent {d['poids']}"
    for niv, p in b.get('publies', {}).items():
        assert 'CODE' in p.columns, f'publies {niv} sans colonne CODE'
    print(f"bloc {i} thème={b['theme']} communes={len(df)} codes hors COG 2026={bad} doublons={dup} indicateurs={len(cols)} non documentés={nodoc[:5]} documentés absents={absent[:5]} publiés={list(b.get('publies', {}).keys())}")
    ok &= bad == 0 and dup == 0 and not nodoc and not absent
    df.to_parquet(out / f'{nom}_{i}.parquet', index=False)
    for niv, p in b.get('publies', {}).items():
        p.to_parquet(out / f'{nom}_{i}_publie_{niv}.parquet', index=False)
    with open(out / f'{nom}_{i}.json', 'w', encoding='utf-8') as fj:
        json.dump({'source': getattr(mod, 'SOURCE', {}), 'theme': b['theme'], 'indicateurs': inds}, fj, ensure_ascii=False, indent=1)
ok &= len(blocs) > 0
print('CONTRAT RESPECTÉ' if ok else 'CONTRAT NON RESPECTÉ', f'({time.time() - t0:.0f} s)')
