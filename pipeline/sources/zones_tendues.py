# -*- coding: utf-8 -*-
"""Communes en zone tendue au sens de la taxe sur les logements vacants et communes où le niveau des loyers est encadré."""
import json, shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

URL_TLV = 'https://gitlab.com/pidila/sp-simulateurs-data/-/raw/master/donnees-de-reference/TaxeLogementVacant.json'
URL_ENC = ('https://static.data.gouv.fr/resources/communes-a-encadrement-des-loyers-encadrement-du-niveau-des-loyers-loi-elan-article-140/'
           '20261029-231309/communes-encadrement-des-loyers.csv')

SOURCE = {'ref': 'P2-112',
          'nom': 'Communes en zone tendue (taxe sur les logements vacants) et communes à encadrement des loyers',
          'producteur': ("Premier ministre (DILA) : données de référence du simulateur « zones tendues » de service-public.fr, reprenant les "
                         "deux listes du décret n° 2013-392 modifié ; Naistor : compilation, commune par commune, des décrets de périmètre "
                         "et des arrêtés préfectoraux d'encadrement des loyers (aucune liste officielle en données ouvertes)"),
          'url': 'https://www.data.gouv.fr/datasets/simulateur-des-zones-tendues ; https://www.data.gouv.fr/datasets/communes-a-encadrement-des-loyers-encadrement-du-niveau-des-loyers-loi-elan-article-140',
          'telechargement': f'{URL_TLV} ; {URL_ENC}',
          'millesime': "Listes de zones tendues en vigueur en 2026 (décret n° 2013-392 modifié, notamment par le décret n° 2023-822 du 25 août 2023) ; encadrement des loyers vérifié le 29 octobre 2026",
          'licence': 'Licence ouverte 2.0'}

