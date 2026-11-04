# -*- coding: utf-8 -*-
"""Zonages d'étude de l'Insee par commune : aires d'attraction des villes 2020, unités urbaines 2020 et bassins de vie 2022 (géographie 2026)."""
import io, shutil, time, urllib.request, zipfile
from pathlib import Path
import pandas as pd
import geo

URL_AAV = 'https://www.insee.fr/fr/statistiques/fichier/4803954/AAV2020_au_01-01-2026.zip'
URL_UU = 'https://www.insee.fr/fr/statistiques/fichier/4802589/UU2020_au_01-01-2026.zip'
URL_BV = 'https://www.insee.fr/fr/statistiques/fichier/6676988/BV2022_au_01-01-2026.zip'

SOURCE = {'ref': 'E2-08 ; E2-09',
          'nom': "Base des aires d'attraction des villes 2020, base des unités urbaines 2020 et base des bassins de vie 2022",
          'producteur': 'Insee',
          'url': 'https://www.insee.fr/fr/information/4803954 ; https://www.insee.fr/fr/information/4802589 ; https://www.insee.fr/fr/information/6676988',
          'telechargement': f'{URL_AAV} ; {URL_UU} ; {URL_BV}',
          'millesime': 'Zonages AAV 2020, UU 2020 et BV 2022 en géographie au 1er janvier 2026 (mise en ligne le 19 mars 2026) ; tranches de taille calculées sur la population 2017',
          'licence': 'Licence ouverte 2.0'}

CATE_AAV = {'11': 'Commune-centre', '12': 'Autre commune du pôle principal', '13': "Commune d'un pôle secondaire",
            '20': 'Commune de la couronne', '30': 'Commune hors attraction des villes'}
TAILLE_AAV = {'0': 'Hors attraction des villes', '1': 'Aire de moins de 50 000 habitants',
              '2': 'Aire de 50 000 à moins de 200 000 habitants', '3': 'Aire de 200 000 à moins de 700 000 habitants',
              '4': 'Aire de 700 000 habitants ou plus (hors Paris)', '5': 'Aire de Paris'}
STATUT_UU = {'C': 'Ville-centre', 'B': 'Banlieue', 'I': 'Ville isolée', 'H': 'Hors unité urbaine'}
TAILLE_UU = {'0': 'Hors unité urbaine', '1': 'Unité urbaine de 2 000 à 4 999 habitants', '2': 'Unité urbaine de 5 000 à 9 999 habitants',
             '3': 'Unité urbaine de 10 000 à 19 999 habitants', '4': 'Unité urbaine de 20 000 à 49 999 habitants',
             '5': 'Unité urbaine de 50 000 à 99 999 habitants', '6': 'Unité urbaine de 100 000 à 199 999 habitants',
             '7': 'Unité urbaine de 200 000 à 1 999 999 habitants', '8': 'Unité urbaine de Paris'}
CATE_BV = {'00': 'Non pôle', '11': 'Pôle partiel', '12': 'Commune associée à un pôle partiel', '20': 'Pôle'}


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


def _feuille(zp, feuille):
    with zipfile.ZipFile(zp) as zf:
        nom = [n for n in zf.namelist() if n.lower().endswith('.xlsx')][0]
        return pd.read_excel(io.BytesIO(zf.read(nom)), sheet_name=feuille, header=5, dtype=str, engine='calamine')


def _commune_2026(df):
    """Passage en codes 2026 ; ces fichiers sont déjà en géographie 2026, on vérifie l'absence de doublon."""
    df = df.copy()
    df['CODGEO'] = geo.vers_cog2026(df.CODGEO.str.strip()).values
    df = df.dropna(subset=['CODGEO'])
    if df.CODGEO.duplicated().any():
        raise ValueError('fichier Insee attendu en géographie 2026 (une ligne par commune)')
    return df


def _flag(inds, df, col, masque, libelle, definition, annee):
    df[col] = masque.astype('int64')
    inds.append({'col': col, 'libelle': libelle, 'unite': 'communes', 'agregation': 'somme', 'annee': annee,
                 'definition': definition + ' Vaut 1 si oui, 0 sinon ; additionnée sur un territoire, donne le nombre de communes concernées.'})


