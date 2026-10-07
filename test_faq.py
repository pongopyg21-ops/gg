"""FAQ: informazioni utili, protette dal controllo biometrico.

Le voci vivono **cifrate** nel database della casa e si leggono e si scrivono
via `/api/faq` solo a modulo aperto. Non c'e' nessuna password: si apre col
sensore (`POST /api/faq/apri-biometria`), e la prima apertura configura da sola
la chiave del dispositivo.

Fixture in `conftest.py`; helper in `test_comuni.py`.
"""
import sqlite3

from test_comuni import *  # noqa: F401,F403

CHIAVE = "chiave-del-dispositivo-di-prova"


def _apri(client, chiave=CHIAVE):
    return client.post("/api/faq/apri-biometria", json={"chiave": chiave})


# ----------------------------------------------------- il modulo e' protetto

def test_a_modulo_chiuso_il_valore_non_arriva_al_client(client):
    """Il vero requisito di riservatezza: chiuso il modulo, il valore non
    compare nella risposta, non solo nascosto a schermo."""
    _apri(client)
    client.post("/api/faq", json={"question": "Wi-Fi", "answer": "Rete: CasaRossi",
                                  "category": "wifi"})
    client.post("/api/faq/chiudi")
    elenco = client.get("/api/faq")
    assert elenco.status_code == 200
    assert "CasaRossi" not in elenco.get_data(as_text=True), "il valore e' trapelato"
    assert elenco.get_json()["totale"] == 0
    # e non si scrive a modulo chiuso
    assert client.post("/api/faq", json={"question": "Y"}).status_code == 401


def test_il_valore_non_e_in_chiaro_nel_database(client):
    """Il testo e' cifrato a riposo: un database copiato non mostra i valori.

    Si guarda il **file** vero, non l'API: e' l'unica prova che la cifratura
    esiste davvero e non e' solo un filtro sulle risposte.
    """
    _apri(client)
    client.post("/api/faq", json={"question": "Cancello", "answer": "codice-segreto-42"})
    with open(houses.db_path(CASA_TEST), "rb") as fh:
        grezzo = fh.read()
    assert b"codice-segreto-42" not in grezzo, "il valore e' in chiaro nel database"


def test_le_voci_si_vedono_dopo_l_apertura_col_sensore(client):
    _apri(client)
    client.post("/api/faq", json={"question": "Cancello", "answer": "codice 42",
                                  "category": "codici"})
    client.post("/api/faq/chiudi")
    _apri(client)
    voci = client.get("/api/faq").get_json()["voci"]
    assert [v["question"] for v in voci] == ["Cancello"]
    assert voci[0]["answer"] == "codice 42"
    assert voci[0]["category_label"] == "Codici e accessi"


def test_la_prima_apertura_configura_la_biometria(client):
    """Non c'e' niente da configurare a mano: la prima apertura deposita la
    chiave del dispositivo, e lo stato lo dice."""
    assert client.get("/api/faq/stato").get_json()["biometria"] is False
    _apri(client)
    assert client.get("/api/faq/stato").get_json()["biometria"] is True


def test_un_altro_dispositivo_non_passa(client):
    """La chiave del secondo dispositivo non apre la scatola del primo."""
    _apri(client, "chiave-del-telefono")
    client.post("/api/faq/chiudi")
    r = _apri(client, "chiave-del-computer")
    assert r.status_code == 401
    assert client.get("/api/faq/stato").get_json()["aperta"] is False


def test_serve_la_chiave_del_dispositivo(client):
    """Senza chiave (nessun sensore) non si apre: non c'e' una password di
    riserva, perche' l'utente l'ha tolta apposta."""
    assert _apri(client, "").status_code == 400
    assert client.get("/api/faq/stato").get_json()["aperta"] is False


def test_il_modulo_non_si_apre_da_solo_con_l_accesso(client):
    """Entrare nella casa non basta: il modulo resta chiuso finche' non si apre."""
    assert client.get("/api/faq/stato").get_json()["aperta"] is False


# ------------------------------------------------------------------ CRUD voci

def test_faq_ciclo_completo(client):
    """Aggiungere, leggere, modificare ed eliminare una voce."""
    _apri(client)
    r = client.post("/api/faq", json={"question": "Idraulico", "answer": "333 111",
                                      "category": "contatti", "pinned": True})
    assert r.status_code == 201
    fid = r.get_json()["id"]

    voce = client.get("/api/faq").get_json()["voci"][0]
    assert voce["question"] == "Idraulico"
    assert voce["pinned"] is True

    r = client.put(f"/api/faq/{fid}", json={"answer": "333 222"})
    assert r.status_code == 200
    assert r.get_json()["answer"] == "333 222"

    assert client.delete(f"/api/faq/{fid}").status_code == 200
    assert client.get("/api/faq").get_json()["totale"] == 0


