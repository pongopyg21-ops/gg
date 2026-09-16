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
  if (!res.ok) throw new Error((data && data.error) || `Errore ${res.status}`);
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
let meta = { units: [], categories: [], meals: [] };
let recipesCache = [];
let weekStart = startOfWeek(new Date());

function startOfWeek(d) {
  const x = new Date(d);
  const day = (x.getDay() + 6) % 7; // lunedì = 0
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
}

/* ---------- tabs ---------- */
$$('#tabs button').forEach((btn) => btn.addEventListener('click', () => {
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b === btn));
  $$('.tab').forEach((t) => t.classList.toggle('active', t.id === `tab-${btn.dataset.tab}`));
  if (btn.dataset.tab === 'plan') renderPlan();
  if (btn.dataset.tab === 'recipes') renderRecipes();
  if (btn.dataset.tab === 'pantry') renderPantry();
  if (btn.dataset.tab === 'shopping') renderShopping();
}));

/* ---------- PIANO ---------- */
async function renderPlan() {
  const days = [...Array(7)].map((_, i) => addDays(weekStart, i));
  $('#week-label').textContent = `${fmtDay(days[0])} – ${fmtDay(days[6])}`;
  const plan = await api(`/api/plan?start=${iso(days[0])}&end=${iso(days[6])}`);
  const today = iso(new Date());

  $('#plan-grid').innerHTML = days.map((d) => {
    const key = iso(d);
    const cells = MEALS.map((m) => {
      const entry = plan.find((p) => p.date === key && p.meal === m);
      return entry
        ? `<div class="slot filled" data-id="${entry.id}" title="Clicca per rimuovere">
             <span class="meal">${m} · ${entry.servings}p</span>
             <span class="rname">${esc(entry.recipe_name)}</span></div>`
        : `<div class="slot" data-date="${key}" data-meal="${m}">
             <span class="meal">${m}</span><span class="rname">+ aggiungi</span></div>`;
    }).join('');
    return `<div class="day ${key === today ? 'today' : ''}"><h3>${fmtDay(d)}</h3>${cells}</div>`;
  }).join('');
}

$('#plan-grid').addEventListener('click', async (e) => {
  const slot = e.target.closest('.slot');
  if (!slot) return;
  if (slot.classList.contains('filled')) {
    if (!confirm('Rimuovere questo pasto dal piano?')) return;
    await api(`/api/plan/${slot.dataset.id}`, { method: 'DELETE' });
    toast('Pasto rimosso');
  } else {
    openMealPicker(slot.dataset.date, slot.dataset.meal);
  }
  renderPlan();
});

async function openMealPicker(date, meal) {
  if (!recipesCache.length) recipesCache = await api('/api/recipes');
  if (!recipesCache.length) return toast('Crea prima una ricetta');
  showModal(`Aggiungi ${meal}`, `
    <div class="field"><label>Ricetta</label>
      <select id="pick-recipe">${recipesCache.map((r) => `<option value="${r.id}">${esc(r.name)}</option>`).join('')}</select>
    </div>
    <div class="field"><label>Porzioni</label><input id="pick-serv" type="number" min="1" value="2"></div>
    <button class="primary" id="pick-ok">Aggiungi al piano</button>
  `);
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
  recipesCache = await api('/api/recipes?full=1');
  const q = $('#recipe-search').value.toLowerCase();
  const list = recipesCache.filter((r) => r.name.toLowerCase().includes(q));
  $('#recipe-list').innerHTML = list.map((r) => `
    <div class="card">
      <h3>${esc(r.name)}</h3>
      <div class="meta">${r.servings} porzioni${r.time_minutes ? ` · ${r.time_minutes} min` : ''} · ${esc(r.difficulty)}</div>
      <div class="ings">${r.items.map((i) => `${esc(i.name)} ${i.quantity}${esc(i.unit)}`).join(' · ') || 'Nessun ingrediente'}</div>
      <div class="actions">
        <button data-edit="${r.id}">Modifica</button>
        <button data-del="${r.id}">Elimina</button>
      </div>
    </div>`).join('') || '<p>Nessuna ricetta. Creane una!</p>';
}

$('#recipe-search').addEventListener('input', renderRecipes);
$('#new-recipe').addEventListener('click', () => recipeForm(null));

$('#recipe-list').addEventListener('click', async (e) => {
  const editId = e.target.dataset.edit;
  const delId = e.target.dataset.del;
  if (editId) recipeForm(recipesCache.find((r) => r.id === Number(editId)));
  if (delId) {
    if (!confirm('Eliminare la ricetta?')) return;
    await api(`/api/recipes/${delId}`, { method: 'DELETE' });
    toast('Ricetta eliminata');
    renderRecipes();
  }
});

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
    <button class="primary" id="r-save">Salva</button>
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
      <td>${esc(i.name)}</td>
      <td>${esc(i.category)}</td>
      <td><input type="number" step="0.1" value="${i.quantity}" data-qty="${i.id}" style="width:90px"> ${esc(i.unit)}</td>
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
async function renderShopping() {
  const items = await api('/api/shopping');
  const groups = {};
  items.forEach((i) => (groups[i.category] = groups[i.category] || []).push(i));
  $('#shop-list').innerHTML = Object.entries(groups).map(([cat, list]) => `
    <div class="shop-group">
      <h3>${esc(cat)}</h3>
      ${list.map((i) => `
        <div class="shop-item ${i.checked ? 'done' : ''}">
          <input type="checkbox" data-check="${i.id}" ${i.checked ? 'checked' : ''}>
          <span class="name">${esc(i.name)}</span>
          <span class="qty">${i.quantity} ${esc(i.unit)}</span>
          <button data-del="${i.id}">🗑</button>
        </div>`).join('')}
    </div>`).join('') || '<p>Lista vuota. Generala dal piano settimanale o aggiungi voci manualmente.</p>';
}

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

/* ---------- datalist ---------- */
async function loadIngredientsDatalist() {
  const items = await api('/api/ingredients');
  $('#ingredient-list').innerHTML = items.map((i) => `<option value="${esc(i.name)}">`).join('');
}

/* ---------- init ---------- */
(async function init() {
  meta = await api('/api/meta');
  MEALS = meta.meals;
  $('#unit-list').innerHTML = meta.units.map((u) => `<option value="${u}">`).join('');
  $('#shop-cat').innerHTML = meta.categories.map((c) => `<option>${esc(c)}</option>`).join('');
  await loadIngredientsDatalist();
  await renderPlan();
})();
