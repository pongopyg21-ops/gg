"""Case separate: registro, accesso e tentativi.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_senza_accesso_le_api_rispondono_401(anon):
    """Nessuna casa collegata: i dati non si toccano e non si leggono."""
    for percorso in ["/api/recipes", "/api/pantry", "/api/shopping", "/api/profile",
                     "/api/meta", "/api/storage", "/api/projects", "/api/faq",
                     "/api/cinema"]:
        r = anon.get(percorso)
        assert r.status_code == 401, f"{percorso} accessibile senza accesso"
        assert r.get_json().get("auth") is False
    # e le scritture del Cinema non si possono fare da fuori
    assert anon.post("/api/cinema/nascondi", json={"id": 1}).status_code == 401
    assert anon.post("/api/cinema/ripristina", json={}).status_code == 401

def test_la_pagina_e_i_file_statici_restano_pubblici(anon):
    """La pagina deve caricarsi per poter mostrare l'accesso."""
    assert anon.get("/").status_code == 200
    assert anon.get("/static/app.js").status_code == 200

def test_sessione_anonima_dice_non_autenticato(anon):
    assert anon.get("/api/session").get_json() == {"authenticated": False}

def test_password_sbagliata_non_entra(anon):
    r = anon.post("/api/login", json={"nome": "Casa Test", "password": "sbagliata"})
    assert r.status_code == 401
    assert anon.get("/api/session").get_json()["authenticated"] is False

def test_casa_inesistente_non_entra(anon):
    r = anon.post("/api/login", json={"nome": "Non Esiste", "password": "x"})
    assert r.status_code == 401
    # stesso messaggio della password sbagliata: non rivela quali case esistono
    assert r.get_json()["error"] == "Nome o password non corretti"

def test_accesso_riuscito_e_session(anon):
    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 200
    info = anon.get("/api/session").get_json()
    assert info["authenticated"] is True
    assert info["nome"] == "Casa Test"

def test_uscire_toglie_laccesso(anon):
    anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert anon.get("/api/recipes").status_code == 200
    anon.post("/api/logout")
    assert anon.get("/api/recipes").status_code == 401

def test_ogni_casa_vede_solo_le_sue_ricette(anon):
    """Il cuore della separazione: due case, ricette diverse, nessuna interferenza."""
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    anon.post("/api/recipes", json={"name": "Piatto di A", "servings": 2, "items": []})
    nomi_a = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di A" in nomi_a

    # casa B, creata dopo: non deve vedere nulla di A
    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa B", "password": "bbbb"})
    nomi_b = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di A" not in nomi_b, "una casa vede le ricette dell'altra"
    anon.post("/api/recipes", json={"name": "Piatto di B", "servings": 2, "items": []})

    # tornando ad A, la ricetta di B non deve comparire
    anon.post("/api/logout")
    anon.post("/api/login", json={"nome": "Casa A", "password": "aaaa"})
    nomi_a2 = {r["name"] for r in anon.get("/api/recipes").get_json()}
    assert "Piatto di B" not in nomi_a2, "una casa vede le ricette dell'altra"
    assert "Piatto di A" in nomi_a2

