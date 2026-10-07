/* Memory: il secondo gioco dell'arcade di casa, accanto a Snake.

   Sta in un file suo come `snake.js`, e per le stesse ragioni: e' un pezzo a se',
   non tocca nessun dato della casa e non usa la rete — si gioca anche senza
   connessione. La logica (`memoryNuovo`, `memoryGira`, `memoryNascondi`) e'
   **pura**: prende lo stato e ne restituisce uno nuovo, senza DOM e senza
   attese, cosi' si prova con node. `memoryGira` scopre una carta e, alla
   seconda, decide: se i simboli combaciano le segna come trovate, altrimenti le
   lascia scoperte perche' l'interfaccia le nasconda dopo un momento
   (`memoryNascondi`). Tenere la decisione nella funzione pura significa che il
   "quando" si nasconde e' l'unica cosa rimandata. */

const MEMORY_COPPIE = 8;
const MEMORY_SIMBOLI = ['\u{1F34B}', '\u{1F353}', '\u{1F347}', '\u{1F955}',
                        '\u{1F344}', '\u{1F33B}', '\u{1F41A}', '\u{1F340}'];
const MEMORY_NASCONDI_MS = 850;
const MEMORY_TASTO = 'memoryRecord';

/** Il mazzo mischiato: ogni simbolo due volte, in ordine casuale.

    Fisher-Yates con il generatore passato: cosi' il test decide l'ordine invece
    di sperare, e la distribuzione resta uniforme. */
function memoryMazzo(rand) {
  rand = rand || Math.random;
  const mazzo = [];
  for (let i = 0; i < MEMORY_COPPIE; i++) mazzo.push(i, i);
  for (let i = mazzo.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const t = mazzo[i]; mazzo[i] = mazzo[j]; mazzo[j] = t;
  }
  return mazzo;
}

/** Lo stato iniziale: tutte le carte coperte, nessuna mossa. */
function memoryNuovo(rand) {
  return {
    carte: memoryMazzo(rand).map((s) => ({ simbolo: s, stato: 'coperta' })),
    indice: [], mosse: 0, finito: false,
  };
}

/** Scopre la carta `i` e restituisce lo stato nuovo.

    Si ignora se la carta non e' coperta, se il gioco e' finito o se ci sono gia'
    due carte scoperte in attesa: e' la guardia che impedisce di scoprirne una
    terza mentre le prime due si stanno ancora guardando. Alla seconda carta si
    decide: simboli uguali -> trovate; diversi -> restano scoperte e sara'
    `memoryNascondi` a rimetterle coperte. */
function memoryGira(stato, i) {
  if (stato.finito || stato.indice.length >= 2) return stato;
  if (!stato.carte[i] || stato.carte[i].stato !== 'coperta') return stato;
  const carte = stato.carte.map((c, k) =>
    k === i ? { simbolo: c.simbolo, stato: 'scoperta' } : c);
  const indice = stato.indice.concat(i);
  if (indice.length < 2) return Object.assign({}, stato, { carte: carte, indice: indice });
  const a = indice[0], b = indice[1];
  const mosse = stato.mosse + 1;
  if (carte[a].simbolo === carte[b].simbolo) {
    carte[a] = { simbolo: carte[a].simbolo, stato: 'trovata' };
    carte[b] = { simbolo: carte[b].simbolo, stato: 'trovata' };
    const finito = carte.every((c) => c.stato === 'trovata');
    return Object.assign({}, stato, { carte: carte, indice: [], mosse: mosse, finito: finito });
  }
  return Object.assign({}, stato, { carte: carte, indice: indice, mosse: mosse });
}

/** Rimette coperte le due carte sbagliate (dopo che l'utente le ha viste).

    Separata da `memoryGira` perche' e' un fatto di **tempo**, non di regola: la
    logica decide che sono sbagliate, l'interfaccia le nasconde un attimo dopo. */
function memoryNascondi(stato) {
  if (stato.indice.length !== 2) return stato;
  const a = stato.indice[0], b = stato.indice[1];
  const carte = stato.carte.map((c, k) =>
    (k === a || k === b) && c.stato === 'scoperta'
      ? { simbolo: c.simbolo, stato: 'coperta' } : c);
  return Object.assign({}, stato, { carte: carte, indice: [] });
}

/** Vero se le due carte scoperte combaciano (per decidere se aspettare). */
function memoryAspetta(stato) {
  return stato.indice.length === 2
    && stato.carte[stato.indice[0]].simbolo !== stato.carte[stato.indice[1]].simbolo;
}

/* ---------- il gioco nel browser ---------- */

let memoryGioco = null;
let memoryAttesa = null;

function memoryRecord() {
  // il record e' il **minor** numero di mosse con cui si e' vinto: meno e'
  // meglio, quindi non si sovrascrive con un numero piu' alto
  try { return parseInt(localStorage.getItem(MEMORY_TASTO), 10) || 0; } catch (_e) { return 0; }
}

