// Page « Dictionnaire » : tous les indicateurs, recherche, filtre par thème et par règle de calcul.
import { chargerMeta, chargerDictionnaire } from './data.js';
import { Tableau } from './table.js';
import { el, vider, fmtEntier, normaliser, contientTous, debounce, messageErreur, chargement, alerte, lienExterne, AGREGATIONS_COURT } from './util.js';

let dico = null; let meta = null; let tableau = null;
let parametres = null;
const $ = (id) => document.getElementById(id);

export async function init() {
  $('dic-recherche').addEventListener('input', debounce(filtrer, 150));
  $('dic-theme').addEventListener('change', filtrer);
  $('dic-agregation').addEventListener('change', filtrer);
  await preparer();
}

async function preparer() {
  const zone = $('dic-tableau');
  vider(zone).append(el('p', {}, chargement('Chargement du dictionnaire...')));
  try {
    meta = await chargerMeta();
    dico = await chargerDictionnaire();
  } catch (e) {
    vider(zone).append(alerte('Le dictionnaire ne peut pas être chargé. ' + messageErreur(e), { reessayer: async () => { if (await preparer()) show(parametres || new URLSearchParams()); } }));
    return false;
  }
  for (const d of dico.liste) d.rechercheComplete = d.texteRecherche + ' ' + normaliser(d.definition);
  const m = /\(([\d\s  ]+) communes\)/.exec(meta.geographie || '');
  const nbCommunes = m ? Number(m[1].replace(/\D/g, '')) : 34875;
  const sel = vider($('dic-theme'));
  sel.append(el('option', { value: '' }, `Tous les thèmes (${fmtEntier(dico.liste.length)})`));
  for (const [cle, t] of Object.entries(meta.themes)) sel.append(el('option', { value: cle }, `${t.libelle} (${fmtEntier((dico.parTheme.get(cle) || []).length)})`));
  tableau = new Tableau(zone, {
    legende: 'Dictionnaire des indicateurs',
    taillePage: 50,
    vide: 'Aucun indicateur ne correspond à ces critères.',
    colonnes: [
      { titre: 'Thème', type: 'texte', valeur: (d) => d.theme_libelle },
      { titre: 'Indicateur', sousTitre: 'libellé, nom technique, définition', type: 'texte', valeur: (d) => d.libelle, classe: 'cellule-lib', rendu: (d) => el('div', {},
        el('span', {}, d.libelle), el('span', { class: 'tech' }, d.colonne),
        el('details', { class: 'def' }, el('summary', {}, 'Définition'), el('p', {}, d.definition || 'Pas de définition.'),
          el('p', {}, el('a', { href: `#explorer?${new URLSearchParams({ theme: d.theme, niveau: d.agregation === 'texte' ? 'commune' : 'departement', ind: d.colonne })}` }, "Voir cet indicateur dans l'explorateur")))) },
      { titre: 'Unité', type: 'texte', valeur: (d) => d.unite },
      { titre: 'Année', type: 'texte', valeur: (d) => d.annee },
      { titre: 'Agrégation', type: 'texte', valeur: (d) => AGREGATIONS_COURT[d.agregation] || d.agregation },
      { titre: 'Source', type: 'texte', valeur: (d) => d.source, classe: 'cellule-lib', rendu: (d) => el('div', {},
        d.adresse ? lienExterne(d.adresse, d.source || d.adresse) : el('span', {}, d.source || '-'),
        d.producteur ? el('span', { class: 'tech' }, d.producteur) : null,
        d.source_ref ? el('span', { class: 'tech' }, 'Réf. ' + d.source_ref) : null) },
      { titre: 'Communes renseignées', sousTitre: `sur ${fmtEntier(nbCommunes)}`, type: 'num', valeur: (d) => d.communes_renseignees, format: (v) => fmtEntier(v) },
    ],
  });
  return true;
}

export function show(params) {
  parametres = params;
  if (params.has('theme')) $('dic-theme').value = params.get('theme');
  if (params.has('q')) $('dic-recherche').value = params.get('q');
  filtrer();
}

function filtrer() {
  if (!dico || !tableau) return;
  const theme = $('dic-theme').value;
  const agr = $('dic-agregation').value;
  const mots = normaliser($('dic-recherche').value).split(' ').filter(Boolean);
  const lignes = dico.liste.filter((d) => (!theme || d.theme === theme) && (!agr || d.agregation === agr)
    && (!mots.length || contientTous(d.rechercheComplete, mots)));
  tableau.charger(lignes);
  const n = lignes.length;
  $('dic-compte').textContent = `${fmtEntier(n)} indicateur${n > 1 ? 's' : ''} sur ${fmtEntier(dico.liste.length)}`;
  $('dic-compte').dataset.n = String(n);
}
