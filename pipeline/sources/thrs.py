# -*- coding: utf-8 -*-
"""Délibérations fiscales des communes pour 2026 : majoration de la taxe d'habitation sur les résidences secondaires (et son taux), taxe d'habitation sur les logements vacants."""
import shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

URL = ('https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/deliberations-de-fiscalite-directe-locale-des-communes-2026-hors-taux/'
       'exports/csv?select=dep,depcom,com,libcom,indtlv,thlvdat,thsurtaxrsdat,thsurtaxrstau&delimiter=%3B')

SOURCE = {'ref': 'E7-38',
          'nom': 'Délibérations de fiscalité directe locale des communes 2026 (hors taux)',
          'producteur': 'Direction générale des finances publiques (DGFiP), ministères économiques et financiers',
          'url': 'https://www.data.gouv.fr/datasets/deliberations-de-fiscalite-directe-locale-des-communes-2026-hors-taux',
          'telechargement': URL,
          'millesime': 'Délibérations applicables en 2026 (mises en ligne le 24 juillet 2026)',
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


def _codes(brut):
    """Code commune : depcom est stocké comme un nombre (zéro initial perdu) et il est vide pour la Corse (2A, 2B).
    Pour la Corse, le numéro de commune (com) est unique sur l'île : on choisit 2A ou 2B selon le code qui existe en 2026."""
    actifs, _ = geo._passage()
    code = brut.depcom.str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(5)
    corse = code.isna()
    num = brut.com.str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(3)
    code[corse] = ['2A' + n if '2A' + n in actifs else '2B' + n for n in num[corse]]
    return code


def charger(cache: Path) -> list:
    p = _telecharger(URL, Path(cache) / 'thrs' / 'delib_com_2026_extrait.csv')
    brut = pd.read_csv(p, sep=';', dtype=str, encoding='utf-8-sig')
    brut['CODGEO'] = geo.vers_cog2026(_codes(brut)).values
    if brut.CODGEO.isna().any():
        print(f'thrs : {brut.CODGEO.isna().sum()} lignes sans commune 2026 écartées')
    brut = brut.dropna(subset=['CODGEO'])
    taux = pd.to_numeric(brut.thsurtaxrstau.str.replace(',', '.'), errors='coerce')
    brut['taux'] = taux.where(taux > 0)
    brut['majo'] = brut.taux.notna().astype('int64')
    brut['thlv'] = brut.thlvdat.notna().astype('int64')
    # plusieurs lignes pour une même commune 2026 (fusion) : 1 si l'une des parties est concernée, taux le plus élevé
    g = brut.groupby('CODGEO').agg(delib_majo_thrs_2026=('majo', 'max'), delib_taux_majo_thrs_2026=('taux', 'max'),
                                   delib_thlv_2026=('thlv', 'max'))
    df = geo.referentiel()[['CODGEO']].merge(g, left_on='CODGEO', right_index=True, how='left')
    for c in ['delib_majo_thrs_2026', 'delib_thlv_2026']:
        df[c] = df[c].fillna(0).astype('int64')
    df['delib_taux_majo_thrs_2026'] = df.delib_taux_majo_thrs_2026.astype('float64')
    df = df[['CODGEO', 'delib_majo_thrs_2026', 'delib_taux_majo_thrs_2026', 'delib_thlv_2026']].sort_values('CODGEO').reset_index(drop=True)

    src = ("Source : fichier des délibérations de fiscalité directe locale des communes applicables en 2026 (DGFiP, mis en ligne "
           "le 24 juillet 2026). Pour une commune nouvelle de 2026 issue de plusieurs lignes, on retient 1 si l'une des anciennes "
           "communes est concernée et le taux le plus élevé.")
    inds = [
        {'col': 'delib_majo_thrs_2026', 'libelle': "Commune majorant la taxe d'habitation sur les résidences secondaires en 2026",
         'unite': 'communes', 'agregation': 'somme', 'annee': '2026',
         'definition': ("Vaut 1 si la commune applique en 2026 une majoration de la part communale de la taxe d'habitation sur les "
                        "résidences secondaires (article 1407 ter du code général des impôts, possible seulement en zone tendue), 0 sinon ; "
                        "additionné sur un territoire, donne le nombre de communes qui l'appliquent. ") + src},
        {'col': 'delib_taux_majo_thrs_2026', 'libelle': "Taux de majoration de la taxe d'habitation sur les résidences secondaires en 2026",
         'unite': '%', 'agregation': 'non_additif', 'poids': 'delib_majo_thrs_2026', 'annee': '2026',
         'definition': ("Taux de la majoration votée par la commune, en pourcentage de la cotisation de taxe d'habitation sur les "
                        "résidences secondaires (de 5 à 60 %). Vide si la commune n'applique pas de majoration. Sur un territoire, "
                        "moyenne simple des taux des communes qui appliquent la majoration. ") + src},
        {'col': 'delib_thlv_2026', 'libelle': "Commune ayant institué la taxe d'habitation sur les logements vacants",
         'unite': 'communes', 'agregation': 'somme', 'annee': '2026',
         'definition': ("Vaut 1 si la commune a institué la taxe d'habitation sur les logements vacants depuis plus de deux ans "
                        "(article 1407 bis du code général des impôts, réservée aux communes hors zone tendue), 0 sinon ; additionné "
                        "sur un territoire, donne le nombre de communes concernées. ") + src}]
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
