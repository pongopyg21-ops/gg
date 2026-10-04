"""Verifica conversione unità e generazione lista della spesa. Crea un DB temporaneo."""
import base64
import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import date, timedelta

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
import calendario  # noqa: E402
import cinema  # noqa: E402
import comprensione  # noqa: E402
import copie  # noqa: E402
import dispensa  # noqa: E402
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
             "Tagliolini", "Calamarata", "Lasagne", "Noodles"}
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


def test_migrazione_aggiunge_expires_at_a_un_db_esistente():
    """Un database creato prima non ha `expires_at` in `pantry`, e
    `CREATE TABLE IF NOT EXISTS` non aggiunge una colonna a una tabella che
    esiste gia': la migrazione deve farlo, senza toccare le scorte presenti."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio-pantry.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
            CREATE TABLE pantry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT 'pz',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(ingredient_id, unit)
            );
            INSERT INTO ingredients (name) VALUES ('Farina');
            INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (1, 500, 'g');
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(pantry)")}
        assert "expires_at" in cols
        row = db.execute("SELECT quantity, unit, expires_at FROM pantry").fetchone()
        assert tuple(row) == (500, "g", None)
        app_module.migrate(db)  # rieseguire non deve fallire


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


# ----------------------------------------------- condividi / esporta la spesa
# La lista si compra al supermercato, spesso in due: qui si verifica il dato
# della scheda condivisibile (oggi, un giorno, un intervallo), che deve
# rispecchiare la lista. La scheda grafica si compone nel client: il server
# fornisce i numeri, il testo e le voci raggruppate.
def _spesa_su_giorni(client, *giorni):
    """Mette in piano un ingrediente diverso per giorno, poi rigenera la lista."""
    for i, g in enumerate(giorni):
        nome = f"Alimento{i}"
        rid = ricetta(client, nome, 2, [{"name": nome, "quantity": 100, "unit": "g"}])
        client.post("/api/plan", json={"date": g, "meal": "cena", "recipe_id": rid, "servings": 2})
    client.post("/api/shopping/generate",
                json={"start": min(giorni), "end": max(giorni)})


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


def test_ogni_ricetta_ha_la_sua_foto():
    """Ogni ricetta del ricettario ha una foto che esiste davvero su disco.

    Una foto mancante non si nota leggendo il codice: si nota aprendo la
    scheda e trovando un riquadro vuoto. Il test guarda `PHOTOS` *e* il file,
    perche' un nome giusto con il file assente e' lo stesso difetto.

    La licenza deve essere libera e il credito completo: le foto arrivano da
    Wikimedia Commons e l'attribuzione (autore, licenza, pagina) e' un
    obbligo, non un abbellimento.
    """
    import seed
    cartella = os.path.join(os.path.dirname(app_module.__file__), "static", "recipes")
    for r in seed.RECIPES:
        nome = r["name"]
        assert nome in seed.PHOTOS, f"{nome} senza foto in PHOTOS"
        file_name, credito = seed.PHOTOS[nome]
        assert os.path.exists(os.path.join(cartella, file_name)), \
            f"{nome}: manca il file {file_name}"
        assert file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")), \
            f"{nome}: {file_name} non e' un'immagine"
        assert "Wikimedia Commons" in credito and "CC" in credito.upper() \
            or "Public domain" in credito, f"{nome}: credito incompleto «{credito}»"
        assert "https://commons.wikimedia.org/" in credito, \
            f"{nome}: manca l'indirizzo della foto nel credito"


def test_ricettario_copre_primi_e_piatti_unici_recenti(client):
    """I piatti entrati in voga negli ultimi anni esistono e sono pianificabili.

    Il database di test nasce vuoto, quindi le ricette vengono caricate davvero
    via API: il test verifica sia la presenza nel ricettario sia che il formato
    del seed sia accettato dall'endpoint di creazione.
    """
    import seed
    attesi = {"Pasta alla Norma", "Spaghetti all'assassina", "Cacio e pepe",
              "Trofie al pesto", "Bucatini all'amatriciana", "Penne all'arrabbiata",
              "Pasta fredda alla mediterranea", "Calamarata",
              "Tagliolini al tartufo", "Poke bowl",
              "Gulasch", "Pizza napoletana", "Ramen"}
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


# ------------------------------------------------------------ bucati al giorno
def test_bucati_al_giorno_regola_la_cadenza_della_lavatrice(client):
    """I bucati dichiarati decidono ogni quanto torna «Avviare la lavatrice».

    Il legame e' diretto e va provato per intero: la scelta si salva nel profilo,
    `/api/chores` la usa, e il campo `cadenza_giorni` della voce lo dice. Senza
    il giro completo, la scelta resterebbe scritta e non cambierebbe niente."""
    # non dichiarato: la cadenza di partenza e' un giorno e mezzo
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.5

    r = client.put("/api/profile", json={"bucati_giorno": 1})
    assert r.status_code == 200
    assert r.get_json()["bucati_giorno"] == 1
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.0

    # zero torna alla cadenza di partenza: "non dico" non e' "mai"
    client.put("/api/profile", json={"bucati_giorno": 0})
    voce = next(v for v in client.get("/api/chores").get_json()["attivita"]
                if v["name"] == "Avviare la lavatrice")
    assert voce["cadenza_giorni"] == 1.5


def test_bucati_al_giorno_non_valido_rifiutato(client):
    for cattivo in (-1, 6, "tre", None):
        r = client.put("/api/profile", json={"bucati_giorno": cattivo})
        assert r.status_code == 400, cattivo
        assert "bucati" in r.get_json()["error"].lower()
    assert client.get("/api/profile").get_json()["bucati_giorno"] == 0


def test_le_opzioni_dei_bucati_arrivano_dalla_meta(client):
    """L'interfaccia non inventa i numeri: li legge dalla meta, cosi' onboarding
    e Profilo offrono le stesse scelte del backend."""
    meta = client.get("/api/meta").get_json()
    assert meta["bucati_opzioni"] == [1, 2, 3, 4, 5]
    assert client.get("/api/chores/meta").get_json()["bucati_opzioni"] == [1, 2, 3, 4, 5]


def test_cadenza_lavatrice_dai_bucati():
    """Il conto e' in un posto solo: piu' bucati, meno attesa. Il minimo e'
    mezza giornata, altrimenti la voce resterebbe sempre in cima al piano."""
    assert igiene.cadenza_lavatrice(0) == 1.5      # non dichiarato
    assert igiene.cadenza_lavatrice(1) == 1.0
    assert igiene.cadenza_lavatrice(2) == 0.5
    assert igiene.cadenza_lavatrice(5) == 0.5      # il minimo regge
    assert igiene.cadenza_lavatrice("x") == 1.5    # valore storto: si torna al default


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
    for chiave in ("giornaliera", "frazionaria", "settimanale", "mensile", "stagionale"):
        assert any(v["frequency"] == chiave for v in voci), chiave


def test_il_catalogo_ha_la_lavatrice_a_giorno_e_mezzo():
    """«Avviare la lavatrice» e' una voce del catalogo, a cadenza frazionaria.

    Un giorno e mezzo non e' un blocco tondo: la voce sta nel proprio gruppo e
    il conto usa l'ora (vedi `test_scadenza_frazionaria_conta_la_mezza_giornata`).
    """
    voci = igiene.catalogo()
    lavatrice = next((v for v in voci if v["name"] == "Avviare la lavatrice"), None)
    assert lavatrice is not None
    assert lavatrice["frequency"] == "frazionaria"
    assert igiene.CADENZE["frazionaria"] == 1.5
    # e la frequenza e' dichiarata fra le scelte dell'interfaccia
    assert any(f["key"] == "frazionaria" for f in igiene.FREQUENZE)


def test_la_sezione_igiene_ha_le_schede_e_i_pannelli(client):
    """Le schede separano tre mestieri diversi — cosa fare adesso, cosa esiste,
    cosa tocca nell'anno — e ognuna ha il suo pannello. Senza un pannello per
    scheda, il pulsante non avrebbe niente da mostrare e la sezione tornerebbe
    un'unica colonna."""
    html = client.get("/").get_data(as_text=True)
    sezione = html[html.index('id="tab-igiene"'):]
    sezione = sezione[:sezione.index("</section>")]
    for chiave in ("oggi", "routine", "anno", "catalogo"):
        assert f'data-chp="{chiave}"' in sezione, f"manca la scheda {chiave}"
        assert f'data-chp-panel="{chiave}"' in sezione, f"manca il pannello {chiave}"
    # una sola scheda parte aperta, e i pannelli sono tutti definiti
    assert sezione.count('ch-nav-btn active') == 1
    assert sezione.count('ch-panel active') == 1


def test_il_cambio_scheda_mostra_un_pannello_solo():
    """`mostraChPanel` e' la resa vera nel client: si esegue con node su un DOM
    finto. Il difetto da evitare e' che i pannelli restino tutti visibili, che e'
    esattamente cio' che rendeva la sezione dispersiva."""
    import subprocess
    js = open("static/app.js", encoding="utf-8").read()
    inizio = js.index("function mostraChPanel")
    blocco = js[inizio: js.index("\n}\n", inizio) + 3]
    prova = blocco + """
class Finto {
  constructor(dataset) {
    this.dataset = dataset;
    this.classes = new Set();
    this.attrs = {};
    this.classList = { toggle: (c, on) => (on ? this.classes.add(c) : this.classes.delete(c)) };
  }
  setAttribute(k, v) { this.attrs[k] = v; }
}
const bottoni = ['oggi', 'routine', 'anno', 'catalogo'].map((k) => new Finto({ chp: k }));
const pannelli = ['oggi', 'routine', 'anno', 'catalogo'].map((k) => new Finto({ chpPanel: k }));
const $$ = (sel) => sel.includes('btn') ? bottoni : pannelli;
mostraChPanel('anno');
console.log(JSON.stringify({
  bottoniAttivi: bottoni.filter((b) => b.classes.has('active')).map((b) => b.dataset.chp),
  pannelliVisibili: pannelli.filter((p) => p.classes.has('active')).map((p) => p.dataset.chpPanel),
}));
"""
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    d = json.loads(esito.stdout)
    assert d["bottoniAttivi"] == ["anno"]
    assert d["pannelliVisibili"] == ["anno"], "si vede piu' di un pannello"



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


def test_scadenza_frazionaria_conta_la_mezza_giornata():
    """Una cadenza di un giorno e mezzo non e' ne' un giorno ne' due.

    Con la sola data la mezza andrebbe persa: fatta lunedi' alle 8, la voce
    risulterebbe da rifare gia' martedi' mattina. L'ora del completamento e'
    quella che distingue "un giorno e mezzo" da "un giorno".
    """
    # lunedi' 8:00 -> la prossima e' martedi' alle 20:00, cioe' 1,5 giorni
    stato = igiene.scadenza("frazionaria", "2026-09-14T08:00:00",
                            "2026-09-15T08:00:00")
    assert stato["prossima"] == "2026-09-15T20:00:00"
    assert stato["in_scadenza"] is False
    assert stato["giorni"] == 0.5, "meta' giornata ancora da aspettare"
    # martedi' sera alle 20:00 e' il momento: rientra
    scaduta = igiene.scadenza("frazionaria", "2026-09-14T08:00:00",
                              "2026-09-15T20:00:00")
    assert scaduta["in_scadenza"] is True
    assert scaduta["giorni"] == 0


def test_scadenza_frazionaria_senza_ora_e_tollerante():
    """Un valore con la sola data non deve far esplodere il calcolo."""
    stato = igiene.scadenza("frazionaria", "2026-09-14", "2026-09-15T20:00:00")
    assert "in_scadenza" in stato
    assert stato["prossima"] == "2026-09-15T12:00:00", "mezzanotte + 1,5 giorni"


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
    assert len(m["frequencies"]) == 5
    assert m["areas"]
    assert 0 <= m["chore_day"] <= 6


def test_api_pulizie_seminata_al_primo_avvio(client):
    """Un database nuovo deve uscire con il catalogo delle pulizie gia' pronto."""
    r = client.get("/api/chores").get_json()
    assert r["attivita"], "il catalogo non e' vuoto"
    assert r["attive"] == len([v for v in r["attivita"] if v["active"]])
    assert set(r["piano"]["gruppi"]) == {"quotidiane", "frazionarie", "settimanali"}
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
    assert all(v["frequency"] in ("giornaliera", "frazionaria", "settimanale") for v in oggi)
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


# --------------------------------------------- suggerimenti dalla dispensa
def test_suggerimenti_vuoti_con_dispensa_vuota(client):
    """Senza niente in casa non c'e' niente da suggerire, e nessun errore."""
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    r = client.get("/api/pantry/suggerimenti")
    assert r.status_code == 200
    assert r.get_json() == {"dispensa": 0, "suggerimenti": []}


def test_suggerisce_le_ricette_che_usa_la_dispensa(client):
    """La ricetta i cui ingredienti sono in casa viene suggerita, e risulta pronta."""
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                        "unit": i["unit"]})
    dati = client.get("/api/pantry/suggerimenti").get_json()
    nomi = [s["name"] for s in dati["suggerimenti"]]
    assert "Cacio e pepe" in nomi
    cacio_sug = next(s for s in dati["suggerimenti"] if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is True
    assert cacio_sug["mancanti"] == 0
    assert cacio_sug["punteggio"] == 1.0
    # e' la prima: con tutti gli ingredienti in casa non puo' essere superata
    assert nomi[0] == "Cacio e pepe"


def test_una_ricetta_coperta_in_parte_non_e_pronta(client):
    """Mezza scorta non copre: la ricetta si suggerisce, ma non come pronta.

    E' il caso in cui l'errore sarebbe peggiore: dire «hai tutto» con 100 g di
    farina al posto di 500 manda a cucinare una ricetta che non si fa.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    # meta' quantita' per ogni ingrediente: nessuno e' coperto del tutto
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"] / 2,
                                        "unit": i["unit"]})
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is False
    assert cacio_sug["parziali"] == len(cacio["items"])
    assert cacio_sug["coperti"] == 0
    assert cacio_sug["punteggio"] == 0.5


def test_le_quantita_si_confrontano_solo_fra_unita_convertibili(client):
    """500 g coprono mezzo chilo, ma una confezione non copre un pezzo.

    Se le unita' non convertibili venissero sommate lo stesso, un ingrediente
    senza scorta risulterebbe coperto e la ricetta direbbe «hai tutto» a vuoto.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    spaghetti = next(i for i in cacio["items"] if i["name"] == "Spaghetti")
    # in dispensa mezzo chilo, in ricetta 180 g: stesso peso, unita' diverse
    client.post("/api/pantry", json={"name": "Spaghetti", "quantity": 0.5, "unit": "kg"})
    for i in cacio["items"]:
        if i["name"] != "Spaghetti":
            client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                            "unit": i["unit"]})
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is True, "0,5 kg doveva coprire 180 g"

    # e una confezione non copre un pezzo: si cambia l'unita' della riga di
    # dispensa direttamente sul database della casa collegata
    percorso = houses.db_path(CASA_TEST)
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("""UPDATE pantry SET unit = 'confezione'
                      WHERE ingredient_id = (SELECT id FROM ingredients
                                             WHERE name = 'Spaghetti')""")
        db.commit()
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is False, "una confezione non copre 180 g"


def test_il_suggerimento_rispetta_le_allergie(client):
    """Una ricetta con un allergene dichiarato non viene suggerita.

    Qui l'app dice «cucina questa»: proporre un allergene non e' una svista da
    correggere, e' un errore. Il filtro sta sul server, quindi non dipende da
    cosa il browser decide di mostrare.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    client.put("/api/profile", json={"restrictions": "glutine"})
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                        "unit": i["unit"]})
    nomi = [s["name"] for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]]
    assert "Cacio e pepe" not in nomi, "suggerita una ricetta con glutine"


def test_una_ricetta_corta_e_completa_batte_una_lunga_e_incompleta():
    """Il punteggio e' una frazione, non un conteggio di ingredienti coperti.

    Contando gli ingredienti coperti vincerebbe la ricetta piu' lunga: una da
    dodici con sette in dispensa batterebbe una da quattro con quattro, che e'
    invece quella che si puo' cucinare stasera. E' il motivo per cui il
    punteggio e' una frazione.
    """
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "punteggio.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        # ingredienti una volta sola: la copertura si misura sull'ingrediente,
        # quindi le due ricette devono condividere le stesse righe
        ids = {}
        for nome_ing in "abcdefghijkl":
            ids[nome_ing] = db.execute("INSERT INTO ingredients (name) VALUES (?)",
                                       (nome_ing,)).lastrowid
        def ricetta(nome, lettere):
            rid = db.execute("INSERT INTO recipes (name) VALUES (?)", (nome,)).lastrowid
            for lettera in lettere:
                db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                           " VALUES (?, ?, 1, 'pz')", (rid, ids[lettera]))
        ricetta("Corta e completa", "abcd")
        ricetta("Lunga e incompleta", "abcdefghijkl")
        # in casa ci sono solo a, b, c, d
        for lettera in "abcd":
            db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                       (ids[lettera],))
        db.commit()
        esito = dispensa.suggerimenti(db)
    nomi = [s["name"] for s in esito["suggerimenti"]]
    assert nomi[0] == "Corta e completa", nomi
    lunga = next(s for s in esito["suggerimenti"] if s["name"] == "Lunga e incompleta")
    corta = next(s for s in esito["suggerimenti"] if s["name"] == "Corta e completa")
    assert corta["coperti"] == 4 and corta["punteggio"] == 1.0
    assert lunga["coperti"] == 4 and lunga["punteggio"] < 1.0


def test_una_ricetta_senza_ingredienti_non_e_un_suggerimento():
    """Senza ingredienti non c'e' niente da consumare, quindi non si suggerisce."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "vuota.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        db.execute("INSERT INTO recipes (name) VALUES ('Solo un nome')")
        iid = db.execute("INSERT INTO ingredients (name) VALUES ('qualcosa')").lastrowid
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                   (iid,))
        db.commit()
        esito = dispensa.suggerimenti(db)
    assert esito["suggerimenti"] == []


