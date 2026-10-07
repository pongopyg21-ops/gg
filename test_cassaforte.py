"""La cassaforte: i dati riservati cifrati con una password a parte.

Due livelli di prova:

1. la **crittografia pura** (`cassaforte.py`): roundtrip, password sbagliata,
   manomissione, sale, impronta. E' la parte che, se sbaglia, non se ne accorge
   nessuno, quindi e' quella con piu' casi.
2. le **rotte** (`/api/cassaforte/*`): creazione, apertura, chiusura, cambio
   password, e soprattutto i confini — che entrare nell'app **non** apra la
   cassaforte, che il testo dei segreti non finisca mai in chiaro nel file, e che
   la **password non finisca mai nella sessione** (il biscotto e' leggibile dal
   client).
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


# ------------------------------------------------------- impronta della password

def test_impronta_verifica_la_password_senza_conservarla():
    """L'impronta serve solo a dire se la password e' giusta: non deve contenere
    la password, e non deve permettere di ricavarla."""
    imp = cassaforte.impronta("aprisicuro")
    assert "aprisicuro" not in imp
    assert cassaforte.impronta_giusta(imp, "aprisicuro") is True
    assert cassaforte.impronta_giusta(imp, "sbagliata") is False


def test_impronta_due_volte_e_diversa():
    """Il sale e' nuovo a ogni calcolo: due case con la stessa password non
    hanno la stessa impronta."""
    assert cassaforte.impronta("uguale") != cassaforte.impronta("uguale")


def test_impronta_assente_o_malformata_non_e_giusta():
    assert cassaforte.impronta_giusta("", "x") is False
    assert cassaforte.impronta_giusta("non-un-impronta", "x") is False


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

def _crea(client, password="aprisicuro", **extra):
    return client.post("/api/cassaforte/crea", json={"password": password, **extra})


def test_cassaforte_nasce_chiusa_all_accesso(client):
    """Entrare nella casa non apre la cassaforte: e' tutto il punto di averne una
    con una password propria."""
    _crea(client, "aprisicuro")
    stato = client.get("/api/cassaforte/stato").get_json()
    assert stato["esiste"] is True
    # appena creata resta aperta per chi l'ha appena fatta...
    assert stato["aperta"] is True
    # ...ma chiudendola, l'accesso all'app non basta a riaprirla
    client.post("/api/cassaforte/chiudi")
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is False


def test_cassaforte_si_riapre_con_la_sua_password(client):
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/chiudi")
    assert client.post("/api/cassaforte/apri", json={"password": "sbagliata"}).status_code == 401
    assert client.post("/api/cassaforte/apri", json={"password": "aprisicuro"}).status_code == 200
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is True


def test_cassaforte_chiusa_non_fa_leggere_le_voci(client):
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/voci", json={"question": "Wi-Fi", "answer": "ciao123"})
    client.post("/api/cassaforte/chiudi")
    r = client.get("/api/cassaforte/voci")
    assert r.status_code == 200
    # il valore non compare, non e' solo nascosto a schermo
    assert "ciao123" not in r.get_data(as_text=True)
    assert r.get_json()["totale"] == 0


def test_cassaforte_ciclo_completo_delle_voci(client):
    _crea(client, "aprisicuro")
    r = client.post("/api/cassaforte/voci", json={
        "question": "Wi-Fi di casa", "answer": "Rete: CasaRossi\nPassword: segreta",
        "category": "wifi", "pinned": True,
    })
    assert r.status_code == 201
    voce = r.get_json()
    elenco = client.get("/api/cassaforte/voci").get_json()
    assert elenco["totale"] == 1
    assert elenco["voci"][0]["answer"] == "Rete: CasaRossi\nPassword: segreta"

    assert client.put(f"/api/cassaforte/voci/{voce['id']}", json={
        "answer": "Password: nuova"}).get_json()["answer"] == "Password: nuova"
    assert client.delete(f"/api/cassaforte/voci/{voce['id']}").status_code == 200
    assert client.get("/api/cassaforte/voci").get_json()["totale"] == 0


def test_cassaforte_la_modifica_parziale_non_azzera_il_resto(client):
    _crea(client, "aprisicuro")
    voce = client.post("/api/cassaforte/voci", json={
        "question": "Idraulico", "answer": "333 1234567", "category": "contatti"}).get_json()
    dopo = client.put(f"/api/cassaforte/voci/{voce['id']}", json={"pinned": True}).get_json()
    assert dopo["question"] == "Idraulico"
    assert dopo["answer"] == "333 1234567"
    assert dopo["pinned"] is True


def test_cassaforte_titolo_obbligatorio_e_voce_inesistente(client):
    _crea(client, "aprisicuro")
    assert client.post("/api/cassaforte/voci", json={"answer": "x"}).status_code == 400
    assert client.put("/api/cassaforte/voci/999", json={"question": "x"}).status_code == 404
    assert client.delete("/api/cassaforte/voci/999").status_code == 404


def test_cassaforte_non_si_crea_due_volte(client):
    assert _crea(client, "aprisicuro").status_code == 201
    assert _crea(client, "altra").status_code == 400


def test_cassaforte_password_troppo_corta(client):
    assert _crea(client, "abc").status_code == 400


def test_cassaforte_il_testo_non_finisce_in_chiaro_nel_database(client):
    """Il vero requisito: chi apre il file `.db` con un editor non deve leggere i
    segreti. Si guarda il file grezzo, non l'API."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/voci", json={
        "question": "Banca", "answer": "PIN: 987654", "category": "codici"})
    percorso = houses.db_path(CASA_TEST)
    with sqlite3.connect(percorso) as db:
        riga = db.execute("SELECT dati FROM cassaforte WHERE id = 1").fetchone()
    assert riga is not None
    assert "987654" not in riga[0]
    assert "Banca" not in riga[0]


