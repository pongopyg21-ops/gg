"""Magazzino: voci, foto e scorte minime.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_voce_magazzino_si_crea(client):
    r = client.post("/api/storage", json={
        "name": "Sapone per i piatti", "category": "Pulizia casa",
        "place": "Cucina", "quantity": 2, "unit": "pz", "min_quantity": 1,
    })
    assert r.status_code == 201
    v = r.get_json()
    assert v["name"] == "Sapone per i piatti"
    assert v["low"] is False

def test_voce_magazzino_senza_nome_rifiutata(client):
    assert client.post("/api/storage", json={"quantity": 1}).status_code == 400

def test_voce_in_esaurimento_segnalata(client):
    """Sotto la scorta minima la voce si segnala: e' il motivo del magazzino."""
    client.post("/api/storage", json={"name": "Batterie", "quantity": 1, "min_quantity": 4})
    assert client.get("/api/storage").get_json()[0]["low"] is True

def test_voce_senza_scorta_minima_non_e_mai_in_esaurimento(client):
    """Senza soglia non si segnala nulla: 0 non e' una soglia."""
    client.post("/api/storage", json={"name": "Quadro", "quantity": 0, "min_quantity": 0})
    assert client.get("/api/storage").get_json()[0]["low"] is False

def test_giacenza_magazzino_si_ritocca_da_sola(client):
    """PATCH cambia la giacenza senza toccare il resto della voce."""
    v = client.post("/api/storage", json={
        "name": "Detersivo", "category": "Pulizia casa", "place": "Cantina",
        "quantity": 5, "min_quantity": 2, "notes": "scaffale alto"}).get_json()
    dopo = client.patch(f"/api/storage/{v['id']}", json={"quantity": 1}).get_json()
    assert dopo["quantity"] == pytest.approx(1)
    assert dopo["category"] == "Pulizia casa" and dopo["place"] == "Cantina"
    assert dopo["notes"] == "scaffale alto"
    assert dopo["low"] is True

def test_voce_magazzino_si_modifica_interamente(client):
    v = client.post("/api/storage", json={"name": "Rasoio", "quantity": 1}).get_json()
    dopo = client.put(f"/api/storage/{v['id']}", json={
        "name": "Rasoi", "category": "Igiene personale", "place": "Bagno",
        "quantity": 3, "unit": "pz", "min_quantity": 1, "notes": "usa e getta"}).get_json()
    assert dopo["name"] == "Rasoi" and dopo["quantity"] == pytest.approx(3)

def test_voce_magazzino_eliminata(client):
    v = client.post("/api/storage", json={"name": "Mensola"}).get_json()
    assert client.delete(f"/api/storage/{v['id']}").status_code == 200
    assert client.get("/api/storage").get_json() == []

def test_magazzino_inesistente_da_404(client):
    assert client.delete("/api/storage/999").status_code == 404

def test_dettaglio_di_una_voce(client):
    sid = client.post("/api/storage", json={"name": "Sapone", "quantity": 2}).get_json()["id"]
    r = client.get(f"/api/storage/{sid}")
    assert r.status_code == 200
    v = r.get_json()
    assert v["name"] == "Sapone"
    assert v["quantity"] == 2
    assert v["has_photo"] is False

def test_dettaglio_porta_la_foto(client):
    sid = voce_con_foto(client)
    v = client.get(f"/api/storage/{sid}").get_json()
    assert v["has_photo"] is True
    assert v["photo_url"].startswith(f"/api/storage/{sid}/photo?v=")

def test_una_voce_nasce_senza_foto(client):
    """Il campo esiste da subito: il client non deve indovinare se manca."""
    v = client.post("/api/storage", json={"name": "Sapone"}).get_json()
    assert v["has_photo"] is False
    assert v["photo_url"] == ""

def test_caricare_una_foto_la_rende_visibile_nellelenco(client):
    sid = voce_con_foto(client)
    v = next(x for x in client.get("/api/storage").get_json() if x["id"] == sid)
    assert v["has_photo"] is True
    # l'indirizzo porta la versione della foto: senza, il browser mostrerebbe
    # quella vecchia dopo una sostituzione
    assert v["photo_url"].startswith(f"/api/storage/{sid}/photo?v=")

