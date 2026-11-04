# -*- coding: utf-8 -*-
"""Zonage ABC des communes (tension du marché du logement), en texte et en colonnes 0/1 par zone."""
import shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

SOURCE = {'ref': 'P2-029',
          'nom': 'Liste des communes selon le zonage ABC',
          'producteur': 'Ministère chargé du logement (DGALN), publié par le ministère de la Transition écologique',
          'url': 'https://www.data.gouv.fr/datasets/liste-des-communes-selon-le-zonage-abc',
          'telechargement': 'https://static.data.gouv.fr/resources/liste-des-communes-selon-le-zonage-abc/20260703-091314/liste-ensemble-des-communes-zonage-abc-en-vigueur-26-juin-2026.csv',
          'millesime': 'Zonage en vigueur depuis le 26 juin 2026 (arrêté du 1er août 2014 modifié, en dernier lieu le 23 juin 2026), géographie communale 2026',
          'licence': 'Licence ouverte 2.0'}

ZONES = [('Abis', 'A bis', 'abc_abis_2026'), ('A', 'A', 'abc_a_2026'), ('B1', 'B1', 'abc_b1_2026'),
         ('B2', 'B2', 'abc_b2_2026'), ('C', 'C', 'abc_c_2026')]
ORDRE = {lib: i for i, (_, lib, _) in enumerate(ZONES)}   # de la plus tendue (A bis) à la moins tendue (C)


def _telecharger(url, dest, essais=30):
    """Télécharge url dans dest une seule fois, avec reprises (le réseau vers data.gouv.fr coupe souvent)."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    err = None
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (besoins-logement)'})
            with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            part.replace(dest)
            return dest
        except Exception as e:
            err = e
            time.sleep(min(2 + k, 10))
    raise RuntimeError(f'téléchargement impossible : {url} ({err})')


def charger(cache: Path) -> list:
    p = _telecharger(SOURCE['telechargement'], Path(cache) / 'zonage_abc' / SOURCE['telechargement'].rsplit('/', 1)[1])
    brut = pd.read_csv(p, sep=';', dtype=str, encoding='utf-8')
    col_zone = [c for c in brut.columns if c.lower().startswith('zonage abc')][0]
    brut['zone'] = brut[col_zone].str.strip().map({code: lib for code, lib, _ in ZONES})
    if brut.zone.isna().any():
        raise ValueError(f"valeurs de zone inattendues : {brut.loc[brut.zone.isna(), col_zone].unique()[:5]}")
    brut['CODGEO'] = geo.vers_cog2026(brut.CODGEO).values
    brut = brut.dropna(subset=['CODGEO'])
    # Le fichier est déjà en géographie 2026 (une ligne par commune). Si une commune 2026 regroupait
    # plusieurs anciennes communes de zones différentes, on garderait la zone la plus tendue (cas absent ici).
    brut['rang'] = brut.zone.map(ORDRE)
    df = brut.sort_values('rang').drop_duplicates('CODGEO')[['CODGEO', 'zone']].rename(columns={'zone': 'abc_zone_2026'})
    for _, lib, col in ZONES:
        df[col] = (df.abc_zone_2026 == lib).astype('int64')
    df = df.sort_values('CODGEO').reset_index(drop=True)

    texte_zone = ("Le zonage ABC classe les communes selon la tension du marché du logement, de la plus tendue "
                  "(A bis) à la moins tendue (C). Il sert notamment au prêt à taux zéro, aux aides à l'investissement "
                  "locatif, au logement locatif intermédiaire et aux plafonds de loyer de certains dispositifs. "
                  "Zonage en vigueur depuis le 26 juin 2026 (arrêté du 1er août 2014 modifié).")
    inds = [{'col': 'abc_zone_2026', 'libelle': 'Zone ABC (zonage en vigueur au 26 juin 2026)', 'unite': '',
             'definition': "Zone de la commune dans le zonage ABC : A bis, A, B1, B2 ou C. " + texte_zone,
             'agregation': 'texte', 'annee': '2026'}]
    for _, lib, col in ZONES:
        inds.append({'col': col, 'libelle': f'Commune en zone {lib} du zonage ABC (2026)', 'unite': 'communes',
                     'definition': (f"Vaut 1 si la commune est classée en zone {lib} du zonage ABC, 0 sinon. "
                                    f"Additionnée sur un territoire, donne le nombre de communes en zone {lib}. ") + texte_zone,
                     'agregation': 'somme', 'annee': '2026'})
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
