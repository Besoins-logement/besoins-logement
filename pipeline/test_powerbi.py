# -*- coding: utf-8 -*-
"""Tests des fichiers Power BI (docs/data/powerbi) sur les chiffres de contrôle France et les règles de la base.

Usage : python pipeline/test_powerbi.py   (après powerbi.py ou run_all.py ; fonctionne aussi avec pytest).
Les chiffres de contrôle sont ceux de la base publiée le 4 novembre 2026 : ils changeront si le SDES publie une nouvelle étude
ou si Sitadel révise la construction 2023-2025. Mettre alors à jour CONTROLE ci-dessous (et les mesures « Contrôle » du rapport)."""
import re, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import powerbi

P = powerbi.SORTIE
CONTROLE = {'besoin_2020_2030': 340804, 'besoin_2030_2040': 335354, 'besoin_2040_2050': 179622,
            'construction_actuelle': 278500, 'couverture_2030_2040_pct': 83, 'manque_2030_2040': 56855,
            'departements_par_classe': {1: 33, 2: 9, 3: 58}}


def lire(nom):
    return pd.read_csv(P / f'{nom}.csv.gz', sep=';', dtype={'id': str, 'code': str, 'id_parent': str})


def test_fichiers_presents():
    for n in ['territoires', 'indicateurs', 'besoins_periode', 'series', 'repartitions', 'meta', 'correspondance']:
        assert (P / f'{n}.csv.gz').exists(), n


def test_besoin_france_par_decennie():
    b = lire('besoins_periode').set_index(['id', 'periode']).besoin_construction
    assert round(b['FR', '2020-2030']) == CONTROLE['besoin_2020_2030']
    assert round(b['FR', '2030-2040']) == CONTROLE['besoin_2030_2040']
    assert round(b['FR', '2040-2050']) == CONTROLE['besoin_2040_2050']


def test_construction_couverture_manque_france():
    i = lire('indicateurs').set_index('id')
    b = lire('besoins_periode').set_index(['id', 'periode']).besoin_construction
    cons = i.loc['FR', 'construction_actuelle']
    assert round(cons, -2) == CONTROLE['construction_actuelle']
    assert round(cons / b['FR', '2030-2040'] * 100) == CONTROLE['couverture_2030_2040_pct']
    assert round(b['FR', '2030-2040'] - cons) == CONTROLE['manque_2030_2040']
    assert round(i.loc['FR', 'manque_2030_2040']) == CONTROLE['manque_2030_2040']


def test_departements_par_classe_mayotte_hors_champ():
    t = lire('territoires'); i = lire('indicateurs').merge(t[['id', 'niveau', 'code']], on='id')
    d = i[i.niveau == 'Département']
    assert d.classe_2030_2040.value_counts().to_dict() == CONTROLE['departements_par_classe']
    may = d[d.code == '976']
    assert may.classe_2030_2040.isna().all() and may.construction_actuelle.isna().all()   # hors champ : vide
    bp = lire('besoins_periode')
    assert bp[bp.id == 'DEP-976'].besoin_construction.isna().all()      # vide, jamais 0


def test_regle_de_classe_par_periode():
    """La règle du rapport (1 si construction >= besoin avant vacants, 2 si >= besoin, sinon 3) redonne bes_classe_3040."""
    i = lire('indicateurs').set_index('id')
    b = lire('besoins_periode'); b = b[b.periode == '2030-2040'].set_index('id').loc[i.index]
    cl = powerbi.classe(i.construction_actuelle, b.besoin_avant_vacants, b.besoin_construction)
    pub = i.classe_2030_2040.astype(float)
    assert ((cl == pub) | (cl.isna() & pub.isna())).all()
    assert len(i) == 1680