def test_la_foto_si_rilegge_identica(client):
    """I byte che escono sono quelli che sono entrati, senza conversioni."""
    sid = voce_con_foto(client)
    r = client.get(f"/api/storage/{sid}/photo")
    assert r.status_code == 200
    assert r.data == PNG_1PX
    assert r.headers["Content-Type"].startswith("image/png")

def test_sostituire_la_foto_cambia_la_versione(client):
    """Ricaricare non accumula: la seconda foto prende il posto della prima."""
    sid = voce_con_foto(client)
    prima_versione = version_foto(client, sid)
    altra = PNG_1PX + b"\x00" * 10

    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url(altra)})
    assert r.status_code == 200
    assert client.get(f"/api/storage/{sid}/photo").data == altra
    # la versione cambia insieme ai byte: e' quello che evita al browser di
    # mostrare la foto vecchia presa dalla cache
    assert version_foto(client, sid) != prima_versione
    # una foto per voce, non una pila: la tabella ha una riga sola
    assert righe_foto(sid) == 1

def test_togliere_la_foto(client):
    sid = voce_con_foto(client)
    assert client.delete(f"/api/storage/{sid}/photo").status_code == 200
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404
    v = client.get("/api/storage").get_json()[0]
    assert v["has_photo"] is False

def test_eliminare_la_voce_porta_via_la_foto(client):
    """La foto non deve restare orfana nel database."""
    sid = voce_con_foto(client)
    assert righe_foto(sid) == 1
    client.delete(f"/api/storage/{sid}")
    assert righe_foto(sid) == 0

def test_foto_di_una_voce_inesistente_da_404(client):
    assert client.get("/api/storage/999/photo").status_code == 404
    assert client.post("/api/storage/999/photo", json={"image": data_url()}).status_code == 404

@pytest.mark.parametrize("valore,motivo", [
    ("", "vuoto"),
    ("ciao", "non e' un data url"),
    ("data:image/gif;base64,R0lGODlhAQABAAAAACw=", "formato non gestito"),
    ("data:image/png,ciao", "senza base64"),
    ("data:image/png;base64,!!!non-base64!!!", "base64 illeggibile"),
])
def test_foto_non_valida_rifiutata(client, valore, motivo):
    sid = client.post("/api/storage", json={"name": "Sapone"}).get_json()["id"]
    r = client.post(f"/api/storage/{sid}/photo", json={"image": valore})
    assert r.status_code == 400, f"accettata una foto {motivo}"
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404

def test_foto_troppo_pesante_rifiutata(client):
    """Un file sbagliato non deve far crescere il database senza limite."""
    sid = client.post("/api/storage", json={"name": "Sapone"}).get_json()["id"]
    enorme = b"\xff" * (app_module.FOTO_MAX_BYTE + 1000)
    r = client.post(f"/api/storage/{sid}/photo", json={"image": data_url(enorme)})
    assert r.status_code == 400
    assert client.get(f"/api/storage/{sid}/photo").status_code == 404

def test_la_foto_non_e_visibile_senza_accesso(anon):
    """Come il resto dei dati: senza casa collegata non si scarica nulla."""
    assert anon.get("/api/storage/1/photo").status_code == 401
    assert anon.post("/api/storage/1/photo", json={"image": data_url()}).status_code == 401

def test_ogni_casa_vede_solo_le_sue_foto(anon):
    """La foto e' un dato della casa: non deve trapelare nell'altra."""
    anon.post("/api/houses", json={"nome": "Casa Foto A", "password": "aaaa"})
    sid_a = anon.post("/api/storage", json={"name": "Sapone di A"}).get_json()["id"]
    anon.post(f"/api/storage/{sid_a}/photo", json={"image": data_url()})

    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa Foto B", "password": "bbbb"})
    # per B l'id non esiste: nessun dato di A, e nessun modo di agganciarsi
    assert anon.get(f"/api/storage/{sid_a}/photo").status_code == 404
    assert anon.get("/api/storage").get_json() == []

