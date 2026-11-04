# -*- coding: utf-8 -*-
"""Assemble les sorties des modules (cache/sorties) en une base publiée dans docs/data :
- un fichier Parquet par thème, une ligne par territoire des sept niveaux (France, régions, départements, zones d'emploi, EPCI,
  territoires d'industrie, communes) ;
- territoires.parquet (appartenances, pour les filtres), dictionnaire (parquet et csv), sources.csv (catalogue), meta.json.
Règles d'agrégation : somme des communes ; ratio recalculé (somme du numérateur / somme du dénominateur) ; valeur publiée par la source
quand elle existe, sinon moyenne pondérée, pour les indicateurs non additifs ; texte à la commune seulement."""
import json, glob, re, datetime
from pathlib import Path
import numpy as np, pandas as pd
import geo

RACINE = geo.RACINE
SORTIES = geo.CACHE / 'sorties'
PUB = RACINE / 'docs' / 'data'
REGISTRE = RACINE / 'pipeline' / 'catalogue' / 'registre_sources.csv'
THEMES = {'territoire': 'Territoire et zonages', 'population': 'Population', 'menages': 'Ménages et familles', 'profils': 'Profils de ménages',
          'logement': 'Logement (parc existant)', 'construction': 'Construction neuve', 'besoins': 'Besoins en logement',
          'marche': 'Marché et prix', 'revenus': 'Revenus et aides', 'emploi': 'Emploi et activité', 'economie': 'Entreprises et salaires',
          'equipements': 'Équipements et services', 'risques_energie': 'Risques, climat et énergie'}
NIVEAUX = [('France', None, None), ('Région', 'REG', None), ('Département', 'DEP', None), ("Zone d'emploi", 'ZE2020', 'LIBZE2020'),
           ('EPCI', 'EPCI', 'LIBEPCI'), ("Territoire d'industrie", 'id_ti', 'lib_ti'), ('Commune', 'CODGEO', 'LIBGEO')]
CLE_PUB = {'Région': 'REG', 'Département': 'DEP', "Zone d'emploi": 'ZE2020', 'EPCI': 'EPCI', 'France': 'FRANCE'}


def theme_publie(nom_bloc, meta):
    """Thème de la base où sont publiés les indicateurs d'un bloc (quelques blocs sont rangés hors de leur thème déclaré)."""
    cols = [d['col'] for d in meta['indicateurs']]
    if cols and all(c.startswith('prof_') for c in cols):
        return 'profils'
    if nom_bloc.startswith('rp_menages'):
        return 'menages'
    if nom_bloc.startswith('economie_insee'):
        return 'economie'
    return meta['theme']


def charger_sorties():
    blocs = []
    for j in sorted(glob.glob(str(SORTIES / '*.json'))):
        meta = json.load(open(j, encoding='utf-8'))
        base = j[:-5]
        df = pd.read_parquet(base + '.parquet')
        pub = {}
        for p in glob.glob(base + '_publie_*.parquet'):
            pub[p.rsplit('_publie_', 1)[1][:-8]] = pd.read_parquet(p)
        theme = theme_publie(Path(base).name, meta)
        blocs.append({'id': Path(base).name, 'theme': theme, 'data': df, 'indicateurs': meta['indicateurs'], 'publies': pub, 'source': meta.get('source', {})})
    return blocs


def appartenances(ref):
    reg, dep = geo.libelles_niveaux()
    t = ref.copy()
    t['LIBREG'] = t.REG.map(reg); t['LIBDEP'] = t.DEP.map(dep)
    return t, reg, dep


