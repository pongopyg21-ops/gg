"""Copia dei dati, percorsi e copie automatiche.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_backup_richiede_accesso(anon):
    assert anon.get("/api/backup").status_code == 401

def test_backup_contiene_i_dati_della_casa_e_ricostruisce_un_database(client, tmp_path):
    import io as _io
    import zipfile as _zip

    # un dato riconoscibile, per ritrovarlo dopo il giro completo
    client.post("/api/shopping", json={"name": "Carciofi per la copia", "qty": 2})

    r = client.get("/api/backup")
    assert r.status_code == 200
    assert r.mimetype == "application/zip"

    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    nomi = archivio.namelist()
    # il database col suo nome, piu' il file in scena
    assert any(n.endswith(".db") for n in nomi), nomi
    assert "LEGGIMI.txt" in nomi
    assert "Copia dei dati" in archivio.read("LEGGIMI.txt").decode()

    # il file estratto deve essere un database che l'app sa riaprire, non il
    # testo delle istruzioni SQL: rinominato `.db` un dump testuale farebbe
    # rispondere `file is not a database`, e il ripristino fallirebbe
    dati = archivio.read([n for n in nomi if n.endswith(".db")][0])
    assert dati[:16] == b"SQLite format 3\x00", dati[:32]
    percorso = tmp_path / "ripristinato.db"
    percorso.write_bytes(dati)
    with closing(sqlite3.connect(percorso)) as riaperto:
        trovato = riaperto.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE name LIKE '%Carciofi per la copia%'"
        ).fetchone()[0]
    assert trovato == 1

def test_backup_porta_via_anche_le_foto(client, tmp_path):
    """Le foto stanno nel database proprio per questo: la copia resta un file solo.

    Se le foto fossero su disco, l'archivio sarebbe incompleto e chi ripristina
    perderebbe le immagini senza accorgersene.
    """
    import io as _io
    import zipfile as _zip

    sid = voce_con_foto(client, nome="Scatola fotografata")

    r = client.get("/api/backup")
    assert r.status_code == 200
    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    dati = archivio.read([n for n in archivio.namelist() if n.endswith(".db")][0])
    percorso = tmp_path / "con-foto.db"
    percorso.write_bytes(dati)

    with closing(sqlite3.connect(percorso)) as riaperto:
        riga = riaperto.execute(
            "SELECT storage_id, mime, data FROM storage_photos WHERE storage_id = ?",
            (sid,)).fetchone()
    assert riga is not None, "la foto non e' finita nel backup"
    assert riga[1] == "image/png"
    assert riga[2] == PNG_1PX

def test_backup_non_contiene_le_altre_case(client, tmp_path):
    """L'archivio non deve contenere tracce di case diverse da quella collegata.

    Il registro (`houses.db`) e' la cosa da non far uscire: contiene nomi e
    password di tutte le case. Un utente collegato a una casa non deve poter
    scaricare l'elenco, ne' i dati, dell'altra.
    """
    import io as _io
    import zipfile as _zip

    r = client.get("/api/backup")
    assert r.status_code == 200

    archivio = _zip.ZipFile(_io.BytesIO(r.data))
    nomi = archivio.namelist()
    # i byte non testuali si saltano: lo schema delle tabelle e' testo UTF-8, e
    # quello basta a scoprire un nome indesiderato dentro l'archivio
    grezzo = b"".join(archivio.read(n) for n in nomi)
    contenuto = grezzo.decode("utf-8", "ignore")

    # il registro delle case non deve comparire, in nessuna forma: ne' come file,
    # ne' come tabella dentro l'esportazione
    assert not any("houses.db" in n for n in nomi), nomi
    assert "CREATE TABLE houses" not in contenuto
    # non si cerca la parola "password" nuda: e' anche nelle note dello schema
    # (che finiscono in `sqlite_master`), quindi darebbe un falso allarme. Si
    # cerca la forma vera dell'hash del registro, che e' quello che non deve
    # uscire.
    assert "pbkdf2_sha256" not in contenuto, "l'hash delle password non deve uscire"

    # controlla anche la struttura, non solo il testo: il database esportato non
    # deve avere una tabella che somigli al registro
    percorso = tmp_path / "esportato.db"
    percorso.write_bytes(archivio.read([n for n in nomi if n.endswith(".db")][0]))
    with closing(sqlite3.connect(percorso)) as esportato:
        tabelle = {r[0].lower() for r in esportato.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert not (tabelle & {"houses", "case", "registry"}), tabelle

def test_data_dir_sposta_registro_case_e_database_storico(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    # i percorsi sono calcolati all'import: per provare la variabile va ricaricato
    importlib.reload(houses)
    try:
        assert houses.REGISTRY_PATH == str(tmp_path / "houses.db")
        assert houses.CASE_DIR == str(tmp_path / "case")

        # il registro deve nascere dove abbiamo detto, non accanto al codice
        houses.init_registro()
        assert (tmp_path / "houses.db").exists()
        assert not (tmp_path.parent / "houses.db").exists()

        houses.registra("casa-prova", "Casa Prova", "segreta", "cucina.db")
        # la casa storica punta a un file che sta in DATA_DIR: cercarlo accanto al
        # codice lo renderebbe invisibile con i dati altrove
        assert houses.db_path("casa-prova").endswith("cucina.db")
        assert os.path.dirname(houses.db_path("casa-prova")) == str(tmp_path)
    finally:
        # si ripristina il modulo vero, altrimenti i test successivi userebbero
        # una DATA_DIR temporanea ormai cancellata
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)

def test_la_copia_e_un_database_riapribile_con_i_dati_dentro(client):
    """Non basta che il file esista: deve essere un database che l'app riapre."""
    client.post("/api/shopping", json={"name": "Sedano per la copia", "qty": 3})

    scritte = copie.fai_copie()
    assert len(scritte) == 1, scritte

    with closing(sqlite3.connect(scritte[0])) as copiato:
        trovato = copiato.execute(
            "SELECT COUNT(*) FROM shopping_items WHERE name LIKE '%Sedano per la copia%'"
        ).fetchone()[0]
    assert trovato == 1

