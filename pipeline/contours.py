# -*- coding: utf-8 -*-
"""Contours simplifiés pour les cartes (rapport Power BI et site) : docs/geo/.

Lancé à la main, à chaque changement de géographie (une fois par an, après la mise à jour du COG dans geo.py), pas par le
robot mensuel (le robot vérifie seulement que les quatre TopoJSON existent) :
    python pipeline/contours.py

Source : communes au 1er janvier 2026 de l'IGN (ADMIN EXPRESS COG), dans la version simplifiée à 50 m publiée par Etalab
(« Contours administratifs », Licence ouverte 2.0) : un GeoJSON compressé, sans archive 7z à décompresser.
Les communes sont regroupées avec les appartenances de geo.py (région, département, zone d'emploi 2020, EPCI 2026), puis
fusionnées et simplifiées par mapshaper (npm, version épinglée ci-dessous). La simplification est topologique : deux
territoires voisins partagent la même frontière, il n'y a ni trou ni chevauchement entre eux.

Outre-mer en encarts : la Guadeloupe, la Martinique, la Guyane, La Réunion et Mayotte sont déplacées et mises à l'échelle
dans une colonne à l'ouest de la Bretagne, comme dans les cartes de l'Insee. Les coordonnées restent en degrés (WGS 84) et
le placement est calculé en projection de Mercator : choisir « Mercator » dans le visuel Shape Map de Power BI.

Sorties dans docs/geo/ :
  regions.topojson, departements.topojson, zones_emploi.topojson, epci.topojson   (Power BI, visuel Shape Map)
  regions.geojson, departements.geojson, zones_emploi.geojson, epci.geojson       (site)
Chaque contour porte les propriétés `id` (exactement l'id de docs/data/powerbi/territoires.csv.gz, par exemple DEP-33)
et `nom`. Nécessite Node.js (npx)."""
import gzip, json, math, shutil, subprocess, sys, urllib.request
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo, powerbi

SOURCE = {'ref': 'E7-60', 'nom': 'Contours administratifs 2026 : communes, généralisation 50 m',
          'producteur': 'IGN (ADMIN EXPRESS COG 2026), mis en forme par Etalab',
          'url': 'https://www.data.gouv.fr/datasets/contours-administratifs/',
          'telechargement': 'https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2026/geojson/communes-50m.geojson.gz',
          'millesime': 'Communes au 1er janvier 2026', 'licence': 'Licence ouverte 2.0'}
MAPSHAPER = 'mapshaper@0.7.101'
CACHE = geo.CACHE / 'contours'
GEO = geo.RACINE / 'docs' / 'geo'

# niveau : (fichier, colonne d'appartenance de geo.referentiel(), préfixe de l'id, part des points gardés par mapshaper)
NIVEAUX = [('Région', 'regions', 'REG', 'REG', '4%'),
           ('Département', 'departements', 'DEP', 'DEP', '4%'),
           ("Zone d'emploi", 'zones_emploi', 'ZE2020', 'ZE', '3%'),
           ('EPCI', 'epci', 'EPCI', 'EPCI', '2.5%')]
TAILLE_MAX_EPCI = 1_000_000   # octets

# Encarts d'outre-mer, de haut en bas, dans une colonne à l'ouest de la métropole (coordonnées de Mercator, en degrés)
ENCARTS = ['971', '972', '973', '974', '976']
COLONNE_X = -6.3          # centre de la colonne (longitude), dans le golfe de Gascogne, à l'ouest de la pointe bretonne
HAUT_Y = 48.6             # latitude du haut de la colonne
CASE = 1.6                # taille d'une case (unités de Mercator, environ des degrés) ; 2,25 jusqu'au 24 novembre 2026 :
ECART = 0.45              # encarts trop grands à côté de la métropole dans le rapport


def telecharger():
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / 'communes-50m-2026.geojson.gz'
    if not f.exists():
        tmp = f.with_suffix('.part')
        with urllib.request.urlopen(SOURCE['telechargement'], timeout=600) as r:
            tmp.write_bytes(r.read())
        tmp.replace(f)
    return f


def merc(lat):
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def inv_merc(y):
    return math.degrees(2 * math.atan(math.exp(math.radians(y))) - math.pi / 2)


def coordonnees(geom):
    if geom['type'] == 'Polygon':
        for anneau in geom['coordinates']:
            yield from anneau
    elif geom['type'] == 'MultiPolygon':
        for poly in geom['coordinates']:
            for anneau in poly:
                yield from anneau


def transformer(geom, f):
    if geom['type'] == 'Polygon':
        geom['coordinates'] = [[f(p) for p in anneau] for anneau in geom['coordinates']]
    elif geom['type'] == 'MultiPolygon':
        geom['coordinates'] = [[[f(p) for p in anneau] for anneau in poly] for poly in geom['coordinates']]


