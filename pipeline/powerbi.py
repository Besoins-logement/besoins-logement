# -*- coding: utf-8 -*-
"""Fichiers légers pour la restitution Power BI : docs/data/powerbi/.

Lancé par run_all.py juste après assembler.py (ou seul : python pipeline/powerbi.py). Lit la base publiée (docs/data/*.parquet)
et écrit, pour les niveaux France, Région, Département, Zone d'emploi et EPCI seulement :
  territoires      une ligne par territoire : id, niveau, hiérarchie, parent de comparaison, nombre de communes
  indicateurs      table large : id puis les indicateurs du rapport sous des noms stables (sans année)
  besoins_periode  table longue : id, période, besoin et ses composantes
  series           table longue : id, série, année, valeur
  repartitions     table longue : id, répartition, modalité, ordre, valeur (toutes les barres empilées ou groupées)
  meta             date de mise à jour de la base et millésime de chaque source utilisée
  correspondance   nom stable -> colonne de la base, thème, millésime, libellés, définition, source
Format : CSV point-virgule, décimale point, UTF-8 sans BOM, compressé en gzip (fichier .csv.gz), comme les autres CSV de la base.

Noms stables : les requêtes Power Query et les mesures DAX ne lisent que les noms stables. À une nouvelle édition d'une source,
seule la table de correspondance ci-dessous change (colonne de la base et millésime).

Garde-fous (le programme s'arrête en erreur et run_all.py ne publie rien) : une colonne de la base citée dans la correspondance
manque ; un identifiant de territoire est en double ; la règle de classe par période ne redonne pas bes_classe_3040."""
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd

RACINE = Path(__file__).resolve().parents[1]
PUB = RACINE / 'docs' / 'data'
SORTIE = PUB / 'powerbi'

# Niveaux du rapport : libellé de la base -> (préfixe de l'identifiant, ordre, libellé court pour la recherche)
NIVEAUX = {'France': ('FR', 1, ''), 'Région': ('REG', 2, 'région'), 'Département': ('DEP', 3, 'département'),
           "Zone d'emploi": ('ZE', 4, "zone d'emploi"), 'EPCI': ('EPCI', 5, 'EPCI')}
PERIODES = {'2030': '2020-2030', '3040': '2030-2040', '4050': '2040-2050'}

# ---------------------------------------------------------------------------------------------------------------------
# Table de correspondance. Une ligne : (nom stable, colonne(s) de la base, thème, millésime, libellé court).
# Une colonne peut être une formule simple « a + b - c » (somme ou différence de colonnes de la base) ; une formule vaut
# vide si l'une des colonnes est vide. Le libellé du rapport = libellé court + millésime (par exemple « Population 2023 »).
# ---------------------------------------------------------------------------------------------------------------------

