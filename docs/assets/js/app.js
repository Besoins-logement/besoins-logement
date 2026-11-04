// Point d'entrée : menu, navigation par onglets (adresse après le #), informations générales (date de mise à jour).
import { chargerMeta } from './data.js';
import { el, vider, fmtDate, fmtEntier, alerte, messageErreur } from './util.js';

const TITRE_SITE = 'Besoins en logement - base de données';
const PAGES = {
  accueil: { titre: 'Accueil', module: () => import('./accueil.js') },
  explorer: { titre: 'Explorer la base', module: () => import('./explorer.js') },
  territoire: { titre: 'Fiche territoire', module: () => import('./territoire.js') },
  dictionnaire: { titre: 'Dictionnaire', module: () => import('./dictionnaire.js') },
  sources: { titre: 'Sources', module: () => import('./sources.js') },
  telechargements: { titre: 'Téléchargements', module: () => import('./telechargements.js') },
  methode: { titre: 'Méthode', module: () => import('./methode.js') },
};
const initialisees = new Map(); // route -> promesse d'init
let routeCourante = null;

function lireAdresse() {
  const h = location.hash.replace(/^#/, '');
  const i = h.indexOf('?');
  const route = (i < 0 ? h : h.slice(0, i)) || 'accueil';
  return { route, params: new URLSearchParams(i < 0 ? '' : h.slice(i + 1)) };
}

async function naviguer({ initial = false } = {}) {
  let { route, params } = lireAdresse();
  if (route === 'contenu') { document.getElementById('contenu').focus(); route = routeCourante || 'accueil'; }
  if (!PAGES[route]) route = 'accueil';
  const changement = route !== routeCourante;
  routeCourante = route;

  for (const s of document.querySelectorAll('.page')) s.hidden = s.dataset.page !== route;
  for (const a of document.querySelectorAll('.menu a[data-route]')) {
    if (a.dataset.route === route) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  }
  document.title = route === 'accueil' ? TITRE_SITE : `${PAGES[route].titre} - ${TITRE_SITE}`;
  fermerMenu();
  const section = document.getElementById('page-' + route);
  if (changement && !initial) {
    try { window.scrollTo({ top: 0, behavior: 'instant' }); } catch (_) { window.scrollTo(0, 0); }
    const h1 = section.querySelector('h1');
    if (h1) h1.focus({ preventScroll: true });
  }

  try {
    const mod = await PAGES[route].module();
    if (!initialisees.has(route)) {
      const p = Promise.resolve(mod.init ? mod.init(section) : null);
      initialisees.set(route, p);
      p.catch(() => initialisees.delete(route));
    }
    await initialisees.get(route);
    if (routeCourante === route && mod.show) await mod.show(params);
  } catch (e) {
    console.warn(e);
    const zone = section.querySelector('.erreur-page') || section.insertBefore(el('div', { class: 'erreur-page' }), section.children[1] || null);
    vider(zone).append(alerte("Cette page n'a pas pu se charger. " + messageErreur(e), { reessayer: () => { vider(zone); naviguer(); } }));
  }
}

function fermerMenu() {
  const b = document.getElementById('menu-bouton');
  const m = document.getElementById('menu');
  if (b && m) { b.setAttribute('aria-expanded', 'false'); m.classList.remove('ouvert'); }
}

function initialiserMenu() {
  const b = document.getElementById('menu-bouton');
  const m = document.getElementById('menu');
  b.addEventListener('click', () => {
    const ouvert = b.getAttribute('aria-expanded') !== 'true';
    b.setAttribute('aria-expanded', String(ouvert));
    m.classList.toggle('ouvert', ouvert);
    if (ouvert) { const a = m.querySelector('a'); if (a) a.focus(); }
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && m.classList.contains('ouvert')) { fermerMenu(); b.focus(); }
  });
  // Lien d'évitement : aller au contenu sans changer d'onglet
  const evitement = document.querySelector('.lien-evitement');
  evitement.addEventListener('click', (ev) => {
    ev.preventDefault();
    const s = document.getElementById('page-' + (routeCourante || 'accueil'));
    const h1 = s && s.querySelector('h1');
    (h1 || document.getElementById('contenu')).focus();
  });
}

async function informationsGenerales() {
  try {
    const meta = await chargerMeta();
    const valeurs = {
      date: fmtDate(meta.mise_a_jour),
      indicateurs: fmtEntier(meta.indicateurs),
      themes: fmtEntier(Object.keys(meta.themes || {}).length),
      territoires: fmtEntier(meta.territoires),
    };
    const m = /\(([\d\s  ]+) communes\)/.exec(meta.geographie || '');
    if (m) valeurs.communes = fmtEntier(Number(m[1].replace(/\D/g, '')));
    for (const n of document.querySelectorAll('[data-meta]')) {
      const v = valeurs[n.dataset.meta];
      if (v) n.textContent = v;
    }
  } catch (e) {
    for (const n of document.querySelectorAll('[data-meta="date"]')) n.textContent = 'date indisponible';
    console.warn(e);
  }
}

function lienDepot() {
  // Sur GitHub Pages (https://<compte>.github.io/<depot>/), lien vers le dépôt public.
  const m = /^([a-z0-9-]+)\.github\.io$/i.exec(location.hostname);
  const depot = location.pathname.split('/').filter(Boolean)[0];
  if (!m || !depot) return;
  const p = document.getElementById('pied-depot');
  vider(p).append('Code, historique des données et robot de mise à jour : ', el('a', { href: `https://github.com/${m[1]}/${depot}`, rel: 'noopener' }, `dépôt ${m[1]}/${depot} sur GitHub`), '.');
  p.hidden = false;
}

initialiserMenu();
lienDepot();
informationsGenerales();
window.addEventListener('hashchange', () => naviguer());
naviguer({ initial: true });
