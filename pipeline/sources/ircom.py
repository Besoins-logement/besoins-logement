# -*- coding: utf-8 -*-
"""Impôt sur le revenu par commune (DGFiP, IRCOM) : foyers fiscaux, foyers imposés, revenu fiscal de référence total et moyen, répartition par tranche de revenu."""
import io, time, shutil, zipfile, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import geo

URL = ('https://static.data.gouv.fr/resources/limpot-sur-le-revenu-par-collectivite-territoriale-ircom/'
       '20260526-131537/ircom-2025-revenus-2024.zip')
FICHIER_XLSX = 'ircom_2025_revenus_2024/ircom_communes_complet_revenus_2024.xlsx'
AN = '2024'

SOURCE = {'ref': 'E6-29',
          'nom': "L'impôt sur le revenu par collectivité territoriale (IRCOM)",
          'producteur': 'DGFiP (Département des études et statistiques fiscales)',
          'url': 'https://www.data.gouv.fr/datasets/limpot-sur-le-revenu-par-collectivite-territoriale-ircom',
          'telechargement': URL,
          'millesime': 'revenus 2024 déclarés en 2025 (publication mai 2026)',
          'licence': 'Licence ouverte 2.0'}

# tranches de revenu fiscal de référence publiées (libellé du fichier -> suffixe de colonne, libellé)
TRANCHES = [('0 à 10 000', '0_10k', 'de 0 à 10 000 euros'),
            ('10 001 à 12 000', '10k_12k', 'de 10 001 à 12 000 euros'),
            ('12 001 à 15 000', '12k_15k', 'de 12 001 à 15 000 euros'),
            ('15 001 à 20 000', '15k_20k', 'de 15 001 à 20 000 euros'),
            ('20 001 à 30 000', '20k_30k', 'de 20 001 à 30 000 euros'),
            ('30 001 à 50 000', '30k_50k', 'de 30 001 à 50 000 euros'),
            ('50 001 à 100 000', '50k_100k', 'de 50 001 à 100 000 euros'),
            ('+ de 100 000', 'plus_100k', 'de plus de 100 000 euros')]


def _telecharger(url, dest, essais=6):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=600) as r, open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.replace(dest)
            return dest
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def _somme_stricte(df, cols):
    """Somme par commune 2026 ; vide si une des anciennes communes regroupées a une valeur absente (secret)."""
    s = df.groupby('CODGEO')[cols].sum(min_count=1)
    manque = df[cols].isna().groupby(df['CODGEO']).any()
    return s.mask(manque)


