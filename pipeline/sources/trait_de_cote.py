# -*- coding: utf-8 -*-
"""Communes inscrites sur la liste des communes exposées au recul du trait de côte (article L. 321-15 du code de l'environnement)."""
import ast, shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

SOURCE = {'ref': 'P2-067',
          'nom': "Liste des communes dont l'action en matière d'urbanisme doit être adaptée au recul du trait de côte (art. L. 321-15 du code de l'environnement)",
          'producteur': 'Ministère de la Transition écologique',
          'url': 'https://www.data.gouv.fr/datasets/liste-des-communes-volontaires-pour-sadapter-au-recul-du-trait-de-cote',
          'telechargement': 'https://static.data.gouv.fr/resources/liste-des-communes-volontaires-pour-sadapter-au-recul-du-trait-de-cote/20260218-105039/trait-de-cote-commune-2026-95.csv',
          'millesime': 'Décret n° 2022-750 du 29 avril 2022 modifié, en dernier lieu par le décret n° 2026-95 du 13 février 2026 (371 communes)',
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


def _premiere_annee(historique):
    """Année du premier décret qui a inscrit la commune (champ trait_de_cote_historique : liste de décrets successifs)."""
    try:
        dates = [h['start_date'] for h in ast.literal_eval(historique) if h.get('start_date')]
        return min(dates)[:4] if dates else None
    except (ValueError, SyntaxError, TypeError):
        return None


def charger(cache: Path) -> list:
    p = _telecharger(SOURCE['telechargement'], Path(cache) / 'trait_de_cote' / 'trait-de-cote-commune-2026-95.csv')
    brut = pd.read_csv(p, dtype=str, encoding='utf-8')
    brut = brut[brut.is_currently_active.str.strip().str.lower() == 'true'].copy()
    brut['CODGEO'] = geo.vers_cog2026(brut.code_commune.str.strip()).values
    if brut.CODGEO.isna().any():
        print(f'trait_de_cote : {brut.CODGEO.isna().sum()} communes sans code 2026 écartées')
    brut = brut.dropna(subset=['CODGEO'])
    brut['annee'] = brut.trait_de_cote_historique.map(_premiere_annee)
    g = brut.groupby('CODGEO').annee.min()     # commune nouvelle : première inscription de l'une de ses parties

    df = geo.referentiel()[['CODGEO']].copy()
    df['tdc_liste_2026'] = df.CODGEO.isin(set(g.index)).astype('int64')
    df['tdc_premiere_inscription'] = df.CODGEO.map(g)
    df = df.sort_values('CODGEO').reset_index(drop=True)

    base = ("Liste fixée par le décret n° 2022-750 du 29 avril 2022, modifié en 2023, 2024 et en dernier lieu par le décret "
            "n° 2026-95 du 13 février 2026 (371 communes, outre-mer compris). L'inscription, faite à la demande ou avec l'accord de "
            "la commune, entraîne l'élaboration d'une carte locale d'exposition au recul du trait de côte à 30 ans et de 30 à 100 ans, "
            "des zones d'exposition dans le document d'urbanisme et un droit de préemption spécifique ; elle traduit une exposition "
            "reconnue, pas une mesure de l'intensité de l'érosion.")
    inds = [{'col': 'tdc_liste_2026', 'libelle': 'Commune inscrite sur la liste des communes exposées au recul du trait de côte',
             'unite': 'communes', 'agregation': 'somme', 'annee': '2026',
             'definition': ("Vaut 1 si la commune figure sur la liste des communes dont l'action en matière d'urbanisme et la politique "
                            "d'aménagement doivent être adaptées aux phénomènes entraînant l'érosion du littoral (article L. 321-15 du "
                            "code de l'environnement), 0 sinon ; additionné sur un territoire, donne le nombre de communes inscrites. ") + base},
            {'col': 'tdc_premiere_inscription', 'libelle': "Année de première inscription sur la liste du recul du trait de côte",
             'unite': 'année', 'agregation': 'texte',
             'definition': ("Année d'entrée en vigueur du premier décret qui a inscrit la commune sur la liste (2022, 2023, 2024 ou "
                            "2026) ; vide si la commune n'est pas inscrite. ") + base}]
    return [{'theme': 'risques_energie', 'data': df, 'indicateurs': inds}]
