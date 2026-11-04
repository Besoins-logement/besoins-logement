# -*- coding: utf-8 -*-
"""Emploi et actifs des communes : activité et chômage des habitants, emplois au lieu de travail, statut et
conditions d'emploi, diplômes, scolarisation, déplacements domicile-travail (recensement 2023, rappels 2012 et 2017 ;
Insee, Melodi).

Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_EMPLOI_LR_PRINC, DS_RP_EMPLOI_LR_COMP, DS_RP_EMPLOI_LT_PRINC,
DS_RP_ACTIVITE_PRINC, DS_RP_DIPLOMES_PRINC, DS_RP_EDUCATION_PRINC, DS_RP_NAVETTES_PRINC. Les migrations
résidentielles (DS_RP_MIGRES_PRINC) sont dans rp_population (thème population).

Règles : dernière année de chaque série ; 2012 et 2017 seulement pour les totaux ; au plus deux dimensions hors total.
Totaux d'âge retenus : 15 à 64 ans pour l'activité et le chômage, 15 ans ou plus pour les actifs occupés, 2 ans ou plus
pour la scolarisation. Écartés (trois dimensions ou plus) : activité x sexe x âge et activité x âge x diplôme par
tranche d'âge (seuls les totaux 15-64 ans ou 15 ans ou plus de ces croisements sont gardés) ; actifs occupés croisés par
trois ou quatre de temps de travail, sexe, âge et statut ; scolarisation âge x sexe x inscription. Les taux (chômage,
activité, emploi, concentration de l'emploi, parts) sont des ratios recalculés à partir des effectifs.
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'E7-55',
          'nom': "Recensement de la population 2023 (dossier complet) : population active et chômage, emploi au lieu de "
                 "travail, caractéristiques de l'emploi, diplômes, scolarisation, déplacements domicile-travail ; "
                 "autres fiches : E4-18, P2-001",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_EMPLOI_LR_PRINC',
          'telechargement': 'https://api.insee.fr/melodi/file/<jeu>/<jeu>_2023_CSV_FR (zips CSV Melodi : DS_RP_EMPLOI_LR_PRINC, '
                            'DS_RP_EMPLOI_LR_COMP, DS_RP_EMPLOI_LT_PRINC, DS_RP_ACTIVITE_PRINC, DS_RP_DIPLOMES_PRINC, '
                            'DS_RP_EDUCATION_PRINC, DS_RP_NAVETTES_PRINC)',
          'millesime': 'Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017',
          'licence': 'Licence ouverte 2.0'}

def _c(dim, d): return {(dim, k): v for k, v in d.items()}

STATUT = {'1': ('occ', 'actifs occupés'), '1T2': ('actifs', 'actifs'), '2': ('chom', 'chômeurs'), '3': ('inact', 'inactifs'),
          '31': ('retraites', 'retraités ou préretraités'), '33': ('etud', 'élèves, étudiants et stagiaires non rémunérés'),
          '35': ('foyer', 'femmes ou hommes au foyer'), '35T36': ('autres_inact', 'autres inactifs (y compris au foyer)'),
          '36': ('autres_inact_hors_foyer', 'autres inactifs (hors personnes au foyer)')}
DIPL = {'001T100_RP': ('aucun', "sans diplôme ou avec le certificat d'études primaires"),
        '200_RP': ('bepc', 'diplôme le plus élevé : BEPC, brevet des collèges ou DNB'),
        '300_RP': ('cap_bep', 'diplôme le plus élevé : CAP, BEP ou équivalent'),
        '350T351_RP': ('bac', 'diplôme le plus élevé : baccalauréat, brevet professionnel ou équivalent'),
        '500_RP': ('sup_court', "diplôme le plus élevé : diplôme de l'enseignement supérieur court (bac + 2)"),
        '600_RP': ('licence', 'diplôme le plus élevé : licence ou équivalent (bac + 3 ou 4)'),
        '700_RP': ('bac5', 'diplôme le plus élevé : bac + 5 ou plus'),
        '500T702_RP': ('sup', "diplôme le plus élevé : diplôme de l'enseignement supérieur"),
        '600T702_RP': ('sup_long', "diplôme le plus élevé : diplôme de l'enseignement supérieur long (bac + 3 ou plus)")}
PCS = {'1': ('agri', 'agriculteurs exploitants'), '2': ('artcom', "artisans, commerçants et chefs d'entreprise"),
       '3': ('cadres', 'cadres et professions intellectuelles supérieures'), '4': ('profint', 'professions intermédiaires'),
       '5': ('employes', 'employés'), '6': ('ouvriers', 'ouvriers')}
TPS = {'FT': ('tps_complet', 'à temps complet'), 'PT': ('tps_partiel', 'à temps partiel')}
FORME = {'1': ('non_salaries', 'non salariés'), '2': ('salaries', 'salariés'),
         '211': ('cdi', 'salariés en emploi sans limite de durée (CDI, fonctionnaires)'),
         '22T27': ('cdd_interim', 'salariés en contrat à durée limitée (CDD, intérim, apprentissage, stage, emploi aidé)')}
HAB = dict(nom='', lib='Population', unite='habitants', defn="Nombre d'habitants")

JEUX = [
    dict(ds='DS_RP_EMPLOI_LR_PRINC', prefixe='emp', titre='Population active et chômage, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['EMPSTA_ENQ', 'SEX', 'AGE', 'EDUC'], totaux={'AGE': 'Y15T64'},
         dims={'EMPSTA_ENQ': dict(abr='', remplace=True), 'SEX': dict(abr=''),
               'AGE': dict(abr='age', lib_total='de 15 à 64 ans'), 'EDUC': dict(abr='dipl')},
         codes={**_c('EMPSTA_ENQ', STATUT), **_c('EDUC', DIPL)}, mesures={'POP': dict(HAB)}),
    dict(ds='DS_RP_EMPLOI_LR_COMP', prefixe='empc', titre='Population active et chômage, indicateurs complémentaires (dossier complet)',
         mesure='RP_MEASURE', ordre=['EMPSTA_ENQ', 'PCS'], totaux={'EMPSTA_ENQ': '1T2'},
         dims={'EMPSTA_ENQ': dict(abr='', remplace=True), 'PCS': dict(abr='pcs')},
         codes={('EMPSTA_ENQ', '1'): ('occ', 'actifs occupés de 15 à 64 ans'), ('EMPSTA_ENQ', '2'): ('chom', 'chômeurs de 15 à 64 ans'),
                **_c('PCS', PCS)},
         mesures={'POP': dict(nom='', lib='Actifs de 15 à 64 ans', unite='habitants', defn="Nombre d'actifs de 15 à 64 ans")}),
    dict(ds='DS_RP_EMPLOI_LT_PRINC', prefixe='emplt', titre='Emploi au lieu de travail, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['SEX', 'WKTIME', 'EMPFORM', 'AGE'],
         dims={'SEX': dict(abr=''), 'WKTIME': dict(abr=''), 'EMPFORM': dict(abr=''), 'AGE': dict(abr='age')},
         codes={**_c('WKTIME', TPS), **_c('EMPFORM', FORME), ('AGE', 'Y_GE15'): ('15p', 'occupés par des personnes de 15 ans ou plus')},
         mesures={'NBEMP': dict(nom='', lib='Emplois au lieu de travail', unite='emplois',
                                defn="Nombre d'emplois situés dans la commune (lieu de travail)")}),
    dict(ds='DS_RP_ACTIVITE_PRINC', prefixe='actocc', titre="Caractéristiques de l'emploi, principaux indicateurs (dossier complet)",
         mesure='RP_MEASURE', ordre=['EMPFORM', 'WKTIME', 'SEX', 'AGE'], totaux={'AGE': 'Y_GE15'},
         dims={'EMPFORM': dict(abr=''), 'WKTIME': dict(abr=''), 'SEX': dict(abr=''), 'AGE': dict(abr='age', lib_total='15 ans ou plus')},
         codes={**_c('WKTIME', TPS), **_c('EMPFORM', FORME)},
         mesures={'POP': dict(nom='', lib='Actifs occupés', unite='habitants',
                              defn="Nombre d'habitants ayant un emploi (actifs occupés)")}),
    dict(ds='DS_RP_DIPLOMES_PRINC', prefixe='dipl', titre='Diplômes et formation, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['SEX', 'EDUC'], dims={'SEX': dict(abr=''), 'EDUC': dict(abr='')}, codes=_c('EDUC', DIPL),
         mesures={'POP': dict(nom='', lib='Population non scolarisée de 15 ans ou plus', unite='habitants',
                              defn="Nombre d'habitants de 15 ans ou plus non scolarisés")}),
    dict(ds='DS_RP_EDUCATION_PRINC', prefixe='scol', titre='Éducation et scolarisation, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['AGE', 'SEX', 'STUD'], totaux={'AGE': 'Y_GE2'},
         dims={'AGE': dict(abr='age', lib_total='2 ans ou plus'), 'SEX': dict(abr=''), 'STUD': dict(abr='')},
         codes={('STUD', '1'): ('inscrits', "inscrits dans un établissement d'enseignement"),
                ('STUD', '0'): ('non_inscrits', "non inscrits dans un établissement d'enseignement")},
         mesures={'POP': dict(HAB)}),
    dict(ds='DS_RP_NAVETTES_PRINC', prefixe='nav', titre='Déplacements domicile-travail, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['WORK_AREA', 'TRANS'], dims={'WORK_AREA': dict(abr='lieu'), 'TRANS': dict(abr='mode')},
         codes={('WORK_AREA', '10'): ('meme_com', 'travaillant dans leur commune de résidence'),
                ('WORK_AREA', '20_30'): ('autre_com', 'travaillant dans une autre commune'),
                ('WORK_AREA', '21'): ('autre_com_dep', 'travaillant dans une autre commune du département'),
                ('WORK_AREA', '22'): ('autre_dep_reg', 'travaillant dans un autre département de la région'),
                ('WORK_AREA', '23'): ('autre_reg', 'travaillant dans une autre région de métropole'),
                ('WORK_AREA', '24T30'): ('hors_metro', "travaillant hors de la métropole (outre-mer ou étranger)"),
                ('TRANS', '1'): ('aucun', 'sans transport (travail à domicile)'), ('TRANS', '2'): ('marche', 'allant au travail à pied'),
                ('TRANS', '3'): ('velo', 'allant au travail à vélo'), ('TRANS', '3T4'): ('deux_roues', 'allant au travail en deux-roues'),
                ('TRANS', '4'): ('deux_roues_mot', 'allant au travail en deux-roues motorisé'),
                ('TRANS', '5'): ('voiture', 'allant au travail en voiture, camion ou fourgonnette'),
                ('TRANS', '6'): ('tc', 'allant au travail en transports en commun')},
         mesures={'POP': dict(nom='', lib='Actifs occupés de 15 ans ou plus', unite='habitants',
                              defn="Nombre d'habitants de 15 ans ou plus ayant un emploi")}),
]

def _r(col, num, den, lib, defn, facteur=100, unite='%'):
    return dict(col=col, num=num, den=den, libelle=lib, definition=defn, facteur=facteur, unite=unite, annee='2023')

RP23 = 'recensement de la population 2023.'
RATIOS = [
    _r('emp_tx_chom_2023', 'emp_chom_2023', 'emp_actifs_2023', 'Taux de chômage des 15 à 64 ans (2023)',
       f'Chômeurs de 15 à 64 ans pour 100 actifs de 15 à 64 ans (au sens du recensement), {RP23}'),
    _r('emp_tx_chom_age_15_24_2023', 'emp_chom_age_15_24_2023', 'emp_actifs_age_15_24_2023', 'Taux de chômage des 15 à 24 ans (2023)',
       f'Chômeurs de 15 à 24 ans pour 100 actifs de 15 à 24 ans (au sens du recensement), {RP23}'),
    _r('emp_tx_act_2023', 'emp_actifs_2023', 'emp_2023', "Taux d'activité des 15 à 64 ans (2023)",
       f'Actifs de 15 à 64 ans pour 100 habitants de 15 à 64 ans, {RP23}'),
    _r('emp_tx_emploi_2023', 'emp_occ_2023', 'emp_2023', "Taux d'emploi des 15 à 64 ans (2023)",
       f'Actifs occupés de 15 à 64 ans pour 100 habitants de 15 à 64 ans, {RP23}'),
    _r('emplt_concentration_2023', 'emplt_2023', 'actocc_2023', "Indicateur de concentration d'emploi (2023)",
       f"Emplois situés dans la commune pour 100 actifs occupés de 15 ans ou plus qui y résident, {RP23}"),
    _r('actocc_part_cdd_interim_2023', 'actocc_cdd_interim_2023', 'actocc_salaries_2023',
       'Part des salariés en contrat à durée limitée (2023)',
       f'Salariés en CDD, intérim, apprentissage, stage ou emploi aidé pour 100 salariés de 15 ans ou plus résidant dans la commune, {RP23}'),
    _r('actocc_part_tps_partiel_2023', 'actocc_tps_partiel_2023', 'actocc_2023', 'Part des actifs occupés à temps partiel (2023)',
       f'Actifs occupés de 15 ans ou plus à temps partiel pour 100 actifs occupés de 15 ans ou plus, {RP23}'),
    _r('dipl_part_sup_2023', 'dipl_sup_2023', 'dipl_2023', "Part des diplômés de l'enseignement supérieur (2023)",
       f"Personnes non scolarisées de 15 ans ou plus diplômées de l'enseignement supérieur pour 100 personnes non scolarisées de 15 ans ou plus, {RP23}"),
    _r('dipl_part_aucun_2023', 'dipl_aucun_2023', 'dipl_2023', 'Part des personnes sans diplôme (2023)',
       f"Personnes non scolarisées de 15 ans ou plus sans diplôme ou avec le certificat d'études primaires pour 100 personnes non scolarisées de 15 ans ou plus, {RP23}"),
    _r('nav_part_autre_com_2023', 'nav_lieu_autre_com_2023', 'nav_2023', 'Part des actifs occupés travaillant dans une autre commune (2023)',
       f'Actifs occupés de 15 ans ou plus travaillant hors de leur commune de résidence pour 100 actifs occupés de 15 ans ou plus, {RP23}'),
    _r('nav_part_voiture_2023', 'nav_mode_voiture_2023', 'nav_2023', 'Part des actifs occupés allant travailler en voiture (2023)',
       f'Actifs occupés de 15 ans ou plus allant au travail en voiture, camion ou fourgonnette pour 100 actifs occupés de 15 ans ou plus, {RP23}'),
    _r('nav_part_tc_2023', 'nav_mode_tc_2023', 'nav_2023', 'Part des actifs occupés allant travailler en transports en commun (2023)',
       f'Actifs occupés de 15 ans ou plus allant au travail en transports en commun pour 100 actifs occupés de 15 ans ou plus, {RP23}'),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'emploi'."""
    return [mc.assembler('emploi', [mc.traiter(j, cache) for j in JEUX], ratios=RATIOS,
                         titre_ratios='recensement de la population 2023 (dossier complet)')]
