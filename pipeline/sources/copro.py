# -*- coding: utf-8 -*-
"""CoproFF (Anah, Cerema) : nombre de copropriétés et de logements en copropriété par commune, par taille, période de construction et type de syndic, et taux d'immatriculation."""
import time, urllib.request
from pathlib import Path
import pandas as pd
import geo

BASE = 'https://static.data.gouv.fr/resources/donnees-agregees-du-referentiel-national-des-coproprietes-coproff/'
FICHIERS = {'COM': BASE + '20261030-102306/tableau-synthetique-coproff-com-2025.csv',
            'EPCI': BASE + '20261030-102040/tableau-synthetique-coproff-epci-2025.csv',
            'DEP': BASE + '20261030-101925/tableau-synthetique-coproff-dep-2025.csv',
            'REG': BASE + '20261030-101716/tableau-synthetique-coproff-reg-2025.csv',
            'DICO': BASE + '20261030-101344/dictionnaire-tableau-synthetique-coproff-com-2025.csv'}
AN = '2025'

SOURCE = {'ref': 'E7-45',
          'nom': 'CoproFF - données agrégées du référentiel national des copropriétés',
          'producteur': 'Anah et Cerema (Fichiers fonciers et registre national des copropriétés)',
          'url': 'https://www.data.gouv.fr/datasets/donnees-agregees-du-referentiel-national-des-coproprietes-coproff',
          'telechargement': FICHIERS['COM'],
          'millesime': 'CoproFF 2025 (publié en octobre 2026)',
          'licence': 'Licence ouverte 2.0'}

# colonne source -> (suffixe, libellé, définition)
COMPTES = {
    'nb_copros': ('coproprietes', 'Copropriétés', 'Nombre de copropriétés repérées dans les Fichiers fonciers (hors copropriétés à la localisation inexploitable).'),
    'nb_logements': ('logements', 'Logements en copropriété', 'Nombre total de logements situés dans des copropriétés.'),
    'copros_5_moins': ('5_moins', 'Copropriétés de 5 logements ou moins', 'Nombre de copropriétés de 5 logements ou moins.'),
    'copros_6_10': ('6_10', 'Copropriétés de 6 à 10 logements', 'Nombre de copropriétés de 6 à 10 logements.'),
    'copros_11_20': ('11_20', 'Copropriétés de 11 à 20 logements', 'Nombre de copropriétés de 11 à 20 logements.'),
    'copros_21_50': ('21_50', 'Copropriétés de 21 à 50 logements', 'Nombre de copropriétés de 21 à 50 logements.'),
    'copros_51_200': ('51_200', 'Copropriétés de 51 à 200 logements', 'Nombre de copropriétés de 51 à 200 logements.'),
    'copros_plus_200': ('plus_200', 'Copropriétés de plus de 200 logements', 'Nombre de copropriétés de plus de 200 logements.'),
    'copros_avant_49': ('avant_1949', 'Copropriétés construites avant 1949', 'Nombre de copropriétés dont la période de construction est antérieure à 1949.'),
    'copros_49_74': ('1949_1974', 'Copropriétés construites de 1949 à 1974', 'Nombre de copropriétés construites entre 1949 et 1974.'),
    'copros_75_2000': ('1975_2000', 'Copropriétés construites de 1975 à 2000', 'Nombre de copropriétés construites entre 1975 et 2000.'),
    'copros_apres_2000': ('apres_2000', 'Copropriétés construites après 2000', 'Nombre de copropriétés construites après 2000.'),
    'periode_inconnue': ('periode_inconnue', 'Copropriétés sans période de construction connue', 'Nombre de copropriétés dont la période de construction n\'est pas renseignée.'),
    'syndic_pro_connu': ('syndic_pro', 'Copropriétés gérées par un syndic professionnel', 'Nombre de copropriétés dont le syndic est déclaré professionnel.'),
    'syndic_benevole_connu': ('syndic_benevole', 'Copropriétés gérées par un syndic bénévole', 'Nombre de copropriétés dont le syndic est déclaré bénévole (non professionnel).'),
    'syndic_inconnu': ('syndic_inconnu', 'Copropriétés sans type de syndic connu', 'Nombre de copropriétés dont le type de syndic n\'est pas renseigné.'),
}


def _dl(url, p, essais=8):
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    for k in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                p.write_bytes(r.read())
                return p
        except Exception:
            if k == essais - 1:
                raise
            time.sleep(5 * (k + 1))


def _lire(p):
    x = pd.read_csv(p, sep=None, engine='python', dtype=str, encoding='utf-8-sig')
    for c in list(COMPTES) + ['taux_immat']:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c].str.replace(',', '.', regex=False), errors='coerce')
    return x


def charger(cache: Path) -> list:
    d = cache / 'copro'
    loc = {k: _dl(u, d / u.rsplit('/', 1)[1]) for k, u in FICHIERS.items()}
    c = _lire(loc['COM'])
    c['CODGEO'] = geo.vers_cog2026(c.code_com).values
    c = c.dropna(subset=['CODGEO'])
    c['immat'] = c.taux_immat * c.nb_copros
    agg = c.groupby('CODGEO')[list(COMPTES) + ['immat']].sum(min_count=1)
    agg['taux'] = (agg.immat / agg.nb_copros.where(agg.nb_copros > 0) * 100).round(2)
    agg = agg.reset_index()

    p = 'copro_'
    ren = {k: f'{p}{v[0]}_{AN}' for k, v in COMPTES.items()}
    ren['taux'] = f'{p}taux_immatriculation_{AN}'
    df = agg.rename(columns=ren)[['CODGEO'] + list(ren.values())]
    # communes absentes du fichier : aucune copropriété repérée (sauf départements non couverts)
    ref = geo.referentiel()[['CODGEO', 'DEP']]
    deps = set(ref.loc[ref.CODGEO.isin(df.CODGEO), 'DEP'])
    df = ref.merge(df, on='CODGEO', how='left')
    couvert = df.DEP.isin(deps)
    for col in [ren[k] for k in COMPTES]:
        df[col] = df[col].where(df[col].notna() | ~couvert, 0).astype('float64')
    df = df.drop(columns='DEP')

    inds = [{'col': ren[k], 'libelle': f'{v[1]} en {AN}', 'unite': 'logements' if k == 'nb_logements' else 'copropriétés',
             'definition': f'{v[2]} Source CoproFF {AN}. Commune sans copropriété repérée : 0.', 'agregation': 'somme', 'annee': AN}
            for k, v in COMPTES.items()]
    inds.append({'col': ren['taux'], 'libelle': f'Taux d\'immatriculation des copropriétés en {AN}', 'unite': '%',
                 'definition': f'Part des copropriétés repérées qui disposent d\'un numéro d\'immatriculation au registre national des copropriétés (CoproFF {AN}).',
                 'agregation': 'non_additif', 'poids': ren['nb_copros'], 'annee': AN})

    pub = {}
    for niv, cle in [('EPCI', 'code_epci'), ('DEP', 'code_dep'), ('REG', 'code_reg')]:
        x = _lire(loc[niv])
        x = x[x[cle].notna() & (x[cle] != 'SANS_EPCI')]
        pub[niv] = pd.DataFrame({'CODE': x[cle].values, ren['taux']: (x.taux_immat * 100).round(2).values}).drop_duplicates('CODE')
    return [{'theme': 'logement', 'data': df, 'indicateurs': inds, 'publies': pub}]