INDICATEURS = [
    # Besoin en logement (bloc 1 de la base)
    ('construction_actuelle', 'bes_construction_actuelle', 'besoins', '2023-2025', 'Construction actuelle'),
    ('stock_mal_logement', 'bes_stock_mal_logement', 'besoins', '2021', 'Stock de mal-logement'),
    ('manque_2030_2040', 'bes_manque_3040', 'besoins', '2030-2040', 'Logements manquants par an'),
    ('couverture_2030_2040', 'bes_couverture_3040', 'besoins', '2030-2040', 'Taux de couverture'),
    ('classe_2030_2040', 'bes_classe_3040', 'besoins', '2030-2040', 'Classe de conclusion'),
    ('conclusion_2030_2040', 'bes_conclusion_3040', 'besoins', '2030-2040', 'Conclusion'),
    # Population et ménages
    ('population', 'pop_2023', 'population', '2023', 'Population'),
    ('population_debut', 'pop_2017', 'population', '2017', 'Population'),
    ('population_1an_plus', 'migr_2023', 'population', '2023', 'Population de 1 an ou plus'),
    ('arrivants', 'migr_ante_autre_com_2023', 'population', '2023', 'Habitants arrivés d\'une autre commune en un an'),
    ('menages', 'menc_2023', 'menages', '2023', 'Ménages'),
    ('menages_milieu', 'menc_2017', 'menages', '2017', 'Ménages'),
    ('menages_debut', 'menc_2012', 'menages', '2012', 'Ménages'),
    ('population_menages', 'menc_pmen_2023', 'menages', '2023', 'Population des ménages'),
    ('population_menages_debut', 'menc_pmen_2012', 'menages', '2012', 'Population des ménages'),
    ('menages_1_personne', 'menc_1p_2023', 'menages', '2023', 'Ménages d\'une personne'),
    ('menages_2_personnes', 'mnoc_2pers_2023', 'menages', '2023', 'Ménages de 2 personnes'),
    ('menages_3_personnes', 'mnoc_3pers_2023', 'menages', '2023', 'Ménages de 3 personnes'),
    ('menages_4_personnes', 'mnoc_4pers_2023', 'menages', '2023', 'Ménages de 4 personnes'),
    ('menages_5_personnes', 'mnoc_5pers_2023', 'menages', '2023', 'Ménages de 5 personnes'),
    ('menages_6_personnes_plus', 'mnoc_6pers_p_2023', 'menages', '2023', 'Ménages de 6 personnes ou plus'),
    ('menages_famille', 'menc_fam_2023', 'menages', '2023', 'Ménages avec une famille'),
    ('couples_sans_enfant', 'menc_couple_sans_enf_2023', 'menages', '2023', 'Couples sans enfant'),
    ('familles_monoparentales', 'menc_monop_2023', 'menages', '2023', 'Familles monoparentales'),
    ('menages_sans_famille', 'menc_sansfam_2023', 'menages', '2023', 'Ménages de plusieurs personnes sans famille'),
    ('menages_age_15_24', 'lage_age_15_24_2023', 'menages', '2023', 'Ménages, personne de référence de moins de 25 ans'),
    ('menages_age_25_39', 'lage_age_25_39_2023', 'menages', '2023', 'Ménages, personne de référence de 25 à 39 ans'),
    ('menages_age_40_54', 'lage_age_40_54_2023', 'menages', '2023', 'Ménages, personne de référence de 40 à 54 ans'),
    ('menages_age_55_64', 'lage_age_55_64_2023', 'menages', '2023', 'Ménages, personne de référence de 55 à 64 ans'),
    ('menages_age_65_79', 'lage_age_65_79_2023', 'menages', '2023', 'Ménages, personne de référence de 65 à 79 ans'),
    ('menages_age_80_plus', 'lage_age_80p_2023', 'menages', '2023', 'Ménages, personne de référence de 80 ans ou plus'),
    # Profils de ménages
    ('profil_jeune_seul', 'prof_jeune_seul_2023', 'profils', '2023', 'Jeunes actifs seuls'),
    ('profil_couple_sans_enfant', 'prof_couple_sans_enf_2023', 'profils', '2023', 'Couples primo-accédants sans enfant'),
    ('profil_famille_enfants', 'prof_famille_enf_2023', 'profils', '2023', 'Familles avec enfants'),
    ('profil_monoparental', 'prof_monop_2023', 'profils', '2023', 'Familles monoparentales'),
    ('profil_secundo_accedant', 'prof_secundo_2023', 'profils', '2023', 'Secundo-accédants'),
    ('profil_senior_60_74', 'prof_senior_6074_2023', 'profils', '2023', 'Seniors autonomes, 60-74 ans'),
    ('profil_senior_grande_maison', 'prof_senior_grande_maison_2023', 'profils', '2023', 'Seniors en grande maison'),
    ('profil_grand_age', 'prof_grand_age_2023', 'profils', '2023', 'Grand âge, 75 ans ou plus'),
    ('profil_grand_age_seul', 'prof_grand_age_seul_2023', 'profils', '2023', 'Grand âge seul'),
    ('profil_etudiant', 'prof_etudiant_2023', 'profils', '2023', 'Étudiants'),
    ('profil_mobilite', 'prof_mobilite_2023', 'profils', '2023', 'Salariés en mobilité (habitants)'),
    ('profil_locataire_social', 'prof_locataire_social_2023', 'profils', '2023', 'Locataires durables du parc social'),
    # Parc de logements
    ('logements', 'log_2023', 'logement', '2023', 'Logements'),
    ('logements_maisons', 'log_maison_2023', 'logement', '2023', 'Maisons'),
    ('logements_vacants', 'log_vac_2023', 'logement', '2023', 'Logements vacants'),
    ('logements_secondaires', 'log_rs_2023', 'logement', '2023', 'Résidences secondaires'),
    ('residences_principales', 'log_rp_2023', 'logement', '2023', 'Résidences principales'),
    ('rp_maisons', 'log_rp_maison_2023', 'logement', '2023', 'Résidences principales, maisons'),
    ('rp_1_piece', 'log_rp_pieces_1_2023', 'logement', '2023', 'Résidences principales d\'une pièce'),
    ('rp_2_pieces', 'log_rp_pieces_2_2023', 'logement', '2023', 'Résidences principales de 2 pièces'),
    ('rp_3_pieces', 'log_rp_pieces_3_2023', 'logement', '2023', 'Résidences principales de 3 pièces'),
    ('rp_4_pieces', 'log_rp_pieces_4_2023', 'logement', '2023', 'Résidences principales de 4 pièces'),
    ('rp_5_pieces_plus', 'log_rp_pieces_5p_2023', 'logement', '2023', 'Résidences principales de 5 pièces ou plus'),
    ('rp_proprietaires', 'log_rp_proprio_2023', 'logement', '2023', 'Propriétaires'),
    ('rp_locataires_prive_vide', 'log_rp_loc_prive_2023', 'logement', '2023', 'Locataires du privé, logement vide'),
    ('rp_locataires_meuble', 'log_rp_loc_meuble_2023', 'logement', '2023', 'Locataires d\'un meublé'),
    ('rp_locataires_hlm', 'log_rp_loc_hlm_2023', 'logement', '2023', 'Locataires HLM'),
    ('rp_loges_gratuitement', 'log_rp_gratuit_2023', 'logement', '2023', 'Logés gratuitement'),
    ('rp_surocc_moderee', 'logc_surocc_moderee_2023', 'logement', '2023', 'Suroccupation modérée'),
    ('rp_surocc_accentuee', 'logc_surocc_accentuee_2023', 'logement', '2023', 'Suroccupation accentuée'),
    ('rp_occ_normale', 'logc_occ_normale_2023', 'logement', '2023', 'Occupation normale'),
    ('rp_sousocc_moderee', 'logc_sousocc_moderee_2023', 'logement', '2023', 'Sous-occupation modérée'),
    ('rp_sousocc_accentuee', 'logc_sousocc_accentuee_2023', 'logement', '2023', 'Sous-occupation accentuée'),
    ('rp_sousocc_tres_accentuee', 'logc_sousocc_tres_accentuee_2023', 'logement', '2023', 'Sous-occupation très accentuée'),
    ('vacants_longue_duree', 'lovac_vacants_2ans_2025', 'logement', '2025', 'Logements vacants depuis plus de 2 ans (parc privé)'),
    ('logements_sociaux', 'rpls_logements_2025', 'logement', '2025', 'Logements sociaux'),
    # Construction neuve
    ('autorises_3ans', 'sit_autorises_3ans', 'construction', '2023-2025', 'Logements autorisés'),
    ('autorises_maisons_3ans', 'sit_autorises_maisons_3ans', 'construction', '2023-2025', 'Maisons autorisées'),
    # Marché et prix
    ('prix_m2_maison', 'dvf_prix_m2_maisons_2025', 'marche', '2025', 'Prix médian au m² d\'une maison'),
    ('prix_m2_appartement', 'dvf_prix_m2_appartements_2025', 'marche', '2025', 'Prix médian au m² d\'un appartement'),
    ('loyer_m2_appartement', 'loyers_m2_appartements_2025', 'marche', '2025', 'Loyer d\'annonce au m² d\'un appartement'),
    ('loyer_m2_maison', 'loyers_m2_maisons_2025', 'marche', '2025', 'Loyer d\'annonce au m² d\'une maison'),
    ('communes_zone_tendue', 'zt_zone_tendue_2026', 'territoire', '2026', 'Communes en zone tendue'),
    ('communes_abis', 'abc_abis_2026', 'territoire', '2026', 'Communes en zone Abis'),
    ('communes_a', 'abc_a_2026', 'territoire', '2026', 'Communes en zone A'),
    ('communes_b1', 'abc_b1_2026', 'territoire', '2026', 'Communes en zone B1'),
    ('communes_b2', 'abc_b2_2026', 'territoire', '2026', 'Communes en zone B2'),
    ('communes_c', 'abc_c_2026', 'territoire', '2026', 'Communes en zone C'),
    # Revenus et aides
    ('niveau_vie_median', 'filo_med_2023', 'revenus', '2023', 'Niveau de vie médian'),
    ('niveau_vie_locataires', 'filoage_med_loc_2023', 'revenus', '2023', 'Niveau de vie médian des locataires'),
    ('niveau_vie_proprietaires', 'filoage_med_proprio_2023', 'revenus', '2023', 'Niveau de vie médian des propriétaires'),
    ('taux_pauvrete', 'filo_tx_pauvrete_2023', 'revenus', '2023', 'Taux de pauvreté'),
    ('niveau_vie_d1', 'filo_d1_2023', 'revenus', '2023', 'Niveau de vie, 1er décile'),
    ('niveau_vie_d9', 'filo_d9_2023', 'revenus', '2023', 'Niveau de vie, 9e décile'),
    ('foyers_aide_logement', 'caf_foyers_al_2024', 'revenus', '2024', 'Foyers aidés au logement'),
    ('foyers_allocataires', 'caf_foyers_allocataires_2024', 'revenus', '2024', 'Foyers allocataires de la CAF'),
    ('foyers_rfr_0_10k', 'ircom_foyers_rfr_0_10k_2024', 'revenus', '2024', 'Foyers fiscaux, moins de 10 000 €'),
    ('foyers_rfr_10k_12k', 'ircom_foyers_rfr_10k_12k_2024', 'revenus', '2024', 'Foyers fiscaux, 10 000 à 12 000 €'),
    ('foyers_rfr_12k_15k', 'ircom_foyers_rfr_12k_15k_2024', 'revenus', '2024', 'Foyers fiscaux, 12 000 à 15 000 €'),
    ('foyers_rfr_15k_20k', 'ircom_foyers_rfr_15k_20k_2024', 'revenus', '2024', 'Foyers fiscaux, 15 000 à 20 000 €'),
    ('foyers_rfr_20k_30k', 'ircom_foyers_rfr_20k_30k_2024', 'revenus', '2024', 'Foyers fiscaux, 20 000 à 30 000 €'),
    ('foyers_rfr_30k_50k', 'ircom_foyers_rfr_30k_50k_2024', 'revenus', '2024', 'Foyers fiscaux, 30 000 à 50 000 €'),
    ('foyers_rfr_50k_100k', 'ircom_foyers_rfr_50k_100k_2024', 'revenus', '2024', 'Foyers fiscaux, 50 000 à 100 000 €'),
    ('foyers_rfr_100k_plus', 'ircom_foyers_rfr_plus_100k_2024', 'revenus', '2024', 'Foyers fiscaux, plus de 100 000 €'),
    ('foyers_rfr_detailles', 'ircom_foyers_detail_2024', 'revenus', '2024', 'Foyers fiscaux des communes détaillées'),
    # Emploi
    ('salaries_prives', 'urssaf_salaries_2025', 'emploi', '2025', 'Salariés du privé'),
    ('salaries_prives_debut', 'urssaf_salaries_2015', 'emploi', '2015', 'Salariés du privé'),
    ('salaries_industrie', 'urssaf_salaries_industrie_2025', 'emploi', '2025', 'Salariés de l\'industrie'),
    ('salaries_industrie_debut', 'urssaf_salaries_industrie_2015', 'emploi', '2015', 'Salariés de l\'industrie'),
    ('communes_territoires_industrie', 'anct_territoires_industrie', 'territoire', '2025', 'Communes en Territoires d\'industrie'),
    # Climat, risques, énergie
    ('dpe_a', 'dpe_nb_a_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette A'),
    ('dpe_b', 'dpe_nb_b_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette B'),
    ('dpe_c', 'dpe_nb_c_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette C'),
    ('dpe_d', 'dpe_nb_d_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette D'),
    ('dpe_e', 'dpe_nb_e_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette E'),
    ('dpe_f', 'dpe_nb_f_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette F'),
    ('dpe_g', 'dpe_nb_g_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette G'),
    ('dpe_total', 'dpe_nb_2021_2026', 'risques_energie', '2021-2026', 'DPE de logements existants'),
    ('dpe_fg', 'dpe_nb_fg_2021_2026', 'risques_energie', '2021-2026', 'DPE étiquette F ou G'),
    ('catnat_total', 'catnat_total_2016_2025', 'risques_energie', '2016-2025', 'Reconnaissances de catastrophe naturelle'),
    ('catnat_secheresse', 'catnat_secheresse_2016_2025', 'risques_energie', '2016-2025', 'Reconnaissances pour sécheresse'),
    ('catnat_inondation', 'catnat_inond_2016_2025', 'risques_energie', '2016-2025', 'Reconnaissances pour inondation'),
    ('communes_trait_de_cote', 'tdc_liste_2026', 'risques_energie', '2026', 'Communes exposées au recul du trait de côte'),
    ('communes_h1a', 'zclim_h1a', 'risques_energie', 'RE2020', 'Communes en zone climatique H1a'),
    ('communes_h1b', 'zclim_h1b', 'risques_energie', 'RE2020', 'Communes en zone climatique H1b'),
    ('communes_h1c', 'zclim_h1c', 'risques_energie', 'RE2020', 'Communes en zone climatique H1c'),
    ('communes_h2a', 'zclim_h2a', 'risques_energie', 'RE2020', 'Communes en zone climatique H2a'),
    ('communes_h2b', 'zclim_h2b', 'risques_energie', 'RE2020', 'Communes en zone climatique H2b'),
    ('communes_h2c', 'zclim_h2c', 'risques_energie', 'RE2020', 'Communes en zone climatique H2c'),
    ('communes_h2d', 'zclim_h2d', 'risques_energie', 'RE2020', 'Communes en zone climatique H2d'),
    ('communes_h3', 'zclim_h3', 'risques_energie', 'RE2020', 'Communes en zone climatique H3'),
]