def charger(cache: Path) -> list:
    zp = _telecharger(URL, Path(cache) / 'ircom' / URL.rsplit('/', 1)[1])
    with zipfile.ZipFile(zp) as z:
        brut = pd.read_excel(io.BytesIO(z.read(FICHIER_XLSX)), header=None, dtype=str, engine='calamine')
    brut = brut.iloc[7:, 1:14]
    brut.columns = ['dep', 'com', 'lib', 'tranche', 'foyers', 'rfr', 'impot', 'foyers_imp', 'rfr_imp',
                    'foyers_sal', 'sal', 'foyers_pen', 'pen']
    brut = brut[brut.dep.notna() & brut.com.notna() & (brut.dep != 'B31')]       # B31 : non-résidents
    # code commune : 2 premiers caractères du code département + code commune à 3 chiffres (97 + 101 pour les DOM)
    brut['code'] = brut.dep.str[:2] + brut.com.str.zfill(3)
    num = ['foyers', 'rfr', 'impot', 'foyers_imp', 'rfr_imp', 'foyers_sal', 'sal', 'foyers_pen', 'pen']
    for c in num:
        brut[c] = pd.to_numeric(brut[c].str.replace(',', '.', regex=False), errors='coerce')   # 'n.c.' -> vide
    brut['CODGEO'] = geo.vers_cog2026(brut.code).values
    brut = brut.dropna(subset=['CODGEO'])                     # Monaco, Saint-Barthélemy, Saint-Martin

    tot = brut[brut.tranche == 'Total']
    out = _somme_stricte(tot, num)

    # tranches : publiées seulement pour les communes les plus grandes ; on ne garde que les communes dont toutes les tranches sont connues
    tr = brut[brut.tranche != 'Total'].pivot_table(index='code', columns='tranche', values='foyers', aggfunc='first', dropna=False)
    tr = tr.reindex(columns=[t[0] for t in TRANCHES])
    tr = tr[tr.notna().all(axis=1)]
    tr.columns = [f'ircom_foyers_rfr_{t[1]}_{AN}' for t in TRANCHES]
    cols_tr = list(tr.columns)
    tot_codes = tot[['code', 'CODGEO']].drop_duplicates('code')
    trm = tot_codes.merge(tr, left_on='code', right_index=True, how='left')
    det = _somme_stricte(trm, cols_tr)
    det[f'ircom_foyers_detail_{AN}'] = det[cols_tr].sum(axis=1, min_count=len(cols_tr))
    det = det.mask(det[f'ircom_foyers_detail_{AN}'].isna())

    noms = {'foyers': f'ircom_foyers_{AN}', 'rfr': f'ircom_rfr_{AN}', 'impot': f'ircom_impot_net_{AN}',
            'foyers_imp': f'ircom_foyers_imposes_{AN}', 'rfr_imp': f'ircom_rfr_imposes_{AN}',
            'foyers_sal': f'ircom_foyers_salaires_{AN}', 'sal': f'ircom_salaires_{AN}',
            'foyers_pen': f'ircom_foyers_pensions_{AN}', 'pen': f'ircom_pensions_{AN}'}
    out = out.rename(columns=noms).join(det, how='left')
    out[f'ircom_rfr_moyen_{AN}'] = out[f'ircom_rfr_{AN}'] / out[f'ircom_foyers_{AN}'] * 1000
    out[f'ircom_part_foyers_imposes_{AN}'] = out[f'ircom_foyers_imposes_{AN}'] / out[f'ircom_foyers_{AN}'] * 100
    out[f'ircom_part_foyers_pensions_{AN}'] = out[f'ircom_foyers_pensions_{AN}'] / out[f'ircom_foyers_{AN}'] * 100
    out[f'ircom_part_foyers_rfr_0_10k_{AN}'] = out[f'ircom_foyers_rfr_0_10k_{AN}'] / out[f'ircom_foyers_detail_{AN}'] * 100
    out = out.replace([np.inf, -np.inf], np.nan).reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    nc = ' Valeur non diffusée par la DGFiP (secret fiscal) laissée vide.'
    md = " Montant en milliers d'euros."
    ind = [
        {'col': f'ircom_foyers_{AN}', 'libelle': f'Foyers fiscaux en {AN}', 'unite': 'foyers fiscaux',
         'definition': f"Nombre de foyers fiscaux ayant déposé une déclaration de revenus {AN} (impôt établi en {int(AN) + 1})." + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_rfr_{AN}', 'libelle': f'Revenu fiscal de référence total en {AN}', 'unite': "milliers d'euros",
         'definition': f"Somme des revenus fiscaux de référence des foyers fiscaux, revenus {AN}." + md + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_rfr_moyen_{AN}', 'libelle': f'Revenu fiscal de référence moyen par foyer en {AN}', 'unite': 'euros par foyer fiscal',
         'definition': f"Revenu fiscal de référence total divisé par le nombre de foyers fiscaux, revenus {AN}.",
         'agregation': 'ratio', 'num': f'ircom_rfr_{AN}', 'den': f'ircom_foyers_{AN}', 'facteur': 1000, 'annee': AN},
        {'col': f'ircom_impot_net_{AN}', 'libelle': f"Impôt sur le revenu net total en {AN}", 'unite': "milliers d'euros",
         'definition': f"Montant total de l'impôt sur le revenu net des foyers fiscaux, revenus {AN}, après réductions et crédits d'impôt (peut être négatif)." + md + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_foyers_imposes_{AN}', 'libelle': f'Foyers fiscaux imposés en {AN}', 'unite': 'foyers fiscaux',
         'definition': f"Nombre de foyers fiscaux redevables d'un impôt sur le revenu, revenus {AN}." + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_part_foyers_imposes_{AN}', 'libelle': f'Part des foyers fiscaux imposés en {AN}', 'unite': '%',
         'definition': f"Foyers fiscaux imposés divisés par l'ensemble des foyers fiscaux, revenus {AN}.",
         'agregation': 'ratio', 'num': f'ircom_foyers_imposes_{AN}', 'den': f'ircom_foyers_{AN}', 'facteur': 100, 'annee': AN},
        {'col': f'ircom_rfr_imposes_{AN}', 'libelle': f'Revenu fiscal de référence des foyers imposés en {AN}', 'unite': "milliers d'euros",
         'definition': f"Somme des revenus fiscaux de référence des seuls foyers fiscaux imposés, revenus {AN}." + md + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_foyers_salaires_{AN}', 'libelle': f'Foyers fiscaux déclarant des salaires en {AN}', 'unite': 'foyers fiscaux',
         'definition': f"Nombre de foyers fiscaux déclarant des traitements et salaires, revenus {AN}." + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_salaires_{AN}', 'libelle': f'Traitements et salaires déclarés en {AN}', 'unite': "milliers d'euros",
         'definition': f"Montant total des traitements et salaires déclarés par les foyers fiscaux, revenus {AN}." + md + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_foyers_pensions_{AN}', 'libelle': f'Foyers fiscaux déclarant des retraites en {AN}', 'unite': 'foyers fiscaux',
         'definition': f"Nombre de foyers fiscaux déclarant des retraites et pensions, revenus {AN}." + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_pensions_{AN}', 'libelle': f'Retraites et pensions déclarées en {AN}', 'unite': "milliers d'euros",
         'definition': f"Montant total des retraites et pensions déclarées par les foyers fiscaux, revenus {AN}." + md + nc,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_part_foyers_pensions_{AN}', 'libelle': f'Part des foyers fiscaux déclarant des retraites en {AN}', 'unite': '%',
         'definition': f"Foyers fiscaux déclarant des retraites et pensions divisés par l'ensemble des foyers fiscaux, revenus {AN}.",
         'agregation': 'ratio', 'num': f'ircom_foyers_pensions_{AN}', 'den': f'ircom_foyers_{AN}', 'facteur': 100, 'annee': AN},
    ]
    det_txt = (" Détail publié par la DGFiP seulement pour les communes les plus grandes (environ 6 300 communes) ;"
               " vide pour les autres communes et pour celles où une tranche est couverte par le secret fiscal."
               " Au-dessus de la commune, la somme ne couvre que les communes détaillées.")
    for lib_f, suf, lib in TRANCHES:
        ind.append({'col': f'ircom_foyers_rfr_{suf}_{AN}', 'libelle': f'Foyers fiscaux au revenu fiscal de référence {lib} en {AN}',
                    'unite': 'foyers fiscaux',
                    'definition': f"Nombre de foyers fiscaux dont le revenu fiscal de référence {AN} est compris dans la tranche {lib}." + det_txt,
                    'agregation': 'somme', 'annee': AN})
    ind += [
        {'col': f'ircom_foyers_detail_{AN}', 'libelle': f'Foyers fiscaux des communes détaillées par tranche en {AN}', 'unite': 'foyers fiscaux',
         'definition': f"Nombre total de foyers fiscaux des communes pour lesquelles toutes les tranches de revenu fiscal de référence sont connues, revenus {AN}. Sert de dénominateur aux parts par tranche." + det_txt,
         'agregation': 'somme', 'annee': AN},
        {'col': f'ircom_part_foyers_rfr_0_10k_{AN}', 'libelle': f'Part des foyers fiscaux au revenu fiscal de référence inférieur à 10 000 euros en {AN}', 'unite': '%',
         'definition': f"Foyers fiscaux dont le revenu fiscal de référence {AN} est compris entre 0 et 10 000 euros, divisés par les foyers fiscaux des communes détaillées par tranche." + det_txt,
         'agregation': 'ratio', 'num': f'ircom_foyers_rfr_0_10k_{AN}', 'den': f'ircom_foyers_detail_{AN}', 'facteur': 100, 'annee': AN},
    ]
    out = out[['CODGEO'] + [d['col'] for d in ind]]
    return [{'theme': 'revenus', 'data': out, 'indicateurs': ind}]
