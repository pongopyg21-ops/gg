"""Dispensa: suggerimenti e scadenze.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_suggerimenti_vuoti_con_dispensa_vuota(client):
    """Senza niente in casa non c'e' niente da suggerire, e nessun errore."""
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    r = client.get("/api/pantry/suggerimenti")
    assert r.status_code == 200
    assert r.get_json() == {"dispensa": 0, "suggerimenti": []}

def test_suggerisce_le_ricette_che_usa_la_dispensa(client):
    """La ricetta i cui ingredienti sono in casa viene suggerita, e risulta pronta."""
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                        "unit": i["unit"]})
    dati = client.get("/api/pantry/suggerimenti").get_json()
    nomi = [s["name"] for s in dati["suggerimenti"]]
    assert "Cacio e pepe" in nomi
    cacio_sug = next(s for s in dati["suggerimenti"] if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is True
    assert cacio_sug["mancanti"] == 0
    assert cacio_sug["punteggio"] == 1.0
    # e' la prima: con tutti gli ingredienti in casa non puo' essere superata
    assert nomi[0] == "Cacio e pepe"

def test_una_ricetta_coperta_in_parte_non_e_pronta(client):
    """Mezza scorta non copre: la ricetta si suggerisce, ma non come pronta.

    E' il caso in cui l'errore sarebbe peggiore: dire «hai tutto» con 100 g di
    farina al posto di 500 manda a cucinare una ricetta che non si fa.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    # meta' quantita' per ogni ingrediente: nessuno e' coperto del tutto
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"] / 2,
                                        "unit": i["unit"]})
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is False
    assert cacio_sug["parziali"] == len(cacio["items"])
    assert cacio_sug["coperti"] == 0
    assert cacio_sug["punteggio"] == 0.5

def test_le_quantita_si_confrontano_solo_fra_unita_convertibili(client):
    """500 g coprono mezzo chilo, ma una confezione non copre un pezzo.

    Se le unita' non convertibili venissero sommate lo stesso, un ingrediente
    senza scorta risulterebbe coperto e la ricetta direbbe «hai tutto» a vuoto.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    spaghetti = next(i for i in cacio["items"] if i["name"] == "Spaghetti")
    # in dispensa mezzo chilo, in ricetta 180 g: stesso peso, unita' diverse
    client.post("/api/pantry", json={"name": "Spaghetti", "quantity": 0.5, "unit": "kg"})
    for i in cacio["items"]:
        if i["name"] != "Spaghetti":
            client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                            "unit": i["unit"]})
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is True, "0,5 kg doveva coprire 180 g"

    # e una confezione non copre un pezzo: si cambia l'unita' della riga di
    # dispensa direttamente sul database della casa collegata
    percorso = houses.db_path(CASA_TEST)
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("""UPDATE pantry SET unit = 'confezione'
                      WHERE ingredient_id = (SELECT id FROM ingredients
                                             WHERE name = 'Spaghetti')""")
        db.commit()
    cacio_sug = next(s for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]
                     if s["name"] == "Cacio e pepe")
    assert cacio_sug["pronta"] is False, "una confezione non copre 180 g"

def test_il_suggerimento_rispetta_le_allergie(client):
    """Una ricetta con un allergene dichiarato non viene suggerita.

    Qui l'app dice «cucina questa»: proporre un allergene non e' una svista da
    correggere, e' un errore. Il filtro sta sul server, quindi non dipende da
    cosa il browser decide di mostrare.
    """
    import seed
    for r in seed.RECIPES:
        client.post("/api/recipes", json=r)
    client.put("/api/profile", json={"restrictions": "glutine"})
    cacio = next(r for r in client.get("/api/recipes?full=1").get_json()
                 if r["name"] == "Cacio e pepe")
    for i in cacio["items"]:
        client.post("/api/pantry", json={"name": i["name"], "quantity": i["quantity"],
                                        "unit": i["unit"]})
    nomi = [s["name"] for s in client.get("/api/pantry/suggerimenti").get_json()["suggerimenti"]]
    assert "Cacio e pepe" not in nomi, "suggerita una ricetta con glutine"

def test_una_ricetta_corta_e_completa_batte_una_lunga_e_incompleta():
    """Il punteggio e' una frazione, non un conteggio di ingredienti coperti.

    Contando gli ingredienti coperti vincerebbe la ricetta piu' lunga: una da
    dodici con sette in dispensa batterebbe una da quattro con quattro, che e'
    invece quella che si puo' cucinare stasera. E' il motivo per cui il
    punteggio e' una frazione.
    """
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "punteggio.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        # ingredienti una volta sola: la copertura si misura sull'ingrediente,
        # quindi le due ricette devono condividere le stesse righe
        ids = {}
        for nome_ing in "abcdefghijkl":
            ids[nome_ing] = db.execute("INSERT INTO ingredients (name) VALUES (?)",
                                       (nome_ing,)).lastrowid
        def ricetta(nome, lettere):
            rid = db.execute("INSERT INTO recipes (name) VALUES (?)", (nome,)).lastrowid
            for lettera in lettere:
                db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                           " VALUES (?, ?, 1, 'pz')", (rid, ids[lettera]))
        ricetta("Corta e completa", "abcd")
        ricetta("Lunga e incompleta", "abcdefghijkl")
        # in casa ci sono solo a, b, c, d
        for lettera in "abcd":
            db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                       (ids[lettera],))
        db.commit()
        esito = dispensa.suggerimenti(db)
    nomi = [s["name"] for s in esito["suggerimenti"]]
    assert nomi[0] == "Corta e completa", nomi
    lunga = next(s for s in esito["suggerimenti"] if s["name"] == "Lunga e incompleta")
    corta = next(s for s in esito["suggerimenti"] if s["name"] == "Corta e completa")
    assert corta["coperti"] == 4 and corta["punteggio"] == 1.0
    assert lunga["coperti"] == 4 and lunga["punteggio"] < 1.0

def test_una_ricetta_senza_ingredienti_non_e_un_suggerimento():
    """Senza ingredienti non c'e' niente da consumare, quindi non si suggerisce."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "vuota.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        db.execute("INSERT INTO recipes (name) VALUES ('Solo un nome')")
        iid = db.execute("INSERT INTO ingredients (name) VALUES ('qualcosa')").lastrowid
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                   (iid,))
        db.commit()
        esito = dispensa.suggerimenti(db)
    assert esito["suggerimenti"] == []

