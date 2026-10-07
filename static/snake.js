/* Snake: il gioco della sezione TV.

   Sta in un file suo, non dentro `app.js`, perche' e' un pezzo a se': si carica
   solo quando si apre la scheda «Giochi» e non tocca nessun dato della casa.
   Non usa librerie e non usa la rete: si disegna su un `<canvas>` e funziona
   anche senza connessione, come il resto della sezione.

   La logica del gioco (`snakeNuovo`, `snakePasso`, `snakeDirezione`) e' **pura**:
   prende lo stato e ne restituisce uno nuovo, senza DOM e senza attese. Cosi' si
   prova con node, che e' l'unico modo di verificare un gioco senza giocarlo. */

const SNAKE_COLS = 15;
const SNAKE_ROWS = 15;
const SNAKE_PASSO_MS = 140;
const SNAKE_TASTO = 'snakeRecord';

/** Lo stato iniziale: serpente al centro, fermo verso destra, cibo a caso. */
function snakeNuovo(rand) {
  rand = rand || Math.random;
  const corpo = [{ x: 7, y: 7 }, { x: 6, y: 7 }, { x: 5, y: 7 }];
  return {
    cols: SNAKE_COLS, rows: SNAKE_ROWS,
    corpo: corpo, dir: { x: 1, y: 0 },
    cibo: snakeCellaLibera(corpo, rand),
    punteggio: 0, finito: false,
  };
}

/** Una cella libera a caso, o `null` se il serpente occupa tutto il campo. */
function snakeCellaLibera(corpo, rand) {
  const libere = [];
  for (let y = 0; y < SNAKE_ROWS; y++) {
    for (let x = 0; x < SNAKE_COLS; x++) {
      if (!corpo.some((c) => c.x === x && c.y === y)) libere.push({ x: x, y: y });
    }
  }
  if (!libere.length) return null;
  return libere[Math.floor(rand() * libere.length)];
}

/** Un passo: la testa avanza, la coda segue. Mangiando, la coda non si toglie.

    Le collisioni sono due e si controllano **dopo** aver mosso la testa: il
    muro (si esce dal campo) e il proprio corpo. La coda dell'ultimo tratto non
    conta come corpo quando non si mangia: si sta spostando, quindi la testa puo'
    prenderne il posto — e' il comportamento classico, e senza questo il serpente
    morirebbe inseguendo la propria coda. */
function snakePasso(stato, rand) {
  rand = rand || Math.random;
  if (stato.finito) return stato;
  const testa = stato.corpo[0];
  const nuova = { x: testa.x + stato.dir.x, y: testa.y + stato.dir.y };
  const fuori = nuova.x < 0 || nuova.y < 0
    || nuova.x >= stato.cols || nuova.y >= stato.rows;
  const mangiato = stato.cibo
    && nuova.x === stato.cibo.x && nuova.y === stato.cibo.y;
  const corpo = mangiato ? stato.corpo : stato.corpo.slice(0, -1);
  const addosso = corpo.some((c) => c.x === nuova.x && c.y === nuova.y);
  if (fuori || addosso) return Object.assign({}, stato, { finito: true });
  const corpoNuovo = [nuova].concat(stato.corpo);
  if (!mangiato) corpoNuovo.pop();
  return Object.assign({}, stato, {
    corpo: corpoNuovo,
    cibo: mangiato ? snakeCellaLibera(corpoNuovo, rand) : stato.cibo,
    punteggio: stato.punteggio + (mangiato ? 1 : 0),
  });
}

/** La direzione richiesta, se non e' quella opposta a quella attuale.

    Senza questo, premendo «indietro» il serpente entrerebbe nella propria testa
    e morirebbe: la direzione opposta si ignora, non si applica. */
function snakeDirezione(richiesta, attuale) {
  if (richiesta.x === -attuale.x && richiesta.y === -attuale.y) return attuale;
  return richiesta;
}

/* ---------- il gioco nel browser ---------- */

let snakeGioco = null;
let snakeRAF = null;
let snakeUltimo = 0;
let snakeAudio = null;
let snakeTocco = null;

function snakeRecord() {
  try { return parseInt(localStorage.getItem(SNAKE_TASTO), 10) || 0; } catch (_e) { return 0; }
}

function snakeSalvaRecord(punti) {
  try { localStorage.setItem(SNAKE_TASTO, String(punti)); } catch (_e) { /* niente memoria */ }
}

/** Un bip breve: stesso suono del resto dell'app, quindi rispetta la preferenza.

    L'`AudioContext` si crea al primo suono e non all'avvio: un contesto creato
    senza un gesto nasce sospeso, e i browser lo tengono fermo finche' non si
    tocca la pagina. Creandolo al momento del bip (che segue sempre un tocco) si
    parte gia' sbloccati. */
