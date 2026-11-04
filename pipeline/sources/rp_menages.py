# -*- coding: utf-8 -*-
"""Ménages et familles des communes (recensement 2023, rappels 2012 et 2017) et nombre de ménages par profil de
besoin en logement (Insee, Melodi).

Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_MENAGES_PRINC, DS_RP_MENAGES_COMP, DS_RP_FAMILLE_COMP,
DS_RP_TD_MENAGES_TPH_COMP (tableaux MEN5 et MEN6 : type de ménage x âge de la personne de référence),
DS_RP_TD_MENAGES_NOC_COMP (MEN4 : taille du ménage x sexe x âge de la personne de référence) ; pour les profils,
aussi DS_RP_TD_LOGEMENT_AGE_PRINC et DS_RP_MIGRES_PRINC.

Bloc 'population' : dernière année de chaque série ; 2012 et 2017 seulement pour les totaux ; au plus deux dimensions
hors total. Écarté : MEN4 croisé taille x sexe x âge (168 séries). Les totaux identiques d'un tableau à l'autre
(nombre de ménages, population des ménages) ne sont gardés qu'une fois.

Bloc 'besoins' : nombre de ménages pour les profils de l'annexe « Profils » (Annexe_base_unique_croisements.xlsx)
comptables avec les tableaux détaillés diffusés. L'approximation exacte figure dans la définition de chaque colonne.
Profils non comptés : « Ménage modeste éligible à l'accession sociale » (critère de revenu, absent du recensement ;
Filosofi ne diffuse pas de déciles par commune et par profil) et « Investisseur particulier » (aucune statistique
locale). Les critères d'emploi, de statut d'occupation, de taille de logement et de revenu ne sont jamais croisés à la
fois avec l'âge et le type de ménage dans les tableaux diffusés : les profils restent des approximations.
"""
from pathlib import Path
import pandas as pd
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'P2-019',
          'nom': "Recensement de la population 2023 : ménages, familles, tableaux détaillés MEN4, MEN5 et MEN6 "
                 "(base Couples, familles, ménages) ; autres fiches : E6-13, E6-15, E7-55, P2-001",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_TD_MENAGES_TPH_COMP',
          'telechargement': 'https://api.insee.fr/melodi/file/<jeu>/<jeu>_2023_CSV_FR (zips CSV Melodi : DS_RP_MENAGES_PRINC, '
                            'DS_RP_MENAGES_COMP, DS_RP_FAMILLE_COMP, DS_RP_TD_MENAGES_TPH_COMP, DS_RP_TD_MENAGES_NOC_COMP, '
                            'DS_RP_TD_LOGEMENT_AGE_PRINC, DS_RP_MIGRES_PRINC)',
          'millesime': 'Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017',
          'licence': 'Licence ouverte 2.0'}

TPH = {'11': ('1p', "d'une personne seule"), '110': ('homme_seul', "d'un homme seul"),
       '111': ('femme_seule', "d'une femme seule"), '12': ('sansfam', 'de plusieurs personnes sans famille'),
       '2': ('fam', 'comprenant une famille'), 'MF21': ('monop', "d'une famille monoparentale"),
       'MF211': ('monop_pere', "d'une famille monoparentale, père avec enfant(s)"),
       'MF212': ('monop_mere', "d'une famille monoparentale, mère avec enfant(s)"),
       'MF22': ('couple', "d'un couple avec ou sans enfant"), 'MF221': ('couple_sans_enf', "d'un couple sans enfant"),
       'MF222': ('couple_avec_enf', "d'un couple avec enfant(s)"),
       'A211': ('couple_h_actif_conj_inactif', "d'un couple, homme actif et conjoint inactif"),
       'A221': ('couple_f_active_conj_inactif', "d'un couple, femme active et conjoint inactif"),
       'A231': ('couple_2_actifs_occ', "d'un couple de deux actifs occupés"),
       'A24': ('couple_sans_actif', "d'un couple sans actif")}
