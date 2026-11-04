# -*- coding: utf-8 -*-
"""Quartiers prioritaires de la politique de la ville (QPV, génération 2024) : nombre de quartiers par commune."""
import shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

SOURCE = {'ref': 'E7-35',
          'nom': 'Quartiers prioritaires de la politique de la ville 2024 (liste)',
          'producteur': 'Agence nationale de la cohésion des territoires (ANCT)',
          'url': 'https://www.data.gouv.fr/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-qpv',
          'telechargement': 'https://static.data.gouv.fr/resources/quartiers-prioritaires-de-la-politique-de-la-ville-qpv/20260721-095036/listeqp2024-cog2025.csv',
          'millesime': "Liste du 21 juillet 2026 (code géographique 2025) ; quartiers de 2024 pour l'hexagone (décret du 28 décembre 2023), 2025 pour l'outre-mer",
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=30):
    """Télécharge url dans dest une seule fois, avec reprises en cas de coupure réseau."""
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
    p = _telecharger(SOURCE['telechargement'], Path(cache) / 'qpv' / 'listeqp2024-cog2025.csv')
    brut = pd.read_csv(p, sep=';', dtype=str, encoding='utf-8-sig')
    # le code commune est écrit sous la forme ="01053" : on garde les 5 caractères du code
    brut['code'] = brut.insee_com.str.extract(r'([0-9AB]{5})', expand=False)
    if brut.code.isna().any() or brut.code_qp.duplicated().any():
        raise ValueError('liste des QPV : code commune illisible ou quartier en double')
    brut['CODGEO'] = geo.vers_cog2026(brut.code).values
    perdus = brut.CODGEO.isna().sum()
    if perdus:
        print(f'qpv : {perdus} quartiers sans commune 2026 écartés')
    n = brut.dropna(subset=['CODGEO']).groupby('CODGEO').code_qp.nunique().rename('qpv_nb_2024')

    df = geo.referentiel()[['CODGEO']].merge(n, left_on='CODGEO', right_index=True, how='left')
    df['qpv_nb_2024'] = df.qpv_nb_2024.fillna(0).astype('int64')
    df['qpv_presence_2024'] = (df.qpv_nb_2024 > 0).astype('int64')
    df = df.sort_values('CODGEO').reset_index(drop=True)

    base = ("Quartiers prioritaires de la politique de la ville de la génération 2024 (ceux d'outre-mer datent de 2025), d'après la liste "
            "officielle de l'ANCT du 21 juillet 2026 : 1 584 quartiers, dont 1 493 dans les communes de la base (les 91 quartiers de "
            "Saint-Martin et de Polynésie française sont hors champ). La liste rattache chaque quartier à une seule commune : un quartier "
            "qui s'étend sur plusieurs communes n'est compté que dans sa commune de rattachement.")
    inds = [{'col': 'qpv_nb_2024', 'libelle': 'Nombre de quartiers prioritaires de la politique de la ville', 'unite': 'quartiers',
             'definition': "Nombre de quartiers prioritaires de la politique de la ville rattachés à la commune. " + base,
             'agregation': 'somme', 'annee': '2024'},
            {'col': 'qpv_presence_2024', 'libelle': 'Commune comptant au moins un quartier prioritaire', 'unite': 'communes',
             'definition': ("Vaut 1 si au moins un quartier prioritaire est rattaché à la commune, 0 sinon ; additionné sur un territoire, "
                            "donne le nombre de communes avec un quartier prioritaire. ") + base,
             'agregation': 'somme', 'annee': '2024'}]
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
