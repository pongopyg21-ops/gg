"""Riconoscimento degli allergeni.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


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
