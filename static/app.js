/* ---------- helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `Errore ${res.status}`);
  return data;
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 2400);
}

/* Riduce una foto scelta dall'utente prima di mandarla al server.
   La riduzione sta qui e non sul server per non aggiungere una libreria di
   elaborazione immagini alle dipendenze: chi installa l'app deve poter
   fotografare una scatola senza scaricare Pillow. Un lato oltre ~1280 px e un
   JPEG di qualita' 0.82 bastano per riconoscere una confezione sullo schermo di
   un telefono, e tengono il database leggero.

   Restituisce un data URL. Le foto gia' piccole, e i PNG con trasparenza, si
   convertono lo stesso in JPEG: e' il formato che il server accetta senza
   dubbi, e un ritaglio di trasparenza su una foto di scatole non serve. */
function riduciFoto(file, maxLato = 1280) {
  return new Promise((resolve, reject) => {
    if (!file.type || !file.type.startsWith('image/')) {
      return reject(new Error('Scegli un file immagine'));
    }
    const lettore = new FileReader();
    lettore.onerror = () => reject(new Error('Non riesco a leggere la foto'));
    lettore.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('Il file non sembra un\'immagine'));
      img.onload = () => {
        // niente ingrandimenti: una foto piccola resta piccola
        const scala = Math.min(1, maxLato / Math.max(img.width, img.height));
        const w = Math.max(1, Math.round(img.width * scala));
        const h = Math.max(1, Math.round(img.height * scala));
        const tela = document.createElement('canvas');
        tela.width = w; tela.height = h;
        const ctx = tela.getContext('2d');
        // il JPEG non ha trasparenza: senza fondo bianco le zone trasparenti
        // diventerebbero nere
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        resolve(tela.toDataURL('image/jpeg', 0.82));
      };
      img.src = lettore.result;
    };
    lettore.readAsDataURL(file);
  });
}

const pad = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fmtDay = (d) => d.toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric', month: 'short' });
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

// i pasti arrivano da /api/meta: unica fonte di verità col backend
let MEALS = [];
let meta = { units: [], categories: [], meals: [], allergens: [] };
let recipesCache = [];
let profile = null;
// etichette italiane delle chiavi allergene, per mostrare i nomi per esteso
let allergenLabels = {};
let weekStart = startOfWeek(new Date());

function startOfWeek(d) {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // lunedì = 0
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
}

/* ---------- pasti al giorno ----------
   Quanti pasti si vogliono gestire e' una scelta dell'utente (1-5), non una
   costante: i nomi dei pasti li decide il backend in MEAL_SETS, qui si mostra
   solo l'etichetta e si rilegge /api/meta dopo ogni cambio. */
function etichettaPasti(n) {
  const nomi = ((meta.meal_sets || {})[String(n)] || []).join(', ');
  return `${n} ${n === 1 ? 'pasto' : 'pasti'}${nomi ? ` · ${nomi}` : ''}`;
}

async function applicaPasti(n) {
  const salvato = await api('/api/profile', { method: 'PUT', body: { meals_per_day: n } });
  meta = await api('/api/meta');
  MEALS = meta.meals;
  profile = salvato;
  await renderPlan();
}

/* ---------- sezioni ----------
   La pagina iniziale smista verso quattro aree. Le schede della barra appartengono
   a un'area (`data-section`): aprendo un'area si mostrano solo le sue, così
   le aree restano separate invece di mischiarsi in un'unica barra piena di voci. */
const SEZIONI = {
  // La Cucina porta l'icona dell'app (la bandiera col cielo sereno) invece di
  // un'emoji: e' l'area principale e la si riconosce a colpo d'occhio. Le altre
  // tengono la loro, che le distingue meglio di un simbolo unico.
  cucina:   { titolo: 'Cucina',   icona: '/static/icons/icona.svg', prima: 'plan' },
  igiene:   { titolo: '\u{1F9FD} Igiene',   prima: 'igiene' },
  progetti: { titolo: '\u{1F4CB} Progetti', prima: 'progetti' },
  faq:      { titolo: '\u{1F4CC} FAQ',      prima: 'faq' },
};

function apriSezione(nome) {
  const cfg = SEZIONI[nome];
  if (!cfg) return;
  const titolo = $('#app-title');
  if (cfg.icona) {
    titolo.innerHTML = `<img class="icona-titolo" src="${cfg.icona}" alt="" aria-hidden="true">${esc(cfg.titolo)}`;
  } else {
    titolo.textContent = cfg.titolo;
  }
  titolo.dataset.sezione = nome;
  document.title = `${cfg.titolo} · Il Maggiordomo`;
  // solo le schede dell'area aperta
  $$('#tabs button').forEach((b) => {
    b.classList.toggle('hidden', b.dataset.section !== nome);
  });
  $('#home').classList.add('hidden');
  $('#app').classList.remove('hidden');
  // il microfono serve in ogni area, non solo in cucina
  $('#mic').classList.remove('hidden');
  // la home invece resta raggiungibile da ogni area
  $('#home-fab').classList.remove('hidden');
  window.scrollTo(0, 0);
  switchTab(cfg.prima);
  // le domande iniziali riguardano la cucina: si aprono qui, non sulla home
  if (nome === 'cucina') avviaProfiloSeServe();
}

function tornaAlleSezioni() {
  hideModal();
  $('#voice').classList.add('hidden');
  $('#app').classList.add('hidden');
  $('#mic').classList.add('hidden');
  $('#home-fab').classList.add('hidden');
  $('#home').classList.remove('hidden');
  document.title = 'Il Maggiordomo';
  window.scrollTo(0, 0);
}

/* Apre l'area a cui appartiene una scheda, se non e' gia' quella aperta.
   Serve ai comandi vocali, che possono toccare una scheda di un'altra area. */
function apreSezioneDella(nome) {
  if (!nome) return;
  if (!$('#app').classList.contains('hidden') && $('#app-title').dataset.sezione === nome) return;
  apriSezione(nome);
}

$$('.home-card').forEach((card) => card.addEventListener('click', () => apriSezione(card.dataset.section)));
$('#to-home').addEventListener('click', tornaAlleSezioni);
$('#home-fab').addEventListener('click', tornaAlleSezioni);
// Stesso pannello del microfono flottante, ma raggiungibile dalla home: qui il
// pulsante flottante e' nascosto, perche' non c'e' ancora una sezione aperta.
$('#home-mic').addEventListener('click', apriVoce);

