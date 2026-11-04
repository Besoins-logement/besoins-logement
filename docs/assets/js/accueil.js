// Page d'accueil : chiffres de la base (meta.json, catalogue des sources) et besoin en logement de la France (besoins.parquet).
import { chargerSources } from './data.js';
import { requete } from './db.js';
import { el, vider, fmtEntier, fmtNombre, messageErreur } from './util.js';

let lance = false;
const $ = (id) => document.getElementById(id);

export function init() {}

export function show() {
  if (lance) return;
  lance = true;
  compterSources();
  // Le moteur de requête (quelques Mo, ensuite gardé en cache par le navigateur) n'est chargé que lorsque le bloc
  // « besoin en logement » approche de l'écran : tout de suite sur un grand écran, au défilement sur un téléphone.
  const bloc = $('acc-besoin');
  if (!('IntersectionObserver' in window)) { setTimeout(besoinFrance, 50); return; }
  const obs = new IntersectionObserver((entrees) => {
    if (entrees.some((e) => e.isIntersecting)) { obs.disconnect(); besoinFrance(); }
  }, { rootMargin: '300px 0px' });
  obs.observe(bloc);
}

async function compterSources() {
  try {
    const { liste } = await chargerSources();
    const integrees = liste.filter((s) => s.integration === 'Intégrée').length;
    $('acc-sources').textContent = fmtEntier(integrees);
    $('acc-sources-libelle').textContent = `sources intégrées, sur ${fmtEntier(liste.length)} repérées dans le catalogue`;
  } catch (e) {
    $('acc-sources').textContent = 'nd';
    $('acc-sources-libelle').textContent = 'sources : catalogue indisponible';
  }
}

async function besoinFrance() {
  const bloc = $('acc-besoin');
  try {
    const { lignes } = await requete(`
      SELECT
        max(CASE WHEN niveau = 'France' THEN bes_besoin_construction_3040 END) AS besoin,
        max(CASE WHEN niveau = 'France' THEN bes_construction_actuelle END) AS construction,
        max(CASE WHEN niveau = 'France' THEN bes_couverture_3040 END) AS couverture,
        max(CASE WHEN niveau = 'France' THEN bes_classe_3040 END) AS classe,
        max(CASE WHEN niveau = 'France' THEN bes_conclusion_3040 END) AS conclusion,
        count(*) FILTER (WHERE niveau = 'Département' AND bes_classe_3040 = 3) AS dep_non_couverts,
        count(*) FILTER (WHERE niveau = 'Département' AND bes_classe_3040 IS NOT NULL) AS dep_total
      FROM read_parquet('besoins.parquet')
      WHERE niveau IN ('France', 'Département')`, ['besoins.parquet']);
    const [besoin, construction, couverture, classe, conclusion, depNon, depTotal] = lignes[0] || [];
    if (besoin == null) throw new Error('La ligne France est absente du fichier besoins.parquet.');
    const valeur = vider($('acc-besoin-valeur'));
    valeur.className = '';
    valeur.append(fmtEntier(besoin));
    $('acc-construction').textContent = fmtEntier(construction);
    $('acc-couverture').textContent = couverture == null ? 'nd' : `${fmtNombre(couverture * 100, 0)} %`;
    $('acc-departements').textContent = depTotal ? `${fmtEntier(depNon)} sur ${fmtEntier(depTotal)}` : 'nd';
    const c = $('acc-conclusion');
    vider(c).className = `besoin-conclusion conclusion conclusion-${classe || 0}`;
    c.append(el('span', {}, `Conclusion pour 2030-2040 : ${conclusion || 'non disponible'}.`,
      el('small', {}, classe === 3
        ? 'Si la construction reste au niveau actuel, elle ne suffira pas à couvrir le besoin, même en remettant sur le marché des logements vacants.'
        : classe === 2 ? 'La construction actuelle couvre le besoin à condition de remettre sur le marché des logements vacants.'
          : 'La construction actuelle couvre le besoin si elle se maintient.')));
    c.hidden = false;
    bloc.dataset.besoin = String(besoin);
  } catch (e) {
    const valeur = vider($('acc-besoin-valeur'));
    valeur.className = '';
    valeur.append(el('span', { class: 'note' }, 'Données indisponibles pour le moment.'));
    for (const id of ['acc-construction', 'acc-couverture', 'acc-departements']) $(id).textContent = 'nd';
    const c = $('acc-conclusion');
    vider(c).className = 'besoin-conclusion alerte';
    c.append(`Les chiffres du besoin n'ont pas pu être lus. ${messageErreur(e)}`, ' ', el('button', {
      type: 'button',
      class: 'btn btn-petit',
      onclick: () => {
        c.hidden = true;
        const v = vider($('acc-besoin-valeur'));
        v.className = 'chargement';
        v.append('Chargement des données...');
        besoinFrance();
      },
    }, 'Réessayer'));
    c.hidden = false;
  } finally {
    bloc.removeAttribute('aria-busy');
  }
}
