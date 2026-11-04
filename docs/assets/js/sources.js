// Page « Sources » : catalogue (sources.csv), filtres par état d'intégration et par thème, recherche, adresses cliquables.
import { chargerSources } from './data.js';
import { Tableau } from './table.js';
import { el, vider, fmtEntier, normaliser, contientTous, debounce, messageErreur, chargement, alerte, lienExterne } from './util.js';

let sources = null; let tableau = null; let parametres = null;
const $ = (id) => document.getElementById(id);
const COLLATOR = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
const BADGES = { 'Intégrée': 'badge-vert', 'À intégrer': 'badge-jaune', 'Production du projet': 'badge-bleu', 'Accès payant ou restreint': 'badge-rose' };
const DETAILS = ['Maille la plus fine', 'Maille (détail)', 'Couverture temporelle', 'Fréquence', 'Licence', 'Accès (détail)', 'Variables clés', 'Usage dans la base', 'Limites'];

export async function init() {
  $('src-recherche').addEventListener('input', debounce(filtrer, 150));
  $('src-integration').addEventListener('change', filtrer);
  $('src-theme').addEventListener('change', filtrer);
  await preparer();
}

function domaine(adresse) {
  try { return new URL(adresse).hostname.replace(/^www\./, ''); } catch (_) { return adresse; }
}

async function preparer() {
  const zone = $('src-tableau');
  vider(zone).append(el('p', {}, chargement('Chargement du catalogue des sources...')));
  try {
    sources = await chargerSources();
  } catch (e) {
    vider(zone).append(alerte('Le catalogue des sources ne peut pas être chargé. ' + messageErreur(e), { reessayer: async () => { if (await preparer()) show(parametres || new URLSearchParams()); } }));
    return false;
  }
  const liste = sources.liste;
  const compter = (cle) => {
    const m = new Map();
    for (const s of liste) { const v = s[cle] || 'Non précisé'; m.set(v, (m.get(v) || 0) + 1); }
    return [...m.entries()].sort((a, b) => b[1] - a[1] || COLLATOR.compare(a[0], b[0]));
  };
  const selEtat = vider($('src-integration'));
  selEtat.append(el('option', { value: '' }, `Tous les états (${fmtEntier(liste.length)})`));
  for (const [v, n] of compter('integration')) selEtat.append(el('option', { value: v }, `${v} (${fmtEntier(n)})`));
  const selTheme = vider($('src-theme'));
  selTheme.append(el('option', { value: '' }, 'Tous les thèmes'));
  for (const [v, n] of compter('Thème').sort((a, b) => COLLATOR.compare(a[0], b[0]))) selTheme.append(el('option', { value: v }, `${v} (${fmtEntier(n)})`));

  tableau = new Tableau(zone, {
    legende: 'Catalogue des sources',
    taillePage: 50,
    vide: 'Aucune source ne correspond à ces critères.',
    colonnes: [
      { titre: 'Réf.', type: 'texte', valeur: (s) => s['Réf.'] },
      { titre: 'Source', sousTitre: 'producteur et détails', type: 'texte', valeur: (s) => s.Source, classe: 'cellule-lib', rendu: (s) => {
        const det = el('details', { class: 'def' }, el('summary', {}, 'Détails'));
        for (const k of DETAILS) if (s[k]) det.append(el('p', {}, el('strong', {}, k + ' : '), s[k]));
        return el('div', {}, el('span', {}, s.Source), s.Producteur ? el('span', { class: 'tech' }, s.Producteur) : null, det.children.length > 1 ? det : null);
      } },
      { titre: 'Thème', type: 'texte', valeur: (s) => s['Thème'] },
      { titre: 'Type', type: 'texte', valeur: (s) => s.Type },
      { titre: 'Millésime', type: 'texte', valeur: (s) => s['Millésime'] },
      { titre: 'Accès', type: 'texte', valeur: (s) => s['Accès'] },
      { titre: 'État', type: 'texte', valeur: (s) => s.integration, rendu: (s) => el('span', { class: 'badge ' + (BADGES[s.integration] || '') }, s.integration || 'Non précisé') },
      { titre: 'Adresse', type: 'texte', valeur: (s) => s.Adresse, rendu: (s) => (s.Adresse ? lienExterne(s.Adresse, domaine(s.Adresse)) : document.createTextNode('-')) },
    ],
  });
  return true;
}

export function show(params) {
  parametres = params;
  if (params.has('etat')) $('src-integration').value = params.get('etat');
  if (params.has('theme')) $('src-theme').value = params.get('theme');
  if (params.has('q')) $('src-recherche').value = params.get('q');
  filtrer();
}

function filtrer() {
  if (!sources || !tableau) return;
  const etat = $('src-integration').value;
  const theme = $('src-theme').value;
  const mots = normaliser($('src-recherche').value).split(' ').filter(Boolean);
  const lignes = sources.liste.filter((s) => (!etat || (s.integration || 'Non précisé') === etat)
    && (!theme || (s['Thème'] || 'Non précisé') === theme)
    && (!mots.length || contientTous(s.texteRecherche, mots)));
  tableau.charger(lignes);
  const integrees = lignes.filter((s) => s.integration === 'Intégrée').length;
  const n = lignes.length;
  $('src-compte').textContent = `${fmtEntier(n)} source${n > 1 ? 's' : ''} sur ${fmtEntier(sources.liste.length)}, dont ${fmtEntier(integrees)} intégrée${integrees > 1 ? 's' : ''} à la base`;
  $('src-compte').dataset.n = String(n);
}