/* ---------- tabs ---------- */
$$('#tabs button').forEach((btn) => btn.addEventListener('click', () => {
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${btn.dataset.tab}`));
  if (btn.dataset.tab === 'plan') renderPlan();
  if (btn.dataset.tab === 'recipes') renderRecipes();
  if (btn.dataset.tab === 'pantry') renderPantry();
  if (btn.dataset.tab === 'shopping') renderShopping();
  if (btn.dataset.tab === 'profile') renderProfile();
  if (btn.dataset.tab === 'igiene') renderIgiene();
  if (btn.dataset.tab === 'progetti') renderProgetti();
  if (btn.dataset.tab === 'magazzino') renderMagazzino();
  if (btn.dataset.tab === 'faq') renderFaq();
}));

/* ---------- PIANO ---------- */
let planCache = [];
async function renderPlan() {
  const days = [...Array(7)].map((_, i) => addDays(weekStart, i));
  $('#week-label').textContent = `${fmtDay(days[0])} – ${fmtDay(days[6])}`;
  const plan = await api(`/api/plan?start=${iso(days[0])}&end=${iso(days[6])}`);
  planCache = plan;
  const today = iso(new Date());

  $('#plan-grid').innerHTML = days.map((d) => {
    const key = iso(d);
    const cells = MEALS.map((m) => {
      const entry = plan.find((p) => p.date === key && p.meal === m);
      if (!entry) {
        return `<div class="slot" data-date="${key}" data-meal="${m}">
             <span class="meal">${m}</span><span class="rname">+ aggiungi</span></div>`;
      }
      const bad = entry.conflicts && entry.conflicts.length;
      return `<div class="slot filled ${bad ? 'unsafe' : ''}" data-id="${entry.id}" data-recipe="${entry.recipe_id}" title="${bad ? `Attenzione: ${esc(entry.conflicts.join(', '))}` : 'Clicca per la preparazione'}">
             <span class="meal">${m} · ${entry.servings}p</span>
             <span class="rname">${esc(entry.recipe_name)}${bad ? ' <span class="warn-icon">⚠️</span>' : ''}</span></div>`;
    }).join('');
    return `<div class="day ${key === today ? 'today' : ''}"><h3>${fmtDay(d)}</h3>${cells}</div>`;
  }).join('');
}

$('#plan-grid').addEventListener('click', async (e) => {
  const slot = e.target.closest('.slot');
  if (!slot) return;
  if (slot.classList.contains('filled')) {
    // cliccare il pasto mostra come si prepara; la rimozione sta nella finestra
    const entry = planCache.find((p) => String(p.id) === slot.dataset.id) || {};
    showRecipeDetail(Number(slot.dataset.recipe), {
      conflicts: entry.conflicts,
      onRemove: async () => {
        await api(`/api/plan/${slot.dataset.id}`, { method: 'DELETE' });
        toast('Pasto rimosso');
        renderPlan();
      },
    });
  } else {
    openMealPicker(slot.dataset.date, slot.dataset.meal);
  }
});

async function openMealPicker(date, meal) {
  const list = await api('/api/recipes?full=1');
  recipesCache = list;
  if (!list.length) return toast('Crea prima una ricetta');
  showModal(`Aggiungi ${meal}`, `
    <div class="field"><label>Ricetta</label>
      <select id="pick-recipe">${list.map((r) => `<option value="${r.id}">${esc(r.name)}${r.conflicts.length ? ' ⚠️' : ''}</option>`).join('')}</select>
    </div>
    <div id="pick-warn"></div>
    <div class="field"><label>Porzioni</label><input id="pick-serv" type="number" min="1" value="2"></div>
    <button class="primary" id="pick-ok">Aggiungi al piano</button>
  `);
  const warn = $('#pick-warn');
  const showWarn = () => {
    const r = list.find((x) => x.id === Number($('#pick-recipe').value));
    warn.innerHTML = r && r.conflicts.length
      ? `<div class="banner"><strong>⚠️ Contiene: ${r.conflicts.map(esc).join(', ')}</strong>
           <p>Hai dichiarato queste restrizioni nel profilo. Puoi comunque aggiungerla.</p></div>`
      : '';
  };
  $('#pick-recipe').addEventListener('change', showWarn);
  showWarn();
  $('#pick-ok').addEventListener('click', async () => {
    await api('/api/plan', {
      method: 'POST',
      body: { date, meal, recipe_id: Number($('#pick-recipe').value), servings: Number($('#pick-serv').value) },
    });
    hideModal();
    toast('Aggiunto al piano');
    renderPlan();
  });
}

$('#week-prev').addEventListener('click', () => { weekStart = addDays(weekStart, -7); renderPlan(); });
$('#week-next').addEventListener('click', () => { weekStart = addDays(weekStart, 7); renderPlan(); });
$('#week-today').addEventListener('click', () => { weekStart = startOfWeek(new Date()); renderPlan(); });

// la lista si aggiorna da sola a ogni modifica del piano: qui si va solo a
// guardarla, senza dover rigenerare nulla
$('#gen-week').addEventListener('click', () => {
  $$('#tabs button').find((b) => b.dataset.tab === 'shopping').click();
});

/* ---------- RICETTE ---------- */
async function renderRecipes() {
  const hideUnsafe = $('#pf-filter') && $('#pf-filter').checked;
  const onlyFav = $('#fav-only') && $('#fav-only').checked;
  recipesCache = await api(hideUnsafe ? '/api/recipes?full=1&safe=1' : '/api/recipes?full=1');
  const q = $('#recipe-search').value.toLowerCase();
  const list = recipesCache.filter((r) => r.name.toLowerCase().includes(q))
    .filter((r) => !onlyFav || r.favorite);
  $('#recipe-list').innerHTML = list.map((r) => {
    const bad = r.conflicts && r.conflicts.length;
    const allerg = r.allergens && r.allergens.length
      ? `<div class="allergens">Allergeni: ${r.allergens.map(esc).join(', ')}</div>` : '';
    const warn = bad ? `<div>${r.conflicts.map((c) => `<span class="badge">⚠️ ${esc(c)}</span>`).join('')}</div>` : '';
    const stella = r.favorite ? '<span class="fav-star" title="Ricetta preferita">★</span>' : '';
    const foto = r.image
      ? `<figure class="card-photo" title="${esc(r.image_credit || '')}">
           <img src="/static/recipes/${encodeURIComponent(r.image)}" alt="${esc(r.name)}"
                loading="lazy" decoding="async" width="800" height="533">
         </figure>` : '';
    return `
    <div class="card ${bad ? 'unsafe' : ''}" data-recipe="${r.id}">
      ${foto}
      <h3>${esc(r.name)}${stella}</h3>
      <div class="meta">${r.servings} porzioni${r.time_minutes ? ` · ${r.time_minutes} min` : ''} · ${esc(r.difficulty)}</div>
      <div class="ings">${r.items.map((i) => `${esc(i.name)} ${i.quantity}${esc(i.unit)}`).join(' · ') || 'Nessun ingrediente'}</div>
      ${allerg}${warn}
      <div class="actions">
        <button class="fav-toggle ${r.favorite ? 'on' : ''}" data-fav="${r.id}" title="${r.favorite ? 'Togli dalle preferite' : 'Segna come preferita'}">${r.favorite ? '★ Preferita' : '☆ Preferita'}</button>
        <button data-open="${r.id}">Preparazione</button>
        <button data-edit="${r.id}">Modifica</button>
        <button data-del="${r.id}">Elimina</button>
      </div>
    </div>`;
  }).join('') || (onlyFav
    ? '<p>Nessuna ricetta preferita. Segnane una con <strong>☆ Preferita</strong>.</p>'
    : '<p>Nessuna ricetta. Creane una!</p>');
}

$('#recipe-search').addEventListener('input', renderRecipes);
// anche dal pulsante si passa dalla scelta: scriverla o cercarla online
$('#new-recipe').addEventListener('click', () => nuovaRicetta());

$('#recipe-list').addEventListener('click', async (e) => {
  const editId = e.target.dataset.edit;
  const delId = e.target.dataset.del;
  const favId = e.target.dataset.fav;
  const openId = e.target.closest('.card')?.dataset.recipe;
  if (favId) {
    // la stella agisce sulla scheda: non deve aprire la preparazione
    const r = recipesCache.find((x) => x.id === Number(favId));
    const next = (profile.favorite_ids || []).filter((i) => i !== Number(favId));
    if (!r || !r.favorite) next.push(Number(favId));
    await saveFavorites(next);
    toast(r && r.favorite ? 'Tolta dalle preferite' : 'Aggiunta alle preferite');
    renderRecipes();
  } else if (editId) recipeForm(recipesCache.find((r) => r.id === Number(editId)));
  else if (delId) {
    if (!confirm('Eliminare la ricetta?')) return;
    await api(`/api/recipes/${delId}`, { method: 'DELETE' });
    toast('Ricetta eliminata');
    renderRecipes();
  } else if (openId) showRecipeDetail(Number(openId));
});

$('#fav-only').addEventListener('change', renderRecipes);

/* ---------- preparazione di una ricetta ---------- */

/* Spezza la preparazione in passi numerati sulle fine di frase.
   La maiuscola dopo il punto evita di troncare "180°C. Poi..." ma anche
   abbreviazioni come "es." quando la parola seguente e' minuscola. */
function passiDa(testo) {
  return String(testo || '')
    .split(/\n+/)
    .flatMap((riga) => riga.split(/(?<=[.!?])\s+(?=[A-ZÀ-Ù])/))
    .map((p) => p.trim())
    .filter(Boolean);
}

/* Mostra la preparazione. Con `contesto` si aggiungono azioni sul pasto
   (es. rimuoverlo dal piano) accanto a quella di modifica. */
async function showRecipeDetail(rid, contesto = {}) {
  let r = recipesCache.find((x) => x.id === rid);
  if (!r || r.instructions === undefined || !r.items) r = await api(`/api/recipes/${rid}`);

  const passi = passiDa(r.instructions);
  const ingredienti = r.items.map((i) =>
    `<li>${esc(i.name)} <span class="qty">${esc(i.quantity)}${esc(i.unit)}</span></li>`).join('');

  const foto = r.image
    ? `<figure class="detail-photo" title="${esc(r.image_credit || '')}">
         <img src="/static/recipes/${encodeURIComponent(r.image)}" alt="${esc(r.name)}"
              loading="lazy" decoding="async"></figure>` : '';

  const preparazione = passi.length
    ? `<ol class="steps">${passi.map((p) => `<li>${esc(p)}</li>`).join('')}</ol>`
    : `<p class="muted">Nessuna preparazione indicata. Usa <strong>Modifica</strong> per aggiungerla.</p>`;

  showModal(r.name, `
    ${foto}
    <div class="detail-meta meta">
      ${r.servings} porzioni${r.time_minutes ? ` · ${r.time_minutes} min` : ''} · ${esc(r.difficulty)}
    </div>
    <h3 class="detail-sub">Ingredienti</h3>
    <ul class="detail-ings">${ingredienti || '<li class="muted">Nessun ingrediente</li>'}</ul>
    <h3 class="detail-sub">Preparazione</h3>
    ${preparazione}
    ${contesto.conflicts?.length ? `<p class="detail-unsafe">⚠️ Contiene: ${contesto.conflicts.map(esc).join(', ')}</p>` : ''}
    ${r.source ? `<p class="detail-source muted">Fonte: ${esc(r.source)}</p>` : ''}
    <div class="modal-foot">
      ${contesto.onRemove ? '<button id="rd-remove">Rimuovi dal piano</button>' : ''}
      <button class="primary" id="rd-edit">Modifica</button>
    </div>
  `);

  $('#rd-edit').addEventListener('click', () => recipeForm(r));
  if (contesto.onRemove) {
    $('#rd-remove').addEventListener('click', async () => {
      hideModal();
      await contesto.onRemove();
    });
  }
}

/* Foto disponibili in static/recipes/, caricate all'avvio. */
let photoFiles = [];
function photoOptions(selezionata) {
  const opts = ['<option value="">Nessuna foto</option>'];
  for (const f of photoFiles) {
    opts.push(`<option value="${esc(f)}" ${f === selezionata ? 'selected' : ''}>${esc(f)}</option>`);
  }
  // la foto della ricetta puo' non essere piu' sul disco: va comunque mostrata
  if (selezionata && !photoFiles.includes(selezionata)) {
    opts.push(`<option value="${esc(selezionata)}" selected>${esc(selezionata)}</option>`);
  }
  return opts.join('');
}

/** Prima di aprire il modulo di una ricetta nuova, chiede come farla.

    Scrivere una ricetta a mano e farsela cercare online sono due strade diverse,
    e il modulo è identico: senza questa domanda l'app imboccherebbe sempre la
    prima, anche a chi aveva in mente la seconda. La domanda arriva sia dal
    pulsante «+ Nuova ricetta» sia dalla voce («crea la ricetta carbonara»), che
    è il caso in cui il nome è già noto: chi lo ha dettato lo ritrova scritto.
*/
function nuovaRicetta(nomeIniziale, ingredientiIniziali) {
  const nome = (nomeIniziale || '').trim();
  const ingredienti = ingredientiIniziali || [];
  showModal('Nuova ricetta', `
    <p class="hint">${nome ? `«${esc(nome)}»: come vuoi farla?` : 'Come vuoi farla?'}</p>
    ${ingredienti.length ? `<p class="hint">Gli ingredienti che hai detto sono già
      nel modulo: ${ingredienti.map((i) => esc(i.name)).join(', ')}.</p>` : ''}
    <div class="modal-foot">
      <button id="ric-scrivi">✍️ La scrivo io</button>
      <button id="ric-cerca" class="primary">🔎 Cercala online</button>
    </div>
  `);
  // scrivendola a mano si ritrovano le dosi appena dette; cercandola online no,
  // perché gli ingredienti arrivano dal sito e sostituirebbero quelli
  $('#ric-scrivi').addEventListener('click', () => recipeForm(null, nome, ingredienti));
  $('#ric-cerca').addEventListener('click', () => cercaRicettaOnline(nome));
}

/** Cerca una ricetta online e, scelta quella giusta, apre il modulo compilato.

    Il modulo resta il passaggio obbligato: la ricetta trovata arriva scritta nei
    campi, ma e' l'utente a salvarla. I dati di un altro sito entrano cosi' in
    archivio solo dopo un'occhiata, e le dosi storte si correggono prima che
    finiscano in dispensa. */
function cercaRicettaOnline(nomeIniziale) {
  showModal('Cercala online', `
    <div class="field"><label>Cosa cerco</label>
      <div class="row">
        <input id="ric-q" value="${esc(nomeIniziale || '')}" placeholder="per esempio carbonara">
        <button id="ric-cerca-avvia" class="primary">Cerca</button>
      </div>
      <p class="hint">Le ricette arrivano da un sito esterno. Dosi e passi li
      riporta il sito: controllali prima di salvare.</p>
    </div>
    <div id="ric-risultati"></div>
  `);
  $('#ric-cerca-avvia').addEventListener('click', () => avviaRicercaRicetta());
  $('#ric-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') avviaRicercaRicetta(); });
  if (nomeIniziale) avviaRicercaRicetta();
}

async function avviaRicercaRicetta() {
  const q = $('#ric-q').value.trim();
  const box = $('#ric-risultati');
  if (!q) return toast('Scrivi cosa cercare');
  box.innerHTML = '<p class="hint">Cerco…</p>';
  try {
    const d = await api(`/api/ricette/cerca?q=${encodeURIComponent(q)}`);
    if (!d.risultati.length) {
      box.innerHTML = `<p class="hint">Nessuna ricetta trovata per «${esc(q)}».</p>`;
      return;
    }
    box.innerHTML = `<div class="ric-trovate">${d.risultati.map((r, i) => `
      <button class="ric-trovata" data-i="${i}">
        <span>${esc(r.titolo)}</span><span class="ric-fonte">${esc(d.sito)}</span>
      </button>`).join('')}</div>`;
    $$('.ric-trovata', box).forEach((b) => b.addEventListener('click', () =>
      importaRicetta(d.risultati[Number(b.dataset.i)].url)));
  } catch (err) {
    box.innerHTML = `<p class="hint">${esc(err.message)}</p>`;
  }
}

async function importaRicetta(url) {
  const box = $('#ric-risultati');
  box.innerHTML = '<p class="hint">Leggo la ricetta…</p>';
  try {
    const r = await api(`/api/ricette/importa?url=${encodeURIComponent(url)}`);
    recipeForm(null, r.name);
    // i campi del modulo appena aperto si riempiono con quello che il sito dice
    $('#r-serv').value = r.servings || 2;
    $('#r-time').value = r.time_minutes ?? '';
    $('#r-instr').value = r.instructions || '';
    $('#r-source').textContent = r.source || '';
    $('#r-source-field').hidden = !r.source;
    const rows = $('#ing-rows');
    rows.innerHTML = '';
    (r.items.length ? r.items : [{}]).forEach((it) => {
      const div = document.createElement('div');
      div.className = 'ing-row';
      div.innerHTML = `<input placeholder="Ingrediente" value="${esc(it.name || '')}" list="ingredient-list">
        <input type="number" step="0.1" placeholder="Qtà" value="${it.quantity ?? ''}">
        <input placeholder="Unità" value="${esc(it.unit || 'pz')}" list="unit-list">`;
      rows.appendChild(div);
    });
    toast('Ricetta importata: controllala e salva');
  } catch (err) {
    toast(err.message);
    box.innerHTML = `<p class="hint">${esc(err.message)}</p>`;
  }
}

function recipeForm(recipe, nomeIniziale, ingredientiIniziali) {
  const r = recipe || { name: nomeIniziale || '', servings: 2, time_minutes: '', difficulty: 'facile', instructions: '', items: ingredientiIniziali || [] };
  showModal(recipe ? 'Modifica ricetta' : 'Nuova ricetta', `
    <div class="field"><label>Nome</label><input id="r-name" value="${esc(r.name)}"></div>
    <div class="row" style="margin-bottom:12px">
      <input id="r-serv" type="number" min="1" value="${r.servings}" title="Porzioni">
      <input id="r-time" type="number" min="0" value="${r.time_minutes ?? ''}" placeholder="Minuti">
      <select id="r-diff">${['facile', 'media', 'difficile'].map((d) => `<option ${d === r.difficulty ? 'selected' : ''}>${d}</option>`).join('')}</select>
    </div>
    <div class="field"><label>Ingredienti</label><div id="ing-rows"></div>
      <button id="ing-add">+ ingrediente</button></div>
    <div class="field"><label>Preparazione</label><textarea id="r-instr">${esc(r.instructions)}</textarea></div>
    <div class="field">
      <label>Foto (facoltativa)</label>
      <div class="photo-field">
        <img id="r-photo-preview" alt="" ${r.image ? `src="/static/recipes/${encodeURIComponent(r.image)}"` : 'hidden'}>
        <div class="photo-controls">
          <select id="r-photo">${photoOptions(r.image)}</select>
          <input id="r-photo-credit" placeholder="Credito (autore, licenza, fonte)"
                 value="${esc(r.image_credit || '')}">
          <button id="r-photo-clear" ${r.image ? '' : 'hidden'}>Togli la foto</button>
        </div>
      </div>
    </div>
    <div class="field" id="r-source-field" ${r.source ? '' : 'hidden'}>
      <label>Fonte</label>
      <div class="muted" id="r-source">${esc(r.source || '')}</div>
    </div>
    <div class="modal-foot"><button class="primary" id="r-save">Salva</button></div>
  `);

  const rowsBox = $('#ing-rows');
  const addRow = (it = { name: '', quantity: '', unit: 'pz' }) => {
    const div = document.createElement('div');
    div.className = 'ing-row';
    // gli ingredienti dettati possono non avere unità ("4 uova"): il campo
    // vuoto verrebbe scritto "null" e l'utente vedrebbe un valore inventato
    div.innerHTML = `<input placeholder="Ingrediente" value="${esc(it.name || '')}" list="ingredient-list">
      <input type="number" step="0.1" placeholder="Qtà" value="${it.quantity ?? ''}">
      <input placeholder="Unità" value="${esc(it.unit || 'pz')}" list="unit-list">`;
    rowsBox.appendChild(div);
  };
  (r.items.length ? r.items : [{}]).forEach(addRow);
  $('#ing-add').addEventListener('click', () => addRow());

  // anteprima della foto: si aggiorna scegliendo dal menu o togliendola
  const preview = $('#r-photo-preview');
  const creditBox = $('#r-photo-credit');
  const clearBtn = $('#r-photo-clear');
  const aggiornaFoto = () => {
    const scelta = $('#r-photo').value;
    if (scelta) {
      preview.src = `/static/recipes/${encodeURIComponent(scelta)}`;
      preview.hidden = false;
      clearBtn.hidden = false;
    } else {
      preview.removeAttribute('src');
      preview.hidden = true;
      clearBtn.hidden = true;
    }
  };
  $('#r-photo').addEventListener('change', aggiornaFoto);
  clearBtn.addEventListener('click', () => {
    $('#r-photo').value = '';
    creditBox.value = '';
    aggiornaFoto();
  });

  $('#r-save').addEventListener('click', async () => {
    const items = $$('.ing-row', rowsBox).map((row) => {
      const [n, q, u] = $$('input', row);
      return { name: n.value.trim(), quantity: Number(q.value) || 0, unit: u.value.trim() || 'pz' };
    }).filter((i) => i.name);
    const body = {
      name: $('#r-name').value.trim(),
      servings: Number($('#r-serv').value) || 2,
      time_minutes: $('#r-time').value ? Number($('#r-time').value) : null,
      difficulty: $('#r-diff').value,
      instructions: $('#r-instr').value,
      image: $('#r-photo').value,
      image_credit: $('#r-photo-credit').value.trim(),
      source: $('#r-source').textContent.trim(),
      items,
    };
    if (!body.name) return toast('Il nome è obbligatorio');
    try {
      await api(recipe ? `/api/recipes/${recipe.id}` : '/api/recipes',
        { method: recipe ? 'PUT' : 'POST', body });
      hideModal();
      toast('Ricetta salvata');
      renderRecipes();
      loadIngredientsDatalist();
    } catch (err) { toast(err.message); }
  });
}

/* ---------- DISPENSA ---------- */

/* Icone degli alimenti.
   Un'icona dice a colpo d'occhio di cosa si tratta: in una lista lunga si
   riconosce "farina" dal simbolo prima ancora di leggerlo. Non c'e' un'icona
   per ogni alimento possibile, quindi si cerca per parola e si ripiega sulla
   categoria: meglio l'icona della categoria che nessuna icona.
   Le voci sono in minuscolo e l'ordine conta: "olio di semi" deve trovare
   "olio" prima di "semi". */
const ICONE_CATEGORIA = {
  'Frutta e Verdura': '🥬',
  'Carne e Pesce': '🥩',
  'Latticini': '🧀',
  'Dispensa': '🫙',
  'Pane e Cereali': '🌾',
  'Bevande': '🥤',
  'Dolci': '🍰',
  'Surgelati': '❄️',
  'Altro': '📦',
};

const ICONE_PAROLA = [
  ['farina', '🌾'], ['pasta', '🍝'], ['spaghett', '🍝'], ['lasagn', '🍝'],
  ['penne', '🍝'], ['rigaton', '🍝'], ['fusill', '🍝'], ['tagliatell', '🍝'],
  ['riso', '🍚'], ['risotto', '🍚'], ['pane', '🍞'], ['pancarr', '🍞'],
  ['grissin', '🥖'], ['cracker', '🥖'], ['polenta', '🌽'], ['mais', '🌽'],
  ['pomodor', '🍅'], ['passata', '🍅'], ['pelati', '🍅'], ['concentrat', '🥫'],
  ['aglio', '🧄'], ['cipoll', '🧅'], ['scalogn', '🧅'], ['patat', '🥔'],
  ['carota', '🥕'], ['zucchin', '🥒'], ['cetriol', '🥒'], ['melanzan', '🍆'],
  ['peperon', '🫑'], ['insalat', '🥬'], ['spinac', '🥬'], ['verz', '🥬'],
  ['cavol', '🥬'], ['broccol', '🥦'], ['fungh', '🍄'], ['limon', '🍋'],
  ['arancia', '🍊'], ['mela', '🍎'], ['pera', '🍐'], ['banan', '🍌'],
  ['fragol', '🍓'], ['uva', '🍇'], ['pesca', '🍑'], ['anguria', '🍉'],
  ['basilic', '🌿'], ['prezzemol', '🌿'], ['rosmarin', '🌿'], ['salvia', '🌿'],
  ['timo', '🌿'], ['origano', '🌿'], ['menta', '🌿'], ['alloro', '🌿'],
  ['olio', '🫒'], ['oliv', '🫒'], ['aceto', '🧴'],
  ['sale', '🧂'], ['pepe', '🧂'], ['spezi', '🧂'], ['curcuma', '🧂'],
  ['zenzero', '🧂'], ['noce moscata', '🧂'], ['zafferan', '🧂'],
  ['zuccher', '🍬'], ['miele', '🍯'], ['marmellat', '🍯'], ['confettur', '🍯'],
  ['cioccolat', '🍫'], ['cacao', '🍫'], ['biscott', '🍪'], ['dolc', '🍰'],
  ['torta', '🍰'], ['lievit', '🥐'],
  ['uov', '🥚'], ['latte', '🥛'], ['burro', '🧈'], ['panna', '🥛'],
  ['yogurt', '🥛'], ['formagg', '🧀'], ['parmigian', '🧀'], ['pecorin', '🧀'],
  ['mozzarell', '🧀'], ['ricott', '🧀'], ['gorgonzol', '🧀'], ['grana', '🧀'],
  ['manzo', '🥩'], ['macinat', '🥩'], ['carne', '🥩'], ['pollo', '🍗'],
  ['tacchino', '🍗'], ['salsicc', '🥓'], ['guancial', '🥓'], ['pancett', '🥓'],
  ['prosciutt', '🥓'], ['salame', '🥓'], ['speck', '🥓'], ['bresaol', '🥓'],
  ['pesce', '🐟'], ['tonno', '🐟'], ['salmone', '🐟'], ['merluzz', '🐟'],
  ['gamber', '🦐'], ['vongol', '🦪'], ['cozze', '🦪'], ['calamar', '🦑'],
  ['brodo', '🥣'], ['legum', '🫘'], ['fagiol', '🫘'], ['ceci', '🫘'],
  ['lenticch', '🫘'], ['pisell', '🫛'], ['frutta secca', '🥜'], ['mandorl', '🥜'],
  ['noci', '🥜'], ['nocciol', '🥜'], ['arachid', '🥜'], ['pinol', '🥜'],
  ['acqua', '💧'], ['vino', '🍷'], ['birra', '🍺'], ['succo', '🧃'],
  ['caffe', '☕'], ['caffè', '☕'], ['tisana', '🍵'],
  ['gelato', '🍨'], ['surgelat', '❄️'],
  ['sapone', '🧼'], ['deter', '🧴'], ['candeggina', '🧴'],
  ['shampoo', '🧴'], ['spugna', '🧽'], ['carta igienic', '🧻'],
  ['scotch', '📎'], ['pile', '🔋'], ['lampadin', '💡'], ['candela', '🕯️'],
  ['irrigator', '🚿'], ['attrez', '🔧'], ['vite', '🔩'], ['chiod', '🔨'],
];

/* Parole che valgono solo da sole, mai dentro un'altra.
   "te" sta dentro "de-te-rsivo" e "de-te-rgente": cercandolo come parte di una
   parola, il detersivo prendeva l'icona della tazza di te'. Da sole invece
   servono: "te" e "te nero" sono bevande. Qui la ricerca e' sulla parola intera,
   tutto il resto sulla parte di parola ("pomodor" trova "pomodori"). */
const ICONE_PAROLA_INTERA = ['te', 'tè', 'the'].map(
  (p) => [new RegExp(`(^|[^a-zàèéìòù])${p}([^a-zàèéìòù]|$)`, 'i'), '🍵'],
);

/** L'icona di un alimento: per parola del nome, altrimenti per categoria. */
function iconaAlimento(nome, categoria) {
  const n = (nome || '').toLowerCase();
  // prima le parole che valgono da sole, poi quelle che valgono anche in parte
  for (const [espressione, icona] of ICONE_PAROLA_INTERA) {
    if (espressione.test(n)) return icona;
  }
  for (const [parola, icona] of ICONE_PAROLA) {
    if (n.includes(parola)) return icona;
  }
  return ICONE_CATEGORIA[categoria] || '📦';
}

async function renderPantry() {
  const items = await api('/api/pantry');
  const q = $('#pantry-search').value.toLowerCase();
  const list = items.filter((i) => i.name.toLowerCase().includes(q));
  $('#pantry-table tbody').innerHTML = list.map((i) => `
    <tr>
      <td data-label="Ingrediente">
        <span class="riga-alimento">
          <span class="icona-alimento" aria-hidden="true">${iconaAlimento(i.name, i.category)}</span>
          <span class="nome-alimento">${esc(i.name)}</span>
        </span>
      </td>
      <td data-label="Categoria">${esc(i.category)}</td>
      <td data-label="Quantità"><input type="number" step="0.1" value="${i.quantity}" data-qty="${i.id}" class="qty-cell"> ${esc(i.unit)}</td>
      <td><button data-del="${i.id}" title="Togli dalla dispensa" aria-label="Togli ${esc(i.name)} dalla dispensa">🗑</button></td>
    </tr>`).join('') || '<tr><td colspan="4">Dispensa vuota</td></tr>';
}

$('#pantry-search').addEventListener('input', renderPantry);

$('#pantry-table').addEventListener('change', async (e) => {
  const id = e.target.dataset.qty;
  if (id) { await api(`/api/pantry/${id}`, { method: 'PATCH', body: { quantity: Number(e.target.value) } }); toast('Aggiornato'); }
});
$('#pantry-table').addEventListener('click', async (e) => {
  const id = e.target.dataset.del;
  if (id) { await api(`/api/pantry/${id}`, { method: 'DELETE' }); renderPantry(); }
});

$('#pantry-add').addEventListener('click', async () => {
  const name = $('#pantry-name').value.trim();
  if (!name) return toast('Inserisci un ingrediente');
  await api('/api/pantry', {
    method: 'POST',
    body: { name, quantity: Number($('#pantry-qty').value) || 0, unit: $('#pantry-unit').value.trim() || 'pz' },
  });
  $('#pantry-name').value = '';
  toast('Aggiunto alla dispensa');
  renderPantry();
  loadIngredientsDatalist();
});

/* ---------- SPESA ---------- */
/**
 * Giacenza in dispensa per una voce di lista, o '' se non c'è.
 * La quantità in lista è già al netto della dispensa: qui si dichiara solo
 * quanto c'è in casa, senza suggerire di saltare l'acquisto.
 */
function pantryNote(pantry) {
  if (!pantry) return '';
  const qty = `${pantry.quantity} ${esc(pantry.unit)}`;
  return `<span class="pantry-note" title="Sottratta dalla quantità da comprare">` +
         `in dispensa: ${qty}</span>`;
}

/* giorno della spesa: null = tutti, altrimenti 'aaaa-mm-gg' */
let shopDay = null;
let shopItems = [];

async function renderShopping() {
  // si carica sempre la lista completa: i giorni noti servono a costruire i
  // pulsanti, e filtrando lato server gli altri giorni sparirebbero dal filtro
  shopItems = await api('/api/shopping');
  renderShopDays();
  const items = shopItems.filter((i) => visibleInDay(i));
  const groups = {};
  items.forEach((i) => (groups[i.category] = groups[i.category] || []).push(i));
  $('#shop-list').innerHTML = Object.entries(groups).map(([cat, list]) => `
    <div class="shop-group">
      <h3>${esc(cat)}</h3>
      ${list.map((i) => `
        <div class="shop-item ${i.checked ? 'done' : ''}">
          <input type="checkbox" data-check="${i.id}" ${i.checked ? 'checked' : ''}>
          <span class="name">${esc(i.name)}${pantryNote(i.pantry)}${dayNote(i)}</span>
          <span class="qty">${esc(itemQty(i))}</span>
          <button data-del="${i.id}">🗑</button>
        </div>`).join('')}
    </div>`).join('') || `<p>${shopDay
      ? 'Niente da comprare per questo giorno.'
      : 'Lista vuota. Generala dal piano settimanale o aggiungi voci manualmente.'}</p>`;
  renderPerishHint(items);
}

/* una voce è del giorno se ha una quota in quel giorno; le voci aggiunte a mano,
   che non hanno giorni, restano sempre in elenco */
function visibleInDay(i) {
  if (!shopDay) return true;
  if (!i.days || !i.days.length) return true;
  return i.days.some((d) => d.date === shopDay);
}

function dayQtyOf(i) {
  return (i.days || []).find((d) => d.date === shopDay);
}

/* nel filtro per giorno mostra la quota di quel giorno, se nota */
function itemQty(i) {
  const d = shopDay ? dayQtyOf(i) : null;
  if (d) return `${d.quantity} ${d.unit}`;
  return `${i.quantity} ${i.unit}`;
}

/* in quale giorno serve la voce: con più giorni mostra il primo e quanti sono */
function dayNote(i) {
  if (shopDay || !i.days || !i.days.length) return '';
  const primo = dayShort(i.days[0].date);
  const testo = i.days.length === 1
    ? `serve ${primo}`
    : `serve ${primo} +${i.days.length - 1}`;
  const titolo = i.days.map((d) => `${dayShort(d.date)}: ${d.quantity} ${d.unit}`).join('\n');
  return `<span class="day-note" title="${esc(titolo)}">${esc(testo)}</span>`;
}

function dayShort(iso) {
  const [a, m, g] = iso.split('-').map(Number);
  return new Date(a, m - 1, g).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' });
}

/* giorni che compaiono nella lista, per offrire solo quelli utili */
function renderShopDays() {
  const giorni = new Set();
  shopItems.forEach((i) => (i.days || []).forEach((d) => giorni.add(d.date)));
  const elenco = [...giorni].sort();
  if (!elenco.length) { $('#shop-days').innerHTML = ''; return; }
  const bottoni = [`<button data-day="" class="${shopDay ? '' : 'active'}">Tutti</button>`]
    .concat(elenco.map((g) =>
      `<button data-day="${g}" class="${shopDay === g ? 'active' : ''}">${esc(dayShort(g))}</button>`));
  $('#shop-days').innerHTML = bottoni.join('');
}

/* avviso sui freschi: comprare in anticipo li fa deperire */
function renderPerishHint(items) {
  const freschi = items.filter((i) => i.perishable && !i.checked);
  const hint = $('#shop-hint');
  if (!freschi.length) { hint.hidden = true; return; }
  hint.hidden = false;
  hint.textContent = shopDay
    ? `🧊 ${freschi.length} voci deperibili in questo giorno: comprale il giorno stesso se puoi.`
    : `🧊 ${freschi.length} voci deperibili (frutta e verdura, carne e pesce, latticini): ` +
      `comprale più vicino al giorno in cui servono, non tutte a inizio settimana.`;
}

$('#shop-days').addEventListener('click', (e) => {
  const g = e.target.dataset.day;
  if (g === undefined) return;
  shopDay = g || null;
  renderShopping();
});

$('#shop-list').addEventListener('click', async (e) => {
  const cid = e.target.dataset.check;
  const did = e.target.dataset.del;
  if (cid) { await api(`/api/shopping/${cid}`, { method: 'PATCH', body: { checked: e.target.checked } }); renderShopping(); }
  if (did) { await api(`/api/shopping/${did}`, { method: 'DELETE' }); renderShopping(); }
});

$('#shop-clear').addEventListener('click', async () => {
  await api('/api/shopping/clear-checked', { method: 'POST' });
  toast('Spuntati rimossi');
  renderShopping();
});

$('#shop-add').addEventListener('click', async () => {
  const name = $('#shop-name').value.trim();
  if (!name) return toast('Inserisci un prodotto');
  await api('/api/shopping', {
    method: 'POST',
    body: {
      name, quantity: Number($('#shop-qty').value) || 1,
      unit: $('#shop-unit').value.trim() || 'pz', category: $('#shop-cat').value,
    },
  });
  $('#shop-name').value = '';
  toast('Aggiunto alla spesa');
  renderShopping();
  loadIngredientsDatalist();
});

/* ---------- IGIENE ----------
   Il metodo e' quello del calendario mensile delle pulizie: tre blocchi per
   frequenza (ogni giorno, ogni settimana, ogni mese) piu' un calendario annuale
   con un focus per mese. La pagina apre su cosa c'e' da fare adesso.

   Le attivita' con una scadenza vera (settimanali, mensili, annuali) hanno un
   pulsante per il tempo; le quotidiane no, sono da pochi minuti e cronometrarle
   sarebbe piu' lavoro della pulizia. */

let chDati = null;       // { oggi, attivita, piano, attive }
let chMeta = null;       // { frequencies, areas, days, months, chore_day }
let chSummary = null;

// il tempo si formatta in minuti finche' e' poco, poi in ore: "2 h 10 min" si
// legge subito, "130 min" no
function durata(minuti) {
  const m = Math.max(0, Math.round(minuti || 0));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto ? `${h} h ${resto} min` : `${h} h`;
}

// quando e' stata fatta l'ultima volta, in parole: piu' utile di una data secca
function quandoDetto(voce) {
  // fatto oggi viene prima di tutto: per una quotidiana `giorni` vale 1 (domani
  // tocca di nuovo) e senza questo controllo la riga direbbe "rifare fra 1
  // giorno" appena spuntata, che suona come se non fosse stata registrata
  if (voce.fatto_oggi) return 'fatta oggi';
  if (voce.mai_fatta) return 'mai fatta';
  if (voce.giorni === null) return `ultima volta il ${voce.ultima}`;
  if (voce.giorni > 0) return `rifare fra ${voce.giorni} ${voce.giorni === 1 ? 'giorno' : 'giorni'}`;
  const r = -voce.giorni;
  return `in ritardo di ${r} ${r === 1 ? 'giorno' : 'giorni'}`;
}

async function renderIgiene() {
  if (!chMeta) chMeta = await api('/api/chores/meta');
  chDati = await api('/api/chores');
  chSummary = await api('/api/chores/summary');
  riempiGiorno();
  renderOggi();
  renderRoutine();
  renderAnno();
  renderChoreList();
}

function riempiGiorno() {
  const sel = $('#ch-day');
  if (sel.options.length) { sel.value = String(chMeta.chore_day); return; }
  sel.innerHTML = chMeta.days.map((d) =>
    `<option value="${d.key}">${esc(d.label)}</option>`).join('');
  sel.value = String(chMeta.chore_day);
}

/* --- cosa c'e' da fare adesso --- */
function renderOggi() {
  const p = chDati.piano;
  const fatto = p.fatto_oggi;
  const totale = p.da_fare + fatto;

  const testa = `
    <div class="ch-hero">
      <div>
        <div class="ch-hero-day">${esc(p.giorno)} ${esc(p.data)}</div>
        <div class="ch-hero-num">
          ${p.da_fare === 0
            ? '<strong>Fatto tutto</strong><span>per oggi non resta niente</span>'
            : `<strong>${p.da_fare}</strong><span>${p.da_fare === 1 ? 'attività da fare' : 'attività da fare'}</span>`}
        </div>
      </div>
      <div class="ch-hero-time">
        ${p.da_fare === 0 ? '' : `<span class="ch-hero-min">${durata(p.minuti_previsti)}</span>
        <span class="ch-hero-min-lab">tempo stimato</span>`}
        ${fatto ? `<span class="ch-hero-done">${fatto}/${totale} già fatte</span>` : ''}
      </div>
    </div>
    ${p.giorno_pulizie ? '<p class="ch-pill">Oggi è il giorno delle pulizie</p>' : ''}`;

  const blocco = (nome, elenco) => {
    if (!elenco.length) return '';
    return `<h4 class="ch-sub">${esc(nome)}</h4>
      <ul class="ch-todo">${elenco.map(choreRiga).join('')}</ul>`;
  };

  // la settimana distribuita: mostra che le settimanali non sono tutte oggi, ed
  // e' il modo per sapere in che giorno tocca ognuna
  const settimana = `
    <div class="ch-week" title="Come sono distribuite le attività della settimana">
      ${p.settimana.map((g) => `
        <div class="ch-week-day${g.oggi ? ' oggi' : ''}${g.minuti ? '' : ' vuoto'}">
          <span class="ch-week-nome">${esc(g.nome.slice(0, 3))}</span>
          <span class="ch-week-min">${g.minuti ? durata(g.minuti) : '—'}</span>
        </div>`).join('')}
    </div>`;

  $('#ch-oggi').innerHTML = testa + settimana
    + blocco('Ogni giorno', p.gruppi.quotidiane)
    + blocco('Ogni settimana', p.gruppi.settimanali);

  const m = p.mese;
  if (m.mensili.length || m.stagionali.length) {
    const html = `
      <div class="ch-month">
        <div class="ch-month-head">
          <h4 class="ch-sub">${esc(m.nome)}${m.titolo ? ` · ${esc(m.titolo)}` : ''}</h4>
          <span class="ch-month-lab">nel mese: ${p.mese_da_fare} attività · ${durata(p.mese_minuti)}</span>
        </div>
        ${m.focus ? `<p class="ch-focus">${esc(m.focus)}</p>` : ''}
        <ul class="ch-todo">
          ${[...m.mensili, ...m.stagionali].map((v) => choreRiga(v)).join('')}
        </ul>
      </div>`;
    $('#ch-oggi').insertAdjacentHTML('beforeend', html);
  }
}

/* Una riga di attività da spuntare. `timer` abilita il pulsante del tempo:
   ha senso solo dove la scadenza conta. `giorno` aggiunge il giorno assegnato,
   per le settimanali: la riga ha gia' cinque colonne fisse, quindi il giorno
   entra nella colonna dello stato invece di aggiungerne una sesta, che sul
   telefono non entrerebbe. */
function choreRiga(v, timer = true, giorno = false) {
  const quando = giorno && v.giorno_settimanale_nome
    ? (v.giorno_settimanale_oggi ? 'oggi' : `tocca ${v.giorno_settimanale_nome}`)
    : quandoDetto(v);
  return `
    <li class="ch-row${v.fatto_oggi ? ' done' : ''}" data-chore="${v.id}">
      <button class="ch-check" data-done="${v.id}" title="${v.fatto_oggi ? 'Fatta oggi, clicca per annullare' : 'Segna come fatta'}">
        ${v.fatto_oggi ? '✓' : '○'}
      </button>
      <span class="ch-name">${esc(v.name)}</span>
      <span class="ch-area">${esc(v.area)}</span>
      <span class="ch-when${giorno ? ' ch-giorno' : ''}">${esc(quando)}</span>
      <span class="ch-min">${durata(v.minutes)}</span>
      ${timer && !v.fatto_oggi
        ? `<button class="ch-clock" data-timer="${v.id}" title="Cronometra">⏱</button>` : ''}
    </li>`;
}

/* --- routine: il catalogo di quotidiane e settimanali ---
   Le settimanali portano il giorno assegnato accanto al nome: la distribuzione
   sui giorni e' invisibile senza, e una voce che non tocca oggi sembrerebbe
   sparita dall'elenco invece che spostata. */
function renderRoutine() {
  const di = (f) => chDati.attivita.filter((v) => v.active && v.frequency === f);
  const sezione = (titolo, elenco, nota, giorno) => `
    <div class="ch-block">
      <h4 class="ch-sub">${esc(titolo)} <span class="ch-hint">${esc(nota)}</span></h4>
      <ul class="ch-todo">${elenco.map((v) => choreRiga(v, true, giorno)).join('')}</ul>
    </div>`;
  $('#ch-routine').innerHTML =
    sezione('Ogni giorno', di('giornaliera'), 'pochi minuti, tengono la casa in ordine', false) +
    sezione('Ogni settimana', di('settimanale'), 'uno o due al giorno, non tutte insieme', true);
}

/* --- calendario dell'anno: un mese per riga, con il suo focus ---
   Il mese corrente e' evidenziato ma chiuso: le sue attivita' sono gia' elencate
   per intero nel blocco qui sopra, e ripeterle due volte nella stessa schermata
   confonde invece di aiutare. */
function renderAnno() {
  const anno = chDati.piano.data.slice(0, 4);
  const meseCorrente = Number(chDati.piano.data.slice(5, 7));

  $('#ch-year').innerHTML = chMeta.months.map((m) => {
    const voci = chDati.attivita
      .filter((v) => v.active && v.frequency === 'stagionale' && v.month === m.mese);
    const fatte = voci.filter((v) => v.ultima && v.ultima.slice(0, 4) === anno).length;
    const cls = m.mese === meseCorrente ? ' current' : '';
    return `
      <details class="ch-month-card${cls}">
        <summary>
          <span class="ch-month-name">${esc(m.nome)}</span>
          <span class="ch-month-title">${esc(m.titolo)}</span>
          <span class="ch-month-count">${fatte}/${voci.length}</span>
        </summary>
        <p class="ch-focus">${esc(m.focus)}</p>
        <ul class="ch-todo">${voci.map((v) => choreRiga(v)).join('')}</ul>
      </details>`;
  }).join('');
}

/* --- catalogo completo, per modificare e disattivare --- */
function renderChoreList() {
  const label = (k) => (chMeta.frequencies.find((f) => f.key === k) || {}).label || k;
  const gruppi = {};
  chDati.attivita.forEach((v) => (gruppi[v.frequency] = gruppi[v.frequency] || []).push(v));
  const ordine = ['giornaliera', 'settimanale', 'mensile', 'stagionale'];

  $('#ch-count').textContent = `${chDati.attive} attività attive su ${chDati.attivita.length}`;
  $('#ch-list').innerHTML = ordine.filter((k) => gruppi[k]).map((k) => `
    <h4 class="ch-sub">${esc(label(k))}</h4>
    <ul class="ch-catalog">${gruppi[k].map((v) => `
      <li class="ch-cat-row${v.active ? '' : ' off'}">
        <span class="ch-name">${esc(v.name)}</span>
        <span class="ch-area">${esc(v.area)}</span>
        ${v.month ? `<span class="ch-month-tag">${esc(chMeta.months[v.month - 1].nome)}</span>` : ''}
        <span class="ch-min">${durata(v.minutes)}</span>
        <button class="ghost ch-edit" data-edit="${v.id}">Modifica</button>
        <button class="ghost ch-toggle" data-toggle="${v.id}">${v.active ? 'Disattiva' : 'Riattiva'}</button>
      </li>`).join('')}</ul>`).join('');
}

/* --- timer ---
   Il tempo parte da un timestamp salvato, non da un contatore in memoria: cosi'
   il cronometro continua anche se la pagina viene ricaricata o il telefono si
   blocca, che e' esattamente quello che succede mentre si pulisce.

   `fine` esiste solo per la regola dei 15 minuti: li' il tempo e' un limite, non
   una misura, quindi si mostra quanto manca e si avvisa quando e' scaduto. */
const CH_TIMER_KEY = 'choreTimer';

function timerAvviato() {
  try { return JSON.parse(localStorage.getItem(CH_TIMER_KEY)); } catch { return null; }
}

function avviaTimer(id, nome, minuti) {
  const inizio = Date.now();
  const t = { id, nome, inizio };
  if (minuti) t.fine = inizio + minuti * 60000;
  localStorage.setItem(CH_TIMER_KEY, JSON.stringify(t));
  mostraTimer();
  toast(minuti ? `${minuti} minuti su ${nome}` : `Timer avviato: ${nome}`);
}

function mostraTimer() {
  const t = timerAvviato();
  $('#ch-timer').classList.toggle('hidden', !t);
  if (!t) { clearInterval(mostraTimer._i); return; }
  $('#ch-timer-what').textContent = t.nome;
  const orologio = $('#ch-timer-clock');

  const tick = () => {
    const ora = Date.now();
    if (t.fine) {
      const resta = Math.round((t.fine - ora) / 1000);
      if (resta <= 0) {
        orologio.textContent = 'tempo scaduto';
        $('#ch-timer').classList.add('scaduto');
        return;
      }
      $('#ch-timer').classList.remove('scaduto');
      const m = Math.floor(resta / 60);
      orologio.textContent = `${m}:${String(resta % 60).padStart(2, '0')}`;
      return;
    }
    const sec = Math.floor((ora - t.inizio) / 1000);
    orologio.textContent = `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  };
  tick();
  clearInterval(mostraTimer._i);
  mostraTimer._i = setInterval(tick, 1000);
}

function fermaTimer() {
  localStorage.removeItem(CH_TIMER_KEY);
  clearInterval(mostraTimer._i);
  $('#ch-timer').classList.add('hidden');
  $('#ch-timer').classList.remove('scaduto');
}

$('#ch-timer-cancel').addEventListener('click', fermaTimer);

$('#ch-timer-done').addEventListener('click', async () => {
  const t = timerAvviato();
  if (!t) return;
  // nella regola dei 15 minuti il tempo e' un tetto: si registra quello usato
  // davvero, che puo' essere meno, e non i 15 minuti interi
  const passati = (Date.now() - t.inizio) / 60000;
  const minuti = Math.max(1, Math.round(t.fine ? Math.min(passati, (t.fine - t.inizio) / 60000) : passati));
  await api(`/api/chores/${t.id}/done`, { method: 'POST', body: { minutes: minuti } });
  fermaTimer();
  toast(`Fatto in ${durata(minuti)}`);
  renderIgiene();
});

/* La regola dei 15 minuti: quando non c'e' tempo per la giornata intera si
   sceglie una zona sola e le si dedicano quindici minuti. Si prende la prima
   attivita' ancora da fare, cosi' il pulsante fa qualcosa di sensato senza
   chiedere nient'altro. */
$('#ch-blitz').addEventListener('click', () => {
  const prime = chDati.piano.gruppi.quotidiane
    .concat(chDati.piano.gruppi.settimanali, chDati.piano.mese.mensili, chDati.piano.mese.stagionali)
    .filter((v) => !v.fatto_oggi);
  if (!prime.length) return toast('Non resta niente da fare');
  avviaTimer(prime[0].id, prime[0].name, 15);
  switchTab('igiene');
});

/* --- azioni sulle attività --- */
$('#ch-oggi').addEventListener('click', choreClick);
$('#ch-routine').addEventListener('click', choreClick);
$('#ch-year').addEventListener('click', choreClick);

async function choreClick(e) {
  const t = e.target.closest('[data-timer]');
  if (t) {
    const v = chDati.attivita.find((x) => x.id === Number(t.dataset.timer));
    avviaTimer(v.id, v.name);
    return;
  }
  const d = e.target.closest('[data-done]');
  if (!d) return;
  const id = Number(d.dataset.done);
  const v = chDati.attivita.find((x) => x.id === id);
  const fatto = chDati.piano.gruppi.quotidiane.concat(chDati.piano.gruppi.settimanali,
    chDati.piano.mese.mensili, chDati.piano.mese.stagionali).find((x) => x.id === id);
  if (fatto && fatto.fatto_oggi) await api(`/api/chores/${id}/done`, { method: 'DELETE' });
  else await api(`/api/chores/${id}/done`, { method: 'POST', body: {} });
  toast(v && fatto && fatto.fatto_oggi ? 'Completamento annullato' : 'Segnata come fatta');
  renderIgiene();
}

$('#ch-list').addEventListener('click', async (e) => {
  const ed = e.target.closest('[data-edit]');
  if (ed) return apriChoreForm(chDati.attivita.find((x) => x.id === Number(ed.dataset.edit)));
  const tg = e.target.closest('[data-toggle]');
  if (tg) {
    const v = chDati.attivita.find((x) => x.id === Number(tg.dataset.toggle));
    await api(`/api/chores/${v.id}`, { method: 'PUT', body: { active: v.active ? 0 : 1 } });
    toast(v.active ? 'Attività disattivata' : 'Attività riattivata');
    renderIgiene();
  }
});

$('#ch-day').addEventListener('change', async (e) => {
  await api('/api/profile', { method: 'PUT', body: { chore_day: Number(e.target.value) } });
  chMeta.chore_day = Number(e.target.value);
  toast(`Giorno delle pulizie: ${chMeta.days[chMeta.chore_day].label}`);
  renderIgiene();
});

/* --- nuova attività / modifica --- */
function apriChoreForm(v) {
  const freq = (v && v.frequency) || 'settimanale';
  showModal(v ? 'Modifica attività' : 'Nuova attività', `
    <div class="field"><label>Nome</label>
      <input id="chf-name" value="${esc(v ? v.name : '')}" placeholder="Es. Pulire il microonde"></div>
    <div class="field"><label>Ambiente</label>
      <select id="chf-area" class="plain">${chMeta.areas.map((a) =>
        `<option${v && v.area === a ? ' selected' : ''}>${esc(a)}</option>`).join('')}</select></div>
    <div class="field"><label>Ogni quanto</label>
      <select id="chf-freq" class="plain">${chMeta.frequencies.map((f) =>
        `<option value="${f.key}"${freq === f.key ? ' selected' : ''}>${esc(f.label)}</option>`).join('')}</select></div>
    <div class="field" id="chf-month-row"><label>Mese</label>
      <select id="chf-month" class="plain">${chMeta.months.map((m) =>
        `<option value="${m.mese}"${v && v.month === m.mese ? ' selected' : ''}>${esc(m.nome)}</option>`).join('')}</select></div>
    <div class="field"><label>Minuti stimati</label>
      <input id="chf-min" type="number" min="0" step="5" value="${v ? v.minutes : 15}"></div>
    <div class="modal-foot">
      <button id="chf-save" class="primary">${v ? 'Salva' : 'Aggiungi'}</button>
      <button id="chf-cancel">Annulla</button>
    </div>`);

  const aggiornaMese = () => {
    $('#chf-month-row').classList.toggle('hidden', $('#chf-freq').value !== 'stagionale');
  };
  aggiornaMese();
  $('#chf-freq').addEventListener('change', aggiornaMese);
  $('#chf-cancel').addEventListener('click', hideModal);

  $('#chf-save').addEventListener('click', async () => {
    const nome = $('#chf-name').value.trim();
    if (!nome) return toast('Inserisci un nome');
    const corpo = {
      name: nome, area: $('#chf-area').value, frequency: $('#chf-freq').value,
      minutes: Number($('#chf-min').value) || 0,
    };
    if (corpo.frequency === 'stagionale') corpo.month = Number($('#chf-month').value);
    try {
      if (v) await api(`/api/chores/${v.id}`, { method: 'PUT', body: corpo });
      else await api('/api/chores', { method: 'POST', body: corpo });
      hideModal();
      toast(v ? 'Attività salvata' : 'Attività aggiunta');
      renderIgiene();
    } catch (err) { toast(err.message); }
  });
}

$('#ch-new').addEventListener('click', () => apriChoreForm(null));

/* ---------- PROGETTI ----------
   Lavori in corso e idee, fuori dalla cucina. La priorita' e' una scelta
   dell'utente da 1 a 5 stelle e ordina la lista: e' il senso della sezione,
   quindi i conclusi si nascondono invece di mescolarsi agli aperti. */
let progetti = [];

function stelle(n) {
  // la stella piena e' un carattere, non un'immagine: resta nitida a ogni zoom
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

function fmtData(iso) {
  if (!iso) return '';
  const [a, m, g] = iso.split('-');
  return `${g}/${m}/${a}`;
}

function periodoProgetto(p) {
  if (p.start_date && p.end_date) return `${fmtData(p.start_date)} → ${fmtData(p.end_date)}`;
  if (p.start_date) return `dal ${fmtData(p.start_date)}`;
  if (p.end_date) return `entro il ${fmtData(p.end_date)}`;
  return '';
}

async function renderProgetti() {
  const tutti = await api('/api/projects');
  const mostraConclusi = $('#pr-show-done').checked;
  progetti = tutti.filter((p) => mostraConclusi || !p.done);

  if (!progetti.length) {
    $('#pr-list').innerHTML = `<div class="empty-state">
        <span class="empty-emoji">📋</span>
        <h2>${tutti.length ? 'Nessun progetto aperto' : 'Nessun progetto'}</h2>
        <p>${tutti.length
          ? 'Tutti i progetti sono conclusi. Spunta "Mostra conclusi" per rivederli.'
          : 'Aggiungi il primo progetto con data di inizio, fine e priorità.'}</p>
      </div>`;
    return;
  }

  $('#pr-list').innerHTML = progetti.map((p) => `
    <article class="project-card ${p.done ? 'done' : ''}" data-id="${p.id}">
      <div class="project-head">
        <button class="project-check ${p.done ? 'on' : ''}" data-act="done"
          title="${p.done ? 'Riapri' : 'Segna come concluso'}">${p.done ? '✓' : ''}</button>
        <div class="project-main">
          <h3 class="project-title">${esc(p.title)}</h3>
          <div class="project-meta">
            <span class="project-stars" title="Priorità ${p.priority} di 5">${stelle(p.priority)}</span>
            ${periodoProgetto(p) ? `<span class="project-dates">📅 ${periodoProgetto(p)}</span>` : ''}
          </div>
        </div>
        <div class="project-actions">
          <button data-act="edit" title="Modifica">✏️</button>
          <button data-act="del" title="Elimina">🗑️</button>
        </div>
      </div>
      ${p.description ? `<p class="project-desc">${esc(p.description)}</p>` : ''}
    </article>`).join('');
}

$('#pr-list').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const id = Number(btn.closest('.project-card').dataset.id);
  const p = progetti.find((x) => x.id === id);
  if (!p) return;

  if (btn.dataset.act === 'done') {
    await api(`/api/projects/${id}`, { method: 'PUT', body: { done: !p.done } });
    toast(p.done ? 'Progetto riaperto' : 'Progetto concluso');
    renderProgetti();
  } else if (btn.dataset.act === 'edit') {
    apriProgettoForm(p);
  } else if (btn.dataset.act === 'del') {
    if (!confirm(`Eliminare "${p.title}"?`)) return;
    await api(`/api/projects/${id}`, { method: 'DELETE' });
    toast('Progetto eliminato');
    renderProgetti();
  }
});

