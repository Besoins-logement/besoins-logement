// Page « Explorer la base » : thème, niveau, filtres géographiques, indicateurs, conditions, tableau trié et paginé, exports.
import { chargerMeta, chargerDictionnaire, chargerTerritoires } from './data.js';
import { requete } from './db.js';
import { Tableau } from './table.js';
import { exporterExcel, exporterCSV } from './export.js';
import {
  el, vider, NIVEAUX, niveauDepuisCle, niveauDepuisLibelle, fmtEntier, fmtNombre, fmtDate, normaliser, contientTous,
  sqlTexte, sqlIdent, lireNombre, debounce, messageErreur, slug, chargement, blocDefinition,
} from './util.js';

const MAX_IND = 100;
const THEME_DEFAUT = 'besoins';
const NIVEAU_DEFAUT = 'departement';
const DEFAUTS = {
  territoire: ['abc_zone_2026', 'zt_zone_tendue_2026', 'qpv_nb_2024', 'dens_urbain_dense_2025', 'aav_pole_2020', 'anct_pvd'],
  population: ['pop_2023', 'pop_2012', 'pop_age_0_19_2023', 'pop_age_65p_2023', 'pop_age_80p_2023', 'migr_ante_autre_com_2023'],
  menages: ['menc_2023', 'menc_2012', 'menc_taille_moy_2023', 'menc_1p_2023', 'menc_monop_2023', 'mtph_couple_2023'],
  profils: ['prof_jeune_seul_2023', 'prof_couple_sans_enf_2023', 'prof_famille_enf_2023', 'prof_monop_2023', 'prof_senior_6074_2023', 'prof_grand_age_2023'],
  logement: ['log_2023', 'log_rp_2023', 'log_rs_2023', 'log_vac_2023', 'log_part_vac_2023', 'log_part_proprio_2023'],
  construction: ['sit_commences_2022', 'sit_commences_2023', 'sit_commences_2024', 'sit_autorises_3ans', 'sit_construction_actuelle', 'sit_part_maisons_autorises'],
  besoins: ['bes_besoin_avant_vacants_3040', 'bes_besoin_construction_3040', 'bes_construction_actuelle', 'bes_manque_3040', 'bes_couverture_3040', 'bes_conclusion_3040'],
  marche: ['dvf_prix_m2_maisons_2025', 'dvf_prix_m2_appartements_2025', 'dvf_ventes_maisons_2025', 'dvf_ventes_appartements_2025', 'loyers_m2_maisons_2025', 'loyers_m2_appartements_2025'],
  revenus: ['filo_med_2023', 'filo_tx_pauvrete_2023', 'ircom_rfr_moyen_2024', 'ircom_part_foyers_imposes_2024', 'caf_foyers_al_2024', 'caf_foyers_rsa_2024'],
  emploi: ['urssaf_salaries_2025', 'urssaf_salaries_2015', 'emp_tx_chom_2023', 'emp_tx_emploi_2023', 'ft_defm_abc_2024t4', 'nav_part_autre_com_2023'],
  economie: ['flores_etab_2024', 'flores_sal_2024', 'flores_sal_construction_2024', 'crea_ent_2025', 'crea_ent_construction_2025', 'sal_net_eqtp_2024'],
  equipements: ['bpe_2025', 'bpe_d265_2025', 'bpe_d307_2025', 'bpe_c108_2025', 'apl_mg_2024', 'gares_nb_2026'],
  risques_energie: ['catnat_total_1982_2026', 'catnat_inond_1982_2026', 'catnat_secheresse_1982_2026', 'dpe_part_fg_2021_2026', 'zclim_zone', 'tdc_liste_2026'],
};
const OPERATEURS = {
  num: [['gt', 'est supérieur à (>)', '>'], ['ge', 'est supérieur ou égal à (≥)', '>='], ['lt', 'est inférieur à (<)', '<'], ['le', 'est inférieur ou égal à (≤)', '<='], ['eq', 'est égal à (=)', '='], ['ne', 'est différent de (≠)', '<>'], ['nn', 'est renseigné', null]],
  texte: [['eq', 'est égal à', '='], ['ne', 'est différent de', '<>'], ['ct', 'contient', null], ['nn', 'est renseigné', null]],
};
const SYMBOLES = { gt: '>', ge: '≥', lt: '<', le: '≤', eq: '=', ne: '≠', ct: 'contient', nn: 'est renseigné' };

