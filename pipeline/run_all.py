# -*- coding: utf-8 -*-
"""Recalcule toute la base : exécute chaque module de pipeline/sources (sauf ceux dont le nom commence par _),
enregistre ses sorties dans cache/sorties, assemble docs/data, puis régénère COLLECTE.md.

Une source en échec est relancée une fois. Garde-fous : le programme s'arrête en erreur (code 1), et le robot ne
publie alors rien, si une source reste en échec ou si des indicateurs déjà publiés disparaissent de la base (signe
qu'une source a changé de structure ou de millésime : à vérifier avant publication). Pour accepter des suppressions
voulues : variable d'environnement ACCEPTER_SUPPRESSIONS=1.
Sur un poste de travail, une source en échec garde sa dernière sortie valide (cache/sorties). Sur le robot, le cache
est vide à chaque exécution : une source en échec n'a pas de sortie, d'où l'arrêt sans publication.

Usage : python pipeline/run_all.py [module ...]   (sans nom de module : tous les modules)"""
import os, re, sys, json, time, importlib, traceback, datetime
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo, assembler, collecte

PUB = geo.RACINE / 'docs' / 'data'
PAUSE_AVANT_RELANCE = 60          # secondes entre l'échec d'une source et son second essai


def executer(nom):
    mod = importlib.import_module(f'sources.{nom}')
    blocs = mod.charger(geo.CACHE)
    out = geo.CACHE / 'sorties'; out.mkdir(parents=True, exist_ok=True)
    ecrits = set()
    for i, b in enumerate(blocs):
        b['data'].to_parquet(out / f'{nom}_{i}.parquet', index=False); ecrits.add(f'{nom}_{i}.parquet')
        for niv, p in b.get('publies', {}).items():
            p.to_parquet(out / f'{nom}_{i}_publie_{niv}.parquet', index=False); ecrits.add(f'{nom}_{i}_publie_{niv}.parquet')
        with open(out / f'{nom}_{i}.json', 'w', encoding='utf-8') as f:
            json.dump({'source': getattr(mod, 'SOURCE', {}), 'theme': b['theme'], 'indicateurs': b['indicateurs']}, f, ensure_ascii=False, indent=1)
        ecrits.add(f'{nom}_{i}.json')
    motif = re.compile(rf'^{re.escape(nom)}_\d+(_publie_\w+)?\.(parquet|json)$')
    for p in out.iterdir():          # restes d'une exécution précédente (bloc ou niveau publié qui n'existe plus)
        if motif.match(p.name) and p.name not in ecrits: p.unlink()
    return len(blocs)


def tenter(nom):
    t = time.time()
    try:
        n = executer(nom)
        return {'module': nom, 'etat': 'ok', 'blocs': n, 'secondes': round(time.time() - t)}
    except Exception as e:
        traceback.print_exc()
        return {'module': nom, 'etat': 'echec', 'erreur': str(e)[:300], 'secondes': round(time.time() - t)}


def colonnes_publiees():
    f = PUB / 'dictionnaire.csv'
    if not f.exists(): return set()
    return set(pd.read_csv(f, usecols=['colonne'], dtype=str, encoding='utf-8-sig').colonne.dropna())


def resume(r):
    """Compte rendu en Markdown : affiché dans l'onglet Actions de GitHub (résumé de l'exécution) et dans le journal."""
    ok = [m for m in r['modules'] if m['etat'] == 'ok']
    l = [f"## Mise à jour de la base : {'nouvelle version prête à publier' if r['publiable'] else 'rien publié'}", '',
         f"{len(ok)} source(s) recalculée(s) sur {len(r['modules'])} ; {r['indicateurs']} indicateurs dans la base.", '']
    if r['echecs']:
        l += [f"**Sources en échec** (la base en ligne reste telle quelle) : {', '.join(r['echecs'])}.", '']
    if r['indicateurs_supprimes']:
        n = len(r['indicateurs_supprimes'])
        l += [f"**{n} indicateur(s) publié(s) disparu(s)** : " + ', '.join(r['indicateurs_supprimes'][:40]) + (' ...' if n > 40 else ''), '',
              "Une source a probablement changé de structure ou de millésime : adapter son script, ou relancer avec "
              "ACCEPTER_SUPPRESSIONS=1 si la suppression est voulue.", '']
    if r['indicateurs_ajoutes']:
        n = len(r['indicateurs_ajoutes'])
        l += [f"{n} indicateur(s) nouveau(x) : " + ', '.join(r['indicateurs_ajoutes'][:40]) + (' ...' if n > 40 else ''), '']
    l += ['| Source | État | Durée (s) | Erreur |', '|---|---|---|---|']
    for m in r['modules']:
        err = ' '.join(str(m.get('erreur', '')).split()).replace('|', '/')
        l.append(f"| {m['module']} | {'ok' if m['etat'] == 'ok' else 'échec'} | {m['secondes']} | {err} |")
    return '\n'.join(l)


def main():
    dossier = Path(__file__).resolve().parent / 'sources'
    noms = sys.argv[1:] or sorted(p.stem for p in dossier.glob('*.py') if not p.stem.startswith('_'))
    avant = colonnes_publiees()
    bilan = []
    for nom in noms:
        bilan.append(tenter(nom)); print(bilan[-1], flush=True)
    for i, b in enumerate(bilan):
        if b['etat'] != 'ok':
            print(f"second essai de {b['module']} dans {PAUSE_AVANT_RELANCE} s", flush=True)
            time.sleep(PAUSE_AVANT_RELANCE)
            r = tenter(b['module']); r['essais'] = 2; bilan[i] = r; print(r, flush=True)
    assembler.main()
    apres = colonnes_publiees()
    echecs = [b['module'] for b in bilan if b['etat'] != 'ok']
    supprimes = sorted(avant - apres) if avant else []
    ajoutes = sorted(apres - avant) if avant else []
    publiable = not echecs and (not supprimes or os.environ.get('ACCEPTER_SUPPRESSIONS') == '1')
    rapport = {'date': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'), 'publiable': publiable,
               'modules': bilan, 'echecs': echecs, 'indicateurs': len(apres),
               'indicateurs_ajoutes': ajoutes, 'indicateurs_supprimes': supprimes}
    with open(PUB / 'derniere_execution.json', 'w', encoding='utf-8') as f:
        json.dump(rapport, f, ensure_ascii=False, indent=1)
    collecte.main()
    texte = resume(rapport)
    print(texte)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(texte + '\n')
    if not publiable:
        print('ARRÊT : rien ne doit être publié (voir le compte rendu ci-dessus).', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
