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
   La pagina iniziale smista verso tre aree. Le schede della barra appartengono
   a un'area (`data-section`): aprendo un'area si mostrano solo le sue, così
   cucina, igiene e progetti restano separati invece di mischiarsi in un'unica
   barra piena di voci. */
const SEZIONI = {
  cucina:   { titolo: '\u{1F373} Cucina',   prima: 'plan' },
  igiene:   { titolo: '\u{1F9FD} Igiene',   prima: 'igiene' },
  progetti: { titolo: '\u{1F4CB} Progetti', prima: 'progetti' },
};

function apriSezione(nome) {
  const cfg = SEZIONI[nome];
  if (!cfg) return;
  $('#app-title').textContent = cfg.titolo;
  document.title = `${cfg.titolo} · Il Cliente`;
  // solo le schede dell'area aperta
  $$('#tabs button').forEach((b) => {
    b.classList.toggle('hidden', b.dataset.section !== nome);
  });
  $('#home').classList.add('hidden');
  $('#app').classList.remove('hidden');
  // il microfono e' una funzione della cucina: altrove non serve
  $('#mic').classList.toggle('hidden', nome !== 'cucina');
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
  $('#home').classList.remove('hidden');
  document.title = 'Il Cliente';
  window.scrollTo(0, 0);
}

$$('.home-card').forEach((card) => card.addEventListener('click', () => apriSezione(card.dataset.section)));
$('#to-home').addEventListener('click', tornaAlleSezioni);