PCS_PR = {'1': ('agri', 'personne de référence agriculteur exploitant'),
          '2': ('artcom', "personne de référence artisan, commerçant ou chef d'entreprise"),
          '3': ('cadres', 'personne de référence cadre ou profession intellectuelle supérieure'),
          '4': ('profint', 'personne de référence de profession intermédiaire'),
          '5': ('employes', 'personne de référence employé'), '6': ('ouvriers', 'personne de référence ouvrier'),
          '7': ('retraites', 'personne de référence retraitée'),
          '9': ('inactifs', 'personne de référence sans activité professionnelle (hors retraités)')}
AGE_PR = {'Y_LT20': ('0_19', 'personne de référence de moins de 20 ans'),
          'Y_GE80': ('80p', 'personne de référence de 80 ans ou plus'),
          'Y_LT15': ('0_14', 'personne de référence de moins de 15 ans')}
MENAGES = dict(nom='', lib='Ménages', unite='ménages', defn='Nombre de ménages',
               note="Un ménage regroupe les occupants d'une résidence principale.")
POP_MEN = dict(nom='pmen', lib='Population des ménages', unite='habitants', defn="Nombre d'habitants vivant dans un ménage")

JEUX = [
    dict(ds='DS_RP_MENAGES_PRINC', prefixe='men', titre='Ménages et couples, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['COUPLE', 'CIVIL_STATUS', 'AGE'], totaux={'AGE': 'Y_GE15'},
         dims={'COUPLE': dict(abr=''), 'CIVIL_STATUS': dict(abr='statut'), 'AGE': dict(abr='age', lib_total='15 ans ou plus')},
         codes={('COUPLE', '0'): ('hors_couple', 'ne vivant pas en couple'), ('COUPLE', '1'): ('couple', 'vivant en couple'),
                ('CIVIL_STATUS', '1'): ('marie', 'marié(e)'), ('CIVIL_STATUS', '2'): ('pacse', 'pacsé(e)'),
                ('CIVIL_STATUS', '3'): ('concubinage', 'en concubinage ou union libre'),
                ('CIVIL_STATUS', '4'): ('veuf', 'veuf ou veuve'), ('CIVIL_STATUS', '5'): ('divorce', 'divorcé(e)'),
                ('CIVIL_STATUS', '6'): ('celib', 'célibataire')},
         mesures={'POP': dict(nom='pop', lib='Population', unite='habitants', defn="Nombre d'habitants"),
                  'DWELLINGS_POPSIZE': dict(POP_MEN),
                  'ONEPERS': dict(nom='seuls', lib='Personnes vivant seules', unite='habitants',
                                  defn='Nombre de personnes vivant seules dans leur logement')},
         ratios=[dict(col=f'men_part_seuls_age_{k}_2023', unite='%', facteur=100, annee='2023',
                      libelle=f'Part des personnes vivant seules parmi les habitants des ménages de {t} (2023)',
                      definition=f'Personnes de {t} vivant seules, pour 100 habitants des ménages de {t}, '
                                 'recensement de la population 2023.', num=f'men_seuls_age_{k}_2023', den=f'men_pmen_age_{k}_2023')
                 for k, t in (('65_79', '65 à 79 ans'), ('80p', '80 ans ou plus'))]),
    dict(ds='DS_RP_MENAGES_COMP', prefixe='menc', titre='Ménages, indicateurs complémentaires (dossier complet)',
         mesure='RP_MEASURE', ordre=['TPH', 'PCS'], dims={'TPH': dict(abr='', colle=True), 'PCS': dict(abr='pcs')},
         codes={**{('TPH', k): v for k, v in TPH.items()}, **{('PCS', k): v for k, v in PCS_PR.items()}},
         mesures={'DWELLINGS': dict(MENAGES), 'DWELLINGS_POPSIZE': dict(POP_MEN)},
         ratios=[dict(col=f'menc_taille_moy_{a}', unite='personnes par ménage', facteur=1, annee=a,
                      libelle=f'Nombre moyen de personnes par ménage ({a})',
                      definition=f'Population des ménages divisée par le nombre de ménages, recensement de la population {a}.',
                      num=f'menc_pmen_{a}', den=f'menc_{a}') for a in ('2012', '2017', '2023')]),
    dict(ds='DS_RP_FAMILLE_COMP', prefixe='fam', titre='Familles, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', dims={'TFN': dict(abr='', colle=True), 'NCH': dict(abr='enf', colle=True)},
         codes={('TFN', '1'): ('monop', 'monoparentales'), ('TFN', '11'): ('monop_pere', 'monoparentales, père avec enfant(s)'),
                ('TFN', '12'): ('monop_mere', 'monoparentales, mère avec enfant(s)'),
                ('TFN', '21'): ('couple_sans_enf', "d'un couple sans enfant résidant avec lui"),
                ('TFN', '22'): ('couple_avec_enf', "d'un couple avec enfant(s) résidant avec lui"),
                ('TFN', '220'): ('recomposees', 'recomposées'), ('TFN', '223'): ('traditionnelles', 'traditionnelles'),
                ('NCH', 'CH0_Y_LT25'): ('0', 'sans enfant de moins de 25 ans'),
                ('NCH', 'CH1_Y_LT25'): ('1', 'avec 1 enfant de moins de 25 ans'),
                ('NCH', 'CH2_Y_LT25'): ('2', 'avec 2 enfants de moins de 25 ans'),
                ('NCH', 'CH3_Y_LT25'): ('3', 'avec 3 enfants de moins de 25 ans'),
                ('NCH', 'CH_GE4_Y_LT25'): ('4p', 'avec 4 enfants ou plus de moins de 25 ans')},
         mesures={'NBFAM': dict(nom='', lib='Familles', unite='familles', defn='Nombre de familles')}),
    dict(ds='DS_RP_TD_MENAGES_TPH_COMP', prefixe='mtph',
         titre="Ménages selon l'âge de la personne de référence et le type de ménage, données détaillées (MEN5 et MEN6)",
         mesure='RP_MEASURE', ordre=['TPH', 'AGE'],
         dims={'TPH': dict(abr='', colle=True), 'AGE': dict(abr='age', tpl='personne de référence {lib}')},
         codes={**{('TPH', k): v for k, v in TPH.items()}, **{('AGE', k): v for k, v in AGE_PR.items()}},
         mesures={'DWELLINGS': dict(MENAGES), 'DWELLINGS_POPSIZE': dict(POP_MEN)}),
    dict(ds='DS_RP_TD_MENAGES_NOC_COMP', prefixe='mnoc',
         titre='Ménages selon la taille du ménage, données détaillées (MEN4)',
         mesure='RP_MEASURE', ordre=['NOC', 'SEX', 'AGE'],
         dims={'NOC': dict(abr='', colle=True), 'SEX': dict(abr=''), 'AGE': dict(abr='age', tpl='personne de référence {lib}')},
         codes={('NOC', 'P1'): ('1pers', "d'une personne"), ('NOC', 'P2'): ('2pers', 'de 2 personnes'),
                ('NOC', 'P3'): ('3pers', 'de 3 personnes'), ('NOC', 'P4'): ('4pers', 'de 4 personnes'),
                ('NOC', 'P5'): ('5pers', 'de 5 personnes'), ('NOC', 'P_GE6'): ('6pers_p', 'de 6 personnes ou plus'),
                ('SEX', 'F'): ('pr_femme', 'personne de référence femme'), ('SEX', 'M'): ('pr_homme', 'personne de référence homme'),
                **{('AGE', k): v for k, v in AGE_PR.items()}},
         mesures={'DWELLINGS': dict(MENAGES)}),
]