def test_case_separate_per_dispensa_e_spesa(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    anon.post("/api/pantry", json={"name": "Farina", "quantity": 5, "unit": "kg"})
    assert any(v["name"] == "Farina" for v in anon.get("/api/pantry").get_json())

    anon.post("/api/logout")
    anon.post("/api/houses", json={"nome": "Casa B", "password": "bbbb"})
    assert not any(v["name"] == "Farina" for v in anon.get("/api/pantry").get_json())

def test_una_casa_col_database_mancante_nasce_col_ricettario(anon, casa_test):
    """Una casa registrata ma rimasta senza file non deve nascere vuota.

    Il caso reale: il file del database non c'e' (ripristino parziale, file
    spostato, copia rimessa nel posto sbagliato). La prima richiesta lo ricrea,
    e ricrearlo vuoto lascia l'utente senza nessuna ricetta da scegliere nel
    piano pasti: proprio il punto da cui scriveva per chiedere aiuto.
    """
    houses.registra("casa-spoglia", "Casa Spoglia", "prova1234")
    percorso = houses.db_path("casa-spoglia")
    assert not os.path.exists(percorso)

    anon.post("/api/login", json={"nome": "Casa Spoglia", "password": "prova1234"})
    ricette = anon.get("/api/recipes").get_json()
    assert len(ricette) > 10, "una casa ricreata da zero deve avere il ricettario"

def test_una_casa_esistente_senza_ricette_non_viene_riseminata(anon):
    """Se l'utente cancella tutte le ricette, non devono tornare da sole.

    La tentazione e' di seminare ogni volta che le ricette sono zero, ma zero e'
    uno stato legittimo: chi ha svuotato il ricettario non deve ritrovarselo
    pieno al riavvio successivo.
    """
    anon.post("/api/houses", json={"nome": "Casa Vuota", "password": "aaaa"})
    for r in anon.get("/api/recipes").get_json():
        anon.delete(f"/api/recipes/{r['id']}")
    assert anon.get("/api/recipes").get_json() == []

    # una richiesta successiva non deve ripopolare il database
    assert anon.get("/api/recipes").get_json() == []

def test_avvio_non_crea_un_database_storico_vuoto(tmp_path, monkeypatch):
    """L'avvio non deve lasciare un `cucina.db` fantasma da adottare.

    Era una trappola in due tempi: il primo avvio creava un `cucina.db` vuoto,
    e al secondo `migra_case()` lo scambiava per il ricettario di mesi e
    registrava una casa "Casa" senza niente dentro.
    """
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.delenv("CUCINA_DB", raising=False)
    importlib.reload(houses)
    importlib.reload(app_module)
    try:
        # macchina nuova: nessun registro, nessun cucina.db
        app_module.migra_case()
        app_module.prepara_database_storico()
        assert not os.path.exists(app_module.DB_PATH), \
            "l'avvio ha creato un database storico dal nulla"
        assert houses.elenco() == []

        # il secondo avvio non deve trovare nulla da adottare
        app_module.migra_case()
        assert houses.elenco() == [], "un guscio vuoto e' stato adottato come casa"
    finally:
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)
        importlib.reload(app_module)

def test_una_casa_storica_senza_ricette_ma_con_dati_viene_adottata(tmp_path, monkeypatch):
    """Chi usa l'app solo per le FAQ non deve perdere l'accesso ai suoi dati.

    Scartare il database perche' non ha ricette renderebbe irraggiungibile il
    lavoro di chi teneva solo la password del Wi-Fi: "nessun dato" e' un
    criterio piu' largo di "nessuna ricetta".
    """
    import importlib
    monkeypatch.setenv("MAGGIORDOMO_DATA", str(tmp_path))
    monkeypatch.delenv("CUCINA_DB", raising=False)
    importlib.reload(houses)
    importlib.reload(app_module)
    try:
        app_module.init_db(str(tmp_path / "cucina.db"))
        with closing(sqlite3.connect(str(tmp_path / "cucina.db"))) as con:
            con.execute("INSERT INTO faq (category, question, answer) "
                        "VALUES ('wifi', 'Fastweb', 'segreta')")
            con.commit()

        app_module.migra_case()

        assert houses.elenco(), "una casa con dati dentro e' stata scartata"
        assert houses.elenco()[0]["slug"] == houses.STORICA
    finally:
        monkeypatch.delenv("MAGGIORDOMO_DATA", raising=False)
        importlib.reload(houses)
        importlib.reload(app_module)

def test_una_casa_nuova_nasce_col_ricettario(anon):
    """Le case nuove non partono vuote: hanno il ricettario italiano di partenza."""
    anon.post("/api/houses", json={"nome": "Casa Nuova", "password": "cccc"})
    ricette = anon.get("/api/recipes").get_json()
    assert len(ricette) > 10, "una casa nuova deve avere il ricettario di partenza"
    nomi = {r["name"] for r in ricette}
    assert "Pasta al pomodoro" in nomi

def test_la_casa_nuova_ha_gli_ingredienti_del_ricettario(anon):
    """Il ricettario seminato deve avere ingredienti veri e foto, non gusci vuoti."""
    anon.post("/api/houses", json={"nome": "Casa Nuova", "password": "cccc"})
    ricette = anon.get("/api/recipes").get_json()
    con_foto = [r for r in ricette if r.get("image")]
    assert con_foto, "le ricette seminate devono avere le foto"

    # l'elenco non porta gli ingredienti: il dettaglio si' (gli ingredienti sono
    # nella tabella `recipe_items`, che l'elenco non interroga)
    pomodoro = next(r for r in ricette if r["name"] == "Pasta al pomodoro")
    dettaglio = anon.get(f"/api/recipes/{pomodoro['id']}").get_json()
    assert len(dettaglio["items"]) >= 3, "la ricetta seminata deve avere ingredienti"
    assert all(v["name"].strip() for v in dettaglio["items"])