/* ---------- tabs ---------- */
$$('#tabs button').forEach((btn) => btn.addEventListener('click', () => {
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${btn.dataset.tab}`));
  if (btn.dataset.tab === 'plan') renderPlan();
  if (btn.dataset.tab === 'recipes') renderRecipes();
  if (btn.dataset.tab === 'pantry') renderPantry();
  if (btn.dataset.tab === 'shopping') renderShopping();
  if (btn.dataset.tab === 'profile') renderProfile();
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

$('#gen-week').addEventListener('click', async () => {
  const end = addDays(weekStart, 6);
  try {
    const r = await api('/api/shopping/generate', {
      method: 'POST', body: { start: iso(weekStart), end: iso(end) },
    });
    toast(`${r.added} voci aggiunte alla lista della spesa`);
    $$('#tabs button').find((b) => b.dataset.tab === 'shopping').click();
  } catch (err) { toast(err.message); }
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
$('#new-recipe').addEventListener('click', () => recipeForm(null));

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

function recipeForm(recipe) {
  const r = recipe || { name: '', servings: 2, time_minutes: '', difficulty: 'facile', instructions: '', items: [] };
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
    <div class="modal-foot"><button class="primary" id="r-save">Salva</button></div>
  `);

  const rowsBox = $('#ing-rows');
  const addRow = (it = { name: '', quantity: '', unit: 'pz' }) => {
    const div = document.createElement('div');
    div.className = 'ing-row';
    div.innerHTML = `<input placeholder="Ingrediente" value="${esc(it.name)}" list="ingredient-list">
      <input type="number" step="0.1" placeholder="Qtà" value="${it.quantity}">
      <input placeholder="Unità" value="${esc(it.unit)}" list="unit-list">`;
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
async function renderPantry() {
  const items = await api('/api/pantry');
  const q = $('#pantry-search').value.toLowerCase();
  const list = items.filter((i) => i.name.toLowerCase().includes(q));
  $('#pantry-table tbody').innerHTML = list.map((i) => `
    <tr>
      <td data-label="Ingrediente">${esc(i.name)}</td>
      <td data-label="Categoria">${esc(i.category)}</td>
      <td data-label="Quantità"><input type="number" step="0.1" value="${i.quantity}" data-qty="${i.id}" class="qty-cell"> ${esc(i.unit)}</td>
      <td><button data-del="${i.id}">🗑</button></td>
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
    <p class="lead">${onBack ? 'Passo 3 di 3 · ' : ''}scegli le tue ricette preferite: le ritrovi
    con il filtro <strong>Solo preferite</strong> nella scheda Ricette. Puoi cambiare la scelta
    quando vuoi dalla scheda <strong>Profilo</strong>.</p>
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
    showModal('Benvenuto su Il Cliente', `
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
   su quella predefinita, meglio una voce diversa che nessuna voce. */
const TIMBRI = {
  chiara: {
    etichetta: 'Chiara',
    rate: 1.05, pitch: 1.06,
    // le voci note cambiano nome fra Windows, macOS, Android e Chrome
    nomi: ['alice', 'elsa', 'paola', 'federica', 'italiano', 'italian'],
  },
  profonda: {
    etichetta: 'Profonda',
    rate: 0.98, pitch: 0.82,
    nomi: ['cosimo', 'diego', 'luca', 'matteo', 'italiano', 'italian'],
  },
  calda: {
    etichetta: 'Calda',
    rate: 0.92, pitch: 0.96,
    nomi: ['alice', 'elsa', 'paola', 'italiano', 'italian'],
  },
};

let tts = { voce: null, caricate: false };

function timbroScelto() {
  return TIMBRI[localStorage.getItem('voceTimbro')] ? localStorage.getItem('voceTimbro') : 'chiara';
}

/** Sceglie la voce del sistema più vicina al timbro richiesto. */
function scegliVoce(timbro) {
  if (!window.speechSynthesis || !speechSynthesis.getVoices) return null;
  const voci = speechSynthesis.getVoices();
  if (!voci.length) return null;

  const it = voci.filter((v) => (v.lang || '').toLowerCase().startsWith('it'));
  const t = TIMBRI[timbro] || TIMBRI.chiara;
  for (const nome of t.nomi) {
    const trovata = it.find((v) => (v.name || '').toLowerCase().includes(nome));
    if (trovata) return trovata;
  }
  // la prima voce italiana, in mancanza di quella cercata
  return it[0] || null;
}

/** Rilegge le voci: su molte piattaforme l'elenco arriva in modo asincrono. */
function caricaVoci() {
  if (!window.speechSynthesis) return;
  tts.caricate = true;
  tts.voce = scegliVoce(timbroScelto());
  aggiornaEtichetteVoci();
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

function speak(text) {
  if (!$('#voice-speak').checked || !window.speechSynthesis) return;
  // la sintesi vocale è un di più: se non è disponibile o fallisce, il comando
  // resta comunque riuscito e non deve trasformarsi in un falso errore
  try {
    speechSynthesis.cancel();
    const timbro = timbroScelto();
    tts.voce = scegliVoce(timbro);
    const u = new SpeechSynthesisUtterance(text);
    if (tts.voce) u.voice = tts.voce;
    u.lang = (tts.voce && tts.voce.lang) || 'it-IT';
    u.rate = TIMBRI[timbro].rate;
    u.pitch = TIMBRI[timbro].pitch;
    speechSynthesis.speak(u);
  } catch (_e) { /* voce non disponibile: si prosegue */ }
}

/** Anteprima del timbro: si sente com'è la voce prima di usarla davvero. */
function anteprimaTimbro(nome) {
  if (!window.speechSynthesis) return;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance("Ciao, sono il tuo assistente in cucina.");
    const v = scegliVoce(nome);
    if (v) u.voice = v;
    u.lang = (v && v.lang) || 'it-IT';
    u.rate = TIMBRI[nome].rate;
    u.pitch = TIMBRI[nome].pitch;
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

let voce = { rec: null, attivo: false, ultimo: '' };

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
      switchTab('recipes');
      $('#recipe-search').value = res.query;
      if (typeof renderRecipes === 'function') renderRecipes();
    } else {
      for (const tab of res.reload || []) {
        if (tab === 'pantry') renderPantry();
        if (tab === 'shopping') renderShopping();
        if (tab === 'profile') renderProfile();
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

/** Avvia l'ascolto; se il browser non supporta l'API, si può comunque digitare. */
function ascolta() {
  if (!SR) {
    voceStato("Questo browser non supporta il riconoscimento vocale: scrivi il comando qui sotto.", 'err');
    $('#voice-heard').hidden = true;
    return;
  }
  if (voce.attivo) { voce.rec.stop(); return; }

  voce.rec = new SR();
  voce.rec.lang = 'it-IT';
  voce.rec.interimResults = true;
  voce.rec.continuous = false;

  voce.rec.onstart = () => {
    voce.attivo = true;
    $('#mic').classList.add('on');
    voceStato('Ti ascolto…');
    $('#voice-result').hidden = true;
  };
  voce.rec.onresult = (e) => {
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
  voce.rec.onerror = (e) => {
    const messaggi = {
      'not-allowed': 'Microfono non autorizzato: consentilo nelle impostazioni del browser.',
      'no-speech': 'Non ho sentito nulla, riprova.',
      'audio-capture': 'Nessun microfono trovato.',
      network: 'Riconoscimento non disponibile senza connessione.',
    };
    voceStato(messaggi[e.error] || 'Errore nel microfono', 'err');
  };
  voce.rec.onend = () => {
    voce.attivo = false;
    $('#mic').classList.remove('on');
    const testo = (voce.finale || '').trim();
    voce.finale = '';
    if (testo) eseguiComando(testo);
    else voceStato('Nessun comando riconosciuto');
  };
  try { voce.rec.start(); } catch (_e) { /* già in ascolto */ }
}

function apriVoce() {
  tentaSuonoApertura();
  $('#voice').classList.remove('hidden');
  $('#voice-result').hidden = true;
  $('#voice-heard').textContent = "Parla ora: ad esempio «aggiungi due chili di farina in dispensa».";
  ascolta();
}

function chiudiVoce() {
  if (voce.attivo && voce.rec) voce.rec.stop();
  if (window.speechSynthesis) speechSynthesis.cancel();
  $('#voice').classList.add('hidden');
}

$('#mic').addEventListener('click', apriVoce);
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
  tts.voce = scegliVoce(e.target.value);
  anteprimaTimbro(e.target.value);
});

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

/* ---------- init ---------- */
(async function init() {
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
  await renderPlan();
  // La prima schermata resta la home: le domande iniziali (pasti, allergie,
  // preferite) riguardano la cucina, quindi si aprono entrando in Cucina e non
  // addosso a chi sta andando in Igiene o Progetti.
  mostraInvitoProfilo();
})();

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
