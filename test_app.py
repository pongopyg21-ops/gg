"""Pagine, home, profilo, tema e errori dell'app.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_dispensa_in_kg_scala_ricetta_in_g(client):
    """Il caso che prima non funzionava: ricetta in g, dispensa in kg."""
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Pasta", "quantity": 0.1, "unit": "kg"})  # 100 g
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert len(items) == 1
    assert items[0]["name"] == "Pasta"
    assert items[0]["quantity"] == pytest.approx(300)  # 400 g - 100 g

def test_dispensa_in_g_scala_ricetta_in_kg(client):
    rid = ricetta(client, "Farina", 2, [{"name": "Farina", "quantity": 1, "unit": "kg"}])
    client.post("/api/pantry", json={"name": "Farina", "quantity": 250, "unit": "g"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert items[0]["quantity"] == pytest.approx(750)  # 1000 g - 250 g
    assert items[0]["unit"] == "g"

def test_fabbisogno_unico_quando_tutto_in_dispensa(client):
    rid = ricetta(client, "Zucchero", 2, [{"name": "Zucchero", "quantity": 100, "unit": "g"}])
    client.post("/api/pantry", json={"name": "Zucchero", "quantity": 1, "unit": "kg"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    r = client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    assert r.get_json()["added"] == 0
    assert client.get("/api/shopping").get_json() == []

def test_due_ricette_con_unita_diverse_si_fondono(client):
    """Stesso ingrediente, una ricetta in g e una in kg: una sola voce di spesa."""
    a = ricetta(client, "A", 2, [{"name": "Riso", "quantity": 300, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Riso", "quantity": 1, "unit": "kg"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": a, "servings": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": b, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert len(items) == 1
    assert items[0]["quantity"] == pytest.approx(1.3)  # 300 g + 1000 g
    assert items[0]["unit"] == "kg"
    assert items[0]["quantity"] != 1.2999999999999998  # arrotondato

def test_porzioni_scalate_e_convertite(client):
    """Ricetta base 2 porzioni (200 ml), mangiata in 4: 400 ml."""
    rid = ricetta(client, "Latte", 2, [{"name": "Latte", "quantity": 200, "unit": "ml"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": rid, "servings": 4})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert items[0]["quantity"] == pytest.approx(400)
    assert items[0]["unit"] == "ml"

def test_unita_non_convertibili_restano_separate(client):
    rid = ricetta(client, "Uova", 2, [{"name": "Uova", "quantity": 3, "unit": "pz"}])
    client.post("/api/pantry", json={"name": "Uova", "quantity": 1, "unit": "confezione"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert items[0]["quantity"] == pytest.approx(3)
    assert items[0]["unit"] == "pz"

def test_dispensa_somma_unita_compatibili_multiple(client):
    """Dispensa con 1 kg e 500 g dello stesso ingrediente: 1.5 kg totali."""
    rid = ricetta(client, "Ceci", 2, [{"name": "Ceci", "quantity": 2, "unit": "kg"}])
    client.post("/api/pantry", json={"name": "Ceci", "quantity": 1, "unit": "kg"})
    client.post("/api/pantry", json={"name": "Ceci", "quantity": 500, "unit": "g"})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert items[0]["quantity"] == pytest.approx(500)  # 2000 g - 1500 g

def test_generazione_ripetuta_non_accumula(client):
    """Rigenerare senza cambiare il piano non raddoppia la spesa.

    La lista generata e' una fotografia del piano: la si ricostruisce, non la si
    somma, altrimenti ogni clic gonfierebbe le quantita' da comprare.
    """
    rid = ricetta(client, "Pomodori", 2, [{"name": "Pomodori", "quantity": 500, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert len(items) == 1
    assert items[0]["quantity"] == pytest.approx(500)

def test_cambio_piano_rimuove_le_voci_dismesse(client):
    """Togliendo una ricetta dal piano, i suoi ingredienti escono dalla lista.

    È il caso segnalato: in lista restavano gli ingredienti di ricette non più
    pianificate, mescolati a quelli giusti.
    """
    a = ricetta(client, "A", 2, [{"name": "Pomodoro", "quantity": 500, "unit": "g"}])
    b = ricetta(client, "B", 2, [{"name": "Zucchine", "quantity": 300, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": a, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    [pasto] = client.get("/api/plan").get_json()
    client.delete(f"/api/plan/{pasto['id']}")
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": b, "servings": 2})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    nomi = [i["name"] for i in client.get("/api/shopping").get_json()]
    assert nomi == ["Zucchine"]

def test_voce_manuale_sopravvive_alla_rigenerazione(client):
    """Quello che l'utente scrive a mano non è della generazione e resta."""
    client.post("/api/shopping", json={"name": "Carta da cucina", "quantity": 1, "unit": "pz"})
    rid = ricetta(client, "A", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})
    nomi = [i["name"] for i in client.get("/api/shopping").get_json()]
    assert nomi == ["Carta da cucina", "Farina"]