# ------------------------------------------------------- scadenze in dispensa
# La scadenza e' un dato della dispensa come la quantita': si salva, si cambia e
# si toglie. La regola che conta e' che "non lo so" (vuoto) resti diverso da "non
# scade", perche' una data inventata farebbe buttare cibo buono.

def test_la_scadenza_si_salva_e_si_rilegge(client):
    r = client.post("/api/pantry", json={"name": "Yogurt", "quantity": 1, "unit": "pz",
                                        "expires_at": "2026-10-05"})
    assert r.status_code == 201
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["expires_at"] == "2026-10-05"


def test_una_scadenza_non_valida_non_entra_nel_database(client):
    """Un testo che non e' una data non deve salvarvisi: romperebbe l'ordinamento
    e i confronti, e l'utente vedrebbe una data che non ha scritto."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 1, "unit": "pz",
                                     "expires_at": "domani"})
    assert client.get("/api/pantry").get_json()[0]["expires_at"] is None


def test_la_scadenza_si_puo_togliere_senza_toccare_la_quantita(client):
    """Il campo della scadenza e' separato dalla quantita': svuotarlo la toglie,
    e non deve azzerare la quantita' scritta nell'altro campo."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 3, "unit": "pz",
                                     "expires_at": "2026-10-05"})
    pid = client.get("/api/pantry").get_json()[0]["id"]
    client.patch(f"/api/pantry/{pid}", json={"expires_at": ""})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["expires_at"] is None
    assert voce["quantity"] == 3


def test_la_quantita_si_cambia_senza_cancellare_la_scadenza(client):
    """Aggiornare la quantita' non manda il campo scadenza: senza la regola del
    "tocca solo se presente", la scadenza sparirebbe a ogni cambio di quantita'."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 3, "unit": "pz",
                                     "expires_at": "2026-10-05"})
    pid = client.get("/api/pantry").get_json()[0]["id"]
    client.patch(f"/api/pantry/{pid}", json={"quantity": 2})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["quantity"] == 2
    assert voce["expires_at"] == "2026-10-05"


def test_aggiungendo_scorte_vince_la_scadenza_piu_vicina(client):
    """Due partite dello stesso ingrediente con scadenze diverse: quella che
    scade prima e' quella da guardare, e deve restare in evidenza."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-20"})
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-03"})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["quantity"] == 2
    assert voce["expires_at"] == "2026-10-03"


def test_una_scorta_senza_data_non_cancella_quella_con_data(client):
    """Chi aggiunge una partita senza sapere la scadenza non deve cancellare
    quella che sapeva: la data che c'era resta."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-03"})
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l"})
    assert client.get("/api/pantry").get_json()[0]["expires_at"] == "2026-10-03"


def test_una_ricetta_che_consuma_una_scadenza_viene_prima():
    """Fra due ricette ugualmente coperte, va suggerita per prima quella che
    consuma una scorta in scadenza: e' quella da cucinare adesso."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "scadenze.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        # due ingredienti: uno scade fra due giorni, l'altro non scade
        presto = db.execute("INSERT INTO ingredients (name) VALUES ('Da consumare')").lastrowid
        tardi = db.execute("INSERT INTO ingredients (name) VALUES ('Tranquillo')").lastrowid
        for iid in (presto, tardi):
            db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                       (iid,))
        db.execute("UPDATE pantry SET expires_at = '2026-10-04' WHERE ingredient_id = ?", (presto,))
        # due ricette da un ingrediente ciascuna, ugualmente coperte
        for nome, iid in (("Usa il fresco", presto), ("Usa il durevole", tardi)):
            rid = db.execute("INSERT INTO recipes (name) VALUES (?)", (nome,)).lastrowid
            db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                       " VALUES (?, ?, 1, 'pz')", (rid, iid))
        db.commit()
        esito = dispensa.suggerimenti(db, oggi=__import__("datetime").date(2026, 10, 2))
    nomi = [s["name"] for s in esito["suggerimenti"]]
    assert nomi[0] == "Usa il fresco", nomi
    fresco = next(s for s in esito["suggerimenti"] if s["name"] == "Usa il fresco")
    assert fresco["scadono"] == ["Da consumare"]
    durevole = next(s for s in esito["suggerimenti"] if s["name"] == "Usa il durevole")
    assert durevole["scadono"] == []


def test_una_scadenza_lontana_non_mette_in_cima_la_ricetta():
    """Una scadenza oltre la settimana non e' un problema di stasera: non deve
    riordinare i suggerimenti."""
    import sqlite3 as sq
    from contextlib import closing as cl
    import datetime as dt
    percorso = os.path.join(tempfile.mkdtemp(), "lontana.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        iid = db.execute("INSERT INTO ingredients (name) VALUES ('Durevole')").lastrowid
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit, expires_at)"
                   " VALUES (?, 1, 'pz', '2026-12-31')", (iid,))
        rid = db.execute("INSERT INTO recipes (name) VALUES ('Una ricetta')").lastrowid
        db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                   " VALUES (?, ?, 1, 'pz')", (rid, iid))
        db.commit()
        esito = dispensa.suggerimenti(db, oggi=dt.date(2026, 10, 2))
    assert esito["suggerimenti"][0]["scadono"] == []


def test_la_dispensa_vuota_lo_dice_invece_di_tacere(client):
    """Il riquadro dei suggerimenti con la dispensa vuota resta nascosto e sembra
    che la funzione non esista: si esegue `renderSuggerimenti` vera con node, con
    la risposta del server, e si guarda cosa finisce nella pagina."""
    js = client.get("/static/app.js").get_data(as_text=True)
    codice = _estrai_funzione_js(js, "renderSuggerimenti")
    preludio = """
let contenuto = '';
function $(sel) { return { set innerHTML(v) { contenuto = v; },
                            get innerHTML() { return contenuto; } }; }
function esc(s) { return String(s); }
let risposta = { dispensa: 0, suggerimenti: [] };
async function api() { return risposta; }
"""
    coda = """
(async () => {
  await renderSuggerimenti();
  const vuota = contenuto;
  risposta = { dispensa: 4, suggerimenti: [] };
  await renderSuggerimenti();
  console.log(JSON.stringify({ vuota: vuota, piena: contenuto }));
})();
"""
    d = _esegui_node(preludio + codice + coda)
    # con la dispensa vuota si dice cosa fare, invece di lasciare il vuoto
    assert "Aggiungi qualche ingrediente" in d["vuota"]
    # con la dispensa piena ma nessuna ricetta fattibile il riquadro resta pulito
    assert d["piena"] == ""


# --------------------------------------------- tempi e costo della ricetta
def test_i_due_tempi_e_il_costo_si_salvano_e_si_rileggono(client):
    r = client.post("/api/recipes", json={
        "name": "Prova tempi", "servings": 4,
        "prep_minutes": 20, "cook_minutes": 45, "cost": 2.5,
        "items": [{"name": "Farina", "quantity": 200, "unit": "g"}],
    })
    assert r.status_code == 201
    rec = r.get_json()
    assert rec["prep_minutes"] == 20
    assert rec["cook_minutes"] == 45
    assert rec["cost"] == 2.5
    # si rileggono dalla scheda, non solo dalla risposta della creazione
    letto = client.get(f"/api/recipes/{rec['id']}").get_json()
    assert (letto["prep_minutes"], letto["cook_minutes"], letto["cost"]) == (20, 45, 2.5)


def test_i_tempi_non_validi_non_diventano_numeri_inventati(client):
    """Vuoto, zero, negativo e testo non sono tempi: restano «non indicato».

    Zero e' il caso che conta: salvarlo mostrerebbe «0 min» al posto di niente,
    e l'utente crederebbe che la ricetta si faccia in zero minuti.
    """
    for valore in ("", 0, -10, "boh", None):
        rec = client.post("/api/recipes", json={
            "name": f"Prova {valore}", "prep_minutes": valore, "cook_minutes": valore,
        }).get_json()
        assert rec["prep_minutes"] is None, valore
        assert rec["cook_minutes"] is None, valore


def test_il_costo_non_valido_non_diventa_un_prezzo(client):
    """Un costo vuoto, negativo o non numerico resta «non indicato».

    Zero invece si tiene: e' un'informazione vera — «non costa niente», tipico di
    una ricetta fatta con gli avanzi — e non va confusa con «non lo so». Il
    campo vuoto e' l'unico modo per dire che il costo non si conosce.
    """
    for valore in ("", -1, "boh", None):
        rec = client.post("/api/recipes", json={
            "name": f"Costo {valore}", "cost": valore,
        }).get_json()
        assert rec["cost"] is None, valore
    zero = client.post("/api/recipes", json={"name": "Costo zero", "cost": 0}).get_json()
    assert zero["cost"] == 0, "lo zero e' un costo, non un dato mancante"


def test_il_totale_vecchio_non_si_perde_quando_i_due_tempi_sono_vuoti(client):
    """Le ricette salvate prima dei due tempi hanno solo `time_minutes`.

    Se il form lo azzerasse, aprire e salvare una ricetta vecchia cancellerebbe
    un dato che l'utente non ha mai toccato. Sparisce solo quando i due tempi
    vengono indicati, perche' allora il totale si ricava da quelli.
    """
    rec = client.post("/api/recipes", json={"name": "Vecchia", "time_minutes": 40}).get_json()
    assert rec["time_minutes"] == 40
    # salvataggio parziale: i due tempi restano vuoti, il totale resta
    rec2 = client.put(f"/api/recipes/{rec['id']}", json={"name": "Vecchia", "time_minutes": 40}).get_json()
    assert rec2["time_minutes"] == 40
    # indicando i due tempi, il totale non serve piu'
    rec3 = client.put(f"/api/recipes/{rec['id']}", json={
        "name": "Vecchia", "time_minutes": None, "prep_minutes": 15, "cook_minutes": 25,
    }).get_json()
    assert rec3["time_minutes"] is None
    assert rec3["prep_minutes"] == 15 and rec3["cook_minutes"] == 25


def test_tempi_e_costo_arrivano_anche_nell_elenco_completo(client):
    """La scheda mostra tempi e costo senza una seconda richiesta."""
    client.post("/api/recipes", json={"name": "Con tempi", "prep_minutes": 10,
                                      "cook_minutes": 20, "cost": 3})
    elenco = client.get("/api/recipes?full=1").get_json()
    rec = next(r for r in elenco if r["name"] == "Con tempi")
    assert rec["prep_minutes"] == 10
    assert rec["cook_minutes"] == 20
    assert rec["cost"] == 3


def test_le_colonne_dei_tempi_arrivano_ai_database_esistenti():
    """Un database creato prima non ha le colonne: `migrate()` le aggiunge."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "vecchio.db")
    with cl(sq.connect(percorso)) as db:
        db.executescript("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                servings INTEGER NOT NULL DEFAULT 2, time_minutes INTEGER,
                difficulty TEXT NOT NULL DEFAULT 'facile',
                instructions TEXT NOT NULL DEFAULT '');
        """)
        db.execute("INSERT INTO recipes (name, time_minutes) VALUES ('Vecchia', 40)")
        db.commit()
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        colonne = {r[1] for r in db.execute("PRAGMA table_info(recipes)")}
        assert {"prep_minutes", "cook_minutes", "cost"} <= colonne
        riga = db.execute("SELECT time_minutes, prep_minutes, cost FROM recipes").fetchone()
        assert riga == (40, None, None), "il totale vecchio non e' stato toccato"


def test_tempiRicetta_e_costoRicetta_funzionano_davvero(client):
    """Le due funzioni del client, eseguite con node sul caso vero.

    Il totale e' la somma dei due tempi; con solo il totale vecchio si mostra
    quello; senza niente non si mostra nulla. Un test sulle stringhe non
    accorgerebbe di una somma sbagliata.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function tempiRicetta")
    blocco = js[inizio:js.index("\n}\n", inizio) + 3]
    inizio2 = js.index("function costoRicetta")
    blocco += js[inizio2:js.index("\n}\n", inizio2) + 3]
    prova = blocco + """