function memorySalvaRecord(mosse) {
  try { localStorage.setItem(MEMORY_TASTO, String(mosse)); } catch (_e) { /* niente memoria */ }
}

function memoryDisegna() {
  const griglia = document.getElementById('memory-griglia');
  if (!griglia || !memoryGioco) return;
  griglia.innerHTML = '';
  memoryGioco.carte.forEach((c, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'memory-carta' + (c.stato === 'coperta' ? '' : ' ' + c.stato);
    btn.dataset.i = String(i);
    btn.setAttribute('aria-label', c.stato === 'coperta' ? 'Carta coperta' : 'Carta scoperta');
    btn.textContent = c.stato === 'coperta' ? '' : MEMORY_SIMBOLI[c.simbolo];
    griglia.appendChild(btn);
  });
}

function memoryAggiornaPunteggio() {
  const m = document.getElementById('memory-mosse');
  const r = document.getElementById('memory-record');
  if (m && memoryGioco) m.textContent = String(memoryGioco.mosse);
  if (r) { const rec = memoryRecord(); r.textContent = rec ? String(rec) : '\u2014'; }
}

function memoryFine() {
  const mosse = memoryGioco.mosse;
  const prima = memoryRecord();
  if (!prima || mosse < prima) memorySalvaRecord(mosse);
  memoryAggiornaPunteggio();
  const esito = document.getElementById('memory-esito');
  if (esito) {
    const rec = memoryRecord();
    esito.textContent = mosse <= rec
      ? `Completato in ${mosse} mosse \u2014 nuovo record!`
      : `Completato in ${mosse} mosse \u2014 record ${rec}`;
    esito.classList.remove('hidden');
  }
}

/** Scopre una carta e, se serve, programma di nascondere le due sbagliate. */
function memoryClic(i) {
  if (!memoryGioco) return;
  const prima = memoryGioco;
  memoryGioco = memoryGira(memoryGioco, i);
  if (memoryGioco === prima) return;   // mossa ignorata: nessun ridisegno
  memoryDisegna();
  memoryAggiornaPunteggio();
  if (memoryGioco.finito) { memoryFine(); return; }
  if (memoryAspetta(memoryGioco)) {
    clearTimeout(memoryAttesa);
    memoryAttesa = setTimeout(() => {
      memoryGioco = memoryNascondi(memoryGioco);
      memoryDisegna();
    }, MEMORY_NASCONDI_MS);
  }
}

/** Avvia una partita nuova. */
function avviaMemory() {
  const griglia = document.getElementById('memory-griglia');
  if (!griglia) return;
  clearTimeout(memoryAttesa);
  memoryGioco = memoryNuovo(Math.random);
  const esito = document.getElementById('memory-esito');
  if (esito) esito.classList.add('hidden');
  memoryDisegna();
  memoryAggiornaPunteggio();
}

/* ---------- l'aggancio alla scheda ----------

   Come Snake: `app.js` non nomina questo gioco (e' scandito da un test che
   pretende ogni funzione chiamata definita **in quel file**, e queste vivono
   qui). Il gioco si aggancia da solo: si disegna quando la sua area e' visibile
   e si mette in pausa la' dove non lo e'. Il Memory non ha un ciclo continuo
   come Snake — reagisce ai clic — quindi "sincronizza" significa solo
   assicurarsi che una partita esista quando la scheda si apre la prima volta. */
const memoryPannello = document.querySelector('[data-tvp-panel="giochi"]');
const memorySezione = document.getElementById('tab-intrattenimento');
const memoryGiocoPanel = document.querySelector('[data-gioco-panel="memory"]');

function memoryAreaAperta() {
  const app = document.getElementById('app');
  return !!(memoryPannello && memoryPannello.classList.contains('active')
    && memoryGiocoPanel && memoryGiocoPanel.classList.contains('active')
    && memorySezione && memorySezione.classList.contains('active')
    && app && !app.classList.contains('hidden'));
}

function memorySincronizza() {
  if (!memoryAreaAperta()) return;
  if (!memoryGioco) avviaMemory();
}

[memoryPannello, memorySezione, memoryGiocoPanel].forEach((nodo) => {
  if (nodo) new MutationObserver(memorySincronizza)
    .observe(nodo, { attributes: true, attributeFilter: ['class'] });
});

document.addEventListener('click', (e) => {
  const carta = e.target.closest('.memory-carta');
  if (!carta) return;
  memoryClic(parseInt(carta.dataset.i, 10));
});

const memoryAvviaBtn = document.getElementById('memory-avvia');
if (memoryAvviaBtn) memoryAvviaBtn.addEventListener('click', avviaMemory);

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', memoryAggiornaPunteggio);
} else {
  memoryAggiornaPunteggio();
}