LISTES = {'PlusDe50000': ('zt_tendue_agglo_2026', "Zone tendue : agglomération de plus de 50 000 habitants"),
          'DesequilibreOffreEtDemande': ('zt_tendue_autre_2026', "Zone tendue : autre commune en déséquilibre marqué")}


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
    d = Path(cache) / 'zones_tendues'
    tlv = json.loads(_telecharger(URL_TLV, d / 'TaxeLogementVacant.json').read_text(encoding='utf-8'))
    enc = pd.read_csv(_telecharger(URL_ENC, d / 'communes-encadrement-des-loyers.csv'), dtype=str, encoding='utf-8')

    lignes = [(cle, str(x['codeInsee']).strip()) for cle in LISTES for x in tlv[cle] if x.get('Ok', True)]
    z = pd.DataFrame(lignes, columns=['liste', 'code'])
    z['CODGEO'] = geo.vers_cog2026(z.code).values
    if z.CODGEO.isna().any():
        print(f"zones_tendues : {z.CODGEO.isna().sum()} codes de la liste TLV sans commune 2026, écartés")
    z = z.dropna(subset=['CODGEO'])
    df = geo.referentiel()[['CODGEO']].copy()
    for cle, (col, _) in LISTES.items():
        df[col] = df.CODGEO.isin(set(z.loc[z.liste == cle, 'CODGEO'])).astype('int64')
    # commune nouvelle dont une partie seulement figure sur une liste : 1 (maximum des anciennes communes) ;
    # si elle figure dans les deux listes, on garde la liste des agglomérations de plus de 50 000 habitants
    df.loc[df.zt_tendue_agglo_2026 == 1, 'zt_tendue_autre_2026'] = 0
    df['zt_zone_tendue_2026'] = (df.zt_tendue_agglo_2026 | df.zt_tendue_autre_2026).astype('int64')
    df['zt_categorie_2026'] = 'Hors zone tendue'
    for cle, (col, lib) in LISTES.items():
        df.loc[df[col] == 1, 'zt_categorie_2026'] = lib

    enc['CODGEO'] = geo.vers_cog2026(enc.code_insee.str.strip()).values
    enc = enc.dropna(subset=['CODGEO'])
    enc['partiel'] = enc.zone.str.strip().eq('partie').astype('int64')
    e = enc.groupby('CODGEO').agg(territoire=('territoire', 'first'), partiel=('partiel', 'min'))
    df = df.merge(e, left_on='CODGEO', right_index=True, how='left')
    df['zt_encadrement_loyers_2026'] = df.territoire.notna().astype('int64')
    df['zt_encadrement_partiel_2026'] = df.partiel.fillna(0).astype('int64')
    df['zt_encadrement_territoire_2026'] = df.territoire.str.replace(r'\s*\(\d+ communes\)', '', regex=True)
    df = df[['CODGEO', 'zt_zone_tendue_2026', 'zt_tendue_agglo_2026', 'zt_tendue_autre_2026', 'zt_categorie_2026',
             'zt_encadrement_loyers_2026', 'zt_encadrement_partiel_2026', 'zt_encadrement_territoire_2026']]
    df = df.sort_values('CODGEO').reset_index(drop=True)

    tlv_txt = ("Listes annexées au décret n° 2013-392 du 10 mai 2013 modifié (notamment par le décret n° 2023-822 du 25 août 2023), "
               "telles que reprises dans les données de référence du simulateur « zones tendues » de service-public.fr. Dans ces "
               "communes s'appliquent la taxe annuelle sur les logements vacants, la possibilité de majorer la taxe d'habitation sur "
               "les résidences secondaires et des règles locatives propres aux zones tendues (préavis réduit, plafonnement des "
               "hausses de loyer à la relocation). Pour une commune nouvelle dont une partie seulement figure sur une liste, "
               "l'indicateur vaut 1.")
    enc_txt = ("Encadrement du niveau des loyers (article 140 de la loi ELAN, à titre expérimental) : un arrêté préfectoral fixe "
               "chaque année des loyers de référence et le loyer d'un nouveau bail ne peut pas dépasser le loyer de référence majoré. "
               "Territoires concernés en 2026 : Paris, Lille (avec Hellemmes et Lomme), Plaine Commune, Est Ensemble, Lyon et "
               "Villeurbanne, Montpellier, Bordeaux, Pays basque et Grenoble-Alpes Métropole. Liste compilée par Naistor à partir "
               "des décrets de périmètre et des arrêtés préfectoraux en vigueur (vérifiée le 29 octobre 2026), faute de liste "
               "officielle en données ouvertes.")
    flag = " Vaut 1 si oui, 0 sinon ; additionné sur un territoire, donne le nombre de communes concernées."
    inds = [
        {'col': 'zt_zone_tendue_2026', 'libelle': 'Commune en zone tendue (taxe sur les logements vacants)', 'unite': 'communes',
         'definition': "Commune figurant sur l'une des deux listes de communes en zone tendue." + flag + ' ' + tlv_txt,
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'zt_tendue_agglo_2026', 'libelle': LISTES['PlusDe50000'][1], 'unite': 'communes',
         'definition': ("Commune de la première liste : commune appartenant à une zone d'urbanisation continue de plus de 50 000 "
                        "habitants où existe un déséquilibre marqué entre l'offre et la demande de logements.") + flag + ' ' + tlv_txt,
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'zt_tendue_autre_2026', 'libelle': LISTES['DesequilibreOffreEtDemande'][1], 'unite': 'communes',
         'definition': ("Commune de la seconde liste, ajoutée en 2023 : commune hors de ces agglomérations mais connaissant un "
                        "déséquilibre marqué entre l'offre et la demande de logements, lié notamment à une forte proportion de "
                        "résidences secondaires.") + flag + ' ' + tlv_txt,
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'zt_categorie_2026', 'libelle': 'Catégorie de zone tendue', 'unite': '',
         'definition': ("Hors zone tendue, zone tendue au titre d'une agglomération de plus de 50 000 habitants, ou zone tendue au "
                        "titre d'un autre déséquilibre marqué (seconde liste). ") + tlv_txt,
         'agregation': 'texte', 'annee': '2026'},
        {'col': 'zt_encadrement_loyers_2026', 'libelle': 'Commune où le niveau des loyers est encadré', 'unite': 'communes',
         'definition': "Commune où s'applique l'encadrement du niveau des loyers, sur tout ou partie de son territoire." + flag + ' ' + enc_txt,
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'zt_encadrement_partiel_2026', 'libelle': 'Encadrement des loyers sur une partie de la commune seulement', 'unite': 'communes',
         'definition': ("Commune où l'encadrement des loyers ne couvre qu'une partie du territoire (zones Iris listées dans le décret, "
                        "cas de 8 communes de Grenoble-Alpes Métropole).") + flag + ' ' + enc_txt,
         'agregation': 'somme', 'annee': '2026'},
        {'col': 'zt_encadrement_territoire_2026', 'libelle': "Territoire d'encadrement des loyers", 'unite': '',
         'definition': "Nom du territoire d'encadrement des loyers auquel appartient la commune (vide sinon). " + enc_txt,
         'agregation': 'texte', 'annee': '2026'}]
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
