// Page « Fiche territoire » : recherche avec autocomplétion, chiffres clés par thème comparés au niveau parent et à la France,
// trois graphiques (construction 2012-2024, décomposition du besoin 2030-2040, population depuis 1968).
import { chargerMeta, chargerDictionnaire, chargerTerritoires } from './data.js';
import { requete } from './db.js';
import {
  el, vider, fmtEntier, fmtNombre, nf, normaliser, contientTous, sqlTexte, sqlIdent, niveauDepuisCle, niveauDepuisLibelle,
  chargerScript, debounce, messageErreur, chargement, alerte, blocDefinition,
} from './util.js';

const CHART_URL = 'https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js';
const CHART_SRI = 'sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ';
const C = { bleu: '#005CCE', rose: '#FF3E65', vert: '#97C33D', texte: '#515459', grille: '#E4E5E7', surface: '#FFFFFF' };

// Indicateurs de la fiche (lus dans le dictionnaire pour les définitions et les sources).
const GROUPES = [
  { titre: 'Population et ménages', couleur: '#00ACFF', lignes: [
    { theme: 'population', col: 'pop_2023', libelle: 'Population (2023)', format: 'entier' },
    { theme: 'population', calcul: 'evolPop', besoin: ['pop_2012', 'pop_2023'], libelle: 'Évolution de la population par an, de 2012 à 2023', format: 'pctSigne',
      definition: "Taux d'évolution annuel moyen de la population entre les recensements 2012 et 2023 : (population 2023 / population 2012) puissance 1/11, moins 1. Calcul de la page à partir des colonnes pop_2012 et pop_2023 du thème Population (Insee, recensement de la population)." },
    { theme: 'menages', col: 'menc_2023', libelle: 'Ménages (2023)', format: 'entier' },
    { theme: 'menages', col: 'menc_taille_moy_2023', libelle: 'Personnes par ménage (2023)', format: 'dec2' },
  ] },
  { titre: 'Profils de ménages (2023)', couleur: '#FF3E65', lignes: [
    { theme: 'profils', col: 'prof_jeune_seul_2023', libelle: 'Jeunes actifs seuls', format: 'entier' },
    { theme: 'profils', col: 'prof_couple_sans_enf_2023', libelle: 'Couples primo-accédants sans enfant', format: 'entier' },
    { theme: 'profils', col: 'prof_famille_enf_2023', libelle: 'Familles avec enfants', format: 'entier' },
    { theme: 'profils', col: 'prof_monop_2023', libelle: 'Familles monoparentales', format: 'entier' },
    { theme: 'profils', col: 'prof_senior_6074_2023', libelle: 'Seniors autonomes de 60 à 74 ans', format: 'entier' },
    { theme: 'profils', col: 'prof_grand_age_2023', libelle: 'Grand âge (75 ans et plus)', format: 'entier' },
  ] },
  { titre: 'Parc de logements', couleur: '#97C33D', lignes: [
    { theme: 'logement', col: 'log_rp_2023', libelle: 'Résidences principales (2023)', format: 'entier' },
    { theme: 'logement', col: 'log_rs_2023', libelle: 'Résidences secondaires et logements occasionnels (2023)', format: 'entier' },
    { theme: 'logement', col: 'log_vac_2023', libelle: 'Logements vacants (2023)', format: 'entier' },
    { theme: 'logement', col: 'log_part_vac_2023', libelle: 'Taux de vacance (2023)', format: 'pct' },
    { theme: 'logement', col: 'log_part_proprio_2023', libelle: 'Part des ménages propriétaires (2023)', format: 'pct' },
    { theme: 'logement', col: 'log_part_loc_prive_2023', libelle: 'Part des locataires du parc privé (2023)', format: 'pct' },
    { theme: 'logement', col: 'log_part_loc_hlm_2023', libelle: 'Part des locataires HLM (2023)', format: 'pct' },
  ] },
  { titre: 'Prix, loyers et revenus', couleur: '#005CCE', lignes: [
    { theme: 'marche', col: 'dvf_prix_m2_maisons_2021_2026', libelle: 'Prix médian au m2 des maisons (juillet 2021 à juin 2026)', format: 'euro' },
    { theme: 'marche', col: 'dvf_prix_m2_appartements_2021_2026', libelle: 'Prix médian au m2 des appartements (juillet 2021 à juin 2026)', format: 'euro' },
    { theme: 'marche', col: 'loyers_m2_appartements_2025', libelle: "Loyer d'annonce au m2 des appartements, par mois (2025)", format: 'euroDec' },
    { theme: 'revenus', col: 'filo_med_2023', libelle: 'Niveau de vie médian par an (2023)', format: 'euro' },
    { theme: 'revenus', col: 'filo_tx_pauvrete_2023', libelle: 'Taux de pauvreté (2023)', format: 'pct' },
  ] },
  { titre: 'Construction et besoin en logement', couleur: '#FFC400', lignes: [
    { theme: 'construction', col: 'sit_autorises_3ans', libelle: 'Logements autorisés de 2023 à 2025', format: 'entier' },
    { theme: 'besoins', col: 'bes_construction_actuelle', libelle: 'Logements mis en chantier par an (moyenne 2023 à 2025)', format: 'entier' },
    { theme: 'besoins', col: 'bes_besoin_construction_3040', libelle: 'Besoin en construction par an (2030-2040)', format: 'entier' },
    { theme: 'besoins', col: 'bes_menages_3040', libelle: 'dont croissance des ménages', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_fluidite_3040', libelle: 'dont fluidité du parc', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_res_secondaires_3040', libelle: 'dont résidences secondaires nouvelles', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_renouvellement_3040', libelle: 'dont renouvellement du parc', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_mal_logement_3040', libelle: 'dont résorption du mal-logement', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_vacants_mobilises_3040', libelle: 'moins les logements vacants remis sur le marché', format: 'entier', sous: true },
    { theme: 'besoins', col: 'bes_manque_3040', libelle: 'Logements manquants par an (2030-2040)', format: 'entier' },
    { theme: 'besoins', col: 'bes_couverture_3040', libelle: 'Taux de couverture du besoin (2030-2040)', format: 'part' },
    { theme: 'besoins', col: 'bes_conclusion_3040', libelle: 'Conclusion (2030-2040)', format: 'texte' },
  ] },
  { titre: 'Emploi', couleur: '#61D2D1', lignes: [
    { theme: 'emploi', col: 'urssaf_salaries_2025', libelle: 'Salariés du secteur privé (fin 2025)', format: 'entier' },
    { theme: 'emploi', col: 'emp_tx_chom_2023', libelle: 'Taux de chômage des 15 à 64 ans (2023)', format: 'pct' },
  ] },
];
const FORMATS = {
  entier: (v) => fmtEntier(v),
  dec2: (v) => fmtNombre(v, 2),
  pct: (v) => `${fmtNombre(v, 1)} %`,
  pctSigne: (v) => `${v > 0 ? '+' : ''}${fmtNombre(v, 2)} %`,
  part: (v) => `${fmtNombre(v * 100, 0)} %`,
  euro: (v) => `${fmtEntier(v)} €`,
  euroDec: (v) => `${fmtNombre(v, 2)} €`,
  texte: (v) => String(v),
};
const COMPOSANTES = [
  ['bes_menages_3040', 'Croissance des ménages'],
  ['bes_fluidite_3040', 'Fluidité du parc'],
  ['bes_res_secondaires_3040', 'Résidences secondaires'],
  ['bes_renouvellement_3040', 'Renouvellement du parc'],
  ['bes_mal_logement_3040', 'Résorption du mal-logement'],
  ['bes_vacants_mobilises_3040', 'Vacants remis sur le marché'],
];
const ORDRE_THEMES = ['besoins', 'construction', 'population', 'menages', 'logement', 'profils', 'marche', 'revenus', 'emploi'];
const RANG = { France: 0, 'Région': 1, 'Département': 2, Commune: 3, EPCI: 4, "Zone d'emploi": 5, "Territoire d'industrie": 6 };
const COLLATOR = new Intl.Collator('fr', { sensitivity: 'base' });

let meta = null; let dico = null; let terr = null;
let courant = null;
let jeton = 0;
let graphiques = [];
let suggestions = [];
let actif = -1;
let derniereRecherche = '';
const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ init / show */
export async function init() {
  const input = $('ft-recherche');
  const liste = $('ft-suggestions');
  const proposerDiffere = debounce(() => proposer(input.value), 90);
  input.addEventListener('input', proposerDiffere);
  input.addEventListener('focus', () => { if (!terr) prechargerTerritoires(); });
  input.addEventListener('keydown', async (ev) => {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); if (liste.hidden) await proposer(input.value); else deplacer(1); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); deplacer(-1); }
    else if (ev.key === 'Enter') {
      ev.preventDefault();
      if (derniereRecherche !== input.value || liste.hidden) await proposer(input.value);
      if (suggestions.length) choisir(actif >= 0 ? actif : 0);
    } else if (ev.key === 'Escape') { if (!liste.hidden) { ev.preventDefault(); fermer(); } }
  });
  input.addEventListener('blur', () => setTimeout(fermer, 180));
  liste.addEventListener('mousedown', (ev) => {
    const li = ev.target.closest('li[data-i]');
    if (li) { ev.preventDefault(); choisir(Number(li.dataset.i)); }
  });
  prechargerTerritoires();
}