def test_ogni_ricetta_ha_una_preparazione_dettagliata():
    """Le preparazioni del ricettario sono scritte per passi, non in due righe.

    Il client le mostra come elenco numerato (`passiDa` divide su righe vuote e
    punti), quindi una preparazione di una frase sola diventa un passo unico e
    non serve a chi cucina. Il test fissa la sostanza: piu' passi e un testo che
    spiega tempi e modi, non solo l'elenco degli ingredienti in prosa.
    """
    import seed
    for r in seed.RECIPES:
        passi = [p for p in r["instructions"].split("\n\n") if p.strip()]
        assert len(passi) >= 4, \
            f"{r['name']}: solo {len(passi)} passi, la preparazione e' troppo breve"
        assert len(r["instructions"]) >= 400, \
            f"{r['name']}: {len(r['instructions'])} caratteri, troppo poco dettaglio"
        for passo in passi:
            assert passo.strip().endswith((".", ":", "!")), \
                f"{r['name']}: passo senza punto finale «{passo[:40]}»"

def test_le_preparazioni_vecchie_vengono_aggiornate(casa_test):
    """Un database esistente riceve le preparazioni nuove al primo `semina()`.

    Chi usa l'app da prima ha ancora i testi brevi: senza questo aggiornamento
    vedrebbe le preparazioni dettagliate solo creando una casa nuova.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 20, 'facile', ?)",
                       (r["name"], seed.PREPARAZIONI_PRECEDENTI[r["name"]]))
        db.commit()

    seed.semina(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            testo = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                               (r["name"],)).fetchone()[0]
            assert testo == r["instructions"], f"{r['name']} non aggiornata"

def test_una_preparazione_scritta_a_mano_non_viene_sovrascritta(casa_test):
    """La preparazione dell'utente e' un dato suo: `semina()` non la tocca.

    L'aggiornamento sostituisce il testo solo se e' ancora quello vecchio. Senza
    questa guardia, chi ha riscritto la ricetta di famiglia se la vedrebbe
    cancellare al primo riavvio del server.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    mio = "La ricetta di nonna: soffriggi tutto e cuoci piano finche' e' pronto."
    with closing(sqlite3.connect(percorso)) as db:
        for r in seed.RECIPES:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 20, 'facile', ?)",
                       (r["name"], seed.PREPARAZIONI_PRECEDENTI[r["name"]]))
        db.execute("UPDATE recipes SET instructions = ? WHERE name = ?",
                   (mio, "Pasta al pomodoro"))
        db.commit()

    seed.semina(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        testo = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                           ("Pasta al pomodoro",)).fetchone()[0]
        assert testo == mio, "la preparazione scritta a mano e' stata sovrascritta"
        # le altre invece si aggiornano: la guardia vale solo per quella toccata
        altro = db.execute("SELECT instructions FROM recipes WHERE name = ?",
                           ("Cacio e pepe",)).fetchone()[0]
        assert altro == next(r["instructions"] for r in seed.RECIPES
                             if r["name"] == "Cacio e pepe")