# Besoin par période : nom stable -> colonne de la base ({p} = 2030, 3040 ou 4050)
BESOINS = [
    ('besoin_construction', 'bes_besoin_construction_{p}', 'Besoin en construction'),
    ('besoin_avant_vacants', 'bes_besoin_avant_vacants_{p}', 'Besoin avant vacants'),
    ('menages', 'bes_menages_{p}', 'Croissance des ménages'),
    ('fluidite', 'bes_fluidite_{p}', 'Fluidité du parc'),
    ('residences_secondaires', 'bes_res_secondaires_{p}', 'Résidences secondaires'),
    ('renouvellement', 'bes_renouvellement_{p}', 'Renouvellement du parc'),
    ('mal_logement', 'bes_mal_logement_{p}', 'Résorption du mal-logement'),
    ('vacants_mobilises', 'bes_vacants_mobilises_{p}', 'Vacants remis sur le marché'),
]

# Séries : nom -> (thème, libellé court, [(année, colonne de la base)])
SERIES = {
    'commences': ('construction', 'Logements mis en chantier', [(a, f'sit_commences_{a}') for a in range(2012, 2025)]),
    'autorises': ('construction', 'Logements autorisés', [(a, f'sit_autorises_{a}') for a in range(2012, 2026)]),
    'prix_m2_maisons': ('marche', 'Prix médian au m² des maisons', [(a, f'dvf_prix_m2_maisons_{a}') for a in range(2022, 2026)]),
    'prix_m2_appartements': ('marche', 'Prix médian au m² des appartements', [(a, f'dvf_prix_m2_appartements_{a}') for a in range(2022, 2026)]),
    'population': ('population', 'Population', [(a, f'pophist_psdc_{a}') for a in (1968, 1975, 1982, 1990, 1999)]
                   + [(a, f'pophist_pmun_{a}') for a in (2006, 2011, 2016, 2021, 2023)]),
    'menages': ('menages', 'Ménages', [(2012, 'menc_2012'), (2017, 'menc_2017'), (2023, 'menc_2023')]),
}

