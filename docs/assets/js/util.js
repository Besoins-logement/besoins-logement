// Outils communs : formats français, échappement, petits composants DOM, chargement de scripts, CSV.

/** Adresse absolue d'un fichier de données, construite depuis l'adresse de la page (fonctionne sous un sous-chemin GitHub Pages). */
export function adresseDonnees(nom) {
  return new URL('data/' + nom, location.href).href;
}

/* ---------- Niveaux géographiques ---------- */
export const NIVEAUX = [
  { cle: 'france', libelle: 'France', pluriel: 'France' },
  { cle: 'region', libelle: 'Région', pluriel: 'Régions' },
  { cle: 'departement', libelle: 'Département', pluriel: 'Départements' },
  { cle: 'ze', libelle: "Zone d'emploi", pluriel: "Zones d'emploi" },
  { cle: 'epci', libelle: 'EPCI', pluriel: 'Intercommunalités (EPCI)' },
  { cle: 'ti', libelle: "Territoire d'industrie", pluriel: "Territoires d'industrie" },
  { cle: 'commune', libelle: 'Commune', pluriel: 'Communes' },
];
const PAR_CLE = new Map(NIVEAUX.map((n) => [n.cle, n]));
const PAR_LIBELLE = new Map(NIVEAUX.map((n) => [n.libelle, n]));
export function niveauDepuisCle(cle) { return PAR_CLE.get(cle) || null; }
export function niveauDepuisLibelle(lib) { return PAR_LIBELLE.get(lib) || { cle: slug(lib), libelle: lib, pluriel: lib }; }
export function ordreNiveau(lib) { const i = NIVEAUX.findIndex((n) => n.libelle === lib); return i < 0 ? 99 : i; }

/* ---------- Nombres et dates ---------- */
const formats = new Map();
export function nf(maxDec = 2, minDec = 0) {
  const k = maxDec + ':' + minDec;
  if (!formats.has(k)) formats.set(k, new Intl.NumberFormat('fr-FR', { maximumFractionDigits: maxDec, minimumFractionDigits: minDec }));
  return formats.get(k);
}
export function estNombre(v) { return typeof v === 'number' && Number.isFinite(v); }
/** Format français ; une valeur qui s'arrondit à zéro s'écrit « 0 », jamais « -0 ». */
export function fmtNombre(v, maxDec = 2) {
  if (!estNombre(v)) return '';
  const s = nf(maxDec).format(v);
  return /^-0([,.]0*)?$/.test(s) ? s.slice(1) : s;
}
export function fmtEntier(v) { return fmtNombre(v, 0); }

const MOIS = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
/** "2026-11-02" -> "2 novembre 2026" (et "1er" pour le premier du mois). */
export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(String(iso).slice(0, 10) + 'T00:00:00Z');
  if (Number.isNaN(d.getTime())) return String(iso);
  const s = MOIS.format(d);
  return d.getUTCDate() === 1 ? s.replace(/^1 /, '1er ') : s;
}
export function fmtTaille(octets) {
  if (!estNombre(octets)) return '';
  if (octets < 1000) return `${fmtEntier(octets)} octets`;
  if (octets < 1e6) return `${fmtNombre(octets / 1e3, 0)} ko`;
  return `${fmtNombre(octets / 1e6, octets < 1e7 ? 1 : 0)} Mo`;
}
/** Lit un nombre saisi en français ("1 000,5", "7.5", "-3") ; renvoie null si invalide. */
export function lireNombre(texte) {
  if (texte == null) return null;
  const s = String(texte).replace(/[\s  ]/g, '').replace(',', '.');
  if (!/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(s)) return null;
  const v = Number(s);
  return Number.isFinite(v) ? v : null;
}