def test_cassaforte_cambia_password_e_le_voci_restano(client):
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/voci", json={"question": "Cancello", "answer": "1234"})
    r = client.put("/api/cassaforte/password", json={"attuale": "aprisicuro", "nuova": "altranuova"})
    assert r.status_code == 200
    client.post("/api/cassaforte/chiudi")
    assert client.post("/api/cassaforte/apri", json={"password": "aprisicuro"}).status_code == 401
    assert client.post("/api/cassaforte/apri", json={"password": "altranuova"}).status_code == 200
    voci = client.get("/api/cassaforte/voci").get_json()["voci"]
    assert voci[0]["answer"] == "1234"


def test_cassaforte_cambia_password_serve_la_vecchia(client):
    _crea(client, "aprisicuro")
    r = client.put("/api/cassaforte/password", json={"attuale": "sbagliata", "nuova": "nuova1"})
    assert r.status_code == 401


def test_cassaforte_si_richiude_da_sola(client, monkeypatch):
    """Dopo il tempo scelto la cassaforte si chiude da sola: senza, resterebbe
    aperta per sempre su un dispositivo lasciato sbloccato."""
    import app as app_module
    _crea(client, "aprisicuro", chiusura_minuti=1)
    client.post("/api/cassaforte/voci", json={"question": "X", "answer": "Y"})
    adesso = time.time()
    monkeypatch.setattr(app_module.time, "time", lambda: adesso + 120)
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is False
    assert client.get("/api/cassaforte/voci").get_json()["totale"] == 0


def _cookie_in_chiaro(intestazione):
    """Il contenuto decodificato di un Set-Cookie di sessione, o None."""
    try:
        biscotto = intestazione.split("session=", 1)[-1].split(";", 1)[0].lstrip(".")
        return zlib.decompress(base64.urlsafe_b64decode(biscotto + "==")).decode("utf-8")
    except Exception:
        return None


def test_la_password_non_finisce_nel_biscotto_di_sessione(client):
    """La password della cassaforte **non** deve stare nella sessione: la sessione
    e' un biscotto leggibile dal client, quindi ci finirebbe in chiaro. Al suo
    posto va l'impronta, che verifica ma non decifra."""
    risposta = _crea(client, "aprisicuro")
    client.post("/api/cassaforte/apri", json={"password": "aprisicuro"})
    # qualunque biscotto emesso nel giro non deve contenere la password in chiaro
    for intestazione in risposta.headers.getlist("Set-Cookie"):
        contenuto = _cookie_in_chiaro(intestazione)
        if contenuto is None:
            continue
        assert "aprisicuro" not in contenuto
    # e la garanzia strutturale: la password non e' mai messa in `session`
    sorgente = open(app_module.__file__, encoding="utf-8").read()
    assert 'session["cassaforte_password"]' not in sorgente
    assert 'session.get("cassaforte_password")' not in sorgente