function snakeBip(freq, durata) {
  if (typeof suonoAttivo === 'function' && !suonoAttivo()) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  try {
    if (!snakeAudio) snakeAudio = new Ctx();
    if (snakeAudio.state === 'suspended') snakeAudio.resume();
    const ora = snakeAudio.currentTime;
    const osc = snakeAudio.createOscillator();
    const vol = snakeAudio.createGain();
    osc.type = 'square';
    osc.frequency.value = freq;
    vol.gain.setValueAtTime(0.0001, ora);
    vol.gain.exponentialRampToValueAtTime(0.08, ora + 0.01);
    vol.gain.exponentialRampToValueAtTime(0.0001, ora + durata);
    osc.connect(vol).connect(snakeAudio.destination);
    osc.start(ora);
    osc.stop(ora + durata + 0.02);
  } catch (_e) { /* audio non disponibile: il gioco funziona lo stesso */ }
}

function snakeDisegna() {
  const cv = document.getElementById('snake-canvas');
  if (!cv || !snakeGioco) return;
  const ctx = cv.getContext('2d');
  const lato = cv.width / SNAKE_COLS;
  const cs = getComputedStyle(document.documentElement);
  const col = (nome, ripiego) => (cs.getPropertyValue(nome).trim() || ripiego);
  const fondo = col('--surface', '#ffffff');
  const linea = col('--line', '#dce9ef');
  const accento = col('--accent', '#0b6e8f');
  const verde = col('--green', '#17796b');
  const scuro = col('--ink', '#0e2a38');

  ctx.fillStyle = fondo;
  ctx.fillRect(0, 0, cv.width, cv.height);
  // griglia appena accennata: aiuta a leggere le celle senza rubare l'occhio
  ctx.strokeStyle = linea;
  ctx.lineWidth = 1;
  for (let i = 1; i < SNAKE_COLS; i++) {
    ctx.beginPath(); ctx.moveTo(i * lato, 0); ctx.lineTo(i * lato, cv.height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i * lato); ctx.lineTo(cv.width, i * lato); ctx.stroke();
  }
  // il cibo: un cerchio pieno, distinto dalle celle quadrate del serpente
  if (snakeGioco.cibo) {
    ctx.fillStyle = accento;
    ctx.beginPath();
    ctx.arc((snakeGioco.cibo.x + 0.5) * lato, (snakeGioco.cibo.y + 0.5) * lato,
            lato * 0.32, 0, Math.PI * 2);
    ctx.fill();
  }
  // il serpente: la testa piu' scura, il corpo verde
  snakeGioco.corpo.forEach((c, i) => {
    ctx.fillStyle = i === 0 ? scuro : verde;
    const m = lato * 0.08;
    ctx.fillRect(c.x * lato + m, c.y * lato + m, lato - 2 * m, lato - 2 * m);
  });
}

function snakeAggiornaPunteggio() {
  const p = document.getElementById('snake-punteggio');
  const r = document.getElementById('snake-record');
  if (p && snakeGioco) p.textContent = String(snakeGioco.punteggio);
  if (r) r.textContent = String(snakeRecord());
}

function snakeFine() {
  const punti = snakeGioco.punteggio;
  if (punti > snakeRecord()) snakeSalvaRecord(punti);
  snakeAggiornaPunteggio();
  snakeBip(160, 0.28);
  const esito = document.getElementById('snake-esito');
  if (esito) {
    const record = snakeRecord();
    esito.textContent = punti >= record && punti > 0
      ? `Punteggio ${punti} — nuovo record!`
      : `Punteggio ${punti} — record ${record}`;
    esito.classList.remove('hidden');
  }
}

function snakeTick() {
  if (!snakeGioco || snakeGioco.finito) return;
  const prima = snakeGioco.punteggio;
  snakeGioco = snakePasso(snakeGioco, Math.random);
  snakeDisegna();
  if (snakeGioco.punteggio > prima) snakeBip(660, 0.09);
  if (snakeGioco.finito) snakeFine();
}

function snakeCiclo(ts) {
  snakeRAF = requestAnimationFrame(snakeCiclo);
  if (!snakeUltimo) snakeUltimo = ts;
  if (ts - snakeUltimo >= SNAKE_PASSO_MS) {
    snakeUltimo = ts;
    snakeTick();
  }
}

function snakeFerma() {
  if (snakeRAF) { cancelAnimationFrame(snakeRAF); snakeRAF = null; }
  snakeUltimo = 0;
}

/** Avvia una partita nuova e accende il ciclo. */
function avviaSnake() {
  const cv = document.getElementById('snake-canvas');
  if (!cv) return;
  snakeGioco = snakeNuovo(Math.random);
  const esito = document.getElementById('snake-esito');
  if (esito) esito.classList.add('hidden');
  snakeDisegna();
  snakeAggiornaPunteggio();
  snakeFerma();
  snakeCiclo(0);
}

/** Cambia direzione, ignorando il contrario di quella attuale. */
function snakeImpostaDir(d) {
  if (!snakeGioco || snakeGioco.finito) return;
  snakeGioco = Object.assign({}, snakeGioco, { dir: snakeDirezione(d, snakeGioco.dir) });
}

/* I comandi: frecce e WASD sul computer, la croce direzionale e lo swipe sul
   telefono. Sono tutti lo stesso `snakeImpostaDir`. */