TPH_DS, NOC_DS, LAGE_DS, MIG_DS = ('DS_RP_TD_MENAGES_TPH_COMP', 'DS_RP_TD_MENAGES_NOC_COMP',
                                   'DS_RP_TD_LOGEMENT_AGE_PRINC', 'DS_RP_MIGRES_PRINC')
TITRES = {TPH_DS: "Ménages selon l'âge de la personne de référence et le type de ménage, données détaillées (MEN5 et MEN6)",
          NOC_DS: 'Ménages selon la taille du ménage, données détaillées (MEN4)',
          LAGE_DS: "Caractéristiques des résidences principales selon l'âge de la personne de référence, données détaillées",
          MIG_DS: 'Migrations résidentielles, principaux indicateurs (dossier complet)'}
D = {'RP_MEASURE': ['DWELLINGS']}
# (colonne, profil de l'annexe, jeu, cellules sommées, unité, approximation)
PROFILS = [
    ('prof_jeune_seul_2023', 'Jeune actif seul', NOC_DS, {**D, 'NOC': ['P1'], 'AGE': ['Y20T24', 'Y25T29', 'Y30T34']}, 'ménages',
     "Ménages d'une personne dont la personne de référence a de 20 à 34 ans. L'emploi et le statut d'occupation "
     "(locataire, logé gratuitement) ne sont pas croisés avec l'âge et la taille du ménage dans les tableaux diffusés : "
     "le nombre comprend donc aussi les personnes seules sans emploi et les propriétaires."),
    ('prof_couple_sans_enf_2023', 'Couple primo-accédant sans enfant', NOC_DS,
     {**D, 'NOC': ['P2'], 'AGE': ['Y25T29', 'Y30T34', 'Y35T39']}, 'ménages',
     "Ménages de 2 personnes dont la personne de référence a de 25 à 39 ans, pris comme approximation des couples sans "
     "enfant (le type de ménage n'est pas croisé avec ces tranches d'âge ; le nombre comprend aussi des parents seuls "
     "avec un enfant et des colocations de 2 personnes). Statut de locataire et emploi des deux conjoints non croisés."),
    ('prof_famille_enf_2023', 'Famille avec enfants (couple, premier achat ou agrandissement)', NOC_DS,
     {**D, 'NOC': ['P3', 'P4', 'P5', 'P_GE6'], 'AGE': ['Y30T34', 'Y35T39', 'Y40T44']}, 'ménages',
     "Ménages de 3 personnes ou plus dont la personne de référence a de 30 à 44 ans, pris comme approximation des couples "
     "avec enfant(s) (le nombre comprend aussi des familles monoparentales d'au moins 2 enfants et quelques ménages sans "
     "enfant). Statut d'occupation, nombre de pièces et surpeuplement non croisés avec l'âge et la taille du ménage."),
    ('prof_monop_2023', 'Famille monoparentale', TPH_DS, {**D, 'TPH': ['MF21'], 'AGE': ['Y25T39', 'Y40T54']}, 'ménages',
     "Ménages dont la famille principale est monoparentale et dont la personne de référence a de 25 à 54 ans. "
     "Statut d'occupation non croisé."),
    ('prof_secundo_2023', 'Secundo-accédant', LAGE_DS, {**D, 'TSH': ['100'], 'AGE': ['Y40T54']}, 'ménages',
     "Ménages propriétaires de leur résidence principale dont la personne de référence a de 40 à 54 ans (tranche "
     "diffusée la plus proche des 35 à 59 ans du profil). Nombre de pièces et revenu non croisés avec le statut et l'âge ; "
     "le recensement ne dit pas si le ménage projette de revendre : c'est un vivier, pas une demande."),
    ('prof_senior_6074_2023', 'Senior autonome de 60 à 74 ans', NOC_DS,
     {**D, 'NOC': ['P1', 'P2'], 'AGE': ['Y60T64', 'Y65T69', 'Y70T74']}, 'ménages',
     "Ménages d'une ou deux personnes dont la personne de référence a de 60 à 74 ans. Statut de propriétaire et taille "
     "du logement non croisés (voir prof_senior_grande_maison_2023)."),
    ('prof_senior_grande_maison_2023', 'Senior autonome de 60 à 74 ans, en maison de 5 pièces ou plus', LAGE_DS,
     {**D, 'TDW': ['1'], 'NOR': ['R5', 'R_GE6'], 'AGE': ['Y65T79']}, 'ménages',
     "Ménages occupant une maison de 5 pièces ou plus dont la personne de référence a de 65 à 79 ans (tranche diffusée "
     "la plus proche des 60 à 74 ans). Statut de propriétaire et nombre de personnes non croisés avec ces critères."),
    ('prof_grand_age_2023', 'Grand âge (75 ans et plus)', NOC_DS, {**D, 'AGE': ['Y75T79', 'Y_GE80']}, 'ménages',
     'Ménages dont la personne de référence a 75 ans ou plus.'),
    ('prof_grand_age_seul_2023', 'Grand âge (75 ans et plus), personne seule', NOC_DS,
     {**D, 'NOC': ['P1'], 'AGE': ['Y75T79', 'Y_GE80']}, 'ménages',
     "Ménages d'une personne de 75 ans ou plus. Statut de propriétaire et ancienneté de la maison non croisés."),
    ('prof_etudiant_2023', 'Étudiant', TPH_DS, {**D, 'TPH': ['11', '12'], 'AGE': ['Y_LT20', 'Y20T24']}, 'ménages',
     "Ménages d'une personne ou de plusieurs personnes sans famille (colocations) dont la personne de référence a moins "
     "de 25 ans. La qualité d'élève ou d'étudiant et le statut de locataire ne sont pas croisés : le nombre comprend de "
     "jeunes actifs, et pas les étudiants logés chez leurs parents."),
    ('prof_mobilite_2023', 'Salarié en mobilité ou arrivant dans un bassin industriel', MIG_DS,
     {'AGE': ['Y25T54'], 'PREV_RES_AREA': ['20_30']}, 'habitants',
     "Habitants de 25 à 54 ans qui résidaient dans une autre commune un an auparavant (des personnes, pas des ménages). "
     "La situation d'emploi n'est pas croisée avec la migration dans les tableaux diffusés."),
    ('prof_locataire_social_2023', 'Locataire durable du parc social ou intermédiaire', LAGE_DS, {**D, 'TSH': ['221']},
     'ménages', "Ménages locataires d'un logement vide du parc social (HLM) : parc social occupé. La demande en attente "
                "(SNE) et le locatif intermédiaire ne sont pas couverts par le recensement."),
]


def profils(cache):
    """Bloc 'besoins' : nombre de ménages (ou d'habitants) par profil, approximations décrites dans les définitions."""
    ref = geo.referentiel().CODGEO
    data = pd.DataFrame({'CODGEO': ref.to_numpy()})
    inds = []
    for col, profil, ds, sel, unite, approx in PROFILS:
        s = mc.somme_cellules(ds, cache, sel)
        if s is None: continue
        data[col] = s.reindex(ref.to_numpy()).to_numpy()
        inds.append({'col': col, 'libelle': f'Profil {profil} (2023)', 'unite': unite,
                     'definition': mc.propre(approx) + f' Recensement de la population 2023. Source : Insee, {mc.propre(TITRES[ds])}.',
                     'agregation': 'somme', 'annee': '2023'})
    return {'theme': 'besoins', 'data': data, 'indicateurs': inds}


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) ; renvoie un bloc 'population' (ménages,
    familles) et un bloc 'besoins' (profils)."""
    return [mc.assembler('population', [mc.traiter(j, cache) for j in JEUX]), profils(cache)]
