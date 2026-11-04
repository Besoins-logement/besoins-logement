# -*- coding: utf-8 -*-
"""Inventaire SRU : logements sociaux décomptés, taux SRU et situation de la commune au regard de l'article 55 de la loi SRU (soumise, déficitaire, carencée, exemptée)."""
import time, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

URL = 'https://static.data.gouv.fr/resources/communes-et-inventaire-sru/20260811-123753/donnees-sru-data-gouv-2026.csv'
DESC = 'https://static.data.gouv.fr/resources/communes-et-inventaire-sru/20260811-123437/descriptif-donnees-sru-2026.ods'

SOURCE = {'ref': 'E7-30',
          'nom': 'Communes et inventaire SRU',
          'producteur': 'DGALN (ministère chargé du logement)',
          'url': 'https://www.data.gouv.fr/datasets/communes-et-inventaire-sru',
          'telechargement': URL,
          'millesime': '2026 (inventaire au 1er janvier 2025, situation 2026)',
          'licence': 'Licence ouverte 2.0'}


def _dl(url, p, essais=8):
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                p.write_bytes(r.read())
                return p
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def _nombre(s):
    """'30,15%' -> 30.15 ; '278 499,32 €' -> 278499.32 ; '-   €' -> 0 ; texte -> NaN."""
    t = s.fillna('').str.replace(r'[\s€%]', '', regex=True).str.replace(',', '.', regex=False)
    t = t.mask(t == '-', '0')
    return pd.to_numeric(t, errors='coerce')