function apriProgettoForm(p) {
  showModal(p ? 'Modifica progetto' : 'Nuovo progetto', `
    <div class="field"><label>Titolo</label>
      <input id="prf-title" value="${esc(p ? p.title : '')}" placeholder="Es. Sistemare il garage"></div>
    <div class="field"><label>Descrizione</label>
      <textarea id="prf-desc" rows="3" placeholder="Cosa c'è da fare, a grandi linee">${esc(p ? p.description : '')}</textarea></div>
    <div class="row" style="margin-bottom:12px; align-items:flex-end">
      <div class="field" style="flex:1; margin:0"><label>Inizio</label>
        <input id="prf-start" type="date" value="${p ? p.start_date : ''}"></div>
      <div class="field" style="flex:1; margin:0"><label>Fine</label>
        <input id="prf-end" type="date" value="${p ? p.end_date : ''}"></div>
    </div>
    <div class="field"><label>Priorità</label>
      <select id="prf-prio" class="plain">${[5, 4, 3, 2, 1].map((n) =>
        `<option value="${n}"${(p ? p.priority : 3) === n ? ' selected' : ''}>${stelle(n)} (${n})</option>`).join('')}</select></div>
    <div class="modal-foot">
      <button id="prf-save" class="primary">${p ? 'Salva' : 'Aggiungi'}</button>
      <button id="prf-cancel">Annulla</button>
    </div>`);

  $('#prf-cancel').addEventListener('click', hideModal);
  $('#prf-save').addEventListener('click', async () => {
    const corpo = {
      title: $('#prf-title').value.trim(),
      description: $('#prf-desc').value.trim(),
      start_date: $('#prf-start').value,
      end_date: $('#prf-end').value,
      priority: Number($('#prf-prio').value),
    };
    if (!corpo.title) return toast('Inserisci un titolo');
    try {
      if (p) await api(`/api/projects/${p.id}`, { method: 'PUT', body: corpo });
      else await api('/api/projects', { method: 'POST', body: corpo });
      hideModal();
      toast(p ? 'Progetto salvato' : 'Progetto aggiunto');
      renderProgetti();
    } catch (err) { toast(err.message); }
  });
}

