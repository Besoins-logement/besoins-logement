# -*- coding: utf-8 -*-
"""Zone climatique réglementaire de la construction (RE2020, DPE) de chaque commune, déduite de son département."""
from pathlib import Path
import pandas as pd
import geo

ANNEXE = Path('/mnt/user-data/uploads/Besoin de logement/phase3/Annexe_base_unique_croisements.xlsx')

SOURCE = {'ref': 'E5-13',
          'nom': 'Zones climatiques réglementaires (RE2020 et méthode DPE) par département',
          'producteur': "Ministère chargé de la construction (DHUP) ; table département - zone déduite par le projet de la base des DPE de l'ADEME",
          'url': 'https://rt-re-batiment.developpement-durable.gouv.fr/documents-complementaires-a706.html',
          'telechargement': "Annexe_base_unique_croisements.xlsx, onglet « Zones climatiques » (phase 3 du projet) ; table recopiée dans ce module",
          'millesime': "Zonage RE2020 (identique à celui de la RT2012) ; table vérifiée sur la base DPE de l'ADEME, extraction du 6 octobre 2026",
          'licence': 'Licence ouverte 2.0 (base DPE ADEME) ; texte réglementaire public'}

# Table département -> zone climatique, recopiée de l'onglet « Zones climatiques » de l'annexe de phase 3
# (96 départements de métropole ; l'outre-mer n'est pas couvert par ce zonage).
ZONE_DEP = {
    '01': 'H1c', '02': 'H1a', '03': 'H1c', '04': 'H2d', '05': 'H1c', '06': 'H3', '07': 'H2d', '08': 'H1b', '09': 'H2c',
    '10': 'H1b', '11': 'H3', '12': 'H2c', '13': 'H3', '14': 'H1a', '15': 'H1c', '16': 'H2b', '17': 'H2b', '18': 'H2b',
    '19': 'H1c', '2A': 'H3', '2B': 'H3', '21': 'H1c', '22': 'H2a', '23': 'H1c', '24': 'H2c', '25': 'H1c', '26': 'H2d',
    '27': 'H1a', '28': 'H1a', '29': 'H2a', '30': 'H3', '31': 'H2c', '32': 'H2c', '33': 'H2c', '34': 'H3', '35': 'H2a',
    '36': 'H2b', '37': 'H2b', '38': 'H1c', '39': 'H1c', '40': 'H2c', '41': 'H2b', '42': 'H1c', '43': 'H1c', '44': 'H2b',
    '45': 'H1b', '46': 'H2c', '47': 'H2c', '48': 'H2d', '49': 'H2b', '50': 'H2a', '51': 'H1b', '52': 'H1b', '53': 'H2b',
    '54': 'H1b', '55': 'H1b', '56': 'H2a', '57': 'H1b', '58': 'H1b', '59': 'H1a', '60': 'H1a', '61': 'H1a', '62': 'H1a',
    '63': 'H1c', '64': 'H2c', '65': 'H2c', '66': 'H3', '67': 'H1b', '68': 'H1b', '69': 'H1c', '70': 'H1b', '71': 'H1c',
    '72': 'H2b', '73': 'H1c', '74': 'H1c', '75': 'H1a', '76': 'H1a', '77': 'H1a', '78': 'H1a', '79': 'H2b', '80': 'H1a',
    '81': 'H2c', '82': 'H2c', '83': 'H3', '84': 'H2d', '85': 'H2b', '86': 'H2b', '87': 'H1c', '88': 'H1b', '89': 'H1b',
    '90': 'H1b', '91': 'H1a', '92': 'H1a', '93': 'H1a', '94': 'H1a', '95': 'H1a'}
ZONES = ['H1a', 'H1b', 'H1c', 'H2a', 'H2b', 'H2c', 'H2d', 'H3']


def _table_annexe():
    """Relit l'onglet de l'annexe quand il est disponible, pour vérifier la table recopiée ci-dessus."""
    if not ANNEXE.exists():
        return None
    t = pd.read_excel(ANNEXE, sheet_name='Zones climatiques', dtype=str, engine='calamine')
    return dict(zip(t['Code département'].str.strip(), t['Zone climatique'].str.strip()))


def charger(cache: Path) -> list:
    table = ZONE_DEP
    annexe = _table_annexe()
    if annexe is not None:
        if annexe != ZONE_DEP:
            print('zone_climatique : la table de l annexe diffère de la table recopiée, la version de l annexe est utilisée')
            table = annexe
        dossier = Path(cache) / 'zone_climatique'
        dossier.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(sorted(table.items()), columns=['DEP', 'zone_climatique']).to_csv(dossier / 'zones_climatiques_departements.csv', index=False)

    ref = geo.referentiel()[['CODGEO', 'DEP']].copy()
    ref['CODGEO'] = geo.vers_cog2026(ref.CODGEO).values
    df = ref.dropna(subset=['CODGEO']).drop_duplicates('CODGEO')
    df['zclim_zone'] = df.DEP.map(table)
    df['zclim_groupe'] = df.zclim_zone.str[:2]
    for z in ZONES:
        df[f'zclim_{z.lower()}'] = (df.zclim_zone == z).astype('int64')
    df = df.drop(columns='DEP').sort_values('CODGEO').reset_index(drop=True)

    regle = ("La zone est celle du département de la commune (table déduite de la base des diagnostics de performance "
             "énergétique de l'ADEME : dans chaque département, une même zone porte 97 à 99,8 % des diagnostics, "
             "extraction du 6 octobre 2026). La règle d'altitude n'est pas appliquée : la modulation selon l'altitude "
             "(moins de 400 m, 400 à 800 m, plus de 800 m) n'est pas prise en compte, toutes les communes d'un département "
             "reçoivent la même zone. L'outre-mer n'est pas couvert par ce zonage (valeur vide).")
    inds = [{'col': 'zclim_zone', 'libelle': 'Zone climatique réglementaire (RE2020)', 'unite': '',
             'definition': ("Zone climatique de la réglementation environnementale RE2020 et de la méthode du DPE : "
                            "H1a, H1b, H1c (climat le plus froid), H2a, H2b, H2c, H2d (climat tempéré) ou H3 (climat méditerranéen). ") + regle,
             'agregation': 'texte'},
            {'col': 'zclim_groupe', 'libelle': 'Grande zone climatique (H1, H2 ou H3)', 'unite': '',
             'definition': "Regroupement des zones climatiques en trois grandes zones : H1 (H1a, H1b, H1c), H2 (H2a à H2d) et H3. " + regle,
             'agregation': 'texte'}]
    for z in ZONES:
        inds.append({'col': f'zclim_{z.lower()}', 'libelle': f'Commune en zone climatique {z}', 'unite': 'communes',
                     'definition': (f"Vaut 1 si la commune est en zone climatique {z}, 0 sinon (0 aussi pour l'outre-mer). "
                                    f"Additionnée sur un territoire, donne le nombre de communes en zone {z}. ") + regle,
                     'agregation': 'somme'})
    return [{'theme': 'risques_energie', 'data': df, 'indicateurs': inds}]
