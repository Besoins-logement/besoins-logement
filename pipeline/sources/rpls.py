# -*- coding: utf-8 -*-
"""Parc locatif social par commune (RPLS, SDES) : nombre de logements des bailleurs sociaux, mises en service récentes, type, taille, financement et étiquette énergie."""
import time, urllib.request
from pathlib import Path
import pandas as pd
import geo

MILLESIME = '2025-01'          # RPLS au 1er janvier 2025
AN = '2025'
RID = 'f3c2f2cb-8fb1-40fd-8733-964247744c9a'
COLONNES = 'DEPCOM,TYPECONST_CODE,NBPIECE,FINAN_CODE,LOCAT,DPEENERGIE'
URL = ('https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/' + RID +
       '/csv?millesime={m}&withColumnName=true&withColumnDescription=false&withColumnUnit=false&columns={c}&DEP_CODE=eq:{d}')

SOURCE = {'ref': 'B2-rpls',
          'nom': 'Répertoire des logements locatifs des bailleurs sociaux (RPLS), données détaillées au logement agrégées à la commune',
          'producteur': 'SDES (ministère chargé du logement)',
          'url': 'https://www.data.gouv.fr/datasets/donnees-detaillees-au-logement-du-repertoire-des-logements-locatifs-des-bailleurs-sociaux-rpls',
          'telechargement': URL.format(m=MILLESIME, c=COLONNES, d='<departement>'),
          'millesime': 'RPLS au 1er janvier 2025',
          'licence': 'Licence ouverte 2.0'}

# Regroupement des codes de financement initial (FINAN_CODE) du RPLS
FINAN = {'tres_social': ['10', '11'],                 # PLA d'intégration, PLA très social, PLA insertion, LLTS (PLAI et assimilés)
         'social': ['12', '13'],                      # PLA ordinaire, PLUS, LLS dans les DOM
         'avant1977': ['50', '51', '52', '53', '54', '55', '99'],   # financements HLM antérieurs à la réforme de 1977
         'pls': ['14', '15'],                         # PLS, PPLS, PCLS, PLA CFF
         'intermediaire': ['16', '17'],               # PLI, PCL
         'autre': ['49']}                             # autre financement après 1977


def _get(url, dest, essais=8):
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                data = r.read()
            tmp = dest.with_suffix('.part')
            tmp.write_bytes(data)
            tmp.replace(dest)
            return dest
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def telecharger(cache: Path):
    """Un fichier CSV par département (export DiDo filtré, colonnes utiles seulement)."""
    d = cache / 'rpls' / MILLESIME
    d.mkdir(parents=True, exist_ok=True)
    deps = pd.read_csv(geo.fichier('insee/v_departement_2026.csv'), dtype=str).DEP.tolist()
    for dep in deps:
        p = d / f'rpls_{dep}.csv'
        if not p.exists():
            _get(URL.format(m=MILLESIME, c=COLONNES, d=dep), p)
    return [d / f'rpls_{dep}.csv' for dep in deps]