def test_voce_manuale_mantiene_la_sua_quantita(client):
    """La riga scritta a mano non viene fusa né riscritta dalla generazione."""
    client.post("/api/shopping", json={"name": "Farina", "quantity": 100, "unit": "g"})
    rid = ricetta(client, "A", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-15", "meal": "cena", "recipe_id": rid, "servings": 2})

    r = client.post("/api/shopping/generate", json={"start": "2026-09-15", "end": "2026-09-15"})
    assert r.get_json() == {"added": 0, "already_listed": 1}
    voci = [i for i in client.get("/api/shopping").get_json() if i["name"] == "Farina"]
    assert len(voci) == 1
    assert voci[0]["quantity"] == pytest.approx(100)

def test_aggiunta_dispensa_si_converte_a_unita_esistente(client):
    client.post("/api/pantry", json={"name": "Burro", "quantity": 1, "unit": "kg"})
    client.post("/api/pantry", json={"name": "Burro", "quantity": 200, "unit": "g"})
    rows = client.get("/api/pantry").get_json()
    assert len(rows) == 1
    assert rows[0]["quantity"] == pytest.approx(1.2)

def test_nessun_pasto_pianificato(client):
    r = client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-17"})
    assert r.status_code == 404
    assert "Nessun pasto" in r.get_json()["error"]

def test_meta_endpoint(client):
    meta = client.get("/api/meta").get_json()
    assert "kg" in meta["units"]
    assert meta["meals"] == ["pranzo", "cena"]

def test_pasto_fuori_piano_rifiutato(client):
    rid = ricetta(client, "X", 2, [{"name": "X", "quantity": 1, "unit": "pz"}])
    r = client.post("/api/plan", json={"date": "2026-09-16", "meal": "colazione", "recipe_id": rid})
    assert r.status_code == 400
    assert "Pasto non valido" in r.get_json()["error"]

def test_format_quantity_no_trailing_zeros():
    assert units.format_quantity(300.0) == 300
    assert units.format_quantity(1.5) == 1.5
    assert units.format_quantity(1.2999999999999998) == 1.3

def test_ricetta_creazione_e_modifica_con_unita_normalizzate(client):
    rid = ricetta(client, "Torta", 4, [{"name": "Farina", "quantity": 0.5, "unit": "KG"}])
    r = client.get(f"/api/recipes/{rid}").get_json()
    assert r["items"][0]["unit"] == "kg"

    r = client.put(f"/api/recipes/{rid}", json={
        "name": "Torta", "servings": 4,
        "items": [{"name": "Farina", "quantity": 250, "unit": "Grammi"}],
    })
    assert r.get_json()["items"][0]["unit"] == "g"

def test_eliminazione_ricetta_rimuove_dal_piano(client):
    rid = ricetta(client, "Temp", 2, [{"name": "X", "quantity": 1, "unit": "pz"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    client.delete(f"/api/recipes/{rid}")
    assert client.get("/api/plan").get_json() == []

def test_eliminazione_ricetta_rimuove_gli_ingredienti_orfani(client):
    """Il catalogo non deve conservare nomi che nessuna ricetta usa piu'.

    Eliminando la ricetta `recipe_items` sparisce per CASCADE ma la riga in
    `ingredients` no: senza la pulizia il nome resterebbe nel riepilogo
    allergeni e fra i suggerimenti del form.
    """
    rid = ricetta(client, "Prova", 2, [{"name": "ZZZunico", "quantity": 100, "unit": "g"}])
    assert "ZZZunico" in nomi_ingredienti(client, "ZZZunico")

    client.delete(f"/api/recipes/{rid}")
    assert nomi_ingredienti(client, "ZZZunico") == []
    assert "ZZZunico" not in client.get("/api/profile/allergens").get_json()

def test_ingrediente_condiviso_sopravvive_alla_rimozione(client):
    """Se un'altra ricetta lo usa ancora, l'ingrediente resta."""
    a = ricetta(client, "Prima", 2, [{"name": "ZZZcondiviso", "quantity": 100, "unit": "g"}])
    ricetta(client, "Seconda", 2, [{"name": "ZZZcondiviso", "quantity": 50, "unit": "g"}])

    client.delete(f"/api/recipes/{a}")
    assert "ZZZcondiviso" in nomi_ingredienti(client, "ZZZcondiviso")

def test_ingrediente_in_dispensa_non_e_orfano(client):
    """Un ingrediente ancora in dispensa si tiene, anche senza ricette."""
    rid = ricetta(client, "Prova", 2, [{"name": "ZZZindispensa", "quantity": 100, "unit": "g"}])
    client.post("/api/pantry", json={"name": "ZZZindispensa", "quantity": 2, "unit": "kg"})

    client.delete(f"/api/recipes/{rid}")
    assert "ZZZindispensa" in nomi_ingredienti(client, "ZZZindispensa")

def test_ingrediente_in_lista_non_e_orfano(client):
    """Comprare a mano qualcosa lo rende un ingrediente in uso."""
    rid = ricetta(client, "Prova", 2, [{"name": "ZZZinlista", "quantity": 100, "unit": "g"}])
    client.post("/api/shopping", json={"name": "ZZZinlista", "quantity": 1, "unit": "kg"})

    client.delete(f"/api/recipes/{rid}")
    assert "ZZZinlista" in nomi_ingredienti(client, "ZZZinlista")

def test_modifica_ricetta_ripulisce_l_ingrediente_tolto(client):
    """Togliere un ingrediente dalla ricetta lo rimuove anche dal catalogo."""
    ric = crea_ricetta(client, name="Prova", items=[
        {"name": "ZZZresta", "quantity": 100, "unit": "g"},
        {"name": "ZZZsparisce", "quantity": 50, "unit": "g"}])
    assert "ZZZsparisce" in nomi_ingredienti(client, "ZZZsparisce")

    client.put(f"/api/recipes/{ric['id']}", json={
        "name": "Prova", "servings": 2,
        "items": [{"name": "ZZZresta", "quantity": 100, "unit": "g"}]})
    assert nomi_ingredienti(client, "ZZZsparisce") == []
    assert "ZZZresta" in nomi_ingredienti(client, "ZZZresta")

def test_rimozione_dalla_dispensa_libera_l_ingrediente(client):
    """Svuotata la dispensa, un ingrediente senza ricette non ha piu' motivo di restare."""
    client.post("/api/pantry", json={"name": "ZZZdispensa", "quantity": 1, "unit": "pz"})
    riga = client.get("/api/pantry").get_json()[0]

    client.delete(f"/api/pantry/{riga['id']}")
    assert nomi_ingredienti(client, "ZZZdispensa") == []

def test_dettaglio_ricetta_espone_la_preparazione(client):
    """La finestra della preparazione legge istruzioni, ingredienti e tempi."""
    rid = ricetta(client, "Frittata", 2, [{"name": "Uova", "quantity": 3, "unit": "pz"}])
    client.put(f"/api/recipes/{rid}", json={
        "name": "Frittata", "servings": 2, "instructions": "Sbatti le uova. Cuoci in padella.",
        "time_minutes": 15, "difficulty": "facile",
        "items": [{"name": "Uova", "quantity": 3, "unit": "pz"}],
    })

    r = client.get(f"/api/recipes/{rid}").get_json()
    assert r["instructions"] == "Sbatti le uova. Cuoci in padella."
    assert r["time_minutes"] == 15
    assert r["difficulty"] == "facile"
    assert [i["name"] for i in r["items"]] == ["Uova"]

def test_dettaglio_ricetta_senza_preparazione(client):
    """Una ricetta senza istruzioni resta leggibile: il campo e' vuoto, non assente."""
    rid = ricetta(client, "Semplice", 2, [{"name": "Pane", "quantity": 100, "unit": "g"}])
    r = client.get(f"/api/recipes/{rid}").get_json()
    assert r["instructions"] == ""
    assert r["items"][0]["name"] == "Pane"

def test_meta_espone_numero_e_insiemi_di_pasti(client):
    meta = client.get("/api/meta").get_json()
    assert meta["meals"] == ["pranzo", "cena"]
    assert meta["meals_per_day"] == 2
    assert meta["meal_sets"]["3"] == ["colazione", "pranzo", "cena"]
    assert meta["meal_sets"]["1"] == ["cena"]

def test_cambiare_pasti_aggiorna_meta_e_profilo(client):
    r = client.put("/api/profile", json={"meals_per_day": 4})
    assert r.status_code == 200
    assert r.get_json()["meals_per_day"] == 4
    meta = client.get("/api/meta").get_json()
    assert meta["meals"] == ["colazione", "pranzo", "merenda", "cena"]

def test_numero_pasti_non_valido_rifiutato(client):
    for cattivo in (0, 6, -1, "tre", None):
        r = client.put("/api/profile", json={"meals_per_day": cattivo})
        assert r.status_code == 400, cattivo
        assert "Numero di pasti" in r.get_json()["error"]
    assert client.get("/api/profile").get_json()["meals_per_day"] == 2

def test_pasti_scelti_decidono_quali_sono_validi(client):
    rid = ricetta(client, "Zuppa", 2, [{"name": "Z", "quantity": 1, "unit": "pz"}])
    r = client.post("/api/plan", json={"date": "2026-09-16", "meal": "colazione", "recipe_id": rid})
    assert r.status_code == 400
    client.put("/api/profile", json={"meals_per_day": 3})
    r = client.post("/api/plan", json={"date": "2026-09-16", "meal": "colazione", "recipe_id": rid})
    assert r.status_code == 201

def test_salvataggio_parziale_non_tocca_il_numero_di_pasti(client):
    client.put("/api/profile", json={"meals_per_day": 5})
    client.put("/api/profile", json={"full_name": "Gianluca"})
    p = client.get("/api/profile").get_json()
    assert p["meals_per_day"] == 5
    assert p["full_name"] == "Gianluca"

def test_riducendo_i_pasti_la_spesa_ignora_i_pasti_nascosti(client):
    """I pasti tolti non devono pesare sulla spesa.

    Ridurre i pasti lascia le righe vecchie in `meal_plan`: se non fossero
    filtrate continuerebbero a contare pur non essendo piu' visibili.
    """
    cena = ricetta(client, "Cena", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    pranzo = ricetta(client, "Pranzo", 2, [{"name": "Riso", "quantity": 300, "unit": "g"}])
    client.put("/api/profile", json={"meals_per_day": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": pranzo})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": cena})

    r = client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    assert r.status_code == 200
    nomi = {v["name"] for v in client.get("/api/shopping").get_json()}
    assert {"Farina", "Riso"} <= nomi

    client.put("/api/profile", json={"meals_per_day": 1})
    for v in client.get("/api/shopping").get_json():
        client.delete(f"/api/shopping/{v['id']}")
    r = client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    assert r.status_code == 200
    nomi = {v["name"] for v in client.get("/api/shopping").get_json()}
    assert "Farina" in nomi
    assert "Riso" not in nomi, "il pranzo non e' piu' gestito: non deve finire in lista"

def test_l_api_risponde_in_italiano_quando_qualcosa_si_rompe(client, monkeypatch):
    def esplode():
        raise RuntimeError("guasto improvviso")

    monkeypatch.setattr(app_module.houses, "elenco", esplode)

    r = client.get("/api/houses")
    assert r.status_code == 500
    assert r.is_json, r.data
    testo = r.get_json()["error"]
    assert "andato storto" in testo
    # il testo e' quello che legge l'utente: in italiano, e senza il nome
    # dell'eccezione ne' la traccia, che confonderebbero e basta
    assert "RuntimeError" not in testo
    assert "Traceback" not in testo

def test_un_guasto_non_previsto_finisce_nel_log(client, monkeypatch, caplog):
    """Senza traccia nel log, un guasto resta irripetibile: si vede solo la
    pagina che l'utente ha visto per un attimo."""
    def esplode():
        raise RuntimeError("guasto da ritrovare nel log")

    monkeypatch.setattr(app_module.houses, "elenco", esplode)

    with caplog.at_level("ERROR", logger="app"):
        client.get("/api/houses")

    assert "guasto da ritrovare nel log" in caplog.text, caplog.text

def test_una_pagina_inesistente_si_spiega_in_italiano(client):
    """Fuori dall'API si risponde con una pagina, sempre in italiano."""
    r = client.get("/pagina-che-non-esiste")
    assert r.status_code == 404
    testo = r.get_data(as_text=True)
    assert "Non ho trovato" in testo
    assert "Not Found" not in testo

def test_un_indirizzo_api_inesistente_risponde_json(client):
    """L'API non deve rispondere l'HTML della pagina: chi la chiama si aspetta
    `{error: ...}` e riceverebbe un errore di analisi al posto del messaggio."""
    r = client.get("/api/rotta-che-non-esiste")
    assert r.status_code == 404
    assert r.is_json, r.data
    assert "error" in r.get_json()

def test_il_metodo_sbagliato_si_spiega_in_italiano(anon):
    r = anon.delete("/api/login")
    assert r.status_code == 405
    assert r.is_json
    assert "prevista" in r.get_json()["error"]

def test_la_password_della_casa_si_cambia_dal_profilo(client):
    """Cambiare la password e' un'operazione rara ma necessaria: deve stare
    nell'app, non solo in uno script da riga di comando. Il modulo chiede la
    vecchia e fa ripetere la nuova, e chiama la rotta vera.

    Sta nel **Profilo**, non nella FAQ: la FAQ raccoglie cose da consultare, la
    password si cambia. Erano in FAQ solo perche' non c'era un posto migliore."""
    html = client.get("/static/index.html").get_data(as_text=True)
    inizio = html.index('id="tab-profile"')
    fine = html.index('id="tab-faq"')
    profilo = html[inizio:fine]
    for pezzo in ('id="pw-attuale"', 'id="pw-nuova"', 'id="pw-ripeti"', 'id="pw-salva"'):
        assert pezzo in profilo, pezzo
    # e non e' rimasta nella FAQ
    assert 'id="pw-salva"' not in html[html.index('id="tab-faq"'):]
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/houses/password" in js
    assert "method: 'PUT'" in js

def test_anche_l_aspetto_sta_nel_profilo_non_nella_faq(client):
    """Il tema e' un'impostazione di servizio come la password: si sceglie nel
    Profilo. Si verifica che i due pulsanti stiano li' e che la FAQ sia tornata
    a essere solo la rubrica."""
    html = client.get("/static/index.html").get_data(as_text=True)
    profilo = html[html.index('id="tab-profile"'):html.index('id="tab-faq"')]
    assert 'id="tema-chiaro"' in profilo and 'id="tema-scuro"' in profilo
    faq = html[html.index('id="tab-faq"'):html.index('id="tab-intrattenimento"')]
    assert 'tema-chiaro' not in faq and 'Password della casa' not in faq

def test_le_due_password_nuove_devono_coincidere(client):
    """Un refuso in un campo password non si vede: senza la ripetizione,
    l'utente cambierebbe la password in una che non conosce e resterebbe fuori
    di casa. La regola e' pura, cosi' si prova il comportamento."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "passwordCoerenti")
    d = _esegui_node(blocco + """
console.log(JSON.stringify({
  uguali: passwordCoerenti('nuovissima', 'nuovissima'),
  diverse: passwordCoerenti('nuovissima', 'nuovissimA'),
  vuota: passwordCoerenti('', ''),
  unaVuota: passwordCoerenti('nuova', ''),
}));""")
    assert d["uguali"] is True
    assert d["diverse"] is False, "due password diverse non devono passare"
    assert d["vuota"] is False, "una password vuota non e' una password"
    assert d["unaVuota"] is False

def test_cambiare_password_dalla_faq_funziona_davvero(anon):
    """La rotta della FAQ e' quella che gia' esiste: si prova end-to-end, cosi'
    il modulo non punta a un indirizzo sbagliato senza che nessuno se ne accorga."""
    anon.post("/api/houses", json={"nome": "Casa Password", "password": "vecchia"})
    r = anon.put("/api/houses/password", json={"attuale": "vecchia", "nuova": "nuovissima"})
    assert r.status_code == 200
    anon.post("/api/logout")
    assert anon.post("/api/login",
                     json={"nome": "Casa Password", "password": "vecchia"}).status_code == 401
    assert anon.post("/api/login",
                     json={"nome": "Casa Password", "password": "nuovissima"}).status_code == 200

def test_le_quantita_si_riscalano_sulle_porzioni(client):
    """Il dettaglio ricetta ha un campo porzioni: le quantita' seguono. Si esegue
    `qtaScalata` vera con node, perche' il conto e' la funzione, e una stringa
    letta nel codice non dice se il risultato e' giusto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "qtaScalata")
    prova = (blocco + "\nconsole.log(JSON.stringify(["
             "qtaScalata(100, 2), qtaScalata(100, 0.5), qtaScalata(3, 1),"
             "qtaScalata(1, 3), qtaScalata('q.b.', 2), qtaScalata(0.5, 3),"
             "qtaScalata(2, 1.5)]));")
    d = _esegui_node(prova)
    assert d == ["200", "50", 3, "3", "q.b.", "1.5", "3"]

def test_il_riepilogo_di_oggi_mette_insieme_le_fonti(client):
    """La home mostra un riepilogo (pasti, pulizie, impegni, scadenze). Si esegue
    `renderHomeOggi` vera con node e risposte preparate: il riquadro deve
    comparire con i pezzi giusti, e restare nascosto se non c'e' niente da dire."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeOggi")
    preludio = """
const stato = { html: '', nascosto: true };
function $(sel) {
  if (sel === '#home-oggi') return {
    set innerHTML(v) { stato.html = v; }, get innerHTML() { return stato.html; },
    classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } },
  };
  return { innerHTML: '', classList: { add() {}, remove() {} } };
}
function esc(s) { return String(s); }
const VERO_DATE = Date;
const OGGI_TS = new VERO_DATE(2026, 9, 2).getTime();
class DataFinta extends VERO_DATE {
  constructor(...a) { if (a.length === 0) super(OGGI_TS); else super(...a); }
  static now() { return OGGI_TS; }
}
globalThis.Date = DataFinta;
function pad(n) { return String(n).padStart(2, '0'); }
function iso(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function statoScadenza(e) {
  if (!e) return { testo: '—', classe: 'scad-niente' };
  return { testo: 'fra 1 giorno', classe: 'scad-vicino' };
}
const risposte = {
  '/api/plan?start=2026-10-02&end=2026-10-02':
    [{ recipe_name: 'Pasta', meal: 'cena' }],
  '/api/chores': { piano: { da_fare: 2 } },
  '/api/appointments?giorno=2026-10-02':
    { prossimi: [{ title: 'Dentista', quando_detto: 'oggi' }] },
  '/api/pantry': [{ name: 'Latte', expires_at: '2026-10-03' }],
};
async function api(url) { return risposte[url]; }
"""
    coda = "\nrenderHomeOggi().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False, "con qualcosa da dire il riquadro deve vedersi"
    assert "Pasta" in d["html"] and "cena" in d["html"]
    assert "2 attività di casa" in d["html"]
    assert "Dentista" in d["html"]
    assert "Latte" in d["html"]
    # domani ha il suo riquadro, piu' sotto: qui non deve comparire
    assert "Domani" not in d["html"]

def test_il_riepilogo_di_oggi_tace_se_non_c_e_niente(client):
    """Senza pasti, pulizie, impegni o scadenze il riquadro resta nascosto: una
    home con un riquadro vuoto e' peggio di una home senza riquadro."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeOggi")
    preludio = """
const stato = { html: 'vecchio', nascosto: false };
function $(sel) {
  if (sel === '#home-oggi') return {
    set innerHTML(v) { stato.html = v; }, get innerHTML() { return stato.html; },
    classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } },
  };
  return { innerHTML: '', classList: { add() {}, remove() {} } };
}
function esc(s) { return String(s); }
function iso(d) { return '2026-10-02'; }
function statoScadenza() { return { testo: '—', classe: 'scad-niente' }; }
async function api() { return []; }
"""
    coda = "\nrenderHomeOggi().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is True
    assert d["html"] == ""

def test_il_riquadro_domani_mette_impegni_e_pasti(client):
    """Domani ha un riquadro suo, dopo le notizie: gli impegni non ancora chiusi
    e i pasti gia' scelti. Solo quelli da fare: un impegno gia' fatto non e' un
    impegno, e mostrarlo farebbe credere che domani ci sia qualcosa."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeDomani")
    preludio = """
const stato = { html: '', nascosto: true };
function $(sel) {
  if (sel === '#home-domani') return {
    classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } },
  };
  if (sel === '#home-domani-corpo') return {
    set innerHTML(v) { stato.html = v; }, get innerHTML() { return stato.html; },
  };
  return { innerHTML: '', classList: { add() {}, remove() {} } };
}
function esc(s) { return String(s); }
const VERO_DATE = Date;
const OGGI_TS = new VERO_DATE(2026, 9, 2).getTime();
class DataFinta extends VERO_DATE {
  constructor(...a) { if (a.length === 0) super(OGGI_TS); else super(...a); }
  static now() { return OGGI_TS; }
}
globalThis.Date = DataFinta;
function pad(n) { return String(n).padStart(2, '0'); }
function iso(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
const risposte = {
  '/api/appointments?giorno=2026-10-03':
    { appointments: [{ title: 'Dentista', done: false }, { title: 'Vecchio', done: true }] },
  '/api/plan?start=2026-10-03&end=2026-10-03':
    [{ recipe_name: 'Lasagne', meal: 'pranzo' }],
};
async function api(url) { return risposte[url]; }
"""
    coda = "\nrenderHomeDomani().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False, "con qualcosa in programma il riquadro si vede"
    assert "Dentista" in d["html"]
    assert "Vecchio" not in d["html"], "un impegno gia' fatto non si suggerisce"
    assert "Lasagne" in d["html"] and "pranzo" in d["html"]

def test_il_riquadro_domani_tace_se_non_c_e_niente(client):
    """Senza impegni ne' pasti di domani il riquadro resta nascosto: una home con
    un riquadro vuoto e' peggio di una home senza riquadro."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeDomani")
    preludio = """
const stato = { html: 'vecchio', nascosto: false };
function $(sel) {
  if (sel === '#home-domani') return {
    classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } },
  };
  if (sel === '#home-domani-corpo') return {
    set innerHTML(v) { stato.html = v; }, get innerHTML() { return stato.html; },
  };
  return { innerHTML: '', classList: { add() {}, remove() {} } };
}
function esc(s) { return String(s); }
function iso() { return '2026-10-03'; }
async function api(url) {
  if (url.startsWith('/api/appointments')) return { appointments: [] };
  return [];
}
"""
    coda = "\nrenderHomeDomani().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is True
    assert d["html"] == ""

def test_il_calendario_in_home_mostra_il_mese_col_puntino(client):
    """La home ripropone il calendario dei Progetti in fondo, in sola lettura. Si
    esegue `renderHomeCalendario` vera con node: il mese compare, il giorno
    occupato ha il puntino e il giorno di oggi e' marcato. `calMeta` e
    `homeCalVista` sono riscritti, quindi il preludio li dichiara con `let`."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeCalendario")
    preludio = """
let calMeta = { categories: ['altro'], months: ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
  'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'],
  category_colors: { altro: '--accent' } };
let homeCalVista = null;
const stato = { griglia: '', mese: '', nascosto: true };
function $(sel) {
  if (sel === '#home-cal') return { classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } } };
  if (sel === '#home-cal-mese') return { set textContent(v) { stato.mese = v; }, get textContent() { return stato.mese; } };
  if (sel === '#home-cal-grid') return { set innerHTML(v) { stato.griglia = v; }, get innerHTML() { return stato.griglia; } };
  return { classList: { add() {}, remove() {} }, innerHTML: '', textContent: '' };
}
function esc(s) { return String(s); }
function iso(d) { return '2026-10-02'; }
function pad(n) { return String(n).padStart(2, '0'); }
async function api(url) {
  if (url === '/api/appointments') return {
    mese: { anno: 2026, mese: 10, celle: [
      { giorno: 1, iso: '2026-10-01', nel_mese: true, weekend: false },
      { giorno: 2, iso: '2026-10-02', nel_mese: true, weekend: false },
    ] },
    appointments: [{ when_date: '2026-10-02', category: 'altro', title: 'Dentista' }],
  };
  throw new Error('non previsto: ' + url);
}
"""
    coda = "\nrenderHomeCalendario().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False, "col calendario il riquadro deve vedersi"
    assert d["mese"] == "Ottobre 2026", d["mese"]
    assert "cal-cella" in d["griglia"]
    assert "2026-10-02" in d["griglia"]
    assert "occupato" in d["griglia"], "il giorno con un impegno porta il puntino"
    assert "cal-cella oggi" in d["griglia"], "il giorno di oggi e' marcato"

def test_il_calendario_in_home_tace_se_il_server_non_risponde(client):
    """Se gli impegni non arrivano, il riquadro in home resta nascosto: un
    calendario vuoto e' peggio di nessun calendario."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeCalendario")
    preludio = """
let calMeta = { categories: [], months: [], category_colors: {} };
let homeCalVista = null;
const stato = { nascosto: false };
function $(sel) {
  if (sel === '#home-cal') return { classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } } };
  return { classList: { add() {}, remove() {} }, innerHTML: '', textContent: '' };
}
function esc(s) { return String(s); }
function iso(d) { return '2026-10-02'; }
function pad(n) { return String(n); }
async function api() { throw new Error('rete assente'); }
"""
    coda = "\nrenderHomeCalendario().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is True