# Répartitions : nom -> (thème, millésime, libellé court, [(modalité, colonne ou formule)]) ; l'ordre de la liste donne `ordre`.
# Une même modalité doit garder le même ordre dans toutes les répartitions (Power BI trie la colonne modalite par ordre).
REPARTITIONS = {
    'composition_menages': ('menages', '2023', 'Composition des ménages', [
        ('Personne seule', 'menc_1p_2023'),
        ('Couple sans enfant', 'menc_couple_sans_enf_2023'),
        ('Couple avec enfants', 'menc_fam_2023 - menc_couple_sans_enf_2023 - menc_monop_2023'),
        ('Famille monoparentale', 'menc_monop_2023'),
        ('Autres', 'menc_sansfam_2023')]),
    'age_reference': ('menages', '2023', 'Âge de la personne de référence', [
        ('Moins de 25 ans', 'lage_age_15_24_2023'), ('25 à 39 ans', 'lage_age_25_39_2023'), ('40 à 54 ans', 'lage_age_40_54_2023'),
        ('55 à 64 ans', 'lage_age_55_64_2023'), ('65 à 79 ans', 'lage_age_65_79_2023'), ('80 ans ou plus', 'lage_age_80p_2023')]),
    'menages_taille': ('menages', '2023', 'Ménages par nombre de personnes', [
        ('1', 'menc_1p_2023'), ('2', 'mnoc_2pers_2023'), ('3', 'mnoc_3pers_2023'), ('4', 'mnoc_4pers_2023'),
        ('5 ou +', 'mnoc_5pers_2023 + mnoc_6pers_p_2023')]),
    'rp_pieces': ('logement', '2023', 'Résidences principales par nombre de pièces', [
        ('1', 'log_rp_pieces_1_2023'), ('2', 'log_rp_pieces_2_2023'), ('3', 'log_rp_pieces_3_2023'), ('4', 'log_rp_pieces_4_2023'),
        ('5 ou +', 'log_rp_pieces_5p_2023')]),
    'occupation': ('logement', '2023', 'Occupation des résidences principales', [
        ('Suroccupés', 'logc_surocc_moderee_2023 + logc_surocc_accentuee_2023'),
        ('Occupation normale', 'logc_occ_normale_2023'),
        ('Sous-occupation modérée', 'logc_sousocc_moderee_2023'),
        ('Sous-occupation forte', 'logc_sousocc_accentuee_2023 + logc_sousocc_tres_accentuee_2023')]),
    'statut_occupation': ('logement', '2023', 'Statut d\'occupation des résidences principales', [
        ('Propriétaires', 'log_rp_proprio_2023'),
        ('Locataires du privé', 'log_rp_loc_prive_2023 + log_rp_loc_meuble_2023'),
        ('Locataires HLM', 'log_rp_loc_hlm_2023'),
        ('Logés gratuitement', 'log_rp_gratuit_2023')]),
    'dpe': ('risques_energie', '2021-2026', 'Étiquettes énergie des logements existants', [
        (e.upper(), f'dpe_nb_{e}_2021_2026') for e in 'abcdefg']),
    'revenu_fiscal': ('revenus', '2024', 'Foyers fiscaux par revenu fiscal de référence', [
        ('Moins de 10 000 €', 'ircom_foyers_rfr_0_10k_2024'),
        ('10 000 à 15 000 €', 'ircom_foyers_rfr_10k_12k_2024 + ircom_foyers_rfr_12k_15k_2024'),
        ('15 000 à 20 000 €', 'ircom_foyers_rfr_15k_20k_2024'),
        ('20 000 à 30 000 €', 'ircom_foyers_rfr_20k_30k_2024'),
        ('30 000 à 50 000 €', 'ircom_foyers_rfr_30k_50k_2024'),
        ('50 000 à 100 000 €', 'ircom_foyers_rfr_50k_100k_2024'),
        ('Plus de 100 000 €', 'ircom_foyers_rfr_plus_100k_2024')]),
    'profils_menages': ('profils', '2023', 'Profils de ménages', [
        ('Seniors autonomes, 60-74 ans', 'prof_senior_6074_2023'),
        ('Secundo-accédants', 'prof_secundo_2023'),
        ('Grand âge, 75 ans ou plus', 'prof_grand_age_2023'),
        ('Locataires durables du parc social', 'prof_locataire_social_2023'),
        ('Familles avec enfants', 'prof_famille_enf_2023'),
        ('Jeunes actifs seuls', 'prof_jeune_seul_2023'),
        ('Familles monoparentales', 'prof_monop_2023'),
        ('Étudiants', 'prof_etudiant_2023'),
        ('Couples primo-accédants sans enfant', 'prof_couple_sans_enf_2023'),
        ('Seniors en grande maison', 'prof_senior_grande_maison_2023'),
        ('Grand âge seul', 'prof_grand_age_seul_2023'),
        ('Salariés en mobilité (habitants)', 'prof_mobilite_2023')]),
    'zonage_abc': ('territoire', '2026', 'Communes par zone ABC', [
        ('Zone Abis', 'abc_abis_2026'), ('Zone A', 'abc_a_2026'), ('Zone B1', 'abc_b1_2026'), ('Zone B2', 'abc_b2_2026'),
        ('Zone C', 'abc_c_2026')]),
    'zones_climatiques': ('risques_energie', 'RE2020', 'Communes par zone climatique', [
        (z.upper()[:2] + z[2:], f'zclim_{z}') for z in ('h1a', 'h1b', 'h1c', 'h2a', 'h2b', 'h2c', 'h2d', 'h3')]),
}