const COLS_FIXES = [
  { cle: 'niveau', entete: 'Niveau', technique: 'niveau', type: 'texte', definition: "Niveau géographique de la ligne : France, Région, Département, Zone d'emploi, EPCI, Territoire d'industrie ou Commune.", source: 'Code officiel géographique au 1er janvier 2026 et zonages officiels', producteur: 'Insee, ANCT' },
  { cle: 'code', entete: 'Code', technique: 'code', type: 'texte', definition: "Code officiel du territoire : FR pour la France, code de région, de département, de zone d'emploi 2020, numéro SIREN de l'EPCI, identifiant du territoire d'industrie ou code commune Insee (COG 2026).", source: 'Code officiel géographique au 1er janvier 2026', producteur: 'Insee' },
  { cle: 'nom', entete: 'Nom', technique: 'nom', type: 'texte', definition: 'Nom du territoire.', source: 'Code officiel géographique au 1er janvier 2026', producteur: 'Insee' },
];

const etat = { theme: '', niveau: '', reg: '', dep: '', epci: '', nom: '', ind: [], conds: [], appart: false };
let meta = null; let dico = null; let terr = null;
let tableau = null;
let resultat = null;
let jeton = 0;
let dernierParams = null;
let rechercheInd = '';
let visibles = [];
let epciParDep = new Map(); let epciParReg = new Map();
let nbCommunes = 34875;
let pret = false;

const $ = (id) => document.getElementById(id);
const entree = (col, theme = etat.theme) => (dico ? dico.entree(theme, col) : null);
const estTexte = (d) => d && d.agregation === 'texte';

/* ------------------------------------------------------------------ init */
export async function init() {
  tableau = new Tableau($('ex-tableau'), { colonnes: [], legende: 'Résultats de la sélection', sansRetour: true, vide: 'Aucun territoire ne correspond à ces critères. Élargissez les filtres ou retirez une condition.' });
  lierEvenements();
  await preparer();
}

async function preparer() {
  basculerFormulaire(false);
  statut(chargement('Chargement du moteur de requête, du dictionnaire et des territoires (quelques secondes la première fois)...'));
  try {
    meta = await chargerMeta();
    dico = await chargerDictionnaire();
    terr = await chargerTerritoires();
  } catch (e) {
    statut('');
    montrerAlerte("La page n'a pas pu se préparer. " + messageErreur(e), async () => {
      if (await preparer()) show(new URLSearchParams(location.hash.split('?')[1] || ''));
    });
    return false;
  }
  cacherAlerte();
  statut('');
  const communes = terr.parNiveau.get('Commune') || [];
  nbCommunes = communes.length || nbCommunes;
  epciParDep = new Map(); epciParReg = new Map();
  for (const c of communes) {
    if (!c.epci) continue;
    if (!epciParDep.has(c.dep)) epciParDep.set(c.dep, new Set());
    epciParDep.get(c.dep).add(c.epci);
    if (!epciParReg.has(c.reg)) epciParReg.set(c.reg, new Set());
    epciParReg.get(c.reg).add(c.epci);
  }
  const selTheme = vider($('ex-theme'));
  for (const [cle, t] of Object.entries(meta.themes)) {
    selTheme.append(el('option', { value: cle }, `${t.libelle} (${fmtEntier(t.indicateurs)} indicateurs)`));
  }
  const selNiveau = vider($('ex-niveau'));
  for (const lib of meta.niveaux || NIVEAUX.map((n) => n.libelle)) {
    const n = niveauDepuisLibelle(lib);
    const nb = (terr.parNiveau.get(lib) || []).length;
    selNiveau.append(el('option', { value: n.cle }, `${n.pluriel} (${fmtEntier(nb)})`));
  }
  const selReg = $('ex-reg');
  vider(selReg).append(el('option', { value: '' }, 'Toutes les régions'));
  for (const r of [...(terr.parNiveau.get('Région') || [])].sort((a, b) => a.nom.localeCompare(b.nom, 'fr'))) selReg.append(el('option', { value: r.code }, r.nom));
  pret = true;
  basculerFormulaire(true);
  return true;
}

function basculerFormulaire(actif) {
  for (const n of $('ex-form').querySelectorAll('select, input, button')) n.disabled = !actif;
  if (actif) rendreGeo();
}

/* ------------------------------------------------------------------ show */
export async function show(params) {
  if (!pret) return;
  const p = params && params.has('theme') ? params : null;
  if (p) {
    if (p.toString() === dernierParams) return;
    appliquerParams(p);
    await lancer();
  } else if (!resultat && !etat.theme) {
    appliquerDefauts();
    await lancer();
  }
}

function appliquerDefauts(theme = THEME_DEFAUT) {
  etat.theme = meta.themes[theme] ? theme : Object.keys(meta.themes)[0];
  etat.niveau = NIVEAU_DEFAUT;
  etat.reg = ''; etat.dep = ''; etat.epci = ''; etat.nom = ''; etat.appart = false;
  etat.ind = defauts(etat.theme);
  etat.conds = [];
  rechercheInd = '';
  rendreTout();
}