export async function show(params) {
  const cle = params.get('niveau');
  const code = params.get('code');
  if (cle && code) await chargerFiche(cle, code);
}

async function prechargerTerritoires() {
  try {
    terr = await chargerTerritoires();
    $('ft-aide').textContent = 'Tapez au moins deux lettres, puis choisissez avec les flèches et la touche Entrée, ou cliquez sur un nom.';
  } catch (e) {
    $('ft-aide').textContent = 'La liste des territoires ne se charge pas : ' + messageErreur(e);
  }
}

/* ------------------------------------------------------------------ autocomplétion */
function chercher(texte) {
  const q = normaliser(texte);
  const brut = String(texte || '').trim().toUpperCase();
  if (!brut || (q.length < 2 && !/^\d/.test(brut))) return [];
  const mots = q.split(' ').filter(Boolean);
  const res = [];
  for (const t of terr.liste) {
    let score = -1;
    if (t.code.toUpperCase() === brut) score = 0;
    else if (t.recherche === q) score = 1;
    else if (t.recherche.startsWith(q)) score = 2;
    else if (t.recherche.includes(' ' + q)) score = 3;
    else if (mots.length > 1 ? contientTous(t.recherche, mots) : t.recherche.includes(q)) score = 4;
    if (score >= 0) res.push([score, t]);
  }
  res.sort((a, b) => a[0] - b[0] || (RANG[a[1].niveau] ?? 9) - (RANG[b[1].niveau] ?? 9) || a[1].nom.length - b[1].nom.length || COLLATOR.compare(a[1].nom, b[1].nom));
  return res.slice(0, 15).map((r) => r[1]);
}