# Profils non affichés dans le graphique de la page « Pour qui » (ils se recoupent avec d'autres ou sont comptés en habitants)
PROFILS_MASQUES = {'Seniors en grande maison', 'Grand âge seul', 'Salariés en mobilité (habitants)'}

LIB_CLASSES = {1: 'Couvert si la construction se maintient', 2: 'Couvert avec la remise sur le marché des vacants',
               3: 'Non couvert, même avec les vacants remis sur le marché'}


class ErreurPowerBI(Exception):
    """Garde-fou : la base ne permet pas de produire les fichiers du rapport."""


def colonnes(formule):
    """Colonnes de la base citées dans une formule « a + b - c »."""
    return [c for c in re.split(r'\s*[+-]\s*', formule.strip()) if c]


def evaluer(df, formule):
    """Somme ou différence de colonnes ; vide si une colonne est vide (jamais 0 à la place d'une valeur absente)."""
    jetons = re.split(r'\s*([+-])\s*', formule.strip())
    val = df[jetons[0]].astype(float)
    for op, col in zip(jetons[1::2], jetons[2::2]):
        val = val + df[col] if op == '+' else val - df[col]
    return val


def lire_dictionnaire():
    d = pd.read_csv(PUB / 'dictionnaire.csv', dtype=str, encoding='utf-8-sig').fillna('')
    return d.drop_duplicates('colonne').set_index('colonne')