def test_faq_la_modifica_parziale_non_azzera_il_resto(client):
    _apri(client)
    fid = client.post("/api/faq", json={"question": "Medico", "answer": "dott. Rossi",
                                        "notes": "studio il martedi"}).get_json()["id"]
    client.put(f"/api/faq/{fid}", json={"answer": "dott. Bianchi"})
    voce = client.get("/api/faq").get_json()["voci"][0]
    assert voce["answer"] == "dott. Bianchi"
    assert voce["question"] == "Medico"
    assert voce["notes"] == "studio il martedi"


def test_faq_titolo_obbligatorio(client):
    _apri(client)
    assert client.post("/api/faq", json={"answer": "senza titolo"}).status_code == 400


def test_faq_categoria_sconosciuta_non_rifiuta_la_voce(client):
    _apri(client)
    r = client.post("/api/faq", json={"question": "X", "category": "inesistente"})
    assert r.status_code == 201
    assert r.get_json()["category"] == "generale"


def test_faq_voce_inesistente(client):
    _apri(client)
    assert client.put("/api/faq/999", json={"answer": "x"}).status_code == 404
    assert client.delete("/api/faq/999").status_code == 404


def test_faq_ordine_per_categoria_poi_evidenza(client):
    _apri(client)
    for q, cat, pin in [("b1", "wifi", False), ("a1", "wifi", True),
                        ("c1", "codici", False)]:
        client.post("/api/faq", json={"question": q, "category": cat, "pinned": pin})
    voci = client.get("/api/faq").get_json()["voci"]
    assert [v["question"] for v in voci] == ["a1", "b1", "c1"]


def test_faq_una_voce_senza_valore_e_ammessa(client):
    _apri(client)
    r = client.post("/api/faq", json={"question": "Da completare"})
    assert r.status_code == 201
    assert r.get_json()["ha_valore"] is False


def test_faq_valori_booleani_normalizzati(client):
    _apri(client)
    r = client.post("/api/faq", json={"question": "X", "pinned": 1})
    assert r.get_json()["pinned"] is True


# -------------------------------------------------------------------- meta

def test_faq_meta_conta_le_voci_per_categoria(client):
    _apri(client)
    client.post("/api/faq", json={"question": "a", "category": "wifi"})
    client.post("/api/faq", json={"question": "b", "category": "wifi"})
    client.post("/api/faq", json={"question": "c", "category": "codici"})
    conteggi = {c["key"]: c["count"]
                for c in client.get("/api/faq/meta").get_json()["categories"]}
    assert conteggi["wifi"] == 2
    assert conteggi["codici"] == 1


def test_faq_meta_elenca_le_categorie(client):
    cats = client.get("/api/faq/meta").get_json()["categories"]
    assert cats and all("key" in c and "label" in c for c in cats)


def test_faq_non_ha_una_seconda_voce_di_menu(client):
    js = client.get("/static/app.js").get_data(as_text=True)
    assert "cass-list" not in js


# ------------------------------------------------------------------ migrazione

def test_il_vecchio_database_faq_viene_importato_e_cifrato(client):
    """Chi aggiorna da una versione con le voci in chiaro non le perde: alla
    prima lettura entrano nel blob cifrato e la tabella vecchia si svuota."""
    with sqlite3.connect(houses.db_path(CASA_TEST)) as db:
        db.execute("INSERT INTO faq (category, question, answer, pinned) "
                   "VALUES ('wifi', 'Fastweb', 'chiave-vecchia', 1)")
        db.commit()
    _apri(client)
    voci = client.get("/api/faq").get_json()["voci"]
    assert [v["question"] for v in voci] == ["Fastweb"]
    assert voci[0]["answer"] == "chiave-vecchia"
    with sqlite3.connect(houses.db_path(CASA_TEST)) as db:
        rimaste = db.execute("SELECT COUNT(*) FROM faq").fetchone()[0]
        grezzo = db.execute("SELECT dati FROM cassaforte WHERE id = 1").fetchone()[0]
    assert rimaste == 0
    assert "chiave-vecchia" not in grezzo, "la voce importata e' rimasta in chiaro"


# ------------------------------------------------------------------ alias

def test_gli_alias_cassaforte_restano(client):
    """I vecchi nomi `/api/cassaforte/voci` non si rompono: stessa logica."""
    _apri(client)
    assert client.post("/api/cassaforte/voci",
                       json={"question": "Alias", "answer": "ok"}).status_code == 201
    voci = client.get("/api/cassaforte/voci").get_json()["voci"]
    assert [v["question"] for v in voci] == ["Alias"]


# ------------------------------------------------------ promemoria e chiusura

def test_il_promemoria_si_cambia_con_la_chiave(client):
    """Niente campi password: la chiave del dispositivo autorizza la modifica."""
    _apri(client)
    r = client.put("/api/faq/frase", json={"chiave": CHIAVE,
                                           "promemoria": "il codice del cancello",
                                           "chiusura_minuti": 5})
    assert r.status_code == 200
    stato = client.get("/api/faq/stato").get_json()
    assert stato["promemoria"] == "il codice del cancello"
    assert stato["chiusura_minuti"] == 5


def test_il_promemoria_non_si_cambia_senza_la_chiave(client):
    _apri(client)
    assert client.put("/api/faq/frase",
                      json={"chiave": "sbagliata", "promemoria": "x"}).status_code == 401
