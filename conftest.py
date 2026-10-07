"""Fixture condivise dai test (pytest le scopre da qui, senza import).

Estratto da `test_cucina.py`: i percorsi dei dati, il client collegato e il
client anonimo. Sono le sole cose che devono essere visibili a tutti i file
di test senza importarle.
"""
from test_comuni import *  # noqa: F401,F403


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