$('#pr-new').addEventListener('click', () => apriProgettoForm(null));
$('#pr-show-done').addEventListener('change', renderProgetti);

/* ---------- MAGAZZINO ----------
   Quello che si tiene in casa e non si mangia: sapone, ferramenta, batterie.
   Vive nei Progetti perche' non centra con la cucina: non entra in nessuna
   ricetta e non si scala dal fabbisogno della spesa come fa la dispensa. */
let magazzinoDati = [];
let magazzinoMeta = { categories: [], places: [], default_category: 'Altro', default_place: 'Ripostiglio' };
let magazzinoFiltro = '';

async function renderMagazzino() {
  if (!magazzinoMeta.categories.length) {
    magazzinoMeta = await api('/api/magazzino/meta');
    $('#st-filter').innerHTML = '<option value="">Tutte le categorie</option>' +
      magazzinoMeta.categories.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
  }

  const tutti = await api('/api/storage');
  const q = $('#st-search').value.trim().toLowerCase();
  const soloScarsi = $('#st-low-only').checked;
  magazzinoDati = tutti.filter((v) =>
    (!soloScarsi || v.low) &&
    (!magazzinoFiltro || v.category === magazzinoFiltro) &&
    (!q || v.name.toLowerCase().includes(q) || v.place.toLowerCase().includes(q)));

  const scarsi = tutti.filter((v) => v.low).length;
  $('#st-count').textContent = tutti.length
    ? `${tutti.length} ${tutti.length === 1 ? 'voce' : 'voci'}${scarsi ? ` · ${scarsi} in esaurimento` : ''}`
    : '';

  if (!magazzinoDati.length) {
    $('#st-list').innerHTML = `<div class="empty-state">
        <span class="empty-emoji">📦</span>
        <h2>${tutti.length ? 'Nessun risultato' : 'Magazzino vuoto'}</h2>
        <p>${tutti.length
          ? 'Nessuna voce corrisponde al filtro.'
          : 'Aggiungi quello che tieni in casa e non si mangia: sapone, bricolage, batterie.'}</p>
      </div>`;
    return;
  }

  $('#st-list').innerHTML = magazzinoDati.map((v) => `
    <article class="storage-card ${v.low ? 'low' : ''}" data-id="${v.id}">
      <div class="storage-head">
        ${v.has_photo ? `<img class="storage-thumb" src="${esc(v.photo_url)}" alt=""
             loading="lazy" data-act="edit" title="Vedi la foto">` : ''}
        <div class="storage-main">
          <h3 class="storage-name">${esc(v.name)}</h3>
          <div class="storage-meta">
            <span class="storage-tag">${esc(v.category)}</span>
            <span class="storage-place">📍 ${esc(v.place)}</span>
          </div>
        </div>
        <div class="storage-qty">
          <input type="number" step="0.1" value="${v.quantity}" data-qty="${v.id}" class="qty-cell">
          <span class="storage-unit">${esc(v.unit)}</span>
        </div>
        <div class="project-actions">
          <button data-act="edit" title="Modifica">✏️</button>
          <button data-act="del" title="Elimina">🗑️</button>
        </div>
      </div>
      ${v.low ? '<p class="storage-alert">⚠️ Sta finendo</p>' : ''}
      ${v.notes ? `<p class="storage-notes">${esc(v.notes)}</p>` : ''}
    </article>`).join('');
}

$('#st-search').addEventListener('input', renderMagazzino);
$('#st-filter').addEventListener('change', (e) => { magazzinoFiltro = e.target.value; renderMagazzino(); });
$('#st-low-only').addEventListener('change', renderMagazzino);

// la giacenza si corregge dalla cella stessa: e' il dato che cambia piu'
// spesso, e aprire il form per una virgola e' un ostacolo inutile
$('#st-list').addEventListener('change', async (e) => {
  const id = e.target.dataset.qty;
  if (!id) return;
  await api(`/api/storage/${id}`, { method: 'PATCH', body: { quantity: Number(e.target.value) } });
  toast('Quantità aggiornata');
  renderMagazzino();
});

$('#st-list').addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-act]');
  if (!btn) return;
  const id = Number(btn.closest('.storage-card').dataset.id);
  const v = magazzinoDati.find((x) => x.id === id);
  if (!v) return;

  if (btn.dataset.act === 'edit') {
    apriStorageForm(v);
  } else if (btn.dataset.act === 'del') {
    if (!confirm(`Eliminare "${v.name}" dal magazzino?`)) return;
    await api(`/api/storage/${id}`, { method: 'DELETE' });
    toast('Voce eliminata');
    renderMagazzino();
  }
});