def agreger_theme(blocs, ref, reg, dep, pop):
    """Renvoie (table empilée des sept niveaux, liste des indicateurs)."""
    com = ref[['CODGEO']].copy()
    inds, pubs = [], {}
    for b in blocs:
        d = b['data']
        new = [c for c in d.columns if c != 'CODGEO' and c not in com.columns]
        com = com.merge(d[['CODGEO'] + new], on='CODGEO', how='left')
        for x in b['indicateurs']:
            if x['col'] in new:
                y = dict(x); y['_source'] = b['source']; y['_bloc'] = b['id']; inds.append(y)
        for niv, p in b['publies'].items():
            pubs.setdefault(niv, []).append(p)
    pubs = {k: pd.concat([p.set_index('CODE') for p in v], axis=1) for k, v in pubs.items()}
    pubs = {k: v.loc[:, ~v.columns.duplicated()] for k, v in pubs.items()}
    base = ref.merge(com, on='CODGEO', how='left')
    som = [x['col'] for x in inds if x['agregation'] == 'somme']
    rat = [x for x in inds if x['agregation'] == 'ratio']
    nad = [x for x in inds if x['agregation'] == 'non_additif']
    txt = [x['col'] for x in inds if x['agregation'] == 'texte']
    besoin_num = sorted({x['num'] for x in rat} | {x['den'] for x in rat} | {x['poids'] for x in nad if x.get('poids')})
    out = []
    for niv, key, lab in NIVEAUX:
        if key is None:
            grp = pd.Series('FR', index=base.index)
        else:
            grp = base[key]
        m = grp.notna()
        b = base[m]; g = grp[m]
        cols_sum = sorted(set(som) | set(besoin_num))
        agg = b[cols_sum].groupby(g.values).sum(min_count=1) if cols_sum else pd.DataFrame(index=pd.Index(sorted(g.unique())))
        if niv == 'Commune':
            agg = b.set_index('CODGEO')[[c for c in base.columns if c in {x['col'] for x in inds}]]
        else:
            for x in rat:
                agg[x['col']] = agg[x['num']] / agg[x['den']].replace(0, np.nan) * x.get('facteur', 1)
            for x in nad:
                c = x['col']; val = pd.Series(np.nan, index=agg.index)
                if x.get('poids') and x['poids'] in b.columns:
                    w = b[x['poids']].where(b[c].notna())
                    num = (b[c] * w).groupby(g.values).sum(min_count=1); den = w.groupby(g.values).sum(min_count=1)
                    val = (num / den.replace(0, np.nan)).reindex(agg.index)
                kp = CLE_PUB.get(niv)
                if kp in pubs and c in pubs[kp].columns:
                    pv = pubs[kp][c]
                    if niv == 'France': pv = pv.rename(index={k: 'FR' for k in pv.index})
                    val = pv.reindex(agg.index).combine_first(val)
                agg[c] = val
            for c in txt:
                agg[c] = np.nan
        agg = agg.reset_index().rename(columns={'index': 'code', 'CODGEO': 'code'})
        if 'code' not in agg.columns: agg = agg.rename(columns={agg.columns[0]: 'code'})
        if niv == 'France': agg['nom'] = 'France'
        elif niv == 'Région': agg['nom'] = agg.code.map(reg)
        elif niv == 'Département': agg['nom'] = agg.code.map(dep)
        else: agg['nom'] = agg.code.map(base.drop_duplicates(key).set_index(key)[lab])
        agg.insert(0, 'niveau', niv)
        out.append(agg)
    t = pd.concat(out, ignore_index=True)
    cols = ['niveau', 'code', 'nom'] + [x['col'] for x in inds]
    t = t[cols]
    for x in inds:
        c = x['col']
        if x['agregation'] != 'texte':
            t[c] = pd.to_numeric(t[c], errors='coerce').round(2 if x['agregation'] != 'somme' else 1)
    return t, inds


