"""Verifica conversione unità e generazione lista della spesa. Crea un DB temporaneo."""
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date

import pytest

DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["CUCINA_DB"] = DB

import app as app_module  # noqa: E402
import allergens  # noqa: E402
import igiene  # noqa: E402
import units  # noqa: E402
import voice  # noqa: E402


@pytest.fixture()
def client():
    if os.path.exists(DB):
        os.remove(DB)
    app_module.init_db()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


# ------------------------------------------------------------ units
def test_normalize_aliases():
    assert units.normalize("Grammi") == "g"
    assert units.normalize("KG") == "kg"
    assert units.normalize("") == "pz"
    assert units.normalize("  Cucchiai ") == "cucchiaio"
    assert units.normalize(None) == "pz"


def test_convert_compatible():
    assert units.convert(1, "kg", "g") == 1000
    assert units.convert(500, "g", "kg") == 0.5
    assert units.convert(2, "cucchiaio", "ml") == 30
    assert units.convert(1, "l", "ml") == 1000


def test_convert_incompatible_returns_none():
    assert units.convert(1, "kg", "l") is None
    assert units.convert(1, "pz", "g") is None
    assert units.convert(1, "confezione", "kg") is None


def test_group_key_merges_same_dimension():
    assert units.group_key("g") == units.group_key("kg")
    assert units.group_key("ml") == units.group_key("cucchiaio")
    assert units.group_key("pz") != units.group_key("confezione")
    assert units.group_key("g") != units.group_key("ml")


def test_display_unit_picks_readable():
    assert units.display_unit(1500, units.MASSA, "g") == "kg"
    assert units.display_unit(200, units.MASSA, "g") == "g"
    assert units.display_unit(1, units.MASSA, "g") == "g"
    assert units.display_unit(400, units.VOLUME, "ml") == "ml"
    assert units.display_unit(2500, units.VOLUME, "ml") == "l"


def test_cucchiai_mantenuti_solo_per_piccole_quantita():
    """5 ml di sale si leggono come 1 cucchiaino, 360 ml no."""
    assert units.display_unit(5, units.VOLUME, "cucchiaino") == "cucchiaino"
    assert units.display_unit(45, units.VOLUME, "cucchiaio") == "cucchiaio"
    assert units.display_unit(360, units.VOLUME, "cucchiaio") == "ml"
    assert units.display_unit(1500, units.VOLUME, "cucchiaio") == "l"


def test_display_unit_keeps_unconvertible():
    assert units.display_unit(3, None, "confezione") == "confezione"


# ------------------------------------------------------------ integrazione
def ricetta(client, name, servings, items):
    r = client.post("/api/recipes", json={"name": name, "servings": servings, "items": items})
    assert r.status_code == 201, r.data
    return r.get_json()["id"]


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


def nomi_ingredienti(client, q=""):
    return [i["name"] for i in client.get(f"/api/ingredients?q={q}").get_json()]


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


# ------------------------------------------------------------ allergeni
def test_riconosce_allergeni_dal_nome():
    assert allergens.allergens_for("Parmigiano") == {"latte"}
    assert allergens.allergens_for("Farina") == {"glutine"}
    assert allergens.allergens_for("Vongole") == {"molluschi"}
    assert allergens.allergens_for("Gamberi") == {"crostacei"}
    assert allergens.allergens_for("Merluzzo") == {"pesce"}
    assert allergens.allergens_for("Pinoli") == {"frutta_guscio"}
    assert allergens.allergens_for("Uova") == {"uova"}
    assert allergens.allergens_for("Brodo") == set()


def test_eccezioni_evitano_falsi_positivi():
    """Nomi che contengono la parola di un allergene senza esserlo."""
    assert allergens.allergens_for("Noce moscata") == set()
    assert allergens.allergens_for("Burro di cacao") == set()
    assert allergens.allergens_for("Latte di cocco") == set()
    assert allergens.allergens_for("Noodles di riso") == set()
    # questi invece l'allergene ce l'hanno davvero
    assert allergens.allergens_for("Burro di arachidi") == {"arachidi"}
    assert allergens.allergens_for("Latte di soia") == {"soia"}
    assert allergens.allergens_for("Salsa di soia") == {"glutine", "soia"}


def test_accento_e_maiuscole_non_contano():
    assert allergens.allergens_for("CAFFÈ") == set()
    assert allergens.allergens_for("Parmigiano") == allergens.allergens_for("PARMIGIANO")


def test_riconosce_le_forme_di_pasta_del_ricettario():
    """Ogni formato di pasta usato nelle ricette deve risultare glutinato."""
    import seed
    forme = {"Pasta", "Pasta corta", "Penne", "Spaghetti", "Bucatini", "Trofie",
             "Tagliolini", "Malloreddus", "Casoncelli", "Lasagne", "Noodles"}
    usati = {i["name"] for r in seed.RECIPES for i in r["items"]}
    for forma in forme:
        assert forma in usati, f"{forma} non compare in nessuna ricetta"
        assert allergens.allergens_for(forma) == {"glutine"}, forma


def test_riepilogo_unione_di_piu_ingredienti():
    tags = allergens.tags_for(["Farina", "Uova", "Parmigiano", "Tonno"])
    assert tags == {"glutine", "uova", "latte", "pesce"}


def test_matching_accetta_chiave_etichetta_e_termine_libero():
    names = ["Pasta", "Parmigiano"]
    tags = allergens.tags_for(names)
    # chiave tecnica
    assert allergens.matching_terms(["latte"], tags, names) == ["latte"]
    # etichetta italiana mostrata nell'interfaccia
    assert allergens.matching_terms(["Latte e lattosio"], tags, names) == ["Latte e lattosio"]
    # termine libero cercato nel nome dell'ingrediente
    assert allergens.matching_terms(["nichel"], tags, ["Farina al nichel"]) == ["nichel"]
    assert allergens.matching_terms(["glutine"], tags, names) == ["glutine"]


def test_profilo_dichiarazione_restrizioni(client):
    p = client.get("/api/profile").get_json()
    assert p["onboarded"] == 0 and p["restriction_list"] == []

    p = client.put("/api/profile", json={"full_name": "Marco",
                                         "restrictions": "latte, glutine\nnichel",
                                         "onboarded": True}).get_json()
    assert p["restriction_list"] == ["latte", "glutine", "nichel"]
    assert p["onboarded"] == 1
    # i termini duplicati non vengono ripetuti
    p = client.put("/api/profile", json={"restrictions": ["Uova", "uova", "Uova"]}).get_json()
    assert p["restriction_list"] == ["Uova"]