function descriptionCourte(t) {
  const parts = [t.niveau === 'EPCI' ? 'Intercommunalité (EPCI)' : t.niveau];
  if (t.niveau !== 'France') parts.push(t.code);
  if (t.niveau === 'Commune' || t.niveau === 'EPCI' || t.niveau === "Zone d'emploi" || t.niveau === "Territoire d'industrie") { if (t.libdep) parts.push(t.libdep); }
  else if (t.niveau === 'Département' && t.libreg) parts.push(t.libreg);
  return parts.join(' · ');
}

async function proposer(texte) {
  const liste = $('ft-suggestions');
  const input = $('ft-recherche');
  if (!terr) {
    try { terr = await chargerTerritoires(); } catch (e) { $('ft-aide').textContent = 'La liste des territoires ne se charge pas : ' + messageErreur(e); return; }
  }
  derniereRecherche = texte;
  suggestions = chercher(texte);
  actif = -1;
  vider(liste);
  if (!suggestions.length) {
    if (normaliser(texte).length >= 2) {
      liste.append(el('li', { class: 'sug-vide', role: 'option', 'aria-disabled': 'true', 'aria-selected': 'false' }, 'Aucun territoire trouvé.'));
      liste.hidden = false; input.setAttribute('aria-expanded', 'true');
    } else fermer();
    return;
  }
  suggestions.forEach((t, i) => liste.append(el('li', { id: `ft-sug-${i}`, role: 'option', 'aria-selected': 'false', 'data-i': i },
    el('span', { class: 'sug-nom' }, t.nom), el('span', { class: 'sug-meta' }, descriptionCourte(t)))));
  liste.hidden = false;
  input.setAttribute('aria-expanded', 'true');
  input.removeAttribute('aria-activedescendant');
}

function deplacer(pas) {
  if (!suggestions.length) return;
  actif = (actif + pas + suggestions.length) % suggestions.length;
  const liste = $('ft-suggestions');
  for (const li of liste.querySelectorAll('li[data-i]')) li.setAttribute('aria-selected', String(Number(li.dataset.i) === actif));
  const li = $(`ft-sug-${actif}`);
  if (li) { li.scrollIntoView({ block: 'nearest' }); $('ft-recherche').setAttribute('aria-activedescendant', li.id); }
}

function fermer() {
  const liste = $('ft-suggestions');
  liste.hidden = true;
  $('ft-recherche').setAttribute('aria-expanded', 'false');
  $('ft-recherche').removeAttribute('aria-activedescendant');
}

function adresseFiche(t) {
  return `#territoire?niveau=${niveauDepuisLibelle(t.niveau).cle}&code=${encodeURIComponent(t.code)}`;
}

function choisir(i) {
  const t = suggestions[i];
  if (!t) return;
  fermer();
  $('ft-recherche').value = t.nom;
  const adresse = adresseFiche(t);
  if (location.hash === adresse) chargerFiche(niveauDepuisLibelle(t.niveau).cle, t.code);
  else location.hash = adresse;
}

/* ------------------------------------------------------------------ fiche */
function trouverParent(t) {
  if (t.niveau === 'Commune' && t.dep) return { t: terr.trouver('Département', t.dep), role: 'Département' };
  if (t.niveau === 'Département' && t.reg) return { t: terr.trouver('Région', t.reg), role: 'Région' };
  if (["Zone d'emploi", 'EPCI', "Territoire d'industrie"].includes(t.niveau) && t.dep) return { t: terr.trouver('Département', t.dep), role: 'Département principal' };
  return null;
}

function colonnesNecessaires() {
  const parTheme = new Map();
  const ajouter = (th, c) => {
    if (!dico.entree(th, c)) return;
    if (!parTheme.has(th)) parTheme.set(th, new Set());
    parTheme.get(th).add(c);
  };
  for (const g of GROUPES) for (const l of g.lignes) { if (l.col) ajouter(l.theme, l.col); for (const b of l.besoin || []) ajouter(l.theme, b); }
  for (const c of anneesConstruction()) ajouter('construction', c.col);
  for (const [c] of COMPOSANTES) ajouter('besoins', c);
  ajouter('besoins', 'bes_besoin_construction_3040');
  ajouter('besoins', 'bes_besoin_avant_vacants_3040');
  ajouter('besoins', 'bes_classe_3040');
  for (const c of anneesPopulation()) ajouter('population', c.col);
  return parTheme;
}

function anneesConstruction() {
  return (dico.parTheme.get('construction') || []).map((d) => {
    const m = /^sit_commences_(\d{4})$/.exec(d.colonne);
    return m ? { annee: Number(m[1]), col: d.colonne } : null;
  }).filter(Boolean).sort((a, b) => a.annee - b.annee);
}