def synthese_besoins(tabs):
    """Colonnes de synthèse du bloc 1, recalculées à chaque niveau : besoin en construction par décennie, comparaison 2030-2040."""
    if 'besoins' not in tabs or 'construction' not in tabs: return []
    b, c = tabs['besoins'], tabs['construction']
    new = []
    for d, lab in [('2030', '2020-2030'), ('3040', '2030-2040'), ('4050', '2040-2050')]:
        comp = [f'bes_{k}_{d}' for k in ['menages', 'fluidite', 'res_secondaires', 'renouvellement', 'mal_logement']]
        b[f'bes_besoin_avant_vacants_{d}'] = b[comp].sum(axis=1, min_count=1).round(1)
        b[f'bes_besoin_construction_{d}'] = (b[f'bes_besoin_avant_vacants_{d}'] - b[f'bes_vacants_mobilises_{d}']).round(1)
        new += [(f'bes_besoin_avant_vacants_{d}', f'Besoin avant vacants {lab}', 'logements par an', 'Ménages + fluidité + résidences secondaires + renouvellement + mal-logement.'),
                (f'bes_besoin_construction_{d}', f'Besoin en construction {lab}', 'logements par an', 'Besoin avant vacants - vacants remis sur le marché (formule de la CERC AURA, sans la composante industrie).')]
    key = c.niveau + '|' + c.code.astype(str)
    cons = pd.Series(c['sit_construction_actuelle'].values, index=key)
    kb = b.niveau + '|' + b.code.astype(str)
    b['bes_construction_actuelle'] = kb.map(cons).where(b['bes_besoin_construction_3040'].notna()).round(1).values
    # construction hors Mayotte pour la France (le besoin exclut Mayotte)
    may = c[(c.niveau == 'Département') & (c.code == '976')]['sit_construction_actuelle']
    if len(may):
        b.loc[b.niveau == 'France', 'bes_construction_actuelle'] -= float(may.iloc[0])
    b['bes_manque_3040'] = (b.bes_besoin_construction_3040 - b.bes_construction_actuelle).round(1)
    b['bes_couverture_3040'] = (b.bes_construction_actuelle / b.bes_besoin_construction_3040.where(b.bes_besoin_construction_3040 > 0)).round(4)
    cl = np.where(b.bes_besoin_construction_3040.isna(), np.nan,
                  np.where(b.bes_construction_actuelle >= b.bes_besoin_avant_vacants_3040, 1,
                           np.where(b.bes_construction_actuelle >= b.bes_besoin_construction_3040, 2, 3)))
    b['bes_classe_3040'] = cl
    lib = {1: 'Couvert si la construction se maintient', 2: 'Couvert avec la remise sur le marché des vacants', 3: 'Non couvert, même avec les vacants remis sur le marché'}
    b['bes_conclusion_3040'] = pd.Series(cl).map(lib).fillna('Hors champ (Mayotte)').values
    new += [('bes_construction_actuelle', 'Construction actuelle (mises en chantier par an, 2023-2025)', 'logements par an', 'Même valeur que dans le thème Construction ; France sans Mayotte, hors champ du besoin.'),
            ('bes_manque_3040', 'Logements manquants par an 2030-2040', 'logements par an', 'Besoin en construction 2030-2040 - construction actuelle (positif : manque).'),
            ('bes_couverture_3040', 'Taux de couverture 2030-2040', 'part (1 = 100 %)', 'Construction actuelle / besoin en construction 2030-2040.'),
            ('bes_classe_3040', 'Classe de conclusion 2030-2040', '1, 2 ou 3', '1 : la construction actuelle couvre le besoin sans les vacants ; 2 : elle ne le couvre qu\'avec eux ; 3 : elle ne le couvre pas.'),
            ('bes_conclusion_3040', 'Conclusion 2030-2040', '', 'Libellé de la classe (même règle que la CERC AURA).')]
    return [{'col': c_, 'libelle': l, 'unite': u, 'definition': d_ + ' Calcul de la base (bloc 1).', 'agregation': 'texte' if c_ == 'bes_conclusion_3040' else 'calcul',
             'annee': '2030-2040' if '3040' in c_ else '', '_source': {'ref': 'P2-056, B1-02', 'nom': 'Calcul de la base à partir du SDES et de Sitadel', 'producteur': 'Projet Besoins en logement'}} for c_, l, u, d_ in new]