function defauts(theme) {
  const entrees = dico.parTheme.get(theme) || [];
  const existants = new Set(entrees.map((d) => d.colonne));
  let cols = (DEFAUTS[theme] || []).filter((c) => existants.has(c));
  if (cols.length < 3) cols = [...new Set([...cols, ...entrees.slice(0, 6).map((d) => d.colonne)])];
  return ordonner(cols, theme);
}
function ordonner(cols, theme = etat.theme) {
  const s = new Set(cols);
  return (dico.parTheme.get(theme) || []).filter((d) => s.has(d.colonne)).map((d) => d.colonne);
}

function appliquerParams(p) {
  const theme = p.get('theme');
  etat.theme = meta.themes[theme] ? theme : THEME_DEFAUT;
  const niv = niveauDepuisCle(p.get('niveau') || '');
  etat.niveau = niv ? niv.cle : NIVEAU_DEFAUT;
  etat.reg = p.get('reg') || ''; etat.dep = p.get('dep') || ''; etat.epci = p.get('epci') || '';
  etat.nom = p.get('nom') || '';
  etat.appart = p.get('app') === '1';
  const demandes = (p.get('ind') || '').split(',').map((s) => s.trim()).filter(Boolean);
  etat.ind = demandes.length ? ordonner(demandes).slice(0, MAX_IND) : defauts(etat.theme);
  if (!etat.ind.length) etat.ind = defauts(etat.theme);
  etat.conds = p.getAll('c').map((s) => {
    const [col, op, ...reste] = s.split(':');
    return { col, op, val: reste.join(':') };
  }).filter((c) => etat.ind.includes(c.col) && (OPERATEURS.num.some((o) => o[0] === c.op) || OPERATEURS.texte.some((o) => o[0] === c.op)));
  rechercheInd = '';
  rendreTout();
}

function versParams(e) {
  const p = new URLSearchParams();
  p.set('theme', e.theme);
  p.set('niveau', e.niveau);
  if (e.reg) p.set('reg', e.reg);
  if (e.dep) p.set('dep', e.dep);
  if (e.epci) p.set('epci', e.epci);
  if (e.nom) p.set('nom', e.nom);
  p.set('ind', e.ind.join(','));
  for (const c of e.conds) p.append('c', `${c.col}:${c.op}:${c.val}`);
  if (e.appart) p.set('app', '1');
  return p;
}

/* ------------------------------------------------------------------ rendu du formulaire */
function rendreTout() {
  $('ex-theme').value = etat.theme;
  $('ex-niveau').value = etat.niveau;
  $('ex-nom').value = etat.nom;
  $('ex-appart').checked = etat.appart;
  $('ex-ind-recherche').value = rechercheInd;
  rendreGeo();
  rendreIndicateurs();
  rendreChoisis();
  rendreConditions();
}

function libNiveau(cle = etat.niveau) { return (niveauDepuisCle(cle) || NIVEAUX[2]).libelle; }

function rendreGeo() {
  if (!terr) return;
  const niv = libNiveau();
  const france = niv === 'France';
  const groupe = ["Zone d'emploi", 'EPCI', "Territoire d'industrie"].includes(niv);
  $('ex-reg-champ').hidden = france;
  $('ex-dep-champ').hidden = france || niv === 'Région';
  $('ex-epci-champ').hidden = niv !== 'Commune';
  $('ex-nom-champ').hidden = france;
  $('ex-appart-champ').hidden = france || niv === 'Région';
  if (france) { etat.reg = ''; etat.dep = ''; etat.nom = ''; $('ex-nom').value = ''; }
  if (niv === 'Région') etat.dep = '';
  if (niv !== 'Commune') etat.epci = '';
  $('ex-geo-aide').textContent = france
    ? 'Le niveau France compte une seule ligne : pas de filtre géographique.'
    : groupe ? 'Pour ce niveau, la région et le département retenus sont ceux où se trouve la plus grande partie du territoire.'
      : niv === 'Commune' ? 'Pour les communes, vous pouvez aussi choisir une intercommunalité.' : '';

  // Régions
  $('ex-reg').value = etat.reg;
  if ($('ex-reg').value !== etat.reg) { etat.reg = ''; $('ex-reg').value = ''; }
  // Départements (de la région choisie)
  const deps = [...(terr.parNiveau.get('Département') || [])].filter((d) => !etat.reg || d.reg === etat.reg).sort((a, b) => a.code.localeCompare(b.code, 'fr', { numeric: true }));
  const selDep = vider($('ex-dep'));
  selDep.append(el('option', { value: '' }, etat.reg ? 'Tous les départements de la région' : 'Tous les départements'));
  for (const d of deps) selDep.append(el('option', { value: d.code }, `${d.nom} (${d.code})`));
  if (!deps.some((d) => d.code === etat.dep)) etat.dep = '';
  selDep.value = etat.dep;
  // Intercommunalités (du département ou de la région choisis)
  const selEpci = vider($('ex-epci'));
  selEpci.append(el('option', { value: '' }, 'Toutes les intercommunalités'));
  if (niv === 'Commune') {
    const codes = etat.dep ? epciParDep.get(etat.dep) : etat.reg ? epciParReg.get(etat.reg) : null;
    const liste = [...(terr.parNiveau.get('EPCI') || [])].filter((e) => !codes || codes.has(e.code)).sort((a, b) => a.nom.localeCompare(b.nom, 'fr'));
    for (const e of liste) selEpci.append(el('option', { value: e.code }, e.nom));
    if (!liste.some((e) => e.code === etat.epci)) etat.epci = '';
  }
  selEpci.value = etat.epci;
}