# ------------------------------------------------------------ preferite
def test_preferite_si_salvano_e_si_rileggono(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])

    assert client.get("/api/profile").get_json()["favorite_ids"] == []

    p = client.put("/api/profile", json={"favorite_ids": [b, a]}).get_json()
    # l'elenco torna in ordine di nome ("Insalata" prima di "Pasta al pomodoro"),
    # non nell'ordine in cui e' stato scelto
    assert p["favorite_ids"] == [b, a]
    assert client.get("/api/profile").get_json()["favorite_ids"] == [b, a]

    # un salvataggio successivo sostituisce l'insieme, non lo somma
    p = client.put("/api/profile", json={"favorite_ids": [a]}).get_json()
    assert p["favorite_ids"] == [a]
    p = client.put("/api/profile", json={"favorite_ids": []}).get_json()
    assert p["favorite_ids"] == []


def test_flag_preferita_nelle_ricette(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])
    client.put("/api/profile", json={"favorite_ids": [a]})

    full = {r["id"]: r for r in client.get("/api/recipes?full=1").get_json()}
    assert full[a]["favorite"] is True
    assert full[b]["favorite"] is False
    assert client.get(f"/api/recipes/{a}").get_json()["favorite"] is True


def test_eliminare_una_ricetta_la_toglie_dalle_preferite(client):
    """La chiave esterna con CASCADE evita preferite che puntano a ricette sparite."""
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])
    client.put("/api/profile", json={"favorite_ids": [a, b]})

    client.delete(f"/api/recipes/{a}")
    assert client.get("/api/profile").get_json()["favorite_ids"] == [b]


def test_preferite_ignorano_id_inesistenti(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    p = client.put("/api/profile", json={"favorite_ids": [a, 9999, "x", None]}).get_json()
    assert p["favorite_ids"] == [a]


def test_salvataggio_parziale_non_azzera_le_preferite(client):
    """Il nome si salva dalla scheda Profilo: non deve cancellare le preferite."""
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    client.put("/api/profile", json={"favorite_ids": [a]})

    p = client.put("/api/profile", json={"full_name": "Marco"}).get_json()
    assert p["favorite_ids"] == [a]
    assert p["full_name"] == "Marco"


def test_onboarding_a_meta_non_chiude_il_percorso(client):
    """Il passo 1 salva le restrizioni senza marcare onboarded: chi si ferma li'
    non perde la dichiarazione e si vede riproporre il passo 2."""
    ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    p = client.put("/api/profile", json={"restrictions": ["latte"]}).get_json()
    assert p["restriction_list"] == ["latte"]
    assert p["onboarded"] == 0

    p = client.put("/api/profile", json={"onboarded": True}).get_json()
    assert p["onboarded"] == 1
    assert p["restriction_list"] == ["latte"]


def test_fav_prompted_separa_i_due_passi(client):
    """Chi si era profilato prima che la scelta esistesse non deve rivedere il
    passo delle allergie, ma solo quello delle preferite."""
    assert client.get("/api/profile").get_json()["fav_prompted"] == 0

    # profilo completo ma preferite mai chieste
    p = client.put("/api/profile", json={"onboarded": True, "restrictions": ["latte"]}).get_json()
    assert p["onboarded"] == 1 and p["fav_prompted"] == 0

    p = client.put("/api/profile", json={"fav_prompted": True}).get_json()
    assert p["fav_prompted"] == 1
    assert p["onboarded"] == 1 and p["restriction_list"] == ["latte"]


def test_migrazione_aggiunge_fav_prompted_a_un_db_esistente():
    """`CREATE TABLE IF NOT EXISTS` non tocca `profile`: la colonna va aggiunta a mano."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row  # come fa init_db
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT NOT NULL DEFAULT '',
                restrictions TEXT NOT NULL DEFAULT '',
                onboarded INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO profile (id, full_name, onboarded) VALUES (1, 'Gianluca', 1);
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(profile)")}
        assert "fav_prompted" in cols
        row = db.execute("SELECT full_name, onboarded, fav_prompted FROM profile").fetchone()
        # i dati gia' presenti restano e la colonna nuova parte da 0
        assert tuple(row) == ("Gianluca", 1, 0)
        # rieseguire la migrazione non deve fallire
        app_module.migrate(db)


def test_filtro_ricette_per_allergia(client):
    buona = ricetta(client, "Verdure", 2, [{"name": "Zucchine", "quantity": 300, "unit": "g"}])
    cattiva = ricetta(client, "Carbonara", 2, [
        {"name": "Spaghetti", "quantity": 180, "unit": "g"},
        {"name": "Parmigiano", "quantity": 50, "unit": "g"},
    ])

    full = client.get("/api/recipes?full=1").get_json()
    assert {r["id"] for r in full} == {buona, cattiva}
    # senza restrizioni dichiarate nessuna ricetta è in conflitto
    assert all(r["conflicts"] == [] for r in full)

    client.put("/api/profile", json={"restrictions": ["latte"], "onboarded": True})
    full = {r["id"]: r for r in client.get("/api/recipes?full=1").get_json()}
    assert full[cattiva]["conflicts"] == ["latte"]
    assert full[buona]["conflicts"] == []

    safe = client.get("/api/recipes?full=1&safe=1").get_json()
    assert [r["id"] for r in safe] == [buona]


def test_piano_segnala_i_conflitti(client):
    rid = ricetta(client, "Carbonara", 2, [{"name": "Parmigiano", "quantity": 50, "unit": "g"}])
    client.put("/api/profile", json={"restrictions": ["Latte e lattosio"], "onboarded": True})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    plan = client.get("/api/plan").get_json()
    assert plan[0]["conflicts"] == ["Latte e lattosio"]


def test_riepilogo_ingredienti_per_allergene(client):
    ricetta(client, "X", 2, [{"name": "Parmigiano", "quantity": 1, "unit": "pz"},
                             {"name": "Zucchine", "quantity": 1, "unit": "pz"}])
    m = client.get("/api/profile/allergens").get_json()
    assert m["Parmigiano"] == ["latte"]
    assert m["Zucchine"] == []


def test_aceto_non_e_solfitato():
    """L'aceto non è di per sé un solfito: era un falso positivo."""
    assert allergens.allergens_for("Aceto di riso") == set()
    assert allergens.allergens_for("Aceto balsamico") == set()
    assert allergens.allergens_for("Vino bianco") == {"solfiti"}


def test_formati_di_pasta_sono_glutine():
    """Ogni formato di pasta di semola è glutine: un celiaco non deve poterlo ignorare."""
    for nome in ["Calamarata", "Bucatini", "Farfalle", "Orecchiette", "Maccheroni",
                 "Conchiglie", "Ditalini", "Trofie", "Vermicelli", "Capellini",
                 "Pappardelle", "Tagliatelle", "Penne", "Fusilli", "Rigatoni"]:
        assert allergens.allergens_for(nome) == {"glutine"}, nome


def test_verdure_e_condimenti_non_danno_falsi_positivi():
    for nome in ["Peperoni", "Peperoncino", "Pepe nero", "Patate", "Basilico",
                 "Rosmarino", "Prezzemolo", "Aglio", "Cipolla", "Carota"]:
        assert allergens.allergens_for(nome) == set(), nome


# ------------------------------------------------------------ dispensa in lista
def voce_spesa(client, nome):
    """Voce della lista della spesa con il dato di dispensa allegato dall'API."""
    for i in client.get("/api/shopping").get_json():
        if i["name"] == nome:
            return i
    raise AssertionError(f"voce {nome!r} assente dalla lista")


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


# ------------------------------------------------- spesa filtrata per giorno
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



# ------------------------------------------------------------ foto ricette
def crea_ricetta(client, **extra):
    body = {"name": "Piatto di prova", "servings": 2, "items": [
        {"name": "Pasta", "quantity": 180, "unit": "g", "category": "Pane e Cereali"}]}
    body.update(extra)
    return client.post("/api/recipes", json=body).get_json()


def test_foto_salvata_e_restituita(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg",
                       image_credit="Autore — CC BY 2.0 — Wikimedia Commons")
    assert ric["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert ric["image_credit"] == "Autore — CC BY 2.0 — Wikimedia Commons"

    letto = client.get(f"/api/recipes/{ric['id']}").get_json()
    assert letto["image"] == "1-pasta-al-pomodoro-2.jpg"


def test_foto_rifiuta_percorsi_e_traversal(client):
    """Solo un nome di file semplice: niente percorsi, niente risalita di cartelle."""
    for tentativo in ["../../etc/passwd", "../segreto.jpg", "static/recipes/x.jpg",
                      "/etc/passwd", "sottocartella/foto.jpg"]:
        ric = crea_ricetta(client, image=tentativo)
        assert ric["image"] == "", f"accettato pericoloso: {tentativo}"


def test_foto_rifiuta_estensioni_non_immagine(client):
    for tentativo in ["script.js", "file.svg", "pagina.html", "dati.json"]:
        ric = crea_ricetta(client, image=tentativo)
        assert ric["image"] == "", f"accettata estensione non immagine: {tentativo}"


def test_foto_senza_immagine_non_tiene_il_credito(client):
    ric = crea_ricetta(client, image="", image_credit="credito orfano")
    assert ric["image"] == ""
    assert ric["image_credit"] == ""


def test_credito_rimosso_quando_si_toglie_la_foto(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore X")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": ric["name"], "servings": 2, "instructions": "", "items": ric["items"],
        "image": "", "image_credit": "Autore X"})
    assert risposta.get_json()["image"] == ""
    assert risposta.get_json()["image_credit"] == ""


def test_salvataggio_senza_campo_foto_non_la_cancella(client):
    """Un salvataggio parziale non deve far sparire la foto."""
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore Y")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": "Nome cambiato", "servings": 3, "instructions": "Nuova", "items": ric["items"]})
    corpo = risposta.get_json()
    assert corpo["name"] == "Nome cambiato"
    assert corpo["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert corpo["image_credit"] == "Autore Y"


def test_elenco_immagini_disponibili(client):
    nomi = client.get("/api/recipe-images").get_json()
    assert isinstance(nomi, list)
    # nel repository le foto delle ricette ci sono e hanno nomi coerenti
    assert nomi, "nessuna immagine trovata in static/recipes/"
    assert all(n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) for n in nomi)


