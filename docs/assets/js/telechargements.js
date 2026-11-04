// Page « Téléchargements » : chaque thème en Parquet et en CSV compressé, fichiers complémentaires, tailles lues par requête HEAD.
import { chargerMeta } from './data.js';
import { el, vider, fmtEntier, fmtTaille, adresseDonnees, messageErreur, alerte } from './util.js';

const COULEURS = ['#97C33D', '#005CCE', '#61D2D1', '#FF3E65', '#FFC400', '#00ACFF'];
const AUTRES = [
  { nom: 'Territoires et appartenances', contenu: "Les 36 738 territoires des 7 niveaux, avec la région, le département, l'EPCI, la zone d'emploi et le territoire d'industrie de chaque commune.", fichiers: [['territoires.parquet', 'Parquet'], ['csv/territoires.csv.gz', 'CSV compressé']] },
  { nom: 'Dictionnaire des indicateurs', contenu: 'Une ligne par indicateur : thème, colonne, libellé, unité, définition, année, règle de calcul, source, adresse, millésime, licence.', fichiers: [['dictionnaire.csv', 'CSV'], ['dictionnaire.parquet', 'Parquet']] },
  { nom: 'Catalogue des sources', contenu: "Les sources repérées par le projet, intégrées ou non, avec leur état d'intégration et leurs limites.", fichiers: [['sources.csv', 'CSV']] },
  { nom: 'Description de la base', contenu: 'Date de mise à jour, thèmes, niveaux et totaux (meta.json) ; compte rendu de la dernière exécution du robot (derniere_execution.json).', fichiers: [['meta.json', 'meta.json'], ['derniere_execution.json', 'derniere_execution.json']] },
];
let fait = false;
const $ = (id) => document.getElementById(id);

export function init() {}

export async function show() {
  if (fait) return;
  fait = true;
  const corps = $('tel-themes').tBodies[0];
  let meta;
  try {
    meta = await chargerMeta();
  } catch (e) {
    fait = false;
    vider(corps).append(el('tr', {}, el('td', { colspan: 4 }, alerte('La liste des fichiers ne peut pas être chargée. ' + messageErreur(e), { reessayer: show }))));
    return;
  }
  vider(corps);
  const liens = [];
  const lien = (chemin, texte) => {
    const taille = el('span', { class: 'taille' }, '');
    const a = el('a', { class: 'lien-fichier', href: 'data/' + chemin, download: chemin.split('/').pop() }, texte, taille);
    liens.push([chemin, taille]);
    return a;
  };
  Object.entries(meta.themes).forEach(([cle, t], i) => {
    const csv = `csv/${t.fichier.replace(/\.parquet$/, '')}.csv.gz`;
    corps.append(el('tr', {},
      el('td', {}, el('span', { class: 'pastille-theme', style: `background:${COULEURS[i % COULEURS.length]}`, 'aria-hidden': 'true' }), t.libelle, el('span', { class: 'tech' }, cle)),
      el('td', { class: 'num' }, fmtEntier(t.indicateurs)),
      el('td', {}, lien(t.fichier, t.fichier)),
      el('td', {}, lien(csv, csv.split('/').pop()))));
  });
  const autres = vider($('tel-autres').tBodies[0]);
  if (meta.territoires && Array.isArray(meta.niveaux)) {
    AUTRES[0].contenu = `Les ${fmtEntier(meta.territoires)} territoires des ${meta.niveaux.length} niveaux, avec la région, le département, l'EPCI, la zone d'emploi et le territoire d'industrie de chaque commune.`;
  }
  for (const f of AUTRES) {
    const td = el('td', {});
    f.fichiers.forEach(([chemin, texte], j) => { if (j) td.append(el('br')); td.append(lien(chemin, texte)); });
    autres.append(el('tr', {}, el('th', { scope: 'row' }, f.nom), el('td', {}, f.contenu), td));
  }
  const pq = $('tel-powerquery');
  vider(pq).append(el('code', {}, [
    'let',
    '    // Adresse stable, mise à jour chaque mois',
    `    Source = Csv.Document(Binary.Decompress(Web.Contents("${adresseDonnees('csv/besoins.csv.gz')}"), Compression.GZip),`,
    '        [Delimiter = ";", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
    '    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true])',
    '    // Les nombres utilisent le point décimal : typez les colonnes avec la culture "en-US"',
    'in',
    '    Entetes',
  ].join('\n')));
  // Tailles des fichiers (requêtes HEAD en parallèle)
  await Promise.all(liens.map(async ([chemin, zone]) => {
    try {
      const r = await fetch(adresseDonnees(chemin), { method: 'HEAD', cache: 'no-cache' });
      if (!r.ok) { zone.textContent = 'fichier absent'; return; }
      const n = Number(r.headers.get('content-length'));
      if (n > 0 && !r.headers.get('content-encoding')) zone.textContent = fmtTaille(n);
    } catch (_) { /* taille inconnue : rien à afficher */ }
  }));
  $('tel-themes').dataset.pret = '1';
}