def charger(cache: Path) -> list:
    fichiers = telecharger(cache)
    lg = pd.concat([pd.read_csv(f, sep=';', dtype=str) for f in fichiers], ignore_index=True)
    lg['CODGEO'] = geo.vers_cog2026(lg.DEPCOM).values
    lg = lg.dropna(subset=['CODGEO'])
    an_prec = str(int(AN) - 1)
    fin = lg.FINAN_CODE.fillna('').str.strip()
    nbp = pd.to_numeric(lg.NBPIECE, errors='coerce')
    dpe = lg.DPEENERGIE.fillna('').str.strip().str.upper()
    tc = lg.TYPECONST_CODE.fillna('').str.strip().str.upper()
    p = 'rpls_'
    v = pd.DataFrame({'CODGEO': lg.CODGEO})
    v[f'{p}logements_{AN}'] = 1
    v[f'{p}mises_service_{AN}'] = (lg.LOCAT.fillna('').str[:4] == an_prec).astype(int)
    v[f'{p}collectifs_{AN}'] = (tc == 'C').astype(int)
    v[f'{p}individuels_{AN}'] = (tc == 'I').astype(int)
    v[f'{p}etudiants_{AN}'] = (tc == 'E').astype(int)
    v[f'{p}t1_{AN}'] = (nbp == 1).astype(int)
    v[f'{p}t2_{AN}'] = (nbp == 2).astype(int)
    v[f'{p}t3_{AN}'] = (nbp == 3).astype(int)
    v[f'{p}t4_{AN}'] = (nbp == 4).astype(int)
    v[f'{p}t5plus_{AN}'] = (nbp >= 5).astype(int)
    for k, codes in FINAN.items():
        v[f'{p}fin_{k}_{AN}'] = fin.isin(codes).astype(int)
    v[f'{p}dpe_connu_{AN}'] = dpe.isin(list('ABCDEFG')).astype(int)
    v[f'{p}dpe_fg_{AN}'] = dpe.isin(['F', 'G']).astype(int)
    df = v.groupby('CODGEO', as_index=False).sum()
    # communes sans logement social : 0 (le répertoire est exhaustif)
    ref = geo.referentiel()[['CODGEO']]
    df = ref.merge(df, on='CODGEO', how='left')
    cols = [c for c in df.columns if c != 'CODGEO']
    df[cols] = df[cols].fillna(0).astype('int64')
    df[f'{p}part_mises_service_{AN}'] = df[f'{p}mises_service_{AN}'] / df[f'{p}logements_{AN}'].where(df[f'{p}logements_{AN}'] > 0) * 100
    df[f'{p}part_dpe_fg_{AN}'] = df[f'{p}dpe_fg_{AN}'] / df[f'{p}dpe_connu_{AN}'].where(df[f'{p}dpe_connu_{AN}'] > 0) * 100

    def ind(col, lib, defi, unite='logements', agr='somme', **kw):
        d = {'col': col, 'libelle': lib, 'unite': unite, 'definition': defi, 'agregation': agr, 'annee': AN}
        d.update(kw)
        return d
    dat = 'au 1er janvier ' + AN
    base = ("Logements locatifs des bailleurs sociaux (organismes HLM, SEM et autres bailleurs tenus de déclarer au RPLS) "
            "présents dans le répertoire " + dat + ", hors logements non conventionnés des SEM.")
    fin_lib = {'tres_social': ('financés en PLAI ou équivalent', "financement initial PLA d'intégration, PLA très social, PLA insertion ou LLTS (codes 10 et 11), soit le logement très social"),
               'social': ('financés en PLUS ou PLA ordinaire', 'financement initial PLA ordinaire, PLUS ou LLS dans les DOM (codes 12 et 13), soit le logement social standard'),
               'avant1977': ('financés avant 1977 (HLM ordinaires et assimilés)', 'financement initial HLM antérieur à la réforme de 1977 (codes 50 à 55 et 99)'),
               'pls': ('financés en PLS', 'financement initial PLS, PPLS, PCLS ou PLA CFF (codes 14 et 15)'),
               'intermediaire': ('financés en PLI ou PCL (intermédiaire)', 'financement initial PLI ou PCL (codes 16 et 17)'),
               'autre': ('ayant un autre financement initial', 'financement initial est un autre financement postérieur à 1977 (code 49)')}
    inds = [
        ind(f'{p}logements_{AN}', f'Logements locatifs sociaux {dat}', 'Nombre de logements. ' + base),
        ind(f'{p}mises_service_{AN}', f'Logements sociaux mis en service en {an_prec}',
            f'Nombre de logements du parc social {dat} dont la première mise en location date de {an_prec} (constructions neuves et acquisitions mises en location pour la première fois).'),
        ind(f'{p}part_mises_service_{AN}', f'Part des logements sociaux mis en service en {an_prec}', f'Logements mis en service en {an_prec} rapportés au parc social {dat}.',
            unite='%', agr='ratio', num=f'{p}mises_service_{AN}', den=f'{p}logements_{AN}', facteur=100),
        ind(f'{p}collectifs_{AN}', f'Logements sociaux en immeuble collectif {dat}', 'Nombre de logements du parc social situés dans un immeuble collectif.'),
        ind(f'{p}individuels_{AN}', f'Logements sociaux individuels {dat}', 'Nombre de logements du parc social de type maison individuelle.'),
        ind(f'{p}etudiants_{AN}', f'Logements sociaux étudiants {dat}', 'Nombre de logements du parc social classés en logement étudiant.'),
        ind(f'{p}t1_{AN}', f'Logements sociaux de 1 pièce {dat}', 'Nombre de logements du parc social comptant 1 pièce principale.'),
        ind(f'{p}t2_{AN}', f'Logements sociaux de 2 pièces {dat}', 'Nombre de logements du parc social comptant 2 pièces principales.'),
        ind(f'{p}t3_{AN}', f'Logements sociaux de 3 pièces {dat}', 'Nombre de logements du parc social comptant 3 pièces principales.'),
        ind(f'{p}t4_{AN}', f'Logements sociaux de 4 pièces {dat}', 'Nombre de logements du parc social comptant 4 pièces principales.'),
        ind(f'{p}t5plus_{AN}', f'Logements sociaux de 5 pièces ou plus {dat}', 'Nombre de logements du parc social comptant 5 pièces principales ou plus.'),
    ]
    for k, (lib, defi) in fin_lib.items():
        inds.append(ind(f'{p}fin_{k}_{AN}', f'Logements sociaux {lib} {dat}', f'Nombre de logements du parc social dont le {defi}.'))
    inds += [
        ind(f'{p}dpe_connu_{AN}', f'Logements sociaux avec une étiquette énergie connue {dat}', 'Nombre de logements du parc social dont la classe de consommation d\'énergie du DPE (A à G) est renseignée.'),
        ind(f'{p}dpe_fg_{AN}', f'Logements sociaux classés F ou G {dat}', 'Nombre de logements du parc social dont la classe de consommation d\'énergie du DPE est F ou G.'),
        ind(f'{p}part_dpe_fg_{AN}', f'Part des logements sociaux classés F ou G {dat}', 'Logements classés F ou G rapportés aux logements dont l\'étiquette énergie est connue.',
            unite='%', agr='ratio', num=f'{p}dpe_fg_{AN}', den=f'{p}dpe_connu_{AN}', facteur=100),
    ]
    return [{'theme': 'logement', 'data': df, 'indicateurs': inds}]