def test_la_password_vive_solo_in_memoria(client):
    """L'apertura vive in una mappa di processo: e' cosi' che non finisce nel
    biscotto. Si verifica che dopo l'apertura la mappa contenga la password."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/chiudi")
    client.post("/api/cassaforte/apri", json={"password": "aprisicuro"})
    assert app_module._cassaforte_aperta(CASA_TEST) is True
    assert app_module._CASSAFORTE_APERTE[CASA_TEST]["password"] == "aprisicuro"
    client.post("/api/cassaforte/chiudi")
    assert app_module._cassaforte_aperta(CASA_TEST) is False


def test_cassaforte_di_una_casa_non_si_vede_dall_altra(client):
    """Due case sullo stesso server non condividono la cassaforte: chi non ha
    accesso alla casa non tocca la cassaforte ne' la vede."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/voci", json={"question": "Mio", "answer": "segreto"})
    # un secondo client, senza sessione, e' "un altro dispositivo": nessuna
    # accesso alla casa, quindi nessuna cassaforte
    with app_module.app.test_client() as anon:
        assert anon.get("/api/cassaforte/stato").status_code == 401
        assert anon.get("/api/cassaforte/voci").status_code == 401
        # e non puo' nemmeno aprirla: non ha la sessione della casa
        assert anon.post("/api/cassaforte/apri", json={"password": "aprisicuro"}).status_code == 401


# ------------------------------------------------------------- biometria
# La biometria *non* e' un accesso senza cassaforte: il sensore sblocca una
# **chiave** che il dispositivo custodisce, e la chiave apre la scatola
# biometrica che contiene la password. La password da sola non apre quella
# scatola, e la chiave da sola non e' la password: servono tutte e due le cose
# nella stessa misura di prima, cambia solo **dove** sta la password.

CHIAVE_TEST = "chiave-del-dispositivo-lunga-abbastanza"


def _attiva_biometria(client, chiave=CHIAVE_TEST):
    return client.put("/api/cassaforte/biometria", json={"chiave": chiave})


def test_la_biometria_non_e_attiva_finche_non_la_si_attiva(client):
    _crea(client, "aprisicuro")
    assert client.get("/api/cassaforte/stato").get_json()["biometria"] is False
    r = _attiva_biometria(client)
    assert r.status_code == 200
    assert r.get_json()["biometria"] is True


def test_la_biometria_apre_la_cassaforte_senza_password(client):
    """Il percorso che l'utente chiede: dito invece di password."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/voci", json={"question": "Banca", "answer": "PIN: 987654"})
    _attiva_biometria(client)
    client.post("/api/cassaforte/chiudi")
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is False
    # niente password: solo la chiave che il sensore custodisce
    r = client.post("/api/cassaforte/apri-biometria", json={"chiave": CHIAVE_TEST})
    assert r.status_code == 200
    assert r.get_json()["aperta"] is True
    voci = client.get("/api/cassaforte/voci").get_json()["voci"]
    assert voci[0]["answer"] == "PIN: 987654"


def test_una_chiave_sbagliata_non_apre(client):
    _crea(client, "aprisicuro")
    _attiva_biometria(client)
    client.post("/api/cassaforte/chiudi")
    r = client.post("/api/cassaforte/apri-biometria", json={"chiave": "un'altra-chiave"})
    assert r.status_code == 401
    assert client.get("/api/cassaforte/stato").get_json()["aperta"] is False


def test_senza_biometria_il_pulsante_del_sensore_non_apre(client):
    """Se la biometria non e' stata attivata, il percorso biometrico non esiste:
    non deve aprire per il solo fatto di mandare una chiave qualsiasi."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/chiudi")
    r = client.post("/api/cassaforte/apri-biometria", json={"chiave": CHIAVE_TEST})
    assert r.status_code == 401


def test_la_biometria_richiede_la_cassaforte_aperta_per_attivarsi(client):
    """Attivarla custodisce la password: se la cassaforte e' chiusa non c'e' una
    password da custodire, quindi si rifiuta invece di attivare qualcosa di rotto."""
    _crea(client, "aprisicuro")
    client.post("/api/cassaforte/chiudi")
    r = _attiva_biometria(client)
    assert r.status_code == 409