/* ---------- Texte ---------- */
export function slug(s) {
  return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
/** Forme de recherche : sans accents, minuscules, tirets et apostrophes remplacés par des espaces. */
export function normaliser(s) {
  return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[-'’_.,;:()«»"/]/g, ' ').replace(/\s+/g, ' ').trim();
}
/** Vrai si tous les mots de la requête sont présents dans le texte (déjà normalisé). */
export function contientTous(texteNormalise, mots) {
  for (const m of mots) if (!texteNormalise.includes(m)) return false;
  return true;
}
export function sqlTexte(s) { return "'" + String(s).replace(/'/g, "''") + "'"; }
export function sqlIdent(s) { return '"' + String(s).replace(/"/g, '""') + '"'; }

/* ---------- DOM ---------- */
/** Crée un élément : el('p', {class: 'x', text: '...'}, enfant1, 'texte'...). Les chaînes deviennent des nœuds texte (jamais du HTML). */
export function el(tag, attrs = {}, ...enfants) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k === 'dataset') Object.assign(n.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else if (v === true) n.setAttribute(k, '');
    else n.setAttribute(k, v);
  }
  for (const e of enfants.flat()) {
    if (e == null || e === false) continue;
    n.append(e instanceof Node ? e : document.createTextNode(String(e)));
  }
  return n;
}
export function vider(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
export function chargement(texte) { return el('span', { class: 'chargement' }, texte); }
export function alerte(texte, { info = false, reessayer = null } = {}) {
  const d = el('div', { class: 'alerte' + (info ? ' alerte-info' : ''), role: info ? 'status' : 'alert' }, el('p', { text: texte }));
  if (reessayer) d.append(el('button', { type: 'button', class: 'btn btn-petit', onclick: reessayer }, 'Réessayer'));
  return d;
}
export function lienExterne(href, texte) {
  if (!href || !/^https?:\/\//i.test(href)) return document.createTextNode(texte || href || '');
  return el('a', { href, target: '_blank', rel: 'noopener noreferrer', class: 'lien-adresse' }, texte || href);
}
/* ---------- Dictionnaire ---------- */
export const AGREGATIONS = {
  somme: 'somme des communes',
  ratio: 'ratio recalculé (numérateur et dénominateur)',
  non_additif: 'valeur publiée par la source, sinon moyenne pondérée',
  texte: 'texte, à la commune seulement',
  calcul: 'calcul de la base, refait à chaque niveau',
};
export const AGREGATIONS_COURT = { somme: 'Somme', ratio: 'Ratio recalculé', non_additif: 'Non additif', texte: 'Texte (commune)', calcul: 'Calcul de la base' };

/** Bloc « définition et source » d'un indicateur du dictionnaire. */
export function blocDefinition(d, id, nbCommunes = 34875) {
  const source = el('p', {}, el('strong', {}, 'Source : '), d.source || 'non précisée', d.producteur ? ` (${d.producteur})` : '');
  if (d.adresse) source.append(' ', lienExterne(d.adresse, 'adresse de la source'));
  const details = [`Unité : ${d.unite || 'sans unité'}`, `année : ${d.annee || 'non précisée'}`, `règle de calcul : ${AGREGATIONS[d.agregation] || d.agregation || 'non précisée'}`];
  if (typeof d.communes_renseignees === 'number') details.push(`communes renseignées : ${fmtEntier(d.communes_renseignees)} sur ${fmtEntier(nbCommunes)}`);
  if (d.colonne) details.push(`colonne : ${d.colonne}`);
  return el('div', { class: 'ind-def', id }, el('p', {}, d.definition || 'Pas de définition.'), source, el('p', {}, details.join(' ; ') + '.'));
}

export function debounce(fn, ms = 150) {
  let t = null;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
/** Message d'erreur lisible pour l'utilisateur. */
export function messageErreur(e) {
  const m = (e && (e.message || String(e))) || 'erreur inconnue';
  return m.length > 400 ? m.slice(0, 400) + '...' : m;
}

/* ---------- Scripts externes (chargés à la demande) ---------- */
const scripts = new Map();
export function chargerScript(url, globale, integrite) {
  if (globale && window[globale]) return Promise.resolve(window[globale]);
  if (!scripts.has(url)) {
    scripts.set(url, new Promise((ok, ko) => {
      const s = document.createElement('script');
      s.src = url; s.async = true; s.crossOrigin = 'anonymous';
      if (integrite) s.integrity = integrite;
      s.onload = () => (globale && !window[globale] ? ko(new Error('Bibliothèque introuvable après chargement : ' + url)) : ok(globale ? window[globale] : undefined));
      s.onerror = () => { scripts.delete(url); s.remove(); ko(new Error('Impossible de charger la bibliothèque ' + url + '. Vérifiez votre connexion.')); };
      document.head.append(s);
    }));
  }
  return scripts.get(url);
}

/* ---------- Fichiers ---------- */
export function telecharger(blob, nom) {
  const url = URL.createObjectURL(blob);
  const a = el('a', { href: url, download: nom, style: 'display:none' });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
export async function lireJSON(nom) {
  const r = await fetch(adresseDonnees(nom), { cache: 'no-cache' });
  if (!r.ok) throw new Error(`Fichier data/${nom} introuvable (erreur ${r.status}).`);
  return r.json();
}
export async function lireTexte(nom) {
  const r = await fetch(adresseDonnees(nom), { cache: 'no-cache' });
  if (!r.ok) throw new Error(`Fichier data/${nom} introuvable (erreur ${r.status}).`);
  return r.text();
}

/** Analyse un CSV (guillemets, guillemets doublés, retours à la ligne dans un champ, BOM). Renvoie un tableau de lignes. */
export function analyserCSV(texte, sep = ',') {
  if (texte.charCodeAt(0) === 0xfeff) texte = texte.slice(1);
  const lignes = [];
  let ligne = [];
  let champ = '';
  let guillemets = false;
  const n = texte.length;
  for (let i = 0; i < n; i++) {
    const c = texte[i];
    if (guillemets) {
      if (c === '"') {
        if (texte[i + 1] === '"') { champ += '"'; i++; } else guillemets = false;
      } else champ += c;
    } else if (c === '"') guillemets = true;
    else if (c === sep) { ligne.push(champ); champ = ''; }
    else if (c === '\n') { ligne.push(champ); lignes.push(ligne); ligne = []; champ = ''; }
    else if (c !== '\r') champ += c;
  }
  if (champ !== '' || ligne.length) { ligne.push(champ); lignes.push(ligne); }
  return lignes;
}
