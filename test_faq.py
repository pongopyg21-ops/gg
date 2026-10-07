"""FAQ: voci protette dalla cassaforte, categorie e ricerca.

Tutto il modulo FAQ e' cifrato: le voci si leggono e si scrivono via `/api/faq`
solo a cassaforte aperta. La cassaforte (creazione, apertura, password) ha i suoi
test in `test_cassaforte.py`; qui si prova il comportamento del modulo FAQ.

Fixture in `conftest.py`; helper in `test_comuni.py`.
"""
from test_comuni import *  # noqa: F401,F403


def _crea_cassaforte(client, password="aprisicuro"):
    r = client.post("/api/cassaforte/crea", json={"password": password})
    assert r.status_code == 201, r.get_data(as_text=True)
    return r


# ----------------------------------------------------------- il modulo e' protetto

def test_senza_cassaforte_le_faq_invitano_a_crearla(client):
    """Non ci sono voci in chiaro da mostrare: il modulo *e'* la cassaforte."""
    stato = client.get("/api/cassaforte/stato").get_json()
    assert stato["esiste"] is False
    r = client.get("/api/faq")
    assert r.status_code == 200
    assert r.get_json()["totale"] == 0
    # senza cassaforte non si scrive: 409, non 401 (che vuol dire "password sbagliata")
    assert client.post("/api/faq", json={"question": "X", "answer": "Y"}).status_code == 409


def test_a_cassaforte_chiusa_il_valore_non_arriva_al_client(client):
    """Il vero requisito di riservatezza: chiusa la cassaforte, il valore non
    compare nella risposta, non solo nascosto a schermo."""
    _crea_cassaforte(client)
    client.post("/api/faq", json={"question": "Wi-Fi", "answer": "Rete: CasaRossi",
                                  "category": "wifi"})
    client.post("/api/cassaforte/chiudi")
    elenco = client.get("/api/faq")
    assert elenco.status_code == 200
    corpo = elenco.get_data(as_text=True)
    assert "CasaRossi" not in corpo, "il valore e' trapelato a cassaforte chiusa"
    assert elenco.get_json()["totale"] == 0
    # e non si scrive a cassaforte chiusa
    assert client.post("/api/faq", json={"question": "Y"}).status_code == 401


def test_le_voci_si_vedono_dopo_l_apertura(client):
    _crea_cassaforte(client)
    client.post("/api/faq", json={"question": "Cancello", "answer": "codice 42",
                                  "category": "codici"})
    client.post("/api/cassaforte/chiudi")
    client.post("/api/cassaforte/apri", json={"password": "aprisicuro"})
    voci = client.get("/api/faq").get_json()["voci"]
    assert [v["question"] for v in voci] == ["Cancello"]
    assert voci[0]["answer"] == "codice 42"
    assert voci[0]["category_label"] == "Codici e accessi"


def test_la_cassaforte_non_si_apre_da_sola_con_l_accesso(client):
    """Entrare nella casa non basta: la password della cassaforte e' un'altra."""
    _crea_cassaforte(client)
    client.post("/api/cassaforte/chiudi")
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is False


# ------------------------------------------------------------------ CRUD voci

def test_faq_ciclo_completo(client):
    """Aggiungere, leggere, modificare ed eliminare una voce."""
    _crea_cassaforte(client)
    r = client.post("/api/faq", json={
        "question": "Wi-Fi di casa",
        "answer": "Rete: CasaRossi\nPassword: segreta",
        "category": "wifi",
    })
    assert r.status_code == 201
    voce = r.get_json()
    assert voce["ha_valore"] is True

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
    _crea_cassaforte(client)
    voce = client.post("/api/faq", json={
        "question": "Idraulico", "answer": "333 1234567", "category": "contatti",
    }).get_json()
    dopo = client.put(f"/api/faq/{voce['id']}", json={"pinned": True}).get_json()
    assert dopo["question"] == "Idraulico"
    assert dopo["answer"] == "333 1234567"
    assert dopo["category"] == "contatti"
    assert dopo["pinned"] is True


def test_faq_titolo_obbligatorio(client):
    _crea_cassaforte(client)
    assert client.post("/api/faq", json={"answer": "solo valore"}).status_code == 400
    assert client.post("/api/faq", json={"question": "   "}).status_code == 400


def test_faq_categoria_sconosciuta_non_rifiuta_la_voce(client):
    """Una categoria ignota ricade sulla predefinita: la voce resta utile."""
    _crea_cassaforte(client)
    r = client.post("/api/faq", json={"question": "X", "category": "inesistente"})
    assert r.status_code == 201
    assert r.get_json()["category"] == "generale"


def test_faq_voce_inesistente(client):
    _crea_cassaforte(client)
    assert client.put("/api/faq/999", json={"question": "x"}).status_code == 404
    assert client.delete("/api/faq/999").status_code == 404


