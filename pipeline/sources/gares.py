# -*- coding: utf-8 -*-
"""Gares de voyageurs par commune (SNCF Gares & Connexions) : nombre de gares ouvertes aux voyageurs et fréquentation annuelle en 2019 et 2024."""
import time, shutil, unicodedata, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

ODS = 'https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/{}/exports/csv?delimiter=%3B'
URL_GARES = ODS.format('gares-de-voyageurs')
URL_FREQ = ODS.format('frequentation-gares')
AN_REF = '2026'          # référentiel des gares mis à jour en novembre 2026

SOURCE = {'ref': 'E7-23, E7-22',
          'nom': 'Gares de voyageurs (référentiel SNCF) et fréquentation en gares',
          'producteur': 'SNCF Gares & Connexions',
          'url': 'https://ressources.data.sncf.com/explore/dataset/gares-de-voyageurs/ ; https://ressources.data.sncf.com/explore/dataset/frequentation-gares/',
          'telechargement': f'{URL_GARES} ; {URL_FREQ}',
          'millesime': 'référentiel des gares au 1er novembre 2026 ; fréquentation 2019 et 2024',
          'licence': 'Licence ouverte 2.0 (Open Licence Etalab)'}


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


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    for a, b in (("'", ' '), ('’', ' '), ('-', ' '), ('saint ', 'st '), ('sainte ', 'ste ')):
        s = s.replace(a, b)
    return ' '.join(s.split())


def charger(cache: Path) -> list:
    rep = Path(cache) / 'gares'
    g = pd.read_csv(_telecharger(URL_GARES, rep / 'gares-de-voyageurs.csv'), sep=';', dtype=str, encoding='utf-8-sig')
    f = pd.read_csv(_telecharger(URL_FREQ, rep / 'frequentation-gares.csv'), sep=';', dtype=str, encoding='utf-8-sig')

    # 1. nombre de gares par commune et par segment (A : intérêt national, B : régional, C : local) ; segment multiple : le plus élevé
    g['CODGEO'] = geo.vers_cog2026(g.codeinsee).values
    g = g.dropna(subset=['CODGEO'])
    seg = g.segment_drg.fillna('').map(lambda s: min([x for x in s.split(';') if x in 'ABC' and x] or ['C']))
    out = pd.DataFrame({'gares_nb': g.groupby('CODGEO').size()})
    for x in 'ABC':
        out[f'gares_nb_segment_{x.lower()}'] = (seg == x).groupby(g.CODGEO).sum()
    out.columns = [f'{c}_{AN_REF}' for c in out.columns]

    # 2. fréquentation : rattachement par code UIC au référentiel ; à défaut, par le nom de la gare et le département du code postal
    uic = g.assign(uic=g.codes_uic.str.split(';')).explode('uic').drop_duplicates('uic').set_index('uic').CODGEO
    f['CODGEO'] = f.code_uic_complet.map(uic)
    cog = pd.read_csv(geo.fichier('insee/v_commune_2026.csv'), dtype=str)
    cog = cog[cog.TYPECOM == 'COM'].assign(cle=lambda x: x.DEP + '|' + x.LIBELLE.map(_norm))
    cog = cog.drop_duplicates('cle', keep=False).set_index('cle').COM
    cp = f.code_postal.fillna('').str.zfill(5)
    dep = np.where(cp.str.startswith('97'), cp.str[:3], np.where(cp.str.startswith('20'),
                   np.where(cp.str[:3].isin(['200', '201']), '2A', '2B'), cp.str[:2]))
    dep = pd.Series(dep, index=f.index)
    noms = f.nom_gare.map(_norm).str.split()
    for n in range(8, 0, -1):          # nom complet de la gare, puis ses premiers mots (« Marle sur Serre » -> Marle)
        cle = dep + '|' + noms.map(lambda t: ' '.join(t[:n]) if len(t) >= n else None)
        f['CODGEO'] = f.CODGEO.fillna(cle.map(cog))
    f = f.dropna(subset=['CODGEO'])
    f['CODGEO'] = geo.vers_cog2026(f.CODGEO).values
    f = f.dropna(subset=['CODGEO'])
    for a in ('2019', '2024'):
        f[a] = pd.to_numeric(f[f'total_voyageurs_{a}'], errors='coerce')
    v = f.groupby('CODGEO')[['2019', '2024']].sum(min_count=1)
    v.columns = ['gares_voyageurs_2019', 'gares_voyageurs_2024']
    out = out.join(v, how='outer')
    for c in [c for c in out.columns if c.startswith('gares_nb')]:
        out[c] = out[c].fillna(0)        # commune où une gare a encore de la fréquentation mais ne figure plus au référentiel
    out = out.reset_index().rename(columns={'index': 'CODGEO'})
    out['CODGEO'] = out.CODGEO.astype(str)

    ref = f" Gares du référentiel SNCF des gares de voyageurs (version de novembre {AN_REF}), localisées par leur code commune."
    freq = (" Nombre de voyageurs (montées et descentes) estimé par SNCF Gares & Connexions à partir des ventes de billets et des comptages,"
            " hors personnes qui traversent la gare sans prendre le train. Gare rattachée à sa commune par son code UIC, ou à défaut par son nom"
            " (ou ses premiers mots) et son département ; la gare de Monaco est exclue.")
    ind = [
        {'col': f'gares_nb_{AN_REF}', 'libelle': f'Gares de voyageurs en {AN_REF}', 'unite': 'gares',
         'definition': "Nombre de gares et haltes ferroviaires ouvertes aux voyageurs dans la commune." + ref, 'agregation': 'somme', 'annee': AN_REF},
        {'col': f'gares_nb_segment_a_{AN_REF}', 'libelle': f"Gares de voyageurs d'intérêt national (segment A) en {AN_REF}", 'unite': 'gares',
         'definition': "Nombre de gares du segment A (gares d'intérêt national, au moins 250 000 voyageurs nationaux ou internationaux par an)." + ref,
         'agregation': 'somme', 'annee': AN_REF},
        {'col': f'gares_nb_segment_b_{AN_REF}', 'libelle': f"Gares de voyageurs d'intérêt régional (segment B) en {AN_REF}", 'unite': 'gares',
         'definition': "Nombre de gares du segment B (gares d'intérêt régional, au moins 100 000 voyageurs par an)." + ref,
         'agregation': 'somme', 'annee': AN_REF},
        {'col': f'gares_nb_segment_c_{AN_REF}', 'libelle': f"Gares de voyageurs d'intérêt local (segment C) en {AN_REF}", 'unite': 'gares',
         'definition': "Nombre de gares du segment C (gares et haltes d'intérêt local)." + ref, 'agregation': 'somme', 'annee': AN_REF},
        {'col': 'gares_voyageurs_2019', 'libelle': 'Voyageurs dans les gares en 2019', 'unite': 'voyageurs par an',
         'definition': "Nombre annuel de voyageurs des gares de la commune en 2019 (année de référence avant la crise sanitaire)." + freq,
         'agregation': 'somme', 'annee': '2019'},
        {'col': 'gares_voyageurs_2024', 'libelle': 'Voyageurs dans les gares en 2024', 'unite': 'voyageurs par an',
         'definition': "Nombre annuel de voyageurs des gares de la commune en 2024." + freq, 'agregation': 'somme', 'annee': '2024'},
    ]
    out = out[['CODGEO'] + [x['col'] for x in ind]]
    return [{'theme': 'equipements', 'data': out, 'indicateurs': ind}]
