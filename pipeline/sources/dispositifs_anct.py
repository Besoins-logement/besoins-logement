# -*- coding: utf-8 -*-
"""Programmes de politique publique de l'ANCT par commune (Action coeur de ville, Petites villes de demain, Villages d'avenir, etc.) et opérations de revitalisation de territoire (ORT)."""
import shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

URL_ANCT = 'https://static.data.gouv.fr/resources/croisement-des-dispositifs-de-politique-publique-de-lanct/20260413-100516/ngeo-anct-cog2025.csv'
URL_ORT = 'https://grist.numerique.gouv.fr/o/dgaln/api/docs/j4i9oKD3jzFtgEUuM9sXnL/download/csv?tableId=BDD'

SOURCE = {'ref': 'E7-31',
          'nom': "Croisement des dispositifs de politique publique de l'ANCT ; liste des communes couvertes par des opérations de revitalisation de territoire",
          'producteur': "Agence nationale de la cohésion des territoires (ANCT) ; ministère de la Cohésion des territoires (DGALN) pour les ORT",
          'url': 'https://www.data.gouv.fr/datasets/croisement-des-dispositifs-de-politique-publique-de-lanct ; https://www.data.gouv.fr/datasets/liste-des-communes-couvertes-par-des-operations-de-revitalisation-de-territoire',
          'telechargement': f'{URL_ANCT} ; {URL_ORT}',
          'millesime': "Croisement ANCT mis en ligne le 13 avril 2026 (code géographique 2025, dispositifs mis à jour entre juillet 2024 et septembre 2025) ; suivi des ORT tenu à jour en continu (téléchargé en novembre 2026)",
          'licence': 'Licence ouverte 2.0'}

# colonne du fichier ANCT -> (colonne de la base, nom du programme, précision)
PROGRAMMES = [
    ('id_acv', 'anct_acv', 'Action coeur de ville', "programme de revitalisation des centres des villes moyennes"),
    ('id_acv2', 'anct_acv_entrees_ville', "Action coeur de ville, volet entrées de ville", "villes Action coeur de ville volontaires pour la requalification de leurs entrées de ville"),
    ('id_pvd', 'anct_pvd', 'Petites villes de demain', "programme de revitalisation des communes de moins de 20 000 habitants qui exercent des fonctions de centralité"),
    ('id_va', 'anct_villages_avenir', "Villages d'avenir", "programme d'appui en ingénierie aux communes rurales porteuses de projets"),
    ('id_ti', 'anct_territoires_industrie', "Territoires d'industrie", "programme de reconquête industrielle des territoires (commune située dans un territoire d'industrie)"),
    ('id_fs', 'anct_france_services', 'France services', "commune où se trouve au moins une structure France services (guichet d'accès aux services publics)"),
    ('id_cite', 'anct_cite_educative', 'Cité éducative', "commune concernée par une cité éducative (programme éducatif des quartiers prioritaires)"),
    ('id_cde', 'anct_cite_emploi', "Cité de l'emploi", "commune concernée par une cité de l'emploi (programme d'accès à l'emploi des habitants des quartiers prioritaires)"),
    ('id_habinclus', 'anct_habitat_inclusif', 'AMI Habitat inclusif', "commune lauréate de l'appel à manifestation d'intérêt sur l'habitat inclusif"),
    ('id_fabp', 'anct_fabrique_prospective', 'Fabrique prospective', "commune concernée par une fabrique prospective de l'ANCT"),
    ('id_ami', 'anct_avenir_montagnes_ing', 'Avenir montagnes ingénierie', "commune lauréate du programme Avenir montagnes ingénierie"),
    ('id_amm', 'anct_avenir_montagnes_mob', 'Avenir montagnes mobilités', "commune lauréate du programme Avenir montagnes mobilités"),
]


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
    d = Path(cache) / 'dispositifs_anct'
    anct = pd.read_csv(_telecharger(URL_ANCT, d / 'ngeo-anct-cog2025.csv'), sep=';', dtype=str, encoding='utf-8')
    ort = pd.read_csv(_telecharger(URL_ORT, d / 'ort_bdd.csv'), dtype=str, encoding='utf-8')

    a = pd.DataFrame({'CODGEO': geo.vers_cog2026(anct.insee_com.str.strip()).values})
    for src, col, _, _ in PROGRAMMES:
        a[col] = anct[src].notna().astype('int64').values
    a = a.dropna(subset=['CODGEO'])        # collectivités d'outre-mer hors COG (Polynésie, Nouvelle-Calédonie...)
    a = a.groupby('CODGEO').max()           # communes fusionnées au 1er janvier 2026 : 1 si une des anciennes communes était concernée

    o = pd.DataFrame({'CODGEO': geo.vers_cog2026(ort['Code commune'].str.strip()).values,
                      'anct_ort': ort['Signée ?'].str.strip().eq('Signée').astype('int64').values}).dropna(subset=['CODGEO'])
    o = o.groupby('CODGEO').max()

    df = geo.referentiel()[['CODGEO']].merge(a, left_on='CODGEO', right_index=True, how='left')
    df = df.merge(o, left_on='CODGEO', right_index=True, how='left')
    for c in df.columns[1:]:
        df[c] = df[c].fillna(0).astype('int64')
    df = df.sort_values('CODGEO').reset_index(drop=True)

    base = ("Vaut 1 si oui, 0 sinon ; additionné sur un territoire, donne le nombre de communes concernées. "
            "Source : fichier « Croisement des dispositifs de l'ANCT » (code géographique 2025, mis en ligne le 13 avril 2026) ; "
            "pour une commune nouvelle de 2026, vaut 1 si l'une des anciennes communes était concernée.")
    inds = [{'col': col, 'libelle': f'Commune du programme {nom}', 'unite': 'communes', 'agregation': 'somme', 'annee': '2025',
             'definition': f"Commune concernée par le programme {nom} de l'ANCT : {prec}. " + base}
            for _, col, nom, prec in PROGRAMMES]
    inds.append({'col': 'anct_ort', 'libelle': 'Commune couverte par une opération de revitalisation de territoire (ORT)', 'unite': 'communes',
                 'agregation': 'somme', 'annee': '2026',
                 'definition': ("Vaut 1 si la commune est signataire d'une convention d'opération de revitalisation de territoire (ORT) "
                                "signée et en cours, 0 sinon (les conventions terminées ou non encore signées valent 0). Additionné sur un "
                                "territoire, donne le nombre de communes couvertes. Source : liste des communes couvertes par des ORT du "
                                "ministère de la Cohésion des territoires, état téléchargé en novembre 2026.")})
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