function anneesPopulation() {
  const tout = (dico.parTheme.get('population') || []).map((d) => {
    const m = /^pophist_(psdc|pmun)_(\d{4})$/.exec(d.colonne);
    return m ? { annee: Number(m[2]), type: m[1], col: d.colonne } : null;
  }).filter(Boolean);
  const pmun = tout.filter((x) => x.type === 'pmun');
  const derniere = Math.max(...pmun.map((x) => x.annee), 0);
  const premiere = Math.min(...pmun.map((x) => x.annee), 9999);
  return tout.filter((x) => x.type === 'psdc' || (x.annee - premiere) % 3 === 0 || x.annee === derniere).sort((a, b) => a.annee - b.annee);
}

async function chargerFiche(cleNiveau, code) {
  const niveau = niveauDepuisCle(cleNiveau);
  const fiche = $('ft-fiche');
  if (!niveau) { statut(alerte(`Niveau inconnu : « ${cleNiveau} ».`)); return; }
  const cle = niveau.libelle + '|' + code;
  if (cle === courant && fiche.dataset.etat) return;
  courant = cle;
  const t = ++jeton;
  detruireGraphiques();
  fiche.hidden = true;
  delete fiche.dataset.etat;
  statut(chargement('Chargement de la fiche...'));
  try {
    meta = await chargerMeta();
    dico = await chargerDictionnaire();
    terr = await chargerTerritoires();
  } catch (e) {
    if (t !== jeton) return;
    courant = null;
    statut(alerte('La fiche ne peut pas être préparée. ' + messageErreur(e), { reessayer: () => chargerFiche(cleNiveau, code) }));
    return;
  }
  if (t !== jeton) return;
  const cible = terr.trouver(niveau.libelle, code);
  if (!cible) {
    courant = null;
    statut(alerte(`Territoire introuvable : niveau ${niveau.libelle}, code ${code}. Cherchez-le par son nom ci-dessus.`));
    return;
  }
  const parent = trouverParent(cible);
  const france = terr.trouver('France', 'FR');
  const comparaisons = [{ t: cible, role: cible.niveau }];
  if (parent && parent.t) comparaisons.push(parent);
  if (france && cible !== france) comparaisons.push({ t: france, role: 'France' });

  $('ft-recherche').value = cible.nom;
  document.title = `${cible.nom} - Fiche territoire - Besoins en logement - base de données`;

  const vue = construireFiche(cible, comparaisons);
  vider(fiche).append(vue.racine);
  fiche.hidden = false;
  fiche.dataset.etat = 'chargement';
  statut('');

  const chart = chargerScript(CHART_URL, 'Chart', CHART_SRI).then((Chart) => { reglerChart(Chart); return Chart; }, (e) => e);
  const valeurs = new Map();
  const etats = new Map();
  const besoins = colonnesNecessaires();
  const ou = comparaisons.map(({ t: x }) => `(niveau = ${sqlTexte(x.niveau)} AND code = ${sqlTexte(x.code)})`).join(' OR ');
  const erreurs = [];
  const dessins = [];
  for (const theme of ORDRE_THEMES) {
    const cols = besoins.get(theme);
    if (!cols || !meta.themes[theme]) continue;
    try {
      const select = [...cols].map((c) => (dico.entree(theme, c).agregation === 'texte' ? sqlIdent(c) : `CAST(${sqlIdent(c)} AS DOUBLE) AS ${sqlIdent(c)}`));
      const res = await requete(`SELECT niveau, code, ${select.join(', ')} FROM read_parquet(${sqlTexte(meta.themes[theme].fichier)}) WHERE ${ou}`, [meta.themes[theme].fichier]);
      if (t !== jeton) return;
      for (const l of res.lignes) {
        const k = l[0] + '|' + l[1];
        if (!valeurs.has(k)) valeurs.set(k, new Map());
        res.colonnes.slice(2).forEach((c, j) => valeurs.get(k).set(c, l[j + 2]));
      }
      etats.set(theme, 'ok');
    } catch (e) {
      if (t !== jeton) return;
      etats.set(theme, 'erreur');
      erreurs.push(e);
    }
    vue.majValeurs(valeurs, etats);
    if (theme === 'besoins') vue.majConclusion(valeurs, etats);
    if (theme === 'construction') dessins.push(dessiner(t, chart, vue.graphiques.construction, graphiqueConstruction(vue, cible, valeurs)));
    if (theme === 'besoins') dessins.push(dessiner(t, chart, vue.graphiques.besoin, graphiqueBesoin(vue, cible, valeurs)));
    if (theme === 'population') dessins.push(dessiner(t, chart, vue.graphiques.population, graphiquePopulation(vue, cible, valeurs)));
  }
  if (t !== jeton) return;
  vue.finir();
  await Promise.allSettled(dessins);
  if (t !== jeton) return;
  fiche.dataset.etat = 'complet';
  if (erreurs.length) statut(alerte(`Une partie de la fiche n'a pas pu être lue. ${messageErreur(erreurs[0])}`, { reessayer: () => { courant = null; chargerFiche(cleNiveau, code); } }));
}

function statut(contenu) {
  const z = vider($('ft-statut'));
  if (contenu) z.append(contenu);
}

function lienTerritoire(t, texte) {
  return el('a', { href: adresseFiche(t) }, texte || t.nom);
}

