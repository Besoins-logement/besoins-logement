# -*- coding: utf-8 -*-
"""Reconnaissances de l'état de catastrophe naturelle (arrêtés CatNat) par commune depuis 1982, d'après la base GASPAR de Géorisques."""
import io, shutil, time, urllib.request, zipfile
from pathlib import Path
import pandas as pd
import geo

SOURCE = {'ref': 'P2-069',
          'nom': 'Base GASPAR (Géorisques) : arrêtés de reconnaissance de l état de catastrophe naturelle',
          'producteur': 'Ministère de la Transition écologique (DGPR), diffusion Géorisques (BRGM)',
          'url': 'https://www.data.gouv.fr/datasets/base-nationale-de-gestion-assistee-des-procedures-administratives-relatives-aux-risques-gaspar',
          'telechargement': 'https://files.georisques.fr/GASPAR/gaspar.zip',
          'millesime': 'Export quotidien GASPAR (fichier catnat_gaspar) ; arrêtés publiés au Journal officiel du 21 septembre 1982 à fin janvier 2026',
          'licence': 'Licence ouverte 2.0'}

INONDATION = {'ICB': 'Inondations et/ou coulées de boue', 'IRN': 'Inondations par remontée de nappe', 'COB': 'Coulée de boue',
              'CMV': "Chocs mécaniques liés à l'action des vagues", 'RAZ': 'Raz de marée'}
SECHERESSE = {'SEC': 'Sécheresse (mouvements de terrain différentiels dus à la sécheresse et à la réhydratation des sols)'}
DEBUT_10ANS, FIN_10ANS = '2016-01-01', '2025-12-31'


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
    p = _telecharger(SOURCE['telechargement'], Path(cache) / 'catnat' / 'gaspar.zip')
    with zipfile.ZipFile(p) as zf:
        nom = [n for n in zf.namelist() if n.startswith('catnat_gaspar') and n.endswith('.csv')][0]
        brut = pd.read_csv(io.BytesIO(zf.read(nom)), sep=';', dtype=str,
                           usecols=['id_gaspar', 'code_commune', 'num_risque_jo', 'date_debut', 'date_fin', 'date_signature_arrete'])
    brut['CODGEO'] = geo.vers_cog2026(brut.code_commune.str.strip()).values
    hors = brut.CODGEO.isna().sum()          # Saint-Martin, Saint-Barthélemy, Polynésie... : hors des communes 2026
    brut = brut.dropna(subset=['CODGEO'])
    # Une reconnaissance = un arrêté, un péril, une période ; comptée une fois par commune 2026
    # (une reconnaissance qui visait plusieurs communes fusionnées depuis ne compte qu'une fois pour la commune nouvelle).
    rec = brut.drop_duplicates(['CODGEO', 'id_gaspar', 'num_risque_jo', 'date_debut', 'date_fin']).copy()
    rec['type'] = 'autre'
    rec.loc[rec.num_risque_jo.isin(list(INONDATION)), 'type'] = 'inond'
    rec.loc[rec.num_risque_jo.isin(list(SECHERESSE)), 'type'] = 'sech'
    rec['recent'] = rec.date_signature_arrete.str[:10].between(DEBUT_10ANS, FIN_10ANS)

    def compte(masque, nom_col):
        return rec[masque].groupby('CODGEO').size().rename(nom_col)

    cols = [compte(rec.index == rec.index, 'catnat_total_1982_2026'),
            compte(rec.type == 'inond', 'catnat_inond_1982_2026'),
            compte(rec.type == 'sech', 'catnat_secheresse_1982_2026'),
            compte(rec.type == 'autre', 'catnat_autres_1982_2026'),
            compte(rec.recent, 'catnat_total_2016_2025'),
            compte(rec.recent & (rec.type == 'inond'), 'catnat_inond_2016_2025'),
            compte(rec.recent & (rec.type == 'sech'), 'catnat_secheresse_2016_2025'),
            compte(rec.recent & (rec.type == 'autre'), 'catnat_autres_2016_2025')]
    df = geo.referentiel()[['CODGEO']].merge(pd.concat(cols, axis=1), left_on='CODGEO', right_index=True, how='left')
    for c in df.columns[1:]:
        df[c] = df[c].fillna(0).astype('int64')
    df = df.sort_values('CODGEO').reset_index(drop=True)
    print(f'catnat : {len(rec)} reconnaissances retenues, {hors} lignes hors communes 2026 écartées')

    base = ("Une reconnaissance correspond à un arrêté interministériel de catastrophe naturelle, pour un péril et une période "
            "d'événement donnés, comme dans les listes de Géorisques ; une même reconnaissance qui visait plusieurs communes "
            "fusionnées depuis ne compte qu'une fois pour la commune 2026. Les communes sans reconnaissance valent 0. "
            "Source : base GASPAR, arrêtés publiés au Journal officiel de 1982 à fin janvier 2026 (dernier arrêté présent dans l'export).")
    t_inond = ("inondations et coulées de boue, inondations par remontée de nappe, coulées de boue, chocs mécaniques liés à "
               "l'action des vagues et raz de marée (submersion marine)")
    t_sech = "sécheresse, c'est-à-dire mouvements de terrain différentiels consécutifs à la sécheresse et à la réhydratation des sols (retrait-gonflement des argiles)"
    t_autre = ("tous les autres périls : mouvements de terrain hors sécheresse, glissements, éboulements, effondrements, tempêtes, "
               "vents cycloniques, poids de la neige, grêle, séismes, avalanches, laves torrentielles, éruption volcanique et divers")
    periodes = {'1982_2026': ('depuis 1982', "Tous les arrêtés depuis le début du régime CatNat (1982)."),
                '2016_2025': ('de 2016 à 2025', "Arrêtés signés entre le 1er janvier 2016 et le 31 décembre 2025 (10 dernières années civiles complètes, selon la date de signature de l'arrêté).")}
    inds = []
    for suf, (lib_p, def_p) in periodes.items():
        inds += [
            {'col': f'catnat_total_{suf}', 'libelle': f'Reconnaissances de catastrophe naturelle {lib_p}', 'unite': 'reconnaissances',
             'definition': f"Nombre de reconnaissances de l'état de catastrophe naturelle concernant la commune, tous périls. {def_p} " + base,
             'agregation': 'somme', 'annee': suf.replace('_', '-')},
            {'col': f'catnat_inond_{suf}', 'libelle': f'Reconnaissances de catastrophe naturelle pour inondation {lib_p}', 'unite': 'reconnaissances',
             'definition': f"Nombre de reconnaissances pour inondation au sens large : {t_inond}. {def_p} " + base,
             'agregation': 'somme', 'annee': suf.replace('_', '-')},
            {'col': f'catnat_secheresse_{suf}', 'libelle': f'Reconnaissances de catastrophe naturelle pour sécheresse {lib_p}', 'unite': 'reconnaissances',
             'definition': f"Nombre de reconnaissances pour {t_sech}. {def_p} " + base,
             'agregation': 'somme', 'annee': suf.replace('_', '-')},
            {'col': f'catnat_autres_{suf}', 'libelle': f'Reconnaissances de catastrophe naturelle pour un autre péril {lib_p}', 'unite': 'reconnaissances',
             'definition': f"Nombre de reconnaissances pour {t_autre}. {def_p} " + base,
             'agregation': 'somme', 'annee': suf.replace('_', '-')}]
    return [{'theme': 'risques_energie', 'data': df, 'indicateurs': inds}]
