"""Verifica conversione unità e generazione lista della spesa. Crea un DB temporaneo."""
import base64
import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import date

import pytest

# La cartella dell'app, quella dove girano `avvia.sh` e i test che leggono i
# file veri (Dockerfile, CSS, script di Windows). Si ricava dal file invece di
# scriverla fissa: `test_cucina.py` sta nella cartella dell'app, quindi funziona
# in qualunque posto sia stata clonata — la copia di lavoro qui si chiama
# `project`, non `gg`, e un percorso fisso faceva fallire sette test.
BASE_APP = os.path.dirname(os.path.abspath(__file__))

DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["CUCINA_DB"] = DB

import app as app_module  # noqa: E402
import allergens  # noqa: E402
import comprensione  # noqa: E402
import copie  # noqa: E402
import houses  # noqa: E402
import igiene  # noqa: E402
import units  # noqa: E402
import voice  # noqa: E402
import voce_cloud  # noqa: E402

# Il registro delle case nel test non tocca quello vero del progetto.
REGISTRO = os.path.join(os.path.dirname(DB), "test-houses.db")
houses.REGISTRY_PATH = REGISTRO
houses.CASE_DIR = os.path.join(os.path.dirname(DB), "test-case")
# Anche i dati: senza questo le copie automatiche finirebbero nella cartella
# vera dell'app, e i test lascerebbero file che non hanno creato loro.
houses.DATA_DIR = os.path.dirname(DB)

CASA_TEST = "casa-test"
PASSWORD_TEST = "password-di-prova"


@pytest.fixture(autouse=True)
def percorsi_dei_dati():
    """Rimette i percorsi dei dati nel temporaneo prima di ogni test.

    Un test ricarica `houses` per provare `MAGGIORDOMO_DATA`: al ritorno il
    modulo ha di nuovo i percorsi accanto al codice, e i test successivi
    creerebbero case e copie nei dati veri dell'app. Rimettendoli qui, l'esito
    non dipende dall'ordine in cui i test vengono eseguiti.
    """
    houses.REGISTRY_PATH = REGISTRO
    houses.CASE_DIR = os.path.join(os.path.dirname(DB), "test-case")
    houses.DATA_DIR = os.path.dirname(DB)
    # i tentativi falliti hanno un contatore per casa e per indirizzo: azzerarlo
    # qui evita che un test faccia aspettare il successivo
    houses.dimentica_tentativi()
    yield


def registra_casa(nome="Casa Test", password=PASSWORD_TEST, db_path=None):
    """Registra la casa di prova e le prepara il database.

    I test delle funzioni (ricette, dispensa, spesa...) non riguardano le case:
    questa casa unica serve a farli girare come prima, quando il database era
    uno solo. I test della separazione fra case creano le proprie.
    """
    houses.init_registro()
    if not houses.esiste(CASA_TEST):
        houses.registra(CASA_TEST, nome, password, db_file="")
    percorso = db_path or houses.db_path(CASA_TEST)
    app_module.init_db(percorso)
    return CASA_TEST


@pytest.fixture()
def client():
    if os.path.exists(REGISTRO):
        os.remove(REGISTRO)
    if os.path.exists(DB):
        os.remove(DB)
    copie.svuota()
    for f in os.listdir(houses.CASE_DIR) if os.path.isdir(houses.CASE_DIR) else []:
        if f.startswith("case-"):
            os.remove(os.path.join(houses.CASE_DIR, f))
    registra_casa()
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        # la casa di prova e' collegata in partenza: i test che non riguardano
        # l'accesso non devono ripetere il login ogni volta
        c.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
        yield c


@pytest.fixture()
def casa_test():
    """La casa di prova registrata, per i test che non passano dalla pagina."""
    if os.path.exists(REGISTRO):
        os.remove(REGISTRO)
    for f in os.listdir(houses.CASE_DIR) if os.path.isdir(houses.CASE_DIR) else []:
        if f.startswith("case-"):
            os.remove(os.path.join(houses.CASE_DIR, f))
    registra_casa()
    yield {"slug": CASA_TEST, "password": PASSWORD_TEST}


@pytest.fixture()
def anon():
    """Un client senza nessuna casa collegata: per i test dell'accesso."""
    if os.path.exists(REGISTRO):
        os.remove(REGISTRO)
    if os.path.exists(DB):
        os.remove(DB)
    for f in os.listdir(houses.CASE_DIR) if os.path.isdir(houses.CASE_DIR) else []:
        if f.startswith("case-"):
            os.remove(os.path.join(houses.CASE_DIR, f))
    registra_casa()
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


def test_voce_rimozione_non_diventa_un_aggiunta():
    """Il difetto visto dall'utente: "togli il latte dalla dispensa" **aggiungeva**
    il latte in dispensa, con l'articolo chiamato "togli il latte".

    Verificato sull'endpoint vero prima della correzione: rispondeva "Fatto.
    Togli il latte in dispensa, 1 pz." Non e' un fraintendimento innocuo: scrive
    nella dispensa una voce che non esiste e non toglie quel che serviva."""
    cmd = voice.parse("togli il latte dalla dispensa")
    assert cmd["intent"] == "pantry_remove"
    assert cmd["name"] == "latte"

    # senza destinazione si toglie dalla lista: la dispensa si nomina, la lista
    # e' il posto da cui si toglie e basta
    assert voice.parse("togli il latte")["intent"] == "shopping_remove"
    assert voice.parse("rimuovi il pane dalla spesa")["intent"] == "shopping_remove"


def test_voce_consumo_scala_la_dispensa():
    """"ho finito il latte" e "ho usato 300 grammi di farina" non sono aggiunte:
    consumano. Prima non venivano capite affatto oppure finivano in lista."""
    cmd = voice.parse("ho finito il latte")
    assert cmd["intent"] == "pantry_consume" and cmd["name"] == "latte"

    cmd = voice.parse("ho usato 300 grammi di farina")
    assert cmd["intent"] == "pantry_consume"
    assert cmd["name"] == "farina" and cmd["quantity"] == 300.0 and cmd["unit"] == "g"


def test_voce_preso_spunta_la_lista():
    """Non e' una rimozione: la voce resta fra le prese, come spuntarla a mano."""
    cmd = voice.parse("ho preso il pane")
    assert cmd["intent"] == "shopping_check" and cmd["name"] == "pane"
    assert voice.parse("ho comprato il latte")["intent"] == "shopping_check"


def test_voce_la_cottura_resta_la_cottura():
    """Il verbo "ho preparato" e' cottura di una ricetta, non aggiunta a dispensa:
    la nuova lettura non deve rubargli la frase."""
    cmd = voice.parse("ho cucinato la carbonara")
    assert cmd["intent"] == "recipe_cooked" and cmd["name"] == "carbonara"


def test_voce_togliere_dalla_dispensa_endpoint(client):
    """Dal server: la voce sparisce davvero, e le altre restano."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 2, "unit": "l"})
    client.post("/api/pantry", json={"name": "Pane", "quantity": 1, "unit": "pz"})
    r = client.post("/api/voice", json={"text": "togli il latte dalla dispensa"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]
    nomi = [v["name"] for v in client.get("/api/pantry").get_json()]
    assert "Latte" not in nomi
    assert "Pane" in nomi, "le altre voci della dispensa non si toccano"


def test_voce_consumo_scala_la_quantita_endpoint(client):
    """Con una quantita' la voce resta, diminuita; se arriva a zero sparisce."""
    client.post("/api/pantry", json={"name": "Farina", "quantity": 1000, "unit": "g"})
    r = client.post("/api/voice", json={"text": "ho usato 300 grammi di farina"})
    assert r.status_code == 200
    riga = [v for v in client.get("/api/pantry").get_json() if v["name"] == "Farina"][0]
    assert riga["quantity"] == 700

    client.post("/api/voice", json={"text": "ho finito la farina"})
    assert not [v for v in client.get("/api/pantry").get_json() if v["name"] == "Farina"]


def test_voce_quello_che_non_capisce_non_scrive_niente(client):
    """Una frase senza un alimento non deve inventare un articolo: meglio non
    capire che sporcare la dispensa."""
    client.post("/api/voice", json={"text": "prepara la carbonara"})
    dispensa = client.get("/api/pantry").get_json()
    assert dispensa == [], f"la dispensa doveva restare vuota, invece: {dispensa}"


def test_voce_domanda_su_cosa_comprare_non_e_un_ordine(client):
    """"cosa devo comprare" finiva in lista come articolo "cosa": rispondeva
    "Fatto. Cosa in lista, 1 pz." — una domanda **eseguita** come ordine. Ora e'
    una domanda, e la risposta e' quello che manca."""
    cmd = voice.parse("cosa devo comprare")
    assert cmd["intent"] == "domanda" and cmd["area"] == "shopping"

    # il luogo vince: "cosa manca in dispensa" parla della dispensa
    assert voice.parse("cosa manca in dispensa")["area"] == "pantry"
    # un alimento vince sulla lista: "quanto sale serve" cerca il sale
    cmd = voice.parse("quanto sale serve")
    assert cmd["intent"] == "domanda" and cmd["area"] == "pantry" and cmd["query"] == "sale"

    r = client.post("/api/voice", json={"text": "cosa devo comprare"})
    assert r.status_code == 200
    assert client.get("/api/shopping").get_json() == [], "nessun articolo 'cosa' in lista"