function apriStorageForm(v) {
  const cat = v ? v.category : magazzinoMeta.default_category;
  const luogo = v ? v.place : magazzinoMeta.default_place;
  showModal(v ? 'Modifica voce' : 'Nuova voce', `
    <div class="field"><label>Nome</label>
      <input id="stf-name" value="${esc(v ? v.name : '')}" placeholder="Es. Sapone per i piatti"></div>
    <div class="row" style="margin-bottom:12px">
      <div class="field" style="flex:1; margin:0"><label>Categoria</label>
        <select id="stf-cat" class="plain">${magazzinoMeta.categories.map((c) =>
          `<option${cat === c ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select></div>
      <div class="field" style="flex:1; margin:0"><label>Dove</label>
        <select id="stf-place" class="plain">${magazzinoMeta.places.map((p) =>
          `<option${luogo === p ? ' selected' : ''}>${esc(p)}</option>`).join('')}</select></div>
    </div>
    <div class="row" style="margin-bottom:12px">
      <div class="field" style="flex:1; margin:0"><label>Quantità</label>
        <input id="stf-qty" type="number" step="0.1" value="${v ? v.quantity : 1}"></div>
      <div class="field" style="flex:1; margin:0"><label>Unità</label>
        <input id="stf-unit" list="unit-list" value="${v ? v.unit : 'pz'}"></div>
      <div class="field" style="flex:1; margin:0"><label>Scorta minima</label>
        <input id="stf-min" type="number" step="0.1" value="${v ? v.min_quantity : 0}"></div>
    </div>
    <div class="field"><label>Note</label>
      <input id="stf-notes" value="${esc(v ? v.notes : '')}" placeholder="Es. scaffale in alto, marca X"></div>
    <div class="field"><label>Foto</label>
      <div class="photo-field">
        <img id="stf-photo-img" ${v && v.has_photo ? `src="${esc(v.photo_url)}"` : 'hidden'} alt="">
        <div class="photo-controls">
          <input id="stf-photo-file" type="file" accept="image/*">
          <button type="button" id="stf-photo-del">Togli la foto</button>
          <span class="hint">Serve a riconoscere la scatola. La foto si rimpicciolisce da sola.</span>
        </div>
      </div>
    </div>
    <div class="modal-foot">
      <button id="stf-save" class="primary">${v ? 'Salva' : 'Aggiungi'}</button>
      <button id="stf-cancel">Annulla</button>
    </div>`);

  // la foto si tiene a parte finche' non si salva: prima della creazione la
  // voce non ha un id, e la foto si aggancia all'id. `fotoScelta` e' il data URL
  // gia' ridotto, `fotoDaTogliere` dice di cancellare quella che c'era.
  let fotoScelta = '';
  let fotoDaTogliere = false;
  const anteprima = $('#stf-photo-img');
  const mostraFoto = (src) => {
    if (src) { anteprima.src = src; anteprima.hidden = false; }
    else { anteprima.removeAttribute('src'); anteprima.hidden = true; }
  };

  $('#stf-photo-file').addEventListener('change', async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    try {
      fotoScelta = await riduciFoto(file);
      fotoDaTogliere = false;
      mostraFoto(fotoScelta);
    } catch (err) { toast(err.message); }
  });

  $('#stf-photo-del').addEventListener('click', () => {
    fotoScelta = '';
    fotoDaTogliere = Boolean(v && v.has_photo);
    $('#stf-photo-file').value = '';
    mostraFoto('');
  });

  $('#stf-cancel').addEventListener('click', hideModal);
  $('#stf-save').addEventListener('click', async () => {
    const corpo = {
      name: $('#stf-name').value.trim(),
      category: $('#stf-cat').value,
      place: $('#stf-place').value,
      quantity: Number($('#stf-qty').value) || 0,
      unit: $('#stf-unit').value.trim() || 'pz',
      min_quantity: Number($('#stf-min').value) || 0,
      notes: $('#stf-notes').value.trim(),
    };
    if (!corpo.name) return toast('Inserisci un nome');
    try {
      let id;
      if (v) {
        await api(`/api/storage/${v.id}`, { method: 'PUT', body: corpo });
        id = v.id;
      } else {
        const creata = await api('/api/storage', { method: 'POST', body: corpo });
        id = creata.id;
      }
      // la foto si manda dopo la voce: prima non ci sarebbe un id a cui
      // agganciarla. Se il salvataggio della voce riesce e la foto no, la voce
      // resta comunque: meglio aver perso la foto che l'inserimento.
      if (fotoScelta) await api(`/api/storage/${id}/photo`, { method: 'POST', body: { image: fotoScelta } });
      else if (fotoDaTogliere) await api(`/api/storage/${id}/photo`, { method: 'DELETE' });
      hideModal();
      toast(v ? 'Voce salvata' : 'Voce aggiunta');
      renderMagazzino();
    } catch (err) { toast(err.message); }
  });
}

$('#st-new').addEventListener('click', () => apriStorageForm(null));

/* ---------- FAQ ----------
   Informazioni utili da consultare: Wi-Fi, indirizzi, contatti, codici. Le voci
   si raggruppano per categoria e si cercano in locale: l'elenco e' piccolo e
   filtrare senza passare dal server e' immediato a ogni lettera. */
let faqDati = { voci: [], totale: 0, riservate: 0 };
let faqMeta = { categories: [], default_category: 'generale' };

// quali valori riservati sono stati mostrati: vivono in memoria, non salvati,
// così tornando sulla pagina una password e' di nuovo nascosta
const faqSvelate = new Set();

/* Il valore di una voce: un numero di telefono o un accesso si copiano, un
   indirizzo si legge. `tel:` e `mailto:` sono il modo per renderli toccabili
   sul telefono, dove questa sezione si usa di piu'. */
function faqValore(v) {
  const t = (v.answer || '').trim();
  if (!t) return '<span class="faq-empty">— nessun valore —</span>';
  // solo se il valore *e'* un contatto, non se lo contiene: un testo lungo si
  // mostra come testo, un numero da chiamare diventa un link
  const unaRiga = !t.includes('\n');
  if (unaRiga && /^[+\d][\d\s.\-/()]{4,}$/.test(t)) {
    const pulito = t.replace(/[^\d+]/g, '');
    return `<a class="faq-link" href="tel:${esc(pulito)}">${esc(t)}</a>`;
  }
  if (unaRiga && /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(t)) {
    return `<a class="faq-link" href="mailto:${esc(t)}">${esc(t)}</a>`;
  }
  return esc(t).replace(/\n/g, '<br>');
}

function faqRiga(v) {
  const nascosta = v.secret && !faqSvelate.has(v.id);
  return `
    <div class="faq-item${nascosta ? ' hidden-value' : ''}" data-faq="${v.id}">
      <div class="faq-item-head">
        <span class="faq-q">${v.pinned ? '<span class="faq-pin" title="In evidenza">★</span>' : ''}${esc(v.question)}</span>
        <span class="faq-cat">${esc(v.category_label || '')}</span>
      </div>
      <div class="faq-a">${nascosta
        ? `<span class="faq-secret">••••••••</span>
           <button class="faq-reveal ghost" data-reveal="${v.id}">Mostra</button>`
        : faqValore(v)}</div>
      <div class="faq-tools">
        ${!nascosta && v.answer ? `<button class="ghost" data-copy="${v.id}">Copia</button>` : ''}
        <button class="ghost" data-faq-pin="${v.id}">${v.pinned ? 'Togli da evidenza' : 'In evidenza'}</button>
        <button class="ghost" data-faq-edit="${v.id}">Modifica</button>
        <button class="ghost" data-faq-del="${v.id}">Elimina</button>
      </div>
    </div>`;
}

async function renderFaq() {
  [faqMeta, faqDati] = await Promise.all([api('/api/faq/meta'), api('/api/faq')]);
  // il filtro per categoria si costruisce una volta sola, con i conteggi
  const sel = $('#faq-filter');
  if (!sel.options.length) {
    sel.innerHTML = '<option value="">Tutte le categorie</option>'
      + faqMeta.categories.map((c) => `<option value="${c.key}">${esc(c.label)}</option>`).join('');
  }
  disegnaFaq();
}

function disegnaFaq() {
  const q = ($('#faq-search').value || '').trim().toLowerCase();
  const cat = $('#faq-filter').value || '';
  const visibili = faqDati.voci.filter((v) => {
    if (cat && v.category !== cat) return false;
    if (!q) return true;
    // anche il nome della categoria entra nella ricerca: chi cerca "idraulico"
    // non sa in quale categoria sta, e non deve indovinarlo
    return `${v.question} ${v.answer} ${v.category_label || ''}`.toLowerCase().includes(q);
  });

  $('#faq-count').textContent = visibili.length === faqDati.totale
    ? `${faqDati.totale} ${faqDati.totale === 1 ? 'voce' : 'voci'}`
    : `${visibili.length} di ${faqDati.totale}`;

  if (!faqDati.totale) {
    $('#faq-list').innerHTML = `
      <div class="empty-state">
        <span class="empty-emoji">📌</span>
        <h2>Ancora nessuna voce</h2>
        <p>Aggiungi le informazioni che non ricordi mai: la password del Wi-Fi,
          gli indirizzi che cerchi spesso, i numeri utili, i codici d'accesso.</p>
      </div>`;
    return;
  }
  if (!visibili.length) {
    $('#faq-list').innerHTML = '<p class="faq-none">Nessuna voce corrisponde alla ricerca.</p>';
    return;
  }

  // raggruppate per categoria, nell'ordine deciso da /api/faq: le voci arrivano
  // gia' ordinate, quindi basta spezzare l'elenco quando cambia la categoria
  let html = '';
  let corrente = null;
  for (const v of visibili) {
    if (v.category !== corrente) {
      corrente = v.category;
      const n = visibili.filter((x) => x.category === corrente).length;
      html += `<h3 class="section-title">${esc(v.category_label || '')}
        <span class="faq-n">${n}</span></h3>`;
    }
    html += faqRiga(v);
  }
  $('#faq-list').innerHTML = html;
}

$('#faq-search').addEventListener('input', disegnaFaq);
$('#faq-filter').addEventListener('change', disegnaFaq);

$('#faq-list').addEventListener('click', async (e) => {
  const svela = e.target.closest('[data-reveal]');
  if (svela) {
    faqSvelate.add(Number(svela.dataset.reveal));
    return disegnaFaq();
  }
  const copia = e.target.closest('[data-copy]');
  if (copia) {
    const v = faqDati.voci.find((x) => x.id === Number(copia.dataset.copy));
    try {
      await navigator.clipboard.writeText(v.answer || '');
      toast('Copiato');
    } catch {
      // la Clipboard API richiede HTTPS o localhost: se il browser la nega, il
      // valore resta comunque leggibile sullo schermo
      toast('Copia non riuscita: seleziona il testo a mano');
    }
    return;
  }
  const pin = e.target.closest('[data-faq-pin]');
  if (pin) {
    const v = faqDati.voci.find((x) => x.id === Number(pin.dataset.faqPin));
    await api(`/api/faq/${v.id}`, { method: 'PUT', body: { pinned: v.pinned ? 0 : 1 } });
    toast(v.pinned ? 'Tolta dall\'evidenza' : 'Messa in evidenza');
    return renderFaq();
  }
  const mod = e.target.closest('[data-faq-edit]');
  if (mod) {
    return apriFaqForm(faqDati.voci.find((x) => x.id === Number(mod.dataset.faqEdit)));
  }
  const del = e.target.closest('[data-faq-del]');
  if (del) {
    const v = faqDati.voci.find((x) => x.id === Number(del.dataset.faqDel));
    if (!confirm(`Eliminare "${v.question}"?`)) return;
    await api(`/api/faq/${v.id}`, { method: 'DELETE' });
    toast('Voce eliminata');
    return renderFaq();
  }
});

function apriFaqForm(v) {
  const cat = (v && v.category) || faqMeta.default_category;
  showModal(v ? 'Modifica voce' : 'Nuova voce', `
    <div class="field"><label>Informazione</label>
      <input id="fq-q" value="${esc(v ? v.question : '')}" placeholder="Es. Wi-Fi di casa, Idraulico, Cancello"></div>
    <div class="field"><label>Categoria</label>
      <select id="fq-cat">${faqMeta.categories.map((c) =>
        `<option value="${c.key}"${cat === c.key ? ' selected' : ''}>${esc(c.label)}</option>`).join('')}</select></div>
    <div class="field"><label>Valore</label>
      <textarea id="fq-a" placeholder="Es. Rete: CasaRossi&#10;Password: ...">${esc(v ? v.answer : '')}</textarea></div>
    <label class="toggle"><input type="checkbox" id="fq-secret"${v && v.secret ? ' checked' : ''}>
      Nascondi il valore finché non lo apro</label>
    <p class="faq-note">Serve a non tenere una password sullo schermo, ma non è una
      protezione: chi consulta questa pagina può comunque vederla.</p>
    <label class="toggle"><input type="checkbox" id="fq-pin"${v && v.pinned ? ' checked' : ''}>
      In evidenza in cima alla categoria</label>
    <div class="modal-foot">
      <button id="fq-save" class="primary">${v ? 'Salva' : 'Aggiungi'}</button>
      <button id="fq-cancel">Annulla</button>
    </div>`);

  $('#fq-cancel').addEventListener('click', hideModal);
  $('#fq-q').focus();
  $('#fq-save').addEventListener('click', async () => {
    const corpo = {
      question: $('#fq-q').value.trim(),
      answer: $('#fq-a').value,
      category: $('#fq-cat').value,
      secret: $('#fq-secret').checked,
      pinned: $('#fq-pin').checked,
    };
    if (!corpo.question) return toast('Inserisci il titolo');
    try {
      if (v) await api(`/api/faq/${v.id}`, { method: 'PUT', body: corpo });
      else await api('/api/faq', { method: 'POST', body: corpo });
      hideModal();
      toast(v ? 'Voce salvata' : 'Voce aggiunta');
      // una voce nuova non deve nascere gia' svelata per via di un id riusato
      if (!v) faqSvelate.clear();
      renderFaq();
    } catch (err) { toast(err.message); }
  });
}

$('#faq-new').addEventListener('click', () => apriFaqForm(null));

/* ---------- PROFILO ---------- */
function labelOf(key) { return allergenLabels[key] || key; }

async function renderProfile() {
  profile = await api('/api/profile');
  const declared = profile.restriction_list || [];
  const declaredKeys = new Set(declared.map((t) => t.toLowerCase()));
  const known = meta.allergens;

  $('#pf-name').value = profile.full_name || '';
  // quanti pasti al giorno: le opzioni arrivano dal backend, con i nomi dei pasti
  const pasti = $('#pf-meals');
  pasti.innerHTML = [1, 2, 3, 4, 5]
    .map((n) => `<option value="${n}">${esc(etichettaPasti(n))}</option>`).join('');
  pasti.value = String(profile.meals_per_day || 2);
  $('#pf-allergens').innerHTML = known.map((a) => {
    const on = declaredKeys.has(a.key.toLowerCase()) || declaredKeys.has(a.label.toLowerCase());
    return `<button class="chip ${on ? 'on' : ''}" data-allergen="${a.key}">${esc(a.label)}</button>`;
  }).join('');

  const custom = declared.filter((t) => !known.some((a) =>
    a.key.toLowerCase() === t.toLowerCase() || a.label.toLowerCase() === t.toLowerCase()));
  $('#pf-custom').innerHTML = custom
    .map((t) => `<button class="chip on" data-term="${esc(t)}">${esc(t)} ✕</button>`).join('');

  // le preferite si salvano subito, come gli altri controlli del profilo
  const favBox = $('#pf-favorites');
  if (!recipesCache.length) recipesCache = await api('/api/recipes?full=1');
  favoritesPicker(favBox, recipesCache, profile.favorite_ids || [], (ids) => saveFavorites(ids));

  await renderReport(declared);
  await mostraCopie();
}

// riepilogo: quali ingredienti in uso contengono un allergene riconosciuto
async function renderReport(declared) {
  const map = await api('/api/profile/allergens');
  const rows = Object.entries(map).sort((a, b) => a[0].localeCompare(b[0], 'it'));
  $('#pf-report').innerHTML = rows.map(([name, tags]) => {
    const hit = tags.length && declared.some((t) => {
      const key = meta.allergens.find((a) =>
        a.key.toLowerCase() === t.toLowerCase() || a.label.toLowerCase() === t.toLowerCase());
      return key ? tags.includes(key.key) : false;
    });
    const labels = tags.map((t) => labelOf(t)).join(', ');
    return `<div class="report-row ${hit ? 'unsafe' : ''}">
      <span class="ing">${hit ? '⚠️ ' : ''}${esc(name)}</span>
      <span class="tags">${labels ? esc(labels) : '—'}</span></div>`;
  }).join('') || '<p>Nessun ingrediente in uso.</p>';
}

$('#pf-allergens').addEventListener('click', async (e) => {
  const key = e.target.dataset.allergen;
  if (!key) return;
  const label = labelOf(key);
  const cur = profile.restriction_list || [];
  const has = cur.some((t) => t.toLowerCase() === key.toLowerCase() || t.toLowerCase() === label.toLowerCase());
  const next = has
    ? cur.filter((t) => t.toLowerCase() !== key.toLowerCase() && t.toLowerCase() !== label.toLowerCase())
    : [...cur, label];
  profile = await api('/api/profile', { method: 'PUT', body: { restrictions: next } });
  await renderProfile();
});

$('#pf-term-add').addEventListener('click', async () => {
  const term = $('#pf-term').value.trim();
  if (!term) return;
  const next = [...(profile.restriction_list || []), term];
  profile = await api('/api/profile', { method: 'PUT', body: { restrictions: next } });
  $('#pf-term').value = '';
  await renderProfile();
});

// i pasti si applicano subito: cambiare il numero cambia le caselle del piano,
// quindi conviene vederlo all'istante invece di aspettare "Salva profilo"
$('#pf-meals').addEventListener('change', async () => {
  try {
    await applicaPasti(Number($('#pf-meals').value));
    toast(`Piano aggiornato: ${etichettaPasti(Number($('#pf-meals').value))}`);
  } catch (err) {
    toast(err.message);
    await renderProfile();
  }
});

$('#pf-custom').addEventListener('click', async (e) => {
  const term = e.target.dataset.term;
  if (!term) return;
  const next = (profile.restriction_list || []).filter((t) => t !== term);
  profile = await api('/api/profile', { method: 'PUT', body: { restrictions: next } });
  await renderProfile();
});

$('#pf-save').addEventListener('click', async () => {
  profile = await api('/api/profile', {
    method: 'PUT',
    body: { full_name: $('#pf-name').value.trim(), onboarded: true },
  });
  toast('Profilo salvato');
  renderRecipes();
});

$('#pf-filter').addEventListener('change', () => {
  renderRecipes();
});

/* Il salvataggio dei dati si scarica con un semplice link, non con `fetch`:
   il browser deve gestire il file come un download, con la sua finestrella e il
   suo nome. Passando da `fetch` bisognerebbe ricostruire un blob e un link
   finto, e si perderebbero il nome suggerito dal server e la barra di
   avanzamento. Il file e' piccolo, quindi non serve nulla di piu' elaborato. */
$('#pf-backup').addEventListener('click', () => {
  window.location.href = '/api/backup';
  toast('Preparo la copia dei dati...');
});

/* Le copie automatiche si dicono nel Profilo, dove si parla dei dati: senza
   questa riga l'utente vedrebbe solo il pulsante per scaricarle e crederebbe
   di non averne nessuna. Se la richiesta fallisce non si dice niente: e' una
   informazione in piu', non una cosa per cui valga la pena mostrare un errore. */
async function mostraCopie() {
  const box = $('#pf-copie');
  if (!box) return;
  try {
    const d = await api('/api/copie');
    if (!d.quante) {
      box.textContent = 'La prima copia automatica arriva tra poco: il server la '
        + 'prende da solo ogni giorno senza che tu debba chiederla.';
      return;
    }
    const quando = d.ultima ? `L'ultima è del ${esc(d.ultima)}.` : '';
    box.innerHTML = `Il server ne tiene una al giorno, in automatico: `
      + `adesso ce ne sono <strong>${d.quante}</strong> (tiene le ultime ${d.conservate}). ${quando}`;
  } catch { /* niente: e' un'informazione in piu', non un errore da mostrare */ }
}

/* ---------- ricette preferite ---------- */

/* Selettore di ricette preferite, riusato dall'onboarding e dal Profilo.
   `onChange` riceve l'elenco aggiornato di id: ogni contesto decide quando
   salvare. Le classi (non gli id) tengono il selettore riutilizzabile piu' volte
   nella stessa pagina, e il disegno e' separato dalla ricerca per non far
   perdere il focus al campo mentre si digita. */
function favoritesPicker(box, recipes, selected, onChange) {
  const chosen = new Set(selected);
  box.innerHTML = `
    <input class="fav-search" type="search" placeholder="Cerca fra le ricette...">
    <p class="hint fav-count"></p>
    <div class="chips fav-chips"></div>`;
  const search = box.querySelector('.fav-search');
  const chips = box.querySelector('.fav-chips');
  const count = box.querySelector('.fav-count');

  const draw = () => {
    const q = search.value.trim().toLowerCase();
    const list = recipes.filter((r) => r.name.toLowerCase().includes(q));
    chips.innerHTML = list.map((r) => `
      <button class="chip ${chosen.has(r.id) ? 'on' : ''}" data-fav="${r.id}">
        ${chosen.has(r.id) ? '★' : '☆'} ${esc(r.name)}${r.conflicts && r.conflicts.length ? ' ⚠️' : ''}
      </button>`).join('') || '<p class="muted">Nessuna ricetta trovata.</p>';
    count.textContent = chosen.size
      ? `${chosen.size} ${chosen.size === 1 ? 'ricetta scelta' : 'ricette scelte'}`
      : 'Nessuna ricetta scelta';
  };

  search.addEventListener('input', draw);
  chips.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-fav]');
    if (!btn) return;
    const id = Number(btn.dataset.fav);
    if (chosen.has(id)) chosen.delete(id); else chosen.add(id);
    draw();
    onChange([...chosen]);
  });
  draw();
}

/* Salva le preferite senza ridisegnare il profilo, cosi' il selettore non
   perde la ricerca appena digitata. */
async function saveFavorites(ids) {
  profile = await api('/api/profile', { method: 'PUT', body: { favorite_ids: ids } });
  recipesCache = [];
  return profile;
}

/* Passo 2 dell'onboarding (scelta delle preferite), richiamabile anche da solo:
   serve sia alla fine dell'onboarding completo sia a chi si era profilato prima
   che questa scelta esistesse. `onBack` assente significa che non c'e' un passo
   precedente a cui tornare. `preferite` e' passato dal chiamante perche' la
   scelta sopravviva a un andirivieni fra i due passi, che non salva nulla. */
async function openFavoritesStep(onBack, preferite) {
  preferite = preferite || new Set(profile.favorite_ids || []);
  showModal('Quali ricette ti piacciono?', `
    <p class="lead">${onBack ? 'Passo 3 di 3 · ' : ''}l'app parte con un
    <strong>ricettario italiano già pronto</strong><span id="ob-count"></span>: non devi
    inserire le ricette tu. Qui scegli quelle che ami: le ritrovi con il filtro
    <strong>Solo preferite</strong> nella scheda Ricette. Puoi cambiare la scelta quando
    vuoi dalla scheda <strong>Profilo</strong>.</p>
    <p class="lead">Per aggiungere una ricetta tua, dalla scheda Ricette premi
    <strong>+ Nuova ricetta</strong>, oppure <strong>dilla a voce</strong>: «crea la ricetta
    pasta al forno» e il modulo si apre già col nome scritto.</p>
    <div id="ob-favorites"></div>
    <div class="modal-foot">
      ${onBack ? '<button id="ob-back">Indietro</button>' : '<button id="ob-later">Più tardi</button>'}
      <button class="primary" id="ob-save">Salva e inizia</button>
    </div>
  `);
  const box = $('#ob-favorites');
  box.innerHTML = '<p class="muted">Carico le ricette...</p>';
  let list = [];
  try {
    list = await api('/api/recipes?full=1');
  } catch (err) {
    box.innerHTML = '<p class="muted">Non riesco a caricare le ricette.</p>';
  }
  if (!list.length) {
    box.innerHTML = '<p class="muted">Non ci sono ancora ricette: potrai sceglierle dopo averne create.</p>';
  } else {
    // il numero si legge dalle ricette che ci sono davvero: scritto a mano
    // diventerebbe sbagliato al primo ritocco del ricettario
    const count = $('#ob-count');
    if (count) count.textContent = ` (${list.length} ricette)`;
    favoritesPicker(box, list, [...preferite], (ids) => {
      preferite.clear();
      ids.forEach((i) => preferite.add(i));
    });
  }
  if (onBack) $('#ob-back').addEventListener('click', onBack);
  else $('#ob-later').addEventListener('click', async () => {
    // non riproporre a ogni avvio: la scelta resta disponibile nel Profilo
    profile = await api('/api/profile', { method: 'PUT', body: { fav_prompted: true } });
    hideModal();
    toast('Puoi scegliere le preferite quando vuoi dalla scheda Profilo');
  });
  $('#ob-save').addEventListener('click', async () => {
    profile = await api('/api/profile', {
      method: 'PUT',
      body: { favorite_ids: [...preferite], onboarded: true, fav_prompted: true },
    });
    hideModal();
    const n = preferite.size;
    toast(n ? `Profilo salvato con ${n} ${n === 1 ? 'ricetta preferita' : 'ricette preferite'}`
            : 'Profilo salvato');
    renderPlan();
  });
}

/* Onboarding in tre passi: prima quanti pasti al giorno, poi allergie e
   intolleranze, infine le ricette preferite. Ogni passo salva il suo pezzo
   appena si va avanti, quindi chi chiude a meta' ritrova quanto dichiarato
   invece di ricominciare. */
async function openOnboarding() {
  const known = meta.allergens;
  // Bozza condivisa fra i passi. "Salta" porta al passo successivo senza salvare,
  // e da li' "Indietro" riporta al passo prima: senza questa copia nome, allergie,
  // pasti e preferite andrebbero persi a ogni andirivieni.
  const bozza = {
    nome: profile.full_name || '',
    pasti: profile.meals_per_day || 2,
    selected: known.filter((a) => (profile.restriction_list || []).some((t) =>
      t.toLowerCase() === a.key.toLowerCase() || t.toLowerCase() === a.label.toLowerCase())).map((a) => a.key),
    custom: (profile.restriction_list || []).filter((t) => !known.some((a) =>
      a.key.toLowerCase() === t.toLowerCase() || a.label.toLowerCase() === t.toLowerCase())),
  };
  const preferite = new Set(profile.favorite_ids || []);

  // Passo 1: quanti pasti al giorno.
  const passoPasti = () => {
    const opzioni = [1, 2, 3, 4, 5];
    showModal('Quanti pasti al giorno?', `
      <p class="lead">Passo 1 di 3 · scegli quanti pasti vuoi pianificare ogni giorno.
      Il piano mostra una casella per ciascuno: puoi cambiare quando vuoi dalla scheda
      <strong>Profilo</strong>.</p>
      <div id="ob-meals" class="meal-choice">
        ${opzioni.map((n) => `
          <button class="meal-opt ${bozza.pasti === n ? 'on' : ''}" data-meals="${n}">
            <span class="meal-num">${n}</span>
            <span class="meal-names">${(((meta.meal_sets || {})[String(n)]) || []).join('<br>')}</span>
          </button>`).join('')}
      </div>
      <div class="modal-foot">
        <button id="ob-meals-next" class="primary">Avanti</button>
      </div>
    `);
    $('#ob-meals').addEventListener('click', (e) => {
      const b = e.target.closest('.meal-opt');
      if (!b) return;
      bozza.pasti = Number(b.dataset.meals);
      $$('#ob-meals .meal-opt').forEach((x) => x.classList.toggle('on', x === b));
    });
    $('#ob-meals-next').addEventListener('click', async () => {
      try {
        await applicaPasti(bozza.pasti);
      } catch (err) {
        toast(err.message);
      }
      passoAllergie();
    });
  };

  const passoAllergie = () => {
    showModal('Benvenuto su Il Maggiordomo', `
      <p class="lead">Passo 2 di 3 · dichiara allergie e intolleranze: le ricette che le
      contengono verranno segnalate. Puoi modificare tutto in seguito dalla scheda
      <strong>Profilo</strong>.</p>
      <div class="field"><label>Nome (facoltativo)</label><input id="ob-name" placeholder="Come ti chiami?" value="${esc(bozza.nome)}"></div>
      <div class="field"><label>Seleziona ciò che ti riguarda</label>
        <div id="ob-allergens" class="chips"></div>
        <div class="row">
          <input id="ob-term" placeholder="Altro termine (es. nichel, fruttosio)">
          <button id="ob-term-add">Aggiungi</button>
        </div>
        <div id="ob-custom" class="chips"></div>
      </div>
      <div class="banner"><strong>⚠️ Controlli indicativi</strong>
        <p>Le allerte derivano dal nome degli ingredienti e non sostituiscono la lettura
        dell'etichetta né il parere del medico.</p></div>
      <div class="modal-foot">
        <button id="ob-back">Indietro</button>
        <span class="spacer"></span>
        <button id="ob-skip">Salta</button>
        <button class="primary" id="ob-next">Avanti</button>
      </div>
    `);

    const chipsBox = $('#ob-allergens');
    const drawChips = () => {
      chipsBox.innerHTML = known.map((a) =>
        `<button class="chip ${bozza.selected.includes(a.key) ? 'on' : ''}" data-key="${a.key}">${esc(a.label)}</button>`).join('');
    };
    const drawCustom = () => {
      $('#ob-custom').innerHTML = bozza.custom.map((t) => `<button class="chip on" data-rm="${esc(t)}">${esc(t)} ✕</button>`).join('');
    };
    drawChips();
    drawCustom();
    chipsBox.addEventListener('click', (e) => {
      const k = e.target.dataset.key;
      if (!k) return;
      bozza.selected = bozza.selected.includes(k)
        ? bozza.selected.filter((x) => x !== k) : [...bozza.selected, k];
      drawChips();
    });
    $('#ob-term-add').addEventListener('click', () => {
      const t = $('#ob-term').value.trim();
      if (!t || bozza.custom.includes(t)) return;
      bozza.custom.push(t);
      $('#ob-term').value = '';
      drawCustom();
    });
    $('#ob-custom').addEventListener('click', (e) => {
      const t = e.target.dataset.rm;
      if (t) { bozza.custom = bozza.custom.filter((x) => x !== t); drawCustom(); }
    });

    const salvaRestrizioni = async () => {
      bozza.nome = $('#ob-name').value.trim();
      const terms = [...bozza.selected.map((k) => labelOf(k)), ...bozza.custom];
      profile = await api('/api/profile', {
        method: 'PUT',
        body: { full_name: bozza.nome, restrictions: terms },
      });
    };

    // 'Indietro' non salva: la bozza conserva le scelte fatte, cosi' tornando
    // avanti non si riparte da zero
    $('#ob-back').addEventListener('click', passoPasti);
    $('#ob-skip').addEventListener('click', () => {
      bozza.nome = $('#ob-name').value.trim();
      openFavoritesStep(passoAllergie, preferite);
    });
    $('#ob-next').addEventListener('click', async () => {
      await salvaRestrizioni();
      openFavoritesStep(passoAllergie, preferite);
    });
  };

  passoPasti();
}