def test_le_preparazioni_dettagliate_escono_come_passi(client):
    """`passiDa` deve spezzare la preparazione in un elenco, non in un blocco.

    E' la resa vera nel client: si esegue la funzione estratta da `app.js` con
    node, sul testo che sta davvero nel ricettario. Un test sulle stringhe non
    accorgerebbe di una preparazione che resta un passo unico.
    """
    import seed
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function passiDa"):
                 js.index("\n}\n", js.index("function passiDa")) + 3]
    preparazione = next(r["instructions"] for r in seed.RECIPES
                        if r["name"] == "Cacio e pepe")
    prova = blocco + f"""
const testo = {json.dumps(preparazione)};
console.log(JSON.stringify({{ passi: passiDa(testo) }}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    passi = json.loads(esito.stdout)["passi"]
    assert len(passi) >= 5, f"solo {len(passi)} passi: la preparazione resta un blocco"
    assert all(p.strip() for p in passi), "nessun passo vuoto"
    # il primo passo dice cosa preparare per primo, non e' un titolo
    assert "pepe" in passi[0].lower()

def test_le_ricette_tolte_non_sono_piu_nel_ricettario():
    """Le ricette tolte su richiesta dell'utente non tornano a ogni semina.

    `REMOVED` da solo non basta: la cancellazione in `semina()` avviene prima
    dell'inserimento, quindi una ricetta presente in entrambe le liste verrebbe
    tolta e subito rimessa. Devono mancare da `RECIPES`, e le mappe che le
    accompagnano devono seguire, altrimenti restano chiavi senza ricetta.
    """
    import seed
    tolte = ["Casoncelli alla bergamasca", "Chicken tikka masala",
             "Insalata di riso", "Lasagna soup", "Malloreddus alla campidanese",
             "Marry me chicken", "Paella", "Riso alla cantonese", "Shakshuka"]
    nomi = {r["name"] for r in seed.RECIPES}
    for nome in tolte:
        assert nome not in nomi, f"{nome} e' ancora nel ricettario"
        assert nome not in seed.PHOTOS, f"{nome} ha ancora una foto"
        assert nome not in seed.PREPARAZIONI_PRECEDENTI, nome
    # le tre mappe parlano delle stesse ricette: una chiave in piu' e' un residuo
    assert set(seed.PHOTOS) == nomi
    assert set(seed.PREPARAZIONI_PRECEDENTI) == nomi
    # e i file delle foto tolte non restano orfani su disco
    import os
    for nome in tolte:
        for f in os.listdir(os.path.join(os.path.dirname(seed.__file__),
                                         "static", "recipes")):
            assert nome.replace(" ", "-").lower() not in f.lower(), \
                f"il file {f} della ricetta tolta {nome} e' ancora su disco"

def test_le_ricette_tolte_spariscono_anche_dai_database_esistenti(casa_test):
    """Chi ha gia' i dati non deve tenersi le ricette tolte per sempre.

    `seed.semina()` gira solo quando un database nasce, e `windows\\avvia.bat`
    non lo chiama affatto: senza il passaggio in `migrate()` le ricette tolte
    sparirebbero solo dalle case nuove. Qui si simula il database di prima —
    ricette presenti, una nel piano e fra i preferiti — e si verifica che la
    migrazione le porti via **insieme** a quello che le puntava.
    """
    import seed
    percorso = houses.db_path(casa_test["slug"])
    tolte = seed.REMOVED
    with closing(sqlite3.connect(percorso)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        for nome in tolte:
            db.execute("INSERT INTO recipes (name, servings, time_minutes, difficulty,"
                       " instructions) VALUES (?, 2, 30, 'facile', 'vecchia')", (nome,))
        rid = db.execute("SELECT id FROM recipes WHERE name = ?", (tolte[0],)).fetchone()[0]
        db.execute("INSERT INTO meal_plan (date, meal, recipe_id, servings)"
                   " VALUES ('2026-09-29', 'pranzo', ?, 2)", (rid,))
        db.execute("INSERT INTO favorites (recipe_id) VALUES (?)", (rid,))
        ing = db.execute("INSERT INTO ingredients (name, category)"
                         " VALUES ('ingrediente-fantasma', 'Altro')").lastrowid
        db.execute("INSERT INTO recipe_items (recipe_id, ingredient_id, quantity, unit)"
                   " VALUES (?, ?, 1, 'pz')", (rid, ing))
        db.commit()

    # il passaggio che gira a ogni richiesta
    app_module.init_db(percorso)

    with closing(sqlite3.connect(percorso)) as db:
        rimaste = {r[0] for r in db.execute("SELECT name FROM recipes")}
        assert not (set(tolte) & rimaste), "una ricetta tolta e' rimasta"
        assert db.execute("SELECT COUNT(*) FROM meal_plan").fetchone()[0] == 0, \
            "il piano conserva una ricetta tolta"
        assert db.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0
        orfane = db.execute(
            "SELECT COUNT(*) FROM recipe_items WHERE recipe_id NOT IN"
            " (SELECT id FROM recipes)").fetchone()[0]
        assert orfane == 0, "restano righe di ricette che non esistono piu'"
        # l'ingrediente che solo quella ricetta usava non deve restare orfano
        assert db.execute("SELECT COUNT(*) FROM ingredients WHERE name = ?",
                          ("ingrediente-fantasma",)).fetchone()[0] == 0

def test_le_ricette_con_foto_vengono_prima(client):
    """Nell'elenco le ricette con foto stanno sopra quelle senza.

    Si esegue la funzione vera di `app.js` con node: l'ordine e' una proprieta'
    del client, e un test sulle stringhe non accorgerebbe di un comparatore
    sbagliato. Dentro i due gruppi l'ordine alfabetico non deve cambiare.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    blocco = js[js.index("function conFotoPrima"):
                 js.index("\n}\n", js.index("function conFotoPrima")) + 3]
    prova = blocco + """
const lista = [
  {name: 'Senza A', image: ''},
  {name: 'Con B', image: 'b.jpg'},
  {name: 'Senza C', image: ''},
  {name: 'Con D', image: 'd.jpg'},
];
console.log(JSON.stringify(conFotoPrima(lista).map((r) => r.name)));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    ordine = json.loads(esito.stdout)
    assert ordine == ["Con B", "Con D", "Senza A", "Senza C"], ordine

def test_non_si_possono_creare_due_case_con_lo_stesso_nome(anon):
    anon.post("/api/houses", json={"nome": "Casa Unica", "password": "aaaa"})
    anon.post("/api/logout")
    r = anon.post("/api/houses", json={"nome": "casa unica", "password": "bbbb"})
    assert r.status_code == 400
    assert "nome" in r.get_json()["error"].lower()

def test_creare_una_casa_richiede_una_password(anon):
    r = anon.post("/api/houses", json={"nome": "Senza Password", "password": ""})
    assert r.status_code == 400

def test_lenco_delle_case_non_espone_le_password(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "aaaa"})
    elenco = anon.get("/api/houses").get_json()
    assert elenco and all(set(v) == {"slug", "nome"} for v in elenco)

def test_cambiare_password(anon):
    anon.post("/api/houses", json={"nome": "Casa A", "password": "vecchia"})
    # sbagliata: non deve cambiare nulla
    assert anon.put("/api/houses/password",
                    json={"attuale": "sbagliata", "nuova": "nuovissima"}).status_code == 400
    assert anon.put("/api/houses/password",
                    json={"attuale": "vecchia", "nuova": "nuovissima"}).status_code == 200
    anon.post("/api/logout")
    assert anon.post("/api/login", json={"nome": "Casa A", "password": "vecchia"}).status_code == 401
    assert anon.post("/api/login", json={"nome": "Casa A", "password": "nuovissima"}).status_code == 200

def test_la_password_non_si_salva_in_chiaro(anon):
    """Se il registro finisce in un backup, la password non deve essere leggibile."""
    anon.post("/api/houses", json={"nome": "Casa A", "password": "segretissima"})
    with sqlite3.connect(REGISTRO) as c:
        salvata = c.execute("SELECT password FROM houses WHERE nome = 'Casa A'").fetchone()[0]
    assert "segretissima" not in salvata
    assert salvata.startswith("pbkdf2_sha256$")

def test_la_password_e_verificata_correttamente():
    impronta = houses.hash_password("prova")
    assert houses.verifica_password("prova", impronta)
    assert not houses.verifica_password("sbagliata", impronta)
    assert not houses.verifica_password("prova", "formato-non-valido")

def test_lo_slug_non_ammette_percorsi():
    """Niente traversal: dal nome si ricava uno slug prevedibile."""
    assert houses.slugify("Casa di Anna!") == "casa-di-anna"
    assert houses.slugify("../../etc/passwd") == "etc-passwd"
    with pytest.raises(ValueError):
        houses.db_path("../../etc/passwd")

def test_reimposta_password_entra_senza_quella_vecchia(client):
    """Chi perde la password deve poter rientrare: e' il caso che conta."""
    vecchia = "PasswordPersa123"
    assert not houses.autentica(CASA_TEST, vecchia)      # quella del test e' un'altra
    with closing(sqlite3.connect(REGISTRO)) as db:
        db.execute("UPDATE houses SET password = ? WHERE slug = ?",
                   (houses.hash_password(vecchia), CASA_TEST))
        db.commit()
    assert houses.autentica(CASA_TEST, vecchia)

    houses.reimposta_password(CASA_TEST, "NuovaPassword456")
    assert houses.autentica(CASA_TEST, "NuovaPassword456")
    assert not houses.autentica(CASA_TEST, vecchia)      # la vecchia smette di valere

    # e dalla porta principale funziona: e' quello che serve davvero
    r = client.post("/api/login", json={"nome": "Casa Test", "password": "NuovaPassword456"})
    assert r.status_code == 200

