# -*- coding: utf-8 -*-
"""Produit COLLECTE.md, à la racine du dépôt : pour chaque source, d'où viennent les données (page, fichier
téléchargé), quel millésime est utilisé, ce que fait le script et combien d'indicateurs il produit.
Lit les sorties de la dernière exécution (cache/sorties/<module>_<i>.json, écrites par run_all.py) ; pour un module
sans sortie, lit le bloc SOURCE du script. Appelé par run_all.py ; seul : python pipeline/collecte.py"""
import ast, json, re, sys, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo
from assembler import theme_publie

DOSSIER = Path(__file__).resolve().parent / 'sources'

ENTETE = """# Comment chaque source est collectée et mise à jour

Ce fichier est produit automatiquement à chaque exécution (`pipeline/collecte.py`), à partir des scripts et de leurs sorties.

## Collecte

Chaque source a son propre script dans `pipeline/sources/`. Le script télécharge les données à l'adresse indiquée plus bas, les ramène aux communes au 1er janvier 2026 (communes fusionnées ou scindées comprises), calcule les indicateurs et documente chacun (libellé, définition, unité, année, source). L'assemblage (`pipeline/assembler.py`) calcule ensuite les six autres niveaux : France, régions, départements, zones d'emploi, EPCI, territoires d'industrie. Les règles que respecte chaque script sont dans `pipeline/CONTRAT_SOURCES.md`.

## Mise à jour

Le robot (GitHub Actions) relance tous les scripts le 3 de chaque mois, ou à la demande depuis l'onglet Actions du dépôt. Les scripts retéléchargent les sources, puis la base est reconstruite. Le robot ne publie la nouvelle version que si toutes les sources ont réussi et qu'aucun indicateur déjà publié n'a disparu. Sinon, la base en ligne reste telle quelle et l'exécution apparaît en échec dans l'onglet Actions, avec le détail par source. Le compte rendu de la dernière exécution publiée est dans `docs/data/derniere_execution.json` ; chaque mise à jour publiée est un commit de l'historique du dépôt.

Limite actuelle : la plupart des scripts visent une édition précise de leur source (ligne « Millésime »). Tant que le script n'est pas modifié, il retélécharge cette même édition. Quand le producteur publie une nouvelle édition (nouveau recensement, nouveau fichier LOVAC, nouvel inventaire SRU...), il faut adapter le script. Les sources diffusées en continu (diagnostics de performance énergétique, statistiques DVF, arrêtés de catastrophe naturelle, référentiel des gares) sont relues à chaque exécution.
"""


def lire_script(f):
    """Docstring et bloc SOURCE (valeurs littérales seulement) d'un script, sans l'exécuter."""
    arbre = ast.parse(f.read_text(encoding='utf-8'))
    src = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict) and any(getattr(t, 'id', None) == 'SOURCE' for t in n.targets):
            for k, v in zip(n.value.keys, n.value.values):
                try: src[ast.literal_eval(k)] = ast.literal_eval(v)
                except Exception: src[ast.literal_eval(k)] = '(calculé à l\'exécution)'
    return ast.get_docstring(arbre) or '', src


def texte(x):
    """Une ligne de Markdown sans balise parasite (les < > des adresses modèles sont échappés)."""
    return ' '.join(str(x or '').split()).replace('<', '&lt;').replace('>', '&gt;')


def main():
    sorties = geo.CACHE / 'sorties'
    fiches, total = [], 0
    for f in sorted(DOSSIER.glob('*.py')):
        nom = f.stem
        if nom.startswith('_'): continue
        doc, src = lire_script(f)
        motif = re.compile(rf'^{re.escape(nom)}_\d+\.json$')
        fj = sorted(p for p in sorties.glob(f'{nom}_*.json') if motif.match(p.name)) if sorties.exists() else []
        blocs = [(p.stem, json.loads(p.read_text(encoding='utf-8'))) for p in fj]
        if blocs:
            src = blocs[0][1].get('source') or src
            themes = sorted({theme_publie(nb, b) for nb, b in blocs})
            blocs = [b for _, b in blocs]
            n = sum(len(b['indicateurs']) for b in blocs)
            calcul = datetime.datetime.fromtimestamp(max(p.stat().st_mtime for p in fj), datetime.timezone.utc).date().isoformat()
        else:
            themes, n, calcul = [], 0, 'pas encore exécuté'
        total += n
        fiches.append((nom, doc, src, themes, n, calcul))

    l = [ENTETE, '## Les sources', '',
         f'{len(fiches)} scripts, {total} indicateurs produits par les scripts (la base en compte un peu plus : '
         'les synthèses du besoin en logements sont calculées à l\'assemblage).', '',
         '| Script | Source | Producteur | Indicateurs |', '|---|---|---|---|']
    for nom, doc, src, themes, n, calcul in fiches:
        l.append(f"| [{nom}](#{nom}) | {texte(src.get('nom')).replace('|', '/')} | {texte(src.get('producteur')).replace('|', '/')} | {n} |")
    for nom, doc, src, themes, n, calcul in fiches:
        l += ['', f'### {nom}', '', f"**{texte(src.get('nom'))}**", '',
              f"- Producteur : {texte(src.get('producteur'))}",
              f"- Référence dans le catalogue des sources du projet : {texte(src.get('ref'))}",
              f"- Page de la source : {texte(src.get('url'))}",
              f"- Adresse de téléchargement utilisée : {texte(src.get('telechargement'))}",
              f"- Millésime : {texte(src.get('millesime'))}",
              f"- Licence : {texte(src.get('licence'))}",
              f"- Thèmes de la base : {', '.join(themes) or '-'} ({n} indicateurs)",
              f"- Dernier calcul : {calcul}",
              f"- Ce que fait le script : {texte(doc)}",
              f"- Script : [`pipeline/sources/{nom}.py`](pipeline/sources/{nom}.py)"]
    (geo.RACINE / 'COLLECTE.md').write_text('\n'.join(l) + '\n', encoding='utf-8')
    return len(fiches), total


if __name__ == '__main__':
    print('COLLECTE.md :', *main(), 'scripts, indicateurs')