def test_pagina_ricette_espone_la_foto(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore Z")
    elenco = client.get("/api/recipes?full=1").get_json()
    voce = next(r for r in elenco if r["id"] == ric["id"])
    assert voce["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert "Autore Z" in voce["image_credit"]


# ------------------------------------------------------------ comandi vocali
def test_voce_riconosce_quantita_a_parole_e_in_cifre():
    cmd = voice.parse("aggiungi due chili di farina in dispensa")
    assert cmd["intent"] == "pantry_add"
    assert (cmd["name"], cmd["quantity"], cmd["unit"]) == ("farina", 2.0, "kg")

    cmd = voice.parse("aggiungi 500 grammi di pasta alla spesa")
    assert (cmd["name"], cmd["quantity"], cmd["unit"]) == ("pasta", 500.0, "g")


def test_voce_converte_gli_etti_in_grammi():
    """L'etto non esiste come unità dell'app: 2 etti devono diventare 200 g."""
    for frase in ("due etti di prosciutto in dispensa", "aggiungi 3 etti di ricotta"):
        cmd = voice.parse(frase)
        assert cmd["quantity"] == (200.0 if "due" in frase else 300.0)
        assert cmd["unit"] == "g"


def test_voce_riconosce_le_frazioni():
    assert voice.parse("mezzo litro di latte in dispensa")["quantity"] == 0.5
    assert voice.parse("un chilo e mezzo di patate in dispensa")["quantity"] == 1.5
    assert voice.parse("un quarto di burro in dispensa")["quantity"] == 0.25
    # "un quarto" non deve essere letto come "un" + unità
    assert voice.parse("un quarto di burro in dispensa")["unit"] is None
    assert voice.parse("due litri e un quarto di acqua")["quantity"] == 2.25


def test_voce_numeri_a_parole_composti():
    assert voice.parse("venticinque grammi di lievito")["quantity"] == 25.0
    assert voice.parse("centoventi grammi di ricotta")["quantity"] == 120.0
    assert voice.parse("duecento grammi di zucchero")["quantity"] == 200.0
    assert voice.parse("mille grammi di farina")["quantity"] == 1000.0


def test_voce_destinazione_predefinita_e_lista_della_spesa():
    assert voice.parse("metti il latte nella spesa")["intent"] == "shopping_add"
    # senza indicazioni si finisce in lista, non in dispensa
    assert voice.parse("aggiungi il pane")["intent"] == "shopping_add"
    assert voice.parse("metti il burro in dispensa")["intent"] == "pantry_add"


def test_voce_ripulisce_il_nome_dell_ingrediente():
    casi = {
        "aggiungi due chili di farina alla dispensa": "farina",
        "metti il latte nella spesa": "latte",
        "ci vorrebbero due litri di acqua": "acqua",
        "tre confezioni di passata di pomodoro in dispensa": "passata di pomodoro",
        "aggiungi l'acqua alla spesa": "acqua",
    }
    for frase, atteso in casi.items():
        assert voice.parse(frase)["name"] == atteso, frase


def test_voce_registra_allergie_e_intolleranze():
    cmd = voice.parse("sono allergico al nichel")
    assert cmd["intent"] == "term_add"
    assert cmd["terms"] == ["nichel"]

    # più termini separati da "e", con l'articolo da togliere
    cmd = voice.parse("sono intollerante al lattosio e al fruttosio")
    assert cmd["terms"] == ["lattosio", "fruttosio"]

    # "frutta a guscio" è un'etichetta unica e non va spezzata
    cmd = voice.parse("sono allergico alla frutta a guscio")
    assert cmd["terms"] == ["frutta a guscio"]


def test_voce_ricerca_ricette():
    cmd = voice.parse("cerca la carbonara")
    assert cmd["intent"] == "recipe_search"
    assert cmd["query"] == "carbonara"
    assert voice.parse("cercami ricette con le melanzane")["query"] == "melanzane"


def test_voce_frase_non_compresa():
    assert voice.parse("")["intent"] == "unknown"
    assert voice.parse("   ")["intent"] == "unknown"
    # rumore di fondo o fraintendimento: non deve finire in lista come prodotto
    for frase in ("bla bla", "ehm", "oggi piove forte", "ciao come stai"):
        assert voice.parse(frase)["intent"] == "unknown", frase
    # senza verbo ma con quantità o destinazione resta un comando valido
    assert voice.parse("due chili di farina")["intent"] == "shopping_add"
    assert voice.parse("il latte in dispensa")["intent"] == "pantry_add"


def test_voce_endpoint_aggiunge_in_dispensa(client):
    r = client.post("/api/voice", json={"text": "aggiungi due chili di farina in dispensa"})
    assert r.status_code == 200
    assert "farina" in r.get_json()["message"]

    righe = client.get("/api/pantry").get_json()
    assert len(righe) == 1
    assert righe[0]["name"] == "farina"
    assert righe[0]["quantity"] == 2 and righe[0]["unit"] == "kg"


def test_voce_endpoint_aggiunge_alla_spesa(client):
    r = client.post("/api/voice", json={"text": "metti mezzo litro di latte nella spesa"})
    assert r.status_code == 200
    voci = client.get("/api/shopping").get_json()
    assert [v["name"] for v in voci] == ["latte"]
    assert voci[0]["quantity"] == 0.5 and voci[0]["unit"] == "l"

    # una seconda dettatura si somma, come la generazione della lista
    client.post("/api/voice", json={"text": "aggiungi 500 millilitri di latte alla spesa"})
    voci = client.get("/api/shopping").get_json()
    assert len(voci) == 1
    assert voci[0]["quantity"] == 1 and voci[0]["unit"] == "l"


def test_voce_endpoint_aggiunge_al_profilo(client):
    r = client.post("/api/voice", json={"text": "sono allergico al nichel e al fruttosio"})
    assert r.status_code == 200
    assert "nichel" in r.get_json()["message"]

    profilo = client.get("/api/profile").get_json()
    assert profilo["restriction_list"] == ["nichel", "fruttosio"]

    # ripetere lo stesso termine non lo duplica
    client.post("/api/voice", json={"text": "sono allergico al nichel"})
    assert client.get("/api/profile").get_json()["restriction_list"] == ["nichel", "fruttosio"]


def test_voce_endpoint_ricerca_ricette(client):
    r = client.post("/api/voice", json={"text": "cerca la carbonara"})
    assert r.status_code == 200
    assert r.get_json()["query"] == "carbonara"


def test_voce_endpoint_frase_non_compresa(client):
    r = client.post("/api/voice", json={"text": ""})
    assert r.status_code == 422
    assert "capito" in r.get_json()["message"]


# ------------------------------------------------------------ ricettario
def test_ricettario_di_partenza_e_coerente():
    """Le ricette del seed devono essere caricabili così come sono scritte."""
    import seed
    categorie_note = {"Frutta e Verdura", "Carne e Pesce", "Latticini", "Dispensa",
                      "Pane e Cereali", "Surgelati", "Bevande", "Dolci", "Altro"}
    nomi = [r["name"] for r in seed.RECIPES]
    assert len(nomi) == len(set(nomi)), "nomi duplicati nel ricettario"
    for r in seed.RECIPES:
        assert r["servings"] > 0
        assert r["time_minutes"] > 0
        assert r["difficulty"] in {"facile", "media", "difficile"}
        assert r["instructions"].strip()
        assert r["items"], f"{r['name']} senza ingredienti"
        for i in r["items"]:
            assert i["quantity"] > 0, f"{r['name']}: {i['name']} con quantità non valida"
            assert i["unit"] in {"pz", "g", "kg", "ml", "l", "cucchiaio", "cucchiaino",
                                 "confezione", "fetta"}, f"{r['name']}: unità {i['unit']}"
            assert i["category"] in categorie_note, f"{r['name']}: categoria {i['category']}"


def test_ricettario_copre_primi_e_piatti_unici_recenti(client):
    """I piatti entrati in voga negli ultimi anni esistono e sono pianificabili.

    Il database di test nasce vuoto, quindi le ricette vengono caricate davvero
    via API: il test verifica sia la presenza nel ricettario sia che il formato
    del seed sia accettato dall'endpoint di creazione.
    """
    import seed
    attesi = {"Pasta alla Norma", "Spaghetti all'assassina", "Cacio e pepe",
              "Trofie al pesto", "Bucatini all'amatriciana", "Penne all'arrabbiata",
              "Pasta fredda alla mediterranea", "Casoncelli alla bergamasca",
              "Malloreddus alla campidanese", "Tagliolini al tartufo",
              "Marry me chicken", "Lasagna soup", "Poke bowl", "Riso alla cantonese",
              "Gulasch", "Pizza napoletana", "Paella", "Ramen",
              "Chicken tikka masala", "Shakshuka"}
    assert attesi <= {r["name"] for r in seed.RECIPES}

    for r in seed.RECIPES:
        assert client.post("/api/recipes", json=r).status_code == 201, r["name"]

    elenco = client.get("/api/recipes").get_json()
    assert attesi <= {r["name"] for r in elenco}
    # una new entry si pianifica e finisce nella lista della spesa
    norma = next(r for r in elenco if r["name"] == "Pasta alla Norma")
    r = client.post("/api/plan", json={"date": "2026-09-21", "meal": "pranzo",
                                       "recipe_id": norma["id"], "servings": 2})
    assert r.status_code == 201
    r = client.post("/api/shopping/generate", json={"start": "2026-09-21", "end": "2026-09-21"})
    assert r.status_code == 200
    nomi = {v["name"] for v in client.get("/api/shopping").get_json()}
    assert {"Melanzane", "Penne", "Ricotta salata"} <= nomi


# ------------------------------------------------------------ pasti al giorno
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


def test_riducendo_i_pasti_il_fabbisogno_per_giorno_ignora_i_nascosti(client):
    """Anche la ripartizione per giorno deve ignorare i pasti non piu' gestiti."""
    cena = ricetta(client, "Cena", 2, [{"name": "Farina", "quantity": 200, "unit": "g"}])
    pranzo = ricetta(client, "Pranzo", 2, [{"name": "Farina", "quantity": 300, "unit": "g"}])
    client.put("/api/profile", json={"meals_per_day": 2})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "pranzo", "recipe_id": pranzo})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": cena})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})

    client.put("/api/profile", json={"meals_per_day": 1})
    for v in client.get("/api/shopping").get_json():
        client.delete(f"/api/shopping/{v['id']}")
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    voce = next(v for v in client.get("/api/shopping").get_json() if v["name"] == "Farina")
    assert float(voce["quantity"]) == 200, voce
    giorni = voce.get("days") or []
    assert not giorni or float(giorni[0]["quantity"]) == 200, giorni