/* ---------- modale ---------- */
function showModal(title, html) {
  $('#modal-title').textContent = title;
  $('#modal-body').innerHTML = html;
  $('#modal').classList.remove('hidden');
}
function hideModal() { $('#modal').classList.add('hidden'); }
$('#modal-close').addEventListener('click', hideModal);
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') hideModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideModal(); });

/* ---------- comandi vocali ----------
   Il riconoscimento avviene nel browser (Web Speech API) e restituisce solo
   testo: la comprensione vera resta sul server in /api/voice, dove si può
   verificare con i test. Qui si gestisce microfono, conferma e ricarica. */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

function switchTab(nome) {
  const btn = $(`#tabs button[data-tab="${nome}"]`);
  if (btn) btn.click();
}

/* ---------- timbro della voce ----------
   Il browser espone voci diverse a seconda del sistema operativo, quindi non si
   può indicare un nome fisso: si sceglie per caratteristiche (lingua e genere),
   con una lista di preferenze in ordine. Se una voce italiana non c'è si ripiega
   su quella predefinita, meglio una voce diversa che nessuna voce.

   I valori di `rate` e `pitch` sono volutamente vicini a 1: le voci di sistema
   sono sintetiche, e allontanarsi dalla loro intonazione naturale le rende
   artificiali invece che espressive. Il timbro si distingue per il registro
   (più acuto o più grave), non per la velocità. */
const TIMBRI = {
  chiara: {
    etichetta: 'Chiara',
    rate: 1.0, pitch: 1.0,
    // le voci note cambiano nome fra Windows, macOS, Android e Chrome
    nomi: ['alice', 'elsa', 'paola', 'federica', 'italiano', 'italian'],
  },
  profonda: {
    etichetta: 'Profonda',
    rate: 0.96, pitch: 0.85,
    nomi: ['cosimo', 'diego', 'luca', 'matteo', 'italiano', 'italian'],
  },
  calda: {
    etichetta: 'Calda',
    rate: 0.93, pitch: 0.95,
    nomi: ['alice', 'elsa', 'paola', 'italiano', 'italian'],
  },
};

let tts = { voce: null, caricate: false };

function timbroScelto() {
  return TIMBRI[localStorage.getItem('voceTimbro')] ? localStorage.getItem('voceTimbro') : 'chiara';
}

/** La voce scelta a mano dall'elenco completo, se esiste ancora.

    Si memorizza il `voiceURI` e non il nome: fra due voci diverse il nome può
    coincidere, il voiceURI no. Se la voce è sparita (cambio di sistema, browser
    diverso) si torna al timbro, invece di restare senza voce. */
function voceEsplicita() {
  const uri = localStorage.getItem('voceScelta');
  if (!uri || !window.speechSynthesis || !speechSynthesis.getVoices) return null;
  return speechSynthesis.getVoices().find((v) => v.voiceURI === uri) || null;
}

/** True per le voci "naturali" (neurali), le uniche che suonano davvero bene.

    Windows 11 le ha, ma **non le espone a Chrome e Firefox**: compaiono solo in
    Edge. Per questo su Chrome si sente ancora la voce vecchia e metallica anche
    se sul sistema ci sono voci molto migliori. Riconoscerle qui serve a
    preferirle automaticamente quando ci sono. */
function eVoceNaturale(v) {
  return /natural|neural/i.test(v.name || '');
}

/** Sceglie la voce del sistema più vicina al timbro richiesto.

    L'ordine conta: prima una voce **naturale** che corrisponda al timbro, poi una
    voce normale del timbro, poi una naturale qualsiasi. Una voce naturale di
    registro diverso si sente comunque meglio di una voce sintetica del registro
    giusto: la qualità pesa più della sfumatura. */
function scegliVoce(timbro) {
  if (!window.speechSynthesis || !speechSynthesis.getVoices) return null;
  const voci = speechSynthesis.getVoices();
  if (!voci.length) return null;

  const scelta = voceEsplicita();
  if (scelta) return scelta;

  const it = voci.filter((v) => (v.lang || '').toLowerCase().startsWith('it'));
  if (!it.length) return null;
  const t = TIMBRI[timbro] || TIMBRI.chiara;
  const naturale = (v) => eVoceNaturale(v);

  const naturali = it.filter(naturale);
  for (const nome of t.nomi) {
    const trovata = naturali.find((v) => (v.name || '').toLowerCase().includes(nome));
    if (trovata) return trovata;
  }
  for (const nome of t.nomi) {
    const trovata = it.find((v) => (v.name || '').toLowerCase().includes(nome));
    if (trovata) return trovata;
  }
  // la prima voce italiana, in mancanza di quella cercata
  return naturali[0] || it[0] || null;
}

/** Rilegge le voci: su molte piattaforme l'elenco arriva in modo asincrono. */
function caricaVoci() {
  if (!window.speechSynthesis) return;
  tts.caricate = true;
  tts.voce = scegliVoce(timbroScelto());
  aggiornaEtichetteVoci();
  aggiornaElencoVoci();
}

/** Mostra il nome della voce che ogni timbro usa davvero su questo sistema.
    Il timbro è una preferenza ("una voce femminile"), ma la voce concreta
    cambia di piattaforma in piattaforma: dirlo evita di cercare una voce
    che qui non esiste. */
function aggiornaEtichetteVoci() {
  const pick = $('#voice-pick');
  if (!pick || !window.speechSynthesis || !speechSynthesis.getVoices) return;
  if (!speechSynthesis.getVoices().length) return;
  Object.keys(TIMBRI).forEach((chiave) => {
    const opt = pick.querySelector(`option[value="${chiave}"]`);
    if (!opt) return;
    const v = scegliVoce(chiave);
    opt.textContent = v ? `${TIMBRI[chiave].etichetta} · ${v.name}` : TIMBRI[chiave].etichetta;
  });
}

/** Riempie l'elenco completo delle voci italiane.

    I tre timbri sono scorciatoie comode ma non lasciano scegliere: se il sistema
    espone una voce naturale e il timbro ne pesca un'altra, l'utente non ha modo di
    prenderla. Qui si mostrano tutte, marcando le naturali e quelle che funzionano
    senza rete, così la scelta è esplicita. */
function aggiornaElencoVoci() {
  const sel = $('#voice-all');
  if (!sel || !window.speechSynthesis || !speechSynthesis.getVoices) return;
  const voci = speechSynthesis.getVoices();
  if (!voci.length) return;

  const it = voci.filter((v) => (v.lang || '').toLowerCase().startsWith('it'));
  const corrente = voceEsplicita() || tts.voce;
  const righe = ['<option value="">Automatica (secondo il timbro)</option>'];

  // naturali in cima: sono quelle che l'utente sta cercando
  it.sort((a, b) => (eVoceNaturale(b) ? 1 : 0) - (eVoceNaturale(a) ? 1 : 0) || a.name.localeCompare(b.name));
  for (const v of it) {
    const note = [];
    if (eVoceNaturale(v)) note.push('naturale');
    if (v.localService === false) note.push('online');
    const etichetta = note.length ? `${v.name} · ${note.join(', ')}` : v.name;
    const sel_ = corrente && corrente.voiceURI === v.voiceURI ? ' selected' : '';
    righe.push(`<option value="${esc(v.voiceURI)}"${sel_}>${esc(etichetta)}</option>`);
  }
  sel.innerHTML = righe.join('');

  const avviso = $('#voice-avviso');
  if (avviso) {
    // se non c'e' nessuna voce naturale, dirlo invece di lasciare l'utente a
    // cercare fra nomi che sembrano tutti uguali
    avviso.textContent = it.some(eVoceNaturale)
      ? ''
      : 'Nessuna voce naturale disponibile su questo browser. Su Windows le voci migliori compaiono solo in Microsoft Edge.';
  }
}

/** Divide il testo in frasi, tenendo la punteggiatura di ciascuna.

    Serve a non leggere tutto in una fila sola: la sintesi del sistema applica
    una sola curva di intonazione a una frase lunga, ed è il motivo per cui una
    conferma come "In dispensa: farina 2 kg" suona piatta. Su frasi brevi il
    sistema chiude l'intonazione a ogni punto, e l'ascolto cambia. */
function spezzaInFrasi(testo) {
  const parti = String(testo || '').match(/[^.!?;:]+[.!?;:]*/g) || [];
  return parti.map((p) => p.trim()).filter(Boolean);
}

/** Pronuncia un testo spezzandolo in frasi, ognuna con la sua intonazione. */
function parlaTesto(testo) {
  if (!window.speechSynthesis) { avvisaFineParlato(); return; }
  try {
    speechSynthesis.cancel();
    const timbro = timbroScelto();
    tts.voce = scegliVoce(timbro);
    const t = TIMBRI[timbro] || TIMBRI.chiara;
    const frasi = spezzaInFrasi(testo);
    if (!frasi.length) { avvisaFineParlato(); return; }

    frasi.forEach((frase, i) => {
      const ultima = i === frasi.length - 1;
      const u = new SpeechSynthesisUtterance(frase);
      // l'assegnazione della voce sta da sola in un try: una voce non più valida
      // (l'elenco del browser cambia, e un oggetto tenuto da parte può morire)
      // solleva qui, e senza questa protezione se ne andrebbe in silenzio tutto
      // il messaggio invece della sola voce. Meglio la voce predefinita che niente.
      try {
        if (tts.voce) u.voice = tts.voce;
      } catch (_e) { /* si parla con la voce predefinita */ }
      u.lang = (tts.voce && tts.voce.lang) || 'it-IT';
      // l'ultima frase chiude la frase scendendo appena di tono e rallentando:
      // è quello che fa la voce umana a fine discorso, e senza si sente il
      // troncamento meccanico
      u.rate = t.rate * (ultima ? 0.97 : 1.0);
      u.pitch = t.pitch * (ultima ? 0.95 : 1.0);
      if (ultima) u.onend = avvisaFineParlato;
      speechSynthesis.speak(u);
    });
  } catch (_e) { avvisaFineParlato(); }
}

/** Segnala che l'assistente ha finito di parlare.

    Serve all'ascolto continuo: finché la voce parla il microfono deve tacere,
    altrimenti si riascolta e riparte da solo. Un solo punto di segnalazione,
    chiamato sia dalla voce del browser sia da quella neurale. */
function avvisaFineParlato() {
  const f = voce.aFineParlato;
  voce.aFineParlato = null;
  if (f) { try { f(); } catch (_e) { /* il chiamante ha già fatto il suo */ } }
}

function speak(text) {
  if (!$('#voice-speak').checked) return;
  // la sintesi vocale è un di più: se non è disponibile o fallisce, il comando
  // resta comunque riuscito e non deve trasformarsi in un falso errore
  parla(text);
}

/* ---------- voce neurale cloud ----------
   Quando il server ha una chiave configurata, la conferma arriva da una voce
   neurale (Azure) invece che da quella del browser: è lo stesso suono su ogni
   dispositivo, ed è la differenza fra una voce che sembra una persona e una che
   sembra un sintetizzatore. La chiave resta sul server: qui si riceve solo l'audio.

   Tre regole che valgono la pena di essere scritte, perché non sono ovvie:

   1. il cloud si prova e basta. Se non risponde, non è configurato o fallisce, si
      ripiega sulla voce del browser **senza dire niente**: l'utente ha chiesto di
      sentire una conferma, non di sapere da dove arriva.
   2. niente cloud per le frasi già sentite. Ogni frase non ripetuta è una chiamata
      fatturata, e le conferme sono molto ripetitive ("Fatto.", "Riprova.").
   3. l'anteprima del timbro resta locale. Deve essere immediata, e una chiamata di
      rete al momento della scelta la rende lenta proprio quando si sta decidendo. */

let voceCloud = { disponibile: false, ascolto: false, voci: [], sentite: new Map(), avvisato: false };

// oltre questa memoria non si accumula: le frasi brevi sono poche e ripetute
const CLOUD_CACHE_MAX = 40;

function cloudAttivo() {
  return voceCloud.disponibile && $('#voice-cloud') && $('#voice-cloud').checked;
}

function voceCloudScelta() {
  const salvata = localStorage.getItem('voceCloud');
  if (salvata && voceCloud.voci.some((v) => v.nome === salvata)) return salvata;
  return voceCloud.predefinita || 'it-IT-IsabellaNeural';
}

/** Scarica l'audio cloud e lo riproduce. `false` se non ci riesce, così il
    chiamante può ripiegare sul browser. */
async function parlaCloud(frase) {
  if (frase.length > (voceCloud.maxCaratteri || 600)) return false;
  const chiave = voceCloudScelta() + '|' + frase;

  let blob = voceCloud.sentite.get(chiave);
  if (!blob) {
    try {
      const r = await fetch('/api/voce/parla', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: frase, voice: voceCloudScelta() }),
      });
      if (!r.ok) {
        // il perché va detto una volta sola: ripiegando in silenzio si sente la
        // voce del sistema senza capire che la neurale ha smesso di funzionare,
        // e sembra che la configurazione non sia mai stata letta
        let motivo = '';
        try { motivo = (await r.json()).error || ''; } catch (_e) { /* risposta non JSON */ }
        if (!voceCloud.avvisato) {
          voceCloud.avvisato = true;
          voceStato(motivo ? `${motivo}: si sentirà la voce del sistema.`
                           : 'Voce neurale non raggiungibile: si sentirà la voce del sistema.', 'err');
        }
        return false;
      }
      blob = await r.blob();
    } catch (_e) {
      if (!voceCloud.avvisato) {
        voceCloud.avvisato = true;
        voceStato('Voce neurale non raggiungibile: si sentirà la voce del sistema.', 'err');
      }
      return false;
    }
    // tetto alla memoria: si butta la più vecchia, non si cresce all'infinito
    if (voceCloud.sentite.size >= CLOUD_CACHE_MAX) {
      voceCloud.sentite.delete(voceCloud.sentite.keys().next().value);
    }
    voceCloud.sentite.set(chiave, blob);
  }

  try {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await audio.play();
    // si libera l'URL quando ha finito: senza, il blob resta agganciato in memoria
    audio.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true });
    // l'ascolto continuo deve sapere quando la voce tace, altrimenti il microfono
    // riparte mentre l'assistente parla e lo risente
    audio.addEventListener('ended', avvisaFineParlato, { once: true });
    return true;
  } catch (_e) {
    // capita su iOS finché l'utente non ha toccato la pagina: in quel caso si
    // sente la voce del browser, che parte lo stesso
    return false;
  }
}

function parla(testo) {
  if (!testo) return;
  if (cloudAttivo()) {
    const frasi = spezzaInFrasi(testo);
    // si prova la prima frase: se il cloud non risponde, si passa al browser per
    // **tutto** il testo, senza ripetere il tentativo a ogni frase
    parlaCloud(frasi[0] || testo).then((ok) => {
      if (!ok) { parlaTesto(testo); return; }
      // Le frasi si dicono in fila, non tutte insieme: `speechSynthesis` accoda
      // da solo, ma la voce neurale e' un audio per volta. Si conta quelle
      // finite e si segnala il silenzio **solo** con l'ultima: segnalandolo a
      // ogni frase, l'ascolto continuo ripartirebbe a meta' discorso.
      const coda = frasi.slice(1);
      if (!coda.length) { avvisaFineParlato(); return; }
      let fatte = 0;
      coda.forEach(async (f) => {
        await parlaCloud(f);
        fatte += 1;
        if (fatte === coda.length) avvisaFineParlato();
      });
    });
    return;
  }
  parlaTesto(testo);
}

/** Chiede al server se la voce neurale c'è, e prepara l'interfaccia. */
async function caricaVoceCloud() {
  try {
    const r = await fetch('/api/voce/config');
    if (!r.ok) return;
    const d = await r.json();
    voceCloud.disponibile = !!d.cloud;
    // la trascrizione sul server ha bisogno della stessa chiave della sintesi:
    // se c'e', il microfono passa di la' invece che dal browser
    voceCloud.ascolto = !!d.ascolto;
    voceCloud.voci = d.voci || [];
    voceCloud.predefinita = d.predefinita;
    voceCloud.maxCaratteri = d.max_caratteri || 600;
    popolaVociCloud();
    mostraAvvisoRobotica();
  } catch (_e) { /* resta la voce del browser */ }
}

function popolaVociCloud() {
  const blocco = $('#voice-cloud-block');
  if (!blocco) return;
  blocco.hidden = !voceCloud.disponibile;
  if (!voceCloud.disponibile) return;

  const sel = $('#voice-cloud-voice');
  if (sel) {
    sel.innerHTML = voceCloud.voci
      .map((v) => `<option value="${esc(v.nome)}">${esc(v.etichetta)} · ${esc(v.genere)}</option>`)
      .join('');
    sel.value = voceCloudScelta();
  }
  const attivo = $('#voice-cloud');
  if (attivo) attivo.checked = localStorage.getItem('voceCloudOff') !== '1';
}

/** Anteprima del timbro: si sente com'è la voce prima di usarla davvero. */
function anteprimaTimbro(nome) {
  if (!window.speechSynthesis) return;
  try {
    speechSynthesis.cancel();
    const v = scegliVoce(nome);
    const t = TIMBRI[nome] || TIMBRI.chiara;
    const frasi = spezzaInFrasi('Ciao, sono il maggiordomo. Dimmi pure cosa ti serve.');
    frasi.forEach((frase, i) => {
      const ultima = i === frasi.length - 1;
      const u = new SpeechSynthesisUtterance(frase);
      try {
        if (v) u.voice = v;
      } catch (_e) { /* voce non assegnabile: si sente quella predefinita */ }
      u.lang = (v && v.lang) || 'it-IT';
      u.rate = t.rate * (ultima ? 0.97 : 1.0);
      u.pitch = t.pitch * (ultima ? 0.95 : 1.0);
      speechSynthesis.speak(u);
    });
  } catch (_e) { /* niente anteprima */ }
}

/** Anteprima brevissima di una voce scelta dall'elenco completo. */
function anteprimaVoce(v) {
  if (!window.speechSynthesis || !v) return;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance('Ciao, sono il maggiordomo.');
    try {
      u.voice = v;
    } catch (_e) { /* voce non assegnabile: si sente quella predefinita */ }
    u.lang = v.lang || 'it-IT';
    speechSynthesis.speak(u);
  } catch (_e) { /* niente anteprima */ }
}

/* ---------- suono di apertura ----------
   Un breve jingle sintetizzato con la Web Audio API: due note che salgono, nello
   stile dei loghi in streaming. Non serve nessun file audio da scaricare.

   I browser bloccano l'audio prima che l'utente tocchi la pagina: il suono non
   può partire all'apertura, per scelta loro. Si tenta subito, e se il contesto
   resta sospeso si riproduce al primo tocco o tasto, che è la prima occasione
   in cui è permesso. */
let audioCtx = null;

/** Il suono è attivo salvo esplicita disattivazione: la preferenza si ricorda. */
function suonoAttivo() {
  return localStorage.getItem('voceSuono') !== 'off';
}

function suonoApertura() {
  if (!suonoAttivo()) return;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  try {
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    // due note pulite, ognuna con la sua inviluppo: attacco rapido, coda corta
    const ora = audioCtx.currentTime;
    [[587.33, 0], [880, 0.13]].forEach(([hz, ritardo]) => {
      const osc = audioCtx.createOscillator();
      const vol = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = hz;
      vol.gain.setValueAtTime(0.0001, ora + ritardo);
      vol.gain.exponentialRampToValueAtTime(0.14, ora + ritardo + 0.02);
      vol.gain.exponentialRampToValueAtTime(0.0001, ora + ritardo + 0.34);
      osc.connect(vol).connect(audioCtx.destination);
      osc.start(ora + ritardo);
      osc.stop(ora + ritardo + 0.36);
    });
  } catch (_e) { /* audio non disponibile: la pagina funziona lo stesso */ }
}