def charger(cache: Path) -> list:
    d = Path(cache) / 'aav'
    p_aav = _telecharger(URL_AAV, d / 'AAV2020_au_01-01-2026.zip')
    p_uu = _telecharger(URL_UU, d / 'UU2020_au_01-01-2026.zip')
    p_bv = _telecharger(URL_BV, d / 'BV2022_au_01-01-2026.zip')

    aav = _commune_2026(_feuille(p_aav, 'Composition_communale'))
    aav_t = _feuille(p_aav, 'AAV2020')[['AAV2020', 'TAAV2017']]
    aav = aav.merge(aav_t, on='AAV2020', how='left')
    uu = _commune_2026(_feuille(p_uu, 'Composition_communale'))
    uu_t = _feuille(p_uu, 'UU2020')[['UU2020', 'TUU2017']]
    uu = uu.merge(uu_t, on='UU2020', how='left')
    bv = _commune_2026(_feuille(p_bv, 'Composition_communale'))

    df = geo.referentiel()[['CODGEO']].copy()
    df = df.merge(aav[['CODGEO', 'AAV2020', 'LIBAAV2020', 'CATEAAV2020', 'TAAV2017']], on='CODGEO', how='left')
    df = df.merge(uu[['CODGEO', 'UU2020', 'LIBUU2020', 'STATUT_COM_UU', 'TUU2017']], on='CODGEO', how='left')
    df = df.merge(bv[['CODGEO', 'BV2022', 'LIBBV2022', 'TYPE_COMMUNE_BV2022']], on='CODGEO', how='left')
    for col, dico in [('CATEAAV2020', CATE_AAV), ('TAAV2017', TAILLE_AAV), ('STATUT_COM_UU', STATUT_UU),
                      ('TUU2017', TAILLE_UU), ('TYPE_COMMUNE_BV2022', CATE_BV)]:
        inconnu = set(df[col].dropna()) - set(dico)
        if inconnu:
            raise ValueError(f'modalités inattendues dans {col} : {sorted(inconnu)[:5]}')

    out = pd.DataFrame({'CODGEO': df.CODGEO})
    inds = []
    a = "Zonage en aires d'attraction des villes 2020 de l'Insee, en géographie au 1er janvier 2026."
    u = "Zonage en unités urbaines 2020 de l'Insee (continuité du bâti, au moins 2 000 habitants), en géographie au 1er janvier 2026."
    b = "Zonage en bassins de vie 2022 de l'Insee (plus petit territoire où les habitants ont accès aux équipements et services courants), en géographie au 1er janvier 2026."

    out['aav_code_2020'] = df.AAV2020
    out['aav_libelle_2020'] = df.LIBAAV2020
    out['aav_categorie_2020'] = df.CATEAAV2020.map(CATE_AAV)
    out['aav_taille_2020'] = df.TAAV2017.map(TAILLE_AAV)
    inds += [
        {'col': 'aav_code_2020', 'libelle': "Code de l'aire d'attraction des villes", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Code de l'aire d'attraction des villes à laquelle appartient la commune ('000' pour une commune hors attraction des villes). " + a},
        {'col': 'aav_libelle_2020', 'libelle': "Nom de l'aire d'attraction des villes", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Nom de l'aire d'attraction des villes de la commune. " + a},
        {'col': 'aav_categorie_2020', 'libelle': "Catégorie de la commune dans l'aire d'attraction des villes", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': ("Place de la commune dans son aire : commune-centre, autre commune du pôle principal, commune d'un pôle secondaire "
                        "(ces trois catégories forment le pôle), commune de la couronne (au moins 15 % des actifs travaillent dans le pôle), "
                        "ou commune hors attraction des villes. ") + a},
        {'col': 'aav_taille_2020', 'libelle': "Tranche de taille de l'aire d'attraction des villes", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Tranche de population de l'aire d'attraction des villes, calculée par l'Insee sur la population 2017. " + a}]
    cate = df.CATEAAV2020
    _flag(inds, out, 'aav_pole_2020', cate.isin(['11', '12', '13']), "Commune d'un pôle d'aire d'attraction des villes",
          "Commune appartenant au pôle (principal ou secondaire) d'une aire d'attraction des villes. " + a, '2020')
    _flag(inds, out, 'aav_couronne_2020', cate.eq('20'), "Commune de la couronne d'une aire d'attraction des villes",
          "Commune de la couronne d'une aire d'attraction des villes (au moins 15 % de ses actifs travaillent dans le pôle). " + a, '2020')
    _flag(inds, out, 'aav_hors_attraction_2020', cate.eq('30'), 'Commune hors attraction des villes',
          "Commune située hors de toute aire d'attraction des villes. " + a, '2020')
    for code, col in [('1', 'aav_taille_moins50k_2020'), ('2', 'aav_taille_50k_200k_2020'), ('3', 'aav_taille_200k_700k_2020'),
                      ('4', 'aav_taille_700k_plus_2020'), ('5', 'aav_paris_2020')]:
        _flag(inds, out, col, df.TAAV2017.eq(code), f"Commune d'une {TAILLE_AAV[code][0].lower() + TAILLE_AAV[code][1:]}",
              f"Commune appartenant à une aire d'attraction des villes de la tranche « {TAILLE_AAV[code]} » (population 2017). " + a, '2020')

    out['uu_code_2020'] = df.UU2020
    out['uu_libelle_2020'] = df.LIBUU2020
    out['uu_statut_2020'] = df.STATUT_COM_UU.map(STATUT_UU)
    out['uu_taille_2020'] = df.TUU2017.map(TAILLE_UU)
    inds += [
        {'col': 'uu_code_2020', 'libelle': "Code de l'unité urbaine", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Code de l'unité urbaine de la commune (code du type 'dd000' pour les communes hors unité urbaine du département dd). " + u},
        {'col': 'uu_libelle_2020', 'libelle': "Nom de l'unité urbaine", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Nom de l'unité urbaine de la commune. " + u},
        {'col': 'uu_statut_2020', 'libelle': "Statut de la commune dans l'unité urbaine", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Ville-centre, banlieue, ville isolée (unité urbaine d'une seule commune) ou hors unité urbaine, statut calculé par l'Insee sur la population 2017. " + u},
        {'col': 'uu_taille_2020', 'libelle': "Tranche de taille de l'unité urbaine", 'unite': '', 'agregation': 'texte', 'annee': '2020',
         'definition': "Tranche de population de l'unité urbaine, calculée par l'Insee sur la population 2017. " + u}]
    st = df.STATUT_COM_UU
    _flag(inds, out, 'uu_urbaine_2020', st.isin(['C', 'B', 'I']), 'Commune appartenant à une unité urbaine',
          "Commune située dans une unité urbaine (ville-centre, banlieue ou ville isolée). " + u, '2020')
    _flag(inds, out, 'uu_ville_centre_2020', st.eq('C'), "Ville-centre d'unité urbaine", "Commune ville-centre d'une unité urbaine de plusieurs communes. " + u, '2020')
    _flag(inds, out, 'uu_banlieue_2020', st.eq('B'), "Commune de banlieue d'unité urbaine", "Commune de banlieue d'une unité urbaine de plusieurs communes. " + u, '2020')
    _flag(inds, out, 'uu_ville_isolee_2020', st.eq('I'), 'Ville isolée', "Commune formant à elle seule une unité urbaine. " + u, '2020')
    for codes, col, lib in [(['1', '2'], 'uu_taille_moins10k_2020', 'unité urbaine de 2 000 à 9 999 habitants'),
                            (['3', '4'], 'uu_taille_10k_50k_2020', 'unité urbaine de 10 000 à 49 999 habitants'),
                            (['5', '6'], 'uu_taille_50k_200k_2020', 'unité urbaine de 50 000 à 199 999 habitants'),
                            (['7'], 'uu_taille_200k_plus_2020', 'unité urbaine de 200 000 à 1 999 999 habitants'),
                            (['8'], 'uu_paris_2020', 'unité urbaine de Paris')]:
        _flag(inds, out, col, df.TUU2017.isin(codes), f"Commune d'une {lib}",
              f"Commune appartenant à une {lib} (population 2017). " + u, '2020')

    out['bv_code_2022'] = df.BV2022
    out['bv_libelle_2022'] = df.LIBBV2022
    out['bv_categorie_2022'] = df.TYPE_COMMUNE_BV2022.map(CATE_BV)
    inds += [
        {'col': 'bv_code_2022', 'libelle': 'Code du bassin de vie', 'unite': '', 'agregation': 'texte', 'annee': '2022',
         'definition': 'Code du bassin de vie 2022 de la commune. ' + b},
        {'col': 'bv_libelle_2022', 'libelle': 'Nom du bassin de vie', 'unite': '', 'agregation': 'texte', 'annee': '2022',
         'definition': 'Nom du bassin de vie 2022 de la commune. ' + b},
        {'col': 'bv_categorie_2022', 'libelle': 'Catégorie de la commune dans le bassin de vie', 'unite': '', 'agregation': 'texte', 'annee': '2022',
         'definition': "Pôle, pôle partiel, commune associée à un pôle partiel ou non pôle (catégories de l'Insee). " + b}]
    _flag(inds, out, 'bv_pole_2022', df.TYPE_COMMUNE_BV2022.isin(['20', '11']), 'Commune pôle de bassin de vie',
          "Commune classée pôle ou pôle partiel de son bassin de vie (commune qui concentre les équipements et services courants). " + b, '2022')

    out = out.sort_values('CODGEO').reset_index(drop=True)
    return [{'theme': 'territoire', 'data': out, 'indicateurs': inds}]
