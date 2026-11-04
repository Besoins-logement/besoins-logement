# -*- coding: utf-8 -*-
"""Niveaux de vie, pauvreté et composition du revenu disponible en 2023 (Insee, Filosofi, jeux Melodi
DS_FILOSOFI_CC et DS_FILOSOFI_SAGE_LOG_TP_NIVVIE).

Tous les indicateurs sont non additifs (médianes, déciles, taux, parts, indices) : la base reprend les valeurs publiées
par l'Insee pour les EPCI, départements, régions, zones d'emploi et la France ('publies'), et à défaut une moyenne
pondérée par la population du recensement 2023 (colonne filo_poids_pop_2023, reprise de DS_RP_POPULATION_PRINC).

À la commune, le secret statistique limite fortement la diffusion : le niveau de vie médian est publié pour environ
30 800 communes et le taux de pauvreté pour environ 5 200 (avec des valeurs publiées pour les EPCI et zones d'emploi) ;
les déciles, quartiles, indices d'inégalité et la composition du revenu ne sont publiés dans ce jeu que pour les
départements, les régions et la France (colonnes vides à la commune). La définition de chaque colonne précise le
nombre de communes renseignées et les niveaux publiés. DS_FILOSOFI_SAGE_LOG_TP_NIVVIE (niveau de vie médian et taux de pauvreté par âge, sexe et statut
d'occupation du logement) n'existe que pour les départements, les régions et la France métropolitaine : colonnes
vides à la commune, valeurs publiées aux niveaux DEP, REG et FRANCE. Pour ces deux jeux, la valeur « France » publiée
est celle de la France métropolitaine (pas de valeur France entière dans Melodi).
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'P2-021',
          'nom': 'Indicateurs sur les revenus et la pauvreté au niveau local en 2023 (Filosofi) ; niveau de vie médian et '
                 "taux de pauvreté par âge, sexe et statut d'occupation du logement",
          'producteur': 'Insee (Filosofi : Insee, DGFiP, Cnaf, Cnav, CCMSA)',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_FILOSOFI_CC',
          'telechargement': 'https://api.insee.fr/melodi/file/DS_FILOSOFI_CC/DS_FILOSOFI_CC_2023_CSV_FR ; '
                            'https://api.insee.fr/melodi/file/DS_FILOSOFI_SAGE_LOG_TP_NIVVIE/DS_FILOSOFI_SAGE_LOG_TP_NIVVIE_2023_CSV_FR',
          'millesime': 'Revenus 2023',
          'licence': 'Licence ouverte 2.0'}

FM = "La valeur France publiée est celle de la France métropolitaine."
EUR, PCT = 'euros par an', '%'
# code : (nom court, libellé, unité, diffusé à la commune)
MESURES = {
    'MED_SL': ('med', 'Niveau de vie médian', EUR, True),
    'PR_MD60': ('tx_pauvrete', 'Taux de pauvreté au seuil de 60 % du niveau de vie médian', PCT, True),
    **{f'D{k}_SL': (f'd{k}', f"{k}{'er' if k == 1 else 'e'} décile du niveau de vie", EUR, False) for k in (1, 2, 3, 4, 6, 7, 8, 9)},
    'Q1_SL': ('q1', '1er quartile du niveau de vie', EUR, False),
    'Q3_SL': ('q3', '3e quartile du niveau de vie', EUR, False),
    'IQR_SL': ('ecart_iq', 'Écart interquartile du niveau de vie', EUR, False),
    'IR_D9_D1_SL': ('rapport_d9_d1', 'Rapport interdécile du niveau de vie (9e décile sur 1er décile)', 'rapport', False),
    'S80S20_SL': ('s80_s20', 'Rapport entre la masse des niveaux de vie des 20 % de personnes les plus aisées et celle '
                             'des 20 % les plus modestes', 'rapport', False),
    'GI_SL': ('gini', 'Indice de Gini du niveau de vie', 'indice de 0 à 1', False),
    'S_EI_DI': ('part_rev_activite', "Part des revenus d'activité dans le revenu disponible", PCT, False),
    'S_EI_DI_SAL': ('part_salaires', 'Part des salaires dans le revenu disponible', PCT, False),
    'S_EI_DI_N_SAL': ('part_non_salaries', 'Part des revenus des activités non salariées dans le revenu disponible', PCT, False),
    'S_EI_DI_UNE': ('part_chomage', 'Part des indemnités de chômage dans le revenu disponible', PCT, False),
    'S_RET_PEN_DI': ('part_pensions', 'Part des pensions, retraites et rentes dans le revenu disponible', PCT, False),
    'S_INC_ASS_DI': ('part_patrimoine', 'Part des revenus du patrimoine et autres revenus dans le revenu disponible', PCT, False),
    'S_SOC_BEN_DI': ('part_prestations', "Part de l'ensemble des prestations sociales dans le revenu disponible", PCT, False),
    'S_SOC_BEN_DI_FAM_BEN': ('part_prest_familiales', 'Part des prestations familiales dans le revenu disponible', PCT, False),
    'S_SOC_BEN_DI_HOU_BEN': ('part_prest_logement', 'Part des prestations logement dans le revenu disponible', PCT, False),
    'S_SOC_BEN_DI_MIN_SOC': ('part_minima_sociaux', 'Part des minima sociaux dans le revenu disponible', PCT, False),
    'S_DIR_TAX_DI': ('part_impots', 'Part des impôts directs dans le revenu disponible', PCT, False),
}
POIDS = 'filo_poids_pop_2023'

JEUX = [
    dict(ds='DS_RP_POPULATION_PRINC', prefixe='filo',
         titre='Évolution et structure de la population, principaux indicateurs (dossier complet), recensement 2023',
         mesure='RP_MEASURE', garder=lambda r: r['_n'] == 0 and r['TIME_PERIOD'] == '2023',
         mesures={'POP': dict(nom='poids_pop', lib='Population, poids des indicateurs Filosofi', unite='habitants',
                              defn="Nombre d'habitants, utilisé pour pondérer les moyennes des indicateurs de niveau de vie "
                                   "sur des territoires sans valeur publiée")}),
    dict(ds='DS_FILOSOFI_CC', prefixe='filo', periode='revenus {a}',
         titre='Niveau de vie, taux de pauvreté, décomposition du revenu disponible en 2023 (Filosofi)',
         mesure='FILOSOFI_MEASURE',
         mesures={k: dict(nom=n, lib=l, unite=u, defn=l, agr='non_additif', poids=POIDS, note=FM)
                  for k, (n, l, u, com) in MESURES.items()}),
    dict(ds='DS_FILOSOFI_SAGE_LOG_TP_NIVVIE', prefixe='filoage', periode='revenus {a}', niveau_series='DEP',
         titre="Niveau de vie médian et taux de pauvreté par tranche d'âge, sexe et statut d'occupation du logement en 2023 (Filosofi)",
         mesure='FILOSOFI_MEASURE', ordre=['TSH', 'SEX', 'AGE_GP'],
         dims={'TSH': dict(abr=''), 'SEX': dict(abr=''), 'AGE_GP': dict(abr='age')},
         codes={('TSH', '1'): ('proprio', 'personnes des ménages propriétaires'),
                ('TSH', '2'): ('loc', 'personnes des ménages locataires'),
                ('AGE_GP', 'Y_GE18'): ('18p', '18 ans ou plus'), ('AGE_GP', 'Y_LT18'): ('0_17', 'moins de 18 ans'),
                ('AGE_GP', 'Y_GE75'): ('75p', '75 ans ou plus')},
         mesures={'MED_SL': dict(nom='med', lib='Niveau de vie médian', unite=EUR, defn='Niveau de vie médian',
                                 agr='non_additif', poids=POIDS, note=FM),
                  'PR_MD60': dict(nom='tx_pauvrete', lib='Taux de pauvreté au seuil de 60 % du niveau de vie médian',
                                  unite=PCT, defn='Taux de pauvreté au seuil de 60 % du niveau de vie médian métropolitain',
                                  agr='non_additif', poids=POIDS, note=FM)}),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'revenus'."""
    return [mc.noter_diffusion(mc.assembler('revenus', [mc.traiter(j, cache) for j in JEUX]))]