let tingsuonato = false;

function tentaSuonoApertura() {
  if (tingsuonato) return;
  tingsuonato = true;
  suonoApertura();
}

// primo tocco o primo tasto: la prima occasione in cui il browser concede l'audio
['pointerdown', 'keydown'].forEach((ev) => {
  document.addEventListener(ev, tentaSuonoApertura, { once: true });
});

/* ---------- registrazione per il server ----------
   Il microfono consegna i campioni nell'ordine in cui li ha presi, a blocchi di
   `ASCOLTO_BLOCCO`. I valori sono tarati su un comando detto a voce: una frase
   breve, non una dettatura. */
const ASCOLTO_BLOCCO = 4096;         // campioni per blocco (~93 ms a 44,1 kHz)
const ASCOLTO_CAMPIONI = 16000;      // quello che vuole il servizio di ascolto
const ASCOLTO_FINE_MS = 1600;        // silenzio che chiude la frase
const ASCOLTO_ATTESA_MS = 6000;      // nessuno parla: si chiude
const ASCOLTO_MAX_MS = 15000;        // tetto, qualunque cosa succeda
const ASCOLTO_SILENZIO = 0.012;      // sopra questa ampiezza c'è voce

/** Quanto è "forte" un blocco di campioni, per distinguere voce e silenzio.
    Un picco, non una media: una media su blocchi quasi muti resta a zero anche
    quando si parla, e il silenzio non finirebbe mai. */
function ampiezza(campioni) {
  let massimo = 0;
  for (let i = 0; i < campioni.length; i++) {
    const v = campioni[i] < 0 ? -campioni[i] : campioni[i];
    if (v > massimo) massimo = v;
  }
  return massimo;
}

/** Porta i campioni alla frequenza voluta, mediando i valori vicini.

    Il microfono non consegna sempre 16 kHz: dipende dalla scheda. L'audio breve
    del servizio ne accetta una sola, quindi si riscrive qui invece di spedire
    qualcosa che potrebbe non essere letto. */
function aSediciKhz(campioni, frequenza) {
  if (!frequenza || frequenza === ASCOLTO_CAMPIONI) return campioni;
  const rapporto = frequenza / ASCOLTO_CAMPIONI;
  const quanti = Math.max(1, Math.round(campioni.length / rapporto));
  const fuori = new Float32Array(quanti);
  for (let i = 0; i < quanti; i++) {
    const inizio = Math.floor(i * rapporto);
    const fine = Math.min(campioni.length, Math.floor((i + 1) * rapporto));
    let somma = 0;
    for (let j = inizio; j < fine; j++) somma += campioni[j];
    fuori[i] = fine > inizio ? somma / (fine - inizio) : (campioni[inizio] || 0);
  }
  return fuori;
}

/** Impacchetta i campioni in un WAV PCM 16 bit mono.

    Il browser sa registrare in webm/opus, ma il servizio di ascolto non lo
    legge: WAV sì, e i campioni ci sono già in memoria. Scriverne l'intestazione
    costa poche righe e non aggiunge nessuna libreria. */
function wavDaCampioni(campioni, frequenza) {
  const dati = new ArrayBuffer(44 + campioni.length * 2);
  const vista = new DataView(dati);
  const scrivi = (pos, testo) => {
    for (let i = 0; i < testo.length; i++) vista.setUint8(pos + i, testo.charCodeAt(i));
  };
  scrivi(0, 'RIFF');
  vista.setUint32(4, 36 + campioni.length * 2, true);
  scrivi(8, 'WAVE');
  scrivi(12, 'fmt ');
  vista.setUint32(16, 16, true);            // dimensione del blocco "fmt "
  vista.setUint16(20, 1, true);             // PCM
  vista.setUint16(22, 1, true);             // un canale
  vista.setUint32(24, frequenza, true);
  vista.setUint32(28, frequenza * 2, true); // byte al secondo
  vista.setUint16(32, 2, true);             // byte per campione
  vista.setUint16(34, 16, true);            // bit per campione
  scrivi(36, 'data');
  vista.setUint32(40, campioni.length * 2, true);
  for (let i = 0; i < campioni.length; i++) {
    // il campione può uscire dai limiti e si taglia: senza, il valore avvolge
    // di segno e la conversione a intero esplode
    const v = Math.max(-1, Math.min(1, campioni[i]));
    vista.setInt16(44 + i * 2, Math.round(v * 32767), true);
  }
  return new Blob([dati], { type: 'audio/wav' });
}

let voce = { rec: null, attivo: false, ultimo: '', finale: '', registratore: null,
             aFineParlato: null, tempoVoce: null };
// Ascolto continuo ("hey Google"): il microfono resta aperto e i comandi partono
// solo dopo la parola di sveglia. `continuo` e' l'intenzione dell'utente,
// `sospeso` dice che in questo momento l'assistente sta parlando e non deve
// ascoltare se stesso (si sentirebbe, si riconoscerebbe e ripartirebbe da solo).
let ascoltoContinuo = { continuo: false, sospeso: false, ciclo: 0 };
const SVEGLIA_RIPRESA_MS = 700;   // pausa dopo la voce, prima di riascoltare
// Tetto alla pausa: se il browser non dice mai che la voce ha finito, il
// microfono deve riaccendersi lo stesso. Una conferma dura pochi secondi.
const TETTO_VOCE_MS = 20000;

function voceStato(msg, tipo = '') {
  const el = $('#voice-status');
  el.textContent = msg;
  el.dataset.tipo = tipo;
}

/** Esegue il comando dettato e ricarica le schede che il server indica. */
async function eseguiComando(testo) {
  voce.ultimo = testo;
  voceStato('Comando in corso…');
  try {
    const res = await api('/api/voice', { method: 'POST', body: { text: testo } });
    const box = $('#voice-result');
    box.hidden = false;
    box.className = 'voice-result ok';
    box.textContent = '✓ ' + res.message;

    // una ricerca apre subito la scheda Ricette con il testo cercato
    if (res.intent === 'recipe_search') {
      apriSezione('cucina');
      switchTab('recipes');
      $('#recipe-search').value = res.query;
      if (typeof renderRecipes === 'function') renderRecipes();
    } else if (res.open_recipe_form) {
      // "crea la ricetta carbonara" apre il modulo col nome gia' scritto: la
      // parte noiosa la fa la voce, ingredienti e preparazione restano all'utente.
      // Il pannello vocale va chiuso prima: sta a un livello piu' alto del modulo
      // e altrimenti lo coprirebbe.
      chiudiVoce();
      apriSezione('cucina');
      switchTab('recipes');
      // la voce ha già il nome (ed eventuali ingredienti con le dosi): si
      // chiede solo se scriverla a mano o cercarla online
      if (typeof nuovaRicetta === 'function') nuovaRicetta(res.name || '', res.items || []);
    } else {
      // un comando puo' toccare una scheda di un'altra area (dettare una spesa
      // mentre si e' nei Progetti): si apre prima l'area giusta, altrimenti la
      // scheda si attiverebbe sotto un'intestazione che non le appartiene
      for (const tab of res.reload || []) {
        const btn = $(`#tabs button[data-tab="${tab}"]`);
        if (btn) apreSezioneDella(btn.dataset.section);
        if (tab === 'pantry') renderPantry();
        if (tab === 'shopping') renderShopping();
        if (tab === 'profile') renderProfile();
        if (tab === 'magazzino') renderMagazzino();
      }
      if (res.reload && res.reload.length) switchTab(res.reload[0]);
      loadIngredientsDatalist();
    }
    voceStato('Fatto', 'ok');
    speak(res.message);
    toast(res.message);
  } catch (err) {
    const box = $('#voice-result');
    box.hidden = false;
    box.className = 'voice-result err';
    box.textContent = '✕ ' + err.message;
    voceStato('Non ho capito', 'err');
    speak('Non ho capito il comando');
  }
}

/** Avvia l'ascolto: prima dal server, e solo se non c'e' dal browser.

    Il riconoscimento del browser manda l'audio ai server di Google, e in molte
    case quel traffico e' bloccato (firewall, antivirus, VPN): Chrome risponde
    "network" e il microfono resta muto senza rimedio. Il server invece esce,
    quindi si registra qui e si fa trascrivere la'. Il browser si usa solo come
    ripiego, quando il server non ha la chiave. */
function ascolta() {
  // già in ascolto (dal server o dal browser): il clic ferma e fa partire la frase
  if (voce.attivo) { fermaAscolto(); return; }
  if (voceCloud.ascolto && ascoltaSulServer(esitoAscolto)) return;
  ascoltaDalBrowser();
}

/** Cosa fare col testo arrivato dal server nell'ascolto singolo. */
function esitoAscolto(d) {
  // 503: il server non ha la chiave. Non è un errore da mostrare, è il motivo
  // per cui esiste il ripiego sul riconoscimento del browser.
  if (d && d.ripiega) { ascoltaDalBrowser(); return; }
  if (!d || d.errore) return;
  const testo = (d.testo || '').trim();
  if (!testo) { voceStato('Non ho sentito nulla, riprova.'); return; }
  $('#voice-heard').textContent = testo;
  eseguiComando(testo);
}

function fermaAscolto() {
  if (voce.registratore) { voce.registratore.ferma(); return; }
  if (voce.attivo && voce.rec) {
    try { voce.rec.stop(); } catch (_e) { /* niente da fermare */ }
  }
}

/** Registra dal microfono e manda l'audio al server.

    Restituisce `false` se non c'e' modo di registrare qui (microfono negato o
    API assente): chi chiama ripiega sul riconoscimento del browser.
    `alTesto` riceve l'esito, anche quando il microfono viene negato: l'ascolto
    continuo deve saperlo per non restare in attesa di un ciclo mai partito. */
function ascoltaSulServer(alTesto) {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !Ctx) return false;

  navigator.mediaDevices.getUserMedia({ audio: true }).then((flusso) => {
    const ctx = new Ctx();
    const sorgente = ctx.createMediaStreamSource(flusso);
    const nodo = ctx.createScriptProcessor(ASCOLTO_BLOCCO, 1, 1);
    const pezzi = [];
    const inizio = Date.now();
    let parlatoDa = null;      // quando si è cominciata a sentire la voce
    let ultimoSuono = 0;       // quando si è sentito l'ultimo suono
    let chiuso = false;

    const chiudi = () => {
      if (chiuso) return;
      chiuso = true;
      try { nodo.disconnect(); } catch (_e) { /* già staccato */ }
      try { sorgente.disconnect(); } catch (_e) { /* già staccato */ }
      try { ctx.close(); } catch (_e) { /* già chiuso */ }
      flusso.getTracks().forEach((t) => t.stop());
      voce.registratore = null;
      voce.attivo = false;
      $('#mic').classList.remove('on');
    };
    const termina = () => {
      if (chiuso) return;
      chiudi();
      inviaAscolto(pezzi, ctx.sampleRate).then(alTesto);
    };

    nodo.onaudioprocess = (e) => {
      if (chiuso) return;
      const blocco = e.inputBuffer.getChannelData(0);
      pezzi.push(new Float32Array(blocco));
      const adesso = Date.now();
      if (ampiezza(blocco) > ASCOLTO_SILENZIO) {
        ultimoSuono = adesso;
        if (parlatoDa === null) parlatoDa = adesso;
      }
      // La frase finisce quando si smette di parlare: senza, il microfono
      // resterebbe aperto finché non lo si chiude a mano.
      if (parlatoDa !== null && adesso - ultimoSuono > ASCOLTO_FINE_MS) termina();
      else if (parlatoDa === null && adesso - inizio > ASCOLTO_ATTESA_MS) termina();
      else if (adesso - inizio > ASCOLTO_MAX_MS) termina();
    };

    sorgente.connect(nodo);
    nodo.connect(ctx.destination);   // serve solo perché il nodo elabori

    voce.registratore = { ferma: termina, annulla: chiudi };
    voce.attivo = true;
    $('#mic').classList.add('on');
    voceStato('Ti ascolto…');
    $('#voice-result').hidden = true;
    $('#voice-heard').textContent = '…';
  }).catch(() => {
    // microfono negato o assente: non è un guasto del server, si ripiega
    voceStato('Microfono non disponibile: consentilo nelle impostazioni del '
      + 'browser. Intanto puoi scrivere il comando qui sotto.', 'err');
    $('#voice-heard').hidden = true;
    const campo = $('#voice-text');
    if (campo) campo.focus();
    // l'ascolto continuo va fermato: senza questo avviso resterebbe "acceso"
    // ad aspettare un ciclo che non partirà mai, e il pulsante mentirebbe
    if (alTesto) alTesto({ errore: true });
  });
  return true;
}

/** Manda la registrazione al server e restituisce l'esito.

    L'esito è la risposta del server (`testo`, `sveglia`, `resto`) oppure
    `{ripiega: true}` se il server non ha la chiave, o `{errore: true}`. Cosa
    farne lo decide chi chiama: l'ascolto singolo esegue il comando, quello
    continuo guarda prima la parola di sveglia. Un solo percorso per la
    trascrizione, così le due modalità non possono divergere. */
function inviaAscolto(pezzi, frequenza) {
  const totale = pezzi.reduce((n, p) => n + p.length, 0);
  const uniti = new Float32Array(totale);
  let pos = 0;
  pezzi.forEach((p) => { uniti.set(p, pos); pos += p.length; });

  voceStato('Trascrivo…');
  const wav = wavDaCampioni(aSediciKhz(uniti, frequenza), ASCOLTO_CAMPIONI);
  return fetch('/api/voce/ascolta', {
    method: 'POST',
    headers: { 'Content-Type': 'audio/wav' },
    body: wav,
  }).then(async (r) => {
    // 503: il server non ha la chiave. Non è un errore da mostrare, è il
    // motivo per cui esiste il ripiego sul riconoscimento del browser.
    if (r.status === 503) return { ripiega: true };
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      voceStato(d.error || 'Non sono riuscito a trascrivere, riprova.', 'err');
      return { errore: true };
    }
    return d;
  }).catch(() => {
    voceStato('Non riesco a parlare con il server. Riprova.', 'err');
    return { errore: true };
  });
}

/** Il riconoscimento del browser: ripiego quando il server non può trascrivere. */
function ascoltaDalBrowser() {
  if (!SR) {
    voceStato('Questo browser non sa ascoltare: il riconoscimento vocale c\'è '
      + 'solo su Chrome, Edge e Safari. Qui puoi scrivere il comando qui sotto, '
      + 'e funziona lo stesso.', 'err');
    $('#voice-heard').hidden = true;
    return;
  }
  // Il primo clic apre il pannello e arriva qui: non c'e' ancora nessun
  // riconoscimento da fermare. Chiamare `stop()` su `null` solleva un errore che
  // nessuno vede, e il microfono resta muto senza dire perche': era il motivo per
  // cui sul PC non succedeva nulla, mentre dal telefono (dove il riconoscimento
  // parte dal secondo clic in poi) sembrava tutto a posto.
  if (voce.attivo && voce.rec) {
    try { voce.rec.stop(); } catch (_e) { /* niente da fermare */ }
    return;
  }

  const rec = new SR();
  voce.rec = rec;
  voce.finale = '';
  rec.lang = 'it-IT';
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;

  rec.onstart = () => {
    voce.attivo = true;
    $('#mic').classList.add('on');
    voceStato('Ti ascolto…');
    $('#voice-result').hidden = true;
  };
  rec.onresult = (e) => {
    let parziale = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      parziale += r[0].transcript;
      if (r.isFinal) {
        voce.finale = parziale.trim();
      }
    }
    $('#voice-heard').textContent = (voce.finale || parziale).trim() || '…';
  };
  rec.onerror = (e) => {
    // un annullamento voluto non è un errore da mostrare
    if (e.error === 'aborted') return;
    voceStato(messaggioMicrofono(e.error, voceCloud.ascolto), 'err');
    // Se il browser non può ascoltare, l'unica strada è scrivere: portare lì il
    // cursore evita di cercare il campo in fondo al pannello.
    if (e.error === 'network' || e.error === 'audio-capture'
        || e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      const campo = $('#voice-text');
      if (campo) campo.focus();
    }
  };
  rec.onend = () => {
    voce.attivo = false;
    $('#mic').classList.remove('on');
    const testo = (voce.finale || '').trim();
    voce.finale = '';
    if (testo) eseguiComando(testo);
    else if ($('#voice-status').dataset.tipo !== 'err') voceStato('Nessun comando riconosciuto, riprova.');
  };
  try {
    rec.start();
  } catch (err) {
    voce.attivo = false;
    // due clic rapidi arrivano qui: il riconoscimento era già partito
    voceStato('Il microfono è già in ascolto: parla, oppure riprova fra un istante.', 'err');
  }
}

/** Il messaggio da mostrare quando il microfono del browser non parte.

    Sta in una funzione a parte perche' "network" ha due letture diverse: se il
    server sa gia' trascrivere, l'ascolto passa di la' e all'utente basta
    scrivere; se il server **non** ha la chiave, quella e' la vera soluzione al
    blocco che sta vedendo — firewall o VPN che tagliano fuori i server di
    Google — e va detta adesso, non dopo.

    Non e' un dettaglio di messaggistica: senza questa seconda lettura, chi ha il
    browser bloccato e la chiave non configurata vede solo "scrivi qui sotto" e
    non sa che l'app avrebbe potuto ascoltare lo stesso. */
function messaggioMicrofono(errore, serverAscolta) {
  const messaggi = {
    'not-allowed': 'Microfono non autorizzato: consentilo nelle impostazioni del browser.',
    'service-not-allowed': 'Il browser non concede il riconoscimento vocale da questo '
      + 'indirizzo. Apri l\'app da http://localhost o da un indirizzo HTTPS.',
    'no-speech': 'Non ho sentito nulla, riprova.',
    'audio-capture': 'Nessun microfono trovato.',
    aborted: '',
  };
  if (errore === 'network' && !serverAscolta) {
    return 'Il browser non riesce a raggiungere il servizio di ascolto: di solito '
      + 'è un firewall, un antivirus o una VPN. Con la chiave della voce naturale '
      + 'Azure la trascrizione la fa il server, che non è bloccato: la chiave si '
      + 'imposta accanto al programma, prima di avviare l\'app. Intanto scrivi qui '
      + 'sotto: funziona lo stesso.';
  }
  if (errore === 'network') {
    return 'Il browser non riesce a raggiungere il servizio di ascolto: di solito '
      + 'è un firewall o una VPN che blocca il browser. Intanto scrivi qui sotto: '
      + 'funziona lo stesso.';
  }
  return messaggi[errore] || `Errore nel microfono (${errore || 'sconosciuto'})`;
}

function apriVoce() {
  tentaSuonoApertura();
  mostraAvvisoSicurezza();
  $('#voice').classList.remove('hidden');
  $('#voice-result').hidden = true;
  aggiornaSpiaAscolto();
  // con l'ascolto continuo acceso il microfono sta gia' girando: avviarne uno
  // singolo lo sovrapporrebbe, e due registrazioni insieme non si capiscono
  if (ascoltoContinuo.continuo) {
    voceStato('Ascolto continuo acceso: di\' «maggiordomo…»', 'ok');
    return;
  }
  $('#voice-heard').textContent = "Parla ora: ad esempio «aggiungi due chili di farina in dispensa».";
  ascolta();
}

/* ---------- ascolto continuo: la parola di sveglia ----------
   In stile "hey Google": il microfono resta aperto e i comandi partono solo dopo
   "maggiordomo". Serve perche' il caso d'uso e' cucinare con le mani occupate, e
   chiedere di toccare il pulsante a ogni frase lo vanifica.

   Perche' a cicli e non un microfono sempre aperto: l'audio breve di Azure
   accetta registrazioni di poche decine di secondi, non un flusso continuo. Si
   registra una frase, si manda, si guarda se conteneva la sveglia, e si riparte.

   Perche' la sveglia si riconosce sul server: la trascrizione la fa gia' lui, e
   tenerla li' significa che anche il ripiego sul browser usa la stessa logica,
   invece di una seconda versione che puo' divergere. */