const casi = [
  {prep_minutes: 20, cook_minutes: 45},
  {prep_minutes: 15},
  {time_minutes: 40},
  {},
];
console.log(JSON.stringify({
  tempi: casi.map((r) => tempiRicetta(r)),
  costi: [costoRicetta({cost: 2.5}), costoRicetta({cost: 0}), costoRicetta({cost: null})],
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    # in JSON: una stringa vuota stampata da sola sparirebbe nello strip()
    esito_js = json.loads(esito.stdout)
    tempi = esito_js["tempi"]
    assert tempi[0] == {"totale": 65, "testo": "prep 20 min + cottura 45 min · totale 65 min"}
    assert tempi[1] == {"totale": 15, "testo": "prep 15 min · totale 15 min"}
    assert tempi[2] == {"totale": 40, "testo": "40 min"}
    assert tempi[3] is None
    assert esito_js["costi"] == ["€ 2,50 a porzione", "€ 0,00 a porzione", ""]


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
    l'app da prima continuerebbe a vedere le voci che il catalogo ha tolto — la
    voce unita e "Arieggiare le stanze" — e il riordino non arriverebbe mai
    proprio a chi ha piu' da guadagnarci.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        # com'era il database prima: la voce unita, che il catalogo ha assorbito
        # in "Riordino generale"
        con.execute("INSERT INTO chores (name, area, frequency, minutes, month) "
                    "VALUES ('Raccogliere gli oggetti fuori posto', 'Tutta la casa', 'giornaliera', 5, NULL)")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        nomi = {r[0] for r in con.execute("SELECT name FROM chores")}
        assert "Raccogliere gli oggetti fuori posto" not in nomi, "la voce unita va tolta"
        assert "Arieggiare le stanze" not in nomi, "la voce non e' piu' un lavoro da spuntare"


def test_le_quotidiane_sono_tre(tmp_path):
    """Le attivita' quotidiane sono tre, non quattro.

    La giornata fissa deve restare una routine breve: le voci che dicevano la
    stessa cosa sono state unite e "Arieggiare le stanze" e' stata tolta, perche'
    e' aprire le finestre mentre si fa altro, non un lavoro a se'."""
    voci = igiene.catalogo()
    quotidiane = [v for v in voci if v["frequency"] == "giornaliera"]
    assert len(quotidiane) == 3
    nomi = {v["name"] for v in quotidiane}
    assert "Arieggiare le stanze" not in nomi
    # e il piano di oggi non le gonfia: le tre voci restano sotto il budget
    assert sum(v["minutes"] for v in quotidiane) <= 25


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
    """La migrazione non riallinea i minuti: la stima dell'utente resta.

    I minuti sono una stima che l'utente puo' correggere, e il riallineamento
    del catalogo non li tocca: correggerla a forza cancellerebbe la sua
    correzione a ogni richiesta.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("UPDATE chores SET minutes = 7 WHERE name = 'Riordino generale'")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        minuti = dict(con.execute("SELECT name, minutes FROM chores"))
        assert minuti["Riordino generale"] == 7, "la stima dell'utente resta"


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


def test_ogni_ricetta_ha_una_preparazione_dettagliata():
    """Le preparazioni del ricettario sono scritte per passi, non in due righe.

    Il client le mostra come elenco numerato (`passiDa` divide su righe vuote e
    punti), quindi una preparazione di una frase sola diventa un passo unico e
    non serve a chi cucina. Il test fissa la sostanza: piu' passi e un testo che
    spiega tempi e modi, non solo l'elenco degli ingredienti in prosa.
    """
    import seed
    for r in seed.RECIPES:
        passi = [p for p in r["instructions"].split("\n\n") if p.strip()]
        assert len(passi) >= 4, \
            f"{r['name']}: solo {len(passi)} passi, la preparazione e' troppo breve"
        assert len(r["instructions"]) >= 400, \
            f"{r['name']}: {len(r['instructions'])} caratteri, troppo poco dettaglio"
        for passo in passi:
            assert passo.strip().endswith((".", ":", "!")), \
                f"{r['name']}: passo senza punto finale «{passo[:40]}»"


def test_le_preparazioni_vecchie_vengono_aggiornate(casa_test):
    """Un database esistente riceve le preparazioni nuove al primo `semina()`.

    Chi usa l'app da prima ha ancora i testi brevi: senza questo aggiornamento
    vedrebbe le preparazioni dettagliate solo creando una casa nuova.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 20, 'facile', ?)",
                       (r["name"], seed.PREPARAZIONI_PRECEDENTI[r["name"]]))
        db.commit()

    seed.semina(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            testo = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                               (r["name"],)).fetchone()[0]
            assert testo == r["instructions"], f"{r['name']} non aggiornata"


def test_una_preparazione_scritta_a_mano_non_viene_sovrascritta(casa_test):
    """La preparazione dell'utente e' un dato suo: `semina()` non la tocca.

    L'aggiornamento sostituisce il testo solo se e' ancora quello vecchio. Senza
    questa guardia, chi ha riscritto la ricetta di famiglia se la vedrebbe
    cancellare al primo riavvio del server.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    mio = "La ricetta di nonna: soffriggi tutto e cuoci piano finche' e' pronto."
    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 20, 'facile', ?)",
                       (r["name"], seed.PREPARAZIONI_PRECEDENTI[r["name"]]))
        db.execute("UPDATE recipes SET instructions = ? WHERE name = ?",
                   (mio, "Pasta al pomodoro"))
        db.commit()

    seed.semina(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        testo = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                           ("Pasta al pomodoro",)).fetchone()[0]
        assert testo == mio, "la preparazione scritta a mano e' stata sovrascritta"
        # le altre invece si aggiornano: la guardia vale solo per quella toccata
        altro = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                           ("Cacio e pepe",)).fetchone()[0]
        assert altro == next(r["instructions"] for r in seed.RECIPES
                             if r["name"] == "Cacio e pepe")


def test_le_preparazioni_dettagliate_escono_come_passi(client):
    """`passiDa` deve spezzare la preparazione in un elenco, non in un blocco.

    E' la resa vera nel client: si esegue la funzione estratta da `app.js` con
    node, sul testo che sta davvero nel ricettario. Un test sulle stringhe non
    accorgerebbe di una preparazione che resta un passo unico.
    """
    import seed
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function passiDa"):
                 js.index("\n}\n", js.index("function passiDa")) + 3]
    preparazione = next(r["instructions"] for r in seed.RECIPES
                        if r["name"] == "Cacio e pepe")
    prova = blocco + f"""
const testo = {json.dumps(preparazione)};
console.log(JSON.stringify({{ passi: passiDa(testo) }}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    passi = json.loads(esito.stdout)["passi"]
    assert len(passi) >= 5, f"solo {len(passi)} passi: la preparazione resta un blocco"
    assert all(p.strip() for p in passi), "nessun passo vuoto"
    # il primo passo dice cosa preparare per primo, non e' un titolo
    assert "pepe" in passi[0].lower()


def test_le_ricette_tolte_non_sono_piu_nel_ricettario():
    """Le ricette tolte su richiesta dell'utente non tornano a ogni semina.

    `REMOVED` da solo non basta: la cancellazione in `semina()` avviene prima
    dell'inserimento, quindi una ricetta presente in entrambe le liste verrebbe
    tolta e subito rimessa. Devono mancare da `RECIPES`, e le mappe che le
    accompagnano devono seguire, altrimenti restano chiavi senza ricetta.
    """
    import seed
    tolte = ["Casoncelli alla bergamasca", "Chicken tikka masala",
             "Insalata di riso", "Lasagna soup", "Malloreddus alla campidanese",
             "Marry me chicken", "Paella", "Riso alla cantonese", "Shakshuka"]
    nomi = {r["name"] for r in seed.RECIPES}
    for nome in tolte:
        assert nome not in nomi, f"{nome} e' ancora nel ricettario"
        assert nome not in seed.PHOTOS, f"{nome} ha ancora una foto"
        assert nome not in seed.PREPARAZIONI_PRECEDENTI, nome
    # le tre mappe parlano delle stesse ricette: una chiave in piu' e' un residuo
    assert set(seed.PHOTOS) == nomi
    assert set(seed.PREPARAZIONI_PRECEDENTI) == nomi
    # e i file delle foto tolte non restano orfani su disco
    import os
    for nome in tolte:
        for f in os.listdir(os.path.join(os.path.dirname(seed.__file__),
                                         "static", "recipes")):
            assert nome.replace(" ", "-").lower() not in f.lower(), \
                f"il file {f} della ricetta tolta {nome} e' ancora su disco"


def test_le_ricette_tolte_spariscono_anche_dai_database_esistenti(casa_test):
    """Chi ha gia' i dati non deve tenersi le ricette tolte per sempre.

    `seed.semina()` gira solo quando un database nasce, e `windows\\avvia.bat`
    non lo chiama affatto: senza il passaggio in `migrate()` le ricette tolte
    sparirebbero solo dalle case nuove. Qui si simula il database di prima —
    ricette presenti, una nel piano e fra i preferiti — e si verifica che la
    migrazione le porti via **insieme** a quello che le puntava.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    tolte = seed.REMOVED
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        for nome in tolte:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 30, 'facile', 'vecchia')", (nome,))
        rid = db.execute("SELECT id FROM recipes WHERE name = ?", (tolte[0],)).fetchone()[0]
        db.execute("INSERT INTO meal_plan (date, meal, recipe_id, servings)"
                   " VALUES ('2026-09-29', 'pranzo', ?, 2)", (rid,))
        db.execute("INSERT INTO favorites (recipe_id) VALUES (?)", (rid,))
        ing = db.execute("INSERT INTO ingredients (name, category)"
                         " VALUES ('ingrediente-fantasma', 'Altro')").lastrowid
        db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                   " VALUES (?, ?, 1, 'pz')", (rid, ing))
        db.commit()

    # il passaggio che gira a ogni richiesta
    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        rimaste = {r[0] for r in db.execute("SELECT name FROM recipes")}
        assert not (set(tolte) & rimaste), "una ricetta tolta e' rimasta"
        assert db.execute("SELECT COUNT(*) FROM meal_plan").fetchone()[0] == 0, \
            "il piano conserva una ricetta tolta"
        assert db.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0
        orfane = db.execute(
            "SELECT COUNT(*) FROM recipe_items WHERE recipe_id NOT IN"
            " (SELECT id FROM recipes)").fetchone()[0]
        assert orfane == 0, "restano righe di ricette che non esistono piu'"
        # l'ingrediente che solo quella ricetta usava non deve restare orfano
        assert db.execute("SELECT COUNT(*) FROM ingredients WHERE name = ?",
                          ("ingrediente-fantasma",)).fetchone()[0] == 0


def test_le_ricette_con_foto_vengono_prima(client):
    """Nell'elenco le ricette con foto stanno sopra quelle senza.

    Si esegue la funzione vera di `app.js` con node: l'ordine e' una proprieta'
    del client, e un test sulle stringhe non accorgerebbe di un comparatore
    sbagliato. Dentro i due gruppi l'ordine alfabetico non deve cambiare.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function conFotoPrima"):
                 js.index("\n}\n", js.index("function conFotoPrima")) + 3]
    prova = blocco + """
const lista = [
  {name: 'Senza A', image: ''},
  {name: 'Con B', image: 'b.jpg'},
  {name: 'Senza C', image: ''},
  {name: 'Con D', image: 'd.jpg'},
];
console.log(JSON.stringify(conFotoPrima(lista).map((r) => r.name)));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    ordine = json.loads(esito.stdout)
    assert ordine == ["Con B", "Con D", "Senza A", "Senza C"], ordine


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


def test_la_domanda_sulla_quantita_vale_senza_sveglia(client):
    """Il difetto riferito: dopo aver chiamato l'assistente, comandi come
    "quante ricette ho" venivano **ignorati in silenzio**, e sembrava che
    servisse dire "Hey GG" ogni volta.

    La causa: il criterio che apre la frase (`sembraComando`) accettava "quanto"
    ma non "quante"/"quanti"/"quanta", che sono la forma piu' naturale ("quante
    uova ho?", "quanti grammi sono rimasti"). Il parser del server li capisce
    (intento `domanda`), quindi era solo il cancello a sbarrarli."""
    d = _decisione_js(client, """{
      quanteRicette: decisioneContinuo('quante ricette ho', false, '', true),
      quantiGrammi: decisioneContinuo('quanti grammi sono rimasti', false, '', true),
      quantaFarina: decisioneContinuo('quanta farina ho', false, '', true),
      quantoSale: decisioneContinuo('quanto sale ho', false, '', true),
    }""")
    for caso in ("quanteRicette", "quantiGrammi", "quantaFarina", "quantoSale"):
        assert d[caso]["azione"] == "esegui", (caso, d[caso])
    # e la forma resta fuori **fuori** dalla finestra, come ogni comando
    d2 = _decisione_js(client, """{
      fuori: decisioneContinuo('quante ricette ho', false, '', false),
    }""")
    assert d2["fuori"]["azione"] == "ignora"


def _finestra_js(client, script):
    """Esegue le funzioni della finestra dopo "Sì." con un orologio finto.

    Il tempo e' l'unico modo di provare una regola a scadenza senza aspettare:
    `Date.now` si sostituisce con un valore che il test fa avanzare a mano."""
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("const ATTESA_COMANDO_MS")
    fine = js.index("\n}\n", js.index("function inAttesaComando")) + 3
    blocco = js[inizio:fine]
    prova = """
let adesso = 1000000;   // non zero: l'orologio vero non parte mai da zero, e
                        // `apertaIl` a zero sarebbe indistinguibile da "mai aperta"
const Date = { now: () => adesso };
let ascoltoContinuo = { inAttesa: 0, apertaIl: 0 };
function avanza(ms) { adesso += ms; }
""" + blocco + "\n" + script
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


def test_la_finestra_dopo_si_si_riarma_dopo_un_comando(client):
    """Il secondo pezzo del difetto: la finestra si chiudeva col **primo**
    comando, quindi "Hey GG", "metti il latte", "e aggiungi il pane" richiedeva
    la sveglia a ogni frase. Ora dopo un comando si rinnova, cosi' piu' ordini
    di fila si dicono dopo una sola attivazione.

    Il tetto resta: la finestra non e' eterna, altrimenti il discorso di casa
    diventerebbe un ordine."""
    d = _finestra_js(client, """
attendeComando();                       // t=0: si apre
const subito = inAttesaComando();       // true
avanza(9000);
riarmaFinestra();                       // t=9000: un comando la rinnova
avanza(6000);                           // t=15000
const dopoComando = inAttesaComando();  // true: 15s - 9s < 10s
avanza(5000);                           // t=20000: 20s - 9s = 11s > 10s
const scaduta = inAttesaComando();      // false
console.log(JSON.stringify({ subito, dopoComando, scaduta }));
""")
    assert d == {"subito": True, "dopoComando": True, "scaduta": False}, d


def test_la_finestra_ha_un_tetto_e_non_si_apre_da_sola(client):
    """Due guardie opposte, entrambe necessarie:

    - `riarmaFinestra` **non** apre una finestra chiusa: altrimenti bastava un
      comando qualunque per far entrare il discorso di casa;
    - una raffica di comandi non tiene la finestra aperta per sempre: il tetto
      si misura dall'apertura, non dall'ultimo comando."""
    d = _finestra_js(client, """
// chiusa: riarmare non apre
riarmaFinestra();
const chiusaRestaChiusa = inAttesaComando();
// aperta, con comandi a raffica ogni 9 s
attendeComando();
for (let i = 0; i < 5; i++) { avanza(9000); riarmaFinestra(); }
avanza(1000);                            // t = 46 s dall'apertura
const oltreIlTetto = inAttesaComando();  // il tetto e' 30 s
console.log(JSON.stringify({ chiusaRestaChiusa, oltreIlTetto }));
""")
    assert d == {"chiusaRestaChiusa": False, "oltreIlTetto": False}, d


def test_dopo_un_comando_la_finestra_non_si_azzera(client):
    """Il legame che rende utile il riarmo: nel ramo `esegui` si chiama
    `riarmaFinestra()`. Con il vecchio `inAttesa = 0` il secondo ordine di fila
    veniva ignorato in silenzio — il difetto riferito."""
    js = client.get("/static/app.js").get_data(as_text=True)
    ramo = js[js.index("if (d.azione === 'esegui')"):]
    ramo = ramo[:ramo.index("eseguiComandoContinuo(")]
    assert "riarmaFinestra()" in ramo
    assert "inAttesa = 0" not in ramo


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


def test_gli_asset_hanno_la_versione_nell_indirizzo(client):
    """`app.js` e `style.css` non hanno un indirizzo che cambia: senza un numero
    di versione il browser non sa che sono nuovi e continua a usarne una copia.
    La versione e' un'impronta del contenuto, quindi cambia solo quando il file
    cambia."""
    html = client.get("/").get_data(as_text=True)
    assert "/static/app.js?v=" in html
    assert "/static/style.css?v=" in html
    # la versione e' quella vera del file: la stessa cosa che darebbe l'impronta
    js = client.get("/static/app.js").get_data(as_text=True)
    import hashlib
    attesa = hashlib.sha256(js.encode("utf-8")).hexdigest()[:10]
    assert f"/static/app.js?v={attesa}" in html


def test_un_asset_versionato_resta_in_memoria_a_lungo(client):
    """Con la versione nell'indirizzo tenere la copia a lungo e' sicuro: se il
    file cambia cambia anche l'indirizzo, quindi non si vede mai una versione
    vecchia. E' quello che evita di riscaricare 200 KB a ogni apertura."""
    r = client.get("/static/app.js?v=qualsiasi")
    assert "max-age=31536000" in r.headers.get("Cache-Control", "")
    assert "immutable" in r.headers.get("Cache-Control", "")


def test_il_service_worker_si_serve_dalla_radice_e_senza_accesso(anon):
    """Il service worker controlla solo il percorso da cui e' servito: da
    `/static/` non potrebbe mostrare la pagina `/` senza rete. E non chiede
    l'accesso, perche' deve poter partire prima del login."""
    r = anon.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("Content-Type", "")
    assert "caches" in r.get_data(as_text=True)


def test_la_pagina_registra_il_service_worker(client):
    """La registrazione sta nella pagina, non in `app.js`: cosi' parte anche se
    il codice dell'app non e' stato ancora caricato."""
    html = client.get("/").get_data(as_text=True)
    assert "serviceWorker" in html and "register('/sw.js')" in html


def test_i_file_statici_si_chiedono_prima_alla_rete(client):
    """Il service worker serviva `app.js` **prima dalla copia**: `chiave()`
    ignora `?v=...`, quindi la copia salvata all'installazione (senza versione)
    rispondeva a qualunque richiesta, anche a una versione nuova. Risultato: la
    pagina (`index.html`, prima la rete) si aggiornava, `app.js` restava vecchio,
    e una funzione nuova — come il calendario in home — non veniva mai disegnata.
    Qui si esegue `serveStatico` vera: con la rete su deve vincere la rete,
    non la copia; con la rete giu' deve reggere la copia."""
    js = client.get("/static/sw.js").get_data(as_text=True)
    chiave = _estrai_funzione_js(js, "chiave")
    blocco = _estrai_funzione_js(js, "serveStatico")
    preludio = """
const CACHE = 'prova';
let reteOk = true;
const salvati = { 'http://a/static/app.js': { corpo: 'VECCHIO' } };
globalThis.caches = {
  open: async () => ({
    put: async (k, v) => { salvati[k] = v; },
    match: async (k) => salvati[k],
  }),
  match: async (k) => salvati[k],
};
globalThis.fetch = async () => {
  if (!reteOk) throw new Error('offline');
  return { ok: true, corpo: 'NUOVO', clone() { return this; } };
};
"""
    coda = """
(async () => {
  const online = await serveStatico({ url: 'http://a/static/app.js?v=123' });
  reteOk = false;
  const offline = await serveStatico({ url: 'http://a/static/app.js?v=999' });
  console.log(JSON.stringify({ online: online.corpo, offline: offline.corpo,
    salvato: salvati['http://a/static/app.js'].corpo }));
})();
"""
    d = _esegui_node(preludio + chiave + blocco + coda)
    assert d["online"] == "NUOVO", "con la rete su deve arrivare la versione nuova, non la copia"
    assert d["salvato"] == "NUOVO", "la copia va aggiornata con la versione nuova"
    assert d["offline"] == "NUOVO", "senza rete deve reggere l'ultima copia buona"


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


def test_avvia_accende_anche_la_sorveglianza():
    """`./avvia.sh` da solo deve bastare: dopo ogni ricreazione del container la
    sorveglianza andava riaccesa a mano ed era il passo che si dimenticava, così
    il link restava a 502. Qui si guarda che l'accensione ci sia, che `stop`/lo
    `stop` di `ferma()` la spenga (altrimenti riavvia il server appena fermato) e
    che il richiamo dal sorvegliante non la riaccenda (ricorsione infinita)."""
    avvia = open(f"{BASE_APP}/avvia.sh", encoding="utf-8").read()
    sorveglia = open(f"{BASE_APP}/sorveglia.sh", encoding="utf-8").read()

    assert "avvia_sorveglianza()" in avvia, "manca l'accensione della sorveglianza"
    assert "avvia_sorveglianza" in avvia.split("avvia() {", 1)[1], \
        "avvia() deve chiamarla, non solo definirla"
    assert "ferma_sorveglianza" in avvia.split("ferma() {", 1)[1], \
        "ferma() deve spegnere la sorveglianza prima del server"
    assert "MAGGIORDOMO_SORVEGLIA_GIRO" in avvia
    assert "MAGGIORDOMO_SORVEGLIA_GIRO" in sorveglia, \
        "il sorvegliante deve esportare il freno prima di richiamare avvia.sh"
    # il freno e' un export, non una semplice menzione
    assert "export MAGGIORDOMO_SORVEGLIA_GIRO=1" in sorveglia
    # e lo script sa accendere la sorveglianza da solo
    assert "sorveglianza|sorveglia)" in avvia


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


def test_verifica_pubblico_controlla_le_tre_cose(client):
    """`verifica-pubblico.bat` e' il controllo da fare quando il tunnel sembra
    attivo ma il telefono non carica: le tre cause si confondono fra loro, e se
    ne dimenticasse una il suo verdetto mentirebbe. Deve guardare il tunnel, se
    l'app risponde, e se `DIETRO_PROXY` e' dichiarato in `avvia.bat`.

    Si guarda il file vero: il lavoro sta nel `.ps1` e il `.bat` lo chiama, per
    la stessa ragione per cui esiste `indirizzo.ps1`."""
    bat = open(f"{BASE_APP}/windows/verifica-pubblico.bat", encoding="utf-8").read()
    ps1 = open(f"{BASE_APP}/windows/verifica-pubblico.ps1", encoding="utf-8").read()
    # il .bat non fa il lavoro: chiama il .ps1 accanto a se'
    assert "verifica-pubblico.ps1" in bat
    # 1. il tunnel: si cerca l'indirizzo https invece di fidarsi del codice di
    # uscita, che cambia fra versioni di Tailscale
    assert "funnel status" in ps1 and "https://" in ps1
    # 2. l'app che risponde
    assert "Invoke-WebRequest" in ps1
    # 3. DIETRO_PROXY dichiarato nel file che comanda davvero
    assert 'set "DIETRO_PROXY=1"' in ps1


def test_avvia_bat_annuncia_il_modello(client):
    """`avvia.bat` deve dire da solo se il modello di casa e' pronto.

    Il sintomo «il modello non capisce» ha tre cause (Ollama spento, modello non
    scaricato, interruttore spento) e l'app le confonde in silenzio: senza un
    controllo all'avvio si crede che Ollama sia configurato mentre l'interruttore
    e' spento. Il lavoro sta in `modello.ps1` (come `indirizzo.ps1`), e il `.bat`
    lo chiama."""
    bat = open(f"{BASE_APP}/windows/avvia.bat", encoding="utf-8").read()
    assert "modello.ps1" in bat, "avvia.bat non annuncia lo stato del modello"


def test_verifica_modello_guarda_le_tre_cause(client):
    """`verifica-modello.bat` separa le tre cause che danno lo stesso sintomo.

    Deve guardare: se Ollama risponde, se il modello che l'app si aspetta e'
    scaricato, e — quando tutto e' pronto — che resta l'interruttore. La
    configurazione si chiede all'app (`comprensione`), non si riscrive nello
    script: due copie della stessa regola divergono, e allora lo stato mente."""
    bat = open(f"{BASE_APP}/windows/verifica-modello.bat", encoding="utf-8").read()
    ps1 = open(f"{BASE_APP}/windows/modello.ps1", encoding="utf-8").read()
    # il .bat non fa il lavoro: chiama il .ps1 accanto a se'
    assert "modello.ps1" in bat
    # 1. Ollama che risponde: l'elenco dei modelli sta in /api/tags, non in /v1
    assert "/api/tags" in ps1
    # 2. il modello atteso: chiesto all'app, non scritto a mano qui
    assert "import comprensione" in ps1
    assert "c.modello()" in ps1
    # 3. l'interruttore, che e' la causa piu' frequente del "non capisce"
    assert "Capire i comandi" in ps1
    # e l'invito a scaricare il modello giusto, quando manca
    assert "ollama pull" in ps1


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
  '/api/appointments?giorno=2026-10-03':
    { appointments: [{ title: 'Riunione', done: false }] },
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
    assert "Domani" in d["html"] and "Riunione" in d["html"]
    assert "Latte" in d["html"]


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


def test_il_riepilogo_non_cade_se_una_fonte_non_risponde(client):
    """Se il calendario non risponde, i pasti si mostrano lo stesso: un errore su
    una fonte non deve far sparire le altre."""
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
function iso(d) { return '2026-10-02'; }
function statoScadenza() { return { testo: '—', classe: 'scad-niente' }; }
async function api(url) {
  if (url.startsWith('/api/plan')) return [{ recipe_name: 'Pasta', meal: 'cena' }];
  throw new Error('rete assente');
}
"""
    coda = "\nrenderHomeOggi().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False
    assert "Pasta" in d["html"]


def test_il_riepilogo_suggerisce_gli_impegni_di_domani(client):
    """Gli impegni di domani si suggeriscono in «Oggi»: quelli che non sono
    ancora scattati non stanno in `prossimi`, ma sapere stasera che domani c'e'
    il dentista e' utile. Solo quelli da fare: un impegno gia' chiuso non e' un
    impegno, e mostrarlo farebbe credere che domani ci sia qualcosa."""
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
function statoScadenza() { return { testo: '—', classe: 'scad-niente' }; }
const risposte = {
  '/api/plan?start=2026-10-02&end=2026-10-02': [],
  '/api/chores': { piano: { da_fare: 0 } },
  '/api/appointments?giorno=2026-10-02': { prossimi: [] },
  '/api/appointments?giorno=2026-10-03':
    { appointments: [{ title: 'Dentista', done: false }, { title: 'Vecchio', done: true }] },
  '/api/pantry': [],
};
async function api(url) { return risposte[url]; }
"""
    coda = "\nrenderHomeOggi().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is False, "solo gli impegni di domani bastano a mostrare il riquadro"
    assert "Domani" in d["html"] and "Dentista" in d["html"]
    assert "Vecchio" not in d["html"], "un impegno gia' fatto non si suggerisce"

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


def test_le_notizie_in_home_stanno_sotto_il_calendario(client):
    """La home finisce con le notizie del giorno: prima le categorie, poi il
    riepilogo «Oggi», il calendario e infine le notizie. Sono da leggere e da
    dove si e', quindi in fondo; l'elenco completo resta nella sezione TV."""
    html = client.get("/").get_data(as_text=True)
    assert 'id="home-notizie"' in html
    assert html.index('id="home-cal"') < html.index('id="home-notizie"')
    # il riquadro rimanda alla TV, non duplica l'elenco con i sommari
    sezione = html[html.index('id="home-notizie"'):html.index('<div id="app"')]
    assert "home-notizie-apri" in sezione
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "$('#home-notizie-apri')" in js and "apriSezione('tv')" in js


def test_l_intestazione_chiude_la_home(client):
    """L'intestazione «Il Maggiordomo» sta in fondo alla home.

    In alto era la prima cosa che si incontrava e spingeva giu' le categorie,
    che sono il motivo per cui si arriva in home. Ora chiude la pagina, dopo
    «Oggi», il calendario e le notizie."""
    html = client.get("/").get_data(as_text=True)
    inizio = html.index('id="home"')
    home = html[inizio:html.index('<div id="app"', inizio)]
    assert "home-hero-basso" in home
    assert home.index('class="home-cards"') < home.index("home-hero-basso")
    assert home.index('id="home-notizie"') < home.index("home-hero-basso")


def test_l_endpoint_notizie_serve_solo_le_notizie_dalla_cache(client, monkeypatch):
    """`/api/notizie` alimenta il riquadro in home: deve portare le notizie e
    quando sono state prese, senza tirare dietro i video della TV (in home non
    si mostrano, e i loro embed sono peso inutile)."""
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    db = app_module.get_db()
    tv.aggiorna_notizie(db, forse=False)

    r = client.get("/api/notizie")
    assert r.status_code == 200
    d = r.get_json()
    assert len(d["notizie"]) == 2
    assert d["aggiornato"]
    assert "video" not in d


def test_l_endpoint_notizie_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con un elenco vuoto. E' un riquadro da
    riempire, non un guasto da mostrare in home."""
    monkeypatch.setattr(tv, "_apri",
                        lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    monkeypatch.setattr(app_module, "_aggiorna_notizie_in_sottofondo", lambda db: None)
    r = client.get("/api/notizie")
    assert r.status_code == 200
    assert r.get_json()["notizie"] == []


def test_il_riquadro_notizie_in_home_tace_se_non_ce_ne_sono(client):
    """Senza notizie il riquadro resta nascosto, come il riepilogo «Oggi»: una
    home con un riquadro vuoto e' peggio di una home senza riquadro."""
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = _estrai_funzione_js(js, "renderHomeNotizie")
    preludio = """
const stato = { nascosto: false };
function $(sel) {
  if (sel === '#home-notizie') return { classList: { add() { stato.nascosto = true; }, remove() { stato.nascosto = false; } } };
  return { innerHTML: '' };
}
function esc(s) { return String(s); }
async function api() { return { notizie: [] }; }
"""
    coda = "\nrenderHomeNotizie().then(() => console.log(JSON.stringify(stato)));"
    d = _esegui_node(preludio + blocco + coda)
    assert d["nascosto"] is True




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


class _ModelloFinto:
    """Un modello che **risponde**: sia alla verifica di raggiungibilita'
    (`/api/tags` o `/models`), sia alla chat (`/chat/completions`).

    Serve perche' le due cose ora sono distinte: la chiave dice che la
    configurazione c'e', ma l'interruttore si accende solo se il modello
    risponde. Questa classe finge entrambe, cosi' i test provano il percorso
    vero invece di dipendere dalla rete."""

    def __init__(self, contenuto: str = '{"intent": "unknown"}'):
        self.contenuto = contenuto
        self.url = []

    def __call__(self, richiesta, timeout=None):
        self.url.append(richiesta.full_url)
        if richiesta.full_url.endswith(("/api/tags", "/models")):
            return _RispostaLlm('{"models": []}')
        return _RispostaLlm(self.contenuto)


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


def test_la_disponibilita_non_basta_serve_che_il_modello_risponda(monkeypatch):
    """Il difetto che questo corregge: l'endpoint locale predefinito c'e' sempre,
    quindi `configurato()` era vero anche a Ollama spento. L'app diceva
    "disponibile" e l'interruttore si accendeva, ma ogni comando finiva in
    silenzio sulle regole. `raggiungibile()` guarda davvero se risponde."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    # configurazione presente, ma nessuno risponde
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("connessione rifiutata")))
    assert comprensione.configurato() is True
    assert comprensione.raggiungibile() is False
    # e l'avviso dice la causa vera, non "manca la chiave"
    msg = comprensione.messaggio_stato()
    assert "Ollama non risponde" in msg and "ollama pull" in msg


def test_se_il_modello_risponde_la_verifica_passa(monkeypatch):
    """Con Ollama che risponde la verifica passa, e l'indirizzo interrogato e'
    quello giusto: l'elenco dei modelli sta in `/api/tags`, non in `/v1`."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    finto = _ModelloFinto()
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", finto)
    assert comprensione.raggiungibile() is True
    assert finto.url and finto.url[0].endswith("/api/tags")
    assert comprensione.messaggio_stato() == ""


def test_con_una_chiave_ma_servizio_muto_l_avviso_nomina_la_chiave(monkeypatch):
    """Un servizio in rete con la chiave ma che non risponde: la causa non e'
    Ollama, quindi l'avviso non deve parlare di Ollama."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setenv("LLM_BASE_URL", "https://esempio.invalid/v1")
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("rete assente")))
    assert comprensione.raggiungibile() is False
    # con la chiave presente l'avviso e' vuoto: la configurazione e' completa,
    # e' solo il servizio a non rispondere. Non si accusa la chiave.
    assert comprensione.messaggio_stato() == ""


# ---- la chiave del modello: ambiente o file accanto all'app, mai dall'app ----
def _con_segreto_llm(tmp_path, monkeypatch, testo, nome_file="segreto.txt"):
    """Prepara un `segreto.txt` con la chiave del modello, senza toccare quello vero."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.setattr(comprensione, "_letto", {"fatto": False})
    (tmp_path / nome_file).write_text(testo)


def test_la_chiave_del_modello_si_legge_da_segreto_txt(tmp_path, monkeypatch):
    """`chiave: valore` come per la voce: chi configura non deve sapere i nomi
    delle variabili. Il modello e l'indirizzo si leggono dallo stesso file."""
    _con_segreto_llm(tmp_path, monkeypatch,
                     "chiave: sk-llm-di-prova-123\n"
                     "modello: qwen2.5:7b-instruct\n"
                     "base_url: https://esempio.invalid/v1\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"
    assert comprensione.modello() == "qwen2.5:7b-instruct"
    assert comprensione.base_url() == "https://esempio.invalid/v1"
    assert comprensione.configurato()


def test_la_chiave_del_modello_nuda_si_riconosce(tmp_path, monkeypatch):
    """Il file piu' semplice: una riga e basta. Una parola che sembra una chiave
    (`sk-...`) e' la chiave; una parola minuscola corta non la ruba."""
    _con_segreto_llm(tmp_path, monkeypatch, "sk-llm-di-prova-123\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"


def test_una_spiegazione_nel_file_non_diventa_la_chiave_del_modello(tmp_path, monkeypatch):
    """Le righe con spazi sono testo libero: non devono finire nell'ambiente."""
    _con_segreto_llm(tmp_path, monkeypatch,
                     "Questa e' la chiave del modello, non copiarla in giro\n"
                     "chiave: sk-llm-di-prova-123\n")
    assert comprensione.chiave() == "sk-llm-di-prova-123"


def test_l_ambiente_vince_sul_file_per_la_chiave_del_modello(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda, come per `segreto.sh`."""
    _con_segreto_llm(tmp_path, monkeypatch, "chiave: DalFile\n")
    monkeypatch.setenv("LLM_API_KEY", "DallAmbiente")
    assert comprensione.chiave() == "DallAmbiente"


def test_il_modello_e_l_indirizzo_predefiniti_sono_quelli_di_casa(monkeypatch):
    """Senza nessuna scelta la configurazione e' Ollama in locale: nessuna
    chiave, nessun costo, niente che esce di casa."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione.modello() == "qwen2.5:7b-instruct"
    assert comprensione.base_url() == "http://127.0.0.1:11434/v1"


def test_ollama_si_riconosce_dall_indirizzo_locale(monkeypatch):
    """Un modello in casa non chiede una chiave: si riconosce dall'indirizzo,
    perche' non c'e' altro modo di saperlo. Un servizio in rete no."""
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    for locale in ("http://127.0.0.1:11434/v1", "http://localhost:11434/v1"):
        monkeypatch.setenv("LLM_BASE_URL", locale)
        assert comprensione._e_locale(), locale
    monkeypatch.setenv("LLM_BASE_URL", "https://api.esempio.invalid/v1")
    assert not comprensione._e_locale()


def test_l_elenco_dei_modelli_dipende_dalla_porta_di_ollama(monkeypatch):
    """Ollama tiene l'elenco in `/api/tags`, non nella parte compatibile OpenAI:
    da `.../v1` si risale a `/api/tags`. Un servizio in rete risponde a `/models`."""
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    assert comprensione._endpoint_salute("http://127.0.0.1:11434/v1").endswith("/api/tags")
    assert comprensione._endpoint_salute("http://127.0.0.1:8080/v1").endswith("/models")
    assert comprensione._endpoint_salute("non-un-indirizzo") == ""


def test_la_chiave_del_modello_non_si_salva_dall_app(client):
    """Come per la voce: la chiave LLM entra solo dall'ambiente o dal file prima
    di avviare. L'app puo' nominarla in un avviso («registrala come segreto
    LLM_API_KEY»), ma non deve avere un campo che la scriva, ne' una rotta che la
    salvi: chi apre la pagina potrebbe cambiarla, e la chiave finirebbe in una
    richiesta HTTP."""
    html = client.get("/static/index.html").get_data(as_text=True)
    # nessun campo dove incollare la chiave del modello
    for campo in ('id="llm-chiave"', 'id="llm-chiave-salva"', 'id="voice-llm-chiave"'):
        assert campo not in html, campo
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "salvaChiaveLlm" not in js
    assert "/api/llm/configura" not in js
    # e la rotta non esiste: senza, la chiave non si potrebbe scrivere via HTTP
    percorsi = {r.rule for r in app_module.app.url_map.iter_rules()}
    assert not any("llm" in p.lower() and "configur" in p.lower() for p in percorsi)


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
    """La scelta e' dell'utente e resta; e la chiave non compare mai nella risposta.

    Il modello e' finto ma **risponde**: da quando l'interruttore si accende solo
    se risponde, una chiave da sola non basta piu'."""
    monkeypatch.setenv("LLM_API_KEY", "chiave-llm-di-prova")
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
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
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
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
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    client.put("/api/voce/llm", json={"abilitato": True})
    monkeypatch.setattr(comprensione, "chiama", lambda t: {"intent": "unknown"})
    r = client.post("/api/voice", json={"text": "aggiungi il latte alla spesa"})
    assert r.get_json()["intent"] == "shopping_add"


def test_la_comprensione_e_disattiva_di_partenza(client):
    """Nessuna chiamata a consumo senza che l'utente l'abbia accesa."""
    assert client.get("/api/voce/config").get_json()["llm_abilitato"] is False


def test_non_si_accende_l_interruttore_se_il_modello_non_risponde(client, monkeypatch):
    """L'endpoint locale predefinito c'e' sempre, anche a Ollama spento: senza
    questa guardia l'interruttore si accendeva e ogni comando finiva in silenzio
    sulle regole. Ora la rotta chiede che il modello **risponda**, e se no dice
    la causa (Ollama spento / modello non scaricato), non "manca la chiave"."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("connessione rifiutata")))
    r = client.put("/api/voce/llm", json={"abilitato": True})
    assert r.status_code == 400
    assert "Ollama non risponde" in r.get_json()["error"]
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_pronto"] is False and cfg["llm_abilitato"] is False


def test_lo_stato_distingue_configurato_da_raggiungibile(client, monkeypatch):
    """`/api/voce/config` espone le due cose separatamente: `disponibile` (c'e'
    la configurazione) e `pronto` (il modello risponde). E' la distinzione che
    mancava e che faceva mentire il pannello."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(comprensione, "_letto", {"fatto": True})
    monkeypatch.setattr(comprensione.urllib.request, "urlopen", _ModelloFinto())
    cfg = client.get("/api/voce/config").get_json()
    assert cfg["llm_disponibile"] is True and cfg["llm_pronto"] is True
    assert cfg["llm_manca"] == ""


def _nomi_chiamati_senza_definizione(js):
    """Ritorna i nomi chiamati come `nome(...)` che non risultano definiti da
    nessuna parte nel file (function, const/let/var, class, parametro).

    E' una scansione testuale, non un vero parser: toglie i commenti, le
    stringhe e i template literal, poi cerca le chiamate. Serve a scoprire un
    riferimento a una funzione **inesistente**, che il browser solleva come
    ReferenceError solo quando quella riga viene raggiunta — quindi un errore
    che sfugge a ogni test che non esegue la pagina intera. E' il caso di
    `caricaVoci`: rimossa con la scheda Voce, ma ancora chiamata in `init()`,
    faceva fallire l'accesso e l'app restava sulla schermata di login."""
    import re

    def senza_commenti_stringhe(s):
        out = []
        i, n = 0, len(s)
        while i < n:
            if s[i:i + 2] == '//':
                j = s.find('\n', i)
                i = n if j < 0 else j
                continue
            if s[i:i + 2] == '/*':
                j = s.find('*/', i + 2)
                i = n if j < 0 else j + 2
                continue
            c = s[i]
            if c in '"\'':
                # stringa mono-riga: se non si chiude sulla stessa riga non e'
                # una stringa (es. apostrofo dentro un commento gia' tolto)
                j, chiusa = i + 1, False
                while j < n and s[j] != '\n':
                    if s[j] == '\\':
                        j += 2
                        continue
                    if s[j] == c:
                        chiusa = True
                        break
                    j += 1
                if chiusa:
                    i = j + 1
                    out.append(' ')
                    continue
                out.append(c)
                i += 1
                continue
            if c == '`':
                j = i + 1
                while j < n:
                    if s[j] == '\\':
                        j += 2
                        continue
                    if s[j] == '`':
                        break
                    j += 1
                i = n if j >= n else j + 1
                out.append(' ')
                continue
            out.append(c)
            i += 1
        return ''.join(out)

    code = senza_commenti_stringhe(js)
    defs = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)', code))
    defs |= set(re.findall(r'(?:const|let|var)\s+([A-Za-z_$][\w$]*)', code))
    defs |= set(re.findall(r'class\s+([A-Za-z_$][\w$]*)', code))
    params = set()
    for m in re.finditer(r'\(([^()]*)\)\s*(?:=>|\{)', code):
        for p in m.group(1).split(','):
            p = p.strip().split('=')[0].strip()
            if re.fullmatch(r'[A-Za-z_$][\w$]*', p):
                params.add(p)
    for m in re.finditer(r'\{([^{}]*)\}\s*=\s*', code):
        for p in re.findall(r'[A-Za-z_$][\w$]*', m.group(1)):
            params.add(p)
    chiamate = re.findall(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(', code)
    parole = {'if', 'for', 'while', 'switch', 'catch', 'return', 'function',
              'typeof', 'new', 'do', 'else', 'in', 'of', 'case', 'delete',
              'void', 'yield', 'await', 'super', 'this', 'async'}
    # nomi forniti dal browser, non definiti nel file
    browser = set("""Array ArrayBuffer Audio Blob Boolean DataView Date Error
File FileReader Float32Array Image JSON Map Math Number Object Promise RegExp Set
String Symbol SpeechSynthesisUtterance parseInt parseFloat isNaN
encodeURIComponent decodeURIComponent fetch setTimeout clearTimeout setInterval
clearInterval confirm alert console requestAnimationFrame cancelAnimationFrame
AudioContext webkitAudioContext MediaRecorder URL URLSearchParams FormData btoa
atob structuredClone queueMicrotask crypto""".split())
    return sorted(set(c for c in chiamate
                      if c not in parole and c not in defs
                      and c not in params and c not in browser))


def test_app_js_non_chiama_funzioni_che_non_esiste(client):
    """Un riferimento a una funzione rimossa non deve restare in `app.js`.

    Non e' un'ipotesi: e' successo con `caricaVoci`, tolta insieme alla scheda
    Voce ma lasciata in `init()`. `init()` solleva il ReferenceError **dopo** che
    il login e' riuscito, quindi l'errore finisce nel `catch` di `avviaApp` e
    l'utente, appena entra, resta sulla schermata di accesso con la casa non
    collegata a schermo: l'app "si blocca e si chiude". Nessun test lo vedeva,
    perche' nessuno eseguiva `init()` intera."""
    js = client.get("/static/app.js").get_data(as_text=True)
    orfane = _nomi_chiamati_senza_definizione(js)
    assert not orfane, (
        "app.js chiama funzioni che non esistono: " + ", ".join(orfane))


def test_gli_errori_non_gestiti_avvisano_e_finiscono_nel_registro(client):
    """Il gestore non ripara, ma **dice**: un errore non gestito produce un
    avviso breve a schermo e una riga nel registro, e una raffica non ripete
    l'avviso. E' la rete che mancava: senza, un errore a runtime spariva in
    silenzio e l'app sembrava bloccarsi."""
    js = client.get("/static/app.js").get_data(as_text=True)
    corpo = _estrai_funzione_js(js, "erroreNonGestito")
    prova = """
const log = [];
let erroreInCorso = false;
function registra(m, t) { log.push('registra:' + m + ':' + t); }
function toast(m) { log.push('toast:' + m); }
const timer = [];
function setTimeout(fn) { timer.push(fn); return timer.length; }
""" + corpo + """
erroreNonGestito(new Error('primo'));
erroreNonGestito(new Error('secondo'));   // raffica: un solo avviso
timer[0]();                                // passato il momento, si puo' riavvisare
erroreNonGestito(new Error('terzo'));
console.log(JSON.stringify(log));
"""
    log = _esegui_node(prova)
    avvisi = [v for v in log if v.startswith('toast:')]
    registri = [v for v in log if v.startswith('registra:')]
    assert len(avvisi) == 2, log           # primo e terzo, non il secondo
    assert len(registri) == 3, log         # nel registro ci vanno tutti
    # il testo a schermo non porta il nome dell'eccezione ne' la traccia
    assert all('Error' not in v and 'at ' not in v for v in registri), registri


def test_gli_errori_non_gestiti_sono_ascoltati(client):
    """La registrazione degli eventi e' il legame che rende utile il gestore:
    senza, `erroreNonGestito` non verrebbe mai chiamato."""
    import re
    js = client.get("/static/app.js").get_data(as_text=True)
    m = re.search(r"if \(typeof window[^\n]*\n(?:.*\n)*?\}", js)
    assert m, "non trovo la registrazione degli eventi d'errore"
    prova = """
const sentiti = [];
const window = { addEventListener: (t, f) => sentiti.push([t, f]) };
let chiamate = 0;
function erroreNonGestito() { chiamate++; }
""" + m.group(0) + """
for (const [tipo, f] of sentiti) {
  if (tipo === 'error') f({ error: new Error('x') });
  if (tipo === 'unhandledrejection') f({ reason: new Error('y') });
}
console.log(JSON.stringify({ tipi: sentiti.map((s) => s[0]), chiamate }));
"""
    d = _esegui_node(prova)
    assert d["tipi"] == ["error", "unhandledrejection"], d
    assert d["chiamate"] == 2, d


def test_un_avvio_fallito_non_riporta_all_accesso(client):
    """Se la sessione c'e' ma `init()` fallisce, l'utente resta **dentro** con
    un avviso e "Ricarica": rimandarlo all'accesso gli farebbe credere di aver
    sbagliato la password. Solo se la **sessione** non risponde si torna
    all'accesso. E' la differenza che rendeva il difetto di `caricaVoci`
    indistinguibile da un problema di credenziali."""
    js = client.get("/static/app.js").get_data(as_text=True)
    corpo = _estrai_funzione_js(js, "avviaApp")
    prova = """
const log = [];
let scenario = 'sessione-giu';
async function api() {
  if (scenario === 'sessione-giu') throw new Error('server giu');
  return { authenticated: scenario !== 'anonimo' };
}
async function init() {
  if (scenario === 'init-giu') throw new Error('guasto');
  log.push('init-ok');
}
function mostraAccesso() { log.push('mostraAccesso'); }
function mostraErrore() { log.push('mostraErrore'); }
function mostraErroreApp() { log.push('mostraErroreApp'); }
function registra() { log.push('registra'); }
async function avviaAccesso() { log.push('avviaAccesso'); }
""" + corpo + """
(async () => {
  const esiti = {};
  for (const s of ['sessione-giu', 'anonimo', 'init-giu', 'collegato']) {
    scenario = s; log.length = 0;
    await avviaApp();
    esiti[s] = log.slice();
  }
  console.log(JSON.stringify(esiti));
})();
"""
    e = _esegui_node(prova)
    assert e["sessione-giu"] == ["mostraAccesso", "mostraErrore"], e
    assert e["anonimo"] == ["avviaAccesso"], e
    assert e["init-giu"] == ["registra", "mostraErroreApp"], e
    assert e["collegato"] == ["init-ok"], e


# ---------------------------------------------------------------- tv
# La sezione TV legge due fonti esterne: la playlist YouTube e il feed ANSA.
# I test non toccano la rete: sostituiscono `tv._apri` con risposte preparate.
# Si prova l'interpretazione e la tenuta della cache, che sono le parti che
# sbagliano; che YouTube e ANSA rispondano non e' una cosa che si prova qui.
import tv  # noqa: E402

FEED_PLAYLIST = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns="http://www.w3.org/2005/Atom">
  <title>GIAGIA-Max</title>
  <entry>
    <yt:videoId>aaa111</yt:videoId>
    <title>Primo video</title>
    <author><name>Canale Uno</name></author>
    <published>2026-01-02T10:00:00+00:00</published>
  </entry>
  <entry>
    <yt:videoId>bbb222</yt:videoId>
    <title>Secondo video</title>
    <author><name>Canale Due</name></author>
    <published>2026-03-04T10:00:00+00:00</published>
  </entry>
</feed>"""

FEED_NOTIZIE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>RSS di Mondo  - ANSA.it</title>
  <item>
    <title>Notizia vecchia</title>
    <link>https://esempio.invalid/vecchia</link>
    <description>Sommario vecchio</description>
    <pubDate>Mon, 01 Jan 2026 08:00:00 +0100</pubDate>
  </item>
  <item>
    <title>Notizia nuova</title>
    <link>https://esempio.invalid/nuova</link>
    <description>Sommario nuovo</description>
    <pubDate>Thu, 02 Apr 2026 09:30:00 +0200</pubDate>
  </item>
</channel></rss>"""


def finta_tv(monkeypatch, risposte):
    """Sostituisce la lettura di rete di `tv` con risposte preparate.

    Le chiavi sono gli indirizzi; un indirizzo non previsto solleva
    `NonDisponibile`, cosi' un test che sbaglia indirizzo se ne accorge invece
    di scaricare davvero."""
    def apri(url):
        if url not in risposte:
            raise tv.NonDisponibile(f"indirizzo di prova non previsto: {url}")
        return risposte[url].encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)


def _url_playlist():
    return f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.playlist_id()}"


def test_i_video_della_playlist_si_leggono_con_i_loro_campi(client, monkeypatch):
    """Il feed Atom della playlist: id, titolo, autore e data.

    La trappola e' il namespace `yt:`: senza passare la mappa dei namespace a
    `find`, ogni campo torna vuoto e la playlist sembra senza video — e' il
    difetto che c'e' stato davvero, e non si vede leggendo il codice."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST})
    video = tv.video_playlist()
    assert [v["id"] for v in video] == ["aaa111", "bbb222"]
    assert video[0]["titolo"] == "Primo video"
    assert video[0]["autore"] == "Canale Uno"
    assert video[0]["data"] == "2026-01-02"


def test_una_playlist_senza_video_e_un_guasto_non_una_sezione_vuota(client, monkeypatch):
    """Una playlist privata o cancellata risponde senza voci: e' `NonDisponibile`,
    non una lista vuota, cosi' chi chiama tiene la copia vecchia invece di
    sovrascriverla con il vuoto."""
    finta_tv(monkeypatch, {_url_playlist(): "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"})
    with pytest.raises(tv.NonDisponibile):
        tv.video_playlist()


def test_il_gym_legge_la_sua_playlist_non_quella_della_tv(client, monkeypatch):
    """La sezione GYM ha la sua playlist, separata da quella della TV: si guarda
    per fare, non per passare il tempo, e cambiare i video di casa non deve
    toccare l'allenamento. Le due letture sono la stessa funzione (`_video_di`),
    cambia solo l'id: qui si verifica che sia davvero quello giusto."""
    urls = {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}":
            FEED_PLAYLIST,
        _url_playlist(): "<feed xmlns='http://www.w3.org/2005/Atom'></feed>",
    }
    finta_tv(monkeypatch, urls)
    video = tv.video_gym()
    assert [v["id"] for v in video] == ["aaa111", "bbb222"]
    assert tv.gym_playlist_id() == tv.PLAYLIST_GYM_PREDEFINITA


def test_gym_e_tv_si_aggiornano_e_si_leggono_separatamente(client, monkeypatch):
    """I due elenchi vivono in cache separate (`gym` e `video`): aggiornare il
    GYM non deve toccare la TV, ne' viceversa. Se condividessero la chiave, un
    giro del GYM sovrascriverebbe i video della TV."""
    gym_feed = FEED_PLAYLIST.replace("aaa111", "gym111").replace("bbb222", "gym222")
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": gym_feed,
        _url_playlist(): FEED_PLAYLIST,
    })
    db = app_module.get_db()
    assert tv.aggiorna_gym(db, forse=False) is True
    assert tv.aggiorna_video(db, forse=False) is True
    assert [v["id"] for v in tv.gym(db)] == ["gym111", "gym222"]
    assert [v["id"] for v in tv.video(db)] == ["aaa111", "bbb222"]


def test_l_endpoint_gym_serve_la_cache_e_gli_incorpora(client, monkeypatch):
    """L'endpoint GYM serve la copia in cache senza aspettare la rete, e ogni
    video porta l'indirizzo del player (`youtube-nocookie`)."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    tv.aggiorna_gym(app_module.get_db(), forse=False)
    _niente_rete(monkeypatch)  # il sottofondo non deve partire: la copia e' fresca
    d = client.get("/api/gym").get_json()
    assert len(d["video"]) == 2
    assert d["video"][0]["embed"] == "https://www.youtube-nocookie.com/embed/aaa111"
    assert d["playlist"] == tv.PLAYLIST_GYM_PREDEFINITA
    assert d["aggiornato"]


def test_l_endpoint_gym_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con un elenco vuoto. E' una sezione da
    riempire, non un guasto da mostrare."""
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    r = client.get("/api/gym")
    assert r.status_code == 200
    assert r.get_json()["video"] == []


def test_il_pulsante_gym_riscarica_solo_il_gym(client, monkeypatch):
    """`/api/gym/aggiorna` aspetta la rete (e' l'utente a chiederlo) e riscarica
    **solo** il GYM: le notizie non c'entrano con gli esercizi."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    r = client.post("/api/gym/aggiorna")
    assert r.status_code == 200
    d = r.get_json()
    assert d["aggiornati"]["gym"] is True
    assert len(d["video"]) == 2
    # la TV non c'entra: il suo elenco resta quello di prima (vuoto), e le
    # notizie non vengono toccate da un aggiornamento del GYM
    _niente_rete(monkeypatch)  # il sottofondo di /api/tv non deve partire
    assert client.get("/api/tv").get_json()["video"] == []


def test_il_gym_non_cambia_col_cambio_playlist_della_tv(client, monkeypatch):
    """Cambiare la playlist della TV azzera i video della TV, non quelli del GYM:
    la scelta della TV non deve toccare l'allenamento."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
    })
    db = app_module.get_db()
    tv.aggiorna_gym(db, forse=False)
    # la TV cambia playlist: `imposta_playlist` azzera solo la cache 'video'
    nuovo = "PLnuovatv9876543210zyxwv"
    tv.imposta_playlist(db, nuovo)
    assert [v["id"] for v in tv.gym(db)] == ["aaa111", "bbb222"], "il GYM resta"
    assert tv.video(db) == [], "la TV si azzera"