def lire_base(besoin, dico):
    """Lit dans les Parquet de la base les colonnes demandées (niveaux du rapport seulement). Garde-fou : colonne absente."""
    import pyarrow.parquet as pq
    manquantes = [c for c in besoin if c not in dico.index]
    par_theme = {}
    for c in besoin:
        if c in dico.index:
            par_theme.setdefault(dico.loc[c, 'theme'], []).append(c)
    for th, cs in par_theme.items():      # colonne au dictionnaire mais absente du fichier du thème
        f = PUB / f'{th}.parquet'
        dispo = set(pq.read_schema(f).names) if f.exists() else set()
        manquantes += [c for c in cs if c not in dispo]
    if manquantes:
        raise ErreurPowerBI('colonne(s) de la base absente(s) : ' + ', '.join(sorted(set(manquantes)))
                            + ". Mettre à jour la table de correspondance de pipeline/powerbi.py (nouvelle édition d'une source ?).")
    base = None
    for th, cs in sorted(par_theme.items()):
        t = pd.read_parquet(PUB / f'{th}.parquet', columns=['niveau', 'code'] + sorted(set(cs)),
                            filters=[('niveau', 'in', list(NIVEAUX))])
        base = t if base is None else base.merge(t, on=['niveau', 'code'], how='outer')
    base['id'] = [ident(n, c) for n, c in zip(base.niveau, base.code)]
    return base


def ident(niveau, code):
    pre = NIVEAUX[niveau][0]
    return 'FR' if pre == 'FR' else f'{pre}-{code}'


def noms_uniques(out):
    """Rend chaque nom unique dans son niveau : le panneau du rapport choisit un territoire par son nom, et deux homonymes
    (zones d'emploi « Le Sud » de Martinique et de La Réunion, EPCI « des Deux Vallées » de l'Oise et de l'Essonne...)
    seraient choisis ensemble, chiffres vides. Précision ajoutée entre parenthèses : département pour un EPCI, région pour
    une zone d'emploi, code en dernier recours. Les noms de niveaux différents (Paris département et zone d'emploi) restent."""
    for niveau, g in out.groupby('niveau'):
        doubles = g[g.nom.duplicated(keep=False)]
        if doubles.empty:
            continue
        precision = doubles.nom_departement if niveau == 'EPCI' else doubles.nom_region
        precision = precision.fillna(doubles.code)
        if (doubles.nom + precision).duplicated().any():
            precision = doubles.code
        out.loc[doubles.index, 'nom'] = doubles.nom + ' (' + precision + ')'
    doubles = out[out.duplicated(['niveau', 'nom'], keep=False)]
    if not doubles.empty:
        raise ErreurPowerBI('noms de territoire en double dans un niveau : ' + ', '.join(doubles.nom.head(10)))


