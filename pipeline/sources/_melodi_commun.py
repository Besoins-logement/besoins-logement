# -*- coding: utf-8 -*-
"""Outils communs aux modules Insee Melodi (pas une source : aucun charger()).
Lecture des zips CSV Melodi déposés dans cache/melodi/, choix des séries, passage en colonnes communales COG 2026,
valeurs publiées aux niveaux supra-communaux pour les indicateurs non additifs.

Règles appliquées à chaque jeu (paramétrées par un dictionnaire `jeu`, voir traiter()) :
- niveau communal = GEO_OBJECT 'COM', codes passés par geo.vers_cog2026(), effectifs additionnés si plusieurs
  anciennes communes tombent dans une commune 2026 (somme vide si l'une des parties est secrète) ;
- dernière période de chaque série ; périodes antérieures seulement pour les séries dont toutes les dimensions
  (hors mesure) sont au total ;
- au plus `max_dims` dimensions hors total par série (2 par défaut) ; une dimension qui ne prend qu'une valeur pour
  une mesure (par exemple OCS = résidences principales) est considérée comme fixe et ne compte pas ;
- valeurs secrètes, manquantes ou « incluses dans une autre catégorie » (statut K) : vides, jamais 0.
"""
import os, re, time, zipfile, unicodedata, functools, json, urllib.request, urllib.error, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.compute as pc
import geo

API = 'https://api.insee.fr/melodi'
NIVEAUX_PUBLIES = ('EPCI', 'DEP', 'REG', 'ZE2020', 'FRANCE')
HORS_DIM = {'GEO', 'GEO_OBJECT', 'TIME_PERIOD', 'OBS_VALUE', 'OBS_STATUS', 'OBS_STATUS_FR', 'OBS_STATUS_EN', 'FREQ',
            'UNIT_MULT', 'DECIMALS', 'CONF_STATUS', 'UNIT_MEASURE', 'UNIT', 'NOTE'}
CODES_COMMUNS = {('SEX', 'F'): ('femmes', 'femmes'), ('SEX', 'M'): ('hommes', 'hommes')}