def test_reimposta_password_non_cancella_i_dati(client):
    """Il motivo per cui si usa: rientrare e ritrovare tutto."""
    client.post("/api/recipes", json={"name": "Carbonara di prova"})
    prima = len(client.get("/api/recipes").get_json())

    houses.reimposta_password(CASA_TEST, "PasswordNuova1")

    client.post("/api/login", json={"nome": "Casa Test", "password": "PasswordNuova1"})
    dopo = len(client.get("/api/recipes").get_json())
    assert dopo == prima and prima >= 1

def test_reimposta_password_rifiuta_quella_corta():
    with pytest.raises(ValueError):
        houses.reimposta_password(CASA_TEST, "abc")
    with pytest.raises(ValueError):
        houses.reimposta_password(CASA_TEST, "")

def test_reimposta_password_non_crea_case_inesistenti():
    with pytest.raises(ValueError):
        houses.reimposta_password("casa-che-non-esiste", "PasswordLunga1")
    assert not houses.esiste("casa-che-non-esiste")

def test_lo_strumento_di_ripristino_funziona_da_capo_a_capo(client, monkeypatch, capsys):
    """`ripristina_password.py` così come lo esegue l'utente, con `windows\\password.bat`."""
    import ripristina_password
    risposte = iter(["PasswordSmemorata2", "PasswordSmemorata2"])
    monkeypatch.setattr(ripristina_password, "chiedi_nascosta", lambda *a, **k: next(risposte))
    assert ripristina_password.main() == 0
    assert "Fatto" in capsys.readouterr().out
    assert houses.autentica(CASA_TEST, "PasswordSmemorata2")