def test_migrazione_aggiunge_il_numero_di_pasti(client):
    """Un DB creato prima della scelta pasti riceve la colonna a 2."""
    with sqlite3.connect(DB) as c:
        c.execute("ALTER TABLE profile RENAME TO profile_vecchio")
        c.execute("""CREATE TABLE profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            full_name TEXT NOT NULL DEFAULT '',
            restrictions TEXT NOT NULL DEFAULT '',
            onboarded INTEGER NOT NULL DEFAULT 0,
            fav_prompted INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')))""")
        c.execute("INSERT INTO profile (id, full_name) VALUES (1, 'Vecchio')")
        c.execute("DROP TABLE profile_vecchio")
        c.commit()
    with closing(sqlite3.connect(DB)) as conn:
        conn.row_factory = sqlite3.Row  # come fa init_db
        app_module.migrate(conn)
        colonne = {r["name"] for r in conn.execute("PRAGMA table_info(profile)")}
    assert "meals_per_day" in colonne
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        riga = c.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    assert riga["meals_per_day"] == 2, "il profilo vecchio resta a due pasti"
    assert riga["full_name"] == "Vecchio", "i dati esistenti non si perdono"


# ------------------------------------------------------------ igiene
def test_catalogo_pulizie_senza_duplicati():
    """Il catalogo deve restare ordinato: nomi ripetuti confondono il conteggio."""
    voci = igiene.catalogo()
    nomi = [v["name"] for v in voci]
    assert len(nomi) == len(set(nomi))
    assert all(v["name"].strip() for v in voci)
    assert all(v["frequency"] in {f["key"] for f in igiene.FREQUENZE} for v in voci)