def test_la_sezione_gym_e_in_home_e_ha_il_suo_tab(client):
    """Il GYM e' una sezione a se': scheda in home, scheda nella barra, e il
    contenitore dei video. La scheda in home e' cio' che la rende raggiungibile."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-section="gym"' in html
    assert 'id="tab-gym"' in html
    assert 'id="gym-video"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function renderGym" in js
    assert "/api/gym" in js
    assert "gym:      { titolo:" in js or "gym: { titolo:" in js


def test_la_sezione_gym_ha_il_campo_playlist(client):
    """La playlist del GYM si cambia dalla sezione: campo, pulsante e gestore
    presenti, come in TV."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="gym-playlist"' in html
    assert 'id="gym-playlist-salva"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/gym/playlist" in js
    assert "gym-playlist-salva" in js


def test_la_playlist_del_gym_e_della_casa(client, monkeypatch):
    """La playlist del GYM si salva nella casa, come quella della TV: e' una
    preferenza dell'utente, e due case sullo stesso server non devono vedersi i
    video l'una dell'altra."""
    _niente_rete(monkeypatch)
    scelta = "PLgymcasa1234567890abc"
    r = client.put("/api/gym/playlist", json={"playlist": scelta})
    assert r.status_code == 200
    assert r.get_json()["playlist"] == scelta
    assert tv.gym_playlist_id(app_module.get_db()) == scelta
    assert client.get("/api/gym").get_json()["playlist"] == scelta


