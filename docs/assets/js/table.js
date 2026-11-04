// Tableau triable (clic sur un en-tête) et paginé, accessible au clavier. Seule la page affichée est dessinée.
import { el, vider, fmtNombre, nf } from './util.js';

const COLLATOR = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
const TAILLES = [25, 50, 100, 200];
let compteur = 0;

function estVide(v) { return v == null || v === '' || (typeof v === 'number' && Number.isNaN(v)); }

export class Tableau {
  /**
   * @param {HTMLElement} conteneur
   * @param {object} o colonnes: [{ titre, sousTitre?, info?, type: 'num'|'texte', valeur: ligne => v, rendu?: ligne => Node|string, format?: v => string, classe? }]
   */
  constructor(conteneur, { colonnes, legende = 'Tableau de données', taillePage = 50, haut = true, sansRetour = false, vide = 'Aucune ligne à afficher.' }) {
    this.conteneur = conteneur;
    this.colonnes = colonnes;
    this.legende = legende;
    this.taillePage = taillePage;
    this.haut = haut;
    this.sansRetour = sansRetour;
    this.messageVide = vide;
    this.lignes = [];
    this.vue = [];
    this.page = 0;
    this.tri = null; // { index, sens }
    this.id = 'tab' + (++compteur);
  }

  /** Remplace les colonnes et les lignes ; garde le tri si la colonne triée existe encore. */
  definir(colonnes, lignes, { garderTri = false } = {}) {
    this.colonnes = colonnes;
    if (!garderTri || !this.tri || this.tri.index >= colonnes.length) this.tri = null;
    this.charger(lignes);
  }

  charger(lignes) {
    this.lignes = lignes || [];
    this.page = 0;
    this.appliquerTri();
    this.dessiner();
  }

  /** Lignes dans l'ordre affiché (tri compris), pour l'export. */
  lignesOrdonnees() { return this.vue; }

  appliquerTri() {
    if (!this.tri) { this.vue = this.lignes.slice(); return; }
    const col = this.colonnes[this.tri.index];
    const sens = this.tri.sens;
    const vals = this.lignes.map((l) => col.valeur(l));
    const idx = vals.map((_, i) => i);
    const num = col.type === 'num';
    idx.sort((a, b) => {
      const va = vals[a]; const vb = vals[b];
      const ea = estVide(va); const eb = estVide(vb);
      if (ea || eb) return ea === eb ? a - b : (ea ? 1 : -1); // valeurs vides toujours en fin
      const c = num && typeof va === 'number' && typeof vb === 'number' ? va - vb : COLLATOR.compare(String(va), String(vb));
      return c === 0 ? a - b : c * sens;
    });
    this.vue = idx.map((i) => this.lignes[i]);
  }

  trier(index) {
    const col = this.colonnes[index];
    if (this.tri && this.tri.index === index) this.tri = { index, sens: -this.tri.sens };
    else this.tri = { index, sens: col.type === 'num' ? -1 : 1 };
    this.page = 0;
    this.appliquerTri();
    this.dessiner();
    const bouton = this.conteneur.querySelector(`th[data-i="${index}"] button`);
    if (bouton) bouton.focus();
  }

  dessiner() {
    const c = vider(this.conteneur);
    const n = this.vue.length;
    if (!n) {
      c.append(el('div', { class: 'carte vide-message', role: 'status' }, this.messageVide));
      return;
    }
    const pages = Math.max(1, Math.ceil(n / this.taillePage));
    if (this.page >= pages) this.page = pages - 1;
    const debut = this.page * this.taillePage;
    const fin = Math.min(n, debut + this.taillePage);

    const tete = el('tr');
    this.colonnes.forEach((col, i) => {
      const trie = this.tri && this.tri.index === i;
      const th = el('th', { scope: 'col', class: col.type === 'num' ? 'num' : '', 'aria-sort': trie ? (this.tri.sens > 0 ? 'ascending' : 'descending') : 'none', 'data-i': i, title: col.info || null });
      const lib = el('span', { class: 'entete-texte' }, col.titre, col.sousTitre ? el('span', { class: 'entete-unite', text: col.sousTitre }) : null);
      const sens = el('span', { class: 'sens', 'aria-hidden': 'true', text: trie ? (this.tri.sens > 0 ? '▲' : '▼') : '' });
      const b = el('button', { type: 'button', class: 'entete-tri', onclick: () => this.trier(i) }, lib, sens);
      b.setAttribute('aria-label', `${col.titre}${col.sousTitre ? ' (' + col.sousTitre + ')' : ''} : trier`);
      th.append(b);
      tete.append(th);
    });

    const corps = el('tbody');
    for (let r = debut; r < fin; r++) {
      const ligne = this.vue[r];
      const tr = el('tr');
      for (const col of this.colonnes) {
        let contenu; let vide = false;
        if (col.rendu) contenu = col.rendu(ligne);
        else {
          const v = col.valeur(ligne);
          if (estVide(v)) { vide = true; contenu = '-'; }
          else if (col.format) contenu = col.format(v);
          else if (col.type === 'num' && typeof v === 'number') contenu = fmtNombre(v, 2);
          else contenu = String(v);
        }
        const td = el('td', { class: [col.type === 'num' ? 'num' : '', col.classe || '', vide ? 'vide' : ''].join(' ').trim() || null, title: vide ? 'Valeur absente ou secrète' : null });
        td.append(contenu instanceof Node ? contenu : document.createTextNode(contenu));
        tr.append(td);
      }
      corps.append(tr);
    }
    const table = el('table', { class: 'donnees' + (this.sansRetour ? ' sans-retour' : ''), id: this.id }, el('caption', { class: 'visuellement-cache', text: this.legende }), el('thead', {}, tete), corps);
    c.append(el('div', { class: 'table-defile' + (this.haut ? ' haut' : ''), tabindex: '0', role: 'region', 'aria-label': this.legende }, table));

    const info = el('span', { class: 'info' }, `Lignes ${nf(0).format(debut + 1)} à ${nf(0).format(fin)} sur ${nf(0).format(n)}`);
    const pagination = el('div', { class: 'pagination', role: 'navigation', 'aria-label': 'Pagination du tableau' }, info);
    if (pages > 1) {
      const aller = (p) => { this.page = Math.min(pages - 1, Math.max(0, p)); this.dessiner(); };
      const bouton = (texte, p, inactif, label) => el('button', { type: 'button', class: 'btn btn-petit', disabled: inactif, 'aria-label': label || texte, onclick: () => aller(p) }, texte);
      pagination.append(
        bouton('Première', 0, this.page === 0, 'Première page'),
        bouton('Précédente', this.page - 1, this.page === 0, 'Page précédente'),
        el('span', { 'aria-live': 'polite' }, `Page ${nf(0).format(this.page + 1)} sur ${nf(0).format(pages)}`),
        bouton('Suivante', this.page + 1, this.page >= pages - 1, 'Page suivante'),
        bouton('Dernière', pages - 1, this.page >= pages - 1, 'Dernière page'),
      );
    }
    const choix = el('select', { 'aria-label': 'Lignes par page' }, ...TAILLES.map((t) => el('option', { value: t, selected: t === this.taillePage }, String(t))));
    choix.addEventListener('change', () => { this.taillePage = Number(choix.value); this.page = 0; this.dessiner(); });
    pagination.append(el('label', {}, 'Lignes par page', choix));
    c.append(pagination);
  }
}
