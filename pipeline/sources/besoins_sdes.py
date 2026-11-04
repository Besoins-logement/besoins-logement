# -*- coding: utf-8 -*-
"""Bloc 1 : besoin en logements par commune (méthode SDES juin 2025, scénario haut, hypothèses de la CERC AURA, sans l'industrie).
Composantes calculées par le SDES à la zone d'emploi, réparties entre les communes (clés : résidences principales, résidences secondaires,
logements vacants du recensement 2023 ; renouvellement au prorata du besoin lié aux ménages 2020-2050)."""
import io, time, urllib.request, zipfile
from pathlib import Path
import numpy as np, pandas as pd, openpyxl
import geo

SDES = 'https://www.statistiques.developpement-durable.gouv.fr/media/{}/download?inline'
RP_URL = 'https://api.insee.fr/melodi/file/DS_RP_SERIE_HISTORIQUE/DS_RP_SERIE_HISTORIQUE_2023_CSV_FR'
SOURCE = {'ref': 'P2-056', 'nom': 'Besoins en logements à horizon 2030, 2040 et 2050 - fichiers de données (SDES, juin 2025)',
          'producteur': 'SDES', 'url': 'https://www.statistiques.developpement-durable.gouv.fr/besoins-en-logements-horizon-2030-2040-et-2050',
          'telechargement': SDES.format('8509') + ' ; 8510 ; 8511 ; 8512 ; 8477', 'millesime': 'Juin 2025', 'licence': 'Licence ouverte 2.0'}
GROUPES = ['2406+2415+2701+2818+5204+8429', '9402+9403+9404+9405', '9401+9406+9407', '2801+2812', '8411+9302']
DOM = ['971', '972', '973', '974']
DEC = [('2030', '2020-2030', 4), ('3040', '2030-2040', 10), ('4050', '2040-2050', 2)]

def _get(url, dst):
    dst = Path(dst)
    if dst.exists(): return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    for k in range(5):
        try:
            with urllib.request.urlopen(url, timeout=900) as r:
                dst.with_suffix('.part').write_bytes(r.read())
            dst.with_suffix('.part').replace(dst); return dst
        except Exception:
            time.sleep(10 * (k + 1))
    raise RuntimeError(url)

def _sheet(path, name, header_row, data_start):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[name].iter_rows(values_only=True))
    cols = [str(c) if c is not None else f'_c{i}' for i, c in enumerate(rows[header_row])]
    df = pd.DataFrame([r[:len(cols)] for r in rows[data_start:] if r[0] is not None], columns=cols)
    df.iloc[:, 0] = df.iloc[:, 0].astype(str).str.strip()
    return df

def _code4(c):
    c = str(c)
    return c.zfill(4) if c.isdigit() and len(c) < 4 and not c.startswith('97') else c

def _rp(cache):
    z = _get(RP_URL, Path(cache) / 'insee' / 'DS_RP_SERIE_HISTORIQUE_2023_CSV_FR.zip')
    rows = []
    with zipfile.ZipFile(z) as zf:
        n = [i for i in zf.namelist() if i.endswith('_data.csv')][0]
        for ch in pd.read_csv(zf.open(n), sep=';', dtype=str, chunksize=500_000, usecols=['GEO', 'GEO_OBJECT', 'TIME_PERIOD', 'RP_MEASURE', 'OCS', 'OBS_VALUE']):
            rows.append(ch[(ch.GEO_OBJECT == 'COM') & (ch.RP_MEASURE == 'DWELLINGS') & ch.TIME_PERIOD.str.startswith('2023')])
    rp = pd.concat(rows)
    rp['v'] = pd.to_numeric(rp.OBS_VALUE.str.replace(',', '.'))
    rp['CODGEO'] = geo.vers_cog2026(rp.GEO).values
    return rp.pivot_table(index='CODGEO', columns='OCS', values='v', aggfunc='sum')

