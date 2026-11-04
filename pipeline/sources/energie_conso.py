# -*- coding: utf-8 -*-
"""Consommation résidentielle d'électricité et de gaz par commune (Agence ORE) : consommation annuelle et nombre de points de livraison des logements."""
import json, time, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import geo

AN = '2025'
JEU = 'noxwlxv702-ohfyt76f-a3y9'      # Consommation annuelle d'électricité et gaz par commune
API = f'https://opendata.agenceore.fr/data-fair/api/v1/datasets/{JEU}/lines?'
URL = API + urllib.parse.urlencode({'qs': f'annee:{AN} AND code_categorie_consommation:RES', 'size': 10000,
                                    'select': 'operateur,filiere,annee,code_commune,nb_sites,conso_totale_mwh,nombre_de_mailles_secretisees'})

SOURCE = {'ref': 'E7-46',
          'nom': "Consommation annuelle d'électricité et de gaz par commune (secteur résidentiel)",
          'producteur': "Agence ORE (Opérateurs de réseaux d'énergie : Enedis, GRDF et distributeurs locaux)",
          'url': f'https://opendata.agenceore.fr/datasets/{JEU}',
          'telechargement': URL,
          'millesime': f'{AN} (mise à jour du 30 octobre 2026)',
          'licence': 'Licence ouverte 2.0'}


def _get(url, essais=10):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(3 * (k + 1))


def _telecharger(dest):
    """Lit toutes les pages de l'API data-fair (10 000 lignes par page) et les enregistre une seule fois en CSV."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    lignes, url, total = [], URL, None
    while url:
        d = json.loads(_get(url))
        total = d.get('total', total)
        lignes += d['results']
        url = d.get('next') if d['results'] else None
    df = pd.DataFrame(lignes)
    assert total is None or len(df) == total, f'téléchargement incomplet ({len(df)} lignes sur {total})'
    tmp = dest.with_name(dest.name + '.part')
    df.drop(columns=[c for c in df.columns if c.startswith('_')]).to_csv(tmp, index=False)
    tmp.replace(dest)
    return dest


def charger(cache: Path) -> list:
    df = pd.read_csv(_telecharger(Path(cache) / 'energie_conso' / f'ore_conso_residentiel_{AN}.csv'),
                     dtype={'code_commune': str, 'annee': str})
    df = df[df.annee == AN]
    df['CODGEO'] = geo.vers_cog2026(df.code_commune).values
    df = df.dropna(subset=['CODGEO'])
    for c in ['nb_sites', 'conso_totale_mwh']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    out = pd.DataFrame(index=pd.Index(sorted(df.CODGEO.unique()), name='CODGEO'))
    for fil, suf in [('Electricité', 'elec'), ('Gaz', 'gaz')]:
        x = df[df.filiere == fil]
        # lignes secrètes (valeurs absentes) ignorées ; commune vide si toutes ses lignes sont secrètes
        s = x.groupby('CODGEO')[['conso_totale_mwh', 'nb_sites']].sum(min_count=1)
        s.columns = [f'ore_conso_{suf}_res_{AN}', f'ore_pdl_{suf}_res_{AN}']
        out = out.join(s, how='left')
        if suf == 'gaz':   # commune présente pour l'électricité mais sans ligne gaz : aucun point de livraison de gaz
            sans = ~out.index.isin(x.CODGEO.unique())
            out.loc[sans, s.columns] = 0.0
    out[f'ore_conso_moy_elec_res_{AN}'] = out[f'ore_conso_elec_res_{AN}'] / out[f'ore_pdl_elec_res_{AN}']
    out[f'ore_conso_moy_gaz_res_{AN}'] = out[f'ore_conso_gaz_res_{AN}'] / out[f'ore_pdl_gaz_res_{AN}']
    out = out.replace([np.inf, -np.inf], np.nan).reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    sec = (" Les lignes couvertes par le secret statistique (opérateur desservant très peu de points dans la commune) ne sont pas comptées ;"
           " vide si toutes les lignes de la commune sont secrètes.")
    ind = [
        {'col': f'ore_conso_elec_res_{AN}', 'libelle': f"Consommation d'électricité des logements en {AN}", 'unite': 'MWh',
         'definition': f"Consommation annuelle d'électricité des points de livraison du secteur résidentiel, tous gestionnaires de réseau de distribution, année {AN}." + sec,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ore_pdl_elec_res_{AN}', 'libelle': f"Points de livraison d'électricité résidentiels en {AN}", 'unite': 'points de livraison',
         'definition': f"Nombre de points de livraison (compteurs) d'électricité du secteur résidentiel, année {AN}." + sec,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ore_conso_gaz_res_{AN}', 'libelle': f"Consommation de gaz des logements en {AN}", 'unite': 'MWh',
         'definition': f"Consommation annuelle de gaz naturel des points de livraison du secteur résidentiel, année {AN} ; zéro quand la commune n'a aucun point de livraison de gaz." + sec,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ore_pdl_gaz_res_{AN}', 'libelle': f"Points de livraison de gaz résidentiels en {AN}", 'unite': 'points de livraison',
         'definition': f"Nombre de points de livraison (compteurs) de gaz naturel du secteur résidentiel, année {AN} ; zéro quand la commune n'est pas desservie en gaz." + sec,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ore_conso_moy_elec_res_{AN}', 'libelle': f"Consommation moyenne d'électricité par point de livraison résidentiel en {AN}", 'unite': 'MWh par point de livraison',
         'definition': f"Consommation résidentielle d'électricité divisée par le nombre de points de livraison résidentiels, année {AN}.",
         'agregation': 'ratio', 'num': f'ore_conso_elec_res_{AN}', 'den': f'ore_pdl_elec_res_{AN}', 'facteur': 1, 'annee': AN},
        {'col': f'ore_conso_moy_gaz_res_{AN}', 'libelle': f"Consommation moyenne de gaz par point de livraison résidentiel en {AN}", 'unite': 'MWh par point de livraison',
         'definition': f"Consommation résidentielle de gaz divisée par le nombre de points de livraison résidentiels de gaz, année {AN}.",
         'agregation': 'ratio', 'num': f'ore_conso_gaz_res_{AN}', 'den': f'ore_pdl_gaz_res_{AN}', 'facteur': 1, 'annee': AN},
    ]
    out = out[['CODGEO'] + [d['col'] for d in ind]]
    return [{'theme': 'risques_energie', 'data': out, 'indicateurs': ind}]