def charger(cache: Path) -> list:
    d = cache / 'sru'
    p = _dl(URL, d / 'donnees-sru-data-gouv-2026.csv')
    _dl(DESC, d / 'descriptif-donnees-sru-2026.ods')
    raw = pd.read_csv(p, sep=';', dtype=str, encoding='cp1252')
    raw.columns = [c.strip() for c in raw.columns]
    col = {c.lower().replace(' ', ''): c for c in raw.columns}
    g = lambda k: raw[col[k.lower()]].str.strip()
    x = pd.DataFrame({'code': g('Code_INSEE_commune')})
    x['sru_soumise_2026'] = pd.to_numeric(g('Commune_sru_au_01_01_2026'), errors='coerce')
    x['sru_lls_2025'] = pd.to_numeric(g('Nombre_lls_Inventaire_au_01_01_2025'), errors='coerce')
    taux_txt = g('Taux_SRU_au_01_01_2025')
    x['sru_taux_2025'] = _nombre(taux_txt).where(~taux_txt.str.startswith('>', na=False))
    x['sru_taux_plus25_2025'] = taux_txt.str.startswith('>', na=False).astype(int)
    x['sru_taux_cible_2026'] = _nombre(g('Taux_cible_commune'))
    x['sru_deficitaire_2025'] = pd.to_numeric(g('commune_deficitaire_au_01-01-2025'), errors='coerce')
    x['sru_carencee_2023_2025'] = pd.to_numeric(g('Commune_carencee_2023_2025'), errors='coerce')
    x['sru_exemptee_2026_2028'] = pd.to_numeric(g('Commune_exemptee_2026_2028'), errors='coerce')
    x['sru_prelevement_2026'] = _nombre(g('Prelevement_net_2026_dont_majoration'))
    x['entree'] = taux_txt.str.contains('Entr', na=False)

    def statut(r):
        if r.sru_soumise_2026 != 1:
            return 'Non soumise'
        if r.sru_exemptee_2026_2028 == 1:
            return 'Soumise, exemptée 2026-2028'
        if r.entree:
            return 'Soumise, entrée dans le dispositif (pas encore d\'inventaire)'
        if r.sru_carencee_2023_2025 == 1:
            return 'Soumise, déficitaire et carencée'
        if r.sru_deficitaire_2025 == 1:
            return 'Soumise, déficitaire'
        return 'Soumise, non déficitaire'
    x['sru_statut_2026'] = x.apply(statut, axis=1)
    x['CODGEO'] = geo.vers_cog2026(x.code).values
    x = x.dropna(subset=['CODGEO'])
    assert not x.CODGEO.duplicated().any(), 'plusieurs lignes SRU pour une même commune 2026'

    ref = geo.referentiel()[['CODGEO']]
    df = ref.merge(x.drop(columns=['code', 'entree']), on='CODGEO', how='left')
    # communes absentes de l'inventaire : non soumises à l'article 55
    df['sru_statut_2026'] = df['sru_statut_2026'].fillna('Non soumise')
    for c in ['sru_soumise_2026', 'sru_deficitaire_2025', 'sru_carencee_2023_2025', 'sru_exemptee_2026_2028', 'sru_taux_plus25_2025']:
        df[c] = df[c].fillna(0).astype('float64')
    df['sru_prelevement_2026'] = df['sru_prelevement_2026'].where(df.sru_soumise_2026 == 1)

    inds = [
        {'col': 'sru_statut_2026', 'libelle': 'Situation SRU de la commune en 2026', 'unite': '',
         'definition': "Situation de la commune au regard de l'article 55 de la loi SRU : non soumise, soumise non déficitaire, soumise déficitaire, déficitaire et carencée (bilan 2023-2025), exemptée pour 2026-2028, ou entrée dans le dispositif sans inventaire.",
         'agregation': 'texte'},
        {'col': 'sru_soumise_2026', 'libelle': 'Commune soumise à la loi SRU en 2026', 'unite': 'communes',
         'definition': "1 si la commune est soumise à l'obligation de logements sociaux de l'article 55 de la loi SRU au 1er janvier 2026, sinon 0. Additionné, donne le nombre de communes soumises.",
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'sru_deficitaire_2025', 'libelle': 'Commune déficitaire en logements sociaux au 1er janvier 2025', 'unite': 'communes',
         'definition': '1 si la commune soumise n\'atteint pas son taux légal de logements sociaux au 1er janvier 2025, sinon 0.',
         'agregation': 'somme', 'annee': '2025'},
        {'col': 'sru_carencee_2023_2025', 'libelle': 'Commune carencée (bilan 2023-2025)', 'unite': 'communes',
         'definition': '1 si le préfet a prononcé la carence de la commune à l\'issue du bilan triennal 2023-2025, sinon 0.',
         'agregation': 'somme', 'annee': '2025'},
        {'col': 'sru_exemptee_2026_2028', 'libelle': 'Commune exemptée de l\'obligation SRU pour 2026-2028', 'unite': 'communes',
         'definition': '1 si la commune est exemptée de l\'obligation SRU pour la période 2026-2028, sinon 0.',
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'sru_lls_2025', 'libelle': 'Logements sociaux décomptés au titre de la loi SRU au 1er janvier 2025', 'unite': 'logements',
         'definition': "Nombre de logements locatifs sociaux retenus dans l'inventaire SRU au 1er janvier 2025 (communes soumises seulement ; vide pour les autres communes et pour les communes sans inventaire).",
         'agregation': 'somme', 'annee': '2025'},
        {'col': 'sru_taux_2025', 'libelle': 'Taux de logements sociaux SRU au 1er janvier 2025', 'unite': '%',
         'definition': "Part des logements sociaux décomptés dans les résidences principales au 1er janvier 2025, publiée par la source. Vide si la commune n'est pas soumise, si elle entre dans le dispositif ou si la source indique seulement plus de 25 %. Le nombre de résidences principales n'étant pas publié, le taux n'est pas recalculé aux niveaux supérieurs.",
         'agregation': 'non_additif', 'annee': '2025'},
        {'col': 'sru_taux_plus25_2025', 'libelle': 'Commune au taux SRU publié comme supérieur à 25 %', 'unite': 'communes',
         'definition': '1 si la source publie le taux SRU au 1er janvier 2025 sous la forme « plus de 25 % » sans valeur exacte, sinon 0.',
         'agregation': 'somme', 'annee': '2025'},
        {'col': 'sru_taux_cible_2026', 'libelle': 'Taux légal de logements sociaux à atteindre', 'unite': '%',
         'definition': 'Taux de logements sociaux que la commune soumise doit atteindre (20 % ou 25 % des résidences principales).',
         'agregation': 'non_additif', 'annee': '2026'},
        {'col': 'sru_prelevement_2026', 'libelle': 'Prélèvement SRU net 2026', 'unite': 'euros',
         'definition': 'Montant net du prélèvement opéré en 2026 sur les ressources de la commune déficitaire, majoration comprise (0 si aucun prélèvement, vide si la commune n\'est pas soumise).',
         'agregation': 'somme', 'annee': '2026'},
    ]
    df = df[['CODGEO'] + [i['col'] for i in inds]]
    return [{'theme': 'logement', 'data': df, 'indicateurs': inds}]