function lienExplorateur(cible) {
  const p = new URLSearchParams({ theme: 'besoins' });
  let texte = '';
  if (cible.niveau === 'France') { p.set('niveau', 'region'); texte = "Comparer les régions dans l'explorateur"; }
  else if (cible.niveau === 'Région') { p.set('niveau', 'departement'); p.set('reg', cible.code); texte = "Comparer les départements de la région dans l'explorateur"; }
  else if (cible.niveau === 'Département') { p.set('niveau', 'commune'); p.set('dep', cible.code); texte = "Voir les communes du département dans l'explorateur"; }
  else if (cible.niveau === 'EPCI') { p.set('niveau', 'commune'); p.set('epci', cible.code); texte = "Voir les communes de l'intercommunalité dans l'explorateur"; }
  else if (cible.niveau === 'Commune' && cible.epci) { p.set('niveau', 'commune'); p.set('epci', cible.epci); texte = "Comparer avec les communes de l'intercommunalité"; }
  else if (cible.reg) { p.set('niveau', niveauDepuisLibelle(cible.niveau).cle); p.set('reg', cible.reg); texte = "Comparer avec les territoires du même niveau dans la région"; }
  return texte ? el('a', { class: 'btn btn-petit', href: '#explorer?' + p.toString() }, texte) : null;
}

function construireFiche(cible, comparaisons) {
  // En-tête
  const appart = [];
  const ajouter = (lib, niveau, code, nom) => {
    const x = code ? terr.trouver(niveau, code) : null;
    if (x) appart.push([lib, lienTerritoire(x, nom || x.nom)]);
  };
  if (cible.niveau === 'Commune') {
    ajouter('Département', 'Département', cible.dep, cible.libdep ? `${cible.libdep} (${cible.dep})` : null);
    ajouter('Région', 'Région', cible.reg);
    ajouter('Intercommunalité', 'EPCI', cible.epci);
    ajouter("Zone d'emploi", "Zone d'emploi", cible.ze2020);
    ajouter("Territoire d'industrie", "Territoire d'industrie", cible.id_ti);
  } else if (cible.niveau === 'Département') ajouter('Région', 'Région', cible.reg);
  else if (cible.niveau !== 'France' && cible.niveau !== 'Région') {
    ajouter('Département principal', 'Département', cible.dep);
    ajouter('Région principale', 'Région', cible.reg);
  }
  const pAppart = el('p', { class: 'ft-appart' });
  appart.forEach(([lib, lien], i) => { if (i) pAppart.append(' · '); pAppart.append(`${lib} : `, lien); });
  const explorer = lienExplorateur(cible);
  const entete = el('div', { class: 'carte ft-entete' },
    el('p', { class: 'surtitre' }, cible.niveau === 'France' ? 'France entière' : `${cible.niveau === 'EPCI' ? 'Intercommunalité (EPCI)' : cible.niveau} · code ${cible.code}`),
    el('h2', { id: 'ft-nom', tabindex: '-1' }, cible.nom),
    appart.length ? pAppart : null,
    el('div', { class: 'ft-actions' }, explorer));

  const conclusion = el('div', { class: 'ft-conclusion', 'aria-live': 'polite' }, el('p', {}, chargement('Lecture du besoin en logement...')));

  // Tableau de comparaison
  const cellules = [];
  const tete = el('tr', {}, el('th', { scope: 'col' }, 'Indicateur'),
    ...comparaisons.map((c, j) => el('th', { scope: 'col', class: 'num' + (j === 0 ? ' col-cible' : '') }, c.t.nom,
      c.role && c.role !== 'France' ? el('span', { class: 'entete-unite' }, c.role === 'EPCI' ? 'Intercommunalité' : c.role) : null)));
  const corps = el('tbody');
  const ncol = comparaisons.length + 1;
  for (const g of GROUPES) {
    corps.append(el('tr', { class: 'groupe' }, el('th', { scope: 'colgroup', colspan: ncol }, el('span', { class: 'pastille', style: `background:${g.couleur}` }), g.titre)));
    for (const l of g.lignes) {
      const d = l.col ? dico.entree(l.theme, l.col) : null;
      if (l.col && !d) continue;
      const idDef = `ft-def-${l.col || l.calcul}`;
      const info = el('button', { type: 'button', class: 'bouton-info', 'aria-expanded': 'false', 'aria-controls': idDef, 'aria-label': `Définition et source : ${l.libelle}`, title: 'Définition et source' }, 'i');
      const ligneDef = el('tr', { class: 'def-ligne', hidden: true }, el('td', { colspan: ncol },
        d ? blocDefinition(d, idDef) : el('div', { class: 'ind-def', id: idDef }, el('p', {}, l.definition || ''))));
      info.addEventListener('click', () => {
        const ouvert = info.getAttribute('aria-expanded') === 'true';
        info.setAttribute('aria-expanded', String(!ouvert));
        ligneDef.hidden = ouvert;
      });
      const tds = comparaisons.map((c, j) => el('td', { class: (l.format === 'texte' ? 'texte-court' : 'num') + (j === 0 ? ' col-cible' : '') }, '…'));
      cellules.push({ l, tds });
      corps.append(el('tr', { class: l.sous ? 'sous-ligne' : null }, el('th', { scope: 'row', class: 'lib' }, el('div', { class: 'lib-ligne' }, el('span', {}, l.libelle), info)), ...tds), ligneDef);
    }
  }
  const table = el('table', { class: 'donnees comparaison', 'aria-busy': 'true' },
    el('caption', { class: 'visuellement-cache' }, `Chiffres clés : ${comparaisons.map((c) => c.t.nom).join(', ')}`),
    el('thead', {}, tete), corps);
  const notes = el('p', { class: 'note' }, 'Un tiret signale une valeur absente ou couverte par le secret statistique. Pour les revenus (Filosofi), la valeur France est celle de la France métropolitaine. Les effectifs de profils de ménages sont des approximations décrites dans le dictionnaire.');
  const blocTableau = el('div', { class: 'carte ft-tableau' }, el('h2', { class: 'puce' }, 'Chiffres clés'), el('div', { class: 'table-defile' }, table), notes);

  // Graphiques
  const cadre = (id, titre, sousTitre) => {
    const zone = el('div', { class: 'graphique-zone' }, el('p', {}, chargement('Chargement...')));
    const fig = el('figure', { class: 'carte graphique', id }, el('h3', {}, titre), el('p', { class: 'sous-titre' }, sousTitre), zone);
    return { fig, zone };
  };
  const gConstruction = cadre('ft-g-construction', 'Logements commencés chaque année', 'De 2012 à 2024, comparés au besoin en construction par an de 2030 à 2040 (logements)');
  const gBesoin = cadre('ft-g-besoin', 'Décomposition du besoin, 2030-2040', 'Logements par an : les composantes, moins les vacants remis sur le marché, donnent le besoin en construction');
  const gPopulation = cadre('ft-g-population', 'Population depuis 1968', 'Habitants : population sans doubles comptes jusqu\'en 1999, population municipale ensuite');
  const blocGraphiques = el('div', { class: 'ft-graphiques' }, gConstruction.fig, gBesoin.fig, gPopulation.fig);

  const racine = el('div', {}, entete, conclusion, blocTableau, el('h2', { class: 'puce' }, 'Graphiques'), blocGraphiques);

  return {
    racine,
    graphiques: { construction: gConstruction, besoin: gBesoin, population: gPopulation },
    majValeurs(valeurs, etats) {
      for (const { l, tds } of cellules) {
        if (!etats.has(l.theme)) continue;
        comparaisons.forEach((c, j) => {
          const td = tds[j];
          if (etats.get(l.theme) === 'erreur') { td.textContent = 'erreur'; td.classList.add('vide'); return; }
          const v = valeurLigne(l, valeurs.get(c.t.niveau + '|' + c.t.code));
          const vide = v == null || (typeof v === 'number' && !Number.isFinite(v));
          td.textContent = vide ? '-' : FORMATS[l.format](v);
          td.classList.toggle('vide', vide);
          if (vide) td.title = 'Valeur absente ou secrète'; else td.removeAttribute('title');
        });
      }
    },
    majConclusion(valeurs, etats) {
      vider(conclusion);
      const v = valeurs.get(cible.niveau + '|' + cible.code);
      if (etats.get('besoins') !== 'ok' || !v) { conclusion.append(alerte('Le besoin en logement de ce territoire n\'a pas pu être lu.')); return; }
      const besoin = v.get('bes_besoin_construction_3040');
      const construction = v.get('bes_construction_actuelle');
      const couverture = v.get('bes_couverture_3040');
      const classe = v.get('bes_classe_3040');
      const texte = v.get('bes_conclusion_3040');
      if (besoin == null) {
        conclusion.append(el('p', { class: 'conclusion conclusion-0' }, el('span', {}, `Besoin en logement 2030-2040 : ${texte || 'non calculé pour ce territoire'}.`)));
        return;
      }
      conclusion.append(el('p', { class: `conclusion conclusion-${classe || 0}` }, el('span', {},
        `Besoin en construction de ${fmtEntier(besoin)} logements par an de 2030 à 2040, pour ${fmtEntier(construction)} mis en chantier par an aujourd'hui`,
        couverture != null ? ` (couverture : ${fmtNombre(couverture * 100, 0)} %).` : '.',
        el('small', {}, `Conclusion : ${texte || 'non disponible'}.`))));
    },
    finir() { table.removeAttribute('aria-busy'); },
  };
}

