# -*- coding: utf-8 -*-
"""Tissu économique des communes : établissements employeurs et salariés par secteur et taille (Flores fin 2024),
créations d'entreprises et d'établissements (2012-2025), salaires nets moyens du secteur privé au lieu de travail
(2023-2024) ; Insee, Melodi (DS_FLORES_A17, DS_SIDE_CREA_COM, DS_BTS_SAL_EQTP_SEX_AGE).

Règles : dernière année de chaque série ; années antérieures seulement pour les totaux (créations 2012-2024, salaire
moyen 2023) ; au plus deux dimensions hors total (Flores : secteur x tranche d'effectifs, 342 colonnes, sous le seuil
de 400). Le salaire moyen est non additif : valeurs publiées par l'Insee pour les EPCI, départements, régions, zones
d'emploi et la France, moyenne pondérée par les effectifs salariés Flores (flores_sal_2024) ailleurs ; il est soumis au
secret statistique dans la plupart des petites communes. Pour DS_SIDE_CREA_COM (49 millions de lignes), seules la
dernière année et, pour les années antérieures, les lignes au total sont lues.
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'E7-02',
          'nom': "Flores, établissements et effectifs salariés en 17 secteurs (fin 2024) ; créations d'entreprises et "
                 "d'établissements (Sidé, 2012-2025) ; salaires du secteur privé (Base tous salariés 2023-2024) ; "
                 "autres fiches : E7-11, E6-16",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_FLORES_A17',
          'telechargement': 'https://api.insee.fr/melodi/file/DS_FLORES_A17/DS_FLORES_A17_2024_CSV_FR ; '
                            'https://api.insee.fr/melodi/file/DS_SIDE_CREA_COM/DS_SIDE_CREA_COM_2025_CSV_FR ; '
                            'https://api.insee.fr/melodi/file/DS_BTS_SAL_EQTP_SEX_AGE/DS_BTS_SAL_EQTP_SEX_AGE_2024_CSV_FR',
          'millesime': 'Flores fin 2024 ; créations 2012 à 2025 ; salaires 2023 et 2024',
          'licence': 'Licence ouverte 2.0'}

A17 = {'AZ': 'agri', 'C1': 'ind_agroalim', 'C2': 'cokefaction_raffinage', 'C3': 'ind_equip_elec', 'C4': 'ind_mat_transport',
       'C5': 'ind_autres', 'DE': 'energie_eau_dechets', 'FZ': 'construction', 'GZ': 'commerce', 'HZ': 'transports',
       'IZ': 'hebergement_resto', 'JZ': 'info_com', 'KZ': 'finance', 'LZ': 'immobilier', 'MN': 'services_entreprises',
       'OQ': 'admin_enseign_sante', 'RU': 'autres_services'}
A10 = {'BE': 'industrie', 'FZ': 'construction', 'GI': 'commerce_transp_heb', 'JZ': 'info_com', 'KZ': 'finance',
       'LZ': 'immobilier', 'MN': 'services_entreprises', 'OQ': 'admin_enseign_sante', 'RU': 'autres_services'}
TAILLE = {'E0': '0', 'E1T4': '1_4', 'E5T9': '5_9', 'E10T19': '10_19', 'E20T49': '20_49', 'E50T99': '50_99',
          'E100T199': '100_199', 'E200T499': '200_499', 'E_GE500': '500p'}

JEUX = [
    dict(ds='DS_FLORES_A17', prefixe='flores', periode='fin {a}', mesure='FLORES_MEASURE', ordre=['ACTIVITY', 'NUMBER_EMPL'],
         titre="Nombre d'établissements et effectifs salariés en 17 grands secteurs (Flores)",
         dims={'ACTIVITY': dict(abr=''), 'NUMBER_EMPL': dict(abr='taille', tpl='établissements de {lib}')},
         codes={**{('ACTIVITY', k): (v, None) for k, v in A17.items()}, **{('NUMBER_EMPL', k): (v, None) for k, v in TAILLE.items()}},
         mesures={'UNIT_LOC': dict(nom='etab', lib='Établissements employeurs', unite='établissements',
                                   defn="Nombre d'établissements employeurs actifs en fin d'année",
                                   note='Champ : établissements employeurs, hors défense et particuliers employeurs.'),
                  'EMPL3112': dict(nom='sal', lib='Effectifs salariés', unite='salariés',
                                   defn='Nombre de salariés présents la dernière semaine de décembre',
                                   note='Champ : établissements employeurs, hors défense et particuliers employeurs.')}),
    dict(ds='DS_SIDE_CREA_COM', prefixe='crea', periode='année {a}', mesure='SIDE_MEASURE', ordre=['ACTIVITY', 'LEGAL_FORM'],
         titre="Créations d'entreprises et d'établissements au niveau communal et supra-communal par secteur d'activité (A10) et forme légale",
         totaux_anciens=(('ACTIVITY', '_T'), ('LEGAL_FORM', '_T')),
         dims={'ACTIVITY': dict(abr=''), 'LEGAL_FORM': dict(abr='')},
         codes={**{('ACTIVITY', k): (v, None) for k, v in A10.items()},
                ('LEGAL_FORM', '10'): ('ei', 'entrepreneurs individuels'), ('LEGAL_FORM', '54'): ('sarl', 'SARL'),
                ('LEGAL_FORM', '57'): ('sas', 'SAS'), ('LEGAL_FORM', 'OTH_SIDE'): ('autres_societes', 'autres sociétés')},
         mesures={'BURE': dict(nom='ent', lib="Créations d'entreprises", unite='entreprises',
                               defn="Nombre d'entreprises (unités légales) créées dans la commune"),
                  'UNIT_LOC_BURE': dict(nom='etab', lib="Créations d'établissements", unite='établissements',
                                        defn="Nombre d'établissements créés dans la commune",
                                        note='La forme légale est celle du siège.')}),
    dict(ds='DS_BTS_SAL_EQTP_SEX_AGE', prefixe='sal', periode='année {a}', mesure='DERA_MEASURE', ordre=['SEX', 'AGE'],
         titre="Salaires dans le secteur privé selon le sexe et l'âge au niveau communal (Base tous salariés)",
         dims={'SEX': dict(abr=''), 'AGE': dict(abr='age')},
         mesures={'SALAIRE_NET_EQTP_MENSUEL_MOYENNE': dict(
             nom='net_eqtp', lib='Salaire net mensuel moyen en équivalent temps plein', unite='euros par mois',
             defn='Salaire net mensuel moyen en équivalent temps plein des salariés du secteur privé travaillant dans la commune',
             agr='non_additif', poids='flores_sal_2024',
             note='Champ : salariés du privé (y compris alternants, stagiaires et contrats aidés), hors agriculture et '
                  'particuliers employeurs, au lieu de travail.')}),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'emploi'."""
    return [mc.noter_diffusion(mc.assembler('emploi', [mc.traiter(j, cache) for j in JEUX]))]