def test_la_prima_copia_arriva_subito_anche_col_server_appena_acceso(client):
    """Se la prima copia aspettasse un giorno, chi installa l'app oggi non
    avrebbe nessuna copia per un giorno intero."""
    copie.svuota()
    assert copie.elenco(CASA_TEST)["quante"] == 0

    app_module._giro_di_copie()

    assert copie.elenco(CASA_TEST)["quante"] == 1

def test_non_si_accumulano_oltre_il_limite(client):
    """La cartella non deve crescere senza fine su una macchina accesa per mesi."""
    import datetime as _dt

    # copie forzate con orari diversi: due copie nello stesso secondo avrebbero
    # lo stesso nome e la seconda sovrascriverebbe la prima invece di sommarsi
    for i in range(copie.QUANTE + 4):
        copie.copia_casa(CASA_TEST, quando=_dt.datetime.now() + _dt.timedelta(minutes=i))

    assert copie.elenco(CASA_TEST)["quante"] == copie.QUANTE

def test_una_casa_non_tocca_le_copie_dell_altra(client):
    """Le copie stanno separate per casa: chi ne cancella una non deve poter
    toccare lo spazio dell'altra."""
    altra = houses.crea("Casa Vicina", "password-vicina")
    app_module.init_db(houses.db_path(altra), con_ricettario=True)

    copie.fai_copie()

    assert copie.elenco(CASA_TEST)["quante"] == 1
    assert copie.elenco(altra)["quante"] == 1
    # ognuna nel suo spazio, e nessun file condiviso
    assert copie._copie_di(CASA_TEST)[0] != copie._copie_di(altra)[0]

def test_il_giro_automatico_non_ricopia_una_casa_gia_copiata(client):
    """Il giro gira ogni ora ma la copia e' giornaliera: senza questo salto
    una casa avrebbe ventiquattro copie al giorno e la cartella si riempirebbe."""
    app_module._giro_di_copie()
    prima = copie._copie_di(CASA_TEST)

    scritto = copie.fai_copie(forse=True)

    assert scritto == [], scritto
    assert copie._copie_di(CASA_TEST) == prima

def test_una_copia_fallita_non_lascia_un_file_a_meta(client, monkeypatch):
    """Il file provvisorio non deve restare nella cartella: verrebbe contato
    come copia valida al giro dopo, e la copia piu' recente sarebbe rotta.

    Si imita il caso vero: SQLite crea il file appena si connette, quindi un
    guasto durante la scrittura lascia un file a meta' che senza pulizia
    resterebbe li' col nome di una copia buona.
    """
    vero = sqlite3.connect
    chiamate = []

    class Finta:
        def backup(self, *_a):
            raise sqlite3.OperationalError("disco pieno")

        def close(self):
            pass

    class FintoSqlite:
        """Visto solo da `copie`: patching il modulo vero toccherebbe anche il
        registro delle case, che deve continuare a funzionare."""
        Error = sqlite3.Error

        @staticmethod
        def connect(percorso, *a, **k):
            chiamate.append(percorso)
            if len(chiamate) == 1:
                # la sorgente e' quella che fallisce durante la copia, quindi il
                # destinatario e' un file vero: e' proprio il file a meta' che la
                # pulizia deve togliere
                return Finta()
            return vero(percorso)

    monkeypatch.setattr(copie, "sqlite3", FintoSqlite)
    with pytest.raises(sqlite3.OperationalError):
        copie.copia_casa(CASA_TEST)

    cartella = os.path.join(copie.cartella(), CASA_TEST)
    avanzi = os.listdir(cartella) if os.path.isdir(cartella) else []
    assert avanzi == [], avanzi

def test_api_copie_dice_quante_ce_ne_sono(client):
    """L'utente deve poter vedere che le copie ci sono, senza cercare sul disco."""
    app_module._giro_di_copie()
    d = client.get("/api/copie").get_json()
    assert d["quante"] == 1
    assert d["conservate"] == copie.QUANTE
    assert d["ultima"], d

def test_api_copie_richiede_accesso(anon):
    assert anon.get("/api/copie").status_code == 401

def test_api_copie_non_nomina_le_altre_case(client):
    """Il conteggio e' della sola casa collegata: le altre non si nominano."""
    altra = houses.crea("Casa Vicina", "password-vicina")
    app_module.init_db(houses.db_path(altra), con_ricettario=True)
    app_module._giro_di_copie()

    d = client.get("/api/copie").get_json()
    assert d["quante"] == 1
    testo = json.dumps(d, ensure_ascii=False)
    assert "vicina" not in testo.lower()