function valeurLigne(l, v) {
  if (!v) return null;
  if (l.calcul === 'evolPop') {
    const a = v.get('pop_2012'); const b = v.get('pop_2023');
    return a > 0 && b > 0 ? (Math.pow(b / a, 1 / 11) - 1) * 100 : null;
  }
  const x = v.get(l.col);
  return x === undefined ? null : x;
}

/* ------------------------------------------------------------------ graphiques */
function detruireGraphiques() {
  for (const g of graphiques) { try { g.destroy(); } catch (_) { /* déjà détruit */ } }
  graphiques = [];
}

function reglerChart(Chart) {
  Chart.defaults.font.family = 'Arial, Helvetica, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = C.texte;
  Chart.defaults.borderColor = C.grille;
}

/** Dessine un graphique quand Chart.js est prêt. Sans Chart.js, le tableau de données reste affiché. */
async function dessiner(t, chartPromise, cadre, fn) {
  const Chart = await chartPromise;
  if (t !== jeton) return;
  try {
    fn(Chart instanceof Error ? null : Chart);
  } catch (e) {
    console.warn(e);
    messageGraphique(cadre, "Le graphique n'a pas pu s'afficher.");
  }
}

function canvasOuMessage(Chart, cadre, label) {
  if (!Chart) {
    messageGraphique(cadre, "Le graphique n'a pas pu s'afficher (bibliothèque de graphiques non chargée). Les valeurs sont dans le tableau ci-dessous.");
    return null;
  }
  return zoneCanvas(cadre, label);
}