# ---------------------------------------------------------------- téléchargement
def url_csv(ds):
    with urllib.request.urlopen(f'{API}/catalog/{ds}', timeout=120) as r:
        cat = json.loads(r.read())
    trouve = []
    def w(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'accessURL' and isinstance(v, str) and v.endswith('_CSV_FR'): trouve.append(v)
                w(v)
        elif isinstance(o, list):
            for v in o: w(v)
    w(cat)
    if not trouve: raise RuntimeError(f'{ds} : pas de fichier CSV dans le catalogue Melodi')
    return trouve[0]

def _telecharger(url, dst, morceau=8 << 20, essais=8):
    """Téléchargement par plages de 8 Mo avec reprise (les connexions longues vers api.insee.fr se figent vers 22 Mo)."""
    pos = dst.stat().st_size if dst.exists() else 0
    total = None
    with open(dst, 'ab') as f:
        while total is None or pos < total:
            for k in range(essais):
                try:
                    req = urllib.request.Request(url, headers={'Range': f'bytes={pos}-{pos + morceau - 1}'})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        if r.status == 200:          # serveur sans plages : fichier entier
                            f.seek(0); f.truncate(); f.write(r.read()); return
                        total = int(r.headers['Content-Range'].split('/')[-1])
                        data = r.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 416 and pos > 0: return    # fichier déjà complet
                    if k == essais - 1: raise
                    time.sleep(5 * (k + 1))
                except Exception:
                    if k == essais - 1: raise
                    time.sleep(5 * (k + 1))
            f.write(data); f.flush(); pos += len(data)

def zip_melodi(ds, cache):
    """Chemin du zip CSV du jeu dans cache/melodi/ ; le télécharge une seule fois. None si un autre processus
    est en train de le télécharger (fichier .part récent) : on ne lance jamais de second téléchargement.
    Sur le robot (variable CI, un seul processus), un .part récent vient d'un essai interrompu : on le reprend."""
    d = Path(cache) / 'melodi'; d.mkdir(parents=True, exist_ok=True)
    z = d / f'{ds}_CSV_FR.zip'
    if z.exists(): return z
    part = d / f'{ds}_CSV_FR.zip.part'
    if part.exists() and not os.environ.get('CI') and time.time() - part.stat().st_mtime < 900:
        warnings.warn(f'{ds} : téléchargement en cours par un autre processus, jeu laissé de côté pour cette exécution')
        return None
    _telecharger(url_csv(ds), part)
    with zipfile.ZipFile(part) as zf:
        if zf.testzip() is not None: raise RuntimeError(f'{ds} : zip corrompu')
    part.rename(z)
    return z


# ---------------------------------------------------------------- lecture
@functools.lru_cache(maxsize=4)
def lire(ds, cache, niveaux=('COM',), totaux_anciens=None):
    """Observations du jeu pour les niveaux demandés : DataFrame (dimensions en catégories, OBS_VALUE en float)
    et métadonnées (COD_VAR, LIB_VAR, COD_MOD, LIB_MOD). None si le zip n'est pas disponible.
    totaux_anciens : ((dim, code total), ...) pour les très gros jeux : seules la dernière période et, pour les
    périodes antérieures, les lignes où ces dimensions sont au total sont lues (économie de mémoire)."""
    z = zip_melodi(ds, cache)
    if z is None: return None
    with zipfile.ZipFile(z) as zf:
        dn = next(n for n in zf.namelist() if n.endswith('_data.csv'))
        mn = next(n for n in zf.namelist() if n.endswith('_metadata.csv'))
        meta = pd.read_csv(zf.open(mn), sep=';', dtype=str)
        with zf.open(dn) as f:
            entete = [c.strip().strip('"') for c in f.readline().decode('utf-8-sig').split(';')]
        garde = [c for c in entete if c not in ('FREQ', 'OBS_STATUS_FR', 'OBS_STATUS_EN')]
        vs = pa.array(list(niveaux))
        der = None
        if totaux_anciens:
            with zf.open(dn) as f:
                rd = pacsv.open_csv(f, read_options=pacsv.ReadOptions(block_size=1 << 25),
                                    parse_options=pacsv.ParseOptions(delimiter=';'),
                                    convert_options=pacsv.ConvertOptions(column_types={'TIME_PERIOD': pa.string()},
                                                                         include_columns=['TIME_PERIOD']))
                der = max(pc.max(b['TIME_PERIOD']).as_py() or '' for b in rd)
        morceaux = []
        with zf.open(dn) as f:
            rd = pacsv.open_csv(f, read_options=pacsv.ReadOptions(block_size=1 << 25),
                                parse_options=pacsv.ParseOptions(delimiter=';'),
                                convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in entete},
                                                                     include_columns=garde, strings_can_be_null=True))
            for b in rd:
                masque = pc.is_in(b['GEO_OBJECT'], value_set=vs)
                if der is not None:
                    tot = pc.equal(b['TIME_PERIOD'], der)
                    anc = None
                    for d, code in totaux_anciens:
                        e = pc.equal(b[d], code)
                        anc = e if anc is None else pc.and_kleene(anc, e)
                    masque = pc.and_kleene(masque, pc.or_kleene(tot, anc))
                b = b.filter(masque)
                if not b.num_rows: continue
                cols = {}
                for c in garde:
                    if c == 'OBS_VALUE':
                        cols[c] = pc.cast(pc.replace_substring(b[c], ',', '.'), pa.float64())
                    else:
                        cols[c] = pc.dictionary_encode(b[c])
                morceaux.append(pa.table(cols))
    t = pa.concat_tables(morceaux).unify_dictionaries()
    df = t.to_pandas()
    for c in df.columns:
        if c != 'OBS_VALUE' and not isinstance(df[c].dtype, pd.CategoricalDtype):
            df[c] = df[c].astype('category')
    if 'OBS_STATUS' in df.columns:        # K : donnée incluse dans une autre catégorie -> vide
        df.loc[df.OBS_STATUS.astype(str).eq('K'), 'OBS_VALUE'] = np.nan
    return df, meta