def test_il_calendario_in_home_non_sfoglia_quello_dei_progetti(client):
    """La griglia in home ha il suo mese (`homeCalVista`): sfogliare in home non
    deve spostare il calendario dei Progetti (`calVista`)."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "homeCalVista" in js
    assert "let homeCalVista" in js
    # i pulsanti della home scrivono solo homeCalVista, non calVista
    assert "$('#home-cal-prev')" in js and "$('#home-cal-next')" in js
    assert "homeCalVista =" in js
    # l'ordine della home: prima le categorie, poi il riepilogo «Oggi», in fondo
    # il calendario
    html = client.get("/").get_data(as_text=True)
    assert 'id="home-cal"' in html
    assert html.index('class="home-cards"') < html.index('id="home-oggi"') < html.index('id="home-cal"')
    # in home si sfoglia e basta: nessun pulsante per creare impegni
    sezione = html[html.index('id="home-cal"'):html.index('<div id="app"')]
    assert "home-cal-apri" in sezione
    assert "Nuovo impegno" not in sezione

def test_l_intestazione_chiude_la_home(client):
    """L'intestazione «Il Maggiordomo» sta in fondo alla home, dopo «Oggi», il
    calendario, le notizie e «Domani».

    In alto era la prima cosa che si incontrava e spingeva giu' le categorie,
    che sono il motivo per cui si arriva in home. Ora chiude la pagina."""
    html = client.get("/").get_data(as_text=True)
    inizio = html.index('id="home"')
    home = html[inizio:html.index('<div id="app"', inizio)]
    assert "home-hero-basso" in home
    assert home.index('class="home-cards"') < home.index("home-hero-basso")
    assert home.index('id="home-notizie"') < home.index("home-hero-basso")
    assert home.index('id="home-domani"') < home.index("home-hero-basso")

def test_l_intestazione_della_home_e_centrata(client):
    """Il testo «Il Maggiordomo» in home e' centrato: l'intestazione chiude la
    pagina e deve stare al centro, non ancorata a sinistra. La regola e' nel
    CSS, sulla classe `home-hero-basso`."""
    css = client.get("/static/style.css").get_data(as_text=True)
    inizio = css.index(".home-hero-basso")
    blocco = css[inizio:inizio + 400]
    assert "text-align: center" in blocco

def test_la_cucina_ha_la_sua_icona(client):
    """La scheda Cucina ha un'icona sua (la pentola sul fuoco), non il logo
    dell'app: prima erano lo stesso disegno, quindi la scheda non si
    distingueva. L'icona e' un file vero, e la sezione la usa. Il disegno e'
    **piatto e su fondo trasparente**, come le emoji delle altre schede: senza,
    sembrava una tessera col fondo colorato incollata in mezzo a simboli piatti,
    che era l'incoerenza da correggere."""
    import os
    radice = os.path.dirname(os.path.abspath(app_module.__file__))
    percorso = os.path.join(radice, "static", "icons", "cucina.svg")
    assert os.path.isfile(percorso), "l'icona della Cucina deve esistere su disco"
    disegno = open(percorso, encoding="utf-8").read()
    # la pentola e' il disegno nuovo: il cappello aveva il fondo #f7e58a e il
    # contorno ambra, che qui non ci sono piu'
    assert "#c1440e" in disegno, "la Cucina mostra la pentola, non il cappello"
    assert "#f7e58a" not in disegno, "il vecchio cappello non deve restare"
    # il fondo trasparente e' quello che la rende coerente con le emoji: un
    # `<rect>` di fondo a tutta tela era il riquadro che la staccava dalle altre
    assert 'width="64" height="64" rx="14"' not in disegno, \
        "l'icona non deve avere il riquadro di fondo: e' piatta, come le emoji"
    html = client.get("/").get_data(as_text=True)
    card = html[html.index('data-section="cucina"'):html.index('data-section="igiene"')]
    assert "/static/icons/cucina.svg" in card
    assert "icona.svg" not in card, "la Cucina non usa piu' il logo dell'app"
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "icona: '/static/icons/cucina.svg'" in js
    # e la resa non ritaglia piu' gli angoli, che erano del riquadro rimosso
    css = client.get("/static/style.css").get_data(as_text=True)
    assert ".icona-sezione img { width: 34px; height: 34px; display: block; }" in css