def placer_outre_mer(features):
    """Déplace chaque département d'outre-mer dans sa case : même échelle en x et en y dans la projection de Mercator."""
    haut = merc(HAUT_Y)
    for k, dep in enumerate(ENCARTS):
        fs = [f for f in features if f['properties']['DEP'] == dep]
        pts = [(x, merc(y)) for f in fs for x, y in coordonnees(f['geometry'])]
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        s = CASE / max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        tx, ty = COLONNE_X, haut - CASE / 2 - k * (CASE + ECART)
        def f(p, s=s, cx=cx, cy=cy, tx=tx, ty=ty):
            return [round(tx + (p[0] - cx) * s, 6), round(inv_merc(ty + (merc(p[1]) - cy) * s), 6)]
        for feat in fs:
            transformer(feat['geometry'], f)


def communes_jointes():
    """GeoJSON des communes 2026 avec les identifiants de leurs territoires, outre-mer déplacé."""
    with gzip.open(telecharger(), 'rt', encoding='utf-8') as fh:
        gj = json.load(fh)
    ref = geo.referentiel().set_index('CODGEO')
    terr = powerbi.table_territoires().set_index('id')
    feats, inconnues = [], []
    for f in gj['features']:
        code = str(f['properties'].get('code', ''))
        if code not in ref.index:
            inconnues.append(code); continue
        r = ref.loc[code]
        props = {'com': code, 'DEP': r.DEP}
        for niveau, _, col, pre, _ in NIVEAUX:
            v = r[col]
            props[f'id_{pre}'] = f'{pre}-{v}' if isinstance(v, str) else None
            props[f'nom_{pre}'] = terr.nom.get(props[f'id_{pre}'])
        feats.append({'type': 'Feature', 'properties': props, 'geometry': f['geometry']})
    absentes = sorted(set(ref.index) - {f['properties']['com'] for f in feats})
    # écartés normalement : arrondissements municipaux de Paris, Lyon et Marseille (la ville entière est déjà là, sinon
    # double compte) et collectivités d'outre-mer (hors COG des communes)
    cog = pd.read_csv(geo.fichier('insee/v_commune_2026.csv'), dtype=str)
    arm = set(cog.loc[cog.TYPECOM == 'ARM', 'COM'])
    hors_cog = [c for c in inconnues if c not in arm and not c.startswith(('975', '977', '978', '98'))]
    if absentes or hors_cog:
        raise SystemExit(f'communes sans contour : {absentes[:20]} ; contours hors COG 2026 : {hors_cog[:20]}')
    placer_outre_mer(feats)
    out = CACHE / 'communes_jointes.geojson'
    out.write_text(json.dumps({'type': 'FeatureCollection', 'features': feats}, ensure_ascii=False), encoding='utf-8')
    return out, terr


def mapshaper(*args):
    npx = shutil.which('npx')
    if not npx:
        raise SystemExit('Node.js (npx) est nécessaire : https://nodejs.org')
    cmd = [npx, '--yes', '--package', MAPSHAPER, 'mapshaper', *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise SystemExit('mapshaper : ' + r.stderr[-2000:])
    return r.stderr


def main():
    GEO.mkdir(parents=True, exist_ok=True)
    communes, terr = communes_jointes()
    for niveau, fichier, _, pre, garder in NIVEAUX:
        for fmt, ext, extra in [('topojson', 'topojson', ['quantization=100000', 'id-field=id']), ('geojson', 'geojson', ['precision=0.0001'])]:
            mapshaper('-i', str(communes), 'name=' + fichier,
                      '-dissolve2', f'id_{pre}', f'copy-fields=nom_{pre}',
                      '-rename-fields', f'id=id_{pre},nom=nom_{pre}',
                      '-simplify', garder, 'keep-shapes',
                      '-clean',
                      '-o', str(GEO / f'{fichier}.{ext}'), f'format={fmt}', *extra)
        # contrôle : exactement les territoires du niveau, avec le même id
        gj = json.loads((GEO / f'{fichier}.geojson').read_text(encoding='utf-8'))
        ids = [f['properties']['id'] for f in gj['features']]
        attendus = set(terr.index[terr.niveau == niveau])
        if sorted(ids) != sorted(attendus):
            raise SystemExit(f'{fichier} : ids différents de territoires ({len(set(ids) ^ attendus)} écarts, '
                             f'par exemple {sorted(set(ids) ^ attendus)[:5]})')
        tailles = {ext: round((GEO / f'{fichier}.{ext}').stat().st_size / 1e3) for ext in ('topojson', 'geojson')}
        print(f'{fichier} : {len(ids)} contours, ko : {tailles}', flush=True)
    t = (GEO / 'epci.topojson').stat().st_size
    if t > TAILLE_MAX_EPCI:
        raise SystemExit(f'epci.topojson fait {t} octets (plus de {TAILLE_MAX_EPCI}) : simplifier davantage (NIVEAUX)')


if __name__ == '__main__':
    main()