function rendreIndicateurs() {
  const liste = vider($('ex-ind-liste'));
  const entrees = dico ? dico.parTheme.get(etat.theme) || [] : [];
  const mots = normaliser(rechercheInd).split(' ').filter(Boolean);
  visibles = mots.length ? entrees.filter((d) => contientTous(d.texteRecherche, mots)) : entrees;
  if (!visibles.length) liste.append(el('li', { class: 'ind-vide' }, 'Aucun indicateur ne correspond à cette recherche.'));
  const frag = document.createDocumentFragment();
  const choisis = new Set(etat.ind);
  for (const d of visibles) frag.append(ligneIndicateur(d, choisis.has(d.colonne)));
  liste.append(frag);
  majCompte();
}

function ligneIndicateur(d, choisi) {
  const id = 'ind-' + d.colonne;
  const idDef = 'def-' + d.colonne;
  const cb = el('input', { type: 'checkbox', id, value: d.colonne, checked: choisi });
  const details = [d.unite, d.annee, d.colonne].filter(Boolean).join(' · ');
  const label = el('label', { for: id }, el('span', { class: 'ind-libelle' }, d.libelle), el('span', { class: 'ind-meta' }, details));
  const info = el('button', { type: 'button', class: 'bouton-info', 'aria-expanded': 'false', 'aria-controls': idDef, 'aria-label': `Définition et source : ${d.libelle}`, title: 'Définition et source' }, 'i');
  const li = el('li', { class: choisi ? 'choisi' : null, 'data-col': d.colonne }, el('div', { class: 'ind-ligne' }, cb, label, info));
  cb.addEventListener('change', () => basculerIndicateur(d.colonne, cb.checked, cb));
  info.addEventListener('click', () => {
    let bloc = document.getElementById(idDef);
    const ouvert = info.getAttribute('aria-expanded') === 'true';
    if (!bloc) { bloc = blocDefinition(d, idDef, nbCommunes); li.append(bloc); }
    bloc.hidden = ouvert;
    info.setAttribute('aria-expanded', String(!ouvert));
  });
  return li;
}

function majCompte() {
  const total = (dico && dico.parTheme.get(etat.theme) || []).length;
  const n = etat.ind.length;
  const choisis = `${n} indicateur${n > 1 ? 's' : ''} choisi${n > 1 ? 's' : ''} (${MAX_IND} au plus)`;
  $('ex-ind-compte').textContent = visibles.length === total
    ? `${fmtEntier(total)} indicateurs dans ce thème · ${choisis}`
    : `${fmtEntier(visibles.length)} indicateur${visibles.length > 1 ? 's' : ''} trouvé${visibles.length > 1 ? 's' : ''} sur ${fmtEntier(total)} · ${choisis}`;
}

function basculerIndicateur(col, actif, cb) {
  const s = new Set(etat.ind);
  if (actif) {
    if (s.size >= MAX_IND && !s.has(col)) {
      if (cb) cb.checked = false;
      montrerAlerte(`Vous pouvez choisir ${MAX_IND} indicateurs au plus. Pour un thème complet, utilisez la page Téléchargements.`);
      return;
    }
    s.add(col);
  } else s.delete(col);
  etat.ind = ordonner([...s]);
  const li = $('ex-ind-liste').querySelector(`li[data-col="${CSS.escape(col)}"]`);
  if (li) {
    li.classList.toggle('choisi', actif);
    const c = li.querySelector('input'); if (c) c.checked = actif;
  }
  rendreChoisis();
  rendreConditions();
  majCompte();
}

function rendreChoisis() {
  const zone = vider($('ex-choisis'));
  for (const col of etat.ind) {
    const d = entree(col);
    if (!d) continue;
    zone.append(el('span', { class: 'puce-choisie' },
      el('span', { title: `${d.libelle} (${d.colonne})` }, d.libelle),
      el('button', { type: 'button', 'aria-label': `Retirer l'indicateur : ${d.libelle}`, title: 'Retirer', onclick: () => basculerIndicateur(col, false) }, '×')));
  }
}