def test_la_scadenza_si_salva_e_si_rilegge(client):
    r = client.post("/api/pantry", json={"name": "Yogurt", "quantity": 1, "unit": "pz",
                                        "expires_at": "2026-10-05"})
    assert r.status_code == 201
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["expires_at"] == "2026-10-05"

def test_una_scadenza_non_valida_non_entra_nel_database(client):
    """Un testo che non e' una data non deve salvarvisi: romperebbe l'ordinamento
    e i confronti, e l'utente vedrebbe una data che non ha scritto."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 1, "unit": "pz",
                                     "expires_at": "domani"})
    assert client.get("/api/pantry").get_json()[0]["expires_at"] is None

def test_la_scadenza_si_puo_togliere_senza_toccare_la_quantita(client):
    """Il campo della scadenza e' separato dalla quantita': svuotarlo la toglie,
    e non deve azzerare la quantita' scritta nell'altro campo."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 3, "unit": "pz",
                                     "expires_at": "2026-10-05"})
    pid = client.get("/api/pantry").get_json()[0]["id"]
    client.patch(f"/api/pantry/{pid}", json={"expires_at": ""})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["expires_at"] is None
    assert voce["quantity"] == 3

def test_la_quantita_si_cambia_senza_cancellare_la_scadenza(client):
    """Aggiornare la quantita' non manda il campo scadenza: senza la regola del
    "tocca solo se presente", la scadenza sparirebbe a ogni cambio di quantita'."""
    client.post("/api/pantry", json={"name": "Yogurt", "quantity": 3, "unit": "pz",
                                     "expires_at": "2026-10-05"})
    pid = client.get("/api/pantry").get_json()[0]["id"]
    client.patch(f"/api/pantry/{pid}", json={"quantity": 2})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["quantity"] == 2
    assert voce["expires_at"] == "2026-10-05"

def test_aggiungendo_scorte_vince_la_scadenza_piu_vicina(client):
    """Due partite dello stesso ingrediente con scadenze diverse: quella che
    scade prima e' quella da guardare, e deve restare in evidenza."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-20"})
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-03"})
    voce = client.get("/api/pantry").get_json()[0]
    assert voce["quantity"] == 2
    assert voce["expires_at"] == "2026-10-03"

def test_una_scorta_senza_data_non_cancella_quella_con_data(client):
    """Chi aggiunge una partita senza sapere la scadenza non deve cancellare
    quella che sapeva: la data che c'era resta."""
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l",
                                     "expires_at": "2026-10-03"})
    client.post("/api/pantry", json={"name": "Latte", "quantity": 1, "unit": "l"})
    assert client.get("/api/pantry").get_json()[0]["expires_at"] == "2026-10-03"