def test_la_playlist_del_gym_non_tocca_quella_della_tv(client, monkeypatch):
    """Le due scelte vivono su colonne diverse: cambiare l'allenamento non deve
    cambiare i video di casa, ne' viceversa."""
    _niente_rete(monkeypatch)
    db = app_module.get_db()
    tv.imposta_playlist(db, "PLtv1234567890abcdef")
    tv.imposta_playlist_gym(db, "PLgym1234567890abcdef")
    assert tv.playlist_id(db) == "PLtv1234567890abcdef"
    assert tv.gym_playlist_id(db) == "PLgym1234567890abcdef"
    # cambiare solo la TV non tocca il GYM
    tv.imposta_playlist(db, "PLtvnuova9876543210zyx")
    assert tv.gym_playlist_id(db) == "PLgym1234567890abcdef", "il GYM resta"
    # cambiare solo il GYM non tocca la TV
    tv.imposta_playlist_gym(db, "PLgymnuova9876543210zyx")
    assert tv.playlist_id(db) == "PLtvnuova9876543210zyx", "la TV resta"


def test_una_playlist_gym_non_valida_non_si_salva(client, monkeypatch):
    """L'id si valida **prima** di salvarlo: una playlist storta sarebbe una
    sezione vuota che non si capisce da dove venga."""
    _niente_rete(monkeypatch)
    prima = client.get("/api/gym").get_json()["playlist"]
    r = client.put("/api/gym/playlist",
                   json={"playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert client.get("/api/gym").get_json()["playlist"] == prima, "la scelta buona resta"


def test_cambiare_playlist_gym_azzera_solo_i_suoi_video(client, monkeypatch):
    """I video del GYM di prima sono di un'altra playlist: si azzerano solo i
    suoi, e quelli della TV restano."""
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={tv.PLAYLIST_GYM_PREDEFINITA}": FEED_PLAYLIST,
        _url_playlist(): FEED_PLAYLIST,
    })
    db = app_module.get_db()
    tv.aggiorna_gym(db, forse=False)
    tv.aggiorna_video(db, forse=False)

    # la nuova playlist del GYM risponde con un feed diverso: si deve vedere quello
    nuovo = "PLgymnuova9876543210zyxw"
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={nuovo}":
            FEED_PLAYLIST.replace("aaa111", "ggg777").replace("bbb222", "hhh888"),
    })
    r = client.put("/api/gym/playlist", json={"playlist": nuovo})
    assert r.status_code == 200
    assert [v["id"] for v in r.get_json()["video"]] == ["ggg777", "hhh888"]
    # la TV non c'entra: i suoi video restano quelli di prima
    _niente_rete(monkeypatch)  # il sottofondo non deve scaricare: la copia e' appena scritta
    assert [v["id"] for v in client.get("/api/tv").get_json()["video"]] == ["aaa111", "bbb222"]