const compact = new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 });
function graduation(max) { return (v) => (Math.abs(max) >= 10000 ? compact.format(v) : nf(0).format(v)); }
const reduit = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function tableDonnees(titre, entetes, lignes) {
  return el('details', {}, el('summary', {}, 'Voir les données du graphique'),
    el('table', { class: 'donnees' }, el('caption', { class: 'visuellement-cache' }, titre),
      el('thead', {}, el('tr', {}, ...entetes.map((h, i) => el('th', { scope: 'col', class: i ? 'num' : '' }, h)))),
      el('tbody', {}, ...lignes.map((l) => el('tr', {}, ...l.map((c, i) => el('td', { class: i ? 'num' : '' }, c)))))));
}

function zoneCanvas(cadre, label) {
  const canvas = el('canvas', { role: 'img', 'aria-label': label });
  vider(cadre.zone).append(canvas);
  return canvas;
}
function messageGraphique(cadre, texte) {
  vider(cadre.zone).append(el('p', { class: 'note' }, texte));
  cadre.zone.style.height = 'auto';
}

function optionsBase() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    locale: 'fr-FR',
    animation: reduit() ? false : { duration: 350 },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#2F3236', padding: 10, cornerRadius: 6, boxPadding: 4 },
    },
  };
}

function graphiqueConstruction(vue, cible, valeurs) {
  return (Chart) => {
    const cadre = vue.graphiques.construction;
    const v = valeurs.get(cible.niveau + '|' + cible.code);
    const annees = anneesConstruction();
    const points = annees.map((a) => (v ? v.get(a.col) : null));
    if (!v || points.every((x) => x == null)) { messageGraphique(cadre, 'Pas de données de construction pour ce territoire.'); return; }
    const besoin = valeurs.get(cible.niveau + '|' + cible.code)?.get('bes_besoin_construction_3040');
    const max = Math.max(...points.filter((x) => x != null), besoin || 0);
    const datasets = [{
      type: 'bar', label: 'Logements commencés', data: points, backgroundColor: C.bleu, hoverBackgroundColor: '#3380D8',
      borderRadius: 4, borderSkipped: 'start', maxBarThickness: 24, order: 2, pointStyle: 'rect',
    }];
    if (besoin != null) {
      datasets.push({
        type: 'line', label: 'Besoin en construction par an, 2030-2040', data: annees.map(() => besoin), borderColor: C.rose, backgroundColor: C.rose,
        borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 0, pointHitRadius: 0, order: 1, pointStyle: 'line', fill: false,
      });
    }
    const canvas = canvasOuMessage(Chart, cadre, `Graphique en barres : logements commencés chaque année de ${annees[0].annee} à ${annees[annees.length - 1].annee} à ${cible.nom}${besoin != null ? `, comparés au besoin de ${fmtEntier(besoin)} logements par an` : ''}. Les valeurs sont dans le tableau qui suit.`);
    if (canvas) {
      const o = optionsBase();
      o.plugins.legend = { display: besoin != null, position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 14, boxHeight: 8, padding: 12 } };
      o.plugins.tooltip.callbacks = { label: (ctx) => ` ${ctx.dataset.label} : ${fmtEntier(ctx.parsed.y)}` };
      o.scales = {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, autoSkipPadding: 6 } },
        y: { beginAtZero: true, grid: { color: C.grille }, border: { display: false }, ticks: { callback: graduation(max), maxTicksLimit: 6 } },
      };
      graphiques.push(new Chart(canvas, { type: 'bar', data: { labels: annees.map((a) => String(a.annee)), datasets }, options: o }));
    }
    cadre.fig.append(tableDonnees('Logements commencés par année', ['Année', 'Logements commencés'], annees.map((a, i) => [String(a.annee), points[i] == null ? '-' : fmtEntier(points[i])])
      .concat(besoin != null ? [['Besoin par an, 2030-2040', fmtEntier(besoin)]] : [])));
  };
}

const etiquettesBarres = {
  id: 'etiquettesBarres',
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    const donnees = chart.data.datasets[0].data;
    ctx.save();
    ctx.font = 'bold 12px Arial, Helvetica, sans-serif';
    ctx.fillStyle = C.texte;
    ctx.textBaseline = 'middle';
    meta.data.forEach((barre, i) => {
      const v = donnees[i];
      if (v == null) return;
      const negatif = v < 0;
      ctx.textAlign = negatif ? 'right' : 'left';
      ctx.fillText(fmtEntier(v), barre.x + (negatif ? -6 : 6), barre.y);
    });
    ctx.restore();
  },
};

