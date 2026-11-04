# -*- coding: utf-8 -*-
"""Grille communale de densité de l'Insee (édition 2025, géographie 2026) : niveaux à 3 et 7 postes, croisement avec les aires d'attraction, population par niveau."""
import shutil, time, urllib.request
from pathlib import Path
import pandas as pd
import geo

SOURCE = {'ref': 'E7-62',
          'nom': 'Grille communale de densité 2025 (fichier en géographie 2026)',
          'producteur': 'Insee',
          'url': 'https://www.insee.fr/fr/information/8571524',
          'telechargement': 'https://www.insee.fr/fr/statistiques/fichier/8571524/fichier_diffusion_2026.xlsx',
          'millesime': 'Grille de densité 2025, géographie au 1er janvier 2026, population municipale 2023 (mise en ligne le 15 mai 2026)',
          'licence': 'Licence ouverte 2.0'}

NIV3 = [('Urbain dense', 'dens_urbain_dense_2025'), ('Urbain intermédiaire', 'dens_urbain_interm_2025'), ('Rural', 'dens_rural_2025')]
NIV7 = [('Grands centres urbains', 'dens7_grands_centres_2025'), ('Centres urbains intermédiaires', 'dens7_centres_interm_2025'),
        ('Petites villes', 'dens7_petites_villes_2025'), ('Ceintures urbaines', 'dens7_ceintures_2025'),
        ('Bourgs ruraux', 'dens7_bourgs_ruraux_2025'), ('Rural à habitat dispersé', 'dens7_rural_disperse_2025'),
        ('Rural à habitat très dispersé', 'dens7_rural_tres_disperse_2025')]
NIVAAV = [('Rural périurbain', 'dens_rural_periurbain_2025'), ('Rural non périurbain', 'dens_rural_non_periurbain_2025')]


