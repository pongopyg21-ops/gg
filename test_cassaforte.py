"""La cassaforte: i dati riservati cifrati con una password a parte.

Due livelli di prova:

1. la **crittografia pura** (`cassaforte.py`): roundtrip, password sbagliata,
   manomissione, sale. E' la parte che, se sbaglia, non se ne accorge nessuno,
   quindi e' quella con piu' casi.
2. le **rotte** (`/api/cassaforte/*`): creazione, apertura, chiusura, CRUD delle
   voci, e soprattutto i confini — che entrare nell'app **non** apra la
   cassaforte, e che il testo dei segreti non finisca mai in chiaro nel file.
"""
from test_comuni import *  # noqa: F401,F403

import sqlite3


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
    assert r.status_code == 401
    assert "ciao123" not in r.get_data(as_text=True)


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
    assert client.get("/api/cassaforte/voci").status_code == 401


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