def test_una_ricetta_che_consuma_una_scadenza_viene_prima():
    """Fra due ricette ugualmente coperte, va suggerita per prima quella che
    consuma una scorta in scadenza: e' quella da cucinare adesso."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "scadenze.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        # due ingredienti: uno scade fra due giorni, l'altro non scade
        presto = db.execute("INSERT INTO ingredients (name) VALUES ('Da consumare')").lastrowid
        tardi = db.execute("INSERT INTO ingredients (name) VALUES ('Tranquillo')").lastrowid
        for iid in (presto, tardi):
            db.execute("INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (?, 1, 'pz')",
                       (iid,))
        db.execute("UPDATE pantry SET expires_at = '2026-10-04' WHERE ingredient_id = ?", (presto,))
        # due ricette da un ingrediente ciascuna, ugualmente coperte
        for nome, iid in (("Usa il fresco", presto), ("Usa il durevole", tardi)):
            rid = db.execute("INSERT INTO recipes (name) VALUES (?)", (nome,)).lastrowid
            db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                       " VALUES (?, ?, 1, 'pz')", (rid, iid))
        db.commit()
        esito = dispensa.suggerimenti(db, oggi=__import__("datetime").date(2026, 10, 2))
    nomi = [s["name"] for s in esito["suggerimenti"]]
    assert nomi[0] == "Usa il fresco", nomi
    fresco = next(s for s in esito["suggerimenti"] if s["name"] == "Usa il fresco")
    assert fresco["scadono"] == ["Da consumare"]
    durevole = next(s for s in esito["suggerimenti"] if s["name"] == "Usa il durevole")
    assert durevole["scadono"] == []

def test_una_scadenza_lontana_non_mette_in_cima_la_ricetta():
    """Una scadenza oltre la settimana non e' un problema di stasera: non deve
    riordinare i suggerimenti."""
    import sqlite3 as sq
    from contextlib import closing as cl
    import datetime as dt
    percorso = os.path.join(tempfile.mkdtemp(), "lontana.db")
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        db.row_factory = sq.Row
        iid = db.execute("INSERT INTO ingredients (name) VALUES ('Durevole')").lastrowid
        db.execute("INSERT INTO pantry (ingredient_id, quantity, unit, expires_at)"
                   " VALUES (?, 1, 'pz', '2026-12-31')", (iid,))
        rid = db.execute("INSERT INTO recipes (name) VALUES ('Una ricetta')").lastrowid
        db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                   " VALUES (?, ?, 1, 'pz')", (rid, iid))
        db.commit()
        esito = dispensa.suggerimenti(db, oggi=dt.date(2026, 10, 2))
    assert esito["suggerimenti"][0]["scadono"] == []

def test_la_dispensa_vuota_lo_dice_invece_di_tacere(client):
    """Il riquadro dei suggerimenti con la dispensa vuota resta nascosto e sembra
    che la funzione non esista: si esegue `renderSuggerimenti` vera con node, con
    la risposta del server, e si guarda cosa finisce nella pagina."""
    js = client.get("/static/app.js").get_data(as_text=True)
    codice = _estrai_funzione_js(js, "renderSuggerimenti")
    preludio = """
let contenuto = '';
function $(sel) { return { set innerHTML(v) { contenuto = v; },
                            get innerHTML() { return contenuto; } }; }
function esc(s) { return String(s); }
let risposta = { dispensa: 0, suggerimenti: [] };
async function api() { return risposta; }
"""
    coda = """
(async () => {
  await renderSuggerimenti();
  const vuota = contenuto;
  risposta = { dispensa: 4, suggerimenti: [] };
  await renderSuggerimenti();
  console.log(JSON.stringify({ vuota: vuota, piena: contenuto }));
})();
"""
    d = _esegui_node(preludio + codice + coda)
    # con la dispensa vuota si dice cosa fare, invece di lasciare il vuoto
    assert "Aggiungi qualche ingrediente" in d["vuota"]
    # con la dispensa piena ma nessuna ricetta fattibile il riquadro resta pulito
    assert d["piena"] == ""