def test_il_tema_scuro_si_applica_e_si_ricorda(client):
    """Il tema scuro e' l'opposto di quello chiaro, e si sceglie dalla FAQ. Si
    esegue `applicaTema` **vera** con node: deve mettere l'attributo sul
    documento quando e' scuro, toglierlo quando e' chiaro (il chiaro e' il
    predefinito, quindi non ha una regola sua), e segnare il pulsante giusto.

    Un test sulle stringhe non si accorgerebbe di un `dataset` scritto male."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "applicaTema")
    preludio = """
const classi = { 'tema-chiaro': new Set(), 'tema-scuro': new Set() };
const nodi = {};
function $(sel) {
  const id = sel.replace(/^#/, '');
  nodi[id] = {
    classList: {
      toggle(c, v) { if (v) classi[id].add(c); else classi[id].delete(c); },
      contains(c) { return classi[id].has(c); },
    },
  };
  return nodi[id];
}
global.document = { documentElement: { dataset: {} } };
"""
    prova = preludio + blocco + """
applicaTema('scuro');
const scuro = { attr: document.documentElement.dataset.tema ?? null,
                chiaro: classi['tema-chiaro'].has('active'),
                scuroAttivo: classi['tema-scuro'].has('active') };
applicaTema('chiaro');
const chiaro = { attr: document.documentElement.dataset.tema ?? null,
                 chiaro: classi['tema-chiaro'].has('active'),
                 scuroAttivo: classi['tema-scuro'].has('active') };
console.log(JSON.stringify({ scuro, chiaro }));
"""
    d = _esegui_node(prova)
    assert d["scuro"]["attr"] == "scuro"
    assert d["scuro"]["scuroAttivo"] is True and d["scuro"]["chiaro"] is False
    assert d["chiaro"]["attr"] is None, "il chiaro e' il predefinito: niente attributo"
    assert d["chiaro"]["chiaro"] is True and d["chiaro"]["scuroAttivo"] is False

def test_il_tema_scuro_e_l_opposto_di_quello_chiaro():
    """Il tema deve essere davvero l'opposto, non una variante: lo sfondo scuro e
    il testo chiaro. Si guardano le due palette nel CSS, perche' un tema che
    lascia lo sfondo chiaro non e' un tema diverso — e' la stessa pagina con un
    dettaglio cambiato."""
    import re
    css = open(f"{BASE_APP}/static/style.css", encoding="utf-8").read()
    inizio = css.index('html[data-tema="scuro"]')
    blocco = css[inizio:css.index("}", inizio)]

    def valore(nome, testo):
        m = re.search(rf"--{nome}:\s*([^;]+);", testo)
        return m.group(1).strip() if m else None

    def luminanza(colore):
        colore = colore.lstrip("#")
        r, g, b = (int(colore[i:i + 2], 16) for i in (0, 2, 4))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255

    chiaro = css[:inizio]
    # sfondo: scuro nel tema scuro, chiaro in quello chiaro
    assert luminanza(valore("paper", blocco)) < 0.25, "--paper del tema scuro non e' scuro"
    assert luminanza(valore("paper", chiaro)) > 0.8, "--paper del tema chiaro non e' chiaro"
    # inchiostro: l'opposto
    assert luminanza(valore("ink", blocco)) > 0.8, "--ink del tema scuro non e' chiaro"
    assert luminanza(valore("ink", chiaro)) < 0.25, "--ink del tema chiaro non e' scuro"

def test_i_testi_colorati_restano_leggibili_nei_due_temi():
    """Ogni testo colorato deve restare sopra 4,5:1 (WCAG AA) **in entrambi** i
    temi. Il caso che ha motivato il test e' l'etichetta dell'ambiente
    "soggiorno": il fondo sabbia era chiaro fisso e il testo era `--sand`, che
    di notte diventa chiaro — testo dorato su fondo dorato, 1,85:1, illeggibile.

    Si leggono le variabili dalle due palette nel CSS e si calcola il contrasto
    vero (luminanza relativa WCAG), non si guarda se il colore "sembra" giusto:
    un colore fissato a mano fuori dalla palette non si vede leggendo il codice,
    e torna a ogni cambio di tema."""
    import re
    css = open(f"{BASE_APP}/static/style.css", encoding="utf-8").read()

    def blocco(inizio):
        return css[inizio:css.index("}", inizio)]

    def valore(nome, testo):
        m = re.search(rf"--{nome}:\s*([^;]+);", testo)
        assert m, f"manca --{nome}"
        return m.group(1).strip()

    def luminanza(colore):
        colore = colore.lstrip("#")
        if len(colore) == 3:
            colore = "".join(c * 2 for c in colore)
        canali = [int(colore[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        canali = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                  for c in canali]
        return 0.2126 * canali[0] + 0.7152 * canali[1] + 0.0722 * canali[2]

    def contrasto(a, b):
        l1, l2 = sorted((luminanza(a), luminanza(b)), reverse=True)
        return (l1 + 0.05) / (l2 + 0.05)

    chiaro = blocco(css.index(":root {"))
    scuro = blocco(css.index('html[data-tema="scuro"]'))

    # coppie (testo, sfondo): sono i testi colorati che non usano `--ink`/`--muted`
    coppie = [
        ("scadenza vicina", "sand-testo", "surface"),
        ("scadenza vicina sul fondo", "sand-testo", "paper"),
        ("zona soggiorno", "zona-soggiorno-testo", "zona-soggiorno"),
        ("zona bagno", "zona-bagno-testo", "zona-bagno"),
        ("zona cucina", "zona-cucina-testo", "zona-cucina"),
        ("zona camere", "zona-camere-testo", "zona-camere"),
        ("scheda attiva", "testo-su-accento", "accent"),
    ]
    for nome, testo, sfondo in coppie:
        for tema, pal in (("chiaro", chiaro), ("scuro", scuro)):
            rapporto = contrasto(valore(testo, pal), valore(sfondo, pal))
            assert rapporto >= 4.5, (
                f"{nome} in tema {tema}: {rapporto:.2f}:1, sotto il minimo 4,5:1")

    # le regole devono davvero usare le variabili: un colore fissato a mano
    # tornerebbe a rompersi al cambio di tema senza che questo test se ne accorga
    assert ".scad-testo.scad-vicino { color: var(--sand-testo); }" in css
    assert ".ch-area[data-area=\"soggiorno\"], .ch-area[data-area=\"ingresso\"] " \
           "{ background: var(--zona-soggiorno); border-color: var(--zona-soggiorno); " \
           "color: var(--zona-soggiorno-testo); }" in css
    assert "color: var(--sand-testo);" in css[css.index(".sug-card .sug-scade"):
                                             css.index(".sug-card .sug-scade") + 200]

def test_lo_sfondo_della_home_e_dinamico_ma_discreto():
    """La home ha uno sfondo che respira (aloni del mare dietro le schede), ma
    **discreto**: e' trasparenza, non colore pieno, l'animazione e' lenta e il
    movimento e' di pochi punti percentuali. I colori sono variabili del tema,
    cosi' il tema scuro non resta a macchie chiare, e chi ha chiesto meno
    movimento non vede niente animarsi."""
    import re
    css = open(f"{BASE_APP}/static/style.css", encoding="utf-8").read()
    assert ".home::before {" in css, "lo sfondo della home deve esserci"
    blocco = css[css.index(".home::before {"):css.index("@keyframes home-respira")]
    # trasparenze del tema, non colori fissi
    assert "var(--home-alone-1)" in blocco
    assert "var(--home-alone-2)" in blocco
    assert "var(--home-alone-3)" in blocco
    assert not re.search(r"#[0-9a-fA-F]{3,6}", blocco), "colore fisso fuori dalla palette"
    # sta dietro al contenuto: senza, coprirebbe le schede e il testo
    assert "z-index: -1" in blocco
    assert "pointer-events: none" in blocco
    # l'animazione e' lenta: 'respira', non 'si muove'
    m = re.search(r"animation: home-respira (\d+)s", blocco)
    assert m and int(m.group(1)) >= 20, "lo sfondo della home non deve muoversi in fretta"
    # i colori sono definiti in entrambi i temi (altrimenti di notte sparirebbero)
    chiaro = css.split('html[data-tema="scuro"]')[0]
    scuro = css.split('html[data-tema="scuro"]', 1)[1]
    for v in ("--home-alone-1", "--home-alone-2", "--home-alone-3"):
        assert f"{v}:" in chiaro, f"{v} manca nel tema chiaro"
        assert f"{v}:" in scuro, f"{v} manca nel tema scuro"
    # e la regola del movimento ridotto lo spegne (vale per ogni ::before)
    assert "animation: none !important" in css


def test_le_illustrazioni_della_home_sono_doodle_del_tema(client):
    """La home ha delle illustrazioni "doodle" (un pesce, un'onda, un gabbiano,
    un'ancora...) sparse fra le schede, e un piccolo disegno nell'angolo di ogni
    scheda categoria. Devono restare **decorative e discrete**: disegni a
    inchiostro del tema (non colori fissi), dietro al contenuto e con
    `pointer-events: none`, cosi' non coprono mai un testo ne' rubano un tocco.

    Il difetto che il test tiene fuori: le illustrazioni erano `<use>` dentro un
    unico SVG, ma `position` **non si applica ai figli di un SVG** — finivano in
    flow, non posizionate. Ogni disegno e' quindi un `<svg>` a se'."""
    import re
    html = client.get("/").get_data(as_text=True)
    css = client.get("/static/style.css").get_data(as_text=True)

    # Lo sprite dei disegni (i `<symbol>`) e il livello che li mostra in home.
    assert 'class="sprite-doodle"' in html, "manca lo sprite dei disegni"
    assert 'class="home-doodle"' in html, "mancano le illustrazioni della home"
    for nome in ("pesce", "onda", "gabbiano", "ancora", "barca", "sole",
                 "conchiglia", "stella"):
        assert f'id="doodle-{nome}"' in html, f"manca il disegno «{nome}»"
    # in home i disegni sono `<svg>` a se' (non `<use>` di primo livello):
    # solo cosi' il posizionamento assoluto ha effetto
    blocco_home = html[html.index('<div class="home-doodle"'):html.index('class="home-voice"')]
    assert blocco_home.count("<svg") >= 8, "i doodle devono essere <svg>, non <use>"
    # decorativi: nessuno finisce nella lettura per schermo
    assert 'class="home-doodle" aria-hidden="true"' in html

    # e ogni scheda categoria ha il suo doodle d'angolo
    assert html.count('class="home-card-doodle"') == 6, \
        "ogni scheda categoria deve avere il suo disegno"

    # il CSS: inchiostro del tema, dietro al contenuto, niente tocchi
    assert ".sprite-doodle { position: absolute; width: 0; height: 0; overflow: hidden; }" in css
    blocco = css[css.index(".home-doodle {"):css.index(".home-hero { margin-bottom")]
    assert "z-index: -1" in blocco, "i doodle devono stare dietro alle schede"
    assert "pointer-events: none" in blocco, "un disegno non deve rubare un tocco"
    assert "var(--doodle-inchiostro)" in blocco, "il colore deve venire dal tema"
    assert not re.search(r"#[0-9a-fA-F]{3,6}", blocco), "colore fisso fuori dalla palette"
    blocco_card = css[css.index(".home-card-doodle {"):css.index(".home-card-doodle svg {")]
    assert "var(--doodle-inchiostro)" in blocco_card

    # le variabili sono definite in entrambi i temi (di notte non spariscono)
    chiaro = css.split('html[data-tema="scuro"]')[0]
    scuro = css.split('html[data-tema="scuro"]', 1)[1]
    for v in ("--doodle-inchiostro", "--doodle-corallo"):
        assert f"{v}:" in chiaro, f"{v} manca nel tema chiaro"
        assert f"{v}:" in scuro, f"{v} manca nel tema scuro"



def test_l_icona_dell_igiene_e_la_scopa(client):
    """La sezione Igiene si riconosce dalla scopa, non piu' dalla spugna: la
    spugna era un oggetto della cucina e non diceva «pulizie di casa»."""
    html = client.get("/static/index.html").get_data(as_text=True)
    # nella scheda in home e nella scheda della barra
    assert '<span class="home-emoji">🧹</span>' in html
    assert 'data-section="igiene">🧹 Pulizie</button>' in html
    assert '<span class="home-emoji">🧽</span>' not in html
    js = client.get("/static/app.js").get_data(as_text=True)
    # la scopa anche nel menu di benvenuto e nel riepilogo «Oggi»
    assert "{ ico: '🧹', titolo: 'Pulizie'" in js
    assert 'oggi-ico" aria-hidden="true">🧹' in js
    # l'icona della spugna resta dov'e' giusto: e' un ingrediente della dispensa
    assert "['spugna', '🧽']" in js

def test_il_pulsante_elimina_usa_la_palette_del_tema(client):
    """Il rosso di «Elimina» e' la coppia `--errore-*` del tema, non un
    esadecimale fisso: un `#...` scelto a occhio resterebbe illeggibile in tema
    scuro. E' la regola dell'app — ogni colore passa da una variabile — che qui
    vale anche per il rosso di un'azione distruttiva."""
    css = client.get("/static/style.css").get_data(as_text=True)
    blocco = css[css.index(".cinema-elimina {"):css.index(".cinema-elimina:disabled")]
    assert "var(--errore-testo)" in blocco
    assert "var(--errore-bordo)" in blocco
    assert not re.search(r"#[0-9a-fA-F]{3,6}", blocco), "colore fisso fuori dalla palette"

def test_senza_rete_l_eliminazione_riesce_lo_stesso(client, monkeypatch):
    """Il rimpiazzo e' un di piu': se la rete manca, il titolo si elimina
    comunque e la copia resta com'e' (senza il film tolto)."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    monkeypatch.setattr(cinema, "_apri", _apri_tmdb_a_pagine({
        1: [_film(1, "Primo"), _film(2, "Secondo")],
    }))
    cinema.aggiorna(app_module.get_db(), forse=False)

    monkeypatch.setattr(cinema, "_apri",
                        lambda url: (_ for _ in ()).throw(cinema.NonDisponibile("giu")))
    d = client.post("/api/cinema/nascondi", json={"id": 1}).get_json()
    assert [f["id"] for f in d["film"]] == [2]
    assert d["nascosti"] == [1]

def test_la_scheda_progetti_si_chiama_appunti(client):
    """La sezione si chiama «Appunti» dappertutto: scheda in home, scheda nella
    barra, titolo dell'area e testi del pannello. Un nome che resta indietro in
    un punto solo e' peggio di non averlo cambiato, perche' fa cercare due cose."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-section="progetti"' in html
    assert "Appunti" in html
    # nessun «Progetti» visibile: i commenti sono stati aggiornati anch'essi
    assert "Progetti" not in html, "resta del testo visibile con il vecchio nome"
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "progetti: { titolo: '\\u{1F4CB} Appunti'" in js
    # e i messaggi del pannello parlano di appunti, non di progetti
    for vecchio in ("Nessun progetto", "Modifica progetto", "Nuovo progetto",
                    "Progetto salvato", "Progetto eliminato"):
        assert vecchio not in js, vecchio
    assert "Nuovo appunto" in js and "Appunto salvato" in js

def test_il_menù_di_benvenuto_si_puo_saltare(client):
    """Subito dopo aver creato la casa l'app si presenta: un elenco di cosa sa
    fare, con un pulsante per saltare. Chi vuole iniziare a usarla non deve
    leggerlo tutto, e chi non sa cosa cercare lo trova qui."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function mostraBenvenuto" in js
    assert "wb-skip" in js and "wb-inizia" in js
    assert "welcome-list" in js
    # si apre solo per una casa appena creata, non a ogni accesso
    assert "casaAppenaCreata" in js
    assert "casaAppenaCreata = true" in js
    css = client.get("/static/style.css").get_data(as_text=True)
    assert ".welcome-list" in css and ".welcome-ico" in css

def test_l_onboarding_ha_cinque_passi(client):
    """I passi sono cinque e si contano da soli: pasti, allergie, bucati,
    argomenti delle notizie, preferite. Il conteggio nell'intestazione deve
    corrispondere, altrimenti dice il falso a chi lo legge."""
    js = client.get("/static/app.js").get_data(as_text=True)
    for passo in ("Passo 1 di 5", "Passo 2 di 5", "Passo 3 di 5",
                  "Passo 4 di 5", "Passo 5 di 5"):
        assert passo in js, passo
    # i due passi nuovi hanno la loro schermata
    assert "passoBucati" in js and "passoNotizie" in js
    assert 'id="ob-bucati"' in js and 'id="ob-news"' in js

def test_i_titoli_quasi_uguali_non_si_ripetono(client, monkeypatch):
    """Lo stesso fatto esce in due sezioni con titoli che differiscono per un
    apostrofo o una virgola, e con link diversi: si riconosce dal titolo ridotto,
    altrimenti il doppione occupa il posto di un'altra notizia."""
    u1, u2 = "https://esempio.invalid/a", "https://esempio.invalid/b"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    v1 = ("<item><title>Giuseppe Graviano: 'Mio nonno fece una societa'</title>"
          "<link>https://esempio.invalid/1</link><description>S</description>"
          "<pubDate>Thu, 02 Apr 2026 09:00:00 +0200</pubDate></item>")
    v2 = ("<item><title>Giuseppe Graviano, 'Mio nonno fece una societa'</title>"
          "<link>https://esempio.invalid/2</link><description>S</description>"
          "<pubDate>Thu, 02 Apr 2026 08:00:00 +0200</pubDate></item>")
    finta_tv(monkeypatch, {u1: _feed("RSS di Mondo  - ANSA.it", [v1]),
                           u2: _feed("RSS di Cronaca  - ANSA.it", [v2])})
    notizie = tv.notizie_dal_feed()
    assert len(notizie) == 1
    assert notizie[0]["link"] == "https://esempio.invalid/1"

def test_una_sezione_ferma_non_svuota_le_altre(client, monkeypatch):
    """Se una sezione non risponde, le altre si mostrano lo stesso: una ferma non
    deve portare via le notizie che si sono lette."""
    u1, u2 = "https://esempio.invalid/mondo", "https://esempio.invalid/giu"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    finta_tv(monkeypatch, {u1: _feed("RSS di Mondo  - ANSA.it", [_voce("buona")])})
    # `u2` non e' previsto da finta_tv: solleva NonDisponibile
    notizie = tv.notizie_dal_feed()
    assert [n["titolo"] for n in notizie] == ["buona"]