def test_la_password_non_apre_la_scatola_biometrica(client):
    """La scatola biometrica e' cifrata con la **chiave**, non con la password:
    chi conosce la password ma non ha il dispositivo non deve poterla leggere.
    Si guarda il file grezzo."""
    _crea(client, "aprisicuro")
    _attiva_biometria(client)
    percorso = houses.db_path(CASA_TEST)
    with sqlite3.connect(percorso) as db:
        riga = db.execute("SELECT bio FROM cassaforte WHERE id = 1").fetchone()
    assert riga is not None and riga[0], "la scatola biometrica deve esistere"
    # la password non compare in chiaro, e la scatola non si apre con la password
    assert "aprisicuro" not in riga[0]
    assert cassaforte.password_giusta(riga[0], "aprisicuro") is False
    # si apre solo con la chiave del dispositivo
    assert cassaforte.decifra(riga[0], CHIAVE_TEST).decode() == "aprisicuro"


def test_disattivare_la_biometria_torna_alla_sola_password(client):
    _crea(client, "aprisicuro")
    _attiva_biometria(client)
    r = client.delete("/api/cassaforte/biometria")
    assert r.status_code == 200
    assert r.get_json()["biometria"] is False
    client.post("/api/cassaforte/chiudi")
    assert client.post("/api/cassaforte/apri-biometria",
                       json={"chiave": CHIAVE_TEST}).status_code == 401
    assert client.post("/api/cassaforte/apri", json={"password": "aprisicuro"}).status_code == 200


def test_cambiare_password_fa_cadere_la_biometria(client):
    """La scatola biometrica custodiva la vecchia password: con la nuova non
    aprirebbe piu'. Va tolta, e l'utente avvisato, invece di lasciarla rotta."""
    _crea(client, "aprisicuro")
    _attiva_biometria(client)
    r = client.put("/api/cassaforte/password",
                   json={"attuale": "aprisicuro", "nuova": "altranuova"})
    assert r.status_code == 200
    assert r.get_json()["biometria_caduta"] is True
    assert r.get_json()["biometria"] is False
    client.post("/api/cassaforte/chiudi")
    assert client.post("/api/cassaforte/apri-biometria",
                       json={"chiave": CHIAVE_TEST}).status_code == 401


def test_la_chiave_biometrica_non_finisce_nel_database_in_chiaro(client):
    """La chiave e' un segreto del dispositivo: il server non deve conservarla in
    chiaro, solo dentro la scatola che essa stessa apre (non c'e' altra copia)."""
    _crea(client, "aprisicuro")
    _attiva_biometria(client)
    percorso = houses.db_path(CASA_TEST)
    with sqlite3.connect(percorso) as db:
        riga = db.execute("SELECT bio FROM cassaforte WHERE id = 1").fetchone()
    assert CHIAVE_TEST not in riga[0]


def test_il_client_sa_usare_la_biometria(client):
    """Il percorso c'e' anche nel client: il pulsante del sensore chiama le rotte
    giuste. Un backend senza il pezzo di interfaccia non e' una funzione."""
    js = client.get("/static/app.js").get_data(as_text=True)
    for pezzo in ("bioApri", "bioAttiva", "bioTogli", "bioDisponibile",
                  "/api/cassaforte/apri-biometria", "bioVerifica",
                  "navigator.credentials"):
        assert pezzo in js, f"manca {pezzo} nel client"
    # il sensore non e' il segreto: la chiave si genera a caso, non si ricava
    assert "crypto.getRandomValues" in js


def test_la_cassaforte_vecchia_riceve_la_colonna_bio(tmp_path):
    """Una cassaforte creata prima della biometria non ha la colonna `bio`:
    `CREATE TABLE IF NOT EXISTS` non la aggiunge, e la migrazione deve farlo a
    mano, altrimenti ogni lettura della scatola fallirebbe con 'no such column'."""
    import app as app_module
    percorso = str(tmp_path / "vecchio.db")
    app_module.init_db(percorso, con_ricettario=False)
    with sqlite3.connect(percorso) as db:
        db.row_factory = sqlite3.Row
        db.execute("INSERT INTO cassaforte (id, dati) VALUES (1, 'blob')")
        db.commit()
        # la forma di prima della biometria
        db.execute("ALTER TABLE cassaforte DROP COLUMN bio")
        db.commit()
        assert "bio" not in {r[1] for r in db.execute("PRAGMA table_info(cassaforte)")}
        app_module.migrate(db)
        colonne = {r[1] for r in db.execute("PRAGMA table_info(cassaforte)")}
        dati = db.execute("SELECT dati FROM cassaforte WHERE id = 1").fetchone()[0]
    assert "bio" in colonne, "la colonna della scatola biometrica non e' stata aggiunta"
    assert dati == "blob", "la migrazione non deve toccare i dati"
