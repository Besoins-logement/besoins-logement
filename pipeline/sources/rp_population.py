# -*- coding: utf-8 -*-
"""Population des communes : structure par sexe, âge et catégorie sociale (recensement 2023, rappels 2012 et 2017),
populations municipales depuis 1968, naissances et décès annuels 2008-2025, migrations résidentielles (Insee, Melodi).

Jeux Melodi (zips CSV lus dans cache/melodi/) : DS_RP_POPULATION_PRINC, DS_RP_POPULATION_COMP,
DS_POPULATIONS_HISTORIQUES, DS_ETAT_CIVIL_NAIS_COMMUNES, DS_ETAT_CIVIL_DECES_COMMUNES, DS_RP_MIGRES_PRINC.
Les migrations résidentielles (lieu de résidence un an auparavant) sont placées ici, dans le thème population,
plutôt que dans rp_emploi : elles décrivent les arrivées de ménages, utiles à la demande de logement.

Règles de sélection (voir sources/_melodi_commun.py) : dernière année de chaque série ; 2012 et 2017 seulement pour les
totaux ; au plus deux dimensions hors total. Écarté : DS_RP_POPULATION_COMP croisé sexe x catégorie sociale x âge
(48 séries à trois dimensions hors total). Les totaux identiques d'un tableau à l'autre ne sont gardés qu'une fois.
Naissances, décès et populations municipales : toutes les années publiées sont gardées (séries sans dimension).
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'E7-55',
          'nom': "Recensement de la population 2023 (dossier complet : population, migrations résidentielles), populations "
                 "historiques 1968-2023, état civil 2008-2025 (naissances, décès) ; autres fiches : E3-23, E6-14, E6-17, P2-001",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_RP_POPULATION_PRINC',
          'telechargement': 'https://api.insee.fr/melodi/file/<jeu>/<fichier>_CSV_FR (zips CSV Melodi : DS_RP_POPULATION_PRINC_2023, '
                            'DS_RP_POPULATION_COMP_2023, DS_POPULATIONS_HISTORIQUES, DS_ETAT_CIVIL_NAIS_COMMUNES_2025, '
                            'DS_ETAT_CIVIL_DECES_COMMUNES_2025, DS_RP_MIGRES_PRINC_2023)',
          'millesime': 'Recensement 2023 (enquêtes 2021 à 2025), rappels 2012 et 2017 ; état civil 2008-2025 ; populations 1968-2023',
          'licence': 'Licence ouverte 2.0'}

PCS = {'1': ('agri', 'agriculteurs exploitants'), '2': ('artcom', "artisans, commerçants et chefs d'entreprise"),
       '3': ('cadres', 'cadres et professions intellectuelles supérieures'), '4': ('profint', 'professions intermédiaires'),
       '5': ('employes', 'employés'), '6': ('ouvriers', 'ouvriers'), '7': ('retraites', 'retraités'),
       '8': ('inactifs', 'autres personnes sans activité professionnelle'), '9': ('inactifs', 'autres personnes sans activité professionnelle')}

JEUX = [
    dict(ds='DS_RP_POPULATION_PRINC', prefixe='pop',
         titre='Évolution et structure de la population, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['SEX', 'AGE'], dims={'SEX': dict(abr=''), 'AGE': dict(abr='age')},
         mesures={'POP': dict(nom='', lib='Population', unite='habitants', defn="Nombre d'habitants")}),
    dict(ds='DS_RP_POPULATION_COMP', prefixe='popc',
         titre='Évolution et structure de la population, indicateurs complémentaires (dossier complet)',
         mesure='RP_MEASURE', ordre=['SEX', 'PCS', 'AGE'], totaux={'AGE': 'Y_GE15'},
         dims={'SEX': dict(abr=''), 'PCS': dict(abr='pcs'), 'AGE': dict(abr='age', lib_total='15 ans ou plus')},
         codes={('PCS', k): v for k, v in PCS.items()},
         mesures={'POP': dict(nom='', lib='Population', unite='habitants',
                              defn="Nombre d'habitants")}),
    dict(ds='DS_POPULATIONS_HISTORIQUES', prefixe='pophist', titre='Populations municipales de 1968 à 2023',
         mesure='POPREF_MEASURE',
         mesures={'PMUN': dict(nom='pmun', lib='Population municipale', unite='habitants', defn='Population municipale',
                               note="Depuis 2006, deux recensements ne se comparent bien qu'à au moins 5 ans d'écart."),
                  'PSDC': dict(nom='psdc', lib='Population sans doubles comptes', unite='habitants',
                               defn='Population sans doubles comptes')}),
    dict(ds='DS_ETAT_CIVIL_NAIS_COMMUNES', prefixe='nais', titre='Nombre de naissances annuelles par commune',
         mesure='EC_MEASURE', periode='année {a}',
         mesures={'LVB': dict(nom='', lib='Naissances vivantes', unite='naissances',
                              defn="Nombre de naissances vivantes d'après l'état civil")}),
    dict(ds='DS_ETAT_CIVIL_DECES_COMMUNES', prefixe='deces', titre='Nombre de décès annuels par commune',
         mesure='EC_MEASURE', periode='année {a}',
         mesures={'DTH': dict(nom='', lib='Décès', unite='décès', defn="Nombre de décès d'après l'état civil")}),
    dict(ds='DS_RP_MIGRES_PRINC', prefixe='migr',
         titre='Migrations résidentielles, principaux indicateurs (dossier complet)',
         mesure='RP_MEASURE', ordre=['AGE', 'PREV_RES_AREA'], totaux={'AGE': 'Y_GE1'},
         dims={'AGE': dict(abr='age', lib_total='1 an ou plus'), 'PREV_RES_AREA': dict(abr='ante')},
         codes={('PREV_RES_AREA', '11'): ('meme_log', 'résidant un an auparavant dans le même logement'),
                ('PREV_RES_AREA', '12'): ('meme_com', 'résidant un an auparavant dans un autre logement de la même commune'),
                ('PREV_RES_AREA', '20_30'): ('autre_com', 'résidant un an auparavant dans une autre commune'),
                ('PREV_RES_AREA', '21'): ('autre_com_dep', 'résidant un an auparavant dans une autre commune du département'),
                ('PREV_RES_AREA', '22'): ('autre_dep_reg', 'résidant un an auparavant dans un autre département de la région'),
                ('PREV_RES_AREA', '23'): ('autre_reg', 'résidant un an auparavant dans une autre région de métropole'),
                ('PREV_RES_AREA', '24'): ('dom', "résidant un an auparavant dans un département d'outre-mer d'une autre région"),
                ('PREV_RES_AREA', '25T32'): ('hors_france', 'résidant un an auparavant hors de la métropole et des départements d\'outre-mer')},
         mesures={'POP': dict(nom='', lib='Population', unite='habitants', defn="Nombre d'habitants")},
         ratios=[dict(col='migr_part_autre_com_2023', unite='%', facteur=100, annee='2023',
                      libelle="Part des habitants d'un an ou plus qui résidaient dans une autre commune un an auparavant (2023)",
                      definition="Habitants d'un an ou plus qui résidaient dans une autre commune un an auparavant, pour 100 "
                                 "habitants d'un an ou plus, recensement de la population 2023.",
                      num='migr_ante_autre_com_2023', den='migr_2023')]),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'population'."""
    return [mc.assembler('population', [mc.traiter(j, cache) for j in JEUX])]
