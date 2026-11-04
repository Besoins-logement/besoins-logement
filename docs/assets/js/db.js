// Moteur de lecture des fichiers Parquet dans le navigateur : DuckDB-WASM, version épinglée, chargé depuis jsDelivr
// à la première requête seulement. Les fichiers sont déclarés par leur adresse absolue et lus par requêtes HTTP partielles
// (Range) : seules les colonnes demandées sont téléchargées.
import { adresseDonnees } from './util.js';

export const DUCKDB_VERSION = '1.29.0';
const DUCKDB_ESM = `https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@${DUCKDB_VERSION}/+esm`;

let moteur = null; // promesse { duckdb, db, conn }
const fichiers = new Map(); // nom -> promesse d'enregistrement
const verifies = new Map(); // nom -> promesse de vérification (HEAD)

/** Charge DuckDB-WASM (une seule fois) selon le schéma documenté : getJsDelivrBundles, selectBundle, worker depuis un Blob. */
export function moteurDuckDB() {
  if (!moteur) {
    moteur = (async () => {
      let duckdb;
      try {
        duckdb = await import(/* webpackIgnore: true */ DUCKDB_ESM);
      } catch (e) {
        throw new Error("Le moteur de lecture des données (DuckDB) n'a pas pu être téléchargé depuis cdn.jsdelivr.net. Vérifiez votre connexion ou un éventuel blocage par votre réseau, puis réessayez.");
      }
      const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
      const urlWorker = URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' }));
      const worker = new Worker(urlWorker);
      const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
      await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
      URL.revokeObjectURL(urlWorker);
      const conn = await db.connect();
      return { duckdb, db, conn };
    })();
    moteur.catch(() => { moteur = null; fichiers.clear(); });
  }
  return moteur;
}

/** Vérifie qu'un fichier de données existe (requête HEAD, une fois par session) pour donner un message clair s'il manque. */
export function verifierFichier(nom) {
  if (!verifies.has(nom)) {
    const p = fetch(adresseDonnees(nom), { method: 'HEAD', cache: 'no-cache' }).then((r) => {
      if (!r.ok) throw new Error(`Le fichier data/${nom} est introuvable sur le site (erreur ${r.status}).`);
      return true;
    }, () => {
      throw new Error(`Le fichier data/${nom} n'a pas pu être joint. Vérifiez votre connexion.`);
    });
    p.catch(() => verifies.delete(nom));
    verifies.set(nom, p);
  }
  return verifies.get(nom);
}

async function enregistrer(m, nom) {
  if (!fichiers.has(nom)) {
    const p = (async () => {
      await verifierFichier(nom);
      await m.db.registerFileURL(nom, adresseDonnees(nom), m.duckdb.DuckDBDataProtocol.HTTP, false);
    })();
    p.catch(() => fichiers.delete(nom));
    fichiers.set(nom, p);
  }
  return fichiers.get(nom);
}

/** Exécute une requête SQL ; renvoie { colonnes: [noms], lignes: [[valeurs]] }. Les entiers 64 bits deviennent des nombres. */
export async function requete(sql, noms = []) {
  const m = await moteurDuckDB();
  for (const nom of noms) await enregistrer(m, nom);
  let res;
  try {
    res = await m.conn.query(sql);
  } catch (e) {
    throw new Error('La lecture des données a échoué : ' + (e && e.message ? e.message : e));
  }
  const colonnes = res.schema.fields.map((f) => f.name);
  const vecteurs = colonnes.map((_, j) => res.getChildAt(j));
  const n = res.numRows;
  const lignes = new Array(n);
  for (let i = 0; i < n; i++) {
    const l = new Array(colonnes.length);
    for (let j = 0; j < colonnes.length; j++) {
      let v = vecteurs[j].get(i);
      if (typeof v === 'bigint') v = Number(v);
      l[j] = v === undefined ? null : v;
    }
    lignes[i] = l;
  }
  return { colonnes, lignes };
}

/** Même chose, mais chaque ligne est un objet { colonne: valeur }. */
export async function requeteObjets(sql, noms = []) {
  const { colonnes, lignes } = await requete(sql, noms);
  return lignes.map((l) => Object.fromEntries(colonnes.map((c, j) => [c, l[j]])));
}

/** Exécute une instruction sans résultat attendu (CREATE TABLE...). */
export async function executer(sql, noms = []) {
  const m = await moteurDuckDB();
  for (const nom of noms) await enregistrer(m, nom);
  try {
    await m.conn.query(sql);
  } catch (e) {
    throw new Error('La lecture des données a échoué : ' + (e && e.message ? e.message : e));
  }
}