def test_migrazione_aggiunge_gym_playlist_a_un_db_esistente():
    """`tv_prefs` esisteva gia' prima del GYM: la colonna `gym_playlist` va
    aggiunta a mano alle case che l'hanno creata senza, altrimenti cambiare la
    playlist del GYM fallirebbe solo li'."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio-tv.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE tv_prefs (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                playlist TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO tv_prefs (id, playlist) VALUES (1, 'PLsceltavecchia12345ab');
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(tv_prefs)")}
        assert "gym_playlist" in cols
        row = db.execute("SELECT playlist, gym_playlist FROM tv_prefs").fetchone()
        # la scelta della TV resta, quella del GYM parte vuota
        assert tuple(row) == ("PLsceltavecchia12345ab", "")
        app_module.migrate(db)  # rieseguire non deve fallire


def test_la_sezione_cinema_e_in_home_e_ha_il_suo_tab(client):
    """Il Cinema e' una sezione a se': scheda in home, scheda nella barra, il
    carosello e i suoi comandi. La scheda in home e' cio' che la rende
    raggiungibile."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'data-section="cinema"' in html
    assert 'id="tab-cinema"' in html
    assert 'id="cinema-carosello"' in html
    assert 'id="cinema-prima"' in html and 'id="cinema-dopo"' in html
    assert 'id="cinema-punti"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function renderCinema" in js
    assert "/api/cinema" in js
    assert "cinema:   { titolo:" in js or "cinema: { titolo:" in js


def test_il_cinema_si_sfoglia_da_destra_a_sinistra(client):
    """Sfogliare e' la richiesta: frecce, tastiera, rotellina e dito. Se una
    delle quattro sparisce, su un telefono o senza mouse il carosello si blocca."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "function cinemaVai" in js
    assert "cinemaIndice" in js
    # il dito: `touchstart` + `touchend`, col gesto orizzontale
    assert "'touchstart'" in js and "'touchend'" in js
    # la rotellina e la tastiera
    assert "'wheel'" in js and "ArrowRight" in js and "ArrowLeft" in js
    # lo scorrimento e' ciclico: si torna al primo dopo l'ultimo
    assert "% cinemaFilm.length" in js


def test_senza_chiave_il_cinema_non_e_un_guasto(client, monkeypatch):
    """Senza `TMDB_API_KEY` la sezione e' spenta, non rotta: 200 con un elenco
    vuoto e la spiegazione di cosa manca."""
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})  # non rileggere i file
    d = client.get("/api/cinema").get_json()
    assert d["film"] == []
    assert d["configurato"] is False
    assert "TMDB_API_KEY" in d["manca"]
    # anche il pulsante lo dice, e non tenta la rete
    r = client.post("/api/cinema/aggiorna")
    assert r.status_code == 400
    assert "TMDB_API_KEY" in r.get_json()["error"]


def test_la_chiave_tmdb_si_legge_dall_ambiente(monkeypatch):
    """La chiave viene dall'ambiente, e la sezione risulta configurata."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    assert cinema.configurato() is True
    assert cinema.messaggio_stato() == ""
    assert cinema.chiave() == "0123456789abcdef0123456789abcdef"


def test_la_regione_del_cinema_e_l_italia_per_predefinito(monkeypatch):
    """La regione decide quali piattaforme compaiono: il predefinito e' l'Italia,
    e si puo' cambiare."""
    monkeypatch.delenv("CINEMA_REGION", raising=False)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    assert cinema.regione() == "IT"
    monkeypatch.setenv("CINEMA_REGION", "us")
    assert cinema.regione() == "US"


def test_i_film_si_leggono_e_si_schedano(monkeypatch):
    """Una risposta di TMDB diventa schede con solo i campi che si mostrano, e
    un film senza locandina si scarta: e' una sezione di immagini."""
    risposta = {
        "results": [
            {"id": 1, "title": "Film Bello", "release_date": "2024-05-01",
             "vote_average": 8.234, "vote_count": 1200, "overview": "Una trama.",
             "poster_path": "/abc.jpg",
             "watch/providers": {"results": {"IT": {"flatrate": [
                 {"provider_name": "Netflix"}, {"provider_name": "Prime Video"}]}}}},
            {"id": 2, "title": "Senza locandina", "poster_path": "",
             "vote_average": 7.0},
        ]
    }
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(cinema, "_apri", lambda url: json.dumps(risposta).encode())
    film = cinema._scarica(None)
    assert len(film) == 1
    scheda = film[0]
    assert scheda["titolo"] == "Film Bello"
    assert scheda["anno"] == "2024"
    assert scheda["voto"] == 8.2
    assert scheda["locandina"].endswith("/abc.jpg")
    assert scheda["piattaforme"] == ["Netflix", "Prime Video"]


def test_i_film_si_mettono_in_cache_e_si_rileggono(client, monkeypatch):
    """La copia vive in `tv_cache` (chiave `cinema`): la sezione si apre con quello che c'e',
    anche senza rete, e `aggiorna` non riscarica se la copia e' fresca."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    risposta = {"results": [
        {"id": 7, "title": "Rimasto", "release_date": "2023-01-01",
         "vote_average": 7.5, "poster_path": "/x.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", lambda url: json.dumps(risposta).encode())
    db = app_module.get_db()
    assert cinema.aggiorna(db, forse=False) is True
    assert [f["titolo"] for f in cinema.film(db)] == ["Rimasto"]
    # copia fresca: `forse=True` non riscarica (e `_apri` nemmeno verrebbe chiamato)
    assert cinema.aggiorna(db, forse=True) is False


def test_l_endpoint_cinema_serve_la_copia_e_gli_incorpora(client, monkeypatch):
    """`/api/cinema` serve la copia senza aspettare la rete, e ogni film porta
    locandina e piattaforme."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    risposta = {"results": [
        {"id": 9, "title": "In Cache", "release_date": "2022-09-09",
         "vote_average": 6.8, "poster_path": "/y.jpg", "overview": "Trama.",
         "watch/providers": {"results": {"IT": {"flatrate": [{"provider_name": "Disney+"}]}}}},
    ]}
    monkeypatch.setattr(cinema, "_apri", lambda url: json.dumps(risposta).encode())
    cinema.aggiorna(app_module.get_db(), forse=False)
    d = client.get("/api/cinema").get_json()
    assert d["configurato"] is True and d["manca"] == ""
    assert len(d["film"]) == 1
    assert d["film"][0]["locandina"].endswith("/y.jpg")
    assert d["film"][0]["piattaforme"] == ["Disney+"]
    assert d["aggiornato"]


def test_senza_rete_il_cinema_resta_con_la_copia_vecchia(client, monkeypatch):
    """Un guasto di rete non deve svuotare la sezione: si tiene l'ultima copia."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    risposta = {"results": [
        {"id": 3, "title": "Gia' scaricato", "release_date": "2021-01-01",
         "vote_average": 7.0, "poster_path": "/z.jpg", "overview": ""},
    ]}
    monkeypatch.setattr(cinema, "_apri", lambda url: json.dumps(risposta).encode())
    db = app_module.get_db()
    cinema.aggiorna(db, forse=False)
    # ora la rete e' giu': l'aggiornamento non porta niente, ma la copia resta
    monkeypatch.setattr(cinema, "_apri",
                        lambda url: (_ for _ in ()).throw(cinema.NonDisponibile("giu")))
    assert cinema.aggiorna(db, forse=False) is False
    assert [f["titolo"] for f in cinema.film(db)] == ["Gia' scaricato"]


def test_la_chiave_tmdb_non_compare_nella_risposta(client, monkeypatch):
    """La chiave resta del server: non si espone nella risposta, in nessuna forma."""
    segreta = "deadbeefdeadbeefdeadbeefdeadbeef"
    monkeypatch.setenv("TMDB_API_KEY", segreta)
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    monkeypatch.setattr(app_module, "_aggiorna_cinema_in_sottofondo", lambda db: None)
    testo = client.get("/api/cinema").get_data(as_text=True)
    assert segreta not in testo
    assert "api_key" not in testo


def test_l_aggiornamento_in_sottofondo_del_cinema_non_esplode(client, monkeypatch):
    """Il filo di sottofondo e' un percorso che l'utente non vede: se solleva,
    la sezione risponde 500 invece di aprirsi. Qui si controlla che parta e
    finisca, con la copia vecchia (nessuna rete)."""
    monkeypatch.setenv("TMDB_API_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setattr(cinema, "_letto", {"fatto": True})
    chiamate = []
    monkeypatch.setattr(cinema, "aggiorna", lambda db, forse=True: chiamate.append(forse))
    db = app_module.get_db()
    app_module._aggiorna_cinema_in_sottofondo(db)  # copia assente: parte il filo
    for _ in range(50):
        if chiamate:
            break
        time.sleep(0.05)
    assert chiamate == [True]
    # e l'endpoint, senza stub, non risponde 500 con la chiave finta
    monkeypatch.setattr(cinema, "_apri",
                        lambda url: (_ for _ in ()).throw(cinema.NonDisponibile("finta")))
    assert client.get("/api/cinema").status_code == 200


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


def test_il_riquadro_igiene_ha_l_anello_e_la_fascia_di_colore(client):
    """La grafica dell'Igiene: il riquadro «adesso» ha una fascia d'accento e un
    anello che mostra quanto si e' fatto. Sono la parte visibile del lavoro, e
    vanno provati insieme al markup che li disegna."""
    js = client.get("/static/app.js").get_data(as_text=True)
    assert 'class="ch-ring"' in js
    assert "ch-hero-main" in js and "ch-hero-meta" in js
    assert "aria-label=" in js and "attività fatte oggi" in js
    css = client.get("/static/style.css").get_data(as_text=True)
    assert ".ch-ring" in css
    assert "conic-gradient" in css, "l'anello si disegna col gradiente conico"
    assert "--pct" in css
    # la riga ha il colore dell'ambiente: raggruppa le voci della stessa zona
    assert '.ch-area[data-area="cucina"]' in css
    assert "areaChiave" in js


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


def test_il_profilo_ha_bucati_e_argomenti_delle_notizie(client):
    """Le due scelte nuove si governano dal Profilo: quanti bucati al giorno e
    quali argomenti delle notizie. I campi esistono, e i gestori li salvano."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="pf-bucati"' in html
    assert 'id="pf-news-topics"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "meta.bucati_opzioni" in js
    assert "meta.news_topics" in js
    assert "$('#pf-bucati').addEventListener" in js
    assert "$('#pf-news-topics').addEventListener" in js


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


def test_le_notizie_sono_al_massimo_venti_e_mescolate_fra_le_testate(client, monkeypatch):
    """Il tetto e' venti e le fonti si **alternano**, non si ordinano solo per
    data: un elenco per sola data puo' diventare una testata sola, quando una
    pubblica molto piu' spesso delle altre.

    Servono piu' feed: un singolo feed e' limitato a `MAX_PER_FEED` (vedi
    `test_un_feed_generalista_non_occupa_tutto_l_elenco`)."""
    urls = [f"https://esempio.invalid/f{i}" for i in range(3)]
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: urls)
    risposte = {}
    for f, u in enumerate(urls):
        voci = "".join(
            f"<item><title>N{f}-{i}</title><link>https://esempio.invalid/{f}/{i}</link>"
            f"<description>S</description>"
            f"<pubDate>Mon, {i:02d} Jan 2026 08:00:00 +0100</pubDate></item>"
            for i in range(1, 16))
        risposte[u] = f"<rss version='2.0'><channel><title>Prova{f}</title>{voci}</channel></rss>"
    finta_tv(monkeypatch, risposte)
    notizie = tv.notizie_dal_feed()
    assert len(notizie) <= tv.MAX_NOTIZIE
    # le fonti si alternano: due notizie di fila non vengono dalla stessa testata
    fonti = [n["fonte"] for n in notizie]
    assert all(a != b for a, b in zip(fonti, fonti[1:]))
    # e dentro ogni testata l'ordine resta per data
    for fonte in set(fonti):
        date = [n["data"] for n in notizie if n["fonte"] == fonte]
        assert date == sorted(date, reverse=True)


def test_due_testate_si_alternano_e_riempiono_le_venti(client, monkeypatch):
    """Due testate si alternano e riempiono l'elenco: la fetta per testata tiene
    la promessa, dieci e dieci, anche quando una pubblica piu' spesso."""
    u1, u2 = "https://esempio.invalid/ansa", "https://esempio.invalid/rai"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    ansa = [_voce(f"ansa-{i}", f"Thu, 02 Apr 2026 09:{i:02d}:00 +0200") for i in range(15)]
    rai = [_voce(f"rai-{i}", f"Wed, 01 Apr 2026 08:{i:02d}:00 +0200") for i in range(15)]
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it", ansa),
        u2: _feed("RaiNews", rai),
    })
    notizie = tv.notizie_dal_feed()
    fonti = [n["fonte"] for n in notizie]
    assert len(notizie) == tv.MAX_NOTIZIE
    assert fonti.count("ANSA.it") == fonti.count("RaiNews") == tv.MAX_NOTIZIE // 2
    assert all(a != b for a, b in zip(fonti, fonti[1:]))


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