document.addEventListener('keydown', (e) => {
  if (!snakeGioco || !snakeSchedaAperta()) return;
  const mappa = {
    ArrowUp: { x: 0, y: -1 }, ArrowDown: { x: 0, y: 1 },
    ArrowLeft: { x: -1, y: 0 }, ArrowRight: { x: 1, y: 0 },
    w: { x: 0, y: -1 }, s: { x: 0, y: 1 }, a: { x: -1, y: 0 }, d: { x: 1, y: 0 },
    W: { x: 0, y: -1 }, S: { x: 0, y: 1 }, A: { x: -1, y: 0 }, D: { x: 1, y: 0 },
  };
  const d = mappa[e.key];
  if (!d) return;
  e.preventDefault();  // altrimenti le frecce fanno scorrere la pagina
  snakeImpostaDir(d);
});

document.addEventListener('click', (e) => {
  const btn = e.target.closest('.snake-freccia');
  if (!btn) return;
  snakeImpostaDir({ x: parseInt(btn.dataset.dx, 10), y: parseInt(btn.dataset.dy, 10) });
});

/** Lo swipe: un dito che si sposta di almeno 24px decide la direzione. */
document.addEventListener('touchstart', (e) => {
  if (!e.target.closest('#snake-canvas')) return;
  const t = e.changedTouches[0];
  snakeTocco = { x: t.clientX, y: t.clientY };
}, { passive: true });

document.addEventListener('touchend', (e) => {
  if (!snakeTocco) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - snakeTocco.x;
  const dy = t.clientY - snakeTocco.y;
  snakeTocco = null;
  if (Math.abs(dx) < 24 && Math.abs(dy) < 24) return;
  if (Math.abs(dx) > Math.abs(dy)) snakeImpostaDir({ x: dx > 0 ? 1 : -1, y: 0 });
  else snakeImpostaDir({ x: 0, y: dy > 0 ? 1 : -1 });
}, { passive: true });

/* ---------- l'aggancio alle schede ----------

   Il gioco si accende e si spegne da solo: `app.js` non lo chiama. Non e' un
   vezzo — `app.js` e' scandito da un test che pretende che ogni funzione
   chiamata esista **in quel file**, e `avviaSnake` vive qui: chiamandola di la'
   il test la vedrebbe come un riferimento a una funzione inesistente, che e' il
   difetto vero (un `ReferenceError` all'accesso) che quel test esiste per
   cogliere. Il file resta autosufficiente.

   Giochi non e' piu' una scheda della barra ma una **sotto-scheda** della TV:
   non c'e' un clic da ascoltare. Si osserva lo stato delle classi (il pannello e
   la sezione) e si sincronizza: una sola regola, `snakeSincronizza`, cosi' i
   vari inneschi non possono divergere. */
const snakePannello = document.querySelector('[data-tvp-panel="giochi"]');
const snakeSezione = document.getElementById('tab-intrattenimento');
const snakeGiocoPanel = document.querySelector('[data-gioco-panel="snake"]');

/** Il gioco gira solo con la sua sotto-scheda aperta, **e il gioco scelto e'
    Snake** (dentro i Giochi ce ne sono due), con la pagina in primo piano.
    Fuori da li' e' fermo (ma la partita resta). */
function snakeSchedaAperta() {
  const app = document.getElementById('app');
  return !!(snakePannello && snakePannello.classList.contains('active')
    && snakeGiocoPanel && snakeGiocoPanel.classList.contains('active')
    && snakeSezione && snakeSezione.classList.contains('active')
    && app && !app.classList.contains('hidden') && !document.hidden);
}

/** Accende, riprende o ferma secondo lo stato. Idempotente: chiamarla due volte
    di fila non fa ripartire la partita da capo — gli inneschi sono piu' d'uno e
    si sovrappongono. */
function snakeSincronizza() {
  if (!snakeSchedaAperta()) { snakeFerma(); return; }
  if (!snakeGioco) { avviaSnake(); return; }
  if (!snakeGioco.finito && !snakeRAF) snakeCiclo(0);
}

[snakePannello, snakeSezione, snakeGiocoPanel].forEach((nodo) => {
  if (nodo) new MutationObserver(snakeSincronizza)
    .observe(nodo, { attributes: true, attributeFilter: ['class'] });
});

const snakeAvviaBtn = document.getElementById('snake-avvia');
if (snakeAvviaBtn) snakeAvviaBtn.addEventListener('click', avviaSnake);

// Uscendo dall'area l'app nasconde tutto: `snakeSincronizza` se ne accorge e
// ferma il ciclo, che altrimenti girerebbe dietro la home consumando batteria.
['to-home', 'home-fab'].forEach((id) => {
  const b = document.getElementById(id);
  if (b) b.addEventListener('click', snakeSincronizza);
});

// Telefono bloccato o scheda del browser in secondo piano: pausa al ritorno,
// **senza azzerare** la partita. `visibilitychange` e' l'unico segnale
// affidabile su mobile, e `document.hidden` e' gia' dentro `snakeSchedaAperta`.
document.addEventListener('visibilitychange', snakeSincronizza);

// Il record si mostra appena la pagina e' pronta, anche senza aprire la scheda.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', snakeAggiornaPunteggio);
} else {
  snakeAggiornaPunteggio();
}