function avviaAscoltoContinuo() {
  ascoltoContinuo.continuo = true;
  ascoltoContinuo.sospeso = false;
  aggiornaSpiaAscolto();
  cicloAscoltoContinuo();
}

function fermaAscoltoContinuo() {
  ascoltoContinuo.continuo = false;
  ascoltoContinuo.ciclo += 1;      // invalida il ciclo in corso
  ascoltoContinuo.sospeso = false;
  if (voce.registratore) voce.registratore.annulla();
  if (voce.attivo && voce.rec) {
    try { voce.rec.stop(); } catch (_e) { /* niente da fermare */ }
  }
  aggiornaSpiaAscolto();
  voceStato('Ascolto continuo spento.');
}

/** Mette in pausa il microfono e lo riaccende quando l'assistente ha finito.

    La pausa e' il punto: senza, il microfono riprende mentre la voce parla, si
    risente, riconosce se stesso e il ciclo non finisce piu'.

    C'e' anche un tempo di garanzia: in alcuni browser `onend` della sintesi non
    arriva mai (o arriva dopo minuti), e senza un tetto l'ascolto continuo
    resterebbe fermo per sempre con l'aria di essere acceso. */
function riprendiDopoLaVoce(poi) {
  ascoltoContinuo.sospeso = true;
  aggiornaSpiaAscolto();
  let fatto = false;
  const riprendi = () => {
    if (fatto) return;
    fatto = true;
    clearTimeout(voce.tempoVoce);
    voce.aFineParlato = null;
    ascoltoContinuo.sospeso = false;
    aggiornaSpiaAscolto();
    setTimeout(poi, SVEGLIA_RIPRESA_MS);
  };
  voce.aFineParlato = riprendi;
  return riprendi;
}

/** Dice una frase e riprende ad ascoltare solo quando ha finito. */
function parlaPoi(testo, poi) {
  const riprendi = riprendiDopoLaVoce(poi);
  speak(testo);
  if (!$('#voice-speak').checked) { riprendi(); return; }
  // il tetto e' generoso: una conferma di casa dura pochi secondi, e tagliarla
  // prima farebbe riascoltare l'assistente a meta' frase
  voce.tempoVoce = setTimeout(riprendi, TETTO_VOCE_MS);
}

/** Un giro: registra una frase, decide se era per l'app, e si richiama. */
function cicloAscoltoContinuo() {
  if (!ascoltoContinuo.continuo) return;
  if (ascoltoContinuo.sospeso) return;
  const mio = ++ascoltoContinuo.ciclo;

  const ancora = () => {
    if (mio !== ascoltoContinuo.ciclo || !ascoltoContinuo.continuo) return;
    setTimeout(cicloAscoltoContinuo, 250);
  };

  const esito = (d) => {
    if (mio !== ascoltoContinuo.ciclo || !ascoltoContinuo.continuo) return;
    if (!d || d.errore) { ascoltoContinuo.continuo = false; aggiornaSpiaAscolto(); return; }
    if (d.ripiega) {
      // senza la chiave la trascrizione la fa il browser: il ciclo resta lo
      // stesso, cambia solo chi ascolta
      cicloAscoltoDalBrowser(mio);
      return;
    }
    const testo = (d.testo || '').trim();
    if (!testo) { ancora(); return; }
    if (d.sveglia) {
      const comando = (d.resto || '').trim();
      voceStato('Sì?');
      if (!comando) {
        // chiamato e basta: si risponde, e si aspetta il comando
        parlaPoi('Dimmi.', ancora);
        return;
      }
      $('#voice-heard').textContent = comando;
      eseguiComandoContinuo(comando, ancora);
      return;
    }
    // frase non rivolta all'app: si tace, che e' il punto dell'ascolto continuo
    ancora();
  };

  if (voceCloud.ascolto && ascoltaSulServer(esito)) return;
  cicloAscoltoDalBrowser(mio);
}

/** Registra un giro col riconoscimento del browser (server senza chiave).

    La sveglia la riconosce il server anche qui, con `/api/voce/sveglia`:
    eseguire il comando in locale significherebbe una seconda copia della
    comprensione, libera di divergere da quella vera. */
function cicloAscoltoDalBrowser(mio) {
  if (!SR) { fermaAscoltoContinuo(); voceStato('Questo browser non sa ascoltare: l\'ascolto continuo ha bisogno di Chrome, Edge o Safari.', 'err'); return; }
  const rec = new SR();
  rec.lang = 'it-IT';
  rec.interimResults = false;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  const valido = () => mio === ascoltoContinuo.ciclo && ascoltoContinuo.continuo;
  rec.onresult = (e) => {
    const testo = (e.results[0] && e.results[0][0] ? e.results[0][0].transcript : '').trim();
    if (!testo || !valido()) return;
    api('/api/voce/sveglia', { method: 'POST', body: { text: testo } }).then((d) => {
      if (!valido()) return;
      if (d.sveglia && (d.resto || '').trim()) {
        $('#voice-heard').textContent = d.resto.trim();
        eseguiComandoContinuo(d.resto.trim(), () => setTimeout(cicloAscoltoContinuo, 250));
      } else {
        setTimeout(cicloAscoltoContinuo, 250);
      }
    }).catch(() => setTimeout(cicloAscoltoContinuo, 250));
  };
  rec.onerror = (e) => {
    if (e.error === 'aborted') return;
    // il browser non arriva al servizio di ascolto: si prova comunque a
    // ripartire, perche' un errore di rete puo' essere momentaneo
    setTimeout(cicloAscoltoContinuo, 1200);
  };
  rec.onend = () => { if (valido()) setTimeout(cicloAscoltoContinuo, 300); };
  try { rec.start(); } catch (_e) { setTimeout(cicloAscoltoContinuo, 600); }
}

/** Esegue il comando continuando ad ascoltare: la conferma a voce deve finire
    prima che il microfono riprenda, altrimenti l'assistente risente se stesso. */
async function eseguiComandoContinuo(comando, riprendi) {
  const riparti = riprendiDopoLaVoce(riprendi);
  try {
    await eseguiComando(comando);
  } finally {
    if (!$('#voice-speak').checked) { riparti(); return; }
    voce.tempoVoce = setTimeout(riparti, TETTO_VOCE_MS);
  }
}

/** Il pallino del microfono dice se l'ascolto continuo e' acceso. */
function aggiornaSpiaAscolto() {
  const acceso = ascoltoContinuo.continuo && !ascoltoContinuo.sospeso;
  const btn = $('#mic');
  if (btn) btn.classList.toggle('sempre', ascoltoContinuo.continuo);
  const spia = $('#voice-sempre-spia');
  if (spia) {
    spia.textContent = !ascoltoContinuo.continuo ? ''
      : (ascoltoContinuo.sospeso ? '⏸ in pausa (sto parlando)'
                                 : '● in ascolto: di\' «maggiordomo…»');
    spia.className = 'voice-avviso' + (acceso ? ' ok' : '');
  }
  const bottone = $('#voice-sempre');
  if (bottone) {
    bottone.textContent = ascoltoContinuo.continuo ? '⏹ Spegni ascolto continuo'
                                                   : '🟢 Ascolto continuo';
    bottone.classList.toggle('primary', !ascoltoContinuo.continuo);
  }
}

/** Avvisa quando il microfono non puo' funzionare, invece di lasciare che il
    pulsante non faccia nulla.

    Il riconoscimento vocale del browser pretende un contesto sicuro: HTTPS, o
    `localhost`. Da `http://192.168.1.x:12000` il browser non lo concede, e il
    pulsante resta muto senza dire perche'. Su Windows `localhost` va bene, dal
    telefono serve HTTPS — vedi la guida, sezione Tailscale.
*/
function mostraAvvisoSicurezza() {
  const el = $('#voice-avviso-sicurezza');
  if (!el) return;
  if (window.isSecureContext) { el.hidden = true; return; }
  el.hidden = false;
  el.textContent = 'Il microfono non funziona da questo indirizzo: il browser lo '
    + 'concede solo con HTTPS o da localhost. Sul computer usa '
    + 'http://localhost:12000. Dal telefono serve HTTPS (guarda la guida, '
    + 'sezione Tailscale). La voce in ascolto resta comunque disponibile dal '
    + 'pulsante, e puoi scrivere il comando qui sotto.';
}

/** Spiega perche' la voce e' quella meccanica del browser.

    Senza la chiave Azure l'app ripiega sulla voce di sistema, che e' la voce
    robotica che si sente: dirlo qui evita di cercare un guasto che non c'e',
    perche' l'app funziona — le manca solo la voce naturale.
*/
function mostraAvvisoRobotica() {
  const el = $('#voice-avviso-robotica');
  const rimando = $('#voice-chiave-manca');
  if (rimando) rimando.hidden = voceCloud.disponibile;
  if (!el) return;
  if (voceCloud.disponibile) { el.hidden = true; return; }
  el.hidden = false;
  el.textContent = 'La voce che senti \u00e8 quella meccanica del sistema: a '
    + 'questo server non \u00e8 stata data la chiave della voce naturale Azure. '
    + 'La chiave si imposta prima di avviare l\u2019app, accanto al programma '
    + '(segreto.sh, o le variabili AZURE_SPEECH_KEY e AZURE_SPEECH_REGION).';
}

function chiudiVoce() {
  // Con l'ascolto continuo acceso, chiudere il pannello non lo spegne: e' anzi
  // il modo d'uso normale (si cucina e si parla da un'altra stanza), e fermare
  // il microfono qui renderebbe la funzione inutile proprio quando serve.
  if (ascoltoContinuo.continuo) {
    $('#voice').classList.add('hidden');
    return;
  }
  if (voce.registratore) voce.registratore.annulla();
  if (voce.attivo && voce.rec) voce.rec.stop();
  if (window.speechSynthesis) speechSynthesis.cancel();
  $('#voice').classList.add('hidden');
}

$('#mic').addEventListener('click', apriVoce);
$('#voice-sempre').addEventListener('click', () => {
  if (ascoltoContinuo.continuo) fermaAscoltoContinuo();
  else avviaAscoltoContinuo();
});
$('#voice-close').addEventListener('click', chiudiVoce);
$('#voice-retry').addEventListener('click', ascolta);
$('#voice').addEventListener('click', (e) => { if (e.target.id === 'voice') chiudiVoce(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') chiudiVoce(); });
$('#voice-examples').addEventListener('click', (e) => {
  const frase = e.target.dataset.say;
  if (frase) eseguiComando(frase);
});

// riserva quando il microfono non c'è o ha sentito male: si corregge a mano
function inviaTestoVoce() {
  const testo = $('#voice-text').value.trim();
  if (!testo) return toast('Scrivi un comando');
  // il pannello resta aperto: la conferma del comando deve restare visibile
  eseguiComando(testo);
  $('#voice-text').value = '';
}
$('#voice-send').addEventListener('click', inviaTestoVoce);
$('#voice-text').addEventListener('keydown', (e) => { if (e.key === 'Enter') inviaTestoVoce(); });

// scelta del timbro: si salva la preferenza e si fa sentire subito l'anteprima
$('#voice-pick').value = timbroScelto();
$('#voice-pick').addEventListener('change', (e) => {
  localStorage.setItem('voceTimbro', e.target.value);
  // il timbro è una modalità automatica: annulla la voce scelta a mano, altrimenti
  // resterebbe quella e il timbro non avrebbe alcun effetto
  localStorage.removeItem('voceScelta');
  tts.voce = scegliVoce(e.target.value);
  aggiornaElencoVoci();
  $('#voice-all').value = '';
  anteprimaTimbro(e.target.value);
});

// voce di sistema scelta a mano dall'elenco completo: vince sul timbro
$('#voice-all').addEventListener('change', (e) => {
  if (e.target.value) {
    localStorage.setItem('voceScelta', e.target.value);
    tts.voce = voceEsplicita() || scegliVoce(timbroScelto());
    anteprimaVoce(tts.voce);
  } else {
    localStorage.removeItem('voceScelta');
    tts.voce = scegliVoce(timbroScelto());
  }
  aggiornaEtichetteVoci();
});

// voce neurale: si spegne, e la scelta resta
$('#voice-cloud').addEventListener('change', (e) => {
  localStorage.setItem('voceCloudOff', e.target.checked ? '0' : '1');
  if (e.target.checked) anteprimaCloud();
  else parlaTesto('Va bene, uso la voce del sistema.');
});

// voce neurale precisa, con anteprima: è una voce che si sceglie ascoltandola
$('#voice-cloud-voice').addEventListener('change', (e) => {
  localStorage.setItem('voceCloud', e.target.value);
  anteprimaCloud();
});

/** Fa sentire la voce neurale scelta: è l'unico modo per giudicarla. */
function anteprimaCloud() {
  if (!voceCloud.disponibile) return;
  voceCloud.sentite.clear();
  // si riprova: l'avviso torna disponibile, così una nuova prova può dire di nuovo
  // cosa non va invece di restare in silenzio per il resto della sessione
  voceCloud.avvisato = false;
  parlaCloud('Ciao, sono il maggiordomo. Dimmi pure cosa ti serve.');
}

// il jingle di apertura si può disattivare, e la scelta resta
$('#voice-ting').checked = suonoAttivo();
$('#voice-ting').addEventListener('change', (e) => {
  localStorage.setItem('voceSuono', e.target.checked ? 'on' : 'off');
  if (e.target.checked) suonoApertura();  // riaccendendolo si risente subito
});

/* ---------- datalist ---------- */
async function loadIngredientsDatalist() {
  const items = await api('/api/ingredients');
  $('#ingredient-list').innerHTML = items.map((i) => `<option value="${esc(i.name)}">`).join('');
}

/* ---------- accesso ----------
   Con case separate la password non e' un optional: senza, chiunque abbia il
   link scriverebbe il nome di un'altra casa e ne leggerebbe i dati. La sessione
   la tiene il server in un biscotto firmato, quindi qui non si salva nulla:
   si chiede a /api/session chi e' collegato. */
async function avviaAccesso() {
  mostraAccesso();
  await caricaCaseEsistenti();
  $('#accesso-form').addEventListener('submit', entra);
  $('#nuova-form').addEventListener('submit', creaCasa);
  $('#acc-crea').addEventListener('click', () => {
    $('#accesso-form').classList.add('hidden');
    $('#acc-crea').classList.add('hidden');
    $('#nuova-form').classList.remove('hidden');
    $('#new-nome').focus();
  });
  $('#new-annulla').addEventListener('click', () => {
    $('#nuova-form').classList.add('hidden');
    $('#accesso-form').classList.remove('hidden');
    $('#acc-crea').classList.remove('hidden');
    nascondiErrore('#new-errore');
  });
  $('#acc-nome').focus();
}

function mostraAccesso() {
  // la testata e le schede vivono dentro #app, che parte nascosto: basta
  // togliere la home, il resto resta com'e'
  // il titolo si scrive solo qui: sulla schermata di accesso la scheda del
  // browser mostrerebbe l'indirizzo invece del nome dell'app
  document.title = 'Il Maggiordomo';
  $('#accesso').classList.remove('hidden');
  $('#home').classList.add('hidden');
}

function nascondiErrore(sel) {
  const el = $(sel);
  el.hidden = true;
  el.textContent = '';
}

function mostraErrore(sel, messaggio) {
  const el = $(sel);
  el.textContent = messaggio;
  el.hidden = false;
}

async function caricaCaseEsistenti() {
  try {
    const caseEsistenti = await api('/api/houses');
    $('#case-esistenti').innerHTML = caseEsistenti
      .map((c) => `<option value="${esc(c.nome)}">`).join('');
  } catch (e) {
    // l'elenco e' solo un suggerimento: senza, si scrive il nome a mano
  }
}

async function entra(evento) {
  evento.preventDefault();
  nascondiErrore('#acc-errore');
  const bottone = $('#acc-entra');
  bottone.disabled = true;
  try {
    // gli spazi ai bordi li toglie anche il server: si tolgono qui perche' il
    // campo e' nascosto, e uno spazio incollato per sbaglio non si vede
    await api('/api/login', {
      method: 'POST',
      body: {
        nome: $('#acc-nome').value.trim(),
        password: $('#acc-password').value.trim(),
      },
    });
    sessionStorage.removeItem('maggiordomo-errore'); // la sessione e' nuova
    await avviaApp();
  } catch (e) {
    mostraErrore('#acc-errore', e.message || 'Nome o password non corretti');
    $('#acc-password').value = '';
    $('#acc-password').focus();
  } finally {
    bottone.disabled = false;
  }
}

// Rende visibile la password: il campo la nasconde, e su un telefono con la
// correzione automatica non si nota se una lettera e' cambiata o se e' rimasto
// uno spazio. Toglierlo dal campo e' l'unico modo di vedere cosa si e' scritto.
$('#acc-mostra').addEventListener('change', (e) => {
  $('#acc-password').type = e.target.checked ? 'text' : 'password';
});

async function creaCasa(evento) {
  evento.preventDefault();
  nascondiErrore('#new-errore');
  const bottone = $('#new-crea');
  bottone.disabled = true;
  try {
    await api('/api/houses', {
      method: 'POST',
      body: { nome: $('#new-nome').value, password: $('#new-password').value },
    });
    await avviaApp();
  } catch (e) {
    mostraErrore('#new-errore', e.message || 'Non è stato possibile creare la casa');
  } finally {
    bottone.disabled = false;
  }
}

async function esci() {
  await api('/api/logout', { method: 'POST', body: {} });
  location.reload();
}

/** Load della pagina: si entra solo se c'e' una casa collegata. */
async function avviaApp() {
  try {
    const sessione = await api('/api/session');
    if (!sessione.authenticated) {
      await avviaAccesso();
      return;
    }
    await init();
  } catch (e) {
    // se anche la sessione non risponde, meglio mostrare l'accesso che una
    // pagina vuota: il messaggio d'errore serve a capire cosa succede
    mostraAccesso();
    mostraErrore('#acc-errore', e.message || 'Il server non risponde');
  }
}

/* ---------- init ---------- */
async function init() {
  $('#accesso').classList.add('hidden');
  $('#home').classList.remove('hidden');
  $('#esci').addEventListener('click', esci);
  meta = await api('/api/meta');
  MEALS = meta.meals;
  allergenLabels = Object.fromEntries(meta.allergens.map((a) => [a.key, a.label]));
  $('#unit-list').innerHTML = meta.units.map((u) => `<option value="${u}">`).join('');
  $('#shop-cat').innerHTML = meta.categories.map((c) => `<option>${esc(c)}</option>`).join('');
  await loadIngredientsDatalist();
  photoFiles = await api('/api/recipe-images');
  profile = await api('/api/profile');
  // l'elenco delle voci arriva in modo asincrono: si legge ora e si rilegge
  // quando il browser segnala che è pronto
  caricaVoci();
  if (window.speechSynthesis) speechSynthesis.addEventListener?.('voiceschanged', caricaVoci);
  // la voce neurale si annuncia da sola se il server ce l'ha: è una richiesta
  // sola all'avvio, e serve a sapere se mostrare il blocco nel pannello
  caricaVoceCloud();
  await renderPlan();
  // il timer delle pulizie continua a contare anche dopo un ricaricamento: se
  // era attivo, la barra va rimessa subito
  mostraTimer();
  // La prima schermata resta la home: le domande iniziali (pasti, allergie,
  // preferite) riguardano la cucina, quindi si aprono entrando in Cucina e non
  // addosso a chi sta andando in Igiene o Progetti.
  mostraInvitoProfilo();
}

// All'avvio non si carica niente: prima si chiede al server chi e' collegato.
// `avviaApp` decide se mostrare la home o la schermata di accesso.
avviaApp();

/** Prima apertura: segnala sulla scheda Cucina che c'e' da completare il profilo. */
function mostraInvitoProfilo() {
  if (profile.onboarded && profile.fav_prompted) return;
  const card = $('.home-card[data-section="cucina"]');
  if (card && !card.querySelector('.home-todo')) {
    const tag = document.createElement('span');
    tag.className = 'home-todo';
    tag.textContent = 'Da completare';
    card.appendChild(tag);
  }
}

/** Le domande iniziali si aprono entrando in Cucina. */
function avviaProfiloSeServe() {
  if (!profile.onboarded) openOnboarding();
  // profilo gia' fatto ma preferite mai chieste (utenti precedenti): solo il passo 2
  else if (!profile.fav_prompted) openFavoritesStep();
}