def _telecharger(url, dest, essais=30):
    """Télécharge url dans dest une seule fois, avec reprises en cas de coupure réseau."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    err = None
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (besoins-logement)'})
            with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            part.replace(dest)
            return dest
        except Exception as e:
            err = e
            time.sleep(min(2 + k, 10))
    raise RuntimeError(f'téléchargement impossible : {url} ({err})')


def charger(cache: Path) -> list:
    p = _telecharger(SOURCE['telechargement'], Path(cache) / 'densite' / 'fichier_diffusion_2026.xlsx')
    # ligne 5 du tableau : noms courts des variables (CODGEO, DENS, LIBDENS, PMUN23, P1, P2, P3, DENS_AAV, ...)
    brut = pd.read_excel(p, sheet_name='Maille communale', header=4, dtype=str, engine='calamine')
    brut = brut[brut.CODGEO.notna() & brut.CODGEO.str.strip().str.len().eq(5)].copy()
    for c in ['PMUN23', 'P1', 'P2', 'P3']:
        brut[c] = pd.to_numeric(brut[c], errors='coerce')
    brut['CODGEO'] = geo.vers_cog2026(brut.CODGEO.str.strip()).values
    brut = brut.dropna(subset=['CODGEO'])
    if brut.CODGEO.duplicated().any():
        raise ValueError('le fichier de la grille de densité devrait déjà être en géographie 2026 (une ligne par commune)')

    df = pd.DataFrame({'CODGEO': brut.CODGEO.values,
                       'dens_niveau3_2025': brut.LIBDENS.str.strip().values,
                       'dens_niveau7_2025': brut.LIBDENS7.str.strip().values,
                       'dens_niveau_aav_2025': brut.LIBDENS_AAV.str.strip().values})
    for lib, col in NIV3:
        df[col] = (df.dens_niveau3_2025 == lib).astype('int64')
    for lib, col in NIV7:
        df[col] = (df.dens_niveau7_2025 == lib).astype('int64')
    for lib, col in NIVAAV:
        df[col] = (df.dens_niveau_aav_2025 == lib).astype('int64')
    pop = brut.PMUN23.values
    df['dens_pop_2023'] = pop
    for k in (1, 2, 3):
        df[f'dens_pop_niv{k}_2023'] = (pop * brut[f'P{k}'].values / 100).round(2)
    for k in (1, 2, 3):
        df[f'dens_part_pop_niv{k}_2023'] = (df[f'dens_pop_niv{k}_2023'] / df.dens_pop_2023 * 100).round(2)
    for lib, col in NIV3 + NIV7 + NIVAAV:
        if df[col].sum() == 0:
            raise ValueError(f'modalité absente du fichier : {lib}')
    df = df.sort_values('CODGEO').reset_index(drop=True)

    g = ("Grille communale de densité 2025 de l'Insee, en géographie au 1er janvier 2026. La grille classe chaque commune "
         "selon la répartition de sa population entre des carreaux de 1 km2 plus ou moins densément peuplés.")
    inds = [
        {'col': 'dens_niveau3_2025', 'libelle': 'Niveau de densité de la commune (3 postes)', 'unite': '',
         'definition': "Niveau de densité à 3 postes : urbain dense, urbain intermédiaire ou rural. " + g,
         'agregation': 'texte', 'annee': '2025'},
        {'col': 'dens_niveau7_2025', 'libelle': 'Niveau de densité de la commune (7 postes)', 'unite': '',
         'definition': ("Niveau de densité détaillé à 7 postes : grands centres urbains ; centres urbains intermédiaires, "
                        "petites villes, ceintures urbaines (communes de densité intermédiaire) ; bourgs ruraux, rural à habitat "
                        "dispersé, rural à habitat très dispersé (communes rurales). ") + g,
         'agregation': 'texte', 'annee': '2025'},
        {'col': 'dens_niveau_aav_2025', 'libelle': "Niveau de densité croisé avec les aires d'attraction des villes", 'unite': '',
         'definition': ("Niveau de densité à 4 postes : urbain dense, urbain intermédiaire, rural périurbain (commune rurale située "
                        "dans une aire d'attraction des villes de 50 000 habitants ou plus), rural non périurbain (commune rurale "
                        "hors aire d'attraction ou dans une aire de moins de 50 000 habitants). ") + g,
         'agregation': 'texte', 'annee': '2025'}]
    for lib, col in NIV3 + NIV7 + NIVAAV:
        inds.append({'col': col, 'libelle': f'Commune de niveau de densité « {lib} »', 'unite': 'communes',
                     'definition': (f"Vaut 1 si la commune est classée « {lib} » dans la grille de densité, 0 sinon. "
                                    f"Additionnée sur un territoire, donne le nombre de communes de ce niveau. ") + g,
                     'agregation': 'somme', 'annee': '2025'})
    inds.append({'col': 'dens_pop_2023', 'libelle': 'Population municipale 2023 (grille de densité)', 'unite': 'habitants',
                 'definition': "Population municipale 2023 de la commune, telle que diffusée avec la grille de densité. " + g,
                 'agregation': 'somme', 'annee': '2023'})
    noms = {1: 'urbain dense', 2: 'urbain intermédiaire', 3: 'rural'}
    for k in (1, 2, 3):
        inds.append({'col': f'dens_pop_niv{k}_2023', 'libelle': f'Population vivant dans des carreaux de niveau {k} ({noms[k]})',
                     'unite': 'habitants',
                     'definition': (f"Population municipale 2023 de la commune multipliée par la part de sa population qui vit dans des "
                                    f"carreaux de niveau {k} ({noms[k]}) de la grille (variable P{k} de l'Insee). ") + g,
                     'agregation': 'somme', 'annee': '2023'})
    for k in (1, 2, 3):
        inds.append({'col': f'dens_part_pop_niv{k}_2023', 'libelle': f'Part de la population vivant dans des carreaux de niveau {k} ({noms[k]})',
                     'unite': '%',
                     'definition': (f"Part de la population municipale 2023 qui vit dans des carreaux de niveau {k} ({noms[k]}). "
                                    "Recalculée sur un territoire, elle permet de classer ce territoire comme le fait l'Insee : "
                                    "urbain dense si la part du niveau 1 dépasse 50 %, sinon urbain intermédiaire si la part des "
                                    "niveaux 1 et 2 dépasse 50 %, sinon rural. ") + g,
                     'agregation': 'ratio', 'num': f'dens_pop_niv{k}_2023', 'den': 'dens_pop_2023', 'facteur': 100, 'annee': '2023'})
    return [{'theme': 'territoire', 'data': df, 'indicateurs': inds}]