def test_catalogo_copre_tutte_le_frequenze():
    """Ogni frequenza deve avere voce: senza, un blocco della pagina resta vuoto."""
    voci = igiene.catalogo()
    for chiave in ("giornaliera", "settimanale", "mensile", "stagionale"):
        assert any(v["frequency"] == chiave for v in voci), chiave


def test_catalogo_ogni_mese_dell_anno_ha_una_voce():
    """Il calendario annuale ha dodici mesi: un mese vuoto sarebbe un buco visibile."""
    mesi_con_voce = {v["month"] for v in igiene.catalogo() if v["frequency"] == "stagionale"}
    assert mesi_con_voce == set(range(1, 13))


def test_scadenza_giornaliera_sempre_da_fare():
    """Le quotidiane non hanno scadenza: si fanno ogni giorno.

    Fatta oggi risulta "prossima domani" (un giorno di distanza): e' corretto e
    non le toglie dal piano, perche' `piano` include comunque le quotidiane.
    """
    oggi = date(2026, 9, 18)
    mai = igiene.scadenza("giornaliera", None, oggi)
    assert mai["in_scadenza"] is True
    fatta = igiene.scadenza("giornaliera", "2026-09-18", oggi)
    assert fatta["giorni"] == 1, "torna domani, non oggi stesso"


def test_scadenza_settimanale_prima_della_scadenza():
    """Fatta tre giorni fa non e' ancora da rifare: la cadenza e' di sette giorni."""
    stato = igiene.scadenza("settimanale", "2026-09-15", date(2026, 9, 18))
    assert stato["in_scadenza"] is False
    assert stato["giorni"] == 4
    assert stato["prossima"] == "2026-09-22"


def test_scadenza_settimanale_alla_scadenza_esatta():
    """Il settimo giorno la voce rientra: il confine non deve slittare di un giorno."""
    stato = igiene.scadenza("settimanale", "2026-09-11", date(2026, 9, 18))
    assert stato["in_scadenza"] is True
    assert stato["giorni"] == 0


def test_scadenza_settimanale_in_ritardo():
    """Saltare una settimana non deve far sparire la voce: i giorni vanno negativi."""
    stato = igiene.scadenza("settimanale", "2026-09-01", date(2026, 9, 18))
    assert stato["in_scadenza"] is True
    assert stato["giorni"] < 0


def test_scadenza_mensile_e_annuale():
    """Mensile a trenta giorni, annuale solo nel suo mese."""
    oggi = date(2026, 9, 18)
    assert igiene.scadenza("mensile", "2026-08-01", oggi)["in_scadenza"] is True
    assert igiene.scadenza("mensile", "2026-09-10", oggi)["in_scadenza"] is False
    # una voce di giugno non e' in scadenza a settembre
    assert igiene.scadenza("stagionale", None, oggi, 6)["in_scadenza"] is False
    assert igiene.scadenza("stagionale", None, oggi, 9)["in_scadenza"] is True


def test_scadenza_stagionale_fatta_quest_anno_non_rientra():
    """La voce annuale fatta a settembre non deve riproporsi a settembre."""
    stato = igiene.scadenza("stagionale", "2026-09-02", date(2026, 9, 18), 9)
    assert stato["in_scadenza"] is False
    # ma torna l'anno dopo, nello stesso mese
    assert igiene.scadenza("stagionale", "2026-09-02", date(2027, 9, 18), 9)["in_scadenza"] is True


def test_scadenza_mai_fatta_e_segnalata():
    """Chi apre l'app per la prima volta deve vedere gli stati vuoti, non date inventate."""
    stato = igiene.scadenza("settimanale", None, date(2026, 9, 18))
    assert stato["mai_fatta"] is True
    assert stato["ultima"] is None


def test_data_ultima_volta_illeggibile_non_rompe_il_calcolo():
    """Un valore sporco nel DB non deve far fallire l'intera pagina."""
    stato = igiene.scadenza("settimanale", "non-una-data", date(2026, 9, 18))
    assert "in_scadenza" in stato


def test_piano_separa_oggi_dal_mese():
    """Il piano di oggi non deve contenere mensili e annuali.

    E' il punto del metodo: mensili e stagionali si distribuiscono nel mese. Se
    finissero tutte nel piano di oggi la giornata diventerebbe impraticabile e il
    piano verrebbe abbandonato.
    """
    voci = [
        {"id": 1, "name": "Quotidiana", "frequency": "giornaliera", "minutes": 5, "area": "Cucina", "active": 1, "month": None},
        {"id": 2, "name": "Settimanale", "frequency": "settimanale", "minutes": 10, "area": "Bagno", "active": 1, "month": None},
        {"id": 3, "name": "Mensile", "frequency": "mensile", "minutes": 40, "area": "Cucina", "active": 1, "month": None},
        {"id": 4, "name": "Annuale", "frequency": "stagionale", "minutes": 60, "area": "Camere", "active": 1, "month": 9},
    ]
    today = date(2026, 9, 18)  # venerdi
    piano = igiene.piano(voci, {}, today, giorno_pulizie=5)

    oggi_ids = {v["id"] for elenco in piano["gruppi"].values() for v in elenco}
    assert oggi_ids == {1, 2}, "oggi solo quotidiane e settimanali"
    mese_ids = {v["id"] for elenco in (piano["mese"]["mensili"], piano["mese"]["stagionali"]) for v in elenco}
    assert mese_ids == {3, 4}, "mensili e annuali stanno nel mese"


