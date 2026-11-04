# -*- coding: utf-8 -*-
"""Allocataires des CAF par commune (Cafdata) : foyers allocataires, aides au logement par type de parc, RSA, prime d'activité, prestations familiales."""
import time, shutil, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import geo

DATE = '2024-12-01'          # dernier mois de référence publié (décembre 2024)
AN = '2024'
ODS = 'https://data.caf.fr/api/explore/v2.1/catalog/datasets/{}/exports/csv?'
JEUX = {'s_ben_com_f': 's_ben_com_f_2024-12.csv', 'al_s_type_parc_com_f': 'al_s_type_parc_com_f_2024-12.csv'}


def _url(ds):
    return ODS.format(ds) + urllib.parse.urlencode({'where': f"dtreffre=date'{DATE}'", 'delimiter': ';'})


SOURCE = {'ref': 'E6-30, E6-31',
          'nom': "Cafdata : allocataires par prestation (s_ben_com_f) et bénéficiaires d'une aide au logement selon le type de parc (al_s_type_parc_com_f), par commune",
          'producteur': 'Caisse nationale des allocations familiales (Cnaf)',
          'url': 'https://data.caf.fr/explore/dataset/s_ben_com_f/ ; https://data.caf.fr/explore/dataset/al_s_type_parc_com_f/',
          'telechargement': ' ; '.join(_url(d) for d in JEUX),
          'millesime': 'décembre 2024 (géographie au 1er janvier 2025)',
          'licence': 'Licence ouverte 2.0'}


def _telecharger(url, dest, essais=8):
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


def _somme_stricte(df, cols):
    """Somme par commune 2026 ; vide si une des anciennes communes regroupées a une valeur absente."""
    s = df.groupby('CODGEO')[cols].sum(min_count=1)
    return s.mask(df[cols].isna().groupby(df['CODGEO']).any())