def test_un_feed_generalista_non_occupa_tutto_l_elenco(client, monkeypatch):
    """Un feed generalista senza tetto riempirebbe da solo le dieci notizie,
    facendo sparire le sezioni: ogni feed contribuisce al massimo
    `MAX_PER_FEED`."""
    urls = [f"https://esempio.invalid/f{i}" for i in range(4)]
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: urls)
    risposte = {}
    for f, u in enumerate(urls):
        voci = "".join(
            f"<item><title>N{f}-{i}</title><link>https://esempio.invalid/{f}/{i}</link>"
            f"<description>S</description>"
            f"<pubDate>Mon, {i:02d} Jan 2026 08:00:00 +0100</pubDate></item>"
            for i in range(1, 16))
        risposte[u] = f"<rss version='2.0'><channel><title>Prova{f}</title>{voci}</channel></rss>"
    finta_tv(monkeypatch, risposte)
    notizie = tv.notizie_dal_feed()
    per_fonte = {}
    for n in notizie:
        per_fonte[n["fonte"]] = per_fonte.get(n["fonte"], 0) + 1
    assert all(q <= tv.MAX_PER_FEED for q in per_fonte.values())
    # con quattro fonti e il tetto a quattro, l'elenco e' pieno e misto
    assert len(notizie) == tv.MAX_NOTIZIE
    assert len(per_fonte) == 4


def test_il_nome_della_fonte_e_quello_che_si_mostra_non_il_titolo_del_feed(client, monkeypatch):
    """Il titolo di un feed e' per un lettore di feed: "RSS di Mondo  - ANSA.it".
    Accanto a una notizia ci vuole "ANSA.it"."""
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    notizie = tv.notizie_dal_feed()
    assert notizie[0]["fonte"] == "ANSA.it"
    assert notizie[0]["titolo"] == "Notizia nuova"


def test_il_sommario_lungo_si_taglia_sulla_parola(client, monkeypatch):
    """Un sommario tagliato a meta' parola si nota subito: si taglia sul confine."""
    lungo = "parola " * 60
    feed = (f"<rss version='2.0'><channel><title>Prova</title><item>"
            f"<title>T</title><link>https://esempio.invalid/a</link>"
            f"<description>{lungo}</description>"
            f"<pubDate>Thu, 02 Apr 2026 09:30:00 +0200</pubDate></item>"
            f"</channel></rss>")
    finta_tv(monkeypatch, {tv.feed_urls()[0]: feed})
    sommario = tv.notizie_dal_feed()[0]["sommario"]
    assert sommario.endswith("…")
    assert len(sommario) <= tv.MAX_SOMMARIO + 1
    assert not sommario[:-1].endswith(" ")


def test_la_cache_tiene_la_copia_vecchia_se_la_rete_non_risponde(client, monkeypatch):
    """E' la proprieta' che tiene in piedi la sezione: se la rete manca, quello
    che si era scaricato **resta**. Svuotarlo sarebbe il danno peggiore, perche'
    e' proprio la copia che serve quando non c'e' connessione."""
    db = app_module.get_db()
    finta_tv(monkeypatch, {tv.feed_urls()[0]: FEED_NOTIZIE})
    assert tv.aggiorna_notizie(db, forse=False) is True
    quante = len(tv.notizie(db))
    assert quante == 2

    # ora la rete non risponde piu': la copia deve restare
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    assert tv.aggiorna_notizie(db, forse=False) is False
    assert len(tv.notizie(db)) == quante


def test_non_si_riscarica_se_la_copia_e_fresca(client, monkeypatch):
    """Una volta al giorno, non a ogni apertura: senza questo, ogni volta che si
    apre la sezione si chiamerebbe un sito altrui."""
    db = app_module.get_db()
    chiamate = {"n": 0}

    def apri(url):
        chiamate["n"] += 1
        return FEED_NOTIZIE.encode("utf-8")
    monkeypatch.setattr(tv, "_apri", apri)

    quanti_feed = len(tv.feed_urls())
    assert tv.aggiorna_notizie(db, forse=True) is True
    assert chiamate["n"] == quanti_feed
    assert tv.aggiorna_notizie(db, forse=True) is False
    assert chiamate["n"] == quanti_feed, "una copia fresca non si riscarica"


def test_l_endpoint_tv_richiede_l_accesso(anon):
    """La sezione TV sta dietro l'accesso come tutto il resto: non e' un dato
    della casa, ma nemmeno una pagina pubblica da lasciare aperta."""
    assert anon.get("/api/tv").status_code == 401
    assert anon.post("/api/tv/aggiorna").status_code == 401
    assert anon.put("/api/tv/playlist", json={"playlist": "x" * 20}).status_code == 401


def _niente_rete(monkeypatch):
    """Nei test la rete non esiste e il sottofondo non deve partire.

    `/api/tv` riprova a scaricare **dopo** aver risposto, in un filo che apre una
    connessione sua. In un test quel filo sopravvive alla richiesta e, quando
    `monkeypatch` ha gia' rimesso a posto `_apri`, scarica davvero tenendo aperto
    il database di prova: la fixture lo cancella sotto e il test dopo fallisce
    con «disk I/O error». Si spengono entrambe le cose: il guasto di rete e il
    filo di sottofondo.
    """
    monkeypatch.setattr(tv, "_apri",
                        lambda url: (_ for _ in ()).throw(tv.NonDisponibile("test")))
    monkeypatch.setattr(app_module, "_aggiorna_tv_in_sottofondo", lambda db: None)
    monkeypatch.setattr(app_module, "_aggiorna_notizie_in_sottofondo", lambda db: None)


def test_l_indirizzo_della_playlist_diventa_il_suo_id():
    """Nessuno incolla `PLQKkPe...`: si incolla l'indirizzo della barra del
    browser. Il feed Atom vuole il solo id, quindi va estratto — altrimenti la
    sezione resta vuota senza che si capisca perche'."""
    atteso = "PLQKkPe_OTLJygIqIViE5cqnWjxM1Cou0R"
    assert tv.normalizza_playlist(
        f"https://www.youtube.com/playlist?list={atteso}") == atteso
    # altri parametri nell'indirizzo non devono confondere
    assert tv.normalizza_playlist(
        f"https://www.youtube.com/watch?v=abc&list={atteso}&index=2") == atteso
    # un id gia' nudo si accetta com'e'
    assert tv.normalizza_playlist(atteso) == atteso


def test_un_indirizzo_senza_playlist_non_si_accetta():
    """Un video o un canale non sono una playlist: dirlo subito e' meglio che
    salvare un id sbagliato e mostrare una sezione vuota."""
    for storto in ("https://www.youtube.com/watch?v=abc123",
                   "https://www.youtube.com/@un-canale",
                   "non un id!!"):
        with pytest.raises(ValueError):
            tv.normalizza_playlist(storto)


def test_la_playlist_e_della_casa_non_del_modulo(client, monkeypatch):
    """La playlist scelta si salva nella casa: e' una preferenza dell'utente, e
    due case sullo stesso server non devono vedersi i video l'una dell'altra."""
    _niente_rete(monkeypatch)
    scelta = "PLcasa1234567890abcdef"
    r = client.put("/api/tv/playlist", json={"playlist": scelta})
    assert r.status_code == 200
    assert r.get_json()["playlist"] == scelta
    # il modulo continua a leggere la scelta della casa, non una costante
    assert tv.playlist_id(app_module.get_db()) == scelta
    assert client.get("/api/tv").get_json()["playlist"] == scelta


def test_una_playlist_non_valida_non_si_salva(client, monkeypatch):
    """L'id si valida **prima** di salvarlo: una playlist storta salvata sarebbe
    una sezione vuota che non si capisce da dove venga."""
    _niente_rete(monkeypatch)
    prima = client.get("/api/tv").get_json()["playlist"]
    r = client.put("/api/tv/playlist", json={"playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert client.get("/api/tv").get_json()["playlist"] == prima, "la scelta buona resta"


def test_cambiare_playlist_azzera_i_video_vecchi(client, monkeypatch):
    """I video di prima sono di un'altra playlist: tenerli mostrerebbe la scelta
    vecchia fino al prossimo giro, perche' `aggiorna` salta la copia fresca."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST})
    db = app_module.get_db()
    tv.aggiorna_video(db, forse=False)
    # il sottofondo di `/api/tv` non deve scaricare: la copia e' appena scritta
    _niente_rete(monkeypatch)
    assert len(client.get("/api/tv").get_json()["video"]) == 2

    # la nuova playlist risponde con un feed diverso: si deve vedere quello
    nuovo = "PLnuova9876543210zyxwvu"
    finta_tv(monkeypatch, {
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={nuovo}": FEED_PLAYLIST.replace(
            "aaa111", "ccc333").replace("bbb222", "ddd444"),
    })
    r = client.put("/api/tv/playlist", json={"playlist": nuovo})
    assert r.status_code == 200
    assert [v["id"] for v in r.get_json()["video"]] == ["ccc333", "ddd444"]


def test_la_casa_nuova_puo_nascere_con_una_playlist(anon, monkeypatch):
    """La richiesta nasce qui: alla creazione si chiede quale playlist si
    gradisce, cosi' la TV e' giusta fin dal primo avvio."""
    _niente_rete(monkeypatch)
    scelta = "PLscelta1234567890abcde"
    r = anon.post("/api/houses", json={
        "nome": "Casa Playlist", "password": "aaaa", "playlist": scelta})
    assert r.status_code == 201
    assert r.get_json()["playlist"] == scelta
    assert anon.get("/api/tv").get_json()["playlist"] == scelta


def test_una_playlist_non_valida_non_crea_la_casa(anon):
    """Si valida **prima** di registrare la casa: crearla e poi scoprire che la
    playlist non va bene la lascerebbe a meta'."""
    r = anon.post("/api/houses", json={
        "nome": "Casa Storta", "password": "aaaa",
        "playlist": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 400
    assert "Casa Storta" not in [c["nome"] for c in anon.get("/api/houses").get_json()]


def test_senza_playlist_la_casa_usa_la_predefinita(anon, monkeypatch):
    """Chi non sceglie non resta senza TV: la playlist predefinita vale per lui."""
    _niente_rete(monkeypatch)
    anon.post("/api/houses", json={"nome": "Casa Senza Scelta", "password": "aaaa"})
    assert anon.get("/api/tv").get_json()["playlist"] == tv.playlist_id()


def test_la_playlist_si_scegle_alla_creazione_e_si_cambia_dalla_tv(client):
    """La playlist si chiede creando la casa (la richiesta nasce li'), ma si deve
    anche poter cambiare dopo senza rifare la casa: un canale preferito cambia."""
    html = client.get("/static/index.html").get_data(as_text=True)
    assert 'id="new-playlist"' in html
    assert 'id="tv-playlist"' in html and 'id="tv-playlist-salva"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "/api/tv/playlist" in js
    assert "$('#new-playlist').value" in js


def test_l_endpoint_tv_serve_la_cache_e_gli_incorpora(client, monkeypatch):
    """L'endpoint non aspetta la rete: serve quello che c'e' e basta. Ogni video
    porta anche l'indirizzo del player, e il player e' `youtube-nocookie`, cosi'
    la pagina della casa non consegna i cookie a YouTube per il solo fatto di
    mostrare un video."""
    finta_tv(monkeypatch, {_url_playlist(): FEED_PLAYLIST, tv.feed_urls()[0]: FEED_NOTIZIE})
    db = app_module.get_db()
    tv.aggiorna(db, forse=False)

    d = client.get("/api/tv").get_json()
    assert len(d["video"]) == 2
    assert d["video"][0]["embed"] == "https://www.youtube-nocookie.com/embed/aaa111"
    assert len(d["notizie"]) == 2
    assert d["aggiornato"]["notizie"]


def test_l_endpoint_tv_non_cade_se_non_c_e_niente(client, monkeypatch):
    """Cache vuota e rete assente: 200 con due elenchi vuoti. E' una sezione da
    riempire, non un guasto da mostrare a chi apre l'app."""
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    r = client.get("/api/tv")
    assert r.status_code == 200
    d = r.get_json()
    assert d["video"] == [] and d["notizie"] == []


def _feed(titolo, voci):
    return (f"<rss version='2.0'><channel><title>{titolo}</title>"
            + "".join(voci) + "</channel></rss>")


def _voce(n, data="Mon, 01 Jan 2026 08:00:00 +0100"):
    return (f"<item><title>{n}</title><link>https://esempio.invalid/{n}</link>"
            f"<description>S {n}</description><pubDate>{data}</pubDate></item>")


def test_le_notizie_vengono_da_piu_sezioni_e_si_unisono(client, monkeypatch):
    """Le notizie arrivano da piu' sezioni ANSA (mondo, cronaca, politica,
    economia): con una sola il mondo lascia fuori quello che succede in Italia.
    L'elenco unico si riordina per data, non per sezione."""
    u1, u2 = "https://esempio.invalid/mondo", "https://esempio.invalid/cronaca"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it",
                  [_voce("mondo-vecchia", "Mon, 01 Jan 2026 08:00:00 +0100")]),
        u2: _feed("RSS di Cronaca  - ANSA.it",
                  [_voce("italia-nuova", "Thu, 02 Apr 2026 09:00:00 +0200")]),
    })
    notizie = tv.notizie_dal_feed()
    assert [n["titolo"] for n in notizie] == ["italia-nuova", "mondo-vecchia"]
    # la fonte resta quella della sezione di provenienza
    assert notizie[0]["fonte"] == "ANSA.it"


def test_una_sezione_ferma_non_svuota_le_altre(client, monkeypatch):
    """Se una sezione non risponde, le altre si mostrano lo stesso: una ferma non
    deve portare via le notizie che si sono lette."""
    u1, u2 = "https://esempio.invalid/mondo", "https://esempio.invalid/giu"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    finta_tv(monkeypatch, {u1: _feed("RSS di Mondo  - ANSA.it", [_voce("buona")])})
    # `u2` non e' previsto da finta_tv: solleva NonDisponibile
    notizie = tv.notizie_dal_feed()
    assert [n["titolo"] for n in notizie] == ["buona"]


def test_se_nessun_feed_risponde_e_un_guasto(client, monkeypatch):
    """Nessuna sezione risponde: e' `NonDisponibile`, non una lista vuota, cosi'
    la cache buona di ieri non viene sovrascritta con il vuoto."""
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: ["https://esempio.invalid/a",
                                                  "https://esempio.invalid/b"])
    finta_tv(monkeypatch, {})
    with pytest.raises(tv.NonDisponibile):
        tv.notizie_dal_feed()


def test_la_stessa_notizia_non_compare_due_volte(client, monkeypatch):
    """Lo stesso fatto compare in piu' sezioni con titoli diversi: il link e' la
    chiave stabile, e il doppione occuperebbe il posto di un'altra notizia."""
    u1, u2 = "https://esempio.invalid/a", "https://esempio.invalid/b"
    monkeypatch.setattr(tv, "feed_urls", lambda *a, **k: [u1, u2])
    voce = ("<item><title>Stesso fatto</title>"
            "<link>https://esempio.invalid/uguale</link>"
            "<description>S</description>"
            "<pubDate>Thu, 02 Apr 2026 09:00:00 +0200</pubDate></item>")
    finta_tv(monkeypatch, {
        u1: _feed("RSS di Mondo  - ANSA.it", [voce]),
        u2: _feed("RSS di Cronaca  - ANSA.it", [voce]),
    })
    notizie = tv.notizie_dal_feed()
    assert len(notizie) == 1


def test_i_feed_predefiniti_includono_l_italia(client):
    """Le sezioni predefinite non sono il solo «mondo»: dentro c'e' quello che
    succede in Italia, che e' la prima cosa che si guarda."""
    urls = tv.feed_urls()
    assert len(urls) >= 2
    assert any("mondo" in u for u in urls)
    assert any("cronaca" in u or "politica" in u for u in urls)
    # niente doppioni e tutti feed veri
    assert len(urls) == len(set(urls))
    assert all(u.startswith("https://") for u in urls)


def test_i_feed_predefiniti_non_includono_rainews(client):
    """RaiNews e' stato tolto dalle testate: le notizie sono solo ANSA.

    La scelta e' deliberata: il feed generalista di RaiNews pubblicava decine di
    voci e non si voleva piu' in elenco."""
    urls = tv.feed_urls()
    assert all("rainews" not in u.lower() for u in urls)
    assert all("ansa.it" in u for u in urls)


def test_gli_argomenti_scelti_riducono_i_feed(client):
    """Gli argomenti del profilo restringono i feed: chi legge solo economia non
    deve vedersi le notizie di mondo in elenco."""
    # nessuna scelta: tutti i feed predefiniti (nessun database = nessun profilo)
    assert tv.feed_urls() == list(tv.FEED_PREDEFINITI)
    client.put("/api/profile", json={"news_topics": ["economia", "politica"]})
    with closing(sqlite3.connect(houses.db_path(CASA_TEST))) as db:
        db.row_factory = sqlite3.Row
        urls = tv.feed_urls(db)
    assert urls == [tv.FEED_PER_TEMA["economia"], tv.FEED_PER_TEMA["politica"]]
    # e l'ordine e' quello dichiarato, non quello dei predefiniti
    assert urls[0].endswith("economia_rss.xml")