def test_voce_domanda_sulla_lista_risponde_con_le_voci(client):
    """La domanda sulla lista nominava una tabella inesistente (`FROM shopping`) e
    rispondeva 500. Ora elenca le voci vere."""
    client.post("/api/shopping", json={"name": "Latte", "quantity": 2, "unit": "l"})
    r = client.post("/api/voice", json={"text": "cosa devo comprare"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]

    r = client.post("/api/voice", json={"text": "cosa c'è in lista"})
    assert r.status_code == 200
    assert "Latte" in r.get_json()["message"]


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


def test_voce_crea_ricetta_dettata():
    """Dettare una ricetta nuova: si apre il modulo col nome, non si crea a vuoto."""
    casi = {
        "crea la ricetta carbonara": "carbonara",
        "aggiungi la ricetta carbonara": "carbonara",
        "crea una ricetta chiamata pasta al forno": "pasta al forno",
        "nuova ricetta polpette della nonna": "polpette della nonna",
        "salva la ricetta risotto ai funghi": "risotto ai funghi",
        "prepara una ricetta per la carbonara": "carbonara",
        "vorrei aggiungere una ricetta di lasagne": "lasagne",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_add", frase
        assert cmd["name"] == atteso, frase


def test_voce_senza_nome_chiede_il_modulo_vuoto():
    """"aggiungi una ricetta" non ha un nome: il modulo si apre comunque, vuoto."""
    cmd = voice.parse("aggiungi una ricetta")
    assert cmd["intent"] == "recipe_add"
    assert cmd["name"] == ""


def test_voce_crea_ricetta_con_i_verbi_di_tutti_i_giorni():
    """Nessuno dice "crea la ricetta": si dice "fammi una ricetta di lasagne".

    Con i soli verbi "crea/aggiungi/salva" la frase piu' naturale di tutte
    restava `unknown`, e chi la diceva riceveva "non ho capito" per una cosa
    chiarissima. "fai" e "fammi" sono verbi di creazione come gli altri.
    """
    casi = {
        "fai una ricetta di lasagne": "lasagne",
        "fammi una ricetta di carbonara": "carbonara",
        "mi fai una ricetta di lasagne": "lasagne",
        "fai la ricetta carbonara": "carbonara",
        "fammi la ricetta carbonara": "carbonara",
        "fare una ricetta di pizza": "pizza",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_add", frase
        assert cmd["name"] == atteso, frase


def test_voce_fammi_vedere_non_crea_una_ricetta():
    """"fammi" ora crea ricette, quindi "fammi **vedere**" deve restare fuori.

    Chiedere di vedere una ricetta e vedersi aprire il modulo di una ricetta
    nuova e' l'errore opposto a quello appena corretto, e altrettanto fastidioso:
    il verbo di creazione c'e', ma il senso e' un altro.
    """
    for frase in ("fammi vedere la ricetta carbonara",
                  "voglio vedere la ricetta carbonara",
                  "mi fai leggere la ricetta carbonara"):
        assert voice.parse(frase)["intent"] != "recipe_add", frase


def test_voce_fammi_la_spesa_non_scrive_fammi_in_lista():
    """Una frase di comando senza alimento non deve produrre un alimento.

    "fammi la spesa" non dice *cosa* comprare: senza questa guardia il verbo
    finiva in lista come articolo chiamato "fammi", ed era lo stesso guasto di
    "che cosa c'e' in dispensa" per un'altra strada. Una voce sbagliata in lista
    resta li' per sempre, quindi meglio non capire.
    """
    for frase in ("fammi la spesa", "fai la spesa", "fammi la lista della spesa",
                  "fai il punto della spesa", "fammi vedere la spesa",
                  "fammi la dispensa", "fai il magazzino"):
        cmd = voice.parse(frase)
        assert cmd["intent"] == "unknown", (frase, cmd)


def test_una_frase_senza_alimento_non_tocca_la_lista(client):
    """Il comportamento vero: dopo "fammi la spesa" la lista resta vuota.

    Provarlo con `voice.parse` dice che la frase non viene capita; provarlo qui
    dice che il server non ha scritto niente. Sono due cose diverse: la prima
    puo' essere vera mentre la seconda e' falsa se un ramo a valle indovina.
    """
    lista_prima = client.get("/api/shopping").get_json()
    for frase in ("fammi la spesa", "fai la spesa", "fammi la lista della spesa"):
        assert client.post("/api/voice", json={"text": frase}).status_code == 422
    assert client.get("/api/shopping").get_json() == lista_prima


def test_voce_la_parola_della_destinazione_non_e_un_alimento():
    """La destinazione dice *dove*, non *cosa*: non fa parte del nome.

    "il sapone al magazzino" -> "sapone" (non "sapone magazzino"), e in
    "aggiungi il latte alla spesa" l'articolo e' "latte", non "latte spesa".
    """
    assert voice.parse("metti il sapone al magazzino")["name"] == "sapone"
    assert voice.parse("aggiungi il latte alla spesa")["name"] == "latte"
    assert voice.parse("metti il latte in lista")["name"] == "latte"


def test_voce_ricetta_non_finisce_nella_spesa():
    """Senza il ramo `recipe_add`, "aggiungi la ricetta carbonara" diventava una
    voce di lista della spesa chiamata "ricetta carbonara"."""
    cmd = voice.parse("aggiungi la ricetta carbonara")
    assert cmd["intent"] != "shopping_add"
    assert cmd["intent"] != "pantry_add"


def test_voce_ricetta_non_tocca_gli_altri_comandi():
    """Le frasi di ingredienti, allergie e ricerca restano quelle di prima."""
    assert voice.parse("aggiungi il pane")["intent"] == "shopping_add"
    assert voice.parse("metti il burro in dispensa")["intent"] == "pantry_add"
    assert voice.parse("sono allergico al nichel")["intent"] == "term_add"
    assert voice.parse("cerca la carbonara")["intent"] == "recipe_search"
    assert voice.parse("tre confezioni di passata di pomodoro in dispensa")["name"] == "passata di pomodoro"


def test_voce_ricetta_ambigua_non_diventa_un_articolo():
    """Le frasi in cui "ricetta" è l'oggetto del discorso ma non una ricetta da
    scrivere non devono produrre una voce di lista chiamata "ricetta ...".

    Sono i casi in cui la frase parla di una ricetta senza chiedere di crearne
    una: una destinazione esplicita ("nel carrello"), un verbo debole ("vorrei"),
    o gli ingredienti di una ricetta che esiste già."""
    for frase in ("vorrei una ricetta",
                  "voglio una ricetta",
                  "metti la ricetta carbonara",
                  "mi serve una ricetta per la cena",
                  "aggiungi la ricetta nel carrello",
                  "metti la ricetta nel carrello",
                  "aggiungi gli ingredienti della ricetta carbonara"):
        cmd = voice.parse(frase)
        assert cmd["intent"] != "shopping_add", frase
        assert cmd["intent"] != "pantry_add", frase
        assert cmd["intent"] != "recipe_add", frase


def test_voce_ricetta_nel_carrello_resta_una_destinazione():
    """Una destinazione esplicita vince sulla parola "ricetta"."""
    assert voice.parse("aggiungi la ricetta nel carrello")["intent"] == "unknown"


def test_voce_ricetta_legge_gli_ingredienti_dettati():
    """Chi detta una ricetta dice anche cosa ci va, e le dosi non devono finire
    nel nome.

    Prima finivano tutte nel titolo: "crea la ricetta pasta al forno con 500
    grammi di pasta e 300 grammi di pomodoro" diventava una ricetta chiamata
    così, dosi comprese. Il modulo si apriva con quel titolo assurdo e la voce
    sembrava aver capito, mentre l'unica cosa utile — gli ingredienti — andava
    persa."""
    cmd = voice.parse("crea la ricetta pasta al forno con 500 grammi di pasta e 300 grammi di pomodoro")
    assert cmd["intent"] == "recipe_add"
    assert cmd["name"] == "pasta al forno"
    assert cmd["items"] == [{"name": "pasta", "quantity": 500, "unit": "g"},
                            {"name": "pomodoro", "quantity": 300, "unit": "g"}]


def test_voce_ricetta_ingredienti_contati_senza_unita():
    """"4 uova" è una dose anche senza unità di misura."""
    cmd = voice.parse("crea la ricetta carbonara con 4 uova")
    assert cmd["name"] == "carbonara"
    assert cmd["items"] == [{"name": "uova", "quantity": 4, "unit": None}]


def test_voce_ricetta_virgola_dettata_separa_gli_ingredienti():
    """Le virgole non arrivano dal riconoscimento vocale: "guanciale, 4 uova"
    è "guanciale 4 uova", e il numero apre un ingrediente nuovo."""
    cmd = voice.parse("nuova ricetta carbonara con 200 grammi di guanciale, 4 uova e 100 grammi di pecorino")
    assert cmd["name"] == "carbonara"
    assert [i["name"] for i in cmd["items"]] == ["guanciale", "uova", "pecorino"]
    assert [i["quantity"] for i in cmd["items"]] == [200, 4, 100]


def test_voce_ricetta_senza_dosi_resta_solo_il_nome():
    """Un nome con un numero dentro non è un elenco di ingredienti.

    "torta 7 vasetti" è il nome di una torta: senza l'unità di misura o il "con",
    un numero non basta a dire che comincia l'elenco, altrimenti la ricetta si
    chiamerebbe "torta"."""
    cmd = voice.parse("crea la ricetta torta 7 vasetti")
    assert cmd["name"] == "torta 7 vasetti"
    assert cmd["items"] == []


def test_voce_ricetta_gli_ingredienti_non_sono_un_nome_di_ricetta():
    """Gli ingredienti dettati restano fuori dal nome, ma senza dosi non c'è
    niente da separare: il nome resta quello che si è detto."""
    cmd = voice.parse("crea la ricetta pasta al forno con la pasta e il pomodoro")
    assert cmd["name"] == "pasta al forno con la pasta e il pomodoro"
    assert cmd["items"] == []


def test_voce_endpoint_ricetta_riporta_gli_ingredienti(client):
    """Il modulo deve poterli precompilare: la risposta li porta con sé."""
    r = client.post("/api/voice",
                    json={"text": "crea la ricetta pasta al forno con 500 grammi di pasta e 300 grammi di pomodoro"})
    d = r.get_json()
    assert d["open_recipe_form"] is True
    assert d["name"] == "pasta al forno"
    assert d["items"] == [{"name": "pasta", "quantity": 500, "unit": "g"},
                          {"name": "pomodoro", "quantity": 300, "unit": "g"}]
    # il messaggio dice che gli ingredienti ci sono: altrimenti sembra che la
    # voce abbia aperto un modulo vuoto
    assert "2" in d["message"]


def test_voce_endpoint_crea_ricetta_apre_il_modulo(client):
    r = client.post("/api/voice", json={"text": "crea la ricetta pasta al forno"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "recipe_add"
    assert dati["open_recipe_form"] is True
    assert dati["name"] == "pasta al forno"
    # non si crea nulla da soli: il modulo lo compila l'utente
    assert client.get("/api/recipes").get_json() == []


def test_voce_endpoint_ricetta_senza_nome(client):
    r = client.post("/api/voice", json={"text": "aggiungi una ricetta"})
    assert r.status_code == 200
    assert r.get_json()["open_recipe_form"] is True


def test_voce_ricetta_cucinata_riconosce_il_nome():
    """"ho cucinato/preparato X" e' una ricetta consumata, non una da creare."""
    casi = {
        "ho cucinato pasta al sugo": "pasta al sugo",
        "ho preparato pasta al sugo": "pasta al sugo",
        "ho cucinato la pasta al sugo": "pasta al sugo",
        "ho cotto le lasagne": "lasagne",
        "avevo preparato il risotto ai funghi": "risotto ai funghi",
        "ho cucinato pasta al sugo oggi": "pasta al sugo",
        "ho preparato una ricetta per la carbonara": "carbonara",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "recipe_cooked", frase
        assert cmd["name"] == atteso, frase


def test_voce_cucinato_non_e_una_ricetta_da_creare():
    """Il ramo cucinato sta prima di `recipe_add`: "ho preparato una ricetta"
    aprirebbe altrimenti il modulo di una ricetta nuova."""
    assert voice.parse("ho preparato una ricetta per la carbonara")["intent"] != "recipe_add"
    # l'imperativo resta una creazione: e' il participio passato a cambiare tutto
    assert voice.parse("prepara una ricetta per la carbonara")["intent"] == "recipe_add"
    assert voice.parse("prepara la ricetta carbonara")["intent"] == "recipe_add"


def test_voce_cucinato_non_riconosce_frasi_generiche():
    """Senza indicare cosa si e' cucinato, o con un participio aggettivale, non
    si scala niente: e' un comando che tocca la dispensa, va riconosciuto bene."""
    for frase in ("ho preparato la cena", "ho mangiato la pasta",
                  "la pasta cucinata ieri", "ho cotto"):
        assert voice.parse(frase)["intent"] != "recipe_cooked", frase


def _ricetta_con_ingredienti(client, nome, ingredienti):
    """Crea una ricetta passando dall'API, come farebbe il modulo."""
    r = client.post("/api/recipes", json={
        "name": nome,
        "items": [{"name": n, "quantity": q, "unit": u} for n, q, u in ingredienti],
    })
    assert r.status_code == 201
    return r.get_json()["id"]


def test_voce_endpoint_cucinato_scala_la_dispensa(client):
    """Il caso della richiesta: pasta e sugo in dispensa, si cucina "pasta al
    sugo" e le quantita' degli ingredienti si sottraggono."""
    _ricetta_con_ingredienti(client, "pasta al sugo",
                             [("pasta", 500, "g"), ("sugo", 300, "g")])
    client.post("/api/pantry", json={"name": "pasta", "quantity": 1, "unit": "kg"})
    client.post("/api/pantry", json={"name": "sugo", "quantity": 500, "unit": "g"})

    r = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "recipe_cooked"
    assert dati["scalati"] == ["pasta", "sugo"]

    dispensa = {v["name"]: (v["quantity"], v["unit"]) for v in client.get("/api/pantry").get_json()}
    # 1 kg - 500 g = 500 g, e la riga resta in chili: e' l'unita' scelta dall'utente
    assert dispensa["pasta"] == (0.5, "kg")
    assert dispensa["sugo"] == (200, "g")


def test_voce_endpoint_preparato_scala_la_dispensa_come_cucinato(client):
    """"ho preparato X" deve fare **lo stesso** di "ho cucinato X".

    Sono due modi di dire la stessa cosa, e la frase dell'utente li usa
    entrambi: se il percorso dell'uno si rompe, l'altro continuerebbe a
    funzionare e il guasto passerebbe inosservato.
    """
    _ricetta_con_ingredienti(client, "risotto ai funghi", [("riso", 300, "g")])
    client.post("/api/pantry", json={"name": "riso", "quantity": 1, "unit": "kg"})

    r = client.post("/api/voice", json={"text": "ho preparato il risotto ai funghi"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "recipe_cooked"
    assert r.get_json()["scalati"] == ["riso"]
    assert client.get("/api/pantry").get_json()[0]["quantity"] == pytest.approx(0.7)


def test_voce_endpoint_cucinato_svuota_la_riga_a_zero(client):
    """Una giacenza che arriva a zero si toglie: una riga a zero non e' una scorta."""
    _ricetta_con_ingredienti(client, "minestrone", [("carote", 2, "pz")])
    client.post("/api/pantry", json={"name": "carote", "quantity": 2, "unit": "pz"})

    client.post("/api/voice", json={"text": "ho cucinato il minestrone"})
    assert client.get("/api/pantry").get_json() == []


def test_voce_endpoint_cucinato_non_bastava(client):
    """Se in dispensa non basta, si dice: dire "fatto" sarebbe una bugia."""
    _ricetta_con_ingredienti(client, "torta", [("farina", 500, "g"), ("zucchero", 200, "g")])
    client.post("/api/pantry", json={"name": "farina", "quantity": 100, "unit": "g"})

    dati = client.post("/api/voice", json={"text": "ho cucinato la torta"}).get_json()
    assert "farina" in dati["mancanti"]
    assert "farina" not in dati["scalati"]
    # la farina c'era ma non bastava: si scala quello che c'e', non si va sotto zero
    dispensa = {v["name"]: v["quantity"] for v in client.get("/api/pantry").get_json()}
    assert "farina" not in dispensa


def test_voce_endpoint_cucinato_unita_incompatibili_non_si_toccano(client):
    """Grammi e pezzi non si convertono: la giacenza resta, l'ingrediente manca."""
    _ricetta_con_ingredienti(client, "uova sode", [("uova", 4, "pz")])
    client.post("/api/pantry", json={"name": "uova", "quantity": 300, "unit": "g"})

    dati = client.post("/api/voice", json={"text": "ho cucinato uova sode"}).get_json()
    assert dati["scalati"] == []
    assert dati["mancanti"] == ["uova"]
    dispensa = {v["name"]: v["quantity"] for v in client.get("/api/pantry").get_json()}
    assert dispensa["uova"] == 300


def test_voce_endpoint_cucinato_ricetta_inesistente(client):
    """Una ricetta che non c'e' non deve toccare la dispensa."""
    client.post("/api/pantry", json={"name": "farina", "quantity": 1, "unit": "kg"})
    r = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "recipe_cooked"
    assert client.get("/api/pantry").get_json()[0]["quantity"] == 1


def test_voce_endpoint_cucinato_nome_ambiguo_chiede(client):
    """Due ricette che somigliano: si chiede il nome per intero invece di
    scegliere a caso e scalare la dispensa sbagliata."""
    _ricetta_con_ingredienti(client, "pasta al sugo", [("pasta", 500, "g")])
    _ricetta_con_ingredienti(client, "pasta al sugo della nonna", [("pasta", 500, "g")])
    client.post("/api/pantry", json={"name": "pasta", "quantity": 2, "unit": "kg"})

    dati = client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"}).get_json()
    # il nome esatto esiste: vince, e la dispensa si scala
    assert dati["scalati"] == ["pasta"]

    dati = client.post("/api/voice", json={"text": "ho cucinato pasta"}).get_json()
    assert "Dimmi il nome per intero" in dati["message"]
    assert "scalati" not in dati


def test_voce_endpoint_cucinato_rimette_in_lista_quello_consumato(client):
    """Quello che si e' consumato torna da comprare: la lista segue la dispensa."""
    rid = _ricetta_con_ingredienti(client, "pasta al sugo", [("pasta", 500, "g")])
    # la scorta copre esattamente il fabbisogno del piano: la lista e' vuota
    client.post("/api/pantry", json={"name": "pasta", "quantity": 500, "unit": "g"})
    client.post("/api/plan", json={"date": date.today().isoformat(), "meal": "cena", "recipe_id": rid})
    assert {v["name"] for v in client.get("/api/shopping").get_json()} == set()

    client.post("/api/voice", json={"text": "ho cucinato pasta al sugo"})
    # dopo averla consumata la scorta non copre piu' il fabbisogno: torna in lista
    assert {v["name"] for v in client.get("/api/shopping").get_json()} == {"pasta"}


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
    assert "farina" in r.get_json()["message"].lower()

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


def test_voce_magazzino_non_e_dispensa_ne_spesa():
    """Il magazzino è una terza destinazione: sapone e detersivo non sono cibo."""
    cmd = voice.parse("aggiungi il sapone al magazzino")
    assert cmd["intent"] == "storage_add"
    assert cmd["name"] == "sapone"

    cmd = voice.parse("metti due rotoli di carta igienica in magazzino")
    assert cmd["intent"] == "storage_add"
    assert cmd["name"] == "rotoli di carta igienica" and cmd["quantity"] == 2.0

    # la destinazione esplicita vince sulla parola dell'oggetto: il sapone
    # messo in dispensa resta in dispensa
    assert voice.parse("aggiungi il sapone in dispensa")["intent"] == "pantry_add"
    # e un prodotto da mangiare senza indizi resta in lista
    assert voice.parse("aggiungi il latte")["intent"] == "shopping_add"


def test_voce_magazzino_riconosce_il_luogo():
    """Il magazzino si dice anche con il posto: "in garage", "in cantina"."""
    cmd = voice.parse("metti il detersivo in cantina")
    assert cmd["intent"] == "storage_add"
    assert (cmd["name"], cmd["place"]) == ("detersivo", "Cantina")

    cmd = voice.parse("aggiungi una scatola di viti in garage")
    assert cmd["intent"] == "storage_add"
    assert (cmd["name"], cmd["place"]) == ("scatola di viti", "Garage")

    # un luogo senza destinazione esplicita vale comunque
    assert voice.parse("metti il trapano in soffitta")["intent"] == "storage_add"


def test_voce_magazzino_deduce_la_categoria():
    """Categoria e luogo sono un di più: se non si capiscono restano i predefiniti."""
    assert voice.parse("aggiungi il detersivo al magazzino")["category"] == "Pulizia casa"
    assert voice.parse("aggiungi il sapone al magazzino")["category"] == "Igiene personale"
    assert voice.parse("aggiungi il dentifricio")["category"] == "Igiene personale"
    assert voice.parse("aggiungi una scatola di viti in garage")["category"] == "Ferramenta"
    assert voice.parse("aggiungi delle lampadine in cantina")["category"] == "Elettricita'"
    # senza indizi la categoria resta vuota e decide il server
    assert voice.parse("aggiungi il coso al magazzino")["category"] is None


def test_voce_magazzino_non_ruba_le_parole_al_nome():
    """La parola "magazzino" non deve finire nel nome della cosa."""
    casi = {
        "aggiungi il sapone al magazzino": "sapone",
        "metti il rotolone in magazzino": "rotolone",
        "aggiungi il detersivo alle scorte": "detersivo",
    }
    for frase, atteso in casi.items():
        cmd = voice.parse(frase)
        assert cmd["intent"] == "storage_add", frase
        assert cmd["name"] == atteso, frase


def test_voce_endpoint_aggiunge_al_magazzino(client):
    r = client.post("/api/voice", json={"text": "aggiungi il sapone al magazzino"})
    assert r.status_code == 200
    assert r.get_json()["reload"] == ["magazzino"]

    voci = client.get("/api/storage").get_json()
    assert len(voci) == 1
    assert voci[0]["name"] == "sapone"
    assert voci[0]["category"] == "Igiene personale"
    assert voci[0]["quantity"] == 1

    # niente di tutto questo deve finire in dispensa o in lista
    assert client.get("/api/pantry").get_json() == []
    assert client.get("/api/shopping").get_json() == []

    # una seconda dettatura dello stesso oggetto accoda alla stessa voce
    client.post("/api/voice", json={"text": "aggiungi il sapone al magazzino"})
    voci = client.get("/api/storage").get_json()
    assert len(voci) == 1 and voci[0]["quantity"] == 2

    # lo stesso nome in un luogo diverso e' una voce a parte
    client.post("/api/voice", json={"text": "metti il sapone in garage"})
    voci = client.get("/api/storage").get_json()
    assert len(voci) == 2
    assert {v["place"] for v in voci} == {"Ripostiglio", "Garage"}


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
    DB = houses.db_path(CASA_TEST)   # ora il database e' quello della casa
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
    # il giorno della settimanale si fissa esplicitamente: qui interessa **dove**
    # finisce ogni frequenza, non come si distribuisce la settimana
    piano = igiene.piano(voci, {}, today, giorno_pulizie=5, giorni={2: 4})

    oggi_ids = {v["id"] for elenco in piano["gruppi"].values() for v in elenco}
    assert oggi_ids == {1, 2}, "oggi solo quotidiane e settimanali"
    mese_ids = {v["id"] for elenco in (piano["mese"]["mensili"], piano["mese"]["stagionali"]) for v in elenco}
    assert mese_ids == {3, 4}, "mensili e annuali stanno nel mese"


def test_settimanali_distribuite_su_giorni_diversi():
    """Le settimanali non stanno tutte lo stesso giorno.

    Prima entravano tutte nel giorno fisso, che arrivava a cento minuti di soli
    settimanali: e' l'ammasso che questa distribuzione deve togliere.
    """
    voci = [
        {"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale", "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None},
        {"id": 2, "name": "Pulire il bagno in profondità", "frequency": "settimanale", "minutes": 25, "area": "Bagno", "active": 1, "month": None},
        {"id": 3, "name": "Spolverare", "frequency": "settimanale", "minutes": 15, "area": "Tutta la casa", "active": 1, "month": None},
    ]
    giorni = igiene.giorni_settimanali(voci, giorno_pulizie=5)
    assert len(set(giorni.values())) == 3, "una per giorno"
    assert giorni[1] == 5, "la piu' pesante resta nel giorno scelto"
    assert giorni[2] == 4 and giorni[3] == 3, "le altre riempiono i giorni prima"


def test_una_settimanale_saltata_rientra():
    """Una settimanale non fatta resta nel piano anche dopo il suo giorno.

    Senza, saltare il giorno assegnato la farebbe sparire per una settimana
    intera: sembrerebbe un'attivita' conclusa.
    """
    voci = [{"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale",
             "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None}]
    # assegnata a lunedi' (0), fatta otto giorni fa: e' in ritardo
    giorni = {1: 0}
    piano = igiene.piano(voci, {1: "2026-09-10"}, date(2026, 9, 18), giorni=giorni)
    assert piano["da_fare"] == 1, "in ritardo, rientra"


def test_una_settimanale_mai_fatta_aspetta_il_suo_giorno():
    """Al primo uso le settimanali non devono rientrare tutte insieme.

    Senza questo, il primo giorno d'uso mostrerebbe l'ammasso che la
    distribuzione deve togliere.
    """
    voci = [{"id": 1, "name": "Aspirare e lavare i pavimenti", "frequency": "settimanale",
             "minutes": 30, "area": "Tutta la casa", "active": 1, "month": None}]
    piano = igiene.piano(voci, {}, date(2026, 9, 18), giorni={1: 0})
    assert piano["da_fare"] == 0, "il suo giorno e' lunedi', non venerdi"


def test_la_routine_quotidiana_resta_breve():
    """La routine di ogni giorno deve restare sotto la mezz'ora.

    Oltre, smette di essere una routine e diventa un lavoro: e' il motivo per cui
    il piano veniva abbandonato.
    """
    quotidiane = [v for v in igiene.catalogo() if v["frequency"] == "giornaliera"]
    assert sum(v["minutes"] for v in quotidiane) <= 25
    assert all(v["minutes"] <= 10 for v in quotidiane)


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


def test_api_giorno_pulizie_distribuisce_le_settimanali(client):
    """Le settimanali si distribuiscono, non si ammassano nel giorno scelto.

    Il giorno scelto resta il piu' pesante, ma le altre vanno nei giorni
    precedenti: e' la differenza fra una settimana da cento minuti in un giorno
    solo e una da trenta al massimo.
    """
    import datetime as _dt
    oggi = _dt.date.today()
    client.put("/api/profile", json={"chore_day": oggi.weekday()})
    r = client.get(f"/api/chores?date={oggi.isoformat()}").get_json()
    piano = r["piano"]
    assert piano["giorno_pulizie"] is True
    # oggi tocca solo la sua settimanale, non tutte
    assert piano["settimanali_oggi"] == 1
    # e la settimana e' distribuita: nessun giorno porta tutto
    minuti = [g["minuti"] for g in piano["settimana"]]
    assert max(minuti) <= 30, "nessun giorno con cento minuti di settimanali"
    assert sum(1 for m in minuti if m) == 5, "una settimanale per giorno, cinque giorni"


def test_api_ogni_settimanale_dichiara_il_suo_giorno(client):
    """Il frontend mostra il giorno assegnato: i campi devono esserci.

    Senza, la distribuzione sarebbe invisibile e una settimanale spostata a
    giovedi' sembrerebbe sparita dall'elenco.
    """
    r = client.get("/api/chores").get_json()
    settimanali = [v for v in r["attivita"] if v["frequency"] == "settimanale" and v["active"]]
    assert settimanali
    giorni = [v["giorno_settimanale"] for v in settimanali]
    assert all(g is not None and 0 <= g <= 6 for g in giorni)
    # e il piano espone la settimana, con sette giorni
    assert len(r["piano"]["settimana"]) == 7
    assert all("nome" in g and "minuti" in g for g in r["piano"]["settimana"])


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


# ------------------------------------------------- foto del magazzino
# La foto serve a riconoscere a colpo d'occhio una scatola di cui non si ricorda
# il nome. Si verifica il giro completo: si carica, si rilegge identica, si
# sostituisce, si toglie. E si verifica che la foto resti un dato della casa,
# non un file condiviso: non deve essere visibile dall'altra casa.

# Un PNG 1x1 vero: i byte devono tornare identici, quindi non basta una stringa
# qualsiasi.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def data_url(dati=PNG_1PX, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(dati).decode()


def voce_con_foto(client, nome="Sapone"):
    sid = client.post("/api/storage", json={"name": nome, "quantity": 1}).get_json()["id"]
    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url()})
    assert r.status_code == 200, r.data
    return sid


def version_foto(client, sid):
    """La versione (`?v=`) che il client userebbe per la foto di questa voce."""
    v = next(x for x in client.get("/api/storage").get_json() if x["id"] == sid)
    return v["photo_url"].partition("?v=")[2]


def righe_foto(sid):
    """Quante foto ha questa voce nel database della casa di prova."""
    with closing(sqlite3.connect(houses.db_path(CASA_TEST))) as con:
        return con.execute(
            "SELECT COUNT(*) FROM storage_photos WHERE storage_id = ?", (sid,)).fetchone()[0]


def test_dettaglio_di_una_voce(client):
    sid = client.post("/api/storage", json={"name": "Sapone", "quantity": 2}).get_json()["id"]
    r = client.get(f"/api/storage/{sid}")
    assert r.status_code == 200
    v = r.get_json()
    assert v["name"] == "Sapone"
    assert v["quantity"] == 2
    assert v["has_photo"] is False


def test_dettaglio_porta_la_foto(client):
    sid = voce_con_foto(client)
    v = client.get(f"/api/storage/{sid}").get_json()
    assert v["has_photo"] is True
    assert v["photo_url"].startswith(f"/api/storage/{sid}/photo?v=")


def test_una_voce_nasce_senza_foto(client):
    """Il campo esiste da subito: il client non deve indovinare se manca."""
    v = client.post("/api/storage", json={"name": "Sapone"}).get_json()
    assert v["has_photo"] is False
    assert v["photo_url"] == ""


def test_caricare_una_foto_la_rende_visibile_nellelenco(client):
    sid = voce_con_foto(client)
    v = next(x for x in client.get("/api/storage").get_json() if x["id"] == sid)
    assert v["has_photo"] is True
    # l'indirizzo porta la versione della foto: senza, il browser mostrerebbe
    # quella vecchia dopo una sostituzione
    assert v["photo_url"].startswith(f"/api/storage/{sid}/photo?v=")


def test_la_foto_si_rilegge_identica(client):
    """I byte che escono sono quelli che sono entrati, senza conversioni."""
    sid = voce_con_foto(client)
    r = client.get(f"/api/storage/{sid}/photo")
    assert r.status_code == 200
    assert r.data == PNG_1PX
    assert r.headers["Content-Type"].startswith("image/png")


def test_sostituire_la_foto_cambia_la_versione(client):
    """Ricaricare non accumula: la seconda foto prende il posto della prima."""
    sid = voce_con_foto(client)
    prima_versione = version_foto(client, sid)
    altra = PNG_1PX + b"\x00" * 10

    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url(altra)})
    assert r.status_code == 200
    assert client.get(f"/api/storage/{sid}/photo").data == altra
    # la versione cambia insieme ai byte: e' quello che evita al browser di
    # mostrare la foto vecchia presa dalla cache
    assert version_foto(client, sid) != prima_versione
    # una foto per voce, non una pila: la tabella ha una riga sola
    assert righe_foto(sid) == 1


def test_togliere_la_foto(client):
    sid = voce_con_foto(client)
    assert client.delete(f"/api/storage/{sid}/photo").status_code == 200
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404
    v = client.get("/api/storage").get_json()[0]
    assert v["has_photo"] is False


def test_eliminare_la_voce_porta_via_la_foto(client):
    """La foto non deve restare orfana nel database."""
    sid = voce_con_foto(client)
    assert righe_foto(sid) == 1
    client.delete(f"/api/storage/{sid}")
    assert righe_foto(sid) == 0


def test_foto_di_una_voce_inesistente_da_404(client):
    assert client.get("/api/storage/999/photo").status_code == 404
    assert client.post("/api/storage/999/photo", json={"image": data_url()}).status_code == 404


@pytest.mark.parametrize("valore,motivo", [
    ("", "vuoto"),
    ("ciao", "non e' un data url"),
    ("data:image/gif;base64,R0lGODlhAQABAAAAACw=", "formato non gestito"),
    ("data:image/png,ciao", "senza base64"),
    ("data:image/png;base64,!!!non-base64!!!", "base64 illeggibile"),
])
def test_foto_non_valida_rifiutata(client, valore, motivo):
    sid = client.post("/api/storage", json={"name": "Sapone"}).get_json()["id"]
    r = client.post(f"/api/storage/{sid}/photo", json={"image": valore})
    assert r.status_code == 400, f"accettata una foto {motivo}"
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404


def test_foto_troppo_pesante_rifiutata(client):
    """Un file sbagliato non deve far crescere il database senza limite."""
    sid = client.post("/api/storage", json={"name": "Sapone"}).get_json()["id"]
    enorme = b"\xff" * (app_module.FOTO_MAX_BYTE + 1000)
    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url(enorme)})
    assert r.status_code == 400
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404


def test_la_foto_non_e_visibile_senza_accesso(anon):
    """Come il resto dei dati: senza casa collegata non si scarica nulla."""
    assert anon.get("/api/storage/1/photo").status_code == 401
    assert anon.post("/api/storage/1/photo", json={"image": data_url()}).status_code == 401


def test_ogni_casa_vede_solo_le_sue_foto(anon):
    """La foto e' un dato della casa: non deve trapelare nell'altra."""
    anon.post("/api/houses", json={"nome": "Casa Foto A", "password": "aaaa"})
    sid_a = anon.post("/api/storage", json={"name": "Sapone di A"}).get_json()["id"]
    anon.post(f"/api/storage/{sid_a}/photo", json={"image": data_url()})

    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa Foto B", "password": "bbbb"})
    # per B l'id non esiste: nessun dato di A, e nessun modo di agganciarsi
    assert anon.get(f"/api/storage/{sid_a}/photo").status_code == 404
    assert anon.get("/api/storage").get_json() == []


def test_pulizie_vecchie_si_riallineano_al_catalogo(tmp_path):
    """Una casa gia' avviata deve ricevere la nuova routine, non tenerla vecchia.

    Il seme non tocca le righe esistenti, quindi senza questo passaggio chi usa
    l'app da prima continuerebbe a vedere la voce doppia e i minuti di prima:
    il riordino non arriverebbe mai proprio a chi ha piu' da guadagnarci.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        # com'era il database prima: la voce unita e i minuti vecchi
        con.execute("INSERT INTO chores (name, area, frequency, minutes, month) "
                    "VALUES ('Raccogliere gli oggetti fuori posto', 'Tutta la casa', 'giornaliera', 5, NULL)")
        con.execute("UPDATE chores SET minutes = 5 WHERE name = 'Arieggiare le stanze'")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        nomi = {r[0] for r in con.execute("SELECT name FROM chores")}
        assert "Raccogliere gli oggetti fuori posto" not in nomi, "la voce unita va tolta"
        minuti = dict(con.execute("SELECT name, minutes FROM chores"))
        assert minuti["Arieggiare le stanze"] == 2


def test_pulizie_rimozione_non_perde_i_completamenti(tmp_path):
    """Togliere una voce non deve cancellare il lavoro registrato su di essa.

    La voce unita aveva dei completamenti spuntati dall'utente: spostarli sulla
    sostituta li conserva, cancellarli sarebbe una perdita silenziosa.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("INSERT INTO chores (name, area, frequency, minutes, month) "
                    "VALUES ('Raccogliere gli oggetti fuori posto', 'Tutta la casa', 'giornaliera', 5, NULL)")
        vecchio_id = con.execute(
            "SELECT id FROM chores WHERE name = 'Raccogliere gli oggetti fuori posto'").fetchone()[0]
        con.execute("INSERT INTO chore_log (chore_id, date, minutes) VALUES (?, '2026-09-20', 6)",
                    (vecchio_id,))
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        righe = con.execute(
            """SELECT c.name, l.date FROM chore_log l JOIN chores c ON c.id = l.chore_id""").fetchall()
        assert ("Riordino generale", "2026-09-20") in righe, "il completamento segue la sostituta"


def test_pulizie_minuti_ritoccati_a_mano_non_si_perdono(tmp_path):
    """La migrazione tocca solo il valore di partenza, non la stima dell'utente.

    I minuti sono una stima che l'utente puo' correggere: riallinearla a forza
    cancellerebbe la sua correzione a ogni richiesta.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("UPDATE chores SET minutes = 7 WHERE name = 'Arieggiare le stanze'")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        minuti = dict(con.execute("SELECT name, minutes FROM chores"))
        assert minuti["Arieggiare le stanze"] == 7, "la stima dell'utente resta"


def test_schema_applicato_a_una_casa_gia_esistente(tmp_path):
    """Una casa creata prima delle foto deve ricevere la tabella.

    E' il caso che conta per chi aggiorna: il database ha gia' i dati, e senza
    questo passaggio l'app risponderebbe "no such table" proprio a chi ha piu'
    da perdere.
    """
    percorso = str(tmp_path / "vecchia.db")
    # una casa di una versione precedente: schema di allora, senza le foto, e
    # con dentro un dato che deve sopravvivere all'aggiornamento
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("INSERT INTO storage (name, quantity) VALUES ('Sapone', 3)")
        con.execute("DROP TABLE storage_photos")
        con.commit()
    assert not esiste_tabella(percorso, "storage_photos")

    app_module.init_db(percorso)

    assert esiste_tabella(percorso, "storage_photos")
    with closing(sqlite3.connect(percorso)) as con:
        assert con.execute("SELECT name FROM storage").fetchone()[0] == "Sapone"


def esiste_tabella(percorso, nome):
    with closing(sqlite3.connect(percorso)) as con:
        return con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)).fetchone() is not None


# ------------------------------------------------------------ case
# La separazione fra case: il comportamento che deve reggere e' che i dati di
# una casa non si vedano mai dall'altra, ne' in lettura ne' in scrittura.


def test_senza_accesso_le_api_rispondono_401(anon):
    """Nessuna casa collegata: i dati non si toccano e non si leggono."""
    for percorso in ["/api/recipes", "/api/pantry", "/api/shopping", "/api/profile",
                     "/api/meta", "/api/storage", "/api/projects", "/api/faq"]:
        r = anon.get(percorso)
        assert r.status_code == 401, f"{percorso} accessibile senza accesso"
        assert r.get_json().get("auth") is False


def test_la_pagina_e_i_file_statici_restano_pubblici(anon):
    """La pagina deve caricarsi per poter mostrare l'accesso."""
    assert anon.get("/").status_code == 200
    assert anon.get("/static/app.js").status_code == 200


def test_sessione_anonima_dice_non_autenticato(anon):
    assert anon.get("/api/session").get_json() == {"authenticated": False}


def test_password_sbagliata_non_entra(anon):
    r = anon.post("/api/login", json={"nome": "Casa Test", "password": "sbagliata"})
    assert r.status_code == 401
    assert anon.get("/api/session").get_json()["authenticated"] is False


def test_casa_inesistente_non_entra(anon):
    r = anon.post("/api/login", json={"nome": "Non Esiste", "password": "x"})
    assert r.status_code == 401
    # stesso messaggio della password sbagliata: non rivela quali case esistono
    assert r.get_json()["error"] == "Nome o password non corretti"


def test_accesso_riuscito_e_session(anon):
    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 200
    info = anon.get("/api/session").get_json()
    assert info["authenticated"] is True
    assert info["nome"] == "Casa Test"


def test_uscire_toglie_laccesso(anon):
    anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert anon.get("/api/recipes").status_code == 200
    anon.post("/api/logout")
    assert anon.get("/api/recipes").status_code == 401


def test_ogni_casa_vede_solo_le_sue_ricette(anon):
    """Il cuore della separazione: due case, ricette diverse, nessuna interferenza."""
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    anon.post("/api/recipes", json={"name": "Piatto di A", "servings": 2, "items": []})
    nomi_a = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di A" in nomi_a

    # casa B, creata dopo: non deve vedere nulla di A
    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa B", "password": "bbbb"})
    nomi_b = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di A" not in nomi_b, "una casa vede le ricette dell'altra"
    anon.post("/api/recipes", json={"name": "Piatto di B", "servings": 2, "items": []})

    # tornando ad A, la ricetta di B non deve comparire
    anon.post("/api/logout")
    anon.post("/api/login", json={"nome": "Casa A", "password": "aaaa"})
    nomi_a2 = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di B" not in nomi_a2, "una casa vede le ricette dell'altra"
    assert "Piatto di A" in nomi_a2


def test_case_separate_per_dispensa_e_spesa(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    anon.post("/api/pantry", json={"name": "Farina", "quantity": 5, "unit": "kg"})
    assert any(v["name"] == "Farina" for v in anon.get("/api/pantry").get_json())

    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa B", "password": "bbbb"})
    assert not any(v["name"] == "Farina" for v in anon.get("/api/pantry").get_json())


def test_una_casa_col_database_mancante_nasce_col_ricettario(anon, casa_test):
    """Una casa registrata ma rimasta senza file non deve nascere vuota.

    Il caso reale: il file del database non c'e' (ripristino parziale, file
    spostato, copia rimessa nel posto sbagliato). La prima richiesta lo ricrea,
    e ricrearlo vuoto lascia l'utente senza nessuna ricetta da scegliere nel
    piano pasti: proprio il punto da cui scriveva per chiedere aiuto.
    """
    houses.registra("casa-spoglia", "Casa Spoglia", "prova1234")
    percorso = houses.db_path("casa-spoglia")
    assert not os.path.exists(percorso)

    anon.post("/api/login", json={"nome": "Casa Spoglia", "password": "prova1234"})
    ricette = anon.get("/api/recipes").get_json()
    assert len(ricette) > 10, "una casa ricreata da zero deve avere il ricettario"


def test_una_casa_esistente_senza_ricette_non_viene_riseminata(anon):
    """Se l'utente cancella tutte le ricette, non devono tornare da sole.

    La tentazione e' di seminare ogni volta che le ricette sono zero, ma zero e'
    uno stato legittimo: chi ha svuotato il ricettario non deve ritrovarselo
    pieno al riavvio successivo.
    """
    anon.post("/api/houses", json={"nome": "Casa Vuota", "password": "aaaa"})
    for r in anon.get("/api/recipes").get_json():
        anon.delete(f"/api/recipes/{r['id']}")
    assert anon.get("/api/recipes").get_json() == []

    # una richiesta successiva non deve ripopolare il database
    assert anon.get("/api/recipes").get_json() == []


def test_avvio_non_crea_un_database_storico_vuoto(tmp_path, monkeypatch):
    """L'avvio non deve lasciare un `cucina.db` fantasma da adottare.

    Era una trappola in due tempi: il primo avvio creava un `cucina.db` vuoto,
    e al secondo `migra_case()` lo scambiava per il ricettario di mesi e
    registrava una casa "Casa" senza niente dentro.
    """
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.delenv("CUCINA_DB", raising=False)
    importlib.reload(houses)
    importlib.reload(app_module)
    try:
        # macchina nuova: nessun registro, nessun cucina.db
        app_module.migra_case()
        app_module.prepara_database_storico()
        assert not os.path.exists(app_module.DB_PATH), \
            "l'avvio ha creato un database storico dal nulla"
        assert houses.elenco() == []

        # il secondo avvio non deve trovare nulla da adottare
        app_module.migra_case()
        assert houses.elenco() == [], "un guscio vuoto e' stato adottato come casa"
    finally:
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)
        importlib.reload(app_module)


def test_una_casa_storica_senza_ricette_ma_con_dati_viene_adottata(tmp_path, monkeypatch):
    """Chi usa l'app solo per le FAQ non deve perdere l'accesso ai suoi dati.

    Scartare il database perche' non ha ricette renderebbe irraggiungibile il
    lavoro di chi teneva solo la password del Wi-Fi: "nessun dato" e' un
    criterio piu' largo di "nessuna ricetta".
    """
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.delenv("CUCINA_DB", raising=False)
    importlib.reload(houses)
    importlib.reload(app_module)
    try:
        app_module.init_db(str(tmp_path / "cucina.db"))
        with closing(sqlite3.connect(str(tmp_path / "cucina.db"))) as con:
            con.execute("INSERT INTO faq (category, question, answer) "
                        "VALUES ('wifi', 'Fastweb', 'segreta')")
            con.commit()

        app_module.migra_case()

        assert houses.elenco(), "una casa con dati dentro e' stata scartata"
        assert houses.elenco()[0]["slug"] == houses.STORICA
    finally:
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)
        importlib.reload(app_module)


def test_una_casa_nuova_nasce_col_ricettario(anon):
    """Le case nuove non partono vuote: hanno il ricettario italiano di partenza."""
    anon.post("/api/houses", json={"nome": "Casa Nuova", "password": "cccc"})
    ricette = anon.get("/api/recipes").get_json()
    assert len(ricette) > 10, "una casa nuova deve avere il ricettario di partenza"
    nomi = {r["name"] for r in ricette}
    assert "Pasta al pomodoro" in nomi


def test_la_casa_nuova_ha_gli_ingredienti_del_ricettario(anon):
    """Il ricettario seminato deve avere ingredienti veri e foto, non gusci vuoti."""
    anon.post("/api/houses", json={"nome": "Casa Nuova", "password": "cccc"})
    ricette = anon.get("/api/recipes").get_json()
    con_foto = [r for r in ricette if r.get("image")]
    assert con_foto, "le ricette seminate devono avere le foto"

    # l'elenco non porta gli ingredienti: il dettaglio si' (gli ingredienti sono
    # nella tabella `recipe_items`, che l'elenco non interroga)
    pomodoro = next(r for r in ricette if r["name"] == "Pasta al pomodoro")
    dettaglio = anon.get(f"/api/recipes/{pomodoro['id']}").get_json()
    assert len(dettaglio["items"]) >= 3, "la ricetta seminata deve avere ingredienti"
    assert all(v["name"].strip() for v in dettaglio["items"])


def test_non_si_possono_creare_due_case_con_lo_stesso_nome(anon):
    anon.post("/api/houses", json={"nome": "Casa Unica", "password": "aaaa"})
    anon.post("/api/logout")
    r = anon.post("/api/houses", json={"nome": "casa unica", "password": "bbbb"})
    assert r.status_code == 400
    assert "nome" in r.get_json()["error"].lower()


def test_creare_una_casa_richiede_una_password(anon):
    r = anon.post("/api/houses", json={"nome": "Senza Password", "password": ""})
    assert r.status_code == 400


def test_lenco_delle_case_non_espone_le_password(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    elenco = anon.get("/api/houses").get_json()
    assert elenco and all(set(v) == {"slug", "nome"} for v in elenco)


def test_cambiare_password(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "vecchia"})
    # sbagliata: non deve cambiare nulla
    assert anon.put("/api/houses/password",
                    json={"attuale": "sbagliata", "nuova": "nuovissima"}).status_code == 400
    assert anon.put("/api/houses/password",
                    json={"attuale": "vecchia", "nuova": "nuovissima"}).status_code == 200
    anon.post("/api/logout")
    assert anon.post("/api/login", json={"nome": "Casa A", "password": "vecchia"}).status_code == 401
    assert anon.post("/api/login", json={"nome": "Casa A", "password": "nuovissima"}).status_code == 200


def test_la_password_non_si_salva_in_chiaro(anon):
    """Se il registro finisce in un backup, la password non deve essere leggibile."""
    anon.post("/api/houses", json={"nome": "Casa A", "password": "segretissima"})
    with sqlite3.connect(REGISTRO) as c:
        salvata = c.execute("SELECT password FROM houses WHERE nome = 'Casa A'").fetchone()[0]
    assert "segretissima" not in salvata
    assert salvata.startswith("pbkdf2_sha256$")


def test_la_password_e_verificata_correttamente():
    impronta = houses.hash_password("prova")
    assert houses.verifica_password("prova", impronta)
    assert not houses.verifica_password("sbagliata", impronta)
    assert not houses.verifica_password("prova", "formato-non-valido")


def test_lo_slug_non_ammette_percorsi():
    """Niente traversal: dal nome si ricava uno slug prevedibile."""
    assert houses.slugify("Casa di Anna!") == "casa-di-anna"
    assert houses.slugify("../../etc/passwd") == "etc-passwd"
    with pytest.raises(ValueError):
        houses.db_path("../../etc/passwd")


def test_reimposta_password_entra_senza_quella_vecchia(client):
    """Chi perde la password deve poter rientrare: e' il caso che conta."""
    vecchia = "PasswordPersa123"
    assert not houses.autentica(CASA_TEST, vecchia)      # quella del test e' un'altra
    with closing(sqlite3.connect(REGISTRO)) as db:
        db.execute("UPDATE houses SET password = ? WHERE slug = ?",
                   (houses.hash_password(vecchia), CASA_TEST))
        db.commit()
    assert houses.autentica(CASA_TEST, vecchia)

    houses.reimposta_password(CASA_TEST, "NuovaPassword456")
    assert houses.autentica(CASA_TEST, "NuovaPassword456")
    assert not houses.autentica(CASA_TEST, vecchia)      # la vecchia smette di valere

    # e dalla porta principale funziona: e' quello che serve davvero
    r = client.post("/api/login", json={"nome": "Casa Test", "password": "NuovaPassword456"})
    assert r.status_code == 200


def test_reimposta_password_non_cancella_i_dati(client):
    """Il motivo per cui si usa: rientrare e ritrovare tutto."""
    client.post("/api/recipes", json={"name": "Carbonara di prova"})
    prima = len(client.get("/api/recipes").get_json())

    houses.reimposta_password(CASA_TEST, "PasswordNuova1")

    client.post("/api/login", json={"nome": "Casa Test", "password": "PasswordNuova1"})
    dopo = len(client.get("/api/recipes").get_json())
    assert dopo == prima and prima >= 1


def test_reimposta_password_rifiuta_quella_corta():
    with pytest.raises(ValueError):
        houses.reimposta_password(CASA_TEST, "abc")
    with pytest.raises(ValueError):
        houses.reimposta_password(CASA_TEST, "")


def test_reimposta_password_non_crea_case_inesistenti():
    with pytest.raises(ValueError):
        houses.reimposta_password("casa-che-non-esiste", "PasswordLunga1")
    assert not houses.esiste("casa-che-non-esiste")


def test_lo_strumento_di_ripristino_funziona_da_capo_a_capo(client, monkeypatch, capsys):
    """`ripristina_password.py` così come lo esegue l'utente, con `windows\\password.bat`."""
    import ripristina_password
    risposte = iter(["PasswordSmemorata2", "PasswordSmemorata2"])
    monkeypatch.setattr(ripristina_password, "chiedi_nascosta", lambda *a, **k: next(risposte))
    assert ripristina_password.main() == 0
    assert "Fatto" in capsys.readouterr().out
    assert houses.autentica(CASA_TEST, "PasswordSmemorata2")


def test_lo_strumento_non_cambia_niente_se_le_password_non_coincidono(monkeypatch, capsys):
    import ripristina_password
    risposte = iter(["PrimaPassword11", "SecondaPassword22"])
    monkeypatch.setattr(ripristina_password, "chiedi_nascosta", lambda *a, **k: next(risposte))
    assert ripristina_password.main() == 1
    assert "non coincidono" in capsys.readouterr().out
    assert not houses.autentica(CASA_TEST, "PrimaPassword11")


def test_la_chiave_si_legge_dal_file_segreto(tmp_path, monkeypatch):
    """Su Windows `segreto.bat`, sul server `segreto.sh`: senza, un riavvio fa
    tornare la voce meccanica e non si capisce perche'."""
    (tmp_path / "segreto.bat").write_text(
        '@echo off\nREM nota\nset "AZURE_SPEECH_KEY=ChiaveDaFile1"\n'
        'set "AZURE_SPEECH_REGION=italynorth"\n')
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveDaFile1"
    assert voce_cloud.regione() == "italynorth"
    assert voce_cloud.configurato()


def test_la_chiave_si_legge_anche_dal_file_sh(tmp_path, monkeypatch):
    (tmp_path / "segreto.sh").write_text(
        "# nota\nexport AZURE_SPEECH_KEY='ChiaveDaFile2'\nexport AZURE_SPEECH_REGION=italynorth\n")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveDaFile2"


def test_la_regione_diventa_minuscola(tmp_path, monkeypatch):
    """Scritta con maiuscole non funziona, e l'errore non lo dice."""
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_REGION=ITALYNORTH\n")
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.regione() == "italynorth"


def test_l_ambiente_vince_sul_file(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda: il file e' un ripiego, non un vincolo."""
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_KEY=DalFile\n")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "DallAmbiente")
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "DallAmbiente"


def test_senza_file_ne_chiave_configurato_e_falso(tmp_path, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert not voce_cloud.configurato()


# ------------------------------------------- il segreto in un file di testo
# Il file di testo semplice esiste per togliere di mezzo la sintassi: senza
# `export` e senza virgolette, l'errore che fa dire "la chiave c'e' ma la voce
# resta meccanica" non si puo' piu' commettere. Questi test coprono le forme
# che si scrivono davvero, non la presenza di una stringa nel codice.

def _con_segreto(tmp_path, monkeypatch, testo, nome_file="segreto.txt"):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)
    (tmp_path / nome_file).write_text(testo)


def test_il_segreto_si_scrive_in_un_file_di_testo(tmp_path, monkeypatch):
    """`chiave: valore` e `area: valore`: due righe, niente sintassi."""
    _con_segreto(tmp_path, monkeypatch, "chiave: ChiaveDiProva123456\narea: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"
    assert voce_cloud.configurato()


def test_il_segreto_accetta_le_etichette_che_vengono_naturali(tmp_path, monkeypatch):
    """Chi scrive il file non deve sapere i nomi delle variabili."""
    _con_segreto(tmp_path, monkeypatch, "Chiave: ChiaveDiProva123456\nRegione: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"


def test_il_segreto_funziona_anche_con_i_due_valori_nudi(tmp_path, monkeypatch):
    """Il file piu' semplice possibile: due righe e basta, prima la chiave.
    L'area e' una parola minuscola, la chiave no: la forma dice cos'e' ciascuna."""
    _con_segreto(tmp_path, monkeypatch, "AbCdEf1234567890xyz\nitalynorth\n")

    assert voce_cloud.chiave() == "AbCdEf1234567890xyz"
    assert voce_cloud.regione() == "italynorth"


def test_il_segreto_nudo_riconosce_l_area_dopo_la_chiave_e_viceversa(tmp_path, monkeypatch):
    """L'ordine non deve contare: chi scrive il file puo' mettere prima l'area."""
    _con_segreto(tmp_path, monkeypatch, "italynorth\nAbCdEf1234567890xyz\n")

    assert voce_cloud.chiave() == "AbCdEf1234567890xyz"
    assert voce_cloud.regione() == "italynorth"


def test_una_riga_di_testo_libero_non_diventa_la_chiave(tmp_path, monkeypatch):
    """Il file puo' contenere una spiegazione scritta a mano: le righe con spazi
    non sono ne' chiave ne' area, e non devono finire nell'ambiente."""
    _con_segreto(tmp_path, monkeypatch,
                 "Questa e' la chiave della voce, non copiarla in giro\n"
                 "chiave: ChiaveDiProva123456\narea: italynorth\n")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"
    assert voce_cloud.regione() == "italynorth"


def test_il_file_senza_estensione_funziona_come_il_txt(tmp_path, monkeypatch):
    """Si possa chiamare `segreto.txt` o solo `segreto`: e' lo stesso."""
    _con_segreto(tmp_path, monkeypatch,
                 "chiave: ChiaveDiProva123456\narea: italynorth\n", nome_file="segreto")

    assert voce_cloud.chiave() == "ChiaveDiProva123456"


def test_l_ambiente_vince_anche_sul_file_di_testo(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda, come per `segreto.sh`."""
    _con_segreto(tmp_path, monkeypatch, "chiave: DalFile\narea: italynorth\n")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "DallAmbiente")

    assert voce_cloud.chiave() == "DallAmbiente"


def test_il_file_di_esempio_non_contiene_una_chiave_vera():
    """Il modello sta su GitHub: se ci finisse una chiave vera sarebbe pubblica.
    Deve contenere solo il segnaposto, e il file vero deve restare escluso."""
    modello = open("segreto.esempio.txt", encoding="utf-8").read()
    assert "incolla-qui-la-chiave" in modello

    import subprocess
    fuori = subprocess.run(["git", "check-ignore", "-q", "segreto.txt"],
                           cwd=voce_cloud.BASE_DIR, capture_output=True).returncode == 0
    dentro = subprocess.run(["git", "check-ignore", "-q", "segreto.esempio.txt"],
                            cwd=voce_cloud.BASE_DIR, capture_output=True).returncode == 0
    assert fuori, "segreto.txt (la chiave vera) deve essere escluso da git"
    assert not dentro, "il modello deve essere versionato"


def test_il_wav_per_il_server_ha_intestazione_e_campioni_giusti(client):
    """Il servizio di ascolto legge **solo** WAV PCM 16 kHz mono: un webm del
    browser verrebbe rifiutato con un 400 che sembra un guasto.

    Si esegue la funzione vera con node e si legge l'intestazione byte per byte:
    un test sulle stringhe non accorgerebbe di un byte scritto male."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function wavDaCampioni"):js.index("\n}\n", js.index("function wavDaCampioni")) + 3]
    prova = blocco + """
// un'onda semplice: positiva e negativa a campioni alterni
const campioni = new Float32Array(320);
for (let i = 0; i < campioni.length; i++) campioni[i] = (i % 2 === 0) ? 0.25 : -0.25;
const blob = wavDaCampioni(campioni, 16000);
blob.arrayBuffer().then((buf) => {
  const v = new DataView(buf);
  const str = (p, n) => { let s = ''; for (let i = 0; i < n; i++) s += String.fromCharCode(v.getUint8(p + i)); return s; };
  console.log(JSON.stringify({
    riff: str(0, 4), wave: str(8, 4), fmt: str(12, 4), data: str(36, 4),
    formato: v.getUint16(20, true), canali: v.getUint16(22, true),
    frequenza: v.getUint32(24, true), bit: v.getUint16(34, true),
    byteDati: v.getUint32(40, true), totale: buf.byteLength,
    primoCampione: v.getInt16(44, true), secondoCampione: v.getInt16(46, true),
  }));
});
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["riff"] == "RIFF" and d["wave"] == "WAVE"
    assert d["fmt"] == "fmt " and d["data"] == "data"
    assert d["formato"] == 1          # PCM, non compresso
    assert d["canali"] == 1           # mono
    assert d["frequenza"] == 16000    # quello che chiede il servizio
    assert d["bit"] == 16
    assert d["byteDati"] == 320 * 2   # due byte per campione
    assert d["totale"] == 44 + 320 * 2
    # 0,25 e non 0,5: il mezzo esatto si arrotonda in modo diverso fra JS e
    # Python, e qui non e' quello che si vuole provare
    assert d["primoCampione"] == round(0.25 * 32767)
    assert d["secondoCampione"] == round(-0.25 * 32767)


def test_il_campione_fuori_scala_non_avvolge_di_segno(client):
    """Un valore oltre 1 farebbe avvolgere il numero: 1,5 non è "un po' più
    forte", è un valore negativo. Si taglia al limite."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function wavDaCampioni"):js.index("\n}\n", js.index("function wavDaCampioni")) + 3]
    prova = blocco + """
const campioni = new Float32Array([1.8, -1.9, 0]);
wavDaCampioni(campioni, 16000).arrayBuffer().then((buf) => {
  const v = new DataView(buf);
  console.log([v.getInt16(44, true), v.getInt16(46, true), v.getInt16(48, true)].join(','));
});
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert esito.stdout.strip() == "32767,-32767,0"


def test_i_campioni_del_microfono_arrivano_a_16_khz(client):
    """Il microfono non consegna sempre 16 kHz: l'audio breve ne accetta uno solo,
    quindi si riscrive. Sbagliare qui manda audio che il servizio non legge."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("const ASCOLTO_CAMPIONI"):js.index("\n}\n", js.index("function aSediciKhz")) + 3]
    prova = blocco + """
// 48 kHz -> 16 kHz: un campione ogni tre
const alti = new Float32Array(48000);
for (let i = 0; i < alti.length; i++) alti[i] = Math.sin(i / 100);
const fuori = aSediciKhz(alti, 48000);
// già a 16 kHz: non si tocca niente
const stessi = new Float32Array([0.1, 0.2, 0.3]);
console.log(JSON.stringify({
  lunghezza: fuori.length, attesa: 16000,
  intatti: aSediciKhz(stessi, 16000) === stessi,
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["lunghezza"] == d["attesa"]
    assert d["intatti"] is True


def test_il_browser_bloccato_ma_senza_chiave_suggerisce_la_chiave(client):
    """Il caso che l'utente ha davanti: Chrome risponde "network" e il server non
    ha la chiave Azure, quindi non puo' trascrivere al posto del browser.

    Il messaggio non puo' limitarsi a "scrivi qui sotto": la chiave Azure e' la
    soluzione vera al blocco, e va detta proprio allora. Si esegue la funzione
    con node, cosi' il test verifica **quale** messaggio esce, non che una frase
    sia scritta nel file.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function messaggioMicrofono"):
                 js.index("\n}\n", js.index("function messaggioMicrofono")) + 3]
    prova = blocco + """
console.log(JSON.stringify({
  senzaChiave: messaggioMicrofono('network', false),
  conChiave: messaggioMicrofono('network', true),
  negato: messaggioMicrofono('not-allowed', false),
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    # senza chiave: si dice che la chiave sposta la trascrizione sul server
    assert "chiave" in d["senzaChiave"].lower()
    assert "server" in d["senzaChiave"].lower()
    # con la chiave gia' attiva quel consiglio non ha senso: non va ripetuto
    assert "chiave" not in d["conChiave"].lower()
    # gli altri errori non si toccano
    assert "autorizzato" in d["negato"].lower()
    # e la funzione dev'essere quella che l'errore del microfono usa davvero:
    # verificata da sola non servirebbe a niente se restasse scollegata
    assert "voceStato(messaggioMicrofono(e.error, voceCloud.ascolto), 'err');" in js


def _decisione_js(client, casi):
    """Esegue la decisione dell'ascolto continuo sul codice vero.

    `decisioneContinuo` e' pura apposta: si prova senza microfono, senza DOM e
    senza attese. E' la regola che decide se un comando parte, e va provata come
    si comporterebbe davvero.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const VERBI_COMANDO")
    fine = js.index("\n}\n", js.index("function decisioneContinuo")) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def test_dopo_dimmi_il_comando_si_dice_senza_ripetere_la_sveglia(client):
    """Il dialogo naturale, ed era rotto: si chiama "maggiordomo", lui risponde
    "Dimmi.", e la frase successiva è il comando — senza ripetere la sveglia.

    Prima il ciclo pretendeva di nuovo la sveglia anche lì: il comando veniva
    ignorato **in silenzio**, che è il peggior modo di fallire. Qui si verifica
    che dentro la finestra il comando parta.
    """
    d = _decisione_js(client, """{
      // la sveglia da sola apre la finestra, non esegue
      soloSveglia: decisioneContinuo('Maggiordomo.', true, '', false),
      // il comando detto subito dopo, senza sveglia: deve partire
      dopoDimmi: decisioneContinuo('metti il latte nella spesa', false, '', true),
      // e deve partire anche una domanda, che è un comando come gli altri
      domanda: decisioneContinuo("che cosa c'è in dispensa", false, '', true),
    }""")
    assert d["soloSveglia"]["azione"] == "chiedi"
    assert d["dopoDimmi"] == {"azione": "esegui", "comando": "metti il latte nella spesa"}
    assert d["domanda"]["azione"] == "esegui"


def test_fuori_dalla_finestra_la_sveglia_serve_di_nuovo(client):
    """La finestra è a tempo, non per sempre.

    Senza questo limite, una volta chiamato l'assistente ogni frase di casa
    diventerebbe un ordine: "il maggiordomo prepara la cena", detto a tavola,
    scriverebbe in dispensa.
    """
    d = _decisione_js(client, """{
      fuoriFinestra: decisioneContinuo('metti il latte nella spesa', false, '', false),
      chiacchiera: decisioneContinuo('il maggiordomo prepara la cena', false, '', true),
      nonComando: decisioneContinuo('oggi c\\u00e8 il sole', false, '', true),
    }""")
    assert d["fuoriFinestra"]["azione"] == "ignora"
    # anche dentro la finestra, una frase che non è un ordine resta fuori
    assert d["chiacchiera"]["azione"] == "ignora"
    assert d["nonComando"]["azione"] == "ignora"


def test_un_comando_senza_sveglia_lo_dice_invece_di_tacere(client):
    """Il caso del telefono: la frase viene trascritta, l'utente la legge, e poi
    non succede **nulla**. Succede quando il comando non contiene la sveglia e la
    finestra non e' aperta: la decisione e' `ignora`, e l'app taceva del tutto.

    Tacere nel suono va bene (l'ascolto continuo non risponde al discorso di
    casa), ma tacere anche sullo **schermo** lascia chi ha parlato senza sapere
    se e' stato sentito. Un ordine senza la sveglia deve dire che manca la
    sveglia; una chiacchiera di casa resta muta come prima."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "Non ho eseguito" in js and "Hey GG" in js
    # la frase sentita si mostra comunque: dice cosa ha capito
    assert "$('#voice-heard').textContent = frase || '…';" in js
    # e l'avviso si da' solo a una frase che sembra un comando
    blocco = js[js.index("const frase = (testo || '').trim();"):]
    blocco = blocco[:blocco.index("riparti();") + len("riparti();")]
    assert "sembraComando(frase)" in blocco



def test_una_chiacchiera_dopo_dimmi_non_diventa_un_ordine(client):
    """Il rischio della finestra: una volta chiamato l'assistente, il discorso di
    casa che segue non deve trasformarsi in un ordine.

    "il maggiordomo prepara la cena", detto a tavola dopo un "Dimmi.", scriverebbe
    in dispensa. Il criterio è lo stesso della sveglia: la parola che apre la
    frase decide."""
    d = _decisione_js(client, """{
      chiacchiera: decisioneContinuo('il maggiordomo prepara la cena', false, '', true),
      discorso: decisioneContinuo('oggi viene mia madre a pranzo', false, '', true),
      // invece una frase che apre con un numero è una dose, e vale
      dose: decisioneContinuo('due chili di farina', false, '', true),
    }""")
    assert d["chiacchiera"]["azione"] == "ignora"
    assert d["discorso"]["azione"] == "ignora"
    assert d["dose"]["azione"] == "esegui"


def test_la_sveglia_con_il_comando_esegue_senza_finestra(client):
    """Il caso più comune: "maggiordomo, metti il latte". Non serve nessuna
    finestra, il comando è nella frase stessa."""
    d = _decisione_js(client, """{
      insieme: decisioneContinuo('Maggiordomo, metti il latte nella spesa', true,
                                 'metti il latte nella spesa', false),
    }""")
    assert d["insieme"] == {"azione": "esegui", "comando": "metti il latte nella spesa"}


def test_il_microfono_prova_prima_il_server(client):
    """La strada giusta è il server: è quello che esce dalla rete. Il browser
    resta il ripiego, per quando la chiave non c'è."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/voce/ascolta" in js
    assert "ascoltaSulServer" in js and "ascoltaDalBrowser" in js
    # il dispatcher sceglie il server quando è disponibile
    assert "if (voceCloud.ascolto && ascoltaSulServer(esitoAscolto)) return;" in js
    # e il 503 non è un errore da mostrare: si ripiega sul browser
    assert "if (d && d.ripiega) { ascoltaDalBrowser(); return; }" in js


def test_la_registrazione_si_ferma_da_sola_fine_frase(client):
    """Senza la fine automatica il microfono resterebbe aperto finché non lo si
    chiude a mano, e nessuno lo chiude: la frase non partirebbe mai."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "fineRegistrazione" in js
    assert "ASCOLTO_MAX_MS" in js
    d = _fine_registrazione_js(client, """{
      // si sta parlando, l'ultimo suono e' recente: non chiudere
      parlando: fineRegistrazione({inizio: 0, ultimoSuono: 1000, parlatoDa: true, adesso: 1200}),
      // si e' smesso di parlare da un pezzo: chiudere
      finePausa: fineRegistrazione({inizio: 0, ultimoSuono: 1000, parlatoDa: true, adesso: 3000}),
      // nessuno parla ancora: chiudere dopo l'attesa
      silenzioLungo: fineRegistrazione({inizio: 0, ultimoSuono: 0, parlatoDa: false, adesso: 7000}),
      // e non chiudere troppo presto
      silenzioBreve: fineRegistrazione({inizio: 0, ultimoSuono: 0, parlatoDa: false, adesso: 3000}),
      // il tetto chiude qualunque cosa succeda
      tetto: fineRegistrazione({inizio: 0, ultimoSuono: 999999, parlatoDa: true, adesso: 16000}),
    }""")
    assert d["parlando"] is False
    assert d["finePausa"] is True
    assert d["silenzioLungo"] is True
    assert d["silenzioBreve"] is False
    assert d["tetto"] is True


def test_la_registrazione_non_resta_appesa_senza_campioni(client):
    """Il guasto del telefono, riprodotto: la spia dice "in ascolto" ma non passa
    mai a "Trascrivo…". La causa era che su iPhone `onaudioprocess` non scatta, e
    la chiusura della frase dipendeva **solo** da li': la registrazione restava
    appesa per sempre. Qui si esegue `ascoltaSulServer` **vera** con un
    `AudioContext` finto il cui callback dei campioni non viene mai chiamato, e
    si verifica che l'esito arrivi comunque, dal timer di sicurezza."""
    esito = _ascolta_senza_campioni_js(client)
    assert esito["gestoreAssegnato"] is True, "il registratore deve essersi avviato"
    assert esito["campioniChiamati"] is False, "il caso da riprodurre: nessun campione"
    assert esito["esitoRicevuto"] is True, (
        "senza campioni la registrazione deve chiudersi lo stesso")
    assert esito["ms"] < 2000, f"ci ha messo troppo: {esito['ms']} ms"
    # e l'esito lo dice: tacere sembrerebbe che l'app sia sorda
    assert esito["muto"] is True, "l'app deve accorgersi del microfono muto"


def test_il_microfono_muto_non_tace_per_sempre(client):
    """Se il microfono non manda **nessun** campione, l'app deve dirlo: tacere
    con la spia "in ascolto" e' il modo peggiore di fallire, perche' sembra che
    l'app sia sorda. Si riproduce il caso con `ascoltaSulServer` vera e un
    microfono finto muto."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "muto" in js
    assert "Il microfono non manda audio" in js


def test_il_ciclo_ha_un_battito_e_un_sorvegliante(client):
    """Un giro perso (microfono che non consegna l'audio) lasciava l'ascolto
    acceso ma sordo, senza nessun errore. Il battito dice che il ciclo e' vivo,
    e il sorvegliante lo fa ripartire quando non batte piu'."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "battito" in js
    assert "function sorvegliaIlCiclo(" in js
    assert "BATTITO_MASSIMO_MS" in js
    d = _sorvegliante_js(client, """{
      // appena acceso: il ciclo ha battuto, non intervenire
      fresco: cicloDaRiavviare(1000, 5000),
      // fermo da troppo, e non sta parlando: riavviare
      fermo: cicloDaRiavviare(1, 40000),
      // sta parlando (sospeso): attesa voluta, non e' un guasto
      sospeso: cicloDaRiavviare(1, 40000, true),
      // aspetta un tocco del browser: c'e' gia' il suo avviso
      gesto: cicloDaRiavviare(1, 40000, false, true),
    }""")
    assert d["fresco"] is False
    assert d["fermo"] is True, "un ciclo morto va fatto ripartire"
    assert d["sospeso"] is False
    assert d["gesto"] is False


def _sorvegliante_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "cicloDaRiavviare")
    costanti = "const BATTITO_MASSIMO_MS = 25000;\n"
    return _esegui_node(costanti + blocco
                        + "\nconsole.log(JSON.stringify(" + casi + "));")



def _ascolta_senza_campioni_js(client):
    """Esegue il registratore vero con un microfono finto muto e misura se e
    quando arriva l'esito. Le costanti sono piccole per non far durare il test
    quanto una frase vera."""
    js = client.get("/static/app.js").get_data(as_text=True)
    pezzi = [_estrai_funzione_js(js, n) for n in ("ampiezza", "fineRegistrazione",
                                                  "ascoltaSulServer")]
    preludio = """
const ASCOLTO_BLOCCO = 4096;
const ASCOLTO_CAMPIONI = 16000;
const ASCOLTO_FINE_MS = 1600;
const ASCOLTO_ATTESA_MS = 200;
const ASCOLTO_MAX_MS = 400;
const ASCOLTO_SILENZIO = 0.012;
let campioniChiamati = false;
let gestoreCampioni = null;
class AudioContextFinto {
  constructor() { this.state = 'running'; this.sampleRate = 16000; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() {
    return { connect() {}, disconnect() {},
             // il gestore viene **assegnato** dal codice vero, ma in questa
             // simulazione non viene mai invocato: e' il caso iPhone
             set onaudioprocess(f) { gestoreCampioni = f; } };
  }
  close() {}
  resume() { return Promise.resolve(); }
}
global.window = { AudioContext: AudioContextFinto };
// `navigator` in Node e' un oggetto nativo non assegnabile: va ridefinito
Object.defineProperty(globalThis, "navigator", {
  value: { mediaDevices: {
    getUserMedia: async () => ({ getTracks: () => [{ stop() {} }] }),
  } },
  configurable: true,
});
function ampiezza() { return 0; }
function inviaAscolto() { return Promise.resolve({ testo: '' }); }
function $() { return { classList: { add() {}, remove() {} } }; }
function voceStato() {}
let voce = { registratore: null, attivo: false };
"""
    prova = (preludio + "\n".join(pezzi) + """
const t0 = Date.now();
ascoltaSulServer((d) => {
  console.log(JSON.stringify({ esitoRicevuto: true, gestoreAssegnato: !!gestoreCampioni,
                               campioniChiamati, muto: !!(d && d.muto),
                               ms: Date.now() - t0 }));
  process.exit(0);
});
setTimeout(() => {
  console.log(JSON.stringify({ esitoRicevuto: false, gestoreAssegnato: !!gestoreCampioni,
                               campioniChiamati, muto: null,
                               ms: Date.now() - t0 }));
  process.exit(0);
}, 3000);""")
    return _esegui_node(prova)


def _fine_registrazione_js(client, casi):
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "fineRegistrazione")
    costanti = ("const ASCOLTO_FINE_MS = 1600;\n"
                "const ASCOLTO_ATTESA_MS = 6000;\n"
                "const ASCOLTO_MAX_MS = 15000;\n")
    return _esegui_node(costanti + blocco
                        + "\nconsole.log(JSON.stringify(" + casi + "));")


def test_la_pagina_spiega_perche_la_voce_e_robotica(client):
    """Senza chiave la voce e' quella del sistema: il pannello del microfono, dove
    la voce si sente, deve dirlo e indicare come avere quella naturale. (La scheda
    "Voce" delle FAQ, che lo ripeteva, e' stata rimossa su richiesta.)"""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "mostraAvvisoRobotica" in js
    assert "voice-chiave-manca" in js
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave-manca"' in html
    assert "voce naturale" in html


def test_la_pagina_avvisa_se_il_microfono_non_puo_funzionare(client):
    """Da http:// su rete locale il riconoscimento vocale e' negato dal browser."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "isSecureContext" in js and "mostraAvvisoSicurezza" in js


def test_la_pagina_non_gestisce_la_chiave(client):
    """La chiave si configura **prima** di avviare l'app, non dall'utente in FAQ.

    Un campo chiave nella pagina significherebbe che l'app puo' scrivere il
    segreto: chi apre la pagina potrebbe cambiarlo, e la chiave finirebbe in una
    richiesta HTTP. Il posto giusto e' accanto al programma, fuori da git.
    """
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave"' not in html
    assert 'id="voice-chiave-salva"' not in html
    assert 'id="voice-chiave-dettagli"' not in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "salvaChiaveVoce" not in js
    assert "/api/voce/configura" not in js


def test_l_endpoint_che_salvava_la_chiave_non_esiste_piu(client):
    """Senza la rotta non c'e' modo di scrivere il segreto via HTTP: la chiave
    entra solo dal file o dall'ambiente, prima dell'avvio."""
    r = client.post("/api/voce/configura", json={"chiave": "x", "regione": "italynorth"})
    assert r.status_code in (404, 405), r.status_code


def test_il_pannello_del_microfono_dice_di_configurare_prima(client):
    """Senza la chiave la voce e' meccanica, e il pannello del microfono e' dove
    l'utente la sente: deve dire **dove** si mette, e non mandarlo in una pagina
    che non la chiede piu'."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="voice-chiave-manca"' in html
    inizio = html.index('id="voice-chiave-manca"')
    avviso = html[inizio:inizio + 400]
    assert "prima di avviare" in avviso
    assert "FAQ" not in avviso
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "voice-chiave-manca" in js


def test_gli_spazi_ai_bordi_della_password_non_contano(casa_test):
    """Uno spazio incollato per sbaglio non si vede, e l'errore non lo dice."""
    for scritta in [PASSWORD_TEST, PASSWORD_TEST + " ", " " + PASSWORD_TEST, "  " + PASSWORD_TEST + "  "]:
        assert houses.autentica(CASA_TEST, scritta), f"rifiutata: {scritta!r}"


def test_una_password_sbagliata_resta_sbagliata(casa_test):
    """Tollerare gli spazi non deve far entrare chi non sa la password."""
    for scritta in ["sbagliata", PASSWORD_TEST[:-1], PASSWORD_TEST + "x", ""]:
        assert not houses.autentica(CASA_TEST, scritta), f"entrata con: {scritta!r}"


def test_la_password_salvata_non_tiene_gli_spazi(tmp_path):
    """Salvata con uno spazio ai bordi, si salva la parte che conta."""
    registro = str(tmp_path / "houses.db")
    slug = houses.crea("Casa Spazi", "  PasswordConSpazi  ", percorso=registro)
    assert houses.autentica(slug, "PasswordConSpazi", percorso=registro)
    assert houses.autentica(slug, "PasswordConSpazi ", percorso=registro)


def test_l_accesso_accetta_la_password_con_spazio_finale(client):
    """Il giro completo: dalla pagina, con lo spazio che il copia-incolla aggiunge."""
    r = client.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST + " "})
    assert r.status_code == 200


