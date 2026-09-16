"""Verifica conversione unità e generazione lista della spesa. Crea un DB temporaneo."""
import json
import os
import tempfile

import pytest

DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["CUCINA_DB"] = DB

import app as app_module  # noqa: E402
import allergens  # noqa: E402
import units  # noqa: E402


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


def test_generazione_ripetuta_accumula(client):
    rid = ricetta(client, "Pomodori", 2, [{"name": "Pomodori", "quantity": 500, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    client.post("/api/shopping/generate", json={"start": "2026-09-16", "end": "2026-09-16"})
    items = client.get("/api/shopping").get_json()
    assert len(items) == 1
    assert items[0]["quantity"] == pytest.approx(1000)


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
