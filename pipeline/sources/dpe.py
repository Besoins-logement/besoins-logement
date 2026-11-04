# -*- coding: utf-8 -*-
"""Diagnostics de performance énergétique des logements existants par commune (ADEME, observatoire DPE-Audit) : nombre de DPE par étiquette énergie A à G."""
import json, time, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
import pandas as pd
import geo

JEU = 'dpe03existant'
API = f'https://data.ademe.fr/data-fair/api/v1/datasets/{JEU}/values_agg?'
EXTRACTION = '2026-11-02'          # date de l'extraction mise en cache (le jeu est mis à jour en continu)
PERIODE = '2021_2026'
ETIQ = list('ABCDEFG')


def _url(dep, prefixe=None):
    qs = f'code_departement_ban:"{dep}"' + (f' AND code_insee_ban:{prefixe}*' if prefixe else '')
    return API + urllib.parse.urlencode({'field': 'code_insee_ban;etiquette_dpe', 'agg_size': '1000;10', 'size': 0, 'qs': qs})


SOURCE = {'ref': 'P2-024',
          'nom': "Observatoire DPE-Audit : DPE des logements existants (depuis juillet 2021), nombre de DPE par étiquette énergie et par commune",
          'producteur': "ADEME (observatoire DPE-Audit)",
          'url': 'https://data.ademe.fr/datasets/dpe03existant',
          'telechargement': _url('{code_departement}') + " (API d'agrégation data-fair, une requête par département)",
          'millesime': f"DPE établis du 1er juillet 2021 à l'extraction du {EXTRACTION}",
          'licence': 'Licence ouverte 2.0'}


def _get(url, essais=10):
    for k in range(essais):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'besoins-logement'})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(3 * (k + 1))


def _telecharger(dest):
    """Agrège une seule fois les DPE par commune et étiquette (une requête par département) et enregistre le résultat en CSV."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    lignes = []
    for dep in sorted(geo.referentiel().DEP.dropna().unique()):
        reps = [json.loads(_get(_url(dep)))]
        if reps[0].get('total_other', 0) > 0:      # plus de 1 000 communes : découpage par le 3e caractère du code commune
            reps = [json.loads(_get(_url(dep, dep[:2] + x))) for x in '0123456789']
        for d in reps:
            assert d.get('total_other', 0) == 0, f'agrégation tronquée pour le département {dep}'
            for c in d['aggs']:
                assert c.get('total_other', 0) == 0
                for e in c['aggs']:
                    lignes.append((dep, c['value'], e['value'], e['total']))
    df = pd.DataFrame(lignes, columns=['departement', 'code_insee_ban', 'etiquette_dpe', 'nb_dpe'])
    tmp = dest.with_name(dest.name + '.part')
    df.to_csv(tmp, index=False)
    tmp.replace(dest)
    return dest


def charger(cache: Path) -> list:
    d = pd.read_csv(_telecharger(Path(cache) / 'dpe' / f'dpe_existants_commune_etiquette_{EXTRACTION}.csv'),
                    dtype={'departement': str, 'code_insee_ban': str})
    d = d[d.etiquette_dpe.isin(ETIQ)]
    d['CODGEO'] = geo.vers_cog2026(d.code_insee_ban).values
    d = d.dropna(subset=['CODGEO'])
    out = d.pivot_table(index='CODGEO', columns='etiquette_dpe', values='nb_dpe', aggfunc='sum').reindex(columns=ETIQ).fillna(0)
    out.columns = [f'dpe_nb_{e.lower()}_{PERIODE}' for e in ETIQ]
    out[f'dpe_nb_{PERIODE}'] = out.sum(axis=1)
    out[f'dpe_nb_fg_{PERIODE}'] = out[f'dpe_nb_f_{PERIODE}'] + out[f'dpe_nb_g_{PERIODE}']
    out[f'dpe_part_fg_{PERIODE}'] = out[f'dpe_nb_fg_{PERIODE}'] / out[f'dpe_nb_{PERIODE}'] * 100
    out = out.replace([np.inf, -np.inf], np.nan).reset_index()
    out['CODGEO'] = out.CODGEO.astype(str)

    an = '2021-2026'
    base = (f" DPE des logements existants (maisons, appartements, immeubles) établis depuis le 1er juillet 2021 et transmis à l'ADEME jusqu'au {EXTRACTION} ;"
            " un même logement peut avoir plusieurs DPE et tous les logements n'en ont pas, ce n'est donc pas un décompte du parc."
            " Commune issue du géocodage de l'adresse (Base adresse nationale).")
    ind = [{'col': f'dpe_nb_{e.lower()}_{PERIODE}', 'libelle': f"DPE de logements existants classés {e} (2021 à 2026)", 'unite': 'DPE',
            'definition': f"Nombre de diagnostics de performance énergétique dont l'étiquette énergie est {e}." + base,
            'agregation': 'somme', 'annee': an} for e in ETIQ]
    ind += [
        {'col': f'dpe_nb_{PERIODE}', 'libelle': "DPE de logements existants, toutes étiquettes (2021 à 2026)", 'unite': 'DPE',
         'definition': "Nombre de diagnostics de performance énergétique ayant une étiquette énergie de A à G." + base,
         'agregation': 'somme', 'annee': an},
        {'col': f'dpe_nb_fg_{PERIODE}', 'libelle': "DPE de logements existants classés F ou G (2021 à 2026)", 'unite': 'DPE',
         'definition': "Nombre de diagnostics de performance énergétique dont l'étiquette énergie est F ou G (logements très énergivores, dits passoires énergétiques)." + base,
         'agregation': 'somme', 'annee': an},
        {'col': f'dpe_part_fg_{PERIODE}', 'libelle': "Part des DPE classés F ou G (2021 à 2026)", 'unite': '%',
         'definition': "DPE dont l'étiquette énergie est F ou G divisés par l'ensemble des DPE de la commune." + base,
         'agregation': 'ratio', 'num': f'dpe_nb_fg_{PERIODE}', 'den': f'dpe_nb_{PERIODE}', 'facteur': 100, 'annee': an},
    ]
    out = out[['CODGEO'] + [x['col'] for x in ind]]
    return [{'theme': 'risques_energie', 'data': out, 'indicateurs': ind}]