def charger(cache):
    cache = Path(cache)
    f = {k: _get(SDES.format(k), cache / 'sdes' / f'sdes_{k}.xlsx') for k in ['8509', '8510', '8511', '8512', '8477']}
    ref = geo.referentiel()[['CODGEO', 'DEP', 'ZE2020']].copy()
    rp = _rp(cache)
    for c, k in [('rp', 'DW_MAIN'), ('rs', 'DW_SEC_DW_OCC'), ('vac', 'DW_VAC')]:
        ref[c] = ref.CODGEO.map(rp[k])
    g = {z: grp for grp in GROUPES for z in grp.split('+')}
    ref['unite'] = np.where(ref.DEP.isin(DOM), ref.DEP, ref.ZE2020.map(lambda z: g.get(z, z)))
    ref.loc[ref.DEP == '976', 'unite'] = None
    ref['ze_k'] = np.where(ref.DEP.isin(DOM), ref.DEP, ref.ZE2020)
    def part(col, key):
        s = ref.groupby(key)[col].transform('sum'); p = ref[col] / s
        pf = ref['rp'] / ref.groupby(key)['rp'].transform('sum')
        return p.where(s > 0, pf).fillna(0)
    k_u, k_ze, k_rs, k_vac = part('rp', 'unite'), part('rp', 'ze_k'), part('rs', 'ze_k'), part('vac', 'unite')
    men = _sheet(f['8509'], '2.III - Population haute', 1, 2).rename(columns={'ze2020': 'unite'}); men['unite'] = men.unite.map(_code4); men = men.set_index('unite')
    vc = _sheet(f['8512'], '5.I - VC - Population haute', 1, 2).rename(columns={'ZE2020': 'unite'}); vc['unite'] = vc.unite.map(_code4); vc = vc.set_index('unite')
    rs = _sheet(f['8511'], '4.II - Population haute', 1, 2).rename(columns={'ZE2020': 'ze'}); rs['ze'] = rs.ze.map(_code4); rs = rs.set_index('ze')
    rsd = pd.read_excel(f['8511'], sheet_name='4.II - DOM', header=1, engine='calamine'); rsd['DEP'] = rsd.DEP.astype(str)
    rs = pd.concat([rs[['rs_2030', 'rs_3040', 'rs_4050']], rsd.set_index('DEP')[['rs_2030', 'rs_3040', 'rs_4050']]])
    vl = _sheet(f['8512'], '5.III - Vacance longue', 2, 3).rename(columns={'ze2020': 'unite'}); vl['unite'] = vl.unite.map(_code4); vl = vl.set_index('unite')
    pr = _sheet(f['8510'], '3.II - Privation de logement', 1, 2).rename(columns={'ZE2020': 'ze'}); pr['ze'] = pr.ze.map(_code4)
    tp = _sheet(f['8510'], '3.III - Logements trop petits', 1, 2).rename(columns={'ze2020': 'ze'}); tp['ze'] = tp.ze.map(_code4)
    dg = _sheet(f['8510'], '3.IV - Logements dégradés', 1, 2).rename(columns={'ZE2020': 'ze'}); dg['ze'] = dg.ze.map(_code4)
    stock = (pr.set_index('ze').situa_2021.astype(float) + tp.set_index('ze').tot_nr_inf25.astype(float) + dg.set_index('ze').situa_2021.astype(float))
    f56 = pd.read_excel(f['8477'], sheet_name='Figure 56', header=None, engine='calamine')
    ren_nat = {d: float(f56.iloc[i, 5]) for (d, _, _), i in zip(DEC, [5, 6, 7])}
    out = ref[['CODGEO']].copy(); inds = []
    S = ' Source : SDES, Besoins en logements à horizon 2030, 2040 et 2050 (juin 2025), scénario haut ; hypothèses de la CERC AURA.'
    for d, lab, _ in DEC:
        out[f'bes_menages_{d}'] = ref.unite.map(men[f'proj{d}'].astype(float)) * k_u / 10
        out[f'bes_fluidite_{d}'] = ref.unite.map(vc[f'vc_{d}'].astype(float)) * k_u / 10
        out[f'bes_res_secondaires_{d}'] = ref.ze_k.map(rs[f'rs_{d}'].astype(float)) * k_rs / 10
    need = out[[f'bes_menages_{d}' for d, _, _ in DEC]].sum(axis=1)
    for d, lab, n in DEC:
        out[f'bes_renouvellement_{d}'] = ren_nat[d] * need / need.sum()
        out[f'bes_mal_logement_{d}'] = ref.ze_k.map(stock) * k_ze / 16 * n / 10
    sur = (vl.vl.astype(float) - 0.05 * vl.log.astype(float)).clip(lower=0)
    cap = men[[f'proj{d}' for d, _, _ in DEC]].astype(float).sum(axis=1).reindex(sur.index).clip(lower=0)
    mob = np.minimum(sur, cap)
    out['bes_vacants_mobilisables'] = ref.unite.map(mob) * k_vac
    out['bes_stock_mal_logement'] = ref.ze_k.map(stock) * k_ze
    for d, lab, _ in DEC:
        out[f'bes_vacants_mobilises_{d}'] = out.bes_vacants_mobilisables / 30
    mayotte = ref.DEP == '976'
    out.loc[mayotte.values, [c for c in out.columns if c != 'CODGEO']] = np.nan
    LIB = {'menages': ('Croissance des ménages', "Logements à ajouter parce que le nombre de ménages augmente ; nul dans une zone d'emploi où les ménages baissent. Réparti au prorata des résidences principales 2023."),
           'fluidite': ('Fluidité du parc', 'Vacance de courte durée nécessaire aux déménagements. Répartie au prorata des résidences principales 2023.'),
           'res_secondaires': ('Résidences secondaires nouvelles', 'Évolution du nombre de résidences secondaires. Répartie au prorata des résidences secondaires 2023.'),
           'renouvellement': ('Renouvellement du parc', 'Démolitions, fusions et transformations à remplacer, avec l\'effet du ZAN ; total national réparti au prorata du besoin lié aux ménages 2020-2050.'),
           'mal_logement': ('Résorption du mal-logement', 'Stock 2021 (privation de logement + trop petits de 25 m2 ou moins + très dégradés) résorbé entre 2027 et 2042.'),
           'vacants_mobilises': ('Vacants remis sur le marché (en moins)', 'Logements vacants depuis un an ou plus au-delà de 5 % du parc, dans la limite du besoin lié aux ménages, sur 30 ans ; à retrancher du besoin.')}
    for d, lab, _ in DEC:
        for k, (l, defi) in LIB.items():
            inds.append({'col': f'bes_{k}_{d}', 'libelle': f'{l} {lab}', 'unite': 'logements par an', 'definition': defi + S, 'agregation': 'somme', 'annee': lab})
    inds += [{'col': 'bes_vacants_mobilisables', 'libelle': 'Logements vacants mobilisables 2020-2050', 'unite': 'logements', 'definition': 'Total sur 30 ans.' + S, 'agregation': 'somme', 'annee': '2020-2050'},
             {'col': 'bes_stock_mal_logement', 'libelle': 'Stock de mal-logement 2021', 'unite': 'logements', 'definition': 'Privation de logement en propre + logements trop petits de 25 m2 ou moins non réallouables + logements très dégradés.' + S, 'agregation': 'somme', 'annee': '2021'}]
    return [{'theme': 'besoins', 'data': out, 'indicateurs': inds}]