def main():
    PUB.mkdir(parents=True, exist_ok=True)
    blocs = charger_sorties()
    ref, reg, dep = appartenances(geo.referentiel())
    tabs, dico = {}, []
    for th in THEMES:
        bl = [b for b in blocs if b['theme'] == th]
        if not bl: continue
        t, inds = agreger_theme(bl, ref, reg, dep, None)
        tabs[th] = t
        for x in inds: x['theme'] = th
        dico += inds
    extra = synthese_besoins(tabs)
    for x in extra: x['theme'] = 'besoins'
    dico += extra
    for th, t in tabs.items():
        t.to_parquet(PUB / f'{th}.parquet', index=False, compression='zstd', compression_level=12)
        (PUB / 'csv').mkdir(exist_ok=True)
        t.to_csv(PUB / 'csv' / f'{th}.csv.gz', sep=';', index=False, encoding='utf-8-sig', compression={'method': 'gzip', 'compresslevel': 9, 'mtime': 0})
    # territoires et appartenances (pour les filtres du site)
    terr = tabs[next(iter(tabs))][['niveau', 'code', 'nom']].copy()
    com = ref.rename(columns={'CODGEO': 'code'})
    terr = terr.merge(com[['code', 'DEP', 'LIBDEP', 'REG', 'LIBREG', 'ZE2020', 'LIBZE2020', 'EPCI', 'LIBEPCI', 'id_ti', 'lib_ti']].assign(niveau='Commune'), on=['niveau', 'code'], how='left')
    pop = ref.copy()
    for niv, key in [('Département', 'DEP'), ("Zone d'emploi", 'ZE2020'), ('EPCI', 'EPCI'), ("Territoire d'industrie", 'id_ti')]:
        dom = pop.dropna(subset=[key]).groupby(key).agg(REG=('REG', lambda s: s.mode().iat[0]), DEP=('DEP', lambda s: s.mode().iat[0]))
        m = terr.niveau == niv
        terr.loc[m, 'REG'] = terr.loc[m, 'code'].map(dom.REG)
        if niv != 'Département': terr.loc[m, 'DEP'] = terr.loc[m, 'code'].map(dom.DEP)
    terr.loc[terr.niveau == 'Région', 'REG'] = terr.loc[terr.niveau == 'Région', 'code']
    terr['LIBREG'] = terr.REG.map(reg); terr['LIBDEP'] = terr.DEP.map(dep)
    terr.columns = [c.lower() for c in terr.columns]
    terr.to_parquet(PUB / 'territoires.parquet', index=False, compression='zstd')
    terr.to_csv(PUB / 'csv' / 'territoires.csv.gz', sep=';', index=False, encoding='utf-8-sig', compression={'method': 'gzip', 'compresslevel': 9, 'mtime': 0})
    # dictionnaire
    rows = []
    for x in dico:
        s = x.get('_source', {})
        t = tabs[x['theme']]
        cov = int(t.loc[t.niveau == 'Commune', x['col']].notna().sum()) if x['col'] in t.columns else 0
        rows.append({'theme': x['theme'], 'theme_libelle': THEMES[x['theme']], 'colonne': x['col'], 'libelle': x.get('libelle', ''), 'unite': x.get('unite', ''),
                     'definition': x.get('definition', ''), 'annee': str(x.get('annee', '')), 'agregation': x['agregation'],
                     'numerateur': x.get('num', ''), 'denominateur': x.get('den', ''), 'poids': x.get('poids', ''),
                     'source_ref': s.get('ref', ''), 'source': s.get('nom', ''), 'producteur': s.get('producteur', ''), 'adresse': s.get('url', ''),
                     'millesime': s.get('millesime', ''), 'licence': s.get('licence', ''), 'communes_renseignees': cov})
    dic = pd.DataFrame(rows)
    dic.to_parquet(PUB / 'dictionnaire.parquet', index=False, compression='zstd')
    dic.to_csv(PUB / 'dictionnaire.csv', index=False, encoding='utf-8-sig')
    # catalogue des sources
    if REGISTRE.exists():
        cat = pd.read_csv(REGISTRE, dtype=str)
        refs = set()
        for b in blocs:
            for r in re.split(r'[,;\s]+', str(b['source'].get('ref', ''))):
                if r: refs.add(r)
        cat['integration'] = np.where(cat['Réf.'].isin(refs), 'Intégrée', cat.get('integration', ''))
        nouv = []
        for b in blocs:
            s = b['source']; r = str(s.get('ref', ''))
            if r and not any(x in set(cat['Réf.']) for x in re.split(r'[,;\s]+', r)) and r not in [n['Réf.'] for n in nouv]:
                nouv.append({'Réf.': r, 'Source': s.get('nom', ''), 'Producteur': s.get('producteur', ''), 'Adresse': s.get('url', ''), 'Millésime': s.get('millesime', ''),
                             'Licence': s.get('licence', ''), 'integration': 'Intégrée', 'Type': 'Jeu de données'})
        cat = pd.concat([cat, pd.DataFrame(nouv)], ignore_index=True)
        cat.to_csv(PUB / 'sources.csv', index=False, encoding='utf-8-sig')
    meta = {'mise_a_jour': datetime.date.today().isoformat(), 'geographie': 'COG 2026 (34 875 communes)',
            'themes': {th: {'libelle': THEMES[th], 'fichier': f'{th}.parquet', 'indicateurs': int((dic.theme == th).sum())} for th in tabs},
            'niveaux': [n for n, _, _ in NIVEAUX], 'indicateurs': int(len(dic)), 'territoires': int(len(terr))}
    json.dump(meta, open(PUB / 'meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('thèmes :', {th: (len(t), t.shape[1] - 3, round((PUB / f'{th}.parquet').stat().st_size / 1e6, 1)) for th, t in tabs.items()})
    print('indicateurs :', len(dic), '| territoires :', len(terr))


if __name__ == '__main__':
    main()
