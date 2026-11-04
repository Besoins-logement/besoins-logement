// Chargement (une seule fois par session) des fichiers de référence : meta.json, dictionnaire, territoires, catalogue des sources.
import { requete, executer } from './db.js';
import { lireJSON, lireTexte, analyserCSV, normaliser, ordreNiveau } from './util.js';

const cache = new Map();
function unique(cle, fn) {
  if (!cache.has(cle)) {
    const p = fn();
    p.catch(() => cache.delete(cle));
    cache.set(cle, p);
  }
  return cache.get(cle);
}

/** meta.json : date de mise à jour, thèmes (libellé, fichier, nombre d'indicateurs), niveaux, totaux. */
export function chargerMeta() {
  return unique('meta', () => lireJSON('meta.json'));
}

/** Dictionnaire des indicateurs (dictionnaire.parquet). */
export function chargerDictionnaire() {
  return unique('dictionnaire', async () => {
    const { colonnes, lignes } = await requete(`SELECT * FROM read_parquet('dictionnaire.parquet')`, ['dictionnaire.parquet']);
    const liste = lignes.map((l, i) => {
      const o = Object.fromEntries(colonnes.map((c, j) => [c, l[j] == null ? '' : l[j]]));
      o.communes_renseignees = typeof o.communes_renseignees === 'number' ? o.communes_renseignees : null;
      o.ordre = i;
      o.texteRecherche = normaliser([o.libelle, o.colonne, o.unite, o.annee, o.source, o.producteur, o.source_ref].join(' '));
      return o;
    });
    const parTheme = new Map();
    const parCle = new Map();
    for (const d of liste) {
      if (!parTheme.has(d.theme)) parTheme.set(d.theme, []);
      parTheme.get(d.theme).push(d);
      parCle.set(d.theme + '|' + d.colonne, d);
    }
    return { liste, parTheme, parCle, entree: (theme, col) => parCle.get(theme + '|' + col) || null };
  });
}

/** Territoires et appartenances (territoires.parquet), gardés aussi dans une table DuckDB « terr » pour les jointures. */
export function chargerTerritoires() {
  return unique('territoires', async () => {
    await executer(`CREATE TABLE IF NOT EXISTS terr AS SELECT * FROM read_parquet('territoires.parquet')`, ['territoires.parquet']);
    const { colonnes, lignes } = await requete(`SELECT * FROM terr`);
    const liste = lignes.map((l) => {
      const o = Object.fromEntries(colonnes.map((c, j) => [c, l[j]]));
      o.recherche = normaliser(o.nom);
      o.ordreNiveau = ordreNiveau(o.niveau);
      return o;
    });
    const parCle = new Map(liste.map((t) => [t.niveau + '|' + t.code, t]));
    const parNiveau = new Map();
    for (const t of liste) {
      if (!parNiveau.has(t.niveau)) parNiveau.set(t.niveau, []);
      parNiveau.get(t.niveau).push(t);
    }
    return { liste, parCle, parNiveau, trouver: (niveau, code) => parCle.get(niveau + '|' + code) || null };
  });
}

/** Catalogue des sources (sources.csv, séparateur virgule). */
export function chargerSources() {
  return unique('sources', async () => {
    const lignes = analyserCSV(await lireTexte('sources.csv'), ',');
    if (!lignes.length) throw new Error('Le catalogue des sources est vide.');
    const entetes = lignes[0].map((h) => h.trim());
    const liste = lignes.slice(1).filter((l) => l.some((c) => c !== '')).map((l) => {
      const o = Object.fromEntries(entetes.map((h, j) => [h, (l[j] || '').trim()]));
      o.texteRecherche = normaliser([o['Réf.'], o.Source, o.Producteur, o['Thème'], o.Type, o['Millésime'], o['Variables clés']].join(' '));
      return o;
    });
    return { entetes, liste };
  });
}