# ---------------------------------------------------------------- libellés et noms
def ascii_min(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

def propre(s):
    s = str(s).replace('’', "'").replace(' ', ' ')
    s = re.sub(r'\s*[—–]\s*', ', ', s)
    return re.sub(r'\s+', ' ', s).strip()

def minuscule(s):
    s = propre(s)
    if len(s) > 1 and s[0].isupper() and not s[1].isupper(): return s[0].lower() + s[1:]
    return s

def de(txt):
    """« de » ou « d' » devant un nom."""
    t = minuscule(txt)
    return ("d'" if t[:1].lower() in 'aeiouyhéèêàâîôû' else 'de ') + t

def court(code):
    c = str(code)
    m = re.fullmatch(r'Y(\d+)T(\d+)', c)
    if m: return f'{int(m[1])}_{int(m[2])}'
    m = re.fullmatch(r'Y_GE(\d+)', c)
    if m: return f'{int(m[1])}p'
    m = re.fullmatch(r'Y_LT(\d+)', c)
    if m: return f'0_{int(m[1]) - 1}'
    return ascii_min(c)


# ---------------------------------------------------------------- traitement d'un jeu
def _cle(df, cols):
    """Clé entière d'une combinaison de colonnes catégorielles (mêmes catégories partout)."""
    k = np.zeros(len(df), dtype=np.int64)
    mult = 1
    for c in cols:
        n = len(df[c].cat.categories) + 1
        mult *= n
        if mult > 2 ** 62: raise OverflowError('trop de modalités pour une clé entière')
        k = k * n + (df[c].cat.codes.to_numpy().astype(np.int64) + 1)
    return k

def _vers_2026(wide, cols_somme, cols_nonadd, poids):
    """wide : index = codes Melodi COM. Renvoie un DataFrame indexé par CODGEO 2026 (34 875 communes)."""
    ref = geo.referentiel().CODGEO
    cod = geo.vers_cog2026(pd.Series(wide.index.astype(str), index=wide.index))
    w = wide[cod.notna().to_numpy()].copy()
    w.index = pd.Index(cod.dropna().to_numpy(), name='CODGEO')
    n = w.groupby(level=0).size()
    if (n > 1).any():
        out = pd.DataFrame(index=n.index)
        if cols_somme:
            s = w[cols_somme]
            tot = s.groupby(level=0).sum(min_count=1)
            nn = s.isna().groupby(level=0).sum()
            out[cols_somme] = tot.where(nn == 0)
        for c in cols_nonadd:
            p = poids.get(c)
            if p is not None and p in w.columns:
                x = w[[c, p]].dropna()
                num = (x[c] * x[p]).groupby(level=0).sum(); den = x[p].groupby(level=0).sum()
                v = (num / den.replace(0, np.nan)).reindex(n.index)
                comp = w[c].notna().groupby(level=0).sum()
                v[comp < n] = np.nan                # une partie sans valeur : pas d'estimation
            else:
                v = w[c].groupby(level=0).first().where(n == 1)
            out[c] = v
        w = out[wide.columns]
    return w.reindex(ref.to_numpy()).rename_axis('CODGEO')

def traiter(jeu, cache):
    """Transforme un jeu Melodi en colonnes communales. Clés de `jeu` :
      ds, prefixe, titre, periode ('rp' ou gabarit avec {a}), mesure (dimension mesure ou None),
      mesures {code: {nom, lib, unite, defn, agr ('somme' ou 'non_additif'), poids (gabarit avec {a})}},
      totaux {dim: code du total s'il n'est pas _T}, dims {dim: {abr, tpl, lib_total, colle, remplace}},
      codes {(dim, code): (nom court, libellé)}, exclure {dim: [codes]}, garder (fonction ligne -> bool),
      max_dims (2), anciennes (True), anciennes_dims (dimensions admises hors total pour les années antérieures),
      hierarchie (dimensions emboîtées, comptées pour une), dims_mesure (dimensions sans total, non comptées),
      ordre (ordre des dimensions dans les noms), niveau_series ('COM' ; 'DEP' si le jeu n'a pas de communes),
      ratios [{col, libelle, unite, definition, num, den, facteur, annee}].
    Renvoie {'data', 'indicateurs', 'publies', 'jeu'} ou None si le fichier n'est pas disponible."""
    ds, pref = jeu['ds'], jeu['prefixe']
    mesures = jeu['mesures']
    nonadd = any(m.get('agr') == 'non_additif' for m in mesures.values())
    niveaux = ('COM',) + (NIVEAUX_PUBLIES if nonadd else ())
    lu = lire(ds, str(cache), niveaux, jeu.get('totaux_anciens'))
    if lu is None: return None
    df, meta = lu
    lab = {(a, b): c for a, b, c in zip(meta.COD_VAR, meta.COD_MOD, meta.LIB_MOD)}
    dims = [c for c in df.columns if c not in HORS_DIM]
    mdim = jeu.get('mesure')
    if mdim is None:
        df = df.assign(_MESURE=pd.Categorical(['_'] * len(df))); mdim = '_MESURE'; dims = dims + [mdim]
    autres = [d for d in dims if d != mdim]
    ordre = jeu.get('ordre') or autres
    autres = [d for d in ordre if d in autres] + [d for d in autres if d not in ordre]
    totaux = jeu.get('totaux', {})
    hier = jeu.get('hierarchie', [])
    dmes = set(jeu.get('dims_mesure', []))
    anc_dims = set(jeu.get('anciennes_dims', []))
    com = df[df.GEO_OBJECT == 'COM']
    base = df[df.GEO_OBJECT == jeu.get('niveau_series', 'COM')]
    ser = base.groupby(dims + ['TIME_PERIOD'], observed=True).size().reset_index()[dims + ['TIME_PERIOD']]
    ser = ser[ser[mdim].astype(str).isin(list(mesures))]
    for d, cds in jeu.get('exclure', {}).items():
        ser = ser[~ser[d].astype(str).isin([str(c) for c in cds])]
    var = {m: [d for d in autres if g[d].nunique() > 1] for m, g in ser.groupby(mdim, observed=True)}
    lignes = []
    for r in ser.astype(str).to_dict('records'):
        nt = [d for d in var.get(r[mdim], []) if r[d] != totaux.get(d, '_T')]
        nth = [d for d in nt if d in hier]
        if len(nth) > 1:                      # niveaux emboîtés : seul le plus fin compte et figure dans le nom
            fin = max(nth, key=hier.index)
            nt = [d for d in nt if d not in hier or d == fin]
        r['_nt'] = nt
        r['_n'] = len([d for d in nt if d not in dmes])
        r['_nanc'] = len([d for d in nt if d not in dmes and d not in anc_dims])
        lignes.append(r)
    s = pd.DataFrame(lignes)
    s['_der'] = s.groupby(dims).TIME_PERIOD.transform('max')
    s['_max'] = s.groupby(mdim).TIME_PERIOD.transform('max')
    garder = jeu.get('garder', lambda r: True)
    # dernière période de chaque série encore diffusée au dernier millésime ; séries anciennes : totaux seulement
    ok = (s._n <= jeu.get('max_dims', 2)) & (s.TIME_PERIOD == s._der) & (s._der == s._max)
    if jeu.get('anciennes', True):
        ok |= (s._nanc == 0)
    s = s[ok & s.apply(lambda r: bool(garder(r)), axis=1)].copy()
    # noms et libellés
    codes = {**CODES_COMMUNS, **jeu.get('codes', {})}
    dcfg = jeu.get('dims', {})
    periode = jeu.get('periode', 'rp')
    titre = propre(jeu['titre'])
    inds, noms = [], {}
    for r in s.to_dict('records'):
        m = mesures[r[mdim]]
        a = r['TIME_PERIOD']
        parts, dlabs = [pref, m.get('nom', '')], []
        lib_m, defn = m['lib'], m['defn']
        for d in autres:
            cfg = dcfg.get(d, {})
            if d in r['_nt']:
                c = r[d]
                cs, cl = codes.get((d, c), (None, None))
                parts += [cfg.get('abr', ascii_min(d)), cs or court(c)]
                brut = propre(lab.get((d, c), c)) if cfg.get('brut') else minuscule(lab.get((d, c), c))
                txt = cl if cl is not None else cfg.get('tpl', '{lib}').format(lib=brut)
                if cfg.get('remplace'):
                    lib_m, defn = txt[0].upper() + txt[1:], f'Nombre {de(txt)}'
                elif cfg.get('colle'):
                    lib_m, defn = f'{lib_m} {txt}', f'{defn} {txt}'
                else:
                    dlabs.append(txt)
            elif cfg.get('lib_total') and d in var.get(r[mdim], []) and d not in hier:
                dlabs.append(cfg['lib_total'])
        col = '_'.join(p for p in parts + [ascii_min(a)] if p)
        if col in noms: raise ValueError(f'{ds} : nom de colonne en double {col} ({noms[col]} / {r})')
        noms[col] = r
        per = f'recensement de la population {a}' if periode == 'rp' else periode.format(a=a)
        dl = re.sub(r'(personne de référence [^,()]+), personne de référence ', r'\1, ', ', '.join(dlabs))
        ind = {'col': col,
               'libelle': propre(f"{lib_m}{', ' + dl if dl else ''} ({a})"),
               'unite': m.get('unite', ''),
               'definition': propre(f"{defn}{' (' + dl + ')' if dl else ''}, {per}.") + (' ' + m['note'] if m.get('note') else '') + f' Source : Insee, {titre}.',
               'agregation': m.get('agr', 'somme'), 'annee': a}
        if m.get('agr') == 'non_additif' and m.get('poids'):
            ind['poids'] = m['poids'].format(a=a)
        inds.append(ind)
    # passage en colonnes
    kc = dims + ['TIME_PERIOD']
    sel = s[kc].copy()
    for c in kc:
        sel[c] = pd.Categorical(sel[c], categories=df[c].cat.categories)
    carte = dict(zip(_cle(sel, kc), [i['col'] for i in inds]))
    cols = [i['col'] for i in inds]
    def large(sous):
        if not len(sous): return pd.DataFrame(columns=cols, dtype=float)
        k = _cle(sous, kc)
        col = pd.Series(k).map(carte).to_numpy()
        mk = pd.notna(col)
        x = pd.DataFrame({'GEO': sous.GEO.astype(str).to_numpy()[mk], 'col': col[mk], 'v': sous.OBS_VALUE.to_numpy()[mk]})
        if x.duplicated(['GEO', 'col']).any(): raise ValueError(f'{ds} : observations en double')
        return x.pivot(index='GEO', columns='col', values='v').reindex(columns=cols).astype(float)
    wide = large(com)
    agr = {i['col']: i['agregation'] for i in inds}
    poids = {i['col']: i.get('poids') for i in inds}
    cs = [c for c in cols if agr[c] == 'somme']
    cn = [c for c in cols if agr[c] == 'non_additif']
    data = _vers_2026(wide, cs, cn, poids)
    for rt in jeu.get('ratios', []):
        if rt['num'] in data.columns and rt['den'] in data.columns:
            data[rt['col']] = data[rt['num']] / data[rt['den']].where(data[rt['den']] > 0) * rt.get('facteur', 100)
            inds.append({'col': rt['col'], 'libelle': propre(rt['libelle']), 'unite': rt.get('unite', '%'),
                         'definition': propre(rt['definition']) + f' Source : Insee, {titre}.', 'agregation': 'ratio',
                         'num': rt['num'], 'den': rt['den'], 'facteur': rt.get('facteur', 100), 'annee': rt.get('annee', '')})
        else:
            raise ValueError(f"{ds} : ratio {rt['col']} sans numérateur ou dénominateur")
    # valeurs publiées par la source pour les indicateurs non additifs
    publies = {}
    if cn:
        for niv in NIVEAUX_PUBLIES:
            sous = df[df.GEO_OBJECT == niv]
            if niv == 'FRANCE':                # France entière si publiée, sinon France métropolitaine
                geos = set(sous.GEO.astype(str))
                g = 'F' if 'F' in geos else ('FM' if 'FM' in geos else None)
                sous = sous[sous.GEO == g] if g else sous.iloc[:0]
            if not len(sous): continue
            p = large(sous)[cn]
            p.index = ['FR' if niv == 'FRANCE' else g for g in p.index]
            publies[niv] = p.rename_axis('CODE').reset_index()
    data = data.reset_index()
    return {'data': data, 'indicateurs': inds, 'publies': publies, 'jeu': jeu}


def somme_cellules(ds, cache, sel, totaux=None, annee=None):
    """Somme par commune 2026 des observations dont les dimensions prennent les codes listés dans `sel`
    ({dim: [codes]}), les autres dimensions étant au total (code '_T' ou `totaux`) quand ce total existe.
    Somme vide si l'une des cellules est vide. Renvoie une Series indexée par CODGEO (34 875 communes)."""
    lu = lire(ds, str(cache), ('COM',), None)       # même clé de cache que traiter()
    if lu is None: return None
    df, _ = lu
    com = df[df.GEO_OBJECT == 'COM']
    annee = annee or str(max(com.TIME_PERIOD.astype(str).unique()))
    m = np.array((com.TIME_PERIOD == annee).to_numpy(), dtype=bool)
    totaux = totaux or {}
    ncomb = 1
    for d in [c for c in com.columns if c not in HORS_DIM]:
        if d in sel:
            m = m & np.asarray(com[d].isin(sel[d]), dtype=bool); ncomb *= len(sel[d])
        else:
            t = totaux.get(d, '_T')
            if t in set(com[d].cat.categories): m = m & np.asarray(com[d] == t, dtype=bool)
    x = com[m]
    n = x.groupby('GEO', observed=True).size()
    if len(n) == 0 or n.max() > ncomb or n.min() < ncomb:
        raise ValueError(f'{ds} : sélection {sel} incohérente ({n.min() if len(n) else 0} à {n.max() if len(n) else 0} cellules par commune pour {ncomb} attendues)')
    v = x.groupby('GEO', observed=True).OBS_VALUE.sum(min_count=1)
    v[x.OBS_VALUE.isna().groupby(x.GEO, observed=True).sum() > 0] = np.nan
    v.index = v.index.astype(str)
    return _vers_2026(v.to_frame('v'), ['v'], [], {})['v']


# ---------------------------------------------------------------- assemblage en blocs
def assembler(theme, resultats, dedoublonner=True, ratios=(), titre_ratios=''):
    """Réunit les résultats de traiter() dans un bloc du contrat. Les colonnes d'effectifs pondérés (valeurs non
    entières du recensement) identiques à une colonne déjà présente (même total publié dans plusieurs tableaux) ne
    sont gardées qu'une fois. `ratios` : ratios entre
    colonnes de jeux différents, calculés après assemblage (mêmes clés que dans traiter)."""
    resultats = [r for r in resultats if r is not None]
    data = None; inds = []; publies = {}
    vues = {}; alias = {}
    for r in resultats:
        d = r['data'].set_index('CODGEO')
        gardees = []
        for i in r['indicateurs']:
            c = i['col']
            v = d[c].round(6).to_numpy()
            # seulement pour des effectifs pondérés (non entiers) : deux comptages entiers peuvent coïncider par hasard
            if dedoublonner and i['agregation'] == 'somme' and (np.nan_to_num(v) % 1 != 0).any():
                h = hash(np.where(np.isnan(v), -1.2345e300, v).tobytes())
                if h in vues and np.array_equal(v, vues[h][1], equal_nan=True):
                    alias[c] = vues[h][0]
                    continue
                vues[h] = (c, v)
            gardees.append(dict(i))
        for i in gardees:                      # renvois vers une colonne écartée comme doublon
            for k in ('num', 'den', 'poids'):
                if i.get(k) in alias: i[k] = alias[i[k]]
        cols = [i['col'] for i in gardees]
        data = d[cols] if data is None else data.join(d[cols], how='outer')
        inds += gardees
        for niv, p in r['publies'].items():
            p = p.set_index('CODE')
            p = p[[c for c in p.columns if c in cols]]
            publies[niv] = p if niv not in publies else publies[niv].join(p, how='outer')
    for rt in ratios:
        num, den = alias.get(rt['num'], rt['num']), alias.get(rt['den'], rt['den'])
        if num not in data.columns or den not in data.columns:
            raise ValueError(f"ratio {rt['col']} sans numérateur ou dénominateur")
        data[rt['col']] = data[num] / data[den].where(data[den] > 0) * rt.get('facteur', 100)
        inds.append({'col': rt['col'], 'libelle': propre(rt['libelle']), 'unite': rt.get('unite', '%'),
                     'definition': propre(rt['definition']) + (f' Source : Insee, {propre(titre_ratios)}.' if titre_ratios else ''),
                     'agregation': 'ratio', 'num': num, 'den': den, 'facteur': rt.get('facteur', 100), 'annee': rt.get('annee', '')})
    # ratios : numérateur et dénominateur doivent rester dans le bloc
    for i in inds:
        if i['agregation'] == 'ratio':
            assert i['num'] in data.columns and i['den'] in data.columns, i['col']
    if alias:
        print(f'  {theme} : {len(alias)} colonnes identiques à une colonne déjà présente non reprises '
              f'(ex. {", ".join(f"{a} = {b}" for a, b in list(alias.items())[:3])})')
    bloc = {'theme': theme, 'data': data.reset_index(), 'indicateurs': inds}
    if publies:
        bloc['publies'] = {niv: p.reset_index() for niv, p in publies.items()}
    return bloc


NOMS_NIVEAUX = {'EPCI': 'EPCI', 'DEP': 'départements', 'REG': 'régions', 'ZE2020': "zones d'emploi", 'FRANCE': 'France'}

def noter_diffusion(bloc):
    """Complète la définition des indicateurs non additifs : nombre de communes avec une valeur et niveaux pour
    lesquels l'Insee publie une valeur (repris dans 'publies')."""
    pub = bloc.get('publies', {})
    for ind in bloc['indicateurs']:
        if ind['agregation'] != 'non_additif': continue
        n = int(bloc['data'][ind['col']].notna().sum())
        niv = [NOMS_NIVEAUX[k] for k, p in pub.items() if ind['col'] in p.columns and p[ind['col']].notna().any()]
        txt = (f"Valeur publiée pour {n} communes (secret statistique ailleurs)" if n else
               "Non diffusé à la commune (secret statistique ou jeu sans niveau communal)")
        txt += (f" ; valeurs publiées par l'Insee pour : {', '.join(niv)}." if niv else '.')
        d = ind['definition']
        i = d.rfind(' Source : ')
        ind['definition'] = d[:i] + ' ' + txt + d[i:] if i >= 0 else d + ' ' + txt
    return bloc
