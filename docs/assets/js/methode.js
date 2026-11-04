// Page « Méthode » : texte fixe (dans index.html) et compte rendu de la dernière exécution du robot.
import { lireJSON, fmtDate, messageErreur } from './util.js';

let fait = false;

export function init() {}

export async function show() {
  if (fait) return;
  fait = true;
  const zone = document.getElementById('met-robot');
  try {
    const r = await lireJSON('derniere_execution.json');
    const modules = Array.isArray(r.modules) ? r.modules : [];
    const ok = modules.filter((m) => m.etat === 'ok').length;
    const echecs = modules.filter((m) => m.etat !== 'ok');
    const d = new Date(r.date);
    const heure = Number.isNaN(d.getTime()) ? '' : ` à ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} (heure UTC)`;
    let texte = `Dernière exécution du robot : ${fmtDate(r.date)}${heure} ; ${ok} module${ok > 1 ? 's' : ''} recalculé${ok > 1 ? 's' : ''} sans erreur`;
    texte += echecs.length ? ` ; ${echecs.length} en échec, qui gardent leur dernière version valide : ${echecs.map((m) => m.module).join(', ')}.` : '.';
    zone.textContent = texte;
  } catch (e) {
    fait = false;
    zone.textContent = 'Le compte rendu de la dernière exécution est indisponible. ' + messageErreur(e);
  }
}