def test_pulizie_vecchie_si_riallineano_al_catalogo(tmp_path):
    """Una casa gia' avviata deve ricevere la nuova routine, non tenerla vecchia.

    Il seme non tocca le righe esistenti, quindi senza questo passaggio chi usa
    l'app da prima continuerebbe a vedere le voci che il catalogo ha tolto — la
    voce unita e "Arieggiare le stanze" — e il riordino non arriverebbe mai
    proprio a chi ha piu' da guadagnarci.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        # com'era il database prima: la voce unita, che il catalogo ha assorbito
        # in "Riordino generale"
        con.execute("INSERT INTO chores (name, area, frequency, minutes, month) "
                    "VALUES ('Raccogliere gli oggetti fuori posto', 'Tutta la casa', 'giornaliera', 5, NULL)")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        nomi = {r[0] for r in con.execute("SELECT name FROM chores")}
        assert "Raccogliere gli oggetti fuori posto" not in nomi, "la voce unita va tolta"
        assert "Arieggiare le stanze" not in nomi, "la voce non e' piu' un lavoro da spuntare"

def test_le_quotidiane_sono_tre(tmp_path):
    """Le attivita' quotidiane sono tre, non quattro.

    La giornata fissa deve restare una routine breve: le voci che dicevano la
    stessa cosa sono state unite e "Arieggiare le stanze" e' stata tolta, perche'
    e' aprire le finestre mentre si fa altro, non un lavoro a se'."""
    voci = igiene.catalogo()
    quotidiane = [v for v in voci if v["frequency"] == "giornaliera"]
    assert len(quotidiane) == 3
    nomi = {v["name"] for v in quotidiane}
    assert "Arieggiare le stanze" not in nomi
    # e il piano di oggi non le gonfia: le tre voci restano sotto il budget
    assert sum(v["minutes"] for v in quotidiane) <= 25

def test_pulizie_rimozione_non_perde_i_completamenti(tmp_path):
    """Togliere una voce non deve cancellare il lavoro registrato su di essa.

    La voce unita aveva dei completamenti spuntati dall'utente: spostarli sulla
    sostituta li conserva, cancellarli sarebbe una perdita silenziosa.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("INSERT INTO chores (name, area, frequency, minutes, month) "
                    "VALUES ('Raccogliere gli oggetti fuori posto', 'Tutta la casa', 'giornaliera', 5, NULL)")
        vecchio_id = con.execute(
            "SELECT id FROM chores WHERE name = 'Raccogliere gli oggetti fuori posto'").fetchone()[0]
        con.execute("INSERT INTO chore_log (chore_id, date, minutes) VALUES (?, '2026-09-20', 6)",
                    (vecchio_id,))
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        righe = con.execute(
            """SELECT c.name, l.date FROM chore_log l JOIN chores c ON c.id = l.chore_id""").fetchall()
        assert ("Riordino generale", "2026-09-20") in righe, "il completamento segue la sostituta"

def test_pulizie_minuti_ritoccati_a_mano_non_si_perdono(tmp_path):
    """La migrazione non riallinea i minuti: la stima dell'utente resta.

    I minuti sono una stima che l'utente puo' correggere, e il riallineamento
    del catalogo non li tocca: correggerla a forza cancellerebbe la sua
    correzione a ogni richiesta.
    """
    percorso = str(tmp_path / "vecchia.db")
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("UPDATE chores SET minutes = 7 WHERE name = 'Riordino generale'")
        con.commit()

    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as con:
        minuti = dict(con.execute("SELECT name, minutes FROM chores"))
        assert minuti["Riordino generale"] == 7, "la stima dell'utente resta"

def test_schema_applicato_a_una_casa_gia_esistente(tmp_path):
    """Una casa creata prima delle foto deve ricevere la tabella.

    E' il caso che conta per chi aggiorna: il database ha gia' i dati, e senza
    questo passaggio l'app risponderebbe "no such table" proprio a chi ha piu'
    da perdere.
    """
    percorso = str(tmp_path / "vecchia.db")
    # una casa di una versione precedente: schema di allora, senza le foto, e
    # con dentro un dato che deve sopravvivere all'aggiornamento
    app_module.init_db(percorso)
    with closing(sqlite3.connect(percorso)) as con:
        con.execute("INSERT INTO storage (name, quantity) VALUES ('Sapone', 3)")
        con.execute("DROP TABLE storage_photos")
        con.commit()
    assert not esiste_tabella(percorso, "storage_photos")

    app_module.init_db(percorso)

    assert esiste_tabella(percorso, "storage_photos")
    with closing(sqlite3.connect(percorso)) as con:
        assert con.execute("SELECT name FROM storage").fetchone()[0] == "Sapone"