def test_faq_ordine_per_categoria_poi_evidenza(client):
    """Le voci in evidenza risalgono nella loro categoria, non oltre."""
    _crea_cassaforte(client)
    for corpo in (
        {"question": "Zeta", "category": "wifi"},
        {"question": "Alfa", "category": "wifi", "pinned": True},
        {"question": "Beta", "category": "indirizzi"},
    ):
        client.post("/api/faq", json=corpo)
    voci = client.get("/api/faq").get_json()["voci"]
    # Wi-Fi prima degli Indirizzi, e dentro il Wi-Fi l'evidenza viene prima
    assert [v["question"] for v in voci] == ["Alfa", "Zeta", "Beta"]


def test_faq_una_voce_senza_valore_e_ammessa(client):
    """Un promemoria puo' non avere ancora il valore: si aggiunge dopo."""
    _crea_cassaforte(client)
    r = client.post("/api/faq", json={"question": "Password del cancello"})
    assert r.status_code == 201
    assert r.get_json()["answer"] == ""
    assert r.get_json()["ha_valore"] is False


def test_faq_valori_booleani_normalizzati(client):
    """Il frontend manda true/false: nella risposta tornano booleani coerenti."""
    _crea_cassaforte(client)
    voce = client.post("/api/faq", json={
        "question": "Cancello", "pinned": False,
    }).get_json()
    assert voce["pinned"] is False
    dopo = client.put(f"/api/faq/{voce['id']}", json={"pinned": True}).get_json()
    assert dopo["pinned"] is True


def test_faq_meta_conta_le_voci_per_categoria(client):
    _crea_cassaforte(client)
    client.post("/api/faq", json={"question": "A", "category": "wifi"})
    client.post("/api/faq", json={"question": "B", "category": "wifi"})
    client.post("/api/faq", json={"question": "C", "category": "contatti"})
    conteggi = {c["key"]: c["count"] for c in client.get("/api/faq/meta").get_json()["categories"]}
    assert conteggi["wifi"] == 2
    assert conteggi["contatti"] == 1
    assert conteggi["codici"] == 0


def test_faq_meta_elenca_le_categorie(client):
    m = client.get("/api/faq/meta").get_json()
    chiavi = [c["key"] for c in m["categories"]]
    assert chiavi[0] == "wifi", "il Wi-Fi e' la cosa che si cerca piu' spesso"
    assert "generale" in chiavi
    assert m["default_category"] in chiavi


# ------------------------------------------------------------------ interfaccia

def test_faq_non_ha_una_seconda_voce_di_menu(client):
    """L'utente non vuole due schede: c'e' una sola lista, protetta. Si verifica
    che la vista unica (Rubrica/Cassaforte) sia sparita dall'HTML e dal JS."""
    html = client.get("/").get_data(as_text=True)
    assert 'id="faq-vista-rubrica"' not in html
    assert 'id="faq-vista-cassaforte"' not in html
    assert 'id="faq-pannello-rubrica"' not in html
    assert 'id="faq-pannello-cassaforte"' not in html
    # una sola lista, con il riquadro della cassaforte sopra
    assert 'id="cass-blocco"' in html
    assert 'id="cass-contenuto" hidden' in html
    assert 'id="faq-list"' in html
    js = client.get("/static/app.js").get_data(as_text=True)
    for pezzo in ("renderCassaforte", "renderFaqElenco", "/api/cassaforte/stato",
                  "/api/cassaforte/apri", "/api/cassaforte/chiudi", "creaCassaforte"):
        assert pezzo in js, f"manca {pezzo} in app.js"
    # la vecchia vista doppia non deve restare nel client
    assert "cambiaVistaFaq" not in js
    assert "cassRiga" not in js
    assert "cass-list" not in js


def test_il_vecchio_database_faq_viene_importato_e_cifrato(client):
    """Chi aggiorna da una versione con le voci in chiaro non le perde: alla
    creazione della cassaforte entrano nel blob cifrato e la tabella vecchia si
    svuota."""
    import sqlite3
    with sqlite3.connect(houses.db_path(CASA_TEST)) as db:
        db.execute("INSERT INTO faq (category, question, answer, pinned) "
                   "VALUES ('wifi', 'Fastweb', 'chiave-vecchia', 1)")
        db.commit()
    _crea_cassaforte(client)
    voci = client.get("/api/faq").get_json()["voci"]
    assert [v["question"] for v in voci] == ["Fastweb"]
    assert voci[0]["answer"] == "chiave-vecchia"
    # la tabella vecchia non conserva piu' niente in chiaro
    with sqlite3.connect(houses.db_path(CASA_TEST)) as db:
        rimaste = db.execute("SELECT COUNT(*) FROM faq").fetchone()[0]
    assert rimaste == 0