def table_territoires():
    t = pd.read_parquet(PUB / 'territoires.parquet')
    com = t[t.niveau == 'Commune']
    nb = {'France': pd.Series({'FR': len(com)}), 'Région': com.groupby('reg').size(), 'Département': com.groupby('dep').size(),
          "Zone d'emploi": com.groupby('ze2020').size(), 'EPCI': com.groupby('epci').size()}
    t = t[t.niveau.isin(list(NIVEAUX))].copy()
    # pseudo-EPCI des quatre communes insulaires sans intercommunalité (Bréhat, Île-de-Sein, Ouessant, L'Île-d'Yeu)
    t.loc[(t.niveau == 'EPCI') & (t.code == 'ZZZZZZZZZ'), 'nom'] = 'Communes sans EPCI (quatre îles)'
    out = pd.DataFrame({'id': [ident(n, c) for n, c in zip(t.niveau, t.code)], 'niveau': t.niveau.values,
                        'ordre_niveau': t.niveau.map(lambda n: NIVEAUX[n][1]).values, 'code': t.code.values, 'nom': t.nom.values})
    reg = t.reg.where(t.niveau != 'Région', t.code).values
    dep = t.dep.where(t.niveau != 'Département', t.code).values
    out['id_region'] = ['REG-' + r if isinstance(r, str) else None for r in reg]
    out['nom_region'] = t.libreg.values
    out['id_departement'] = ['DEP-' + d if isinstance(d, str) else None for d in dep]
    noms_dep = t[t.niveau == 'Département'].set_index('code').nom
    out['nom_departement'] = [noms_dep.get(d) if isinstance(d, str) else None for d in dep]
    out.loc[out.niveau.isin(['France', 'Région']), ['id_departement', 'nom_departement']] = None
    out.loc[out.niveau == 'France', ['id_region', 'nom_region']] = None
    noms_uniques(out)
    out.insert(out.columns.get_loc('nom') + 1, 'nom_affiche',   # colonne juste après nom, comme avant (ordre publié stable)
               [nm if n == 'France' else f'{nm} ({NIVEAUX[n][2]})' for nm, n in zip(out.nom, out.niveau)])
    # parent de comparaison : France pour une région, région pour un département ou une zone d'emploi, département pour un EPCI
    regle = {'France': None, 'Région': 'FR', 'Département': 'id_region', "Zone d'emploi": 'id_region', 'EPCI': 'id_departement'}
    out['id_parent'] = [None if regle[n] is None else ('FR' if regle[n] == 'FR' else r[regle[n]]) for n, (_, r) in zip(out.niveau, out.iterrows())]
    noms = out.set_index('id').nom
    out['nom_parent'] = [noms.get(p) if p else None for p in out.id_parent]
    niv = out.set_index('id').niveau
    out['niveau_parent'] = [niv.get(p) if p else None for p in out.id_parent]
    out['nb_communes'] = [nb[n].get(c) for n, c in zip(out.niveau, out.code)]
    out['nb_communes'] = out.nb_communes.astype('Int64')
    if out.id.duplicated().any():
        raise ErreurPowerBI('identifiants de territoire en double : ' + ', '.join(out.id[out.id.duplicated()].head(10)))
    if out.id_parent.notna().sum() != (out.niveau != 'France').sum() or not out.id_parent.dropna().isin(set(out.id)).all():
        raise ErreurPowerBI('parent de comparaison manquant ou inconnu pour certains territoires')
    return out.sort_values(['ordre_niveau', 'code']).reset_index(drop=True)


def correspondance(dico):
    """Table publiée : une ligne par (fichier, nom stable, élément)."""
    lignes = []
    def ligne(fichier, nom, element, formule, theme, millesime, court, libelle=None, unite=None, definition=None):
        cs = colonnes(formule)
        d0 = dico.loc[cs[0]] if cs[0] in dico.index else None
        src = '' if d0 is None else ' ; '.join(x for x in [d0['producteur'], d0['source']] if x)
        if len(cs) > 1 and d0 is not None:
            libs = [dico.loc[c, 'libelle'] if c in dico.index else c for c in cs]
            definition = definition or 'Calcul : ' + formule_libelles(formule, libs) + '. ' + d0['definition']
        lignes.append({'fichier': fichier, 'nom_stable': nom, 'element': element, 'colonne_source': formule, 'theme': theme,
                       'millesime': millesime, 'libelle_court': court,
                       'libelle': libelle or ('' if d0 is None else d0['libelle']),
                       'unite': unite or ('' if d0 is None else d0['unite']),
                       'definition': definition or ('' if d0 is None else d0['definition']), 'source': src})
    for nom, col, th, mil, court in INDICATEURS:
        ligne('indicateurs', nom, '', col, th, mil, court)
    for p, lab in PERIODES.items():
        for nom, col, court in BESOINS:
            ligne('besoins_periode', nom, lab, col.format(p=p), 'besoins', lab, court)
    for s, (th, court, liste) in SERIES.items():
        for a, col in liste:
            ligne('series', s, str(a), col, th, str(a), court)
    for r, (th, mil, court, liste) in REPARTITIONS.items():
        for mod, f in liste:
            ligne('repartitions', r, mod, f, th, mil, court)
    return pd.DataFrame(lignes)


def formule_libelles(formule, libs):
    ops = re.findall(r'[+-]', formule)
    txt = libs[0]
    for op, l in zip(ops, libs[1:]):
        txt += (' + ' if op == '+' else ' - ') + l
    return txt


def classe(construction, avant_vacants, besoin):
    """Règle de la conclusion, pour n'importe quelle période : 1 si la construction atteint le besoin avant vacants,
    2 si elle atteint le besoin en construction, sinon 3 ; vide sans besoin (Mayotte)."""
    return pd.Series(np.where(besoin.isna() | construction.isna(), np.nan,
                              np.where(construction >= avant_vacants, 1, np.where(construction >= besoin, 2, 3))), index=besoin.index)