def test_territoires_et_parents():
    t = lire('territoires')
    assert t.id.is_unique
    assert t.niveau.value_counts().to_dict() == {'EPCI': 1254, "Zone d'emploi": 306, 'Département': 101, 'Région': 18, 'France': 1}
    autres = t[t.niveau != 'France']
    assert autres.id_parent.notna().all() and autres.id_parent.isin(set(t.id)).all()
    par = t.set_index('id')
    assert par.loc['DEP-33', 'id_parent'] == 'REG-75' and par.loc['REG-75', 'id_parent'] == 'FR'
    assert par.loc['EPCI-243300316', 'id_parent'] == 'DEP-33'
    assert par.loc['ZE-7505', 'id_parent'] == 'REG-75'
    assert par.loc['FR', 'nb_communes'] == 34875
    assert t[t.niveau == 'Département'].nb_communes.sum() == 34875
    # un nom par territoire dans chaque niveau (le panneau du rapport choisit par le nom)
    assert not t.duplicated(['niveau', 'nom']).any()
    assert par.loc['ZE-0205', 'nom'] != par.loc['ZE-0404', 'nom']
    assert par.loc['DEP-75', 'nom'] == 'Paris'
    for nom in ['indicateurs', 'besoins_periode', 'series', 'repartitions']:
        assert lire(nom).id.isin(set(t.id)).all(), nom


def test_noms_stables_sans_annee():
    cols = lire('indicateurs').columns
    for c in cols:
        assert not re.search(r'_(19|20)\d\d$', c) or re.search(r'_(19|20)\d\d_(19|20)\d\d$', c), c
    c = lire('correspondance')
    assert not c.duplicated(['fichier', 'nom_stable', 'element']).any()
    ind = c[c.fichier == 'indicateurs'].set_index('nom_stable').colonne_source
    assert ind['menages'] == 'menc_2023' and ind['menages_debut'] == 'menc_2012'
    assert ind['prix_m2_maison'] == 'dvf_prix_m2_maisons_2025' and ind['salaries_prives_debut'] == 'urssaf_salaries_2015'


def test_repartitions_parts():
    r = lire('repartitions')
    g = r[(r.id == 'DEP-33') & (r.repartition == 'composition_menages')].set_index('modalite').valeur
    parts = (g / g.sum() * 100).round()
    assert parts['Personne seule'] == 40 and parts['Couple sans enfant'] == 25 and parts['Couple avec enfants'] == 23
    s = r[(r.id == 'FR') & (r.repartition == 'statut_occupation')].valeur.sum()
    i = lire('indicateurs').set_index('id')
    assert abs(s - i.loc['FR', 'residences_principales']) < 1


def test_modalites_triables():
    r = lire('repartitions')
    assert (r.groupby('modalite').ordre.nunique() == 1).all()
    s = lire('series')
    m = s[(s.id == 'DEP-33') & (s.serie == 'menages')].set_index('annee').valeur
    assert round(m[2012]) == 668201 and round(m[2023]) == 801446


def test_valeurs_absentes_restent_vides():
    i = lire('indicateurs').set_index('id')
    assert pd.isna(i.loc['DEP-67', 'prix_m2_maison'])          # DVF absent en Alsace-Moselle
    assert pd.isna(i.loc['DEP-976', 'population']) or i.loc['DEP-976', 'population'] != 0


def test_garde_fou_colonne_absente():
    ancien = list(powerbi.INDICATEURS)
    powerbi.INDICATEURS.append(('colonne_inventee', 'menc_2099', 'menages', '2099', 'Test'))
    try:
        powerbi.construire()
        assert False, 'le garde-fou aurait dû arrêter le programme'
    except powerbi.ErreurPowerBI as e:
        assert 'menc_2099' in str(e)
    finally:
        powerbi.INDICATEURS[:] = ancien


if __name__ == '__main__':
    ok = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith('test_') and callable(f)]
    for n, f in tests:
        try:
            f(); ok += 1; print('ok    ', n)
        except AssertionError as e:
            print('ÉCHEC ', n, e)
        except Exception as e:
            print('ERREUR', n, type(e).__name__, e)
    print(f'{ok}/{len(tests)} tests réussis')
    sys.exit(0 if ok == len(tests) else 1)