function graphiqueBesoin(vue, cible, valeurs) {
  return (Chart) => {
    const cadre = vue.graphiques.besoin;
    const v = valeurs.get(cible.niveau + '|' + cible.code);
    const total = v ? v.get('bes_besoin_construction_3040') : null;
    if (total == null) { messageGraphique(cadre, 'Pas de besoin calculé pour ce territoire (hors champ, par exemple Mayotte).'); return; }
    const libelles = COMPOSANTES.map((c) => c[1]).concat('Besoin en construction');
    const donnees = COMPOSANTES.map(([c]) => {
      const x = v.get(c);
      return x == null ? null : (c === 'bes_vacants_mobilises_3040' ? -x : x);
    }).concat(total);
    const couleurs = COMPOSANTES.map(([c]) => (c === 'bes_vacants_mobilises_3040' ? C.rose : C.bleu)).concat(C.vert);
    const canvas = canvasOuMessage(Chart, cadre, `Graphique en barres horizontales : décomposition du besoin en construction 2030-2040 à ${cible.nom}, soit ${fmtEntier(total)} logements par an. Les valeurs sont écrites au bout des barres et dans le tableau qui suit.`);
    if (canvas) {
      const o = optionsBase();
      o.indexAxis = 'y';
      o.interaction = { mode: 'nearest', axis: 'y', intersect: false };
      o.layout = { padding: { right: 8, left: 4 } };
      o.plugins.tooltip.callbacks = {
        title: (items) => libelles[items[0].dataIndex],
        label: (ctx) => ` ${fmtEntier(ctx.parsed.x)} logements par an`,
      };
      const vals = donnees.filter((x) => x != null);
      const mx = Math.max(0, ...vals); const mn = Math.min(0, ...vals);
      const marge = (mx - mn || 1) * 0.3; // place pour les valeurs écrites au bout des barres
      o.scales = {
        x: { suggestedMin: mn < 0 ? mn - marge : 0, suggestedMax: mx + marge, grid: { color: C.grille }, border: { display: false }, ticks: { callback: graduation(mx - mn), maxTicksLimit: 5 } },
        y: { grid: { display: false }, ticks: { autoSkip: false } },
      };
      // Sur un écran étroit, les libellés longs passent sur deux lignes au lieu d'être coupés.
      const etroit = cadre.zone.clientWidth < 480;
      const etiquettes = libelles.map((lib) => {
        if (!etroit || lib.length <= 16) return lib;
        const milieu = lib.length / 2;
        let coupe = -1;
        for (let i = 0; i < lib.length; i++) if (lib[i] === ' ' && (coupe < 0 || Math.abs(i - milieu) < Math.abs(coupe - milieu))) coupe = i;
        return coupe > 0 ? [lib.slice(0, coupe), lib.slice(coupe + 1)] : lib;
      });
      graphiques.push(new Chart(canvas, {
        type: 'bar',
        data: { labels: etiquettes, datasets: [{ label: 'Logements par an', data: donnees, backgroundColor: couleurs, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 22, categoryPercentage: 0.8, barPercentage: 0.9 }] },
        options: o,
        plugins: [etiquettesBarres],
      }));
    }
    cadre.fig.append(el('ul', { class: 'legende', 'aria-hidden': 'true' },
      el('li', {}, el('span', { class: 'cle', style: `background:${C.bleu}` }), 'composantes'),
      el('li', {}, el('span', { class: 'cle', style: `background:${C.rose}` }), 'vacants (en moins)'),
      el('li', {}, el('span', { class: 'cle', style: `background:${C.vert}` }), 'besoin en construction')));
    cadre.fig.append(tableDonnees('Décomposition du besoin 2030-2040', ['Composante', 'Logements par an'], libelles.map((lib, i) => [lib, donnees[i] == null ? '-' : fmtEntier(donnees[i])])));
  };
}

function graphiquePopulation(vue, cible, valeurs) {
  return (Chart) => {
    const cadre = vue.graphiques.population;
    const v = valeurs.get(cible.niveau + '|' + cible.code);
    const annees = anneesPopulation();
    const points = annees.map((a) => ({ x: a.annee, y: v ? v.get(a.col) : null })).filter((p) => p.y != null);
    if (points.length < 2) { messageGraphique(cadre, 'Pas de série de population pour ce territoire.'); return; }
    const max = Math.max(...points.map((p) => p.y));
    const canvas = canvasOuMessage(Chart, cadre, `Graphique en courbe : population de ${cible.nom} de ${points[0].x} à ${points[points.length - 1].x}, de ${fmtEntier(points[0].y)} à ${fmtEntier(points[points.length - 1].y)} habitants. Les valeurs sont dans le tableau qui suit.`);
    if (canvas) {
      const o = optionsBase();
      o.interaction = { mode: 'nearest', axis: 'x', intersect: false };
      o.layout = { padding: { left: 6, right: 10, top: 6 } };
      o.plugins.tooltip.callbacks = { title: (items) => String(items[0].parsed.x), label: (ctx) => ` ${fmtEntier(ctx.parsed.y)} habitants` };
      o.scales = {
        x: { type: 'linear', min: points[0].x, max: points[points.length - 1].x, grid: { display: false }, ticks: { callback: (x) => String(x), maxTicksLimit: 7, stepSize: 10 } },
        y: { grid: { color: C.grille }, border: { display: false }, grace: '8%', ticks: { callback: graduation(max), maxTicksLimit: 6 } },
      };
      graphiques.push(new Chart(canvas, {
        type: 'line',
        data: { datasets: [{ label: 'Population', data: points, borderColor: C.bleu, backgroundColor: C.bleu, fill: false, borderWidth: 2, tension: 0, clip: false,
          pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: C.bleu, pointBorderColor: C.surface, pointBorderWidth: 2, pointHitRadius: 12 }] },
        options: o,
      }));
    }
    cadre.fig.append(tableDonnees('Population par année', ['Année', 'Habitants'], points.map((p) => [String(p.x), fmtEntier(p.y)])));
  };
}