def test_lo_strumento_non_cambia_niente_se_le_password_non_coincidono(monkeypatch, capsys):
    import ripristina_password
    risposte = iter(["PrimaPassword11", "SecondaPassword22"])
    monkeypatch.setattr(ripristina_password, "chiedi_nascosta", lambda *a, **k: next(risposte))
    assert ripristina_password.main() == 1
    assert "non coincidono" in capsys.readouterr().out
    assert not houses.autentica(CASA_TEST, "PrimaPassword11")

def test_la_chiave_si_legge_dal_file_segreto(tmp_path, monkeypatch):
    """Su Windows `segreto.bat`, sul server `segreto.sh`: senza, un riavvio fa
    tornare la voce meccanica e non si capisce perche'."""
    (tmp_path / "segreto.bat").write_text(
        '@echo off\nREM nota\nset "AZURE_SPEECH_KEY=ChiaveDaFile1"\n'
        'set "AZURE_SPEECH_REGION=italynorth"\n')
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveDaFile1"
    assert voce_cloud.regione() == "italynorth"
    assert voce_cloud.configurato()

def test_la_chiave_si_legge_anche_dal_file_sh(tmp_path, monkeypatch):
    (tmp_path / "segreto.sh").write_text(
        "# nota\nexport AZURE_SPEECH_KEY='ChiaveDaFile2'\nexport AZURE_SPEECH_REGION=italynorth\n")
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "ChiaveDaFile2"

def test_la_regione_diventa_minuscola(tmp_path, monkeypatch):
    """Scritta con maiuscole non funziona, e l'errore non lo dice."""
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_REGION=ITALYNORTH\n")
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.regione() == "italynorth"

def test_l_ambiente_vince_sul_file(tmp_path, monkeypatch):
    """Chi esporta la chiave a mano comanda: il file e' un ripiego, non un vincolo."""
    (tmp_path / "segreto.sh").write_text("export AZURE_SPEECH_KEY=DalFile\n")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "DallAmbiente")
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert voce_cloud.chiave() == "DallAmbiente"

