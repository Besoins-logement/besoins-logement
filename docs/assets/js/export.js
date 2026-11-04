// Export de la sélection : Excel (SheetJS, chargé à la demande) et CSV (point-virgule, virgule décimale, UTF-8 avec BOM).
import { chargerScript, telecharger } from './util.js';

const XLSX_URL = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
const XLSX_SRI = 'sha384-vtjasyidUo0kW94K5MXDXntzOJpQgBKXmE7e2Ga4LG0skTTLeBi97eFAXsqewJjw';

export const LICENCE = 'Licence ouverte 2.0 (Etalab) ou licence équivalente indiquée pour chaque colonne ci-dessous.';
export const ATTRIBUTION = "Source : base Besoins en logement (Procivis), d'après Insee, SDES, DGFiP et les autres producteurs cités pour chaque colonne.";
const VIDES = 'Une case vide signale une valeur absente ou couverte par le secret statistique, jamais un zéro.';

/** En-têtes lisibles et uniques : le libellé, complété du nom technique s'il apparaît deux fois. */
export function entetesUniques(colonnes) {
  const compte = new Map();
  for (const c of colonnes) compte.set(c.entete, (compte.get(c.entete) || 0) + 1);
  return colonnes.map((c) => (compte.get(c.entete) > 1 ? `${c.entete} [${c.technique}]` : c.entete));
}

/** Format d'affichage Excel d'une colonne : séparateur de milliers et autant de décimales que les données en portent (2 au plus). */
function formatExcel(col, lignes, j) {
  if (col.type !== 'num') return null;
  if (col.unite === 'part (1 = 100 %)') return '0.0%';
  let decimales = 0;
  for (let i = 0; i < lignes.length && decimales < 2; i++) {
    const v = lignes[i][j];
    if (typeof v !== 'number' || Number.isInteger(v)) continue;
    decimales = Math.max(decimales, Math.abs(Math.round(v * 10) - v * 10) < 1e-6 ? 1 : 2);
  }
  return decimales === 0 ? '#,##0' : '#,##0.' + '0'.repeat(decimales);
}

/**
 * @param {object} o
 *  colonnes: [{ entete, technique, type: 'num'|'texte', unite, annee, definition, source, producteur, adresse, millesime, licence, agregation }]
 *  lignes: tableaux de valeurs alignés sur colonnes
 *  contexte: [[libellé, valeur]] décrivant la sélection
 *  dateBase: date de mise à jour de la base (texte)
 *  nomFichier: nom du fichier .xlsx
 */
export async function exporterExcel({ colonnes, lignes, contexte, dateBase, nomFichier }) {
  const XLSX = await chargerScript(XLSX_URL, 'XLSX', XLSX_SRI);
  const entetes = entetesUniques(colonnes);

  // Feuille « Données »
  const ws = XLSX.utils.aoa_to_sheet([entetes, ...lignes]);
  colonnes.forEach((col, j) => {
    const z = formatExcel(col, lignes, j);
    if (!z) return;
    for (let i = 0; i < lignes.length; i++) {
      const cell = ws[XLSX.utils.encode_cell({ r: i + 1, c: j })];
      if (cell && cell.t === 'n') cell.z = z;
    }
  });
  ws['!cols'] = colonnes.map((col, j) => {
    let w = Math.min(48, Math.max(10, Math.ceil(entetes[j].length * 0.9)));
    if (col.type === 'texte') {
      for (let i = 0; i < Math.min(lignes.length, 300); i++) {
        const v = lignes[i][j];
        if (v != null) w = Math.max(w, Math.min(60, String(v).length + 2));
      }
    }
    return { wch: w };
  });
  if (lignes.length) ws['!autofilter'] = { ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: lignes.length, c: colonnes.length - 1 } }) };

  // Feuille « Lisez-moi »
  const maintenant = new Date();
  const lm = [
    ['Base « Besoins en logement » : extraction'],
    [],
    ['Date de mise à jour de la base', dateBase || ''],
    ["Date de l'extraction", maintenant.toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' })],
    ...contexte,
    ['Licence', LICENCE],
    ['Attribution', ATTRIBUTION],
    ['Valeurs vides', VIDES],
    [],
    ['Colonnes de la feuille « Données »'],
    ['Libellé (en-tête)', 'Colonne technique', 'Unité', 'Année', 'Définition', 'Source', 'Producteur', 'Adresse', 'Millésime', 'Licence', 'Règle de calcul'],
    ...colonnes.map((c, j) => [entetes[j], c.technique || '', c.unite || '', c.annee || '', c.definition || '', c.source || '', c.producteur || '', c.adresse || '', c.millesime || '', c.licence || '', c.agregation || '']),
  ];
  const wsl = XLSX.utils.aoa_to_sheet(lm);
  wsl['!cols'] = [{ wch: 42 }, { wch: 34 }, { wch: 18 }, { wch: 11 }, { wch: 90 }, { wch: 50 }, { wch: 30 }, { wch: 50 }, { wch: 30 }, { wch: 22 }, { wch: 14 }];
  // Adresses cliquables
  const debut = lm.length - colonnes.length;
  colonnes.forEach((c, j) => {
    if (c.adresse && /^https?:\/\//.test(c.adresse)) {
      const cell = wsl[XLSX.utils.encode_cell({ r: debut + j, c: 7 })];
      if (cell) cell.l = { Target: c.adresse };
    }
  });

  const wb = XLSX.utils.book_new();
  wb.Props = { Title: 'Besoins en logement - extraction', Subject: 'Extraction de la base Besoins en logement', Author: 'Base Besoins en logement', CreatedDate: maintenant };
  XLSX.utils.book_append_sheet(wb, ws, 'Données');
  XLSX.utils.book_append_sheet(wb, wsl, 'Lisez-moi');
  const tampon = XLSX.write(wb, { bookType: 'xlsx', type: 'array', compression: true });
  telecharger(new Blob([tampon], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), nomFichier);
}

function celluleCSV(v) {
  if (v == null) return '';
  if (typeof v === 'number') return Number.isFinite(v) ? String(v).replace('.', ',') : '';
  const s = String(v);
  return /[";\r\n]/.test(s) || /^\s|\s$/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

/** CSV : séparateur point-virgule, virgule décimale, fin de ligne CRLF, UTF-8 avec BOM (lisible directement par Excel). */
export function exporterCSV({ colonnes, lignes, nomFichier }) {
  const morceaux = [entetesUniques(colonnes).map(celluleCSV).join(';')];
  for (const l of lignes) morceaux.push(l.map(celluleCSV).join(';'));
  telecharger(new Blob(['﻿' + morceaux.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' }), nomFichier);
}