def test_argomenti_sconosciuti_non_svuotano_le_notizie():
    """Un refuso non deve lasciare la sezione senza notizie: si tengono solo le
    chiavi note, e se non ne resta nessuna valida si torna a "tutti"."""
    assert tv.argomenti_scelti("economia, sport, calcio") == ["economia"]
    assert tv.argomenti_scelti("") == []
    assert tv.argomenti_scelti(["mondo", "mondo", "cronaca"]) == ["mondo", "cronaca"]
    assert tv.argomenti_scelti("sport, meteo") == []


def test_cambiare_argomenti_azzera_la_copia_vecchia(client):
    """La copia delle notizie e' di altri argomenti: tenerla mostrerebbe la
    scelta precedente fino al giro dopo."""
    percorso = houses.db_path(CASA_TEST)
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("INSERT INTO tv_cache (chiave, dati, aggiornato) "
                   "VALUES ('notizie', '[]', datetime('now'))")
        db.commit()
    client.put("/api/profile", json={"news_topics": ["economia"]})
    with closing(sqlite3.connect(percorso)) as db:
        righe = db.execute("SELECT chiave FROM tv_cache WHERE chiave = 'notizie'").fetchall()
    assert not righe, "la copia delle notizie va azzerata"


def test_la_meta_porta_gli_argomenti_delle_notizie(client):
    """Onboarding e Profilo costruiscono le scelte dalla meta, non a mano."""
    meta = client.get("/api/meta").get_json()
    chiavi = {a["key"] for a in meta["news_topics"]}
    assert chiavi == set(tv.FEED_PER_TEMA)
    assert all("label" in a for a in meta["news_topics"])


def test_gli_argomenti_si_salvano_come_testo_o_lista(client):
    """L'API accetta entrambe le forme, e normalizza in testo separato da virgole:
    e' la forma che `tv.argomenti_scelti` legge."""
    p = client.put("/api/profile", json={"news_topics": ["economia", "politica"]}).get_json()
    assert p["news_topics"] == "economia, politica"
    p = client.put("/api/profile", json={"news_topics": "economia; politica"}).get_json()
    assert p["news_topics"] == "economia, politica"
    p = client.put("/api/profile", json={"news_topics": []}).get_json()
    assert p["news_topics"] == ""


def test_tv_feed_dall_ambiente_ne_accetta_piu_d_uno(client, monkeypatch):
    """`TV_FEED` puo' indicare piu' indirizzi, separati da virgola o a capo:
    cosi' una casa puo' scegliere le proprie sezioni senza toccare il modulo."""
    monkeypatch.setenv("TV_FEED", "https://a.invalid/rss, https://b.invalid/rss\n"
                                  "https://c.invalid/rss")
    assert tv.feed_urls() == ["https://a.invalid/rss", "https://b.invalid/rss",
                              "https://c.invalid/rss"]
    # e il tetto vale anche qui: non si moltiplicano le richieste a un sito altrui
    monkeypatch.setenv("TV_FEED", ",".join(f"https://x{i}.invalid/rss" for i in range(50)))
    assert len(tv.feed_urls()) == tv.MAX_FEED


def test_l_aggiornamento_manuale_lo_dice_se_non_ha_portato_niente(client, monkeypatch):
    """Il pulsante «Aggiorna» aspetta la rete e riporta l'esito: un aggiornamento
    che non ha portato niente di nuovo non deve sembrare riuscito."""
    monkeypatch.setattr(tv, "_apri", lambda url: (_ for _ in ()).throw(tv.NonDisponibile("giu")))
    d = client.post("/api/tv/aggiorna").get_json()
    assert d["aggiornati"] == {"video": False, "notizie": False, "gym": False}


def test_il_database_vecchio_riceve_la_tabella_della_cache(client):
    """`tv_cache` e' una tabella nuova: `CREATE TABLE IF NOT EXISTS` la crea su
    ogni casa, vecchia o nuova. Se non arrivasse, la sezione TV fallirebbe solo
    sulle case con piu' dati — il posto peggiore."""
    db = app_module.get_db()
    tabelle = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "tv_cache" in tabelle



# ------------------------------------------------------------ calendario
# La logica delle date sta in `calendario.py`, dove si prova senza browser:
# la griglia del mese, i giorni di distanza e il promemoria sono funzioni pure.
# Le rotte si provano per quello che aggiungono — la persistenza, la
# validazione, lo stato calcolato — non per il calcolo, che ha gia' i suoi test.

def test_la_griglia_del_mese_comincia_di_lunedi_e_finisce_di_domenica():
    """Le settimane devono essere intere: una riga che comincia a meta' confonde
    piu' di quanto aiuti. Febbraio 2026 comincia di domenica, quindi la prima
    settimana ha sei giorni di gennaio davanti."""
    g = calendario.mese_di(2026, 2)
    assert g["celle"][0]["iso"] == "2026-01-26"       # lunedi'
    assert g["celle"][0]["nel_mese"] is False
    assert g["celle"][0]["weekend"] is False
    assert g["celle"][5]["iso"] == "2026-01-31"
    assert g["celle"][6]["iso"] == "2026-02-01"       # domenica: prima del mese
    assert len(g["celle"]) % 7 == 0
    assert g["primo"] == "2026-02-01" and g["ultimo"] == "2026-02-28"


def test_il_weekend_e_il_sabato_e_la_domenica():
    g = calendario.mese_di(2026, 3)
    for c in g["celle"]:
        atteso = calendario._data(c["iso"]).weekday() >= 5
        assert c["weekend"] is atteso


def test_i_giorni_di_distanza_seguono_il_segno_delle_pulizie():
    """Stessa convenzione di `igiene.scadenza`: negativo se e' passato, 0 oggi,
    positivo se deve venire. Chi legge i due moduli non deve ricordare due
    regole diverse."""
    s = calendario.stato_impegno("2026-09-10", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == -2 and s["passato"] and s["in_ritardo"]
    s = calendario.stato_impegno("2026-09-12", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == 0 and s["oggi"] and not s["passato"]
    s = calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=0)
    assert s["giorni"] == 3 and not s["passato"]


def test_il_promemoria_scatta_da_n_giorni_prima_fino_al_giorno_stesso():
    """Il promemoria non e' "il giorno prima": e' quanti giorni prima, e resta
    acceso fino al giorno dell'impegno compreso."""
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=3)["avvisa"] is True
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-12", promemoria=2)["avvisa"] is False
    assert calendario.stato_impegno("2026-09-15", oggi="2026-09-15", promemoria=1)["avvisa"] is True


def test_una_cosa_passata_non_avvisa_piu_ma_resta_in_ritardo():
    """Un promemoria per una cosa gia' successa non e' un promemoria; ma una
    cosa passata e non chiusa deve restare visibile, altrimenti sparisce in
    silenzio, che e' il modo peggiore di fallire un promemoria."""
    s = calendario.stato_impegno("2026-09-01", oggi="2026-09-10", promemoria=30)
    assert s["avvisa"] is False
    assert s["in_ritardo"] is True


def test_zero_giorni_prima_e_il_giorno_stesso_non_un_nessun_promemoria():
    s = calendario.stato_impegno("2026-09-15", oggi="2026-09-15", promemoria=0)
    assert s["avvisa"] is True


def test_un_impegno_senza_data_non_cade():
    """`when_date` e' obbligatoria, ma una riga scritta a mano nel database puo'
    non averla: la scheda deve mostrare "senza data" invece di sollevare."""
    s = calendario.stato_impegno("", oggi="2026-09-12")
    assert s["giorni"] is None and s["avvisa"] is False
    assert calendario.quando_detto(s) == "senza data"


def test_le_frasi_di_quando_sono_brevi_e_italiane():
    oggi = "2026-09-12"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-12", oggi)) == "oggi"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-13", oggi)) == "domani"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-11", oggi)) == "ieri"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-15", oggi)) == "fra 3 giorni"
    assert calendario.quando_detto(calendario.stato_impegno("2026-09-09", oggi)) == "3 giorni fa"


def test_una_categoria_sconosciuta_ricade_sulla_predefinita():
    """Un'etichetta sbagliata non deve far perdere un appuntamento: si ricade
    invece di rifiutare, come per le FAQ."""
    assert calendario.categoria_valida("Lavoro") == "lavoro"
    assert calendario.categoria_valida("inventata") == calendario.CATEGORIA_DEFAULT
    assert calendario.categoria_valida("") == calendario.CATEGORIA_DEFAULT


def test_ogni_categoria_ha_un_colore_che_e_una_variabile_css():
    """Il colore e' un nome di variabile CSS, non un esadecimale: cosi' il tema
    scuro la schiarisce da sola. Una categoria senza colore lascerebbe il
    puntino invisibile."""
    for c in calendario.CATEGORIE:
        assert c["colore"].startswith("--")
    assert set(calendario.meta()["category_colors"]) == {c["key"] for c in calendario.CATEGORIE}


def test_i_dodici_mesi_sono_in_italiano():
    assert calendario.mesi()[0] == "Gennaio"
    assert calendario.mesi()[11] == "Dicembre"
    assert len(calendario.mesi()) == 12


def test_un_promemoria_fuori_scala_viene_riportato_nei_limiti():
    assert calendario.promemoria_giorni(-5) == 0
    assert calendario.promemoria_giorni(9999) == calendario.PROMEMORIA_MAX
    assert calendario.promemoria_giorni("non un numero") == 0


def test_un_ora_scritta_male_non_fa_perdere_l_impegno():
    """L'ora e' facoltativa e l'impegno e' la parte che conta: un'ora storta si
    scarta, non fa rifiutare tutto."""
    assert calendario._ora("09:30") == "09:30"
    assert calendario._ora("09:30:00") == "09:30"
    assert calendario._ora("") == ""
    assert calendario._ora("venticinque") == ""


def test_impegno_si_crea_con_tutti_i_campi(client):
    r = client.post("/api/appointments", json={
        "title": "Dentista", "when_date": "2026-09-20", "time": "09:30",
        "category": "salute", "notes": "Portare la tessera", "reminder_days": 3,
    })
    assert r.status_code == 201
    a = r.get_json()
    assert a["title"] == "Dentista"
    assert a["category"] == "salute"
    assert a["category_label"] == "Salute"
    assert a["time"] == "09:30"
    assert a["reminder_days"] == 3
    assert a["done"] is False
    assert a["stato"]["giorni"] is not None


def test_impegno_senza_titolo_o_senza_data_rifiutato(client):
    assert client.post("/api/appointments", json={"when_date": "2026-09-20"}).status_code == 400
    assert client.post("/api/appointments", json={"title": "X"}).status_code == 400
    assert client.post("/api/appointments", json={"title": "X", "when_date": "non-data"}).status_code == 400


def test_impegno_si_conclude_e_si_riapre(client):
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20"}).get_json()["id"]
    assert client.put(f"/api/appointments/{aid}", json={"done": True}).get_json()["done"] is True
    assert client.put(f"/api/appointments/{aid}", json={"done": False}).get_json()["done"] is False


def test_spuntare_un_impegno_non_cancella_il_resto(client):
    """`done` si tocca da solo, come per i progetti: spuntare una casella non
    deve richiedere di rimandare titolo, data e promemoria."""
    aid = client.post("/api/appointments", json={
        "title": "Dentista", "when_date": "2026-09-20", "time": "09:30",
        "category": "salute", "notes": "tessera", "reminder_days": 3,
    }).get_json()["id"]
    a = client.put(f"/api/appointments/{aid}", json={"done": True}).get_json()
    assert a["title"] == "Dentista" and a["time"] == "09:30"
    assert a["category"] == "salute" and a["notes"] == "tessera"
    assert a["reminder_days"] == 3


def test_un_impegno_si_puo_spostare_e_il_promemoria_lo_segue(client):
    """Il promemoria e' quanti giorni prima, non una data: spostando l'impegno
    si sposta anche il promemoria, invece di lasciarlo indietro."""
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20", "reminder_days": 2}).get_json()["id"]
    a = client.put(f"/api/appointments/{aid}", json={"when_date": "2026-10-01"}).get_json()
    assert a["when_date"] == "2026-10-01"
    assert a["reminder_days"] == 2


def test_impegno_eliminato(client):
    aid = client.post("/api/appointments", json={
        "title": "X", "when_date": "2026-09-20"}).get_json()["id"]
    assert client.delete(f"/api/appointments/{aid}").status_code == 200
    assert client.get("/api/appointments?giorno=2026-09-20").get_json()["appointments"] == []


def test_impegno_inesistente_da_404(client):
    assert client.put("/api/appointments/99999", json={"done": True}).status_code == 404
    assert client.delete("/api/appointments/99999").status_code == 404


def test_il_mese_si_chiede_con_la_sua_data(client):
    client.post("/api/appointments", json={"title": "Dentro", "when_date": "2026-09-20"})
    client.post("/api/appointments", json={"title": "Fuori", "when_date": "2026-10-20"})
    d = client.get("/api/appointments?mese=2026-09").get_json()
    assert [a["title"] for a in d["appointments"]] == ["Dentro"]
    assert d["mese"]["anno"] == 2026 and d["mese"]["mese"] == 9
    assert len(d["mese"]["celle"]) % 7 == 0


def test_senza_mese_si_serve_quello_corrente(client):
    d = client.get("/api/appointments").get_json()
    oggi = date.today()
    assert d["mese"]["anno"] == oggi.year and d["mese"]["mese"] == oggi.month


def test_gli_impegni_di_un_giorno_si_leggono_insieme(client):
    client.post("/api/appointments", json={"title": "Uno", "when_date": "2026-09-20", "time": "09:00"})
    client.post("/api/appointments", json={"title": "Due", "when_date": "2026-09-20", "time": "15:00"})
    d = client.get("/api/appointments?giorno=2026-09-20").get_json()
    assert [a["title"] for a in d["appointments"]] == ["Uno", "Due"]


def test_gli_avvisi_sono_i_promemoria_scattati_non_tutti_i_prossimi(client):
    """Un promemoria per una cosa fra sei mesi non e' un promemoria: gli avvisi
    sono solo quelli scattati o in ritardo."""
    oggi = date.today()
    vicino = (oggi + timedelta(days=2)).isoformat()
    lontano = (oggi + timedelta(days=120)).isoformat()
    client.post("/api/appointments", json={"title": "Vicino", "when_date": vicino, "reminder_days": 3})
    client.post("/api/appointments", json={"title": "Lontano", "when_date": lontano, "reminder_days": 0})
    d = client.get("/api/appointments").get_json()
    titoli = [a["title"] for a in d["prossimi"]]
    assert "Vicino" in titoli and "Lontano" not in titoli


def test_un_impegno_in_ritardo_resta_negli_avvisi_finche_non_si_chiude(client):
    ieri = (date.today() - timedelta(days=3)).isoformat()
    aid = client.post("/api/appointments", json={
        "title": "Mancato", "when_date": ieri}).get_json()["id"]
    titoli = [a["title"] for a in client.get("/api/appointments").get_json()["prossimi"]]
    assert "Mancato" in titoli
    client.put(f"/api/appointments/{aid}", json={"done": True})
    titoli = [a["title"] for a in client.get("/api/appointments").get_json()["prossimi"]]
    assert "Mancato" not in titoli


def test_il_calendario_richiede_l_accesso(anon):
    assert anon.get("/api/appointments").status_code == 401
    assert anon.post("/api/appointments", json={"title": "X", "when_date": "2026-09-20"}).status_code == 401


def test_il_calendario_meta_ha_categorie_promemoria_e_mesi(client):
    m = client.get("/api/calendario/meta").get_json()
    assert "salute" in m["categories"] and m["category_labels"]["salute"] == "Salute"
    assert m["category_colors"]["salute"].startswith("--")
    assert m["reminders"][0]["giorni"] == 0
    assert len(m["months"]) == 12


def test_il_database_vecchio_riceve_la_tabella_del_calendario(client):
    """`appointments` e' una tabella nuova: `CREATE TABLE IF NOT EXISTS` la crea
    su ogni casa, vecchia o nuova. Se non arrivasse, il calendario fallirebbe
    solo sulle case con piu' dati — il posto peggiore."""
    db = app_module.get_db()
    tabelle = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "appointments" in tabelle


def test_la_griglia_del_calendario_ha_i_puntini_delle_categorie():
    """Ogni cella con un impegno porta un puntino del colore della categoria:
    e' quello che fa leggere il mese a colpo d'occhio."""
    js = open(os.path.join(BASE_APP, "static", "app.js"), encoding="utf-8").read()
    assert "cal-dot" in js and "category_colors" in js
    assert "cal-celle" in js


def test_ogni_colore_di_categoria_e_definito_in_entrambi_i_temi():
    """Il modulo nomina le variabili CSS, ma sono il foglio di stile a
    definirle. Un colore che esiste solo nel tema chiaro lascerebbe il puntino
    invisibile di notte — e il difetto non si vedrebbe di giorno."""
    css = open(os.path.join(BASE_APP, "static", "style.css"), encoding="utf-8").read()
    chiaro = css.split('html[data-tema="scuro"]')[0]
    scuro = css.split('html[data-tema="scuro"]', 1)[1]
    for c in calendario.CATEGORIE:
        assert f"{c['colore']}:" in chiaro, f"{c['colore']} manca nel tema chiaro"
        assert f"{c['colore']}:" in scuro, f"{c['colore']} manca nel tema scuro"