function rendreConditions() {
  const zone = vider($('ex-conds'));
  const choisis = etat.ind.map((c) => entree(c)).filter(Boolean);
  etat.conds = etat.conds.filter((c) => etat.ind.includes(c.col));
  etat.conds.forEach((c, i) => zone.append(ligneCondition(c, i, choisis)));
  $('ex-cond-ajout').disabled = !pret || !choisis.length;
}

function ligneCondition(c, i, choisis) {
  const d = entree(c.col);
  const type = estTexte(d) ? 'texte' : 'num';
  const ops = OPERATEURS[type];
  if (!ops.some((o) => o[0] === c.op)) c.op = ops[0][0];
  const n = i + 1;
  const selCol = el('select', { id: `cond-col-${i}`, 'aria-label': `Condition ${n} : indicateur` }, ...choisis.map((x) => el('option', { value: x.colonne, selected: x.colonne === c.col }, x.libelle)));
  const selOp = el('select', { id: `cond-op-${i}`, 'aria-label': `Condition ${n} : comparaison` }, ...ops.map((o) => el('option', { value: o[0], selected: o[0] === c.op }, o[1])));
  const val = el('input', { type: 'text', id: `cond-val-${i}`, value: c.val, inputmode: type === 'num' ? 'decimal' : 'text', autocomplete: 'off', 'aria-label': `Condition ${n} : valeur`, placeholder: type === 'num' ? 'Nombre' : 'Texte', disabled: c.op === 'nn' });
  const retirer = el('button', { type: 'button', class: 'btn btn-petit', 'aria-label': `Retirer la condition ${n}` }, 'Retirer');
  let aide = d && d.unite ? `Unité : ${d.unite}` : '';
  if (d && d.unite === 'part (1 = 100 %)') aide += ' ; tapez 0,8 pour 80 %';
  else if (d && d.unite === '%') aide += ' ; tapez 10 pour 10 %';
  const unite = el('span', { class: 'unite-cond' }, aide);
  selCol.addEventListener('change', () => {
    c.col = selCol.value;
    const nouveau = estTexte(entree(c.col)) ? 'texte' : 'num';
    if (nouveau !== type) { c.op = OPERATEURS[nouveau][0][0]; c.val = ''; }
    rendreConditions();
    const s = document.getElementById(`cond-col-${i}`); if (s) s.focus();
  });
  selOp.addEventListener('change', () => { c.op = selOp.value; val.disabled = c.op === 'nn'; });
  val.addEventListener('input', () => { c.val = val.value; });
  retirer.addEventListener('click', () => {
    etat.conds.splice(i, 1);
    rendreConditions();
    $('ex-cond-ajout').focus();
  });
  return el('div', { class: 'cond' }, selCol, selOp, val, retirer, unite);
}

/* ------------------------------------------------------------------ événements */
function lierEvenements() {
  $('ex-theme').addEventListener('change', (ev) => {
    etat.theme = ev.target.value;
    etat.ind = defauts(etat.theme);
    etat.conds = [];
    rechercheInd = '';
    $('ex-ind-recherche').value = '';
    rendreIndicateurs(); rendreChoisis(); rendreConditions();
  });
  $('ex-niveau').addEventListener('change', (ev) => { etat.niveau = ev.target.value; rendreGeo(); });
  $('ex-reg').addEventListener('change', (ev) => { etat.reg = ev.target.value; rendreGeo(); });
  $('ex-dep').addEventListener('change', (ev) => { etat.dep = ev.target.value; rendreGeo(); });
  $('ex-epci').addEventListener('change', (ev) => { etat.epci = ev.target.value; });
  $('ex-nom').addEventListener('input', (ev) => { etat.nom = ev.target.value; });
  $('ex-appart').addEventListener('change', (ev) => { etat.appart = ev.target.checked; });
  $('ex-ind-recherche').addEventListener('input', debounce((ev) => { rechercheInd = ev.target.value; rendreIndicateurs(); }, 120));
  $('ex-ind-tous').addEventListener('click', () => {
    const s = new Set(etat.ind);
    let refuses = 0;
    for (const d of visibles) { if (s.size >= MAX_IND && !s.has(d.colonne)) { refuses++; continue; } s.add(d.colonne); }
    etat.ind = ordonner([...s]);
    rendreIndicateurs(); rendreChoisis(); rendreConditions();
    if (refuses) montrerAlerte(`${refuses} indicateurs n'ont pas été ajoutés : ${MAX_IND} au plus. Pour un thème complet, utilisez la page Téléchargements.`);
  });
  $('ex-ind-aucun').addEventListener('click', () => { etat.ind = []; etat.conds = []; rendreIndicateurs(); rendreChoisis(); rendreConditions(); });
  $('ex-ind-defaut').addEventListener('click', () => { etat.ind = defauts(etat.theme); rendreIndicateurs(); rendreChoisis(); rendreConditions(); });
  $('ex-cond-ajout').addEventListener('click', () => {
    const choisis = etat.ind.map((c) => entree(c)).filter(Boolean);
    if (!choisis.length) return;
    const d = choisis.find((x) => !estTexte(x)) || choisis[0];
    etat.conds.push({ col: d.colonne, op: estTexte(d) ? 'eq' : 'gt', val: '' });
    rendreConditions();
    const s = document.getElementById(`cond-col-${etat.conds.length - 1}`); if (s) s.focus();
  });
  $('ex-form').addEventListener('submit', (ev) => { ev.preventDefault(); lancer({ defiler: true }); });
  $('ex-reinit').addEventListener('click', () => { appliquerDefauts(); lancer(); });
  $('ex-export-xlsx').addEventListener('click', () => exporter('xlsx'));
  $('ex-export-csv').addEventListener('click', () => exporter('csv'));
  $('ex-lien').addEventListener('click', copierLien);
}