def test_piano_minuti_previsti_contano_solo_oggi():
    """Il tempo stimato di oggi non deve includere il mese: sarebbe una cifra falsa."""
    voci = [
        {"id": 1, "name": "Quotidiana", "frequency": "giornaliera", "minutes": 5, "area": "Cucina", "active": 1, "month": None},
        {"id": 3, "name": "Mensile", "frequency": "mensile", "minutes": 40, "area": "Cucina", "active": 1, "month": None},
    ]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["minuti_previsti"] == 5
    assert piano["mese_minuti"] == 40


def test_piano_il_giorno_fisso_tira_dentro_le_settimanali():
    """Il giorno fisso serve proprio a questo: raccogliere le settimanali in un giorno."""
    voci = [{"id": 2, "name": "Settimanale", "frequency": "settimanale", "minutes": 10,
             "area": "Bagno", "active": 1, "month": None}]
    # fatta ieri: senza giorno fisso non rientrerebbe
    ultime = {2: "2026-09-17"}
    senza = igiene.piano(voci, ultime, date(2026, 9, 18), giorno_pulizie=0)
    con = igiene.piano(voci, ultime, date(2026, 9, 18), giorno_pulizie=4)  # venerdi
    assert senza["da_fare"] == 0
    assert con["da_fare"] == 1


def test_piano_attivita_disattivate_restano_fuori():
    """Disattivare una voce deve toglierla dal piano, non solo dal catalogo."""
    voci = [{"id": 1, "name": "Spenta", "frequency": "giornaliera", "minutes": 5,
             "area": "Cucina", "active": 0, "month": None}]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["da_fare"] == 0


def test_piano_una_voce_fatta_oggi_non_conta_piu():
    """Spuntata la voce, il conteggio e i minuti devono scendere subito."""
    voci = [{"id": 1, "name": "Fatta", "frequency": "giornaliera", "minutes": 5,
             "area": "Cucina", "active": 1, "month": None}]
    piano = igiene.piano(voci, {1: "2026-09-18"}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["da_fare"] == 0
    assert piano["minuti_previsti"] == 0
    assert piano["fatto_oggi"] == 1, "resta visibile come fatta"


def test_piano_include_il_focus_del_mese():
    """Il focus del mese e' il senso del blocco annuale: senza, le voci non si capiscono."""
    piano = igiene.piano([], {}, date(2026, 9, 18), giorno_pulizie=5)
    assert piano["mese"]["nome"] == "Settembre"
    assert piano["mese"]["focus"]
    assert piano["mese"]["titolo"]


def test_piano_data_non_valida_ricade_su_oggi():
    """Una data storta non deve far esplodere la pagina."""
    piano = igiene.piano([], {}, "non-una-data", giorno_pulizie=5)
    assert piano["data"] == date.today().isoformat()


# ------------------------------------------------------------ igiene: API
def test_api_pulizie_meta(client):
    """La pagina ha bisogno di frequenze, ambienti, giorni e mesi per costruirsi."""
    m = client.get("/api/chores/meta").get_json()
    assert len(m["months"]) == 12
    assert len(m["days"]) == 7
    assert len(m["frequencies"]) == 4
    assert m["areas"]
    assert 0 <= m["chore_day"] <= 6


def test_api_pulizie_seminata_al_primo_avvio(client):
    """Un database nuovo deve uscire con il catalogo delle pulizie gia' pronto."""
    r = client.get("/api/chores").get_json()
    assert r["attivita"], "il catalogo non e' vuoto"
    assert r["attive"] == len([v for v in r["attivita"] if v["active"]])
    assert set(r["piano"]["gruppi"]) == {"quotidiane", "settimanali"}
    assert set(r["piano"]["mese"]) >= {"mensili", "stagionali"}


def test_api_pulizie_data_forzata(client):
    """La data si puo' fissare: serve per verificare scadenze e giorno fisso."""
    r = client.get("/api/chores?date=2026-09-19").get_json()  # sabato
    assert r["oggi"] == "2026-09-19"
    assert r["piano"]["giorno"] == "sabato"
    # il blocco del mese deve seguire la data richiesta, non quella di sistema
    assert r["piano"]["mese"]["nome"] == "Settembre"


def test_api_pulizie_errori(client):
    """Gli ingressi sbagliati si rifiutano con un messaggio, non con un 500."""
    assert client.post("/api/chores", json={"name": "  "}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "oraria"}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "stagionale"}).status_code == 400
    assert client.post("/api/chores", json={"name": "X", "frequency": "stagionale", "month": 13}).status_code == 400
    assert client.put("/api/chores/99999", json={"name": "Z"}).status_code == 404
    assert client.post("/api/chores/99999/done").status_code == 404


def test_api_pulizie_ciclo_completo(client):
    """Creare, modificare, disattivare: le tre operazioni del catalogo."""
    creato = client.post("/api/chores", json={
        "name": "Pulire il microonde", "frequency": "mensile", "minutes": 12, "area": "Cucina"})
    assert creato.status_code == 201
    cid = creato.get_json()["id"]

    # niente doppioni nello stesso ambiente
    assert client.post("/api/chores", json={
        "name": "Pulire il microonde", "frequency": "mensile"}).status_code == 400

    assert client.put(f"/api/chores/{cid}", json={"minutes": 20}).get_json()["minutes"] == 20
    assert client.put(f"/api/chores/{cid}", json={"active": 0}).get_json()["active"] == 0

    # disattivata: fuori dal piano ma ancora nel catalogo
    voci = client.get("/api/chores").get_json()["attivita"]
    voce = next(v for v in voci if v["id"] == cid)
    assert voce["active"] == 0
    assert client.delete(f"/api/chores/{cid}").status_code in (200, 204)


def test_api_pulizie_segno_fatto_e_annullo(client):
    """Spuntare registra il completamento; spuntare di nuovo lo annulla."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]

    assert client.post(f"/api/chores/{cid}/done", json={}).status_code == 200
    cronologia = client.get("/api/chores/history").get_json()
    assert any(h["chore_id"] == cid for h in cronologia)

    assert client.delete(f"/api/chores/{cid}/done").status_code == 200
    assert not any(h["chore_id"] == cid for h in client.get("/api/chores/history").get_json())
    # annullare due volte non deve far esplodere niente
    assert client.delete(f"/api/chores/{cid}/done").status_code == 404


def test_api_pulizie_tempo_registrato(client):
    """Il tempo cronometrato si conserva e finisce nel riepilogo."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]
    client.post(f"/api/chores/{cid}/done", json={"minutes": 17})

    riga = next(h for h in client.get("/api/chores/history").get_json() if h["chore_id"] == cid)
    assert riga["minutes"] == 17

    riepilogo = client.get("/api/chores/summary").get_json()
    assert riepilogo["oggi"]["minuti"] == 17
    assert riepilogo["oggi"]["volte"] == 1
    assert riepilogo["mese"]["minuti"] == 17
    assert riepilogo["settimana"]["minuti"] == 17