def test_senza_file_ne_chiave_configurato_e_falso(tmp_path, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    monkeypatch.setattr(voce_cloud, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(voce_cloud, "_FILE_LETTI", False)

    assert not voce_cloud.configurato()

def test_il_dockerfile_copia_tutto_quello_che_serve(client):
    """Per l'accesso **da ovunque** l'app va su una macchina sempre accesa, e la
    via e' un'immagine: se il `Dockerfile` dimenticasse un modulo, l'app
    partirebbe e morirebbe con un `ModuleNotFoundError` solo in produzione — il
    posto peggiore per scoprirlo.

    Si legge il `Dockerfile` e si controlla che **ogni** modulo locale importato
    dal codice sia copiato nell'immagine, piu' i file dati (`schema.sql`) e la
    cartella `static`."""
    import re
    base = BASE_APP
    dockerfile = open(f"{base}/Dockerfile", encoding="utf-8").read()

    # i moduli locali: quelli importati dal codice e presenti come .py accanto
    # ai sorgenti. I file di test (`test_*.py`, `test_comuni.py`) sono esclusi:
    # non fanno parte dell'app e non devono entrare nell'immagine.
    moduli = set()
    for nome in os.listdir(base):
        if nome.endswith(".py") and not nome.startswith("test_") and nome != "conftest.py":
            moduli.add(nome)
    # quali sono importati da qualche parte (quindi necessari a runtime)
    usati = set()
    for nome in moduli:
        sorgente = open(f"{base}/{nome}", encoding="utf-8").read()
        for altro in moduli:
            if altro == nome:
                continue
            if re.search(rf"^import {altro[:-3]}\b|^from {altro[:-3]} import", sorgente, re.M):
                usati.add(altro)
    # il punto d'ingresso e i suoi import: si parte da app.py e si chiude
    da_copiare = {"app.py", "schema.sql"}
    da_copiare |= usati
    # seed.py e' importato da app.py in modo ritardato (dentro una funzione)
    da_copiare.add("seed.py")

    for nome in sorted(da_copiare):
        assert nome in dockerfile, f"il Dockerfile non copia {nome}"
    assert "static" in dockerfile, "il Dockerfile non copia la cartella static"

def test_dietro_un_proxy_si_legge_l_indirizzo_vero(anon, monkeypatch):
    """Con un tunnel davanti (Tailscale Funnel, Cloudflare) la richiesta arriva
    dal proxy: senza leggere i suoi header, l'indirizzo di chi bussa e' sempre
    quello del proxy, e **il freno ai tentativi conta tutti su un indirizzo
    solo** — chi sbaglia la password blocca anche gli altri.

    Si attiva `DIETRO_PROXY` e si manda l'header come farebbe il tunnel: il freno
    dev'essere contato sull'indirizzo vero, non su quello del proxy."""
    import importlib
    monkeypatch.setenv("DIETRO_PROXY", "1")
    ricaricato = importlib.reload(app_module)
    try:
        with ricaricato.app.test_client() as c:
            # il freno conta due chiavi, l'indirizzo **e** il nome della casa
            # (vedi `chiavi_tentativi`): per isolare l'indirizzo si sbaglia con
            # nomi di casa diversi, cosi' resta in gioco solo la chiave dell'IP
            for i in range(houses.TENTATIVI_LIBERI + 1):
                c.post("/api/login", json={"nome": f"Casa {i}", "password": "no"},
                       headers={"X-Forwarded-For": "10.0.0.1"})
            # lo stesso indirizzo e' ormai frenato
            bloccato = c.post("/api/login", json={"nome": "Altra", "password": "no"},
                              headers={"X-Forwarded-For": "10.0.0.1"})
            assert bloccato.status_code == 429, "l'indirizzo frenato non lo e' piu'"
            # un indirizzo **diverso** non ha ancora sbagliato: se il proxy non
            # fosse letto, sarebbe lo stesso indirizzo del precedente e troverebbe
            # il freno (429) invece di un semplice rifiuto (401)
            r = c.post("/api/login", json={"nome": "Ancora", "password": "no"},
                       headers={"X-Forwarded-For": "10.0.0.2"})
            assert r.status_code == 401, "l'indirizzo vero non e' stato letto"
    finally:
        monkeypatch.delenv("DIETRO_PROXY", raising=False)
        importlib.reload(app_module)

def test_dietro_un_proxy_la_pagina_resta_raggiungibile(anon):
    """Il tunnel inoltra su http, ma chi bussa e' su https: la pagina non deve
    dipendere da quale dei due vede il server. Si guarda che la risposta non
    contenga un indirizzo assoluto in `http://` (un redirect o un link cosi'
    riporterebbe l'utente fuori dall'https, e il browser blocca il microfono)."""
    html = anon.get("/", headers={"X-Forwarded-Proto": "https",
                                  "X-Forwarded-Host": "casa.esempio.ts.net"}
                    ).get_data(as_text=True)
    assert 'src="http://' not in html and "href=\"http://" not in html

def test_dopo_troppi_errori_la_risposta_dice_di_aspettare(anon):
    nome, sbagliata = "Casa Test", "sbagliata"
    # i primi tentativi sono liberi: sbagliare due volte capita, e non deve
    # diventare un'attesa
    for _ in range(houses.TENTATIVI_LIBERI):
        assert anon.post("/api/login", json={"nome": nome, "password": sbagliata}
                         ).status_code == 401

    r = anon.post("/api/login", json={"nome": nome, "password": sbagliata})
    assert r.status_code == 429
    assert "riprova fra" in r.get_json()["error"]

def test_il_freno_non_tocca_chi_sa_la_password(anon):
    """Qualche errore sotto la soglia non deve impedire l'accesso corretto:
    sbagliare la password due volte capita a tutti."""
    for _ in range(houses.TENTATIVI_LIBERI - 1):
        anon.post("/api/login", json={"nome": "Casa Test", "password": "quasi"})

    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 200

def test_l_accesso_riuscito_azzera_i_tentativi_sbagliati(anon):
    """Senza azzerare, gli errori si sommerebbero fra un accesso e l'altro e
    dopo qualche giorno anche chi entra sempre correttamente troverebbe un freno."""
    # sotto la soglia: non si viene bloccati, ma il contatore esiste
    for _ in range(houses.TENTATIVI_LIBERI - 1):
        anon.post("/api/login", json={"nome": "Casa Test", "password": "no"})
    assert anon.post("/api/login", json={"nome": "Casa Test",
                                         "password": PASSWORD_TEST}).status_code == 200

    # azzerato: i prossimi tentativi sono di nuovo liberi. Se non fosse stato
    # azzerato, il terzo risponderebbe 429 invece di 401
    for _ in range(houses.TENTATIVI_LIBERI):
        r = anon.post("/api/login", json={"nome": "Casa Test", "password": "no"})
        assert r.status_code == 401, r.status_code

def test_cambiare_il_nome_non_aggira_l_attesa_ma_solo_il_contatore_per_casa(anon):
    """Chi prova nomi diversi non deve poter continuare all'infinito: l'attesa
    per l'indirizzo ferma anche lui, che sia dietro un tunnel o meno."""
    for _ in range(houses.TENTATIVI_LIBERI + 1):
        anon.post("/api/login", json={"nome": "Casa Sbagliata", "password": "x"})

    r = anon.post("/api/login", json={"nome": "Casa Test", "password": PASSWORD_TEST})
    assert r.status_code == 429

def test_l_attesa_cresce_e_ha_un_tetto():
    """Raddoppiare senza limite diventerebbe un blocco di giorni: c'e' un tetto."""
    adesso = 1000.0
    attese = []
    for i in range(houses.TENTATIVI_LIBERI + 6):
        houses.segnala_fallimento("9.9.9.9", "casa", adesso=adesso + i)
        attese.append(houses.attesa_accesso("9.9.9.9", "casa", adesso=adesso + i))
    # i primi due errori restano liberi, il terzo fa gia' aspettare
    assert attese[0] == 0
    assert attese[1] == 0
    assert attese[2] == houses.ATTESA_BASE
    # e poi raddoppia, fino al tetto
    assert attese[3] > attese[2]
    assert attese[-1] <= houses.ATTESA_MASSIMA

def test_il_contatore_si_dimentica_col_tempo():
    """Una password sbagliata di sera non deve far aspettare la mattina dopo."""
    adesso = 1000.0
    for _ in range(houses.TENTATIVI_LIBERI + 3):
        houses.segnala_fallimento("8.8.8.8", "casa", adesso=adesso)
    assert houses.attesa_accesso("8.8.8.8", "casa", adesso=adesso) > 0

    poi = adesso + houses.DIMENTICARE_DOPO + 1
    assert houses.attesa_accesso("8.8.8.8", "casa", adesso=poi) == 0
