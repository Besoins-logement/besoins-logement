# -*- coding: utf-8 -*-
"""Demandeurs d'emploi inscrits à France Travail par commune (Dares) : catégories A, B, C au 4e trimestre 2024 et 2023, par sexe et âge."""
import time, shutil, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import geo

JEU = 'dares_defm_communales-brutes'
URL = (f'https://data.dares.travail-emploi.gouv.fr/api/explore/v2.1/catalog/datasets/{JEU}/exports/csv?'
       + urllib.parse.urlencode({'select': 'date,code_commune,categorie,sexe,tranche_d_age,nombre_de_demandeurs_d_emploi',
                                 'where': "date='2024-T4' or (date='2023-T4' and sexe='Total' and tranche_d_age='Total')",
                                 'delimiter': ';'}))

SOURCE = {'ref': 'E6-34',
          'nom': "Inscrits à France Travail, données communales trimestrielles brutes",
          'producteur': 'Dares et France Travail (statistique mensuelle du marché du travail)',
          'url': 'https://www.data.gouv.fr/datasets/inscrits-a-france-travail-donnees-communales-trimestrielles-brutes',
          'telechargement': URL,
          'millesime': '4e trimestre 2024 et 4e trimestre 2023 (moyennes trimestrielles, géographie 2024, mise à jour octobre 2026)',
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=10):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=900) as r, open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dest)
            return dest
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def charger(cache: Path) -> list:
    d = pd.read_csv(_telecharger(URL, Path(cache) / 'france_travail' / 'dares_defm_communales_2023T4_2024T4.csv'),
                    sep=';', dtype={'code_commune': str}, encoding='utf-8-sig')
    d = d[(d.categorie == 'ABC') & (d.code_commune != 'Total')]
    # la source donne à la fois Paris, Lyon, Marseille et leurs arrondissements : on retire les arrondissements pour ne pas compter deux fois
    cog = pd.read_csv(geo.fichier('insee/v_commune_2026.csv'), dtype=str)
    arm = cog[cog.TYPECOM == 'ARM']
    arm = set(arm.loc[arm.COMPARENT.isin(set(d.code_commune)), 'COM'])
    d = d[~d.code_commune.isin(arm)]
    d['CODGEO'] = geo.vers_cog2026(d.code_commune).values
    d = d.dropna(subset=['CODGEO'])
    d['n'] = pd.to_numeric(d.nombre_de_demandeurs_d_emploi, errors='coerce')
    series = {('2024-T4', 'Total', 'Total'): 'ft_defm_abc_2024t4',
              ('2024-T4', 'Femmes', 'Total'): 'ft_defm_abc_femmes_2024t4',
              ('2024-T4', 'Total', 'Moins de 25 ans'): 'ft_defm_abc_moins25ans_2024t4',
              ('2024-T4', 'Total', '50 ans et plus'): 'ft_defm_abc_50ansplus_2024t4',
              ('2023-T4', 'Total', 'Total'): 'ft_defm_abc_2023t4'}
    d['col'] = [series.get(k) for k in zip(d.date, d.sexe, d.tranche_d_age)]
    d = d.dropna(subset=['col'])
    s = d.groupby(['CODGEO', 'col']).n.sum(min_count=1)
    manque = d.n.isna().groupby([d.CODGEO, d.col]).any()
    out = s.mask(manque).unstack('col').reindex(columns=list(series.values()))
    out['ft_part_femmes_2024t4'] = out.ft_defm_abc_femmes_2024t4 / out.ft_defm_abc_2024t4 * 100
    out['ft_part_moins25ans_2024t4'] = out.ft_defm_abc_moins25ans_2024t4 / out.ft_defm_abc_2024t4 * 100
    out['ft_part_50ansplus_2024t4'] = out.ft_defm_abc_50ansplus_2024t4 / out.ft_defm_abc_2024t4 * 100
    out['ft_evol_abc_2023t4_2024t4'] = out.ft_defm_abc_2024t4 / out.ft_defm_abc_2023t4 * 100
    out = out.replace([np.inf, -np.inf], np.nan).reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    arr = (" Moyenne des effectifs inscrits en fin de mois sur le trimestre, données brutes arrondies à 5 par la Dares"
           " (la somme des communes peut s'écarter légèrement du total publié).")
    abc = ("demandeurs d'emploi inscrits à France Travail en catégories A, B et C (tenus de rechercher un emploi,"
           " sans emploi pour la catégorie A ou en activité réduite pour B et C)")
    ind = [
        {'col': 'ft_defm_abc_2024t4', 'libelle': "Demandeurs d'emploi en catégories A, B, C au 4e trimestre 2024", 'unite': "demandeurs d'emploi",
         'definition': f"Nombre de {abc}, 4e trimestre 2024." + arr, 'agregation': 'somme', 'annee': '2024'},
        {'col': 'ft_defm_abc_femmes_2024t4', 'libelle': "Femmes demandeuses d'emploi en catégories A, B, C au 4e trimestre 2024", 'unite': "demandeurs d'emploi",
         'definition': f"Nombre de femmes parmi les {abc}, 4e trimestre 2024." + arr, 'agregation': 'somme', 'annee': '2024'},
        {'col': 'ft_defm_abc_moins25ans_2024t4', 'libelle': "Demandeurs d'emploi de moins de 25 ans en catégories A, B, C au 4e trimestre 2024", 'unite': "demandeurs d'emploi",
         'definition': f"Nombre de personnes de moins de 25 ans parmi les {abc}, 4e trimestre 2024." + arr, 'agregation': 'somme', 'annee': '2024'},
        {'col': 'ft_defm_abc_50ansplus_2024t4', 'libelle': "Demandeurs d'emploi de 50 ans ou plus en catégories A, B, C au 4e trimestre 2024", 'unite': "demandeurs d'emploi",
         'definition': f"Nombre de personnes de 50 ans ou plus parmi les {abc}, 4e trimestre 2024." + arr, 'agregation': 'somme', 'annee': '2024'},
        {'col': 'ft_defm_abc_2023t4', 'libelle': "Demandeurs d'emploi en catégories A, B, C au 4e trimestre 2023", 'unite': "demandeurs d'emploi",
         'definition': f"Nombre de {abc}, 4e trimestre 2023." + arr, 'agregation': 'somme', 'annee': '2023'},
        {'col': 'ft_part_femmes_2024t4', 'libelle': "Part des femmes parmi les demandeurs d'emploi en catégories A, B, C au 4e trimestre 2024", 'unite': '%',
         'definition': "Femmes inscrites en catégories A, B, C divisées par l'ensemble des inscrits en catégories A, B, C, 4e trimestre 2024.",
         'agregation': 'ratio', 'num': 'ft_defm_abc_femmes_2024t4', 'den': 'ft_defm_abc_2024t4', 'facteur': 100, 'annee': '2024'},
        {'col': 'ft_part_moins25ans_2024t4', 'libelle': "Part des moins de 25 ans parmi les demandeurs d'emploi en catégories A, B, C au 4e trimestre 2024", 'unite': '%',
         'definition': "Inscrits de moins de 25 ans en catégories A, B, C divisés par l'ensemble des inscrits en catégories A, B, C, 4e trimestre 2024.",
         'agregation': 'ratio', 'num': 'ft_defm_abc_moins25ans_2024t4', 'den': 'ft_defm_abc_2024t4', 'facteur': 100, 'annee': '2024'},
        {'col': 'ft_part_50ansplus_2024t4', 'libelle': "Part des 50 ans ou plus parmi les demandeurs d'emploi en catégories A, B, C au 4e trimestre 2024", 'unite': '%',
         'definition': "Inscrits de 50 ans ou plus en catégories A, B, C divisés par l'ensemble des inscrits en catégories A, B, C, 4e trimestre 2024.",
         'agregation': 'ratio', 'num': 'ft_defm_abc_50ansplus_2024t4', 'den': 'ft_defm_abc_2024t4', 'facteur': 100, 'annee': '2024'},
        {'col': 'ft_evol_abc_2023t4_2024t4', 'libelle': "Indice d'évolution des demandeurs d'emploi A, B, C entre fin 2023 et fin 2024 (base 100 au 4e trimestre 2023)", 'unite': 'indice base 100',
         'definition': "Inscrits en catégories A, B, C au 4e trimestre 2024 divisés par les inscrits au 4e trimestre 2023, multipliés par 100 (110 = hausse de 10 %). À lire avec prudence pour les petites communes, à cause de l'arrondi à 5.",
         'agregation': 'ratio', 'num': 'ft_defm_abc_2024t4', 'den': 'ft_defm_abc_2023t4', 'facteur': 100, 'annee': '2024'},
    ]
    out = out[['CODGEO'] + [x['col'] for x in ind]]
    return [{'theme': 'emploi', 'data': out, 'indicateurs': ind}]
