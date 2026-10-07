"""FAQ: voci, categorie e ricerca.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


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