def ecrire(df, nom):
    SORTIE.mkdir(parents=True, exist_ok=True)
    df.to_csv(SORTIE / f'{nom}.csv.gz', sep=';', index=False, encoding='utf-8', float_format='%.12g', lineterminator='\n',
              compression={'method': 'gzip', 'compresslevel': 9, 'mtime': 0})


def construire():
    """Renvoie les tables du rapport (dictionnaire nom -> DataFrame) sans rien écrire."""
    dico = lire_dictionnaire()
    corr = correspondance(dico)
    besoin = sorted({c for f in corr.colonne_source for c in colonnes(f)})
    base = lire_base(besoin, dico)
    terr = table_territoires()
    if set(base.id) != set(terr.id):
        raise ErreurPowerBI('les territoires des thèmes et de territoires.parquet ne correspondent pas')
    base = base.set_index('id').loc[terr.id]

    # table large
    cols = {'id': terr.id.values}
    for nom, col, *_ in INDICATEURS:
        cols[nom] = evaluer(base, col).values if dico.loc[colonnes(col)[0], 'agregation'] != 'texte' else base[col].values
    ind = pd.DataFrame(cols)
    ind['classe_2030_2040'] = ind.classe_2030_2040.astype('Int64')

    # besoin par période
    bp = []
    for p, lab in PERIODES.items():
        x = pd.DataFrame({'id': terr.id.values, 'periode': lab})
        for nom, col, _ in BESOINS:
            x[nom] = base[col.format(p=p)].values
        bp.append(x)
    bp = pd.concat(bp, ignore_index=True)

    # séries
    se = []
    for s, (_, _, liste) in SERIES.items():
        for a, col in liste:
            se.append(pd.DataFrame({'id': terr.id.values, 'serie': s, 'annee': a, 'valeur': base[col].values}))
    se = pd.concat(se, ignore_index=True).dropna(subset=['valeur'])

    # répartitions
    rp = []
    for r, (_, _, _, liste) in REPARTITIONS.items():
        for i, (mod, f) in enumerate(liste, start=1):
            rp.append(pd.DataFrame({'id': terr.id.values, 'repartition': r, 'modalite': mod, 'ordre': i, 'valeur': evaluer(base, f).values}))
    rp = pd.concat(rp, ignore_index=True).dropna(subset=['valeur'])
    rp['affiche'] = np.where((rp.repartition == 'profils_menages') & rp.modalite.isin(PROFILS_MASQUES), 0, 1)
    doubles = rp.groupby('modalite').ordre.nunique()
    if (doubles > 1).any():
        raise ErreurPowerBI('modalité avec deux ordres différents (tri impossible dans Power BI) : ' + ', '.join(doubles[doubles > 1].index))

    # garde-fou : la règle de classe appliquée à 2030-2040 redonne la classe publiée par la base
    b3 = bp[bp.periode == '2030-2040'].set_index('id')
    cl = classe(ind.set_index('id').construction_actuelle, b3.besoin_avant_vacants, b3.besoin_construction)
    pub = ind.set_index('id').classe_2030_2040.astype(float)
    diff = ~((cl == pub) | (cl.isna() & pub.isna()))
    if diff.any():
        raise ErreurPowerBI(f'la règle de classe ne redonne pas bes_classe_3040 pour {int(diff.sum())} territoire(s) : '
                            + ', '.join(diff[diff].index[:10]))

    # méta : date de mise à jour de la base et millésime de chaque source utilisée par le rapport
    meta_base = json.load(open(PUB / 'meta.json', encoding='utf-8'))
    lignes = [{'element': 'Mise à jour de la base', 'ref': '', 'producteur': '', 'millesime': meta_base['mise_a_jour'],
               'date': meta_base['mise_a_jour']},
              {'element': 'Géographie', 'ref': '', 'producteur': 'Insee', 'millesime': meta_base.get('geographie', ''), 'date': ''}]
    vus = set()
    for c in besoin:
        d = dico.loc[c]
        cle = (d['source_ref'], d['source'])
        if cle in vus or not d['source']: continue
        vus.add(cle)
        lignes.append({'element': d['source'], 'ref': d['source_ref'], 'producteur': d['producteur'], 'millesime': d['millesime'], 'date': ''})
    meta = pd.DataFrame(lignes)
    return {'territoires': terr, 'indicateurs': ind, 'besoins_periode': bp, 'series': se, 'repartitions': rp,
            'meta': meta, 'correspondance': corr}


def main():
    tabs = construire()
    for nom, df in tabs.items():
        ecrire(df, nom)
    tailles = {n: round((SORTIE / f'{n}.csv.gz').stat().st_size / 1e3) for n in tabs}
    print('powerbi :', {n: (len(df), df.shape[1]) for n, df in tabs.items()}, '| ko :', tailles)
    return tabs


if __name__ == '__main__':
    try:
        main()
    except ErreurPowerBI as e:
        print('ARRÊT (powerbi) :', e, file=sys.stderr)
        sys.exit(1)
