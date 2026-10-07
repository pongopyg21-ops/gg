"""La cassaforte: i dati riservati cifrati a riposo e aperti col sensore.

Due livelli di prova:

1. la **crittografia pura** (`cassaforte.py`): roundtrip, password sbagliata,
   manomissione, sale. E' la parte che, se sbaglia, non se ne accorge nessuno,
   quindi e' quella con piu' casi.
2. le **rotte delle FAQ** (`/api/faq/*`): apertura col controllo biometrico,
   chiusura, e soprattutto i confini — che entrare nell'app **non** apra il
   modulo, che il testo dei segreti non finisca mai in chiaro nel file, e che la
   chiave del dispositivo non finisca mai in chiaro nel database.
"""
from test_comuni import *  # noqa: F401,F403

import sqlite3
import zlib
import base64


# ---------------------------------------------------------- crittografia pura

def test_cassaforte_cifra_e_decifra_cosi_com_e():
    chiaro = "Password del Wi-Fi: ciao123\nPIN cancello: 4567".encode()
    blob = cassaforte.cifra(chiaro, "padrone", sale=b"0123456789abcdef")
    assert cassaforte.decifra(blob, "padrone") == chiaro


def test_il_testo_non_e_in_chiaro_nel_file():
    """La prova che conta: il segreto non deve comparire nel blob."""
    chiaro = "La parola magica e girasole".encode()
    blob = cassaforte.cifra(chiaro, "padrone", sale=b"0123456789abcdef")
    assert "girasole" not in blob
    assert "parola" not in blob


def test_cassaforte_password_sbagliata_non_apre():
    blob = cassaforte.cifra(b"segretissimo", "giusta", sale=b"0123456789abcdef")
    with pytest.raises(cassaforte.CassaforteErrore):
        cassaforte.decifra(blob, "sbagliata")
    assert not cassaforte.password_giusta(blob, "sbagliata")
    assert cassaforte.password_giusta(blob, "giusta")


def test_cassaforte_file_manomesso_viene_rifiutato():
    """Cambiare un solo byte del testo cifrato deve far fallire la firma."""
    blob = cassaforte.cifra(b"contenuto importante", "padrone", sale=b"0123456789abcdef")
    dati = json.loads(blob)
    grezzo = bytearray(base64.b64decode(dati["d"]))
    grezzo[0] ^= 1                      # un bit diverso
    dati["d"] = base64.b64encode(bytes(grezzo)).decode()
    manomesso = json.dumps(dati)
    with pytest.raises(cassaforte.CassaforteErrore):
        cassaforte.decifra(manomesso, "padrone")


def test_cassaforte_una_firma_non_si_riusa_su_altre_iterazioni():
    """La firma copre anche le iterazioni: abbassarle per indovinare la password
    non deve passare inosservato."""
    blob = cassaforte.cifra(b"x", "padrone", sale=b"0123456789abcdef", iterazioni=1000)
    dati = json.loads(blob)
    dati["i"] = 1
    with pytest.raises(cassaforte.CassaforteErrore):
        cassaforte.decifra(json.dumps(dati), "padrone")


def test_cassaforte_due_scritture_sono_diverse():
    """Il sale e' nuovo a ogni scrittura: la stessa password non lascia mai lo
    stesso file, quindi non si puo' capire se due case hanno lo stesso segreto."""
    a = cassaforte.cifra(b"uguale", "padrone")
    b = cassaforte.cifra(b"uguale", "padrone")
    assert a != b


def test_cassaforte_il_vuoto_si_cifra():
    blob = cassaforte.cifra(b"", "padrone")
    assert cassaforte.decifra(blob, "padrone") == b""


def test_cassaforte_senza_password_non_cifra():
    with pytest.raises(cassaforte.CassaforteErrore):
        cassaforte.cifra(b"x", "")


def test_il_registro_vecchio_riceve_la_colonna_impronta(tmp_path, monkeypatch):
    """Un registro creato prima dell'impronta non ha la colonna: `CREATE TABLE
    IF NOT EXISTS` non la aggiunge, e ogni lettura fallirebbe con 'no such
    column'. La migrazione la mette a mano."""
    import sqlite3
    percorso = tmp_path / "registro.db"
    with sqlite3.connect(percorso) as db:
        # la forma vecchia: senza la colonna `impronta`
        db.execute("CREATE TABLE cassaforte_registro ("
                   "slug TEXT PRIMARY KEY, promemoria TEXT NOT NULL DEFAULT '', "
                   "chiusura_minuti INTEGER NOT NULL DEFAULT 15, "
                   "created_at TEXT NOT NULL DEFAULT (datetime('now')))")
        db.commit()
    monkeypatch.setattr(houses, "REGISTRY_PATH", str(percorso))
    monkeypatch.setattr(houses, "CASE_DIR", str(tmp_path / "case"))
    houses.init_registro()
    # ora si legge e si scrive l'impronta
    houses.cassaforte_registra("casa", impronta="psha256$x$y$z", percorso=str(percorso))
    assert houses.cassaforte_meta("casa", percorso=str(percorso))["impronta"] == "psha256$x$y$z"


# ------------------------------------------------------------------- le rotte
# Le FAQ non hanno piu' una password: si aprono col **controllo biometrico**. Le
# prove del modulo (voci, cifratura a riposo, chiusura automatica) stanno in
# `test_faq.py`; qui restano la crittografia pura e i confini della biometria.

CHIAVE_TEST = "chiave-del-dispositivo-di-prova"


def _apri(client, chiave=CHIAVE_TEST):
    return client.post("/api/faq/apri-biometria", json={"chiave": chiave})