/* ------------------------------------------------------------------ requête */
function valider(e) {
  const erreurs = [];
  if (!e.ind.length) erreurs.push('Choisissez au moins un indicateur (étape 3).');
  e.conds.forEach((c, i) => {
    const d = entree(c.col, e.theme);
    if (!d || c.op === 'nn') return;
    if (estTexte(d)) { if (!String(c.val).trim()) erreurs.push(`Condition ${i + 1} : indiquez un texte.`); }
    else if (lireNombre(c.val) == null) erreurs.push(`Condition ${i + 1} : « ${c.val || 'vide'} » n'est pas un nombre.`);
  });
  return erreurs;
}

function colonnesAppartenance(niv, avec) {
  if (!avec || niv === 'France' || niv === 'Région') return [];
  const principal = ["Zone d'emploi", 'EPCI', "Territoire d'industrie"].includes(niv);
  const cols = [{ cle: 'libreg', entete: principal ? 'Région principale' : 'Région', definition: principal ? 'Région où se trouve la plus grande partie du territoire.' : 'Région du territoire.' }];
  if (niv !== 'Département') cols.push({ cle: 'libdep', entete: principal ? 'Département principal' : 'Département', definition: principal ? 'Département où se trouve la plus grande partie du territoire.' : 'Département de la commune.' });
  if (niv === 'Commune') cols.push({ cle: 'libepci', entete: 'Intercommunalité (EPCI)', definition: "Établissement public de coopération intercommunale de la commune au 1er janvier 2026." });
  return cols.map((c) => ({ ...c, technique: c.cle, type: 'texte', source: 'Code officiel géographique et intercommunalités au 1er janvier 2026', producteur: 'Insee, DGCL' }));
}

function expressionColonne(d) {
  const id = 't.' + sqlIdent(d.colonne);
  return estTexte(d) ? id : `CAST(${id} AS DOUBLE)`;
}

function construireSQL(e, entrees, appart) {
  const niv = libNiveau(e.niveau);
  const fichier = meta.themes[e.theme].fichier;
  const sel = ['t.niveau AS niveau', 't.code AS code', 'g.nom AS nom'];
  for (const a of appart) sel.push(`g.${a.cle} AS ${sqlIdent(a.cle)}`);
  for (const d of entrees) sel.push(`${expressionColonne(d)} AS ${sqlIdent(d.colonne)}`);
  const where = [`t.niveau = ${sqlTexte(niv)}`];
  if (niv !== 'France') {
    if (e.reg) where.push(niv === 'Région' ? `t.code = ${sqlTexte(e.reg)}` : `g.reg = ${sqlTexte(e.reg)}`);
    if (e.dep && niv !== 'Région') where.push(niv === 'Département' ? `t.code = ${sqlTexte(e.dep)}` : `g.dep = ${sqlTexte(e.dep)}`);
    if (e.epci && niv === 'Commune') where.push(`g.epci = ${sqlTexte(e.epci)}`);
    const nom = normaliser(e.nom).replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
    if (nom) where.push(`contains(trim(regexp_replace(strip_accents(lower(g.nom)), '[^a-z0-9]+', ' ', 'g')), ${sqlTexte(nom)})`);
  }
  for (const c of e.conds) {
    const d = entree(c.col, e.theme);
    if (!d) continue;
    const x = expressionColonne(d);
    if (c.op === 'nn') { where.push(`${x} IS NOT NULL`); continue; }
    if (estTexte(d)) {
      const v = normaliser(c.val);
      const xn = `regexp_replace(strip_accents(lower(${x})), '[^a-z0-9]+', ' ', 'g')`;
      const vn = v.replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
      if (c.op === 'ct') where.push(`contains(${xn}, ${sqlTexte(vn)})`);
      else where.push(`trim(${xn}) ${c.op === 'ne' ? '<>' : '='} ${sqlTexte(vn)}`);
    } else {
      const op = OPERATEURS.num.find((o) => o[0] === c.op);
      const v = lireNombre(c.val);
      if (op && op[2] && v != null) where.push(`${x} ${op[2]} ${v}`);
    }
  }
  return `SELECT ${sel.join(', ')}\nFROM read_parquet(${sqlTexte(fichier)}) AS t\nJOIN terr AS g ON g.niveau = t.niveau AND g.code = t.code\nWHERE ${where.join('\n  AND ')}\nORDER BY t.code`;
}

