"""L'accesso col sensore: il dispositivo indirizza alla sua casa.

Il sensore e' un **permesso**, non un segreto: la chiave del dispositivo e'
quella che il client custodisce dietro Face ID / impronta, e il server la lega
alla casa che quel dispositivo ha creato. All'avvio la chiave trova la casa e la
sessione si apre senza scrivere nome e password.

Qui si prova il legame (`houses.biometria_*`), la rotta pubblica
`/api/login-biometria`, la creazione che collega il sensore, e le rotte del
Profilo per collegare un dispositivo nuovo o scollegarlo.
"""
from test_comuni import *  # noqa: F401,F403

import houses


CHIAVE = "a" * 64
ALTRA = "b" * 64


# --------------------------------------------------------- il legame (houses)

def test_una_chiave_trova_la_sua_casa(casa_test):
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    assert houses.biometria_casa(CHIAVE) == CASA_TEST
    assert houses.biometria_casa(ALTRA) is None


def test_aggiungere_due_volte_non_duplica(casa_test):
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    assert houses.biometria_chiavi(CASA_TEST) == [CHIAVE]


def test_chiave_vuota_non_lega(casa_test):
    with pytest.raises(ValueError):
        houses.biometria_aggiungi(CASA_TEST, "")


def test_casa_inesistente_non_si_lega(casa_test):
    with pytest.raises(ValueError):
        houses.biometria_aggiungi("casa-che-non-esiste", CHIAVE)


def test_togliere_una_chiave_lascia_le_altre(casa_test):
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    houses.biometria_aggiungi(CASA_TEST, ALTRA)
    houses.biometria_togli(CASA_TEST, CHIAVE)
    assert houses.biometria_chiavi(CASA_TEST) == [ALTRA]
    assert houses.biometria_casa(CHIAVE) is None


def test_togliere_tutte_le_chiavi(casa_test):
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    houses.biometria_aggiungi(CASA_TEST, ALTRA)
    houses.biometria_togli(CASA_TEST)
    assert houses.biometria_chiavi(CASA_TEST) == []


def test_eliminare_la_casa_slega_le_chiavi(casa_test):
    houses.biometria_aggiungi(CASA_TEST, CHIAVE)
    houses.elimina(CASA_TEST)
    assert houses.biometria_casa(CHIAVE) is None


# --------------------------------------------------------- la rotta pubblica

def test_la_chiave_del_dispositivo_apre_la_sessione(anon):
    anon.post("/api/houses", json={"nome": "Casa Bio", "password": "biopw",
                                   "chiave": CHIAVE})
    anon.post("/api/logout", json={})
    # la sessione e' chiusa: la rotta e' pubblica, non serve nessuna casa
    r = anon.post("/api/login-biometria", json={"chiave": CHIAVE})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["biometria"] is True
    # la sessione ora e' aperta: la home risponde
    assert anon.get("/api/session").get_json()["authenticated"] is True


def test_senza_chiave_non_si_apre(anon):
    r = anon.post("/api/login-biometria", json={})
    assert r.status_code == 400


def test_chiave_ignota_non_indirizza(anon):
    """Un dispositivo che non conosce case: 404, non un guasto. Il client
    ripiega sull'accesso con nome e password."""
    r = anon.post("/api/login-biometria", json={"chiave": ALTRA})
    assert r.status_code == 404
    assert r.get_json()["biometria"] is False


def test_la_casa_eliminata_non_si_apre(anon):
    anon.post("/api/houses", json={"nome": "Casa Bio", "password": "biopw",
                                   "chiave": CHIAVE})
    houses.elimina("casa-bio")
    anon.post("/api/logout", json={})
    assert anon.post("/api/login-biometria", json={"chiave": CHIAVE}).status_code == 404


def test_la_rotta_e_pubblica(anon):
    """Deve partire **prima** del login, altrimenti non servirebbe a niente."""
    assert "/api/login-biometria" in app_module.ROTTE_PUBBLICHE


# --------------------------------------------------- creazione e Profilo

def test_creare_una_casa_senza_sensore_la_lascia_col_nome(anon):
    r = anon.post("/api/houses", json={"nome": "Casa Normale", "password": "normale"})
    assert r.status_code == 201
    assert r.get_json()["biometria"] is False
    assert houses.biometria_chiavi("casa-normale") == []


def test_un_dispositivo_nuovo_si_collega_dal_profilo(client):
    """Chi entra col nome e la password puo' collegare il sensore dopo: la
    volta successiva basta il sensore."""
    r = client.post("/api/biometria/casa", json={"chiave": CHIAVE})
    assert r.status_code == 200
    assert r.get_json()["collegato"] is True
    assert client.get(f"/api/biometria/casa?chiave={CHIAVE}").get_json()["collegato"] is True
    assert client.get(f"/api/biometria/casa?chiave={ALTRA}").get_json()["collegato"] is False


def test_scollegare_il_dispositivo(client):
    client.post("/api/biometria/casa", json={"chiave": CHIAVE})
    r = client.delete("/api/biometria/casa", json={"chiave": CHIAVE})
    assert r.get_json()["collegato"] is False
    assert client.get(f"/api/biometria/casa?chiave={CHIAVE}").get_json()["collegato"] is False


def test_il_collegamento_richiede_la_sessione(anon):
    """Senza casa collegata non si lega niente a nessuno."""
    assert anon.post("/api/biometria/casa", json={"chiave": CHIAVE}).status_code == 401


def test_collegare_senza_chiave_e_un_errore(client):
    assert client.post("/api/biometria/casa", json={}).status_code == 400


# ------------------------------------------------------------- migrazione

def test_il_registro_vecchio_riceve_la_tabella_biometria(tmp_path):
    """Un registro creato prima della biometria non ha la tabella: `CREATE TABLE
    IF NOT EXISTS` non la aggiunge, e il legame fallirebbe con 'no such table'.
    `init_registro` la crea a ogni avvio."""
    registro = tmp_path / "vecchio.db"
    houses.init_registro(str(registro))
    houses.registra(CASA_TEST, "Casa Test", PASSWORD_TEST, percorso=str(registro))
    import sqlite3 as _sqlite
    with closing(_sqlite.connect(registro)) as db:
        db.execute("DROP TABLE IF EXISTS case_biometria")
        db.commit()
    houses.biometria_aggiungi(CASA_TEST, CHIAVE, percorso=str(registro))
    assert houses.biometria_casa(CHIAVE, percorso=str(registro)) == CASA_TEST
