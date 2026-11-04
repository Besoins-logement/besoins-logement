# -*- coding: utf-8 -*-
"""Parc de logements et résidences principales des communes : catégorie, type, statut d'occupation, taille, époque de
construction, ancienneté d'emménagement, équipement, peuplement, croisements avec l'âge de la personne de référence
(recensement 2023, rappels 2012 et 2017 ; Insee, Melodi).

Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_LOGEMENT_PRINC, DS_RP_LOGEMENT_COMP (indice de peuplement),
DS_RP_TD_LOGEMENT_AGE_PRINC (résidences principales selon l'âge de la personne de référence, le type de logement,
le nombre de pièces et le statut d'occupation).

Règles : dernière année de chaque série ; au plus deux dimensions hors total. Années 2012 et 2017 : totaux, avec une
exception assumée pour la catégorie de logement (résidences principales, secondaires, vacants), indispensable aux
tendances du parc. Écartés : DS_RP_LOGEMENT_PRINC résidences principales x type x époque de construction (trois
dimensions, 21 séries) ; DS_RP_TD_LOGEMENT_AGE_PRINC âge x type x pièces et âge x type x statut (trois dimensions,
231 séries) et la tranche « personne de référence de moins de 15 ans » ; les séries des millésimes 2012 et
2017 qui n'existent plus en 2023 (anciens découpages des époques de construction) ; mode de chauffage « hors logement ordinaire
ou hors métropole ». Le nombre total de pièces et l'ancienneté cumulée d'emménagement sont des effectifs additifs : ils
servent de numérateurs aux moyennes (pièces par logement, ancienneté moyenne), calculées comme ratios.
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'P2-020',
          'nom': "Recensement de la population 2023 : logements (dossier complet), indice de peuplement, résidences "
                 "principales selon l'âge de la personne de référence (tableaux PRINC) ; autres fiches : E6-10, E6-11, E7-55",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_LOGEMENT_PRINC',
          'telechargement': 'https://api.insee.fr/melodi/file/<jeu>/<jeu>_2023_CSV_FR (zips CSV Melodi : DS_RP_LOGEMENT_PRINC, '
                            'DS_RP_LOGEMENT_COMP, DS_RP_TD_LOGEMENT_AGE_PRINC)',
          'millesime': 'Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017',
          'licence': 'Licence ouverte 2.0'}

TDW = {'1': ('maison', 'maisons'), '2': ('appart', 'appartements'),
       '3T6': ('autre_log', "autres logements (logements-foyers, chambres d'hôtel, habitations de fortune)")}
TSH = {'100': ('proprio', 'ménages propriétaires'), '200': ('loc', 'ménages locataires'),
       '211': ('loc_prive', 'locataires du parc privé (logement vide)'), '212_222': ('loc_meuble', "locataires d'un meublé"),
       '221': ('loc_hlm', "locataires d'un logement HLM vide du parc social"), '300': ('gratuit', 'ménages logés gratuitement')}
NOR = {'R1': ('1', '1 pièce'), 'R2': ('2', '2 pièces'), 'R3': ('3', '3 pièces'), 'R4': ('4', '4 pièces'),
       'R5': ('5', '5 pièces'), 'R_GE5': ('5p', '5 pièces ou plus'), 'R_GE6': ('6p', '6 pièces ou plus')}
CONSTR = {'Y_LT1919': ('av1919', 'construites avant 1919'), 'Y1919T1945': ('1919_1945', 'construites de 1919 à 1945'),
          'Y1946T1970': ('1946_1970', 'construites de 1946 à 1970'), 'Y1971T1990': ('1971_1990', 'construites de 1971 à 1990'),
          'Y1991T2005': ('1991_2005', 'construites de 1991 à 2005'), 'Y2006TAAAA': ('2006_2020', 'construites de 2006 à 2020'),
          'Y_LT2021': ('av2021', 'construites avant 2021 (époque connue)')}
EMM = {'Y_LT2': ('lt2', 'emménagés depuis moins de 2 ans'), 'Y2T4': ('2_4', 'emménagés depuis 2 à 4 ans'),
       'Y5T9': ('5_9', 'emménagés depuis 5 à 9 ans'), 'Y10T19': ('10_19', 'emménagés depuis 10 à 19 ans'),
       'Y20T29': ('20_29', 'emménagés depuis 20 à 29 ans'), 'Y_GE30': ('30p', 'emménagés depuis 30 ans ou plus')}
VOIT = {'C0': ('voit0', 'ménages sans voiture'), 'C1': ('voit1', 'ménages avec une seule voiture'),
        'C_GE1': ('voit1p', 'ménages avec au moins une voiture'), 'C_GE2': ('voit2p', 'ménages avec deux voitures ou plus')}
CHAUF = {'BOT_GAS': ('gaz_citerne', 'chauffage principal au gaz en bouteilles ou en citerne'),
         'ELC': ('elec', "chauffage principal à l'électricité"), 'OIL': ('fioul', 'chauffage principal au fioul'),
         'OTH': ('autre', 'chauffage principal par une autre énergie (bois, solaire, géothermie...)'),
         'TOWN_GAS': ('gaz_reseau', 'chauffage principal au gaz de ville ou par un réseau de chaleur')}
PEUPL = {'SEV_OVER_OCC': ('surocc_accentuee', 'en suroccupation accentuée'), 'MOD_OVER_OCC': ('surocc_moderee', 'en suroccupation modérée'),
         'STD_OCC': ('occ_normale', 'en occupation normale'), 'MOD_UNDER_OCC': ('sousocc_moderee', 'en sous-occupation modérée'),
         'SEV_UNDER_OCC': ('sousocc_accentuee', 'en sous-occupation accentuée'),
         'VSEV_UNDER_OCC': ('sousocc_tres_accentuee', 'en sous-occupation très accentuée')}
AGE_PR = {'Y_GE80': ('80p', 'personne de référence de 80 ans ou plus')}

def _c(dim, d): return {(dim, k): v for k, v in d.items()}

RP = dict(nom='', lib='Résidences principales', unite='logements', defn='Nombre de résidences principales')
T_LOG = 'Logements, principaux indicateurs (dossier complet)'
JEUX = [
    dict(ds='DS_RP_LOGEMENT_PRINC', prefixe='log', titre=T_LOG, mesure='RP_MEASURE',
         ordre=['OCS', 'TDW', 'TSH', 'NOR', 'BUILD_END', 'L_STAY', 'CARS', 'CARPARK', 'NRG_SRC'],
         anciennes_dims=['OCS'], exclure={'NRG_SRC': ['_Z']},
         dims={'OCS': dict(abr='', remplace=True), 'TDW': dict(abr=''), 'TSH': dict(abr=''), 'NOR': dict(abr='pieces'),
               'BUILD_END': dict(abr='constr'), 'L_STAY': dict(abr='emm'), 'CARS': dict(abr=''), 'CARPARK': dict(abr=''),
               'NRG_SRC': dict(abr='chauf')},
         codes={('OCS', 'DW_MAIN'): ('rp', 'résidences principales'),
                ('OCS', 'DW_SEC_DW_OCC'): ('rs', 'résidences secondaires et logements occasionnels'),
                ('OCS', 'DW_VAC'): ('vac', 'logements vacants'),
                ('CARPARK', '1'): ('parking', 'avec au moins un emplacement réservé au stationnement'),
                ('CARPARK', '0'): ('sans_parking', 'sans emplacement réservé au stationnement'),
                **_c('TDW', TDW), **_c('TSH', TSH), **_c('NOR', NOR), **_c('BUILD_END', CONSTR), **_c('L_STAY', EMM),
                **_c('CARS', VOIT), **_c('NRG_SRC', {k: (a, b) for k, (a, b) in CHAUF.items()})},
         mesures={'DWELLINGS': dict(nom='', lib='Logements', unite='logements', defn='Nombre de logements'),
                  'DWELLINGS_POPSIZE': dict(nom='pmen', lib='Population des ménages', unite='habitants',
                                            defn="Nombre d'habitants des résidences principales"),
                  'DWELLINGS_ROOMS': dict(nom='pieces_tot', lib='Nombre total de pièces des résidences principales',
                                          unite='pièces', defn='Nombre total de pièces des résidences principales'),
                  'DWELLING_L_STAY': dict(nom='anciennete_tot', lib="Ancienneté d'emménagement cumulée des ménages",
                                          unite='années', defn="Somme, sur les ménages, des années écoulées depuis "
                                                               "l'emménagement dans la résidence principale")},
         ratios=[*[dict(col=f'log_part_vac_{a}', unite='%', facteur=100, annee=a, num=f'log_vac_{a}', den=f'log_{a}',
                        libelle=f'Part des logements vacants ({a})',
                        definition=f'Logements vacants pour 100 logements, recensement de la population {a}.')
                   for a in ('2012', '2017', '2023')],
                 *[dict(col=f'log_part_rs_{a}', unite='%', facteur=100, annee=a, num=f'log_rs_{a}', den=f'log_{a}',
                        libelle=f'Part des résidences secondaires et logements occasionnels ({a})',
                        definition=f'Résidences secondaires et logements occasionnels pour 100 logements, recensement de la population {a}.')
                   for a in ('2012', '2017', '2023')],
                 *[dict(col=f'log_pieces_moy_{a}', unite='pièces par logement', facteur=1, annee=a,
                        num=f'log_pieces_tot_{a}', den=f'log_rp_{a}', libelle=f'Nombre moyen de pièces des résidences principales ({a})',
                        definition=f'Nombre total de pièces divisé par le nombre de résidences principales, recensement de la population {a}.')
                   for a in ('2012', '2017', '2023')],
                 *[dict(col=f'log_pieces_moy_{t}_2023', unite='pièces par logement', facteur=1, annee='2023',
                        num=f'log_pieces_tot_{t}_2023', den=f'log_rp_{t}_2023',
                        libelle=f'Nombre moyen de pièces des résidences principales, {l} (2023)',
                        definition=f'Nombre total de pièces des {l} divisé par le nombre de résidences principales de ce type, '
                                   'recensement de la population 2023.') for t, l in (('maison', 'maisons'), ('appart', 'appartements'))],
                 dict(col='log_anciennete_moy_2023', unite='années', facteur=1, annee='2023',
                      num='log_anciennete_tot_2023', den='log_rp_2023',
                      libelle="Ancienneté moyenne d'emménagement des ménages (2023)",
                      definition="Années écoulées depuis l'emménagement dans la résidence principale, en moyenne par ménage, "
                                 "recensement de la population 2023."),
                 *[dict(col=f'log_part_{k}_2023', unite='%', facteur=100, annee='2023', num=f'log_rp_{k}_2023', den='log_rp_2023',
                        libelle=f'Part des résidences principales occupées par des {l} (2023)',
                        definition=f'Résidences principales occupées par des {l}, pour 100 résidences principales, '
                                   'recensement de la population 2023.')
                   for k, l in (('proprio', 'ménages propriétaires'), ('loc_hlm', "locataires d'un logement HLM vide du parc social"),
                                ('loc_prive', 'locataires du parc privé (logement vide)'))],
                 dict(col='log_part_maison_2023', unite='%', facteur=100, annee='2023', num='log_maison_2023', den='log_2023',
                      libelle='Part des maisons dans les logements (2023)',
                      definition='Maisons pour 100 logements, recensement de la population 2023.')]),
    dict(ds='DS_RP_LOGEMENT_COMP', prefixe='logc', titre='Logements, indicateurs complémentaires (dossier complet)',
         mesure='RP_MEASURE', dims={'OCC_IND': dict(abr='', colle=True)}, codes=_c('OCC_IND', PEUPL),
         mesures={'DWELLINGS': dict(RP, note="L'indice de peuplement compare le nombre de pièces du logement au nombre de "
                                              "pièces jugé nécessaire au ménage (une pièce de séjour, une pièce par couple, "
                                              "par adulte ou par paire d'enfants selon l'âge et le sexe).")}),
    dict(ds='DS_RP_TD_LOGEMENT_AGE_PRINC', prefixe='lage',
         titre="Caractéristiques des résidences principales selon l'âge de la personne de référence, données détaillées (PRINC)",
         mesure='RP_MEASURE', ordre=['AGE', 'TDW', 'TSH', 'NOR'], exclure={'AGE': ['Y_LT15']},
         dims={'AGE': dict(abr='age', tpl='personne de référence {lib}'), 'TDW': dict(abr=''), 'TSH': dict(abr=''),
               'NOR': dict(abr='pieces')},
         codes={**_c('AGE', AGE_PR), **_c('TDW', TDW), **_c('TSH', TSH), **_c('NOR', NOR)},
         mesures={'DWELLINGS': dict(RP)}),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'logement'."""
    return [mc.assembler('logement', [mc.traiter(j, cache) for j in JEUX])]
