# -*- coding: utf-8 -*-
"""Équipements et services des communes (Base permanente des équipements au 1er janvier 2025) et capacités
d'hébergement touristique au 1er janvier 2026 ; Insee, Melodi (DS_BPE, DS_TOUR_CAP).

BPE : domaines, sous-domaines et types d'équipement sont emboîtés et comptent pour une seule dimension ; chaque type
d'équipement (235), sous-domaine (27) et domaine (7) donne une colonne, plus le total (270 colonnes). Tourisme : le type
d'hébergement n'a pas de total (hôtels, campings, autres hébergements collectifs) et fait partie de la mesure ; sont
gardés les croisements avec le classement en étoiles et, pour les campings, la nature des emplacements (à l'année ou
de passage). Tous les indicateurs sont des effectifs (somme).
"""
from pathlib import Path
import geo
from sources import _melodi_commun as mc

SOURCE = {'ref': 'E7-13',
          'nom': "Base permanente des équipements (BPE) 2025, dénombrement des équipements ; capacités d'hébergements "
                 "touristiques 2026 (autre fiche : E4-22)",
          'producteur': 'Insee',
          'url': 'https://catalogue-donnees.insee.fr/fr/catalogue/recherche/DS_BPE',
          'telechargement': 'https://api.insee.fr/melodi/file/DS_BPE/DS_BPE_2025_CSV_FR ; '
                            'https://api.insee.fr/melodi/file/DS_TOUR_CAP/DS_TOUR_CAP_2026_CSV_FR',
          'millesime': 'BPE au 1er janvier 2025 ; hébergements touristiques au 1er janvier 2026',
          'licence': 'Licence ouverte 2.0'}

JEUX = [
    dict(ds='DS_BPE', prefixe='bpe', periode='au 1er janvier {a}', mesure='BPE_MEASURE',
         titre='Base permanente des équipements, dénombrement des équipements (commerce, sport, services, santé...)',
         hierarchie=['FACILITY_DOM', 'FACILITY_SDOM', 'FACILITY_TYPE'], ordre=['FACILITY_DOM', 'FACILITY_SDOM', 'FACILITY_TYPE'],
         dims={'FACILITY_DOM': dict(abr='dom', tpl='domaine {lib}'), 'FACILITY_SDOM': dict(abr='sdom', tpl='sous-domaine {lib}'),
               'FACILITY_TYPE': dict(abr='', brut=True)},
         mesures={'FACILITIES': dict(nom='', lib='Équipements', unite='équipements', defn="Nombre d'équipements")}),
    dict(ds='DS_TOUR_CAP', prefixe='tour', periode='au 1er janvier {a}', mesure='TOUR_MEASURE',
         titre="Capacités d'hébergements touristiques", dims_mesure=['ACTIVITY'], ordre=['ACTIVITY', 'UNIT_LOC_RANKING', 'L_STAY'],
         dims={'ACTIVITY': dict(abr='', colle=True), 'UNIT_LOC_RANKING': dict(abr='etoiles'), 'L_STAY': dict(abr='')},
         codes={('ACTIVITY', 'I551'): ('hotels', 'des hôtels'),
                ('ACTIVITY', 'I552'): ('autres_heb', 'des autres hébergements collectifs de tourisme'),
                ('ACTIVITY', 'I552A'): ('villages_vac', 'des villages vacances et maisons familiales'),
                ('ACTIVITY', 'I552B'): ('res_tourisme', 'des résidences de tourisme et résidences hôtelières'),
                ('ACTIVITY', 'I552C'): ('auberges', 'des auberges de jeunesse et centres sportifs'),
                ('ACTIVITY', 'I553'): ('campings', 'des terrains de camping'),
                **{('UNIT_LOC_RANKING', k): (k, f"{k} étoile{'s' if k != '1' else ''}") for k in '12345'},
                ('UNIT_LOC_RANKING', 'NC'): ('nc', 'non classés'),
                ('L_STAY', 'LONG'): ('annee', "emplacements loués à l'année"), ('L_STAY', 'SHORT'): ('passage', 'emplacements de passage')},
         mesures={'PLACE': dict(nom='places', lib='Places', unite='places', defn='Nombre de places',
                                note="Places : chambres pour les hôtels, emplacements pour les campings, unités "
                                     "d'hébergement pour les autres hébergements collectifs."),
                  'UNIT_LOC': dict(nom='etab', lib='Établissements', unite='établissements', defn="Nombre d'établissements"),
                  'BEDPLACE': dict(nom='lits', lib='Lits', unite='lits', defn='Nombre de lits')}),
]


def charger(cache: Path) -> list:
    """Lit les zips Melodi de cache/melodi/ (téléchargés une seule fois) et renvoie un bloc 'equipements'."""
    return [mc.assembler('equipements', [mc.traiter(j, cache) for j in JEUX])]