def test_api_pulizie_tempo_negativo_o_assurdo_non_trapela(client):
    """Un tempo assurdo non deve inquinare il riepilogo."""
    cid = client.get("/api/chores").get_json()["attivita"][0]["id"]
    client.post(f"/api/chores/{cid}/done", json={"minutes": -5})
    riga = next(h for h in client.get("/api/chores/history").get_json() if h["chore_id"] == cid)
    assert riga["minutes"] >= 0


def test_api_giorno_pulizie_si_salva(client):
    """Il giorno fisso e' una scelta dell'utente e deve restare."""
    assert client.put("/api/profile", json={"chore_day": 3}).status_code == 200
    assert client.get("/api/profile").get_json()["chore_day"] == 3
    assert client.put("/api/profile", json={"chore_day": 9}).status_code == 400


def test_api_giorno_pulizie_raccoglie_le_settimanali(client):
    """Scegliendo oggi come giorno fisso, le settimanali entrano nel piano di oggi."""
    import datetime as _dt
    oggi = _dt.date.today()
    client.put("/api/profile", json={"chore_day": oggi.weekday()})
    r = client.get(f"/api/chores?date={oggi.isoformat()}").get_json()
    assert r["piano"]["giorno_pulizie"] is True
    assert len(r["piano"]["gruppi"]["settimanali"]) == 5
    assert r["piano"]["da_fare"] > 5, "quotidiane piu' settimanali"


def test_api_pulizie_il_mese_non_invade_il_piano_di_oggi(client):
    """Mensili e stagionali non gonfiano la giornata: e' il punto del metodo."""
    r = client.get("/api/chores").get_json()
    oggi = r["piano"]["gruppi"]["quotidiane"] + r["piano"]["gruppi"]["settimanali"]
    assert all(v["frequency"] in ("giornaliera", "settimanale") for v in oggi)
    mensili = r["piano"]["mese"]["mensili"] + r["piano"]["mese"]["stagionali"]
    assert all(v["frequency"] in ("mensile", "stagionale") for v in mensili)
    # e il tempo stimato di oggi non deve includere quello del mese
    assert r["piano"]["minuti_previsti"] <= 24 * 60


# ------------------------------------------------------------ faq
def test_faq_meta_elenca_le_categorie(client):
    m = client.get("/api/faq/meta").get_json()
    chiavi = [c["key"] for c in m["categories"]]
    assert chiavi[0] == "wifi", "il Wi-Fi e' la cosa che si cerca piu' spesso"
    assert "generale" in chiavi
    assert m["default_category"] in chiavi
    assert all(c["count"] == 0 for c in m["categories"])


def test_faq_ciclo_completo(client):
    """Aggiungere, leggere, modificare ed eliminare una voce."""
    r = client.post("/api/faq", json={
        "question": "Wi-Fi di casa",
        "answer": "Rete: CasaRossi\nPassword: segreta",
        "category": "wifi", "secret": True,
    })
    assert r.status_code == 201
    voce = r.get_json()
    assert voce["secret"] == 1

    elenco = client.get("/api/faq").get_json()
    assert elenco["totale"] == 1
    assert elenco["riservate"] == 1
    assert elenco["voci"][0]["category_label"] == "Wi-Fi"

    r = client.put(f"/api/faq/{voce['id']}", json={"answer": "Password: nuova"})
    assert r.status_code == 200
    assert r.get_json()["answer"] == "Password: nuova"

    assert client.delete(f"/api/faq/{voce['id']}").status_code == 200
    assert client.get("/api/faq").get_json()["totale"] == 0


def test_faq_la_modifica_parziale_non_azzera_il_resto(client):
    """Cambiare un campo non deve svuotare gli altri, come per il profilo."""
    voce = client.post("/api/faq", json={
        "question": "Idraulico", "answer": "333 1234567", "category": "contatti",
    }).get_json()
    dopo = client.put(f"/api/faq/{voce['id']}", json={"pinned": True}).get_json()
    assert dopo["question"] == "Idraulico"
    assert dopo["answer"] == "333 1234567"
    assert dopo["category"] == "contatti"
    assert dopo["pinned"] == 1


def test_faq_titolo_obbligatorio(client):
    assert client.post("/api/faq", json={"answer": "solo valore"}).status_code == 400
    assert client.post("/api/faq", json={"question": "   "}).status_code == 400


def test_faq_categoria_sconosciuta_non_rifiuta_la_voce(client):
    """Una categoria ignota ricade sulla predefinita: la voce resta utile."""
    r = client.post("/api/faq", json={"question": "X", "category": "inesistente"})
    assert r.status_code == 201
    assert r.get_json()["category"] == "generale"


def test_faq_voce_inesistente(client):
    assert client.put("/api/faq/999", json={"question": "x"}).status_code == 404
    assert client.delete("/api/faq/999").status_code == 404


def test_faq_ordine_per_categoria_poi_evidenza(client):
    """Le voci in evidenza risalgono nella loro categoria, non oltre."""
    for corpo in (
        {"question": "Zeta", "category": "wifi"},
        {"question": "Alfa", "category": "wifi", "pinned": True},
        {"question": "Beta", "category": "indirizzi"},
    ):
        client.post("/api/faq", json=corpo)
    voci = client.get("/api/faq").get_json()["voci"]
    # Wi-Fi prima degli Indirizzi, e dentro il Wi-Fi l'evidenza viene prima
    assert [v["question"] for v in voci] == ["Alfa", "Zeta", "Beta"]


def test_faq_meta_conta_le_voci_per_categoria(client):
    client.post("/api/faq", json={"question": "A", "category": "wifi"})
    client.post("/api/faq", json={"question": "B", "category": "wifi"})
    client.post("/api/faq", json={"question": "C", "category": "contatti"})
    conteggi = {c["key"]: c["count"] for c in client.get("/api/faq/meta").get_json()["categories"]}
    assert conteggi["wifi"] == 2
    assert conteggi["contatti"] == 1
    assert conteggi["codici"] == 0


def test_faq_una_voce_senza_valore_e_ammessa(client):
    """Un promemoria puo' non avere ancora il valore: si aggiunge dopo."""
    r = client.post("/api/faq", json={"question": "Password del cancello"})
    assert r.status_code == 201
    assert r.get_json()["answer"] == ""


def test_faq_valori_booleani_normalizzati(client):
    """Il frontend manda true/false: nel database diventano 0/1."""
    voce = client.post("/api/faq", json={
        "question": "Cancello", "secret": False, "pinned": False,
    }).get_json()
    assert voce["secret"] == 0 and voce["pinned"] == 0
    dopo = client.put(f"/api/faq/{voce['id']}", json={"secret": True, "pinned": True}).get_json()
    assert dopo["secret"] == 1 and dopo["pinned"] == 1


# ---------------------------------------------------- spesa automatica
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


