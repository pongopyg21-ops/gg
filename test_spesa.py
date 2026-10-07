"""Lista della spesa, quote per giorno e condivisione.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_voce_spesa_mostra_giacenza_in_dispensa(client):
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 100, "unit": "g"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    v = voce_spesa(client, "Pasta")
    assert v["pantry"] == {"quantity": 100, "unit": "g"}
    assert v["quantity"] == pytest.approx(300)  # già al netto della dispensa

def test_voce_spesa_converte_la_giacenza_nell_unita_della_lista(client):
    """Dispensa in kg, lista in g: la giacenza va riportata in grammi."""
    rid = ricetta(client, "Farina", 2, [{"name": "Farina", "quantity": 500, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Farina", "quantity": 0.2, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    v = voce_spesa(client, "Farina")
    assert v["pantry"] == {"quantity": 200, "unit": "g"}
    assert v["quantity"] == pytest.approx(300)

def test_dispensa_che_copre_tutto_non_entra_in_lista(client):
    """Se la dispensa basta, non c'è nulla da comprare e la voce non compare."""
    rid = ricetta(client, "Farina", 2, [{"name": "Farina", "quantity": 500, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Farina", "quantity": 2, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    assert client.get("/api/shopping").get_json() == []

def test_voce_spesa_somma_piu_giacenze_convertibili(client):
    rid = ricetta(client, "Riso", 2, [{"name": "Riso", "quantity": 400, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Riso", "quantity": 100, "unit": "g"})
    client.post("/api/pantry", json={"name": "Riso", "quantity": 0.2, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    assert voce_spesa(client, "Riso")["pantry"] == {"quantity": 300, "unit": "g"}

def test_voce_spesa_manuale_senza_dispensa(client):
    client.post("/api/shopping", json={"name": "Detersivo", "quantity": 1, "unit": "pz"})
    assert voce_spesa(client, "Detersivo")["pantry"] is None

def test_voce_spesa_con_unita_non_confrontabili(client):
    """Dispensa in pezzi, lista in grammi: si mostra la giacenza nella sua unità."""
    client.post("/api/pantry", json={"name": "Uova", "quantity": 6, "unit": "pz"})
    client.post("/api/shopping", json={"name": "Uova", "quantity": 200, "unit": "g"})

    assert voce_spesa(client, "Uova")["pantry"] == {"quantity": 6, "unit": "pz"}

def test_voce_spesa_dispensa_aggiunta_dopo_la_generazione(client):
    """La giacenza è calcolata a ogni lettura, non congelata alla generazione."""
    client.post("/api/shopping", json={"name": "Burro", "quantity": 250, "unit": "g"})
    assert voce_spesa(client, "Burro")["pantry"] is None

    client.post("/api/pantry", json={"name": "Burro", "quantity": 250, "unit": "g"})
    assert voce_spesa(client, "Burro")["pantry"] == {"quantity": 250, "unit": "g"}

def test_ogni_voce_riporta_i_giorni_in_cui_serve(client):
    """Un ingrediente usato in due giorni compare in entrambi con la sua quota."""
    a = ricetta(client, "A", 2, [{"name": "Pomodori", "quantity": 200, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Pomodori", "quantity": 300, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-17", "meal": "cena", "recipe_id": b, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-20"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["name"] == "Pomodori"
    assert [d["date"] for d in voce["days"]] == ["2026-09-14", "2026-09-17"]
    assert [d["quantity"] for d in voce["days"]] == [200, 300]

def test_la_somma_dei_giorni_uguale_il_totale(client):
    """Invariante: la somma delle quote giornaliere è il totale da comprare.

    Se divergessero, la vista per giorno contraddirebbe quella completa.
    """
    a = ricetta(client, "A", 2, [{"name": "Farina", "quantity": 300, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-18", "meal": "cena", "recipe_id": b, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-20"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(500)
    assert sum(d["quantity"] for d in voce["days"]) == pytest.approx(voce["quantity"])

def test_dispensa_scalata_dai_giorni_piu_vicini(client):
    """La dispensa copre i primi pasti: i giorni lontani restano da comprare.

    Serve a rispondere proprio alla perplessità: il lunedì non si compra per la
    domenica se in casa c'è già abbastanza per i primi giorni.
    """
    a = ricetta(client, "A", 2, [{"name": "Riso", "quantity": 400, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Riso", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-20", "meal": "cena", "recipe_id": b, "servings": 2})
    client.post("/api/pantry", json={"name": "Riso", "quantity": 400, "unit": "g"})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-20"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(400)  # 800 g - 400 g in casa
    giorni = {d["date"]: d["quantity"] for d in voce["days"]}
    assert "2026-09-14" not in giorni          # coperto dalla dispensa
    assert giorni["2026-09-20"] == pytest.approx(400)

def test_dispensa_che_copre_un_giorno_solo(client):
    """Con dispensa parziale il giorno vicino si riduce, quello lontano no."""
    a = ricetta(client, "A", 2, [{"name": "Pasta", "quantity": 300, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Pasta", "quantity": 300, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": b, "servings": 2})
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 100, "unit": "g"})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-16"})
    [voce] = client.get("/api/shopping").get_json()
    giorni = {d["date"]: d["quantity"] for d in voce["days"]}
    assert giorni["2026-09-14"] == pytest.approx(200)  # 300 - 100 in casa
    assert giorni["2026-09-16"] == pytest.approx(300)  # intatto
    assert sum(giorni.values()) == pytest.approx(voce["quantity"])

def test_generazione_ripetuta_tiene_le_quote_giornaliere(client):
    """Rigenerare più volte non gonfia né il totale né le quote giornaliere."""
    rid = ricetta(client, "A", 2, [{"name": "Zucchine", "quantity": 250, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})
    client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(250)
    assert voce["days"][0]["quantity"] == pytest.approx(250)

def test_voce_manuale_non_ha_giorni(client):
    client.post("/api/shopping", json={"name": "Carta da cucina", "quantity": 1, "unit": "pz"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["days"] == []

def test_voci_deperibili_segnalate(client):
    """Frutta e verdura, carne e pesce e latticini sono segnalati come deperibili."""
    a = ricetta(client, "A", 2, [{"name": "Spinaci", "quantity": 200, "unit": "g",
                                  "category": "Frutta e Verdura"}])
    b = ricetta(client, "B", 2, [{"name": "Farina", "quantity": 200, "unit": "g",
                                  "category": "Dispensa"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": b, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-15"})
    voci = {v["name"]: v for v in client.get("/api/shopping").get_json()}
    assert voci["Spinaci"]["perishable"] is True
    assert voci["Farina"]["perishable"] is False

def test_unita_convertita_anche_nei_giorni(client):
    """Ricetta in kg, voce mostrata in g: le quote giornaliere seguono l'unità."""
    rid = ricetta(client, "A", 2, [{"name": "Farina", "quantity": 1, "unit": "kg"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-14"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["unit"] == "kg"
    assert voce["days"][0]["unit"] == "kg"
    assert voce["days"][0]["quantity"] == pytest.approx(1)

def test_lista_completa_serve_tutti_i_giorni(client):
    """Regressione: il filtro non deve dipendere dal giorno richiesto."""
    a = ricetta(client, "A", 2, [{"name": "Patate", "quantity": 500, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-14"})

    items = client.get("/api/shopping").get_json()
    assert len(items) == 1
    assert items[0]["days"][0]["date"] == "2026-09-14"

def test_voce_preesistente_senza_giorni_non_contraddice_il_totale(client):
    """Una voce nata senza ripartizione resta coerente col totale.

    E' il caso della lista già in uso: il totale c'è, i giorni no. Al momento
    della lettura la ripartizione viene riscalata sul totale effettivo.
    """
    # voce creata a mano con quantità: la generazione non la tocca
    client.post("/api/shopping", json={"name": "Farina", "quantity": 100, "unit": "g"})
    rid = ricetta(client, "A", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})
    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(100)  # la voce manuale resta com'è
    assert sum(d["quantity"] for d in voce["days"]) == pytest.approx(100)

def test_generazione_ripetuta_non_amplifica_le_quote(client):
    """Rigenerare più volte non deve gonfiare né le quote né il totale."""
    rid = ricetta(client, "A", 2, [{"name": "Olio", "quantity": 50, "unit": "ml"}])
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": rid, "servings": 2})
    for _ in range(3):
        client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})

    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(50)
    assert sum(d["quantity"] for d in voce["days"]) == pytest.approx(50)

def test_condivisione_di_oggi_mostra_le_voci_di_oggi(client):
    """Senza parametri la scheda e' la spesa di oggi: le stesse voci della lista."""
    _spesa_su_giorni(client, "2026-09-14", "2026-09-18")
    d = client.get("/api/shopping/condividi?date=2026-09-14").get_json()
    assert "2026" not in d["titolo"] or "settembre" in d["titolo"]  # data leggibile
    assert "luned" in d["titolo"].lower()
    nomi = [v["name"] for g in d["gruppi"] for v in g["voci"]]
    assert nomi == ["Alimento0"]           # solo quello di oggi, non l'altro giorno

def test_condivisione_di_un_giorno_prende_la_quota_di_quel_giorno(client):
    """Condividendo un giorno, la quantita' e' quella quota, non il totale."""
    a = ricetta(client, "A", 2, [{"name": "Pomodori", "quantity": 200, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Pomodori", "quantity": 300, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-18", "meal": "cena", "recipe_id": b, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-18"})

    d = client.get("/api/shopping/condividi?giorno=2026-09-14").get_json()
    [voce] = [v for g in d["gruppi"] for v in g["voci"]]
    assert voce["name"] == "Pomodori"
    assert voce["quota"]["quantity"] == pytest.approx(200)
    assert "200" in d["testo"]

def test_condivisione_di_un_intervallo_somma_i_giorni(client):
    """Un intervallo prende tutte le voci che servono in quei giorni, col totale."""
    _spesa_su_giorni(client, "2026-09-14", "2026-09-16", "2026-09-20")
    d = client.get("/api/shopping/condividi?dal=2026-09-14&al=2026-09-16").get_json()
    nomi = sorted(v["name"] for g in d["gruppi"] for v in g["voci"])
    assert nomi == ["Alimento0", "Alimento1"]     # il 20 resta fuori
    assert d["totale_voci"] == 2
    assert "dal" in d["titolo"]

def test_condivisione_esclude_le_voci_gia_spuntate(client):
    """Chi compra non deve ricomprare quello che e' gia' nel carrello."""
    _spesa_su_giorni(client, "2026-09-14", "2026-09-16")
    [da_spuntare] = [v for v in client.get("/api/shopping").get_json()
                     if v["name"] == "Alimento0"]
    client.patch(f"/api/shopping/{da_spuntare['id']}", json={"checked": True})

    d = client.get("/api/shopping/condividi?dal=2026-09-14&al=2026-09-16").get_json()
    nomi = [v["name"] for g in d["gruppi"] for v in g["voci"]]
    assert nomi == ["Alimento1"]

def test_condivisione_tiene_le_voci_aggiunte_a_mano(client):
    """Le voci senza giorni non si possono escludere: restano sempre in scheda."""
    _spesa_su_giorni(client, "2026-09-14", "2026-09-16")
    client.post("/api/shopping", json={"name": "Carta da cucina", "quantity": 1, "unit": "pz"})
    d = client.get("/api/shopping/condividi?dal=2026-09-14&al=2026-09-16").get_json()
    nomi = [v["name"] for g in d["gruppi"] for v in g["voci"]]
    assert "Carta da cucina" in nomi

def test_condivisione_raggruppa_per_categoria(client):
    _spesa_su_giorni(client, "2026-09-14")
    d = client.get("/api/shopping/condividi?giorno=2026-09-14").get_json()
    assert all("categoria" in g and g["voci"] for g in d["gruppi"])
    assert d["gruppi"][0]["categoria"] == "Altro"   # la categoria di default

def test_condivisione_testo_contiene_intestazione_e_voci(client):
    _spesa_su_giorni(client, "2026-09-14")
    d = client.get("/api/shopping/condividi?giorno=2026-09-14").get_json()
    assert "Alimento0" in d["testo"]
    assert "[ ]" in d["testo"]                     # caselle da spuntare
    assert "Il Maggiordomo" in d["testo"]          # il marchio c'e'
    assert d["titolo"] in d["testo"]

def test_condivisione_nota_facoltativa(client):
    _spesa_su_giorni(client, "2026-09-14")
    d = client.get("/api/shopping/condividi?giorno=2026-09-14&nota=prendi%20il%20pane").get_json()
    assert d["nota"] == "prendi il pane"
    assert "prendi il pane" in d["testo"]
    senza = client.get("/api/shopping/condividi?giorno=2026-09-14").get_json()
    assert senza["nota"] == ""

def test_condivisione_conta_i_deperibili(client):
    rid = ricetta(client, "A", 2, [{"name": "Spinaci", "quantity": 200, "unit": "g",
                                    "category": "Frutta e Verdura"}])
    client.post("/api/plan", json={"date": "2026-09-14", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-14", "end": "2026-09-14"})
    d = client.get("/api/shopping/condividi?giorno=2026-09-14").get_json()
    assert d["deperibili"] == 1

def test_condivisione_data_storta_e_un_errore(client):
    """Una data storta non deve diventare una scheda vuota che sembra «niente»."""
    r = client.get("/api/shopping/condividi?giorno=14-09-2026")
    assert r.status_code == 400
    assert "Data non valida" in r.get_json()["error"]

def test_condivisione_intervallo_rovesciato_e_un_errore(client):
    r = client.get("/api/shopping/condividi?dal=2026-09-18&al=2026-09-14")
    assert r.status_code == 400
    assert "precedere" in r.get_json()["error"]

def test_condivisione_solo_al_vale_come_un_giorno(client):
    """`al` da solo non si ignora in silenzio: vale come un giorno solo."""
    _spesa_su_giorni(client, "2026-09-14", "2026-09-18")
    d = client.get("/api/shopping/condividi?al=2026-09-14").get_json()
    nomi = [v["name"] for g in d["gruppi"] for v in g["voci"]]
    assert nomi == ["Alimento0"]

def test_condivisione_richiede_l_accesso(anon):
    """La lista e' un dato della casa: la scheda non si serve senza sessione."""
    r = anon.get("/api/shopping/condividi")
    assert r.status_code == 401

def test_condivisione_stesse_voci_della_lista(client):
    """La scheda non e' una seconda verita': le voci sono quelle della lista.

    Se divergessero, si manderebbe a chi compra una lista diversa da quella a
    schermo, ed e' il difetto che questo endpoint deve rendere impossibile.
    """
    _spesa_su_giorni(client, "2026-09-14", "2026-09-18")
    lista = {v["name"] for v in client.get("/api/shopping").get_json() if not v["checked"]}
    d = client.get("/api/shopping/condividi?dal=2026-09-14&al=2026-09-18").get_json()
    scheda = {v["name"] for g in d["gruppi"] for v in g["voci"]}
    assert scheda == lista

def test_la_scheda_ha_il_pulsante_e_il_logo(client):
    """Il pulsante «Condividi» esiste, e la scheda porta il logo dell'app.

    Si esegue `schedaSpesaHtml` vera con node: la scheda deve contenere il
    marchio e l'icona, non solo dei numeri.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "shop-share" in client.get("/static/index.html").get_data(as_text=True)
    codice = _estrai_funzione_js(js, "schedaSpesaHtml")
    preludio = "function esc(s) { return String(s ?? ''); }\n"
    dati = json.dumps({
        "titolo": "Spesa di lunedi 14 settembre",
        "sottotitolo": "tutto quello che serve lunedi 14 settembre",
        "nota": "prendi il pane", "totale_voci": 1, "deperibili": 0,
        "gruppi": [{"categoria": "Altro", "voci": [
            {"name": "Latte", "quantity": 1, "unit": "l", "quota": None}]}],
    })
    coda = f"console.log(JSON.stringify(schedaSpesaHtml({dati})));"
    html = _esegui_node(preludio + codice + coda)
    assert "Il Maggiordomo" in html
    assert "/static/icons/icona.svg" in html     # il logo
    assert "Latte" in html and "prendi il pane" in html

def test_il_canvas_della_scheda_si_disegna(client):
    """`schedaSpesaCanvas` disegna davvero: si esegue con node e un canvas finto.

    Un test sulle stringhe non si accorgerebbe se la funzione non disegnasse
    nulla. Qui si conta che le chiamate di disegno avvengano e che il logo ci
    sia (i due rettangoli della croce).
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    codice = _estrai_funzione_js(js, "schedaSpesaCanvas")
    preludio = """
let chiamate = 0, fillRect = 0, fillText = 0, testi = [];
function ctx() {
  const c = { fillStyle:'', strokeStyle:'', font:'', textAlign:'', lineWidth:1 };
  for (const m of ['fillRect','strokeRect','beginPath','moveTo','lineTo','arcTo','closePath',
                   'fill','stroke','save','restore','clip','createLinearGradient','rect','roundRect']) {
    c[m] = (...a) => { chiamate++; if (m === 'fillRect') fillRect++; };
  }
  c.createLinearGradient = () => ({ addColorStop() {} });
  c.fillText = (t) => { fillText++; testi.push(String(t)); };
  c.measureText = () => ({ width: 10 });
  return c;
}
const document = { createElement: () => ({ width:0, height:0, getContext: ctx }) };
"""
    dati = json.dumps({
        "titolo": "Spesa di oggi", "sottotitolo": "quello che serve",
        "nota": "", "totale_voci": 2, "deperibili": 0,
        "gruppi": [
            {"categoria": "Altro", "voci": [{"name": "Latte", "quantity": 1, "unit": "l"}]},
            {"categoria": "Dispensa", "voci": [{"name": "Pasta", "quantity": 500, "unit": "g"}]},
        ],
    })
    coda = f"const cv = schedaSpesaCanvas({dati}); console.log(JSON.stringify({{chiamate, fillRect, fillText, testi}}));"
    d = _esegui_node(preludio + codice + coda)
    assert d["chiamate"] > 20
    assert d["fillText"] >= 5
    assert any("Latte" in t for t in d["testi"])
    assert any("IL MAGGIORDOMO" in t for t in d["testi"])

def test_aggiungere_al_piano_aggiorna_la_spesa_da_sola(client):
    """Pianificare basta: la lista si aggiorna senza premere "rigenera"."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    items = client.get("/api/shopping").get_json()
    assert [i["name"] for i in items] == ["Pasta"]
    assert items[0]["quantity"] == pytest.approx(400)

def test_togliere_dal_piano_toglie_dalla_spesa(client):
    """Eliminare un pasto porta via i suoi ingredienti, senza altri comandi."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert client.get("/api/shopping").get_json()

    [pasto] = client.get("/api/plan").get_json()
    client.delete(f"/api/plan/{pasto['id']}")
    assert client.get("/api/shopping").get_json() == []

def test_cambiare_ricetta_nello_stesso_pasto_sostituisce_gli_ingredienti(client):
    """Lo stesso slot aggiornato con un'altra ricetta non lascia i vecchi."""
    a = ricetta(client, "A", 2, [{"name": "Pomodoro", "quantity": 500, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Zucchine", "quantity": 300, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": b, "servings": 2})

    assert [i["name"] for i in client.get("/api/shopping").get_json()] == ["Zucchine"]

def test_spesa_automatica_rispetta_la_dispensa(client):
    """L'aggiornamento automatico scala comunque quello che c'e' in casa."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 0.1, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    items = client.get("/api/shopping").get_json()
    assert items[0]["quantity"] == pytest.approx(300)

def test_spesa_coperta_dalla_dispensa_non_compare(client):
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 200, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 1, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    assert client.get("/api/shopping").get_json() == []

def test_piano_multiplo_confluisce_in_una_voce(client):
    """Due pasti con lo stesso ingrediente si sommano in una riga sola."""
    a = ricetta(client, "A", 2, [{"name": "Riso", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-17", "meal": "cena", "recipe_id": a, "servings": 2})

    [voce] = client.get("/api/shopping").get_json()
    assert voce["quantity"] == pytest.approx(400)

def test_rigenerazione_senza_piano_non_esplode(client):
    """L'endpoint resta utilizzabile: senza pasti risponde 404, non 500."""
    assert client.post("/api/shopping/generate", json={}).status_code == 404

def test_modificare_una_ricetta_aggiorna_la_spesa(client):
    """Cambiare le dosi di una ricetta gia' in piano vale subito in lista."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert client.get("/api/shopping").get_json()[0]["quantity"] == pytest.approx(200)

    client.put(f"/api/recipes/{rid}", json={
        "name": "Pasta", "servings": 2,
        "items": [{"name": "Pasta", "quantity": 500, "unit": "g"}]})
    assert client.get("/api/shopping").get_json()[0]["quantity"] == pytest.approx(500)

def test_togliere_un_ingrediente_dalla_ricetta_lo_toglie_dalla_spesa(client):
    """Un ingrediente rimosso dalla ricetta non resta in lista come orfano."""
    rid = ricetta(client, "Pasta", 2, [
        {"name": "Pasta", "quantity": 200, "unit": "g"},
        {"name": "Basilico", "quantity": 1, "unit": "pz"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert len(client.get("/api/shopping").get_json()) == 2

    client.put(f"/api/recipes/{rid}", json={
        "name": "Pasta", "servings": 2,
        "items": [{"name": "Pasta", "quantity": 200, "unit": "g"}]})
    assert [i["name"] for i in client.get("/api/shopping").get_json()] == ["Pasta"]

def test_eliminare_una_ricetta_in_piano_pulisce_la_spesa(client):
    """Eliminare la ricetta porta via i suoi ingredienti dalla lista."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert client.get("/api/shopping").get_json()

    client.delete(f"/api/recipes/{rid}")
    assert client.get("/api/shopping").get_json() == []

def test_mettere_in_dispensa_toglie_dalla_spesa(client):
    """Quello che si compra e si mette via non deve restare in lista."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert client.get("/api/shopping").get_json()[0]["quantity"] == pytest.approx(400)

    client.post("/api/pantry", json={"name": "Pasta", "quantity": 0.2, "unit": "kg"})
    assert client.get("/api/shopping").get_json()[0]["quantity"] == pytest.approx(200)

def test_togliere_dalla_dispensa_rimette_in_spesa(client):
    """Senza piu' la scorta in casa l'ingrediente torna da comprare."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 1, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    assert client.get("/api/shopping").get_json() == []

    [voce] = client.get("/api/pantry").get_json()
    client.delete(f"/api/pantry/{voce['id']}")
    assert client.get("/api/shopping").get_json()[0]["quantity"] == pytest.approx(400)