function cloner(e) { return { ...e, ind: [...e.ind], conds: e.conds.map((c) => ({ ...c })) }; }

function descriptionFiltres(e) {
  const niv = libNiveau(e.niveau);
  const parts = [];
  if (e.reg && niv !== 'France') { const r = terr.trouver('Région', e.reg); parts.push(['Région', r ? r.nom : e.reg]); }
  if (e.dep && niv !== 'France' && niv !== 'Région') { const d = terr.trouver('Département', e.dep); parts.push(['Département', d ? `${d.nom} (${d.code})` : e.dep]); }
  if (e.epci && niv === 'Commune') { const x = terr.trouver('EPCI', e.epci); parts.push(['Intercommunalité (EPCI)', x ? x.nom : e.epci]); }
  if (e.nom && niv !== 'France') parts.push(['Nom contenant', e.nom]);
  return parts;
}
function descriptionConditions(e) {
  return e.conds.map((c) => {
    const d = entree(c.col, e.theme);
    const lib = d ? d.libelle : c.col;
    return c.op === 'nn' ? `${lib} est renseigné` : `${lib} ${SYMBOLES[c.op] || c.op} ${c.val}`;
  });
}

async function lancer({ defiler = false } = {}) {
  if (!pret) return;
  const e = cloner(etat);
  const erreurs = valider(e);
  if (erreurs.length) { montrerAlerte(erreurs.join(' ')); return; }
  cacherAlerte();
  const t = ++jeton;
  const debut = performance.now();
  statut(chargement('Lecture des données...'));
  $('ex-lancer').disabled = true;
  $('ex-tableau').setAttribute('aria-busy', 'true');
  try {
    const entrees = e.ind.map((c) => entree(c, e.theme)).filter(Boolean);
    const niv = libNiveau(e.niveau);
    const appart = colonnesAppartenance(niv, e.appart);
    const sql = construireSQL(e, entrees, appart);
    const res = await requete(sql, [meta.themes[e.theme].fichier]);
    if (t !== jeton) return;
    const colonnes = [
      ...COLS_FIXES,
      ...appart,
      ...entrees.map((d) => ({
        cle: d.colonne, entete: d.libelle, technique: d.colonne, type: estTexte(d) ? 'texte' : 'num', unite: d.unite, annee: d.annee,
        definition: d.definition, source: d.source, producteur: d.producteur, adresse: d.adresse, millesime: d.millesime, licence: d.licence, agregation: d.agregation,
      })),
    ];
    const colsTableau = colonnes.map((c, j) => ({
      titre: c.entete,
      sousTitre: c.unite === 'part (1 = 100 %)' ? '%' : (c.unite || null),
      info: c.technique,
      type: c.type,
      valeur: (l) => l[j],
      format: c.unite === 'part (1 = 100 %)' ? (v) => `${fmtNombre(v * 100, 1)} %` : null,
      // Le nom mène à la fiche du territoire
      rendu: c.cle === 'nom' ? (l) => el('a', { href: `#territoire?niveau=${niveauDepuisLibelle(l[0]).cle}&code=${encodeURIComponent(l[1])}`, title: 'Voir la fiche du territoire' }, l[j] || l[1]) : null,
    }));
    resultat = { etat: e, colonnes, lignes: res.lignes, sql, date: new Date() };
    tableau.definir(colsTableau, res.lignes);
    const n = res.lignes.length;
    const resume = $('ex-resume');
    vider(resume).append(
      el('strong', {}, fmtEntier(n)), ` territoire${n > 1 ? 's' : ''} · niveau ${niv}`,
      ` · ${entrees.length} indicateur${entrees.length > 1 ? 's' : ''} du thème « ${meta.themes[e.theme].libelle} »`);
    const filtres = [...descriptionFiltres(e).map(([k, v]) => `${k} : ${v}`), ...descriptionConditions(e)];
    if (filtres.length) resume.append(el('br'), el('span', { class: 'note' }, 'Filtres et conditions : ' + filtres.join(' ; ')));
    resume.dataset.lignes = String(n);
    resume.dataset.colonnes = String(colonnes.length);
    for (const id of ['ex-export-xlsx', 'ex-export-csv']) $(id).disabled = n === 0;
    $('ex-lien').disabled = false;
    const params = versParams(e).toString();
    dernierParams = params;
    if (location.hash.startsWith('#explorer')) history.replaceState(null, '', '#explorer?' + params);
    const duree = (performance.now() - debut) / 1000;
    statut(`${fmtEntier(n)} territoire${n > 1 ? 's' : ''} trouvé${n > 1 ? 's' : ''} en ${fmtNombre(duree, 1)} s.`);
    $('ex-export-statut').textContent = '';
    if (defiler) {
      const h = $('titre-resultats');
      h.scrollIntoView({ block: 'start' });
      h.focus({ preventScroll: true });
    }
  } catch (err) {
    if (t !== jeton) return;
    statut('');
    montrerAlerte('La requête a échoué. ' + messageErreur(err), () => lancer());
  } finally {
    if (t === jeton) {
      $('ex-lancer').disabled = false;
      $('ex-tableau').removeAttribute('aria-busy');
    }
  }
}