# ---------------------------------------------------- progetti
def test_progetto_si_crea_con_tutti_i_campi(client):
    r = client.post("/api/projects", json={
        "title": "Sistemare il garage", "description": "Liberare l'angolo",
        "start_date": "2026-09-01", "end_date": "2026-09-30", "priority": 5,
    })
    assert r.status_code == 201
    p = r.get_json()
    assert p["title"] == "Sistemare il garage"
    assert p["priority"] == 5
    assert p["done"] is False


def test_progetto_senza_titolo_rifiutato(client):
    assert client.post("/api/projects", json={"description": "x"}).status_code == 400


def test_progetto_priorita_fuori_scala_rifiutata(client):
    assert client.post("/api/projects", json={"title": "X", "priority": 6}).status_code == 400
    assert client.post("/api/projects", json={"title": "X", "priority": 0}).status_code == 400


def test_progetto_fine_prima_dell_inizio_rifiutata(client):
    r = client.post("/api/projects", json={
        "title": "X", "start_date": "2026-09-30", "end_date": "2026-09-01"})
    assert r.status_code == 400


def test_progetto_si_conclude_e_si_riapre(client):
    pid = client.post("/api/projects", json={"title": "X", "priority": 3}).get_json()["id"]
    assert client.put(f"/api/projects/{pid}", json={"done": True}).get_json()["done"] is True
    assert client.put(f"/api/projects/{pid}", json={"done": False}).get_json()["done"] is False


def test_concludere_un_progetto_non_ne_cancella_i_campi(client):
    """Spuntare "concluso" non deve richiedere di rimandare tutto il resto."""
    pid = client.post("/api/projects", json={
        "title": "X", "description": "Nota", "priority": 4}).get_json()["id"]
    client.put(f"/api/projects/{pid}", json={"done": True})
    p = client.get("/api/projects").get_json()[0]
    assert p["description"] == "Nota" and p["priority"] == 4


def test_progetti_ordinati_per_priorita(client):
    for t, p in (("Bassa", 1), ("Alta", 5), ("Media", 3)):
        client.post("/api/projects", json={"title": t, "priority": p})
    assert [p["title"] for p in client.get("/api/projects").get_json()] == ["Alta", "Media", "Bassa"]


def test_progetti_conclusi_in_fondo(client):
    a = client.post("/api/projects", json={"title": "A", "priority": 5}).get_json()["id"]
    client.post("/api/projects", json={"title": "B", "priority": 1})
    client.put(f"/api/projects/{a}", json={"done": True})
    assert [p["title"] for p in client.get("/api/projects").get_json()] == ["B", "A"]


def test_progetto_eliminato(client):
    pid = client.post("/api/projects", json={"title": "X"}).get_json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.get("/api/projects").get_json() == []


def test_progetto_inesistente_da_404(client):
    assert client.put("/api/projects/999", json={"title": "X"}).status_code == 404
    assert client.delete("/api/projects/999").status_code == 404


def test_progetto_priorita_predefinita_tre(client):
    assert client.post("/api/projects", json={"title": "X"}).get_json()["priority"] == 3


# ---------------------------------------------------- magazzino
def test_voce_magazzino_si_crea(client):
    r = client.post("/api/storage", json={
        "name": "Sapone per i piatti", "category": "Pulizia casa",
        "place": "Cucina", "quantity": 2, "unit": "pz", "min_quantity": 1,
    })
    assert r.status_code == 201
    v = r.get_json()
    assert v["name"] == "Sapone per i piatti"
    assert v["low"] is False


def test_voce_magazzino_senza_nome_rifiutata(client):
    assert client.post("/api/storage", json={"quantity": 1}).status_code == 400


def test_voce_in_esaurimento_segnalata(client):
    """Sotto la scorta minima la voce si segnala: e' il motivo del magazzino."""
    client.post("/api/storage", json={"name": "Batterie", "quantity": 1, "min_quantity": 4})
    assert client.get("/api/storage").get_json()[0]["low"] is True


def test_voce_senza_scorta_minima_non_e_mai_in_esaurimento(client):
    """Senza soglia non si segnala nulla: 0 non e' una soglia."""
    client.post("/api/storage", json={"name": "Quadro", "quantity": 0, "min_quantity": 0})
    assert client.get("/api/storage").get_json()[0]["low"] is False


def test_giacenza_magazzino_si_ritocca_da_sola(client):
    """PATCH cambia la giacenza senza toccare il resto della voce."""
    v = client.post("/api/storage", json={
        "name": "Detersivo", "category": "Pulizia casa", "place": "Cantina",
        "quantity": 5, "min_quantity": 2, "notes": "scaffale alto"}).get_json()
    dopo = client.patch(f"/api/storage/{v['id']}", json={"quantity": 1}).get_json()
    assert dopo["quantity"] == pytest.approx(1)
    assert dopo["category"] == "Pulizia casa" and dopo["place"] == "Cantina"
    assert dopo["notes"] == "scaffale alto"
    assert dopo["low"] is True


def test_voce_magazzino_si_modifica_interamente(client):
    v = client.post("/api/storage", json={"name": "Rasoio", "quantity": 1}).get_json()
    dopo = client.put(f"/api/storage/{v['id']}", json={
        "name": "Rasoi", "category": "Igiene personale", "place": "Bagno",
        "quantity": 3, "unit": "pz", "min_quantity": 1, "notes": "usa e getta"}).get_json()
    assert dopo["name"] == "Rasoi" and dopo["quantity"] == pytest.approx(3)


def test_voce_magazzino_eliminata(client):
    v = client.post("/api/storage", json={"name": "Mensola"}).get_json()
    assert client.delete(f"/api/storage/{v['id']}").status_code == 200
    assert client.get("/api/storage").get_json() == []


def test_magazzino_inesistente_da_404(client):
    assert client.delete("/api/storage/999").status_code == 404


def test_magazzino_non_entra_nella_spesa(client):
    """Un detergente non e' un ingrediente: non deve finire in lista."""
    client.post("/api/storage", json={"name": "Sapone", "quantity": 1})
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    assert [i["name"] for i in client.get("/api/shopping").get_json()] == ["Pasta"]


def test_magazzino_non_tocca_la_dispensa(client):
    """Le due sezioni sono separate: riempire una non riempie l'altra."""
    client.post("/api/storage", json={"name": "Sapone", "quantity": 3})
    assert client.get("/api/pantry").get_json() == []


def test_magazzino_meta_ha_categorie_e_luoghi(client):
    meta = client.get("/api/magazzino/meta").get_json()
    assert "Pulizia casa" in meta["categories"]
    assert "Ripostiglio" in meta["places"]


def test_magazzino_ordina_prima_quello_che_manca(client):
    client.post("/api/storage", json={"name": "Abbondante", "quantity": 10, "min_quantity": 1})
    client.post("/api/storage", json={"name": "Scarso", "quantity": 1, "min_quantity": 5})
    assert [v["name"] for v in client.get("/api/storage").get_json()][0] == "Scarso"