def test_la_pagina_fa_vedere_la_password(client):
    """Il campo e' nascosto: senza vederla, uno spazio non si nota."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="acc-mostra"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "acc-mostra" in js and "acc-password" in js


def test_la_pagina_non_resta_in_memoria_nel_browser(anon):
    """Senza questo, una pagina vecchia resta nel browser e l'app sembra
    non aggiornata: e' successo davvero, e per giorni."""
    r = anon.get("/")
    assert r.status_code == 200
    # 'no-cache' basta: dice al browser di richiedere la pagina prima di usarla
    assert "no-cache" in r.headers.get("Cache-Control", "")
    js = anon.get("/static/app.js")
    assert "no-cache" in js.headers.get("Cache-Control", "")


def test_le_immagini_dei_dati_restano_in_memoria(client):
    """La' la memoria serve: una foto non cambia, e riscaricarla a ogni vista
    sarebbe uno spreco."""
    # i dati veri e propri passano dall'API e non si tengono; le foto, che non
    # cambiano, scelgono da sole la loro scadenza in una rotta apposita
    r = client.get("/api/recipes")
    assert "no-cache" in r.headers.get("Cache-Control", "")


def test_una_domanda_non_diventa_un_ordine(client):
    """La frase che assomiglia di piu' a un comando e' una domanda: contiene un
    luogo ("dispensa") e un verbo ("c'e'"). Eseguita, scriveva in dispensa una
    voce chiamata "che cosa c'e in dispensa", e la voce sbagliata resta li'."""
    prima = len(client.get("/api/pantry").get_json())
    r = client.post("/api/voice", json={"text": "che cosa c'è in dispensa"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "domanda"
    assert len(client.get("/api/pantry").get_json()) == prima


def test_una_domanda_su_un_alimento_ne_dice_la_quantita(client):
    """ "quanto sale serve" e' la domanda piu' naturale che ci sia: deve
    rispondere, non finire in lista della spesa."""
    client.post("/api/pantry", json={"name": "Sale", "quantity": 1, "unit": "cucchiaino"})
    r = client.post("/api/voice", json={"text": "quanto sale serve"})
    assert r.status_code == 200
    assert "Sale" in r.get_json()["message"]
    lista = client.get("/api/shopping").get_json()
    assert not any("sale" in i["name"].lower() and "serve" in i["name"].lower() for i in lista)


def test_una_domanda_senza_risposta_non_inventa_niente(client):
    r = client.post("/api/voice", json={"text": "che cosa c'è in dispensa"})
    assert r.status_code == 200
    assert "vuot" in r.get_json()["message"].lower()


def test_un_ordine_resta_un_ordine(client):
    """Le domande non devono rubare il posto ai comandi veri."""
    r = client.post("/api/voice", json={"text": "aggiungi due chili di farina in dispensa"})
    assert r.get_json()["intent"] == "pantry_add"
    r = client.post("/api/voice", json={"text": "segna il pane da comprare"})
    assert r.get_json()["intent"] == "shopping_add"


def test_le_domande_su_ricette_e_pulizie_rispondono(client):
    r = client.post("/api/voice", json={"text": "quante ricette ho"})
    assert r.status_code == 200 and r.get_json()["intent"] == "domanda"
    assert "ricett" in r.get_json()["message"].lower()
    r = client.post("/api/voice", json={"text": "quali pulizie devo fare"})
    assert r.status_code == 200 and r.get_json()["intent"] == "domanda"


def test_il_microfono_non_si_rompe_al_primo_clic(client):
    """Il primo clic apre il pannello e arriva ad `ascolta()` senza nessun
    riconoscimento avviato. Chiamare `stop()` su niente sollevava un errore
    invisibile e il microfono restava muto: era il guasto da PC."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "voce.attivo && voce.rec" in js
    assert "if (voce.attivo) { voce.rec.stop(); return; }" not in js


def test_la_dispensa_mostra_un_icona_per_alimento(client):
    """Un'icona dice a colpo d'occhio di cosa si tratta, prima di leggerlo."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "iconaAlimento" in js and "icona-alimento" in js
    html = client.get("/static/index.html").get_data(as_text=True)
    assert "pantry-table" in html


def test_le_icone_degli_alimenti_sono_scelte_bene(client):
    """Le parole corte non devono entrare dentro le altre: "te" sta in
    "detersivo", e il detersivo non e' una bevanda."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("const ICONE_CATEGORIA"):js.index("\n}\n", js.index("function iconaAlimento")) + 3]
    prova = blocco + """
const casi = [
  ['Farina 00', 'Pane e Cereali', '🌾'],
  ['Passata di pomodoro', 'Dispensa', '🍅'],
  ['Aglio', 'Frutta e Verdura', '🧄'],
  ['Parmigiano', 'Latticini', '🧀'],
  ['Guanciale', 'Carne e Pesce', '🥓'],
  ['Tonno', 'Carne e Pesce', '🐟'],
  ['Detersivo piatti', 'Altro', '🧴'],
  ['Detergente', 'Altro', '🧴'],
  ['Te nero', 'Bevande', '🍵'],
  ['Pile stilo', 'Altro', '🔋'],
  ['Cosa mai vista', 'Altro', '📦'],
];
let esiti = [];
for (const [n, c, atteso] of casi) {
  const avuto = iconaAlimento(n, c);
  esiti.push(`${avuto === atteso ? 'ok' : 'NO'} ${n} -> ${avuto} (atteso ${atteso})`);
}
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout


def test_la_voce_porta_gli_ingredienti_nel_modulo(client):
    """Gli ingredienti dettati arrivano davvero nel modulo, non solo nella risposta.

    Si esegue la funzione vera con node: un test sulle stringhe non accorgerebbe
    di un `nuovaRicetta(res.name)` che si dimentica il secondo argomento, e il
    modulo si aprirebbe vuoto mentre i test del server restano verdi.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function nuovaRicetta")
    blocco = js[inizio:js.index("\n}\n", inizio) + 3]
    prova = """
const finte = [];
let chiamataRecipeForm = null;
global.showModal = (titolo, corpo) => { global._corpo = corpo; };
global.$ = (sel) => ({ addEventListener: (ev, fn) => finte.push([sel, fn]) });
global.esc = (s) => String(s ?? '');
global.recipeForm = (...args) => { chiamataRecipeForm = args; };
global.cercaRicettaOnline = () => {};
""" + blocco + """
const ingredienti = [{ name: 'pasta', quantity: 500, unit: 'g' }];
nuovaRicetta('pasta al forno', ingredienti);
const esiti = [];
esiti.push((global._corpo.includes('pasta') ? 'ok' : 'NO') + ' ingredienti annunciati');
finte.find(([sel]) => sel === '#ric-scrivi')[1]();
esiti.push((chiamataRecipeForm && chiamataRecipeForm[0] === null
  && chiamataRecipeForm[1] === 'pasta al forno'
  && chiamataRecipeForm[2] === ingredienti ? 'ok' : 'NO') + ' ingredienti passati al modulo');
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout


def test_le_righe_degli_ingredienti_dettati_si_precompilano(client):
    """Le dosi dette finiscono nei campi giusti, e chi non ha unità non scrive
    "null".

    Si esegue `addRow` vero con node su un documento finto: un test sulle
    stringhe non vedrebbe un `value="null"` nel campo dell'unità, che l'utente
    leggerebbe come un dato inventato dall'app."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const rowsBox = $('#ing-rows');")
    blocco = js[inizio:js.index("\n  (r.items.length", inizio)]
    prova = """
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const righe = [];
global.document = { createElement: () => ({ set innerHTML(v) { this._html = v; }, appendChild: () => {} }) };
global.$ = () => ({ appendChild: (div) => righe.push(div._html) });
""" + blocco + """
addRow({ name: 'pasta', quantity: 500, unit: 'g' });
addRow({ name: 'uova', quantity: 4, unit: null });
const esiti = [];
esiti.push((righe[0].includes('value="pasta"') && righe[0].includes('value="500"')
  && righe[0].includes('value="g"') ? 'ok' : 'NO') + ' dose completa');
esiti.push((righe[1].includes('value="uova"') && righe[1].includes('value="4"')
  && !righe[1].includes('null') ? 'ok' : 'NO') + ' unita assente senza null');
esiti.push((righe[1].includes('value="pz"') ? 'ok' : 'NO') + ' unita predefinita');
console.log(esiti.join('\\n'));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    assert "NO " not in esito.stdout, esito.stdout


def test_una_sessione_di_una_casa_eliminata_non_da_errore(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    houses.elimina("casa-a")
    info = anon.get("/api/session").get_json()
    assert info["authenticated"] is False


# ------------------------------------------------------------ voce neurale cloud
# La sintesi cloud non si puo' provare chiamando Azure dentro i test: sarebbe una
# chiamata di rete fatturata che dipende da una chiave. Si prova tutto quello che
# sta intorno, che e' la parte che sbaglia: costruzione dell'SSML, validazione
# della voce, limiti, traduzione degli errori e comportamento dell'endpoint.

def test_ssml_ha_voce_lingua_e_prosodia():
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-IsabellaNeural", rate=1.2, pitch=-10)
    assert 'name="it-IT-IsabellaNeural"' in ssml
    assert 'xml:lang="it-IT"' in ssml
    assert 'rate="20%"' in ssml
    assert 'pitch="-10%"' in ssml
    assert ">Ciao<" in ssml


def test_ssml_senza_prosodia_non_aggiunge_tag():
    # a valori normali non deve comparire <prosody>: un tag inutile cambia la
    # lettura di alcune voci, e non c'e' ragione di generarlo
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-ElsaNeural")
    assert "<prosody" not in ssml
    assert ">Ciao<" in ssml


def test_ssml_mette_al_riparo_il_testo():
    # il testo arriva dall'utente e finisce dentro un XML: senza escape un "&"
    # farebbe fallire la sintesi, e un "<" potrebbe iniettare markup
    ssml = voce_cloud.costruisci_ssml("Sale & pepe <script>", "it-IT-ElsaNeural")
    assert "&amp;" in ssml
    assert "&lt;script&gt;" in ssml
    assert "<script>" not in ssml


def test_ssml_limita_i_valori_fuori_scala():
    # un rate assurdamente alto non deve passare ad Azure: si limita qui, dove il
    # comportamento e' prevedibile
    ssml = voce_cloud.costruisci_ssml("Ciao", "it-IT-ElsaNeural", rate=99, pitch=999)
    assert 'rate="100%"' in ssml      # 2.0 - 1
    assert 'pitch="50%"' in ssml      # tetto


def test_voci_italiane_ufficiali():
    nomi = {v["nome"] for v in voce_cloud.elenco_voci()}
    # nomi presi dall'elenco ufficiale Azure: inventarne uno lo farebbe rifiutare
    # da Azure con un 400, quindi restano qui
    assert "it-IT-IsabellaNeural" in nomi
    assert "it-IT-ElsaNeural" in nomi
    assert "it-IT-DiegoNeural" in nomi
    assert voce_cloud.VOCE_PREDEFINITA in nomi


def test_voce_non_riconosciuta_rifiutata_senza_chiamare_azure():
    assert voce_cloud.voce_valida("it-IT-IsabellaNeural")
    # una voce inventata viene fermata prima della chiamata: l'errore e' leggibile
    # e non costa una richiesta
    assert not voce_cloud.voce_valida("it-XX-InventataNeural")
    assert not voce_cloud.voce_valida("")


def test_sintetizza_senza_configurazione_none(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    assert voce_cloud.configurato() is False
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("Ciao", "it-IT-ElsaNeural")
    # 503 e non 502: non e' un guasto, e' una funzione non attivata, e il client
    # usa questo codice per ripiegare sulla voce del browser senza mostrare errori
    assert e.value.stato == 503


def test_testo_troppo_lungo_rifiutato(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("a" * (voce_cloud.MAX_CARATTERI + 1), "it-IT-ElsaNeural")
    assert e.value.stato == 400


def test_testo_vuoto_rifiutato(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    with pytest.raises(voce_cloud.ErroreVoce) as e:
        voce_cloud.sintetizza("   ", "it-IT-ElsaNeural")
    assert e.value.stato == 400


def test_la_chiave_messa_a_monte_accende_la_voce(client, tmp_path, monkeypatch):
    """Il giro completo della configurazione preventiva: si scrive il file
    segreto accanto all'app **prima** dell'avvio, e l'app lo trova da sola.

    E' l'unico modo in cui la chiave entra: non c'e' una rotta che la scriva, e
    non c'e' un campo nella pagina. Se questo giro si rompesse, la voce
    tornerebbe meccanica senza che l'utente abbia modo di rimediare.
    """
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)
    (tmp_path / "segreto.sh").write_text(
        "export AZURE_SPEECH_KEY='ChiaveMessaPrima'\n"
        "export AZURE_SPEECH_REGION='italynorth'\n")

    d = client.get("/api/voce/config").get_json()
    assert d["cloud"] is True
    assert d["ascolto"] is True            # la stessa chiave serve al microfono
    # e la chiave continua a non comparire nella risposta
    assert "ChiaveMessaPrima" not in json.dumps(d)


def test_endpoint_config_senza_chiave(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    d = client.get("/api/voce/config").get_json()
    assert d["cloud"] is False
    # l'elenco si mostra comunque: serve a capire cosa si attiverebbe
    assert any(v["nome"] == "it-IT-ElsaNeural" for v in d["voci"])
    # la chiave non deve mai comparire nella risposta
    assert "AZURE_SPEECH_KEY" not in json.dumps(d)


def test_elenco_voci_viene_dal_servizio_non_da_un_elenco_scritto(monkeypatch):
    """Le voci offerte devono essere quelle che l'area ha davvero.

    Un elenco scritto a mano offriva due voci "HD" che in italynorth non esistono:
    sceglierle faceva rispondere 400, proprio alla voce presentata come migliore.
    """
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_voci_cache", {"area": None, "quando": 0.0, "elenco": None})
    # risposta di prova: l'area ha Isabella ma non la "HD"
    finta = json.dumps([
        {"ShortName": "it-IT-IsabellaNeural", "Gender": "Female"},
        {"ShortName": "it-IT-DiegoNeural", "Gender": "Male"},
        {"ShortName": "en-US-AvaNeural", "Gender": "Female"},   # altra lingua: fuori
    ]).encode()

    class Risposta:
        def read(self): return finta
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", lambda *a, **k: Risposta())
    voci = voce_cloud.elenco_voci()
    nomi = [v["nome"] for v in voci]
    assert nomi[0] == voce_cloud.VOCE_PREDEFINITA      # la predefinita resta in testa
    assert "it-IT-IsabellaNeural" in nomi
    assert "it-IT-DiegoNeural" in nomi
    assert not any("en-US" in n for n in nomi)         # solo italiano
    assert not any("DragonHD" in n for n in nomi)      # la "HD" non esiste qui
    # e la voce che l'area non ha viene fermata prima della chiamata
    assert not voce_cloud.voce_valida("it-IT-Isabella:DragonHDLatestNeural")
    assert voce_cloud.voce_valida("it-IT-IsabellaNeural")


def test_elenco_voci_ripiega_se_il_servizio_non_risponde(monkeypatch):
    """Senza risposta dal servizio resta l'elenco scritto a mano: meglio di nessuno."""
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_voci_cache", {"area": None, "quando": 0.0, "elenco": None})

    def esplode(*a, **k):
        raise OSError("rete assente")

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", esplode)
    nomi = {v["nome"] for v in voce_cloud.elenco_voci()}
    assert "it-IT-IsabellaNeural" in nomi               # il ripiego c'e'
    assert voce_cloud.voce_valida("it-IT-ElsaNeural")   # e resta utilizzabile


def test_errore_400_suggerisce_di_cambiare_voce(monkeypatch):
    """L'errore non dice solo che e' andata male: dice cosa fare."""
    import urllib.error
    e = urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
    assert "voce" in voce_cloud._spiega_errore(e).lower()


# ------------------------------------------------------- trascrizione (ascolto)

class _Ascolto:
    """Risposta finta di Azure all'audio breve, per non toccare la rete."""

    def __init__(self, corpo: bytes):
        self._corpo = corpo

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _con_chiave(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorth")
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)


def test_trascrizione_restituisce_il_testo_riconosciuto(monkeypatch):
    _con_chiave(monkeypatch)
    # un WAV finto abbastanza lungo da non essere scartato come silenzio
    finto = b"\x00" * voce_cloud.MIN_AUDIO_BYTE
    monkeypatch.setattr(
        voce_cloud.urllib.request, "urlopen",
        lambda *a, **k: _Ascolto(json.dumps(
            {"RecognitionStatus": "Success", "DisplayText": "aggiungi due chili di farina in dispensa"}
        ).encode()))
    assert voce_cloud.trascrivi(finto) == "aggiungi due chili di farina in dispensa"


def test_trascrizione_manda_wav_16khz_mono(monkeypatch):
    """Il servizio accetta **solo** WAV PCM 16 kHz: l'intestazione deve dirlo.

    Sbagliarla non da' un errore chiaro: il servizio risponde 400 e sembra un
    guasto dell'app.
    """
    _con_chiave(monkeypatch)
    viste = {}

    def cattura(richiesta, **_k):
        viste["headers"] = {c.lower(): v for c, v in richiesta.header_items()}
        viste["url"] = richiesta.full_url
        return _Ascolto(json.dumps({"RecognitionStatus": "Success", "DisplayText": "ciao"}).encode())

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", cattura)
    voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE)

    assert viste["headers"]["content-type"] == "audio/wav; codecs=audio/pcm; samplerate=16000"
    assert "language=it-IT" in viste["url"]
    assert "stt.speech.microsoft.com" in viste["url"]


def test_trascrizione_senza_parlato_non_e_un_errore(monkeypatch):
    """Silenzio o rumore: il servizio dice NoMatch, che non e' un guasto.

    Se diventasse un errore, il client mostrerebbe un guasto al posto di
    "non ho sentito nulla", e non ripiegherebbe mai sul riconoscimento del
    browser quando serve davvero.
    """
    _con_chiave(monkeypatch)
    monkeypatch.setattr(
        voce_cloud.urllib.request, "urlopen",
        lambda *a, **k: _Ascolto(json.dumps({"RecognitionStatus": "NoMatch"}).encode()))
    assert voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE) == ""


def test_trascrizione_audio_troppo_corto_non_chiama_il_servizio(monkeypatch):
    """Un microfono aperto per sbaglio non deve costare una chiamata."""
    _con_chiave(monkeypatch)

    def non_chiamare(*a, **k):
        raise AssertionError("non doveva contattare Azure")

    monkeypatch.setattr(voce_cloud.urllib.request, "urlopen", non_chiamare)
    assert voce_cloud.trascrivi(b"\x00" * 100) == ""


def test_trascrizione_non_configurata_ripiega(monkeypatch):
    """Senza chiave lo stato e' 503: il client sa che puo' usare il browser."""
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    assert not voce_cloud.configurato()
    with pytest.raises(voce_cloud.ErroreAscolto) as e:
        voce_cloud.trascrivi(b"\x00" * voce_cloud.MIN_AUDIO_BYTE)
    assert e.value.stato == 503


def test_errore_di_ascolto_401_non_riporta_la_risposta(monkeypatch):
    """La spiegazione resta un messaggio per l'utente, senza dettagli della risorsa."""
    import urllib.error
    e = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    messaggio = voce_cloud._spiega_errore_ascolto(e)
    assert "chiave" in messaggio.lower() and "401" not in messaggio


def test_la_scheda_voce_e_stata_rimossa(client):
    """Le impostazioni della voce (timbro, voce neurale) non hanno piu' una scheda
    nelle FAQ: il pannello del microfono resta ai comandi soltanto. L'interruttore
    della comprensione col modello si e' spostato in Profilo, perche' serve."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="tab-voce"' not in html
    for pezzo in ('id="voice-pick"', 'id="voice-all"', 'id="voice-cloud"',
                  'id="voice-ting"'):
        assert pezzo not in html, pezzo
    # il pannello del microfono resta ai comandi
    inizio = html.index('id="voice"')
    pannello = html[inizio:]
    for pezzo in ('id="voice-text"', 'id="voice-retry"', 'id="voice-heard"'):
        assert pezzo in pannello, pezzo
    # e la comprensione col modello sta nel Profilo
    profilo = html.index('id="tab-profile"')
    faq = html.index('id="tab-faq"')
    assert profilo < html.index('id="voice-llm"') < faq


def test_gli_errori_del_microfono_portano_a_scrivere(client):
    """Se il browser non puo' ascoltare (rete bloccata, microfono negato), l'unica
    strada e' scrivere: il campo va messo a fuoco, senza farlo cercare."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "#voice-text" in js
    assert "campo.focus()" in js


def test_il_pannello_mostra_delle_domande_da_provare(client):
    """Le domande sono una possibilita' nuova: senza un esempio non si scoprono."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-say="che cosa c\'è in dispensa"' in html
    assert 'data-say="quanto sale serve"' in html


def test_endpoint_config_con_chiave_non_espone_la_chiave(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-segreta-di-prova")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    r = client.get("/api/voce/config")
    assert r.get_json()["cloud"] is True
    # il controllo che conta: la chiave resta sul server, il browser vede solo
    # l'elenco delle voci
    assert b"chiave-segreta-di-prova" not in r.data


def test_endpoint_parla_senza_configurazione_da_503(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    r = client.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 503


def test_endpoint_parla_restituisce_audio(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    # si sostituisce solo la chiamata di rete: il resto del percorso (validazione,
    # SSML, risposta HTTP) e' quello vero
    def finta(testo, voce, rate=1.0, pitch=0.0, stile=None, timeout=12.0):
        return b"ID3finto"
    monkeypatch.setattr(voce_cloud, "sintetizza", finta)
    r = client.post("/api/voce/parla", json={"text": "Fatto.", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 200
    assert r.mimetype == "audio/mpeg"
    assert r.data == b"ID3finto"


def test_endpoint_parla_rifiuta_voce_inventata(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    r = client.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-XX-NonEsiste"})
    # 400 e non 500: e' una richiesta sbagliata, non un guasto del server
    assert r.status_code == 400


def test_endpoint_parla_richiede_accesso(anon):
    # la chiave del servizio non deve essere usabile da chi non e' collegato:
    # altrimenti chiunque trovi il link potrebbe consumare il credito
    r = anon.post("/api/voce/parla", json={"text": "Ciao", "voice": "it-IT-ElsaNeural"})
    assert r.status_code == 401
    assert anon.get("/api/voce/config").status_code == 401


def test_endpoint_ascolta_restituisce_il_testo(client, monkeypatch):
    """Il microfono passa dal server: il browser non deve raggiungere nessun
    servizio di ascolto, che è quello che gli si blocca dietro firewall e VPN."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "metti il latte nella spesa")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    assert r.get_json()["testo"] == "metti il latte nella spesa"


def test_endpoint_ascolta_distingue_il_silenzio_dalla_frase_non_capita(client, monkeypatch):
    """Vuoto vuol dire "non ho sentito nulla", ed è diverso da una frase che non
    è un comando: il client lo dice con parole diverse."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    assert r.get_json()["testo"] == ""


def test_endpoint_ascolta_senza_chiave_dice_al_client_di_ripiegare(client, monkeypatch):
    """503, non 500: non è un guasto, è una funzione non attivata, e il client
    usa il riconoscimento del browser senza mostrare un errore."""
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", True)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 503


def test_endpoint_ascolta_richiede_accesso(anon):
    # la stessa chiave della sintesi: non deve essere usabile da chi non è collegato
    r = anon.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 401


def test_la_config_dice_al_microfono_di_passare_dal_server(client, monkeypatch):
    """Il client sceglie la strada del microfono in base a `ascolto`: se la chiave
    c'è, registra e manda al server; se non c'è, usa il browser. Sbagliare qui
    riporta il microfono al guasto da firewall che si vuole evitare."""
    _con_chiave(monkeypatch)
    assert client.get("/api/voce/config").get_json()["ascolto"] is True
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", "/nonexistent")
    monkeypatch.setattr(voce_cloud, "DATA_DIR", "/nonexistent")
    assert client.get("/api/voce/config").get_json()["ascolto"] is False


# ------------------------------------------------------------ copia dei dati
# I database non sono in git: senza un modo per scaricarli, cambiare macchina
# significherebbe perdere il lavoro. L'endpoint esiste per questo, ed e' anche
# un punto delicato: esporta *una* casa, non tutte.

def test_backup_richiede_accesso(anon):
    assert anon.get("/api/backup").status_code == 401


def test_backup_contiene_i_dati_della_casa_e_ricostruisce_un_database(client, tmp_path):
    import io as _io
    import zipfile as _zip

    # un dato riconoscibile, per ritrovarlo dopo il giro completo
    client.post("/api/shopping", json={"name": "Carciofi per la copia", "qty": 2})

    r = client.get("/api/backup")
    assert r.status_code == 200
    assert r.mimetype == "application/zip"

    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    nomi = archivio.namelist()
    # il database col suo nome, piu' il file in scena
    assert any(n.endswith(".db") for n in nomi), nomi
    assert "LEGGIMI.txt" in nomi
    assert "Copia dei dati" in archivio.read("LEGGIMI.txt").decode()

    # il file estratto deve essere un database che l'app sa riaprire, non il
    # testo delle istruzioni SQL: rinominato `.db` un dump testuale farebbe
    # rispondere `file is not a database`, e il ripristino fallirebbe
    dati = archivio.read([n for n in nomi if n.endswith(".db")][0])
    assert dati[:16] == b"SQLite format 3\x00", dati[:32]
    percorso = tmp_path / "ripristinato.db"
    percorso.write_bytes(dati)
    with closing(sqlite3.connect(percorso)) as riaperto:
        trovato = riaperto.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE name LIKE '%Carciofi per la copia%'"
        ).fetchone()[0]
    assert trovato == 1


def test_backup_porta_via_anche_le_foto(client, tmp_path):
    """Le foto stanno nel database proprio per questo: la copia resta un file solo.

    Se le foto fossero su disco, l'archivio sarebbe incompleto e chi ripristina
    perderebbe le immagini senza accorgersene.
    """
    import io as _io
    import zipfile as _zip

    sid = voce_con_foto(client, nome="Scatola fotografata")

    r = client.get("/api/backup")
    assert r.status_code == 200
    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    dati = archivio.read([n for n in archivio.namelist() if n.endswith(".db")][0])
    percorso = tmp_path / "con-foto.db"
    percorso.write_bytes(dati)

    with closing(sqlite3.connect(percorso)) as riaperto:
        riga = riaperto.execute(
            "SELECT storage_id, mime, data FROM storage_photos WHERE storage_id = ?",
            (sid,)).fetchone()
    assert riga is not None, "la foto non e' finita nel backup"
    assert riga[1] == "image/png"
    assert riga[2] == PNG_1PX


def test_backup_non_contiene_le_altre_case(client, tmp_path):
    """L'archivio non deve contenere tracce di case diverse da quella collegata.

    Il registro (`houses.db`) e' la cosa da non far uscire: contiene nomi e
    password di tutte le case. Un utente collegato a una casa non deve poter
    scaricare l'elenco, ne' i dati, dell'altra.
    """
    import io as _io
    import zipfile as _zip

    r = client.get("/api/backup")
    assert r.status_code == 200

    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    nomi = archivio.namelist()
    # i byte non testuali si saltano: lo schema delle tabelle e' testo UTF-8, e
    # quello basta a scoprire un nome indesiderato dentro l'archivio
    grezzo = b"".join(archivio.read(n) for n in nomi)
    contenuto = grezzo.decode("utf-8", "ignore")

    # il registro delle case non deve comparire, in nessuna forma: ne' come file,
    # ne' come tabella dentro l'esportazione
    assert not any("houses.db" in n for n in nomi), nomi
    assert "CREATE TABLE houses" not in contenuto
    assert "password" not in contenuto

    # controlla anche la struttura, non solo il testo: il database esportato non
    # deve avere una tabella che somigli al registro
    percorso = tmp_path / "esportato.db"
    percorso.write_bytes(archivio.read([n for n in nomi if n.endswith(".db")][0]))
    with closing(sqlite3.connect(percorso)) as esportato:
        tabelle = {r[0].lower() for r in esportato.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert not (tabelle & {"houses", "case", "registry"}), tabelle


# ------------------------------------------------------------ percorsi dei dati
# I dati devono poter stare fuori dal progetto: e' quello che serve quando il
# codice sta in un'immagine Docker e i dati in un volume, e quando si fa un
# backup. Qui si verifica che `MAGGIORDOMO_DATA` sposti davvero *tutti* i file,
# non solo i piu' ovvi: dimenticarne uno significherebbe un backup incompleto.

def test_data_dir_sposta_registro_case_e_database_storico(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    # i percorsi sono calcolati all'import: per provare la variabile va ricaricato
    importlib.reload(houses)
    try:
        assert houses.REGISTRY_PATH == str(tmp_path / "houses.db")
        assert houses.CASE_DIR == str(tmp_path / "case")

        # il registro deve nascere dove abbiamo detto, non accanto al codice
        houses.init_registro()
        assert (tmp_path / "houses.db").exists()
        assert not (tmp_path.parent / "houses.db").exists()

        houses.registra("casa-prova", "Casa Prova", "segreta", "cucina.db")
        # la casa storica punta a un file che sta in DATA_DIR: cercarlo accanto al
        # codice lo renderebbe invisibile con i dati altrove
        assert houses.db_path("casa-prova").endswith("cucina.db")
        assert os.path.dirname(houses.db_path("casa-prova")) == str(tmp_path)
    finally:
        # si ripristina il modulo vero, altrimenti i test successivi userebbero
        # una DATA_DIR temporanea ormai cancellata
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)




# ------------------------------------------------ ricette da un sito esterno
# La rete non si tocca nei test: si sostituisce solo `_apri`, il punto da cui
# esce ogni richiesta, e si costruiscono pagine finte con lo stesso JSON-LD che
# pubblicano i siti veri. Cosi' si prova l'interpretazione, che e' la parte che
# sbaglia, senza dipendere da un sito che cambia o non risponde alla CI.

import ricette_online  # noqa: E402


def pagina_ricetta(nome="Spaghetti alla Carbonara", porzioni="4",
                   ingredienti=("Spaghetti 320 g", "Guanciale 150 g", "Tuorli 6"),
                   passi=("Mettete l'acqua sul fuoco.", "Rosolate il guanciale.")):
    ld = {
        "@context": "https://schema.org", "@type": "Recipe", "name": nome,
        "recipeYield": porzioni, "totalTime": "PT25M",
        "recipeIngredient": list(ingredienti),
        "recipeInstructions": [{"@type": "HowToStep", "text": p} for p in passi],
        "author": {"@type": "Person", "name": "GialloZafferano"},
    }
    return ('<html><head><script type="application/ld+json">'
            + json.dumps(ld) + '</script></head><body>cucina</body></html>')


def finta_rete(monkeypatch, risposte, permesso=True):
    """Sostituisce la lettura di rete con pagine preparate.

    `risposte` e' un dizionario indirizzo -> contenuto. `_permesso` si forza a
    parte perche' il controllo del robots.txt e' una decisione a se': qui interessa
    la lettura della ricetta, e la politica dei permessi ha i suoi test.
    """
    def apri(url):
        if url not in risposte:
            raise ricette_online.NonDisponibile(f"indirizzo di prova non previsto: {url}")
        return risposte[url]
    monkeypatch.setattr(ricette_online, "_apri", apri)
    monkeypatch.setattr(ricette_online, "_permesso", lambda url: permesso)


def test_dividi_ingrediente_toglie_le_dosi_in_fondo():
    assert ricette_online.dividi_ingrediente("Spaghetti 320 g") == ("Spaghetti", 320.0, "g")
    assert ricette_online.dividi_ingrediente("Tuorli 6") == ("Tuorli", 6.0, "pz")


def test_dividi_ingrediente_ignora_note_e_quantita_a_sentimento():
    # la nota fra parentesi spiega il prodotto, non e' parte del nome; "q.b." non
    # e' una dose: inventarne una falserebbe la dispensa, quindi resta a zero
    assert ricette_online.dividi_ingrediente("Guanciale (stagionato) 200 g") == ("Guanciale", 200.0, "g")
    nome, quantita, _ = ricette_online.dividi_ingrediente("Sale q.b.")
    assert nome == "Sale" and quantita == 0


def test_minuti_da_durata_iso():
    assert ricette_online._minuti("PT25M") == 25
    assert ricette_online._minuti("PT1H20M") == 80
    assert ricette_online._minuti(None) is None


def test_importa_legge_la_ricetta_dal_dato_strutturato(monkeypatch):
    url = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
    finta_rete(monkeypatch, {url: pagina_ricetta()})
    d = ricette_online.importa(url)
    assert d["name"] == "Spaghetti alla Carbonara"
    assert d["servings"] == 4
    assert d["time_minutes"] == 25
    assert [i["name"] for i in d["items"]] == ["Spaghetti", "Guanciale", "Tuorli"]
    assert "Rosolate il guanciale" in d["instructions"]
    # la fonte resta scritta: e' l'unica cosa che rende lecito tenere il testo altrui
    assert "GialloZafferano" in d["source"] and url in d["source"]


def test_importa_non_salva_niente(monkeypatch, client):
    # la ricetta importata si ferma sulla soglia: entra in archivio solo se
    # l'utente la salva dal modulo, mai per il solo fatto di averla letta
    url = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
    finta_rete(monkeypatch, {url: pagina_ricetta(nome="Ricetta Mai Salvata")})
    assert client.get(f"/api/ricette/importa?url={url}").status_code == 200
    elenco = client.get("/api/recipes").get_json()
    assert all(r["name"] != "Ricetta Mai Salvata" for r in elenco)


def test_importa_ricetta_illeggibile_lo_dice(monkeypatch, client):
    url = "https://ricette.giallozafferano.it/vuota.html"
    finta_rete(monkeypatch, {url: "<html><body>niente ricetta qui</body></html>"})
    r = client.get(f"/api/ricette/importa?url={url}")
    assert r.status_code == 502
    assert "non contiene una ricetta leggibile" in r.get_json()["error"]


def test_importa_rifiuta_indirizzi_di_altri_siti():
    # non e' una difesa contro attacchi: e' che il modulo sa leggere *un* sito, e
    # mandarlo altrove e' un errore da dire subito, non da far fallire dopo
    with pytest.raises(ricette_online.NonDisponibile):
        ricette_online.importa("https://esempio.invalid/ricetta.html")


def test_importa_rispetta_i_divieti_del_robots(monkeypatch):
    url = "https://ricette.giallozafferano.it/vietata.html"
    finta_rete(monkeypatch, {url: pagina_ricetta()}, permesso=False)
    with pytest.raises(ricette_online.NonDisponibile):
        ricette_online.importa(url)


def test_il_robots_non_vieta_tutto_per_un_403_dello_scaricatore(monkeypatch):
    """Il robots.txt risponde 403 allo UA di `urllib`, non al nostro.

    `RobotFileParser.read()` scarica con "Python-urllib/...", che questo sito
    respinge; un 403 significa "vietato" e il parser lo leggeva come "vietato a
    tutti". Il risultato era che *nessuna* pagina risultava permessa. Il test
    fissa il comportamento: lo UA di default viene rifiutato, il nostro no, e la
    pagina consentita dal file deve risultare leggibile.
    """
    robot = "User-agent: *\nDisallow: /vietata/\n"
    monkeypatch.setattr(ricette_online, "_apri", lambda url: robot)
    # la pagina di ricerca non e' vietata dal file: deve risultare leggibile
    assert ricette_online._permesso("https://www.giallozafferano.it/ricerca-ricette/carbonara/") is True
    assert ricette_online._permesso("https://www.giallozafferano.it/vietata/pagina/") is False

    def apri(url):
        raise ricette_online.NonDisponibile("403 con lo UA sbagliato")

    # se il robots.txt non si legge si procede: non poterlo leggere non e' un divieto
    monkeypatch.setattr(ricette_online, "_apri", apri)
    assert ricette_online._permesso("https://ricette.giallozafferano.it/Spaghetti.html") is True


def test_cerca_legge_i_collegamenti_alle_ricette(monkeypatch):
    pagina = ('<html><body>'
              '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">x</a>'
              '<a href="https://ricette.giallozafferano.it/Carbonara-di-mare.html" title="Carbonara di mare">y</a>'
              '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">ripetuta</a>'
              '<a href="https://www.giallozafferano.it/altro.html">non una ricetta</a>'
              '</body></html>')
    finta_rete(monkeypatch, {"https://www.giallozafferano.it/ricerca-ricette/carbonara/": pagina})
    trovate = ricette_online.cerca("carbonara")
    assert [r["titolo"] for r in trovate] == ["Carbonara", "Carbonara di mare"]


def test_cerca_una_parola_vuota_non_chiede_niente_alla_rete(monkeypatch):
    monkeypatch.setattr(ricette_online, "_apri",
                        lambda url: pytest.fail("la rete non va interrogata senza testo"))
    assert ricette_online.cerca("   ") == []


def test_endpoint_della_ricerca_risponde_col_risultato(monkeypatch, client):
    pagina = '<a href="https://ricette.giallozafferano.it/Carbonara.html" title="Carbonara">x</a>'
    finta_rete(monkeypatch, {"https://www.giallozafferano.it/ricerca-ricette/carbonara/": pagina})
    r = client.get("/api/ricette/cerca?q=carbonara")
    assert r.status_code == 200
    d = r.get_json()
    assert d["sito"] == "GialloZafferano"
    assert d["risultati"][0]["titolo"] == "Carbonara"


def test_endpoint_della_ricerca_spiega_quando_il_sito_non_risponde(monkeypatch, client):
    finta_rete(monkeypatch, {})   # nessun indirizzo previsto: la lettura fallisce
    r = client.get("/api/ricette/cerca?q=carbonara")
    assert r.status_code == 502
    assert r.get_json()["error"]


def test_endpoint_della_ricerca_senza_testo_non_esce_dal_server(client):
    r = client.get("/api/ricette/cerca?q=")
    assert r.status_code == 400


def test_fonte_di_una_ricetta_importata_si_salva_senza_foto(client):
    """Una ricetta presa da un sito non ha foto ma ha una fonte da citare.

    Legare la fonte alla foto la faceva sparire al salvataggio: la ricetta
    entrava in archivio senza dire da dove veniva.
    """
    ric = crea_ricetta(client, source="GialloZafferano — https://esempio/ricetta")
    letto = client.get(f"/api/recipes/{ric['id']}").get_json()
    assert letto["source"] == "GialloZafferano — https://esempio/ricetta"
    assert letto["image"] == ""


def test_salvataggio_parziale_non_cancella_la_fonte(client):
    ric = crea_ricetta(client, source="Fonte originale")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": "Nome cambiato", "servings": 3, "instructions": "", "items": ric["items"]})
    assert risposta.get_json()["source"] == "Fonte originale"


# ---------------------------------------------------- errori in italiano
# Un errore in inglese, o una pagina bianca senza spiegazione, e' la cosa che
# disorienta di piu' nel momento peggiore. Qui si verifica che l'utente legga
# sempre una frase italiana, e che l'API riceva JSON (non l'HTML della pagina)
# perche' chi chiama l'API si aspetta un campo `error`.

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


# ------------------------------------------------------- copie automatiche
# Il pulsante "Scarica una copia" salva solo chi si ricorda di premerlo. Le copie
# automatiche sono la rete di sicurezza che non dipende dalla memoria: la prima
# deve esistere subito, altrimenti un server appena installato non ne ha nessuna
# proprio quando serve. Qui si verifica il comportamento vero: che la copia sia
# un database riapribile, che non si accumulino all'infinito e che una casa non
# veda le copie dell'altra.

def test_la_copia_e_un_database_riapribile_con_i_dati_dentro(client):
    """Non basta che il file esista: deve essere un database che l'app riapre."""
    client.post("/api/shopping", json={"name": "Sedano per la copia", "qty": 3})

    scritte = copie.fai_copie()
    assert len(scritte) == 1, scritte

    with closing(sqlite3.connect(scritte[0])) as copiato:
        trovato = copiato.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE name LIKE '%Sedano per la copia%'"
        ).fetchone()[0]
    assert trovato == 1


def test_la_prima_copia_arriva_subito_anche_col_server_appena_acceso(client):
    """Se la prima copia aspettasse un giorno, chi installa l'app oggi non
    avrebbe nessuna copia per un giorno intero."""
    copie.svuota()
    assert copie.elenco(CASA_TEST)["quante"] == 0

    app_module._giro_di_copie()

    assert copie.elenco(CASA_TEST)["quante"] == 1


def test_non_si_accumulano_oltre_il_limite(client):
    """La cartella non deve crescere senza fine su una macchina accesa per mesi."""
    import datetime as _dt

    # copie forzate con orari diversi: due copie nello stesso secondo avrebbero
    # lo stesso nome e la seconda sovrascriverebbe la prima invece di sommarsi
    for i in range(copie.QUANTE + 4):
        copie.copia_casa(CASA_TEST, quando=_dt.datetime.now() + _dt.timedelta(minutes=i))

    assert copie.elenco(CASA_TEST)["quante"] == copie.QUANTE


def test_una_casa_non_tocca_le_copie_dell_altra(client):
    """Le copie stanno separate per casa: chi ne cancella una non deve poter
    toccare lo spazio dell'altra."""
    altra = houses.crea("Casa Vicina", "password-vicina")
    app_module.init_db(houses.db_path(altra), con_ricettario=True)

    copie.fai_copie()

    assert copie.elenco(CASA_TEST)["quante"] == 1
    assert copie.elenco(altra)["quante"] == 1
    # ognuna nel suo spazio, e nessun file condiviso
    assert copie._copie_di(CASA_TEST)[0] != copie._copie_di(altra)[0]


def test_il_giro_automatico_non_ricopia_una_casa_gia_copiata(client):
    """Il giro gira ogni ora ma la copia e' giornaliera: senza questo salto
    una casa avrebbe ventiquattro copie al giorno e la cartella si riempirebbe."""
    app_module._giro_di_copie()
    prima = copie._copie_di(CASA_TEST)

    scritto = copie.fai_copie(forse=True)

    assert scritto == [], scritto
    assert copie._copie_di(CASA_TEST) == prima


def test_una_copia_fallita_non_lascia_un_file_a_meta(client, monkeypatch):
    """Il file provvisorio non deve restare nella cartella: verrebbe contato
    come copia valida al giro dopo, e la copia piu' recente sarebbe rotta.

    Si imita il caso vero: SQLite crea il file appena si connette, quindi un
    guasto durante la scrittura lascia un file a meta' che senza pulizia
    resterebbe li' col nome di una copia buona.
    """
    vero = sqlite3.connect
    chiamate = []

    class Finta:
        def backup(self, *_a):
            raise sqlite3.OperationalError("disco pieno")

        def close(self):
            pass

    class FintoSqlite:
        """Visto solo da `copie`: patching il modulo vero toccherebbe anche il
        registro delle case, che deve continuare a funzionare."""
        Error = sqlite3.Error

        @staticmethod
        def connect(percorso, *a, **k):
            chiamate.append(percorso)
            if len(chiamate) == 1:
                # la sorgente e' quella che fallisce durante la copia, quindi il
                # destinatario e' un file vero: e' proprio il file a meta' che la
                # pulizia deve togliere
                return Finta()
            return vero(percorso)

    monkeypatch.setattr(copie, "sqlite3", FintoSqlite)
    with pytest.raises(sqlite3.OperationalError):
        copie.copia_casa(CASA_TEST)

    cartella = os.path.join(copie.cartella(), CASA_TEST)
    avanzi = os.listdir(cartella) if os.path.isdir(cartella) else []
    assert avanzi == [], avanzi


def test_api_copie_dice_quante_ce_ne_sono(client):
    """L'utente deve poter vedere che le copie ci sono, senza cercare sul disco."""
    app_module._giro_di_copie()
    d = client.get("/api/copie").get_json()
    assert d["quante"] == 1
    assert d["conservate"] == copie.QUANTE
    assert d["ultima"], d


def test_api_copie_richiede_accesso(anon):
    assert anon.get("/api/copie").status_code == 401


def test_api_copie_non_nomina_le_altre_case(client):
    """Il conteggio e' della sola casa collegata: le altre non si nominano."""
    altra = houses.crea("Casa Vicina", "password-vicina")
    app_module.init_db(houses.db_path(altra), con_ricettario=True)
    app_module._giro_di_copie()

    d = client.get("/api/copie").get_json()
    assert d["quante"] == 1
    testo = json.dumps(d, ensure_ascii=False)
    assert "vicina" not in testo.lower()


# ---------------------------------------------------- tentativi di accesso
# Le password sono protette bene, ma si potevano provare all'infinito: il server
# ascolta su 0.0.0.0 per farsi raggiungere dal telefono, quindi chi e' sulla
# stessa rete poteva continuare per giorni. Qui si verifica che il freno esista,
# che non dia fastidio a chi entra davvero e che non si possa aggirare cambiando
# il nome della casa.

def test_il_dockerfile_copia_tutto_quello_che_serve(client):
    """Per l'accesso **da ovunque** l'app va su una macchina sempre accesa, e la
    via e' un'immagine: se il `Dockerfile` dimenticasse un modulo, l'app
    partirebbe e morirebbe con un `ModuleNotFoundError` solo in produzione — il
    posto peggiore per scoprirlo.

    Si legge il `Dockerfile` e si controlla che **ogni** modulo locale importato
    dal codice sia copiato nell'immagine, piu' i file dati (`schema.sql`) e la
    cartella `static`."""
    import re
    base = BASE_APP
    dockerfile = open(f"{base}/Dockerfile", encoding="utf-8").read()

    # i moduli locali: quelli importati dal codice e presenti come .py accanto
    moduli = set()
    for nome in os.listdir(base):
        if nome.endswith(".py"):
            moduli.add(nome)
    # quali sono importati da qualche parte (quindi necessari a runtime)
    usati = set()
    for nome in moduli:
        sorgente = open(f"{base}/{nome}", encoding="utf-8").read()
        for altro in moduli:
            if altro == nome:
                continue
            if re.search(rf"^import {altro[:-3]}\b|^from {altro[:-3]} import", sorgente, re.M):
                usati.add(altro)
    # il punto d'ingresso e i suoi import: si parte da app.py e si chiude
    da_copiare = {"app.py", "schema.sql"}
    da_copiare |= usati
    # seed.py e' importato da app.py in modo ritardato (dentro una funzione)
    da_copiare.add("seed.py")

    for nome in sorted(da_copiare):
        assert nome in dockerfile, f"il Dockerfile non copia {nome}"
    assert "static" in dockerfile, "il Dockerfile non copia la cartella static"


def test_dietro_un_proxy_si_legge_l_indirizzo_vero(anon, monkeypatch):
    """Con un tunnel davanti (Tailscale Funnel, Cloudflare) la richiesta arriva
    dal proxy: senza leggere i suoi header, l'indirizzo di chi bussa e' sempre
    quello del proxy, e **il freno ai tentativi conta tutti su un indirizzo
    solo** — chi sbaglia la password blocca anche gli altri.

    Si attiva `DIETRO_PROXY` e si manda l'header come farebbe il tunnel: il freno
    dev'essere contato sull'indirizzo vero, non su quello del proxy."""
    import importlib
    monkeypatch.setenv("DIETRO_PROXY", "1")
    ricaricato = importlib.reload(app_module)
    try:
        with ricaricato.app.test_client() as c:
            # il freno conta due chiavi, l'indirizzo **e** il nome della casa
            # (vedi `chiavi_tentativi`): per isolare l'indirizzo si sbaglia con
            # nomi di casa diversi, cosi' resta in gioco solo la chiave dell'IP
            for i in range(houses.TENTATIVI_LIBERI + 1):
                c.post("/api/login", json={"nome": f"Casa {i}", "password": "no"},
                       headers={"X-Forwarded-For": "10.0.0.1"})
            # lo stesso indirizzo e' ormai frenato
            bloccato = c.post("/api/login", json={"nome": "Altra", "password": "no"},
                              headers={"X-Forwarded-For": "10.0.0.1"})
            assert bloccato.status_code == 429, "l'indirizzo frenato non lo e' piu'"
            # un indirizzo **diverso** non ha ancora sbagliato: se il proxy non
            # fosse letto, sarebbe lo stesso indirizzo del precedente e troverebbe
            # il freno (429) invece di un semplice rifiuto (401)
            r = c.post("/api/login", json={"nome": "Ancora", "password": "no"},
                       headers={"X-Forwarded-For": "10.0.0.2"})
            assert r.status_code == 401, "l'indirizzo vero non e' stato letto"
    finally:
        monkeypatch.delenv("DIETRO_PROXY", raising=False)
        importlib.reload(app_module)


def test_dietro_un_proxy_la_pagina_resta_raggiungibile(anon):
    """Il tunnel inoltra su http, ma chi bussa e' su https: la pagina non deve
    dipendere da quale dei due vede il server. Si guarda che la risposta non
    contenga un indirizzo assoluto in `http://` (un redirect o un link cosi'
    riporterebbe l'utente fuori dall'https, e il browser blocca il microfono)."""
    html = anon.get("/", headers={"X-Forwarded-Proto": "https",
                                  "X-Forwarded-Host": "casa.esempio.ts.net"}
                    ).get_data(as_text=True)
    assert 'src="http://' not in html and "href=\"http://" not in html


def test_dopo_troppi_errori_la_risposta_dice_di_aspettare(anon):
    nome, sbagliata = "Casa Test", "sbagliata"
    # i primi tentativi sono liberi: sbagliare due volte capita, e non deve
    # diventare un'attesa
    for _ in range(houses.TENTATIVI_LIBERI):
        assert anon.post("/api/login", json={"nome": nome, "password": sbagliata}
                         ).status_code == 401

    r = anon.post("/api/login", json={"nome": nome, "password": sbagliata})
    assert r.status_code == 429
    assert "riprova fra" in r.get_json()["error"]


def test_il_freno_non_tocca_chi_sa_la_password(anon):
    """Qualche errore sotto la soglia non deve impedire l'accesso corretto:
    sbagliare la password due volte capita a tutti."""
    for _ in range(houses.TENTATIVI_LIBERI - 1):
        anon.post("/api/login", json={"nome": "Casa Test", "password": "quasi"})

    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 200


def test_l_accesso_riuscito_azzera_i_tentativi_sbagliati(anon):
    """Senza azzerare, gli errori si sommerebbero fra un accesso e l'altro e
    dopo qualche giorno anche chi entra sempre correttamente troverebbe un freno."""
    # sotto la soglia: non si viene bloccati, ma il contatore esiste
    for _ in range(houses.TENTATIVI_LIBERI - 1):
        anon.post("/api/login", json={"nome": "Casa Test", "password": "no"})
    assert anon.post("/api/login", json={"nome": "Casa Test",
                                         "password": PASSWORD_TEST}).status_code == 200

    # azzerato: i prossimi tentativi sono di nuovo liberi. Se non fosse stato
    # azzerato, il terzo risponderebbe 429 invece di 401
    for _ in range(houses.TENTATIVI_LIBERI):
        r = anon.post("/api/login", json={"nome": "Casa Test", "password": "no"})
        assert r.status_code == 401, r.status_code


def test_cambiare_il_nome_non_aggira_l_attesa_ma_solo_il_contatore_per_casa(anon):
    """Chi prova nomi diversi non deve poter continuare all'infinito: l'attesa
    per l'indirizzo ferma anche lui, che sia dietro un tunnel o meno."""
    for _ in range(houses.TENTATIVI_LIBERI + 1):
        anon.post("/api/login", json={"nome": "Casa Sbagliata", "password": "x"})

    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 429


def test_l_attesa_cresce_e_ha_un_tetto():
    """Raddoppiare senza limite diventerebbe un blocco di giorni: c'e' un tetto."""
    adesso = 1000.0
    attese = []
    for i in range(houses.TENTATIVI_LIBERI + 6):
        houses.segnala_fallimento("9.9.9.9", "casa", adesso=adesso + i)
        attese.append(houses.attesa_accesso("9.9.9.9", "casa", adesso=adesso + i))
    # i primi due errori restano liberi, il terzo fa gia' aspettare
    assert attese[0] == 0
    assert attese[1] == 0
    assert attese[2] == houses.ATTESA_BASE
    # e poi raddoppia, fino al tetto
    assert attese[3] > attese[2]
    assert attese[-1] <= houses.ATTESA_MASSIMA


def test_il_contatore_si_dimentica_col_tempo():
    """Una password sbagliata di sera non deve far aspettare la mattina dopo."""
    adesso = 1000.0
    for _ in range(houses.TENTATIVI_LIBERI + 3):
        houses.segnala_fallimento("8.8.8.8", "casa", adesso=adesso)
    assert houses.attesa_accesso("8.8.8.8", "casa", adesso=adesso) > 0

    poi = adesso + houses.DIMENTICARE_DOPO + 1
    assert houses.attesa_accesso("8.8.8.8", "casa", adesso=poi) == 0



# ---------------------------------------------------------------- sveglia
# La parola di sveglia in stile "hey Google": il microfono resta aperto e il
# comando parte solo quando si chiama l'assistente. La comprensione sta sul
# server, cosi' si verifica qui senza microfono.

def test_la_sveglia_si_riconosce_all_inizio():
    """Il caso normale: si chiama l'assistente e si dice il comando."""
    svegliato, resto = voice.sveglia("maggiordomo aggiungi il latte in dispensa")
    assert svegliato
    assert resto == "aggiungi il latte in dispensa"


def test_la_sveglia_tollera_i_saluti_e_le_storpiature():
    """Il riconoscimento vocale sbaglia i nomi propri, e "maggiordomo" non e'
    una parola comune: se non si accettano le forme vicine, l'assistente
    sembra sordo proprio mentre lo si chiama."""
    for frase in ("hey maggiordomo metti il sale",
                  "ehi maggiordomo, metti il sale",
                  "ok magiordomo metti il sale",
                  "ciao maggiordomo metti il sale"):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == "metti il sale", frase


def test_la_sveglia_vale_solo_all_inizio_della_frase():
    """Chi parla d'altro non deve far partire un comando: la sveglia e'
    l'invocazione, non una parola qualsiasi della frase."""
    for frase in ("il maggiordomo prepara la cena",
                  "chiama il maggiordomo",
                  "metti il maggiordomo nella lista"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase


def _deve_accendere_js(client, casi):
    """Esegue `deveAccendereDaSolo` sul codice vero.

    E' pura apposta: decide se il microfono si apre da solo, e una regola cosi'
    non va provata con permessi finti e un microfono vero attorno.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function deveAccendereDaSolo")
    fine = js.index("\n}\n", inizio) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def test_hey_gg_accensione_automatica_solo_se_gia_concessa(client):
    """Il microfono si apre da solo solo quando tutte e tre le condizioni ci sono.
    Ognuna da sola non basta, ed e' quello che questo test fissa: se ne cadesse
    una, l'app aprirebbe il microfono senza permesso o contro la volonta'."""
    d = _deve_accendere_js(client, """{
      tutte: deveAccendereDaSolo('1', 'granted', true),
      maiAcceso: deveAccendereDaSolo('0', 'granted', true),
      maiAccesoNulla: deveAccendereDaSolo(null, 'granted', true),
      spentoDallUtente: deveAccendereDaSolo('0', 'granted', true),
      permessoDaChiedere: deveAccendereDaSolo('1', 'prompt', true),
      permessoNegato: deveAccendereDaSolo('1', 'denied', true),
      statoIgnoto: deveAccendereDaSolo('1', '', true),
      senzaChiave: deveAccendereDaSolo('1', 'granted', false)
    }""")
    assert d["tutte"] is True
    for caso in ("maiAcceso", "maiAccesoNulla", "spentoDallUtente",
                 "permessoDaChiedere", "permessoNegato", "statoIgnoto",
                 "senzaChiave"):
        assert d[caso] is False, caso


def _cenno_js(client, casi):
    """Esegue `cennoDiRicevuto` sul codice vero. Anche questa e' una regola pura:
    decide se l'assistente parla quando ha capito, e va provata come regola, non
    con un microfono e una voce attorno."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function cennoDiRicevuto")
    fine = js.index("\n}\n", inizio) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def test_il_cenno_di_ricevuto_solo_quando_c_e_un_comando(client):
    """Chi dice "Hey GG, metti il latte" aspetta un cenno: senza, fra la frase e
    l'esito passano i secondi della trascrizione e non sa se e' stato sentito.
    Ma il cenno vale **solo** per un comando: chiamare e basta riceve gia' la
    risposta di chiamata ("Sì."), e una frase ignorata non merita risposta,
    altrimenti l'ascolto continuo risponde a tutto e diventa insopportabile."""
    d = _cenno_js(client, """{
      comando: cennoDiRicevuto('esegui'),
      chiamata: cennoDiRicevuto('chiedi'),
      ignorata: cennoDiRicevuto('ignora'),
      niente: cennoDiRicevuto()
    }""")
    assert d["comando"].strip(), "un comando deve avere un cenno"
    assert d["chiamata"] == '', "chiamare e basta riceve gia' la risposta di chiamata"
    assert d["ignorata"] == '', "una frase ignorata non merita risposta"
    assert d["niente"] == ''


def test_la_chiamata_risponde_si(client):
    """Chiamato senza comando, l'assistente risponde "Sì." e basta: e' il
    riscontro breve che l'utente ha chiesto di sentire quando si attiva, prima
    del comando. Prima diceva "Dimmi.", piu' lungo e meno immediato.

    Si esegue la funzione pura, cosi' il test verifica **cosa** risponde, non la
    presenza di una stringa."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "cennoDiChiamata")
    d = _esegui_node(blocco + "\nconsole.log(JSON.stringify(cennoDiChiamata()));")
    assert d == "Sì."
    assert "dimmi" not in d.lower()


def _deve_accendere_accesso_js(client, casi):
    """Esegue `deveAccendereDopoAccesso` sul codice vero. Stessa idea
    dell'altra: la regola dell'avvio all'accesso si prova come regola."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function deveAccendereDopoAccesso")
    fine = js.index("\n}\n", inizio) + 3
    blocco = js[inizio:fine]
    prova = blocco + "\nconsole.log(JSON.stringify(" + casi + "));"
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def test_hey_gg_ascolto_parte_all_accesso(client):
    """Entrando, l'ascolto parte subito, senza doverlo accendere a mano: il click
    su "Entra" e' il gesto che il browser pretende. Un valore assente e' una
    prima volta, e all'accesso parte; solo uno spegnimento esplicito lo tiene
    spento. Senza la chiave non parte, perche' la trascrizione la farebbe il
    browser e li' l'avvio da solo non e' affidabile."""
    d = _deve_accendere_accesso_js(client, """{
      primaVolta: deveAccendereDopoAccesso(null, true),
      giaAcceso: deveAccendereDopoAccesso('1', true),
      spentoDallUtente: deveAccendereDopoAccesso('0', true),
      senzaChiave: deveAccendereDopoAccesso('1', false),
      senzaChiavePrimaVolta: deveAccendereDopoAccesso(null, false)
    }""")
    assert d["primaVolta"] is True, "all'accesso la prima volta deve partire"
    assert d["giaAcceso"] is True
    assert d["spentoDallUtente"] is False, "chi l'ha spento non se lo ritrova acceso"
    assert d["senzaChiave"] is False
    assert d["senzaChiavePrimaVolta"] is False


def test_hey_gg_sveglia_l_assistente():
    """Il secondo modo di chiamare, "Hey GG". Le forme accettate non sono
    indovinate: sono quelle che il trascrittore di Azure rende davvero, misurate
    sintetizzando la frase. Se si accettasse solo la forma scritta "hey gg",
    l'assistente non risponderebbe mai a chi lo chiama a voce."""
    for frase, comando in (
        ("Ai giorni metti il latte nella spesa", "metti il latte nella spesa"),
        ("E i giorni aggiungi due chili di farina", "aggiungi due chili di farina"),
        ("Ai GG metti il latte", "metti il latte"),
        ("Ehi Gigi, metti il latte", "metti il latte"),
        ("Ok Gigi metti il latte", "metti il latte"),
        ("Ciao Gigi metti il latte", "metti il latte"),
        ("Aigigi metti il latte", "metti il latte"),
        ("Giorni, che cosa c'e' in dispensa", "che cosa c'e' in dispensa"),
        # queste sono uscite da `misura_sveglia.py`, non dalla fantasia: sono le
        # forme che il trascrittore rende per "Hey Gi Gi" e per "Ehi GG"
        ("Ai Gigi, metti il latte", "metti il latte"),
        ("Ciao giorni, metti il latte", "metti il latte"),
        ("E i, maggiordomo, metti il latte", "metti il latte"),
        # dette in fretta, il riconoscitore non sente due "gi": sente una parola
        # sola. "Aigi", "Eiji", "Ai g", "AIG", "Aili Gigi" sono tutte in
        # `misura_sveglia.py`, e senza di loro la chiamata resta senza risposta
        ("Aigi, metti il latte", "metti il latte"),
        ("Eiji, metti il latte", "metti il latte"),
        ("Eigi, metti il latte", "metti il latte"),
        ("Aige, metti il latte", "metti il latte"),
        ("Ai g metti il latte", "metti il latte"),
        ("AIG, metti il latte", "metti il latte"),
        ("Aili Gigi, metti il latte", "metti il latte"),
        ("Egiggi, metti il latte", "metti il latte"),
    ):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == comando, frase


def test_hey_gg_da_solo_chiama_senza_comando():
    """Chiamato e basta: si risponde "Dimmi." e si aspetta. Il resto vuoto e'
    quello che dice al ciclo di non eseguire nulla."""
    svegliato, resto = voice.sveglia("Ai giorni")
    assert svegliato
    assert resto == ""


def test_hey_gg_non_sveglia_il_discorso_di_casa():
    """L'ancora all'inizio e' cio' che separa un richiamo dal discorso: "il nonno
    Gigi arriva alle otto" non deve accendere l'assistente, altrimenti in cucina
    si eseguono le chiacchiere."""
    for frase in ("il nonno Gigi arriva alle otto",
                  "metti il latte nella spesa",
                  "oggi il tempo e' bello",
                  "il maggiordomo prepara la cena",
                  "chiama Gigi per favore",
                  # forme brevi ("g", "gi", "aig") accettate per la sveglia: qui
                  # non sono all'inizio, e non devono accendere nulla. E' il
                  # confine che rende sicure le forme corte, e va tenuto stretto
                  "giro le pulizie",
                  "gita fuori porta",
                  "giornale sul tavolo",
                  "gesso",
                  "gelato in freezer",
                  "aiuto in cucina",
                  "e i piatti sono pronti"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase


def test_hey_gg_vale_anche_scritto(client):
    """La stessa frase vale scritta a mano nel campo di testo, non solo detta:
    un modo solo per tutti e due i canali."""
    r = client.post("/api/voice", json={"text": "Ai giorni metti il latte nella spesa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["intent"] == "shopping_add"
    assert d["name"] == "latte"


def test_senza_sveglia_il_testo_resta_intatto():
    """Fuori dall'ascolto continuo la sveglia non deve toccare il comando:
    "metti il latte" resta quello che era."""
    svegliato, resto = voice.sveglia("metti il latte nella spesa")
    assert not svegliato
    assert resto == "metti il latte nella spesa"


def test_la_sveglia_sente_anche_quando_il_trascrittore_mette_l_articolo():
    """Il difetto vero visto dal telefono: "Ehi maggiordomo" torna dal
    trascrittore come **"E il maggiordomo"** (misurato con `misura_sveglia.py` su
    Elsa; Isabella e Diego rendono "E i, maggiordomo"), e la sveglia non
    scattava. L'app rispondeva "Non ho eseguito" o taceva, sembrando sorda
    proprio mentre la si chiamava.

    Le forme qui sotto non sono inventate: sono quelle uscite dalla misurazione.
    L'articolo da solo non deve bastare, altrimenti "il maggiordomo prepara la
    cena" tornerebbe a essere un ordine."""
    for frase, comando in (
        ("E il maggiordomo, metti il latte?", "metti il latte"),
        ("E il maggiordomo aggiungi il pane", "aggiungi il pane"),
        ("E il maggiordomo?", ""),
        ("E i, maggiordomo, metti il latte", "metti il latte"),
        ("E la maggiordomo metti il sale", "metti il sale"),
    ):
        svegliato, resto = voice.sveglia(frase)
        assert svegliato, frase
        assert resto == comando, frase
    # e l'articolo senza esordio **non** sveglia: e' il confine che tiene fuori
    # le frasi di casa, dove "il maggiordomo" e' il soggetto, non una chiamata
    for frase in ("Il maggiordomo, metti il latte", "la maggiordomo prepara la cena"):
        svegliato, _ = voice.sveglia(frase)
        assert not svegliato, frase


def test_la_sveglia_si_toglie_anche_dal_comando_scritto(client):
    """Il comando "maggiordomo aggiungi il latte" vale anche scritto a mano nel
    campo di testo, non solo detto a voce: la stessa frase in tutti e due i modi."""
    r = client.post("/api/voice", json={"text": "maggiordomo aggiungi il latte in dispensa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["intent"] == "pantry_add"
    assert d["name"] == "latte"


def test_l_endpoint_sveglia_non_esegue_il_comando(client):
    """In ascolto continuo si sentono anche le frasi che non c'entrano: l'endpoint
    dice solo se era per l'app. Eseguirlo scriverebbe in dispensa ogni frase
    detta in cucina."""
    r = client.post("/api/voce/sveglia", json={"text": "maggiordomo aggiungi il latte in dispensa"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["sveglia"] is True
    assert d["resto"] == "aggiungi il latte in dispensa"
    # niente e' stato eseguito: la dispensa e' vuota
    assert client.get("/api/pantry").get_json() == []


def test_l_endpoint_sveglia_richiede_accesso(anon):
    r = anon.post("/api/voce/sveglia", json={"text": "maggiordomo aggiungi il latte"})
    assert r.status_code == 401


def test_l_ascolto_dice_se_la_frase_conteneva_la_sveglia(client, monkeypatch):
    """La trascrizione e il riconoscimento della sveglia viaggiano insieme: e' la
    stessa comprensione, e il client non deve indovinare da solo."""
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda audio, **k: "maggiordomo c'e' il latte?")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.status_code == 200
    d = r.get_json()
    assert d["sveglia"] is True
    # la punteggiatura non serve a un comando: e' la stessa normalizzazione di
    # `parse`, ed e' il motivo per cui il resto non porta il punto interrogativo
    assert d["resto"] == "c'e' il latte"


def test_l_ascolto_di_una_frase_comune_non_sveglia(client, monkeypatch):
    _con_chiave(monkeypatch)
    monkeypatch.setattr(voce_cloud, "trascrivi", lambda a, **k: "che bella giornata oggi")
    r = client.post("/api/voce/ascolta", data=b"\x00" * 100, content_type="audio/wav")
    assert r.get_json()["sveglia"] is False


# ---------------------------------------------------------------- chiave
# Difetti trovati attorno alla lettura della chiave: il file puo' contenere la
# chiave ma non essere il primo che si incontra, e la versione precedente si
# fermava li', lasciando la voce meccanica senza che si capisse perche'.

def test_la_chiave_si_cerca_anche_nel_secondo_file(tmp_path, monkeypatch):
    """Un `segreto.bat` di Windows copiato accanto al server, senza chiave, non
    deve far ignorare il `segreto.sh` che la chiave ce l'ha: e' il caso di chi
    passa dal PC al server, e la voce tornava meccanica senza motivo."""
    (tmp_path / "segreto.bat").write_text("@echo off\nREM file di Windows, senza chiave\n")
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_KEY='ChiaveNelSecondo'\n")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveNelSecondo"


def test_la_chiave_nel_file_dopo_uno_vuoto(tmp_path, monkeypatch):
    """Stessa cosa dal lato opposto: il primo file c'e' ma non dice niente, e la
    lettura deve proseguire invece di fermarsi."""
    (tmp_path / "segreto.sh").write_text("# solo commenti\n")
    (tmp_path / "segreto.bat").write_text('set "AZURE_SPEECH_KEY=DalBat"\n')
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "DalBat"


# ------------------------------------------------------- ascolto continuo
# La funzione in stile "hey Google": il microfono resta aperto e i comandi
# partono alla parola di sveglia. E' lato client e non si puo' premere in un
# test, ma le garanzie che non devono rompersi si possono verificare.

def test_l_ascolto_continuo_esiste_e_si_accende_dal_pannello(client):
    """La funzione deve essere raggiungibile: un pulsante nel pannello e il
    ciclo che lo mette in pratica."""
    js = client.get("/static/app.js").get_data(as_text=True)
    html = client.get("/").get_data(as_text=True)
    assert 'id="voice-sempre"' in html
    assert "function avviaAscoltoContinuo()" in js
    assert "function cicloAscoltoContinuo()" in js
    assert "function fermaAscoltoContinuo()" in js


def _estrai_funzione_js(js, nome):
    """Ritaglia una `function NOME(...) { ... }` con parentesi bilanciate.

    Serve a eseguire il codice vero con node invece di leggerne le stringhe: un
    test sulle stringhe non si accorge se la funzione fa la cosa sbagliata."""
    import re
    m = re.search(r'(?:async\s+)?function ' + nome + r'\s*\(', js)
    assert m, f"non trovo la funzione {nome}"
    inizio = m.start()
    i = js.index('(', m.start())
    par = 0
    while i < len(js):
        if js[i] == '(':
            par += 1
        elif js[i] == ')':
            par -= 1
            if par == 0:
                i += 1
                break
        i += 1
    brace = js.index('{', i)
    depth = 0
    j = brace
    while j < len(js):
        if js[j] == '{':
            depth += 1
        elif js[j] == '}':
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    return js[inizio:j]


def _esegui_node(prova):
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def _parlaCloud_e_misura(client):
    """Esegue `parlaCloud` **vera** con un `Audio` finto ma fedele: `play()`
    risolve all'inizio, l'evento 'ended' arriva dopo. Restituisce l'ordine degli
    eventi, per vedere quando la promessa si chiude."""
    js = client.get("/static/app.js").get_data(as_text=True)
    # `parlaCloud` prende l'audio da `audioCloud` (separata per poter preparare le
    # frasi fisse in anticipo): si estraggono entrambe, cosi' il test esegue il
    # percorso vero e non uno stub che potrebbe divergere
    codice = (_estrai_funzione_js(js, "audioCloud")
              + _estrai_funzione_js(js, "parlaCloud"))
    preludio = """
const log = [];
const CLOUD_CACHE_MAX = 40;
function voceStato() {}
let voceCloud = { disponibile: true, maxCaratteri: 600,
                  sentite: new Map([['it-IT-IsabellaNeural|Ciao.', {}]]) };
function voceCloudScelta() { return 'it-IT-IsabellaNeural'; }
global.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };
class Audio {
  play() { log.push('play'); return Promise.resolve(); }
  addEventListener(ev, fn) {
    if (ev === 'ended') setTimeout(() => { log.push('ended'); fn(); }, 40);
  }
}
"""
    prova = (preludio + codice
             + "\nparlaCloud('Ciao.').then(() => log.push('risolta'));"
             + "\nsetTimeout(() => console.log(JSON.stringify(log)), 300);")
    return _esegui_node(prova)


def _parla_e_misura(client, testo):
    """Esegue `parla` **vera** con una `parlaCloud` finta che suona una frase per
    volta, per verificare che le frasi vadano in fila e che il segnale di
    silenzio arrivi solo dopo l'ultima."""
    js = client.get("/static/app.js").get_data(as_text=True)
    pezzi = [_estrai_funzione_js(js, n)
             for n in ("spezzaInFrasi", "avvisaFineParlato", "parla")]
    preludio = """
const log = [];
function voceStato() {}
function $() { return { checked: true }; }
function cloudAttivo() { return true; }
function parlaTesto() {}
let voce = { aFineParlato: () => log.push('FINE-PARLATO') };
function parlaCloud(frase) {
  return new Promise((risolvi) => {
    log.push('suona:' + frase);
    setTimeout(() => { log.push('fine:suona:' + frase); risolvi(true); }, 40);
  });
}
"""
    prova = (preludio + "\n".join(pezzi)
             + "\nparla(" + json.dumps(testo) + ");"
             + "\nsetTimeout(() => console.log(JSON.stringify(log)), 800);")
    return _esegui_node(prova)



def test_l_ascolto_continuo_non_risente_se_stesso(client):
    """Il difetto che rompe la funzione: mentre l'assistente parla, il microfono
    lo sente, riconosce la propria voce come comando e riparte da solo. La pausa
    `sospeso` e il segnale di "fine parlato" esistono per questo."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "sospeso" in js
    assert "function avvisaFineParlato()" in js
    assert "function riprendiDopoLaVoce(" in js
    # la voce del browser segnala la fine con onend dell'ultima frase
    assert "if (ultima) u.onend = avvisaFineParlato;" in js
    # la voce neurale segnala la fine quando l'audio **termina**, non quando parte
    assert "audio.addEventListener('ended', () => finito(true)" in js
    # e non deve piu' segnalarla all'avvio della riproduzione (il difetto)
    assert "await audio.play();" not in js


def test_la_voce_neurale_avvisa_la_fine_quando_l_audio_finisce(client):
    """Il difetto che incastrava l'ascolto dopo il primo comando.

    `play()` risolve **all'inizio** dell'audio, quindi la promessa di
    `parlaCloud` si chiudeva subito: il segnale di "fine parlato" partiva mentre
    Azure stava ancora parlando, il microfono riprendeva sopra la voce,
    l'assistente si risentiva e il ciclo si bloccava. Si esegue la funzione vera
    con un `Audio` finto ma fedele (`play()` subito, 'ended' dopo) e si guarda
    **quando** la promessa si chiude."""
    ordine = _parlaCloud_e_misura(client)
    # l'audio comincia, e solo dopo l'evento 'ended' la promessa si chiude
    assert ordine.index("play") < ordine.index("ended") < ordine.index("risolta")


def test_le_frasi_della_voce_neurale_si_dicono_in_fila(client):
    """Le frasi non si sovrappongono: la voce neurale suona un audio per volta, e
    in parallelo la seconda mangerebbe la prima. Il segnale di silenzio arriva
    **solo** dopo l'ultima, altrimenti l'ascolto continuo ripartirebbe a meta'
    discorso."""
    ordine = _parla_e_misura(client, "Fatto. Il latte e' in lista.")
    assert ordine.count("FINE-PARLATO") == 1, "un solo segnale di fine, non uno per frase"
    assert ordine.index("fine:suona:Fatto.") < ordine.index("suona:Il latte e' in lista.")
    assert (ordine.index("suona:Il latte e' in lista.")
            < ordine.index("fine:suona:Il latte e' in lista."))
    assert ordine[-1] == "FINE-PARLATO", "il silenzio si segnala dopo l'ultima frase"



def test_l_ascolto_continuo_non_si_incastra(client):
    """Se il browser non dice mai che la voce ha finito, il ciclo deve ripartire
    lo stesso: senza il tetto, l'ascolto resterebbe fermo con l'aria di acceso."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "TETTO_VOCE_MS" in js
    assert "voce.tempoVoce = setTimeout(" in js


def test_chiudere_il_pannello_non_spegne_l_ascolto_continuo(client):
    """Il modo d'uso e' proprio a pannello chiuso - si cucina e si parla - e
    fermare il microfono li' renderebbe la funzione inutile quando serve."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function chiudiVoce()" in js
    inizio = js.index("function chiudiVoce()")
    corpo = js[inizio:inizio + 700]
    assert "ascoltoContinuo.continuo" in corpo


# ------------------------------------------- password della casa nella FAQ
def test_la_password_della_casa_si_cambia_dalla_faq(client):
    """Cambiare la password e' un'operazione rara ma necessaria: deve stare
    nell'app, non solo in uno script da riga di comando. Il modulo chiede la
    vecchia e fa ripetere la nuova, e chiama la rotta vera."""
    html = client.get("/static/index.html").get_data(as_text=True)
    inizio = html.index('id="tab-faq"')
    fine = html.index('</main>')
    faq = html[inizio:fine]
    for pezzo in ('id="pw-attuale"', 'id="pw-nuova"', 'id="pw-ripeti"', 'id="pw-salva"'):
        assert pezzo in faq, pezzo
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/houses/password" in js
    assert "method: 'PUT'" in js


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


def test_una_area_sbagliata_lo_dice_invece_di_sembrare_un_guasto_di_rete(monkeypatch):
    """Il caso riferito dal desktop: "Servizio vocale non raggiungibile:
    [Errno 11001] getaddrinfo failed". L'indirizzo del servizio contiene l'area
    (`italynorth.tts.speech.microsoft.com`), quindi un refuso **non ha un nome da
    risolvere**: l'errore che ne segue parla di rete e non dice cosa correggere.

    Si prova con un refuso tipico e si guarda che il messaggio nomini l'area
    sbagliata e la variabile da controllare, invece di "getaddrinfo"."""
    import voce_cloud
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "italynorht")   # n e h invertite
    voce_cloud._FILE_LETTI = True   # niente file segreto: comanda l'ambiente
    with pytest.raises(voce_cloud.ErroreVoce) as errore:
        voce_cloud.sintetizza("ciao", "it-IT-ElsaNeural")
    messaggio = str(errore.value)
    assert "italynorht" in messaggio, messaggio
    assert "AZURE_SPEECH_REGION" in messaggio, messaggio
    # le aree vere passano: il controllo non deve fermare l'uso normale
    for area in ("italynorth", "westeurope", "eastus"):
        assert voce_cloud.area_valida(area), area
    for area in ("IT", "italia", "", "italynorht"):
        assert not voce_cloud.area_valida(area), area


def test_avvio_avvisa_se_l_area_non_esiste():
    """L'avvio diceva "voce neurale Azure attiva" anche con l'area sbagliata: chi
    legge quella riga va a cercare un guasto di rete che non c'e', mentre la
    causa e' un refuso. E' successo davvero: in `segreto.bat` era finita l'area
    "s" (la S della conferma scritta al posto sbagliato).

    Si esegue lo script con un'area inesistente e si guarda che NON dica "attiva"."""
    import os
    import subprocess
    ambiente = dict(os.environ)
    ambiente["AZURE_SPEECH_KEY"] = "chiave-finta"
    ambiente["AZURE_SPEECH_REGION"] = "s"
    esito = subprocess.run(["./avvia.sh", "status"], cwd=BASE_APP,
                           env=ambiente, capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    assert "NON attiva" in uscita, uscita
    assert "«s»" in uscita, uscita
    assert "AZURE_SPEECH_REGION" in uscita, uscita


def test_voce_bat_non_accetta_un_area_inventata(client):
    """`voce.bat` scrive `segreto.bat` e chiede l'area a mano: qualunque cosa si
    scriva finiva nel file, anche una lettera sola. Ora rifiuta un'area che non
    esiste e la richiede, cosi' il file non puo' piu' nascere sbagliato.

    Si guarda il file vero: la validazione c'e', e l'elenco e' quello di
    `voce_cloud` (due elenchi diversi divergerebbero)."""
    bat = open(f"{BASE_APP}/windows/voce.bat", encoding="utf-8").read()
    assert "non e' un'area Azure" in bat
    # almeno un'area vera e' nell'elenco di controllo
    assert "italynorth" in bat and "westeurope" in bat
    # e la scrittura del file avviene solo dopo il controllo
    pos_controllo = bat.index("non e' un'area Azure")
    pos_scrittura = bat.index("> \"segreto.bat\"")
    assert pos_controllo < pos_scrittura, "il controllo deve venire prima di salvare"


def test_si_vede_da_quale_file_viene_l_area(monkeypatch, tmp_path):
    """Il caso che fa perdere tempo: si corregge un file e l'errore resta, perche'
    il valore vero arriva da un altro posto. Su Windows `avvia.bat` chiama
    `windows\\segreto.bat`, che imposta l'**ambiente**: da li' in poi
    `segreto.txt` non viene nemmeno guardato.

    Qui si guarda che il valore dica la sua **provenienza** (il file esatto), cosi'
    si sa quale correggere."""
    import importlib
    import voce_cloud
    importlib.reload(voce_cloud)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    (tmp_path / "segreto.txt").write_text(
        "set \"AZURE_SPEECH_KEY=chiave-finta\"\nset \"AZURE_SPEECH_REGION=s\"\n",
        encoding="utf-8")
    voce_cloud._FILE_LETTI = False
    voce_cloud._ORIGINE.clear()
    voce_cloud.BASE_DIR = str(tmp_path)
    voce_cloud.DATA_DIR = str(tmp_path)

    assert voce_cloud.regione() == "s"
    assert voce_cloud.origine("AZURE_SPEECH_REGION") == str(tmp_path / "segreto.txt")
    # e il messaggio d'errore lo dice, cosi' non si corregge il file sbagliato
    with pytest.raises(voce_cloud.ErroreVoce) as errore:
        voce_cloud._controlla_area()
    assert "letta da" in str(errore.value), str(errore.value)

    # dall'ambiente invece lo dice: e' il caso di avvia.bat su Windows
    importlib.reload(voce_cloud)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "chiave-finta")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "s")
    voce_cloud._FILE_LETTI = True
    assert voce_cloud.origine("AZURE_SPEECH_REGION") == "ambiente"


def test_la_diagnosi_non_stampa_la_chiave():
    """La diagnostica serve a capire da dove viene un valore sbagliato, e si fa
    con qualcuno che guarda: la chiave **non** deve comparire. Si vedono le prime
    lettere e la lunghezza, che bastano a riconoscere un copia-incolla tronco."""
    import subprocess
    esito = subprocess.run(["./avvia.sh", "diagnosi"], cwd=BASE_APP,
                           capture_output=True, text=True)
    uscita = esito.stdout + esito.stderr
    import voce_cloud
    chiave = voce_cloud.chiave()
    if chiave:
        assert chiave not in uscita, "la diagnosi ha stampato la chiave intera"
    # ma la provenienza si vede
    assert "da:" in uscita
    assert "area valida:" in uscita


def test_ripara_voce_corregge_l_area_senza_toccare_la_chiave(tmp_path):
    """Il caso reale: `windows\\segreto.bat` contiene l'area `s`, la chiave e'
    probabilmente giusta. Il riparatore deve cambiare **solo** la riga dell'area:
    una riga scritta male rovinerebbe la chiave, e la chiave non si recupera.

    Si esegue il riparatore **vero** su file veri, e si controlla che la chiave
    resti identica e che `segreto.txt` — che in questo caso non comanda — non
    venga toccato."""
    import ripara_voce
    (tmp_path / "windows").mkdir()
    chiave = "D58nABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnop"
    bat = tmp_path / "windows" / "segreto.bat"
    bat.write_text(
        '@echo off\nREM Chiave della voce neurale. Generato da voce.bat.\n'
        f'set "AZURE_SPEECH_KEY={chiave}"\nset "AZURE_SPEECH_REGION=s"\n',
        encoding="utf-8")
    txt = tmp_path / "segreto.txt"
    txt.write_text(f"chiave: {chiave}\narea: germanywestcentral\n", encoding="utf-8")

    esito = ripara_voce.ripara(str(tmp_path), area="italynorth")

    assert esito == 0
    dopo = bat.read_text(encoding="utf-8")
    # la chiave e' rimasta identica, e l'area e' corretta
    assert chiave in dopo
    assert 'AZURE_SPEECH_REGION=italynorth' in dopo
    assert 'AZURE_SPEECH_REGION=s' not in dopo
    # segreto.txt non comanda (c'e' il .bat) e non viene toccato
    assert "germanywestcentral" in txt.read_text(encoding="utf-8")


def test_ripara_voce_non_tocca_niente_se_l_area_e_giusta(tmp_path):
    """Se l'area e' gia' valida non si scrive: riscrivere un file che contiene una
    chiave funzionante e' un rischio senza guadagno."""
    import ripara_voce
    bat = tmp_path / "windows"
    bat.mkdir()
    (bat / "segreto.bat").write_text(
        'set "AZURE_SPEECH_KEY=k"\nset "AZURE_SPEECH_REGION=westeurope"\n', encoding="utf-8")
    prima = (bat / "segreto.bat").read_text(encoding="utf-8")

    assert ripara_voce.ripara(str(tmp_path), area="italynorth") == 0
    assert (bat / "segreto.bat").read_text(encoding="utf-8") == prima, \
        "un'area valida non va toccata"


def test_ripara_voce_non_scrive_un_area_inventata(tmp_path):
    """Se l'area non e' valida non si scrive niente: meglio un errore chiaro che
    un file corretto con un altro valore sbagliato."""
    import ripara_voce
    (tmp_path / "windows").mkdir()
    bat = tmp_path / "windows" / "segreto.bat"
    bat.write_text('set "AZURE_SPEECH_KEY=k"\nset "AZURE_SPEECH_REGION=s"\n', encoding="utf-8")
    prima = bat.read_text(encoding="utf-8")

    assert ripara_voce.ripara(str(tmp_path), area="italia") == 1
    assert bat.read_text(encoding="utf-8") == prima


def test_windows_avvia_dietro_il_tunnel(client):
    """Su Windows l'app sta dietro Tailscale Funnel (o Cloudflare, o nginx):
    `avvia.bat` deve dirlo all'app, altrimenti vede l'indirizzo del tunnel al
    posto di quello di chi bussa e il freno ai tentativi conta tutti insieme.

    Dimenticarlo non rompe niente in modo visibile — l'app funziona — quindi si
    scoprirebbe solo dal sintomo sbagliato (qualcuno che aspetta senza motivo)."""
    bat = open(f"{BASE_APP}/windows/avvia.bat", encoding="utf-8").read()
    assert "DIETRO_PROXY=1" in bat, "avvia.bat non dichiara di stare dietro un proxy"
    # e la funzione che lo legge esiste davvero lato server
    app_py = open(f"{BASE_APP}/app.py", encoding="utf-8").read()
    assert "DIETRO_PROXY" in app_py and "ProxyFix" in app_py


def test_il_pulsante_voce_c_e_su_ogni_pagina(client):
    """Il pulsante del microfono deve restare raggiungibile da ogni area: serve
    proprio quando non si possono usare le mani, e un'area senza pulsante e' una
    parte dell'app da cui la voce sparisce senza che nessuno se ne accorga.

    Si esegue `apriSezione` **vera** con un DOM finto che registra le classi del
    pulsante: un test sulle stringhe non si accorgerebbe se una delle quattro
    aree lo nascondesse."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "apriSezione")
    preludio = """
const classi = {};
function elemento(id) {
  classi[id] = classi[id] || new Set();
  return {
    classList: {
      add(c) { classi[id].add(c); },
      remove(c) { classi[id].delete(c); },
      toggle(c, v) { if (v) classi[id].add(c); else classi[id].delete(c); },
      contains(c) { return classi[id].has(c); },
    },
    dataset: {}, innerHTML: '', textContent: '',
  };
}
const nodi = {};
function $(sel) {
  const id = sel.replace(/^#/, '');
  nodi[id] = nodi[id] || elemento(id);
  return nodi[id];
}
function $$() { return []; }
function switchTab() {}
function avviaProfiloSeServe() {}
function esc(t) { return t; }
const SEZIONI = {
  cucina:   { titolo: 'Cucina',   icona: '/static/icons/icona.svg', prima: 'plan' },
  igiene:   { titolo: 'Igiene',   prima: 'igiene' },
  progetti: { titolo: 'Progetti', prima: 'progetti' },
  faq:      { titolo: 'FAQ',      prima: 'faq' },
};
global.window = { scrollTo() {} };
global.document = { title: '' };
"""
    prove = "\n".join(
        f"apriSezione({nome!r}); esiti[{nome!r}] = !classi['mic'].has('hidden');"
        for nome in ("cucina", "igiene", "progetti", "faq"))
    prova = (preludio + blocco + "\nconst esiti = {};\n" + prove
             + "\nconsole.log(JSON.stringify(esiti));")
    esiti = _esegui_node(prova)
    # il pulsante nacque nascosto (`class="mic hidden"`): se resta `hidden` in
    # un'area, da quell'area la voce non si puo' aprire
    for nome, visibile in esiti.items():
        assert visibile, f"il pulsante voce resta nascosto in {nome}"


def test_la_frase_sentita_si_vede_anche_col_pannello_chiuso(client):
    """Con l'ascolto continuo acceso il pannello e' chiuso, e `#voice-heard` sta
    dentro di esso: la frase trascritta e l'esito non si vedono. Chi parla col
    pannello chiuso vede solo il pulsante colorato, e se l'assistente non risponde
    (ascolto continuo: tace sul discorso di casa) sembra che non abbia sentito.

    `mostraFuori` scrive in una riga **fuori** dal pannello. Si esegue la funzione
    vera con node: a pannello chiuso la riga si vede, a pannello aperto no
    (altrimenti si raddoppierebbe)."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "mostraFuori")
    preludio = """
const stato = { nascosto: true, testo: '', classi: '' };
let pannelloChiuso = true;
function $(sel) {
  if (sel === '#voice-fuori') {
    return {
      set hidden(v) { stato.nascosto = v; }, get hidden() { return stato.nascosto; },
      set textContent(v) { stato.testo = v; }, get textContent() { return stato.testo; },
      set className(v) { stato.classi = v; }, get className() { return stato.classi; },
    };
  }
  return { classList: { contains: () => pannelloChiuso } };
}
"""
    prova = preludio + blocco + """
mostraFuori('Ti ho sentito, dimmi.', 'ok');
const chiuso = { nascosto: stato.nascosto, testo: stato.testo, classi: stato.classi };
pannelloChiuso = false;   // pannello aperto: li' c'e' gia' #voice-heard
mostraFuori('Ho sentito: «metti il latte»', 'ok');
const aperto = { nascosto: stato.nascosto };
console.log(JSON.stringify({ chiuso, aperto }));
"""
    d = _esegui_node(prova)
    assert d["chiuso"]["nascosto"] is False, "col pannello chiuso la riga deve vedersi"
    assert "Ti ho sentito" in d["chiuso"]["testo"]
    assert "ok" in d["chiuso"]["classi"]
    assert d["aperto"]["nascosto"] is True, "col pannello aperto la riga non si raddoppia"


def test_il_comando_parte_subito_senza_aspettare_la_voce(client):
    """La latenza riferita: il comando partiva solo **dopo** la fine di
    "Comandi.", quindi l'esecuzione restava ferma per tutta la voce — e col
    telefono (trascrizione + voce neurale) sembrava che non eseguisse affatto.

    Si esegue `eseguiComandoContinuo` **vera** con node: il comando dev'essere
    invocato **subito**, prima che la voce finisca, e le due frasi (cenno, esito)
    devono restare in fila, senza sovrapporsi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = (_estrai_funzione_js(js, "confermaVoce")
              + _estrai_funzione_js(js, "tettoVoceMs")
              + _estrai_funzione_js(js, "eseguiComandoContinuo"))
    preludio = """
const ordine = [];
let risolviCenno, risolviEsito, risolviCmd;
function parlaEAttendi(f) {
  ordine.push('parla:' + f);
  return new Promise((r) => { if (f === 'Comandi.') risolviCenno = r; else risolviEsito = r; });
}
function riprendiDopoLaVoce() { return () => ordine.push('ripartito'); }
function eseguiComando(c, o) {
  ordine.push('esegui:' + c + ':parla=' + (o && o.parla));
  return new Promise((r) => { risolviCmd = r; });
}
function cennoDiRicevuto() { return 'Comandi.'; }
// piccolo apposta: il tetto vero segue la frase, e nel banco non serve — anzi,
// con quello vero il processo node resterebbe vivo a ogni esecuzione dei test
const TETTO_VOCE_MS = 30;
let voce = {};
function $() { return { checked: true }; }
"""
    prova = preludio + blocco + """
(async () => {
  const attendi = () => new Promise((r) => setTimeout(r, 0));
  const p = eseguiComandoContinuo('metti il latte', () => {});
  const subito = ordine.slice();   // prima che qualunque voce sia finita
  risolviCenno && risolviCenno(); await attendi();
  risolviCmd({ message: 'Fatto.' }); await attendi();
  risolviEsito && risolviEsito(); await p;
  console.log(JSON.stringify({ subito, dopo: ordine }));
})();
"""
    d = _esegui_node(prova)
    # il comando e' la **prima** cosa che succede: non aspetta la voce
    assert d["subito"][0] == "esegui:metti il latte:parla=false", d["subito"]
    # l'esecuzione non parla da sola (l'esito lo dice `eseguiComandoContinuo`)
    assert "esegui:metti il latte:parla=false" in d["subito"]
    # e le due frasi si dicono in fila: prima il cenno, poi l'esito
    parlate = [v for v in d["dopo"] if v.startswith("parla:")]
    assert parlate == ["parla:Comandi.", "parla:Fatto."], parlate


def test_le_frasi_fisse_si_preparano_in_anticipo(client):
    """La latenza che si nota di piu' e' il silenzio dopo aver parlato: ogni
    "Comandi." costava un giro di rete **prima** di sentirsi. Le frasi fisse sono
    sempre le stesse, quindi si scaricano in anticipo, senza riprodurle.

    Si esegue la funzione **vera** con node: deve chiedere al server proprio le
    due frasi fisse, e **non** creare nessun `Audio` (preparare non e' parlare)."""
    js = client.get("/static/app.js").get_data(as_text=True)
    codice = (_estrai_funzione_js(js, "audioCloud")
              + _estrai_funzione_js(js, "preriscaldaFrasiFisse"))
    preludio = """
const CLOUD_CACHE_MAX = 40;
const chieste = [];
let audioCreati = 0;
function voceStato() {}
function voceCloudScelta() { return 'it-IT-IsabellaNeural'; }
let voceCloud = { disponibile: true, maxCaratteri: 600, sentite: new Map() };
global.fetch = (url, opzioni) => {
  chieste.push(JSON.parse(opzioni.body).text);
  return Promise.resolve({ ok: true, blob: () => Promise.resolve({}) });
};
class Audio { constructor() { audioCreati++; } }
"""
    prova = (preludio + codice + """
preriscaldaFrasiFisse();
setTimeout(() => console.log(JSON.stringify({ chieste, audioCreati })), 100);
""")
    d = _esegui_node(prova)
    assert sorted(d["chieste"]) == ["Comandi.", "Sì."], d["chieste"]
    assert d["audioCreati"] == 0, "preparare l'audio non deve farlo suonare"


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


def test_il_tetto_della_voce_non_lascia_muti_per_venti_secondi(client):
    """Il difetto riferito: dopo il "Si." l'assistente torna muto e non trascrive
    i comandi. La causa e' il tetto dell'attesa di "fine parlato": se la sintesi
    non annuncia la fine (succede), la pausa durava fino a 20 s **fissi**, e in
    quei venti secondi il microfono resta chiuso.

    Si esegue `tettoVoceMs` **vera**: il tetto dev'essere proporzionale alla
    frase, cosi' una parola come "Si." non fa aspettare venti secondi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "tettoVoceMs")
    d = _esegui_node(blocco + """
console.log(JSON.stringify({
  si: tettoVoceMs('Si.'),
  comandi: tettoVoceMs('Comandi.'),
  lunga: tettoVoceMs('Fatto. Farina in dispensa, 2 kg.'),
}));""")
    # una parola breve: pochi secondi, non venti
    assert d["si"] <= 3000, d
    assert d["comandi"] <= 3500, d
    # una conferma lunga ha piu' tempo, ma sempre sotto il vecchio tetto fisso
    assert d["lunga"] > d["si"]
    assert d["lunga"] <= 12000


def test_il_microfono_che_non_risponde_non_blocca_il_ciclo(client):
    """Un'altra causa del "dopo il Si. torna muto": `getUserMedia` puo' non
    risolversi (su Android al secondo giro il permesso c'e' gia', e la promessa
    resta appesa). Senza un limite, il ciclo non parte e il sorvegliante lo
    riavvia solo dopo 25 s.

    Si esegue `ascoltaSulServer` **vera** con un `getUserMedia` che non risponde
    mai: l'esito dev'essere `ritenta`, non un silenzio."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "ascoltaSulServer")
    preludio = """
function registra() {}
function ampiezza() { return 0; }
function wavDaCampioni() { return {}; }
function aSediciKhz(c) { return c; }
function voceStato() {}
function $() { return { classList: { add() {}, remove() {} }, hidden: false }; }
let voce = { registratore: null, attivo: false };
const ASCOLTO_BLOCCO = 4096, ASCOLTO_CAMPIONI = 16000;
const ASCOLTO_FINE_MS = 800, ASCOLTO_ATTESA_MS = 4000, ASCOLTO_MAX_MS = 12000;
const ASCOLTO_SILENZIO = 0.012;
class AudioContextFinto { constructor() { this.state = 'running'; this.sampleRate = 16000; } }
global.window = { AudioContext: AudioContextFinto };
Object.defineProperty(globalThis, 'navigator', {
  value: { mediaDevices: { getUserMedia: () => new Promise(() => {}) } },  // mai risolta
  configurable: true,
});
global.setTimeout = setTimeout;
"""
    prova = preludio + blocco + """
const t0 = Date.now();
const avviato = ascoltaSulServer((d) => {
  console.log(JSON.stringify({ esito: d, ms: Date.now() - t0, avviato }));
  process.exit(0);
});
setTimeout(() => { console.log(JSON.stringify({ esito: null })); process.exit(0); }, 9000);
"""
    d = _esegui_node(prova)
    assert d["esito"] and d["esito"].get("ritenta") is True, d
    assert d["ms"] < 8000, f"ha aspettato troppo: {d['ms']} ms"


def test_il_registro_dice_cosa_fa_l_assistente(client):
    """Il riscontro chiesto: l'assistente deve dire in trasparenza cosa fa. Si
    esegue `registra` **vera**: ogni passo finisce in una riga con l'ora e i
    millisecondi, le righe vecchie si buttano (non cresce all'infinito) e il
    pannello ha il contenitore dove scriverle."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "registra")
    preludio = """
const REGISTRO_MAX = 60;
let registroInizio = Date.now();
const figli = [];
const lista = {
  children: figli,
  get firstChild() { return figli[0]; },
  appendChild(li) { figli.push(li); },
  removeChild(li) { figli.splice(figli.indexOf(li), 1); },
  set scrollTop(v) {}, get scrollTop() { return 0; },
  get scrollHeight() { return 0; },
};
let conteggio = null;
const nodi = { 'voice-registro': lista,
               'voice-registro-n': { set textContent(v) { conteggio = v; } } };
function $(sel) { return nodi[sel.replace(/^#/, '')]; }
global.document = {
  createElement: () => ({
    className: '', children: [],
    appendChild(c) { this.children.push(c); },
  }),
  createTextNode: (t) => ({ testo: t }),
};
"""
    prova = preludio + blocco + """
for (let i = 0; i < 70; i++) registra('passo ' + i);
const righe = lista.children.length;
const testo = lista.children[lista.children.length - 1].children
  .map((c) => c.testo || '').join('');
console.log(JSON.stringify({ righe, conteggio, testo, orario: /\\d\\d:\\d\\d:\\d\\d/.test(lista.children[0].children[0].textContent || '') }));
"""
    d = _esegui_node(prova)
    assert d["righe"] == 60, "il registro non deve crescere all'infinito"
    assert d["conteggio"] == "(60)"
    assert "passo 69" in d["testo"]


def test_il_comando_pubblica_rifiuta_senza_credenziali():
    """Il push non deve mai partire senza un modo di autenticarsi: senza, git
    chiederebbe l'username a un terminale che non c'e' e il fallimento sembrerebbe
    un problema di rete. Si esegue lo script vero senza token e **senza chiave SSH**
    (il percorso della chiave si punta a un file inesistente), e si guarda che
    rifiuti dicendo cosa serve, invece di tentare un push a vuoto.

    E' il difetto che ha lasciato commit non pubblicati credendo che il token ci
    fosse: la variabile puo' esistere ma essere vuota, ed e' lo stesso."""
    import os
    import subprocess
    ambiente = dict(os.environ)
    for nome in ("GITHUB_TOKEN", "GH_TOKEN", "GIT_SSH_COMMAND"):
        ambiente.pop(nome, None)
    ambiente["MAGGIORDOMO_SSH_CONFIG"] = "/nonexistent/ssh/config"
    esito = subprocess.run(["./avvia.sh", "pubblica"], cwd=BASE_APP,
                           env=ambiente, capture_output=True, text=True)
    assert esito.returncode != 0, "senza credenziali il push non deve riuscire"
    assert "autenticarsi" in esito.stdout.lower()
    # e niente push a vuoto: la URL non deve comparire con credenziali dentro
    assert "@github.com" not in esito.stdout + esito.stderr


# ------------------------------------------------- comprensione col modello (LLM)
# La comprensione con un modello e' facoltativa: senza chiave si usa il parser a
# regole di `voice.parse`, con il comportamento identico a prima. I test qui sotto
# sostituiscono `urlopen` di `comprensione`: la rete non si tocca, si prova il
# percorso vero — costruzione della richiesta, interpretazione della risposta e,
# soprattutto, **cosa succede quando la risposta e' sbagliata**.


class _RispostaLlm:
    """Risposta finta di un servizio compatibile con OpenAI."""

    def __init__(self, contenuto: str):
        self._corpo = json.dumps(
            {"choices": [{"message": {"content": contenuto}}]}).encode()

    def read(self): return self._corpo
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_comprensione_valida_solo_un_intento_che_esiste():
    """Un intento inventato dal modello non deve arrivare all'esecuzione."""
    assert comprensione._ripulisci({"intent": "spegni_la_luce"})["intent"] == "unknown"
    assert comprensione._ripulisci({"intent": "shopping_add", "name": "latte"})["intent"] == "shopping_add"
    # senza nome non c'e' niente da scrivere: meglio non capire che scrivere vuoto
    assert comprensione._ripulisci({"intent": "shopping_add"})["intent"] == "unknown"


def test_comprensione_scarta_unita_e_quantita_non_previste():
    """Un'unita' fuori elenco o una quantita' non numerica vanno scartate, non
    passate: e' la differenza fra "non ho capito" e una voce sbagliata in dispensa."""
    c = comprensione._ripulisci({"intent": "pantry_add", "name": "farina",
                                 "quantity": "due", "unit": "cucchiaiate"})
    assert c["name"] == "farina"
    assert c["quantity"] is None    # "due" non e' un numero: il client mettera' 1
    assert c["unit"] is None        # unita' sconosciuta: si usa pz
    c = comprensione._ripulisci({"intent": "pantry_add", "name": "farina",
                                 "quantity": 2, "unit": "kg"})
    assert c["quantity"] == 2.0 and c["unit"] == "kg"


def test_comprensione_legge_il_json_anche_con_testo_attorno():
    """Non tutti i servizi rispettano `response_format`: si prende il primo oggetto."""
    assert comprensione._estrai_json('{"intent": "unknown"}') == {"intent": "unknown"}
    assert comprensione._estrai_json('Ecco: {"intent": "unknown"} grazie') == {"intent": "unknown"}
    assert comprensione._estrai_json("nessun json qui") is None


def test_comprensione_senza_chiave_ne_modello_non_e_configurata(monkeypatch):
    """Senza chiave **e** con un endpoint in rete non c'e' un modello: la
    comprensione resta a regole. (Un endpoint locale, come Ollama, invece vale
    anche senza chiave: vedi il test qui sotto.)"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert not comprensione.configurato()
    assert comprensione.chiama("aggiungi il latte alla spesa") is None


def test_un_modello_in_casa_non_richiede_una_chiave(monkeypatch):
    """Ollama non usa chiavi: l'endpoint locale da solo basta. E' la
    configurazione predefinita, e senza questo resterebbe spenta."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione.configurato()


def test_comprensione_chiama_il_modello_e_ne_interpreta_la_risposta(monkeypatch):
    """Si prova la richiesta vera, non solo l'interpretazione: la chiave va
    nell'intestazione e il modello richiesto e' quello configurato."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setenv("LLM_MODEL", "modello-di-prova")
    catturato = {}

    def finta(richiesta, timeout=None):
        catturato["url"] = richiesta.full_url
        catturato["aut"] = richiesta.headers.get("Authorization")
        catturato["corpo"] = json.loads(richiesta.data.decode())
        return _RispostaLlm('{"intent": "shopping_add", "name": "latte", "quantity": 1, "unit": "pz"}')

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finta)
    cmd = comprensione.chiama("dammi il latte")
    assert cmd["intent"] == "shopping_add" and cmd["name"] == "latte"
    assert catturato["aut"] == "Bearer chiave-llm-di-prova"
    assert catturato["corpo"]["model"] == "modello-di-prova"
    assert catturato["url"].endswith("/chat/completions")
    assert "latte" in catturato["corpo"]["messages"][-1]["content"]


def test_la_comprensione_lascia_budget_ai_modelli_di_ragionamento(monkeypatch):
    """Il tetto di token non deve strozzare i modelli che "pensano" prima di
    rispondere: il ragionamento spende lo stesso budget, e con un tetto stretto il
    JSON arriva troncato o vuoto. L'app ripiegherebbe in silenzio sulle regole e
    sembrerebbe che il modello non capisca. Un tetto largo non costa sugli altri
    modelli: si fermano da soli."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    catturato = {}

    def finta(richiesta, timeout=None):
        catturato["corpo"] = json.loads(richiesta.data.decode())
        return _RispostaLlm('{"intent": "unknown"}')

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finta)
    comprensione.chiama("dammi il latte")
    assert catturato["corpo"]["max_tokens"] >= 1024


def test_il_tempo_di_attesa_del_modello_si_puo_allungare(monkeypatch):
    """Un modello locale (Ollama su CPU) impiega diversi secondi a rispondere: il
    tetto del cloud lo farebbe scadere sempre, e si ricadrebbe in silenzio sulle
    regole. `LLM_TIMEOUT` lo allunga; senza la variabile resta il predefinito."""
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    assert comprensione.timeout() == comprensione.TIMEOUT
    monkeypatch.setenv("LLM_TIMEOUT", "30")
    assert comprensione.timeout() == 30.0
    monkeypatch.setenv("LLM_TIMEOUT", "non-un-numero")
    assert comprensione.timeout() == comprensione.TIMEOUT


def test_comprensione_ripiega_in_silenzio_se_il_modello_non_risponde(monkeypatch):
    """Un errore di rete non deve diventare un errore per chi ha parlato: si
    restituisce `None`, e il chiamante usa il parser a regole."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")

    def esplode(*a, **k):
        raise OSError("rete assente")

    monkeypatch.setattr(comprensione.urllib.request, "urlopen", esplode)
    assert comprensione.chiama("aggiungi il latte alla spesa") is None


def test_senza_modello_l_interruttore_non_si_accende(client, monkeypatch):
    """Accendere una cosa che non c'e' confonderebbe: si risponde 400 dicendo
    quale variabile registrare."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 400
    assert "LLM_API_KEY" in r.get_json()["error"]


def test_interruttore_del_modello_si_salva_per_casa(client, monkeypatch):
    """La scelta e' dell'utente e resta; e la chiave non compare mai nella risposta."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 200 and r.get_json()["llm_abilitato"] is True
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_disponibile"] is True and cfg["llm_abilitato"] is True
    assert "chiave-llm-di-prova" not in json.dumps(cfg)
    # e si puo' spegnere
    assert client.put("/api/voce/llm", json={"abilitato": False}).get_json()["llm_abilitato"] is False


def test_con_l_interruttore_spento_la_comprensione_resta_a_regole(client, monkeypatch):
    """Con l'interruttore spento (o la chiave assente) non si chiama nessuno:
    la comprensione e' quella del parser, identica a prima."""
    def non_chiamare(*a, **k):
        raise AssertionError("il modello non deve essere chiamato")

    monkeypatch.setattr(comprensione, "chiama", non_chiamare)
    r = client.post("/api/voice", json={"text": "aggiungi il latte alla spesa"})
    assert r.status_code == 200
    assert r.get_json()["intent"] == "shopping_add"


def test_la_comprensione_col_modello_corregge_la_frase_che_il_parser_sbaglia(client, monkeypatch):
    """Il caso che ha motivato tutto: "metti via il vino in cantina" finiva in
    magazzino con l'articolo chiamato "via il vino". Col modello il nome e' "vino".

    Il modello e' finto: si prova l'**integrazione** — che la sua risposta vinca
    su quella del parser e finisca davvero nel database."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {
        "intent": "storage_add", "name": "vino", "quantity": None, "unit": None,
        "place": "Cantina", "category": None})
    r = client.post("/api/voice", json={"text": "metti via il vino in cantina"})
    assert r.status_code == 200
    dati = r.get_json()
    assert dati["intent"] == "storage_add"
    assert dati["name"] == "vino"
    # e il nome sbagliato del parser non e' finito nel magazzino
    mag = client.get("/api/storage").get_json()
    nomi = [v["name"] for v in (mag.get("items", mag) if isinstance(mag, dict) else mag)]
    assert "vino" in nomi and "via il vino" not in nomi


def test_se_il_modello_non_capisce_si_usa_il_parser(client, monkeypatch):
    """`unknown` dal modello non cancella quello che il parser sapeva gia' fare."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {"intent": "unknown"})
    r = client.post("/api/voice", json={"text": "aggiungi il latte alla spesa"})
    assert r.get_json()["intent"] == "shopping_add"


def test_la_comprensione_e_disattiva_di_partenza(client):
    """Nessuna chiamata a consumo senza che l'utente l'abbia accesa."""
    assert client.get("/api/voce/config").get_json()["llm_abilitato"] is False