/* ------------------------------------------------------------------ exports */
async function exporter(format) {
  if (!resultat || !resultat.lignes.length) return;
  const { etat: e, colonnes } = resultat;
  const lignes = tableau.lignesOrdonnees();
  const niv = libNiveau(e.niveau);
  const jour = new Date().toISOString().slice(0, 10);
  const base = `besoins-logement_${e.theme}_${slug(niv)}_${jour}`;
  const boutons = ['ex-export-xlsx', 'ex-export-csv'].map($);
  boutons.forEach((b) => { b.disabled = true; });
  const zone = $('ex-export-statut');
  const cellules = lignes.length * colonnes.length;
  vider(zone).append(chargement(format === 'xlsx'
    ? (cellules > 1500000 ? `Préparation du fichier Excel (${fmtEntier(cellules)} cellules : cela peut prendre une minute)...` : 'Préparation du fichier Excel...')
    : 'Préparation du fichier CSV...'));
  try {
    if (format === 'xlsx') {
      const tri = tableau.tri ? `${colonnes[tableau.tri.index].entete} (${tableau.tri.sens > 0 ? 'croissant' : 'décroissant'})` : 'par code';
      const contexte = [
        ['Thème', meta.themes[e.theme].libelle],
        ['Niveau', niv],
        ...descriptionFiltres(e),
        ['Conditions', descriptionConditions(e).join(' ; ') || 'aucune'],
        ['Nombre de lignes', lignes.length],
        ['Ordre des lignes', tri],
        ['Adresse de la sélection', lienSelection(e)],
      ];
      await exporterExcel({ colonnes, lignes, contexte, dateBase: fmtDate(meta.mise_a_jour), nomFichier: base + '.xlsx' });
    } else {
      exporterCSV({ colonnes, lignes, nomFichier: base + '.csv' });
    }
    vider(zone).append(`Fichier ${format === 'xlsx' ? 'Excel' : 'CSV'} prêt : ${fmtEntier(lignes.length)} lignes, ${colonnes.length} colonnes.`);
  } catch (err) {
    vider(zone).append(el('span', { class: 'alerte' }, "L'export a échoué. " + messageErreur(err)));
  } finally {
    boutons.forEach((b) => { b.disabled = false; });
  }
}

function lienSelection(e = resultat && resultat.etat) {
  return location.href.split('#')[0] + '#explorer?' + versParams(e).toString();
}

async function copierLien() {
  if (!resultat) return;
  const lien = lienSelection();
  const zone = $('ex-export-statut');
  try {
    await navigator.clipboard.writeText(lien);
    zone.textContent = 'Lien copié : il rouvre cette sélection.';
  } catch (_) {
    vider(zone).append('Copiez ce lien : ', el('input', { type: 'text', value: lien, readonly: true, 'aria-label': 'Lien de la sélection', onfocus: (ev) => ev.target.select() }));
  }
}

/* ------------------------------------------------------------------ messages */
function statut(contenu) {
  const z = vider($('ex-statut'));
  if (contenu) z.append(contenu);
}
function montrerAlerte(texte, reessayer) {
  const a = vider($('ex-alerte'));
  a.append(el('p', { text: texte }));
  if (reessayer) a.append(el('button', { type: 'button', class: 'btn btn-petit', onclick: reessayer }, 'Réessayer'));
  a.hidden = false;
}
function cacherAlerte() { const a = $('ex-alerte'); a.hidden = true; vider(a); }