def _aggiungi(client, question="Wi-Fi", answer="Rete: CasaRossi"):
    return client.post("/api/faq", json={"question": question, "answer": answer})


# ------------------------------------------------------------ il confine

def test_le_faq_nascono_chiuse_all_accesso(client):
    """Entrare nella casa non basta: il modulo e' chiuso finche' non si apre."""
    stato = client.get("/api/faq/stato").get_json()
    assert stato["aperta"] is False
    assert stato["biometria"] is False


def test_senza_sessione_non_si_tocca_niente(anon):
    """Nessun accesso alla casa, nessun modulo: ne' stato ne' voci."""
    assert anon.get("/api/faq/stato").status_code == 401
    assert anon.get("/api/faq").status_code == 401
    assert anon.post("/api/faq/apri-biometria", json={"chiave": "x"}).status_code == 401


def test_le_faq_di_una_casa_non_si_vedono_dall_altra(client):
    """Il blob e' nel database della casa: un'altra casa non lo vede."""
    _apri(client)
    _aggiungi(client, "Mio", "segreto-di-questa-casa")
    # una seconda casa, con la sua sessione: non deve vedere le voci della prima
    with app_module.app.test_client() as altro:
        altro.post("/api/houses", json={"nome": "Altra Casa", "password": "altrapw"})
        assert altro.get("/api/faq/stato").get_json()["aperta"] is False
        assert altro.get("/api/faq").get_json()["totale"] == 0
        _apri(altro, "chiave-dell-altra-casa")
        assert altro.get("/api/faq").get_json()["totale"] == 0


# ------------------------------------------------------------ biometria

def test_la_biometria_si_configura_alla_prima_apertura(client):
    assert client.get("/api/faq/stato").get_json()["biometria"] is False
    _apri(client)
    stato = client.get("/api/faq/stato").get_json()
    assert stato["biometria"] is True
    assert stato["aperta"] is True


def test_una_chiave_diversa_non_apre(client):
    _apri(client, "chiave-del-telefono")
    client.post("/api/faq/chiudi")
    assert _apri(client, "chiave-del-computer").status_code == 401
    assert client.get("/api/faq/stato").get_json()["aperta"] is False


def test_la_chiave_apre_senza_password(client):
    """La prova che l'utente chiede: aprire le FAQ col solo sensore."""
    _apri(client)
    _aggiungi(client, "Cancello", "codice 42")
    client.post("/api/faq/chiudi")
    _apri(client)
    voci = client.get("/api/faq").get_json()["voci"]
    assert voci and voci[0]["answer"] == "codice 42"


def test_senza_chiave_non_si_apre(client):
    """Nessun sensore, nessuna apertura: non c'e' una password di riserva."""
    assert _apri(client, "").status_code == 400
    assert client.get("/api/faq/stato").get_json()["aperta"] is False


def test_il_timbro_del_dispositivo_non_e_in_chiaro(client):
    """Il timbro custodisce la chiave, ma non in chiaro nel database."""
    _apri(client)
    _aggiungi(client, "X", "Y")
    with sqlite3.connect(houses.db_path(CASA_TEST)) as db:
        bio = db.execute("SELECT bio FROM cassaforte WHERE id = 1").fetchone()[0]
    assert bio and CHIAVE_TEST not in bio


def test_il_client_sa_usare_il_sensore(client):
    """Il percorso c'e' anche nel client: il pulsante chiama la rotta giusta."""
    js = client.get("/static/app.js").get_data(as_text=True)
    for pezzo in ("apriFaqConSensore", "bioDisponibile", "bioNuovaChiave",
                  "/api/faq/apri-biometria", "navigator.credentials"):
        assert pezzo in js, f"manca {pezzo} nel client"
    assert "crypto.getRandomValues" in js


def test_la_cassaforte_vecchia_riceve_la_colonna_bio(tmp_path):
    """Un database creato prima della biometria non ha la colonna `bio`:
    `CREATE TABLE IF NOT EXISTS` non la aggiunge, e la migrazione deve farlo a
    mano, altrimenti ogni lettura della scatola fallirebbe con 'no such column'."""
    import app as app_module
    percorso = str(tmp_path / "vecchio.db")
    app_module.init_db(percorso, con_ricettario=False)
    with sqlite3.connect(percorso) as db:
        db.row_factory = sqlite3.Row
        db.execute("INSERT INTO cassaforte (id, dati) VALUES (1, 'blob')")
        db.commit()
        db.execute("ALTER TABLE cassaforte DROP COLUMN bio")
        db.commit()
        assert "bio" not in {r[1] for r in db.execute("PRAGMA table_info(cassaforte)")}
        app_module.migrate(db)
        colonne = {r[1] for r in db.execute("PRAGMA table_info(cassaforte)")}
        dati = db.execute("SELECT dati FROM cassaforte WHERE id = 1").fetchone()[0]
    assert "bio" in colonne, "la colonna del timbro non e' stata aggiunta"
    assert dati == "blob", "la migrazione non deve toccare i dati"


def test_le_faq_nascono_anche_in_una_tabella_cassaforte_vecchia(tmp_path):
    """Un database di prima non ha `dati` con default: la migrazione non deve
    rompersi, e il blob si crea al primo salvataggio."""
    import app as app_module
    percorso = str(tmp_path / "vecchio2.db")
    app_module.init_db(percorso, con_ricettario=False)
    with sqlite3.connect(percorso) as db:
        db.row_factory = sqlite3.Row
        app_module.migrate(db)
        colonne = {r[1] for r in db.execute("PRAGMA table_info(cassaforte)")}
    assert {"dati", "bio"} <= colonne