def charger(cache: Path) -> list:
    rep = Path(cache) / 'caf'
    a = pd.read_csv(_telecharger(_url('s_ben_com_f'), rep / JEUX['s_ben_com_f']), sep=';', dtype={'numcomdo': str})
    b = pd.read_csv(_telecharger(_url('al_s_type_parc_com_f'), rep / JEUX['al_s_type_parc_com_f']), sep=';', dtype={'numcomdo': str})

    # 1. allocataires par prestation (une ligne par commune ; la ligne sans code commune regroupe les foyers non localisés)
    champs = {'indfoy_ndur': 'foyers_allocataires', 'indnbp_ndur': 'personnes_couvertes', 'indmtt_ndur': 'montant_prestations',
              'indfoy_ndural': 'foyers_al', 'indnbp_ndural': 'personnes_al', 'indmtt_ndural': 'montant_al',
              'indfoy_apl': 'foyers_apl', 'indfoy_alf': 'foyers_alf', 'indfoy_als': 'foyers_als',
              'indfoy_rsa': 'foyers_rsa', 'indnbp_rsa': 'personnes_rsa', 'indfoy_ppa': 'foyers_ppa',
              'indfoy_af': 'foyers_af', 'indfoy_asf': 'foyers_asf', 'indfoy_ndurpaje': 'foyers_paje'}
    a = a.dropna(subset=['numcomdo'])
    a['CODGEO'] = geo.vers_cog2026(a.numcomdo).values
    a = a.dropna(subset=['CODGEO']).rename(columns=champs)
    cols = list(champs.values())
    for c in cols:
        a[c] = pd.to_numeric(a[c], errors='coerce')
    out = _somme_stricte(a, cols)

    # 2. aides au logement selon le type de parc (absence de ligne pour un type = aucun foyer pour ce type)
    b = b.dropna(subset=['numcomdo'])
    b['indfoy_ndural'] = pd.to_numeric(b.indfoy_ndural, errors='coerce')
    p = b.pivot_table(index='numcomdo', columns='al_type_parc', values='indfoy_ndural', aggfunc='first')
    p = p.reindex(columns=['Parc privé', 'Parc public']).fillna(0)
    p.columns = ['foyers_al_parc_prive', 'foyers_al_parc_public']
    p['foyers_al_type_parc'] = p.sum(axis=1)
    p = p.reset_index()
    p['CODGEO'] = geo.vers_cog2026(p.numcomdo).values
    p = p.dropna(subset=['CODGEO'])
    out = out.join(_somme_stricte(p, ['foyers_al_parc_prive', 'foyers_al_parc_public', 'foyers_al_type_parc']), how='outer')

    out['part_foyers_al'] = out.foyers_al / out.foyers_allocataires * 100
    out['montant_moyen_al'] = out.montant_al / out.foyers_al
    out['part_al_parc_public'] = out.foyers_al_parc_public / out.foyers_al_type_parc * 100
    out = out.replace([np.inf, -np.inf], np.nan)
    out.columns = [f'caf_{c}_{AN}' for c in out.columns]
    out = out.reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    arr = " Effectif arrondi à 5 par la Cnaf (la somme des communes ne donne pas exactement le total publié pour un territoire plus grand)."
    mois = f"au titre du mois de décembre {AN}"
    def n(col, lib, unite, definition, agr='somme', **kw):
        d = {'col': f'caf_{col}_{AN}', 'libelle': lib, 'unite': unite, 'definition': definition, 'agregation': agr, 'annee': AN}
        d.update({k: (f'caf_{v}_{AN}' if k in ('num', 'den') else v) for k, v in kw.items()})
        return d
    ind = [
        n('foyers_allocataires', f'Foyers allocataires des CAF en décembre {AN}', 'foyers allocataires',
          f"Nombre de foyers bénéficiaires d'au moins une prestation légale versée par la CAF {mois} (hors allocation de rentrée scolaire et hors prestations ADE et AVVC, selon la définition de la Cnaf)." + arr),
        n('personnes_couvertes', f'Personnes couvertes par les CAF en décembre {AN}', 'personnes',
          f"Nombre de personnes vivant dans un foyer allocataire (allocataire, conjoint, enfants et autres personnes à charge) {mois}." + arr),
        n('montant_prestations', f'Montant des prestations CAF versées pour décembre {AN}', 'euros par mois',
          f"Montant total des prestations légales versées par la CAF {mois}."),
        n('foyers_al', f"Foyers bénéficiaires d'une aide au logement en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant une aide personnelle au logement (APL, ALF ou ALS) {mois}." + arr),
        n('personnes_al', f"Personnes couvertes par une aide au logement en décembre {AN}", 'personnes',
          f"Nombre de personnes vivant dans un foyer percevant une aide personnelle au logement {mois}." + arr),
        n('montant_al', f"Montant des aides au logement versées pour décembre {AN}", 'euros par mois',
          f"Montant total des aides personnelles au logement (APL, ALF, ALS) versées {mois}."),
        n('foyers_apl', f"Foyers bénéficiaires de l'APL en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant l'aide personnalisée au logement (logement conventionné, surtout le parc social) {mois}." + arr),
        n('foyers_alf', f"Foyers bénéficiaires de l'ALF en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant l'allocation de logement familiale (familles avec personnes à charge, logement non conventionné) {mois}." + arr),
        n('foyers_als', f"Foyers bénéficiaires de l'ALS en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant l'allocation de logement sociale (personnes sans charge de famille, logement non conventionné, dont étudiants) {mois}." + arr),
        n('foyers_rsa', f'Foyers bénéficiaires du RSA en décembre {AN}', 'foyers allocataires',
          f"Nombre de foyers percevant le revenu de solidarité active versé par la CAF {mois}." + arr),
        n('personnes_rsa', f'Personnes couvertes par le RSA en décembre {AN}', 'personnes',
          f"Nombre de personnes vivant dans un foyer bénéficiaire du revenu de solidarité active {mois}." + arr),
        n('foyers_ppa', f"Foyers bénéficiaires de la prime d'activité en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant la prime d'activité {mois}." + arr),
        n('foyers_af', f'Foyers bénéficiaires des allocations familiales en décembre {AN}', 'foyers allocataires',
          f"Nombre de foyers percevant les allocations familiales (au moins deux enfants à charge) {mois}." + arr),
        n('foyers_asf', f"Foyers bénéficiaires de l'allocation de soutien familial en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant l'allocation de soutien familial, versée surtout aux parents qui élèvent seuls leurs enfants {mois}." + arr),
        n('foyers_paje', f"Foyers bénéficiaires de la PAJE en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant au moins une prestation d'accueil du jeune enfant (prime à la naissance, allocation de base, complément mode de garde, PreParE) {mois}." + arr),
        n('foyers_al_parc_prive', f"Foyers bénéficiaires d'une aide au logement dans le parc privé en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant une aide au logement et logés dans le parc privé {mois} (jeu al_s_type_parc_com_f ; zéro quand la Cnaf ne publie pas de ligne pour ce type)." + arr),
        n('foyers_al_parc_public', f"Foyers bénéficiaires d'une aide au logement dans le parc public en décembre {AN}", 'foyers allocataires',
          f"Nombre de foyers percevant une aide au logement et logés dans le parc public (logement social) {mois} (jeu al_s_type_parc_com_f ; zéro quand la Cnaf ne publie pas de ligne pour ce type)." + arr),
        n('foyers_al_type_parc', f"Foyers bénéficiaires d'une aide au logement au type de parc connu en décembre {AN}", 'foyers allocataires',
          f"Somme des foyers bénéficiaires d'une aide au logement dans le parc privé et dans le parc public {mois}. Sert de dénominateur à la part du parc public." + arr),
        n('part_foyers_al', f"Part des foyers allocataires percevant une aide au logement en décembre {AN}", '%',
          f"Foyers bénéficiaires d'une aide au logement divisés par l'ensemble des foyers allocataires de la CAF {mois}.",
          'ratio', num='foyers_al', den='foyers_allocataires', facteur=100),
        n('montant_moyen_al', f"Montant moyen de l'aide au logement en décembre {AN}", 'euros par foyer et par mois',
          f"Montant total des aides au logement divisé par le nombre de foyers bénéficiaires, {mois}.",
          'ratio', num='montant_al', den='foyers_al', facteur=1),
        n('part_al_parc_public', f"Part du parc public parmi les bénéficiaires d'une aide au logement en décembre {AN}", '%',
          f"Foyers bénéficiaires d'une aide au logement logés dans le parc public divisés par les foyers bénéficiaires au type de parc connu, {mois}.",
          'ratio', num='foyers_al_parc_public', den='foyers_al_type_parc', facteur=100),
    ]
    out = out[['CODGEO'] + [d['col'] for d in ind]]
    return [{'theme': 'revenus', 'data': out, 'indicateurs': ind}]
