"""Ricettario, preferite, foto e tempi delle ricette.

Fixture in `conftest.py`; helper in `test_comuni.py`. Test estratti
da `test_cucina.py`, spezzato per modulo.
"""
from test_comuni import *  # noqa: F401,F403


def test_preferite_si_salvano_e_si_rileggono(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])

    assert client.get("/api/profile").get_json()["favorite_ids"] == []

    p = client.put("/api/profile", json={"favorite_ids": [b, a]}).get_json()
    # l'elenco torna in ordine di nome ("Insalata" prima di "Pasta al pomodoro"),
    # non nell'ordine in cui e' stato scelto
    assert p["favorite_ids"] == [b, a]
    assert client.get("/api/profile").get_json()["favorite_ids"] == [b, a]

    # un salvataggio successivo sostituisce l'insieme, non lo somma
    p = client.put("/api/profile", json={"favorite_ids": [a]}).get_json()
    assert p["favorite_ids"] == [a]
    p = client.put("/api/profile", json={"favorite_ids": []}).get_json()
    assert p["favorite_ids"] == []

def test_flag_preferita_nelle_ricette(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])
    client.put("/api/profile", json={"favorite_ids": [a]})

    full = {r["id"]: r for r in client.get("/api/recipes?full=1").get_json()}
    assert full[a]["favorite"] is True
    assert full[b]["favorite"] is False
    assert client.get(f"/api/recipes/{a}").get_json()["favorite"] is True

def test_eliminare_una_ricetta_la_toglie_dalle_preferite(client):
    """La chiave esterna con CASCADE evita preferite che puntano a ricette sparite."""
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    b = ricetta(client, "Insalata", 2, [{"name": "Lattuga", "quantity": 1, "unit": "pz"}])
    client.put("/api/profile", json={"favorite_ids": [a, b]})

    client.delete(f"/api/recipes/{a}")
    assert client.get("/api/profile").get_json()["favorite_ids"] == [b]

def test_preferite_ignorano_id_inesistenti(client):
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    p = client.put("/api/profile", json={"favorite_ids": [a, 9999, "x", None]}).get_json()
    assert p["favorite_ids"] == [a]

def test_salvataggio_parziale_non_azzera_le_preferite(client):
    """Il nome si salva dalla scheda Profilo: non deve cancellare le preferite."""
    a = ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    client.put("/api/profile", json={"favorite_ids": [a]})

    p = client.put("/api/profile", json={"full_name": "Marco"}).get_json()
    assert p["favorite_ids"] == [a]
    assert p["full_name"] == "Marco"

def test_onboarding_a_meta_non_chiude_il_percorso(client):
    """Il passo 1 salva le restrizioni senza marcare onboarded: chi si ferma li'
    non perde la dichiarazione e si vede riproporre il passo 2."""
    ricetta(client, "Pasta al pomodoro", 2, [{"name": "Pasta", "quantity": 180, "unit": "g"}])
    p = client.put("/api/profile", json={"restrictions": ["latte"]}).get_json()
    assert p["restriction_list"] == ["latte"]
    assert p["onboarded"] == 0

    p = client.put("/api/profile", json={"onboarded": True}).get_json()
    assert p["onboarded"] == 1
    assert p["restriction_list"] == ["latte"]

def test_fav_prompted_separa_i_due_passi(client):
    """Chi si era profilato prima che la scelta esistesse non deve rivedere il
    passo delle allergie, ma solo quello delle preferite."""
    assert client.get("/api/profile").get_json()["fav_prompted"] == 0

    # profilo completo ma preferite mai chieste
    p = client.put("/api/profile", json={"onboarded": True, "restrictions": ["latte"]}).get_json()
    assert p["onboarded"] == 1 and p["fav_prompted"] == 0

    p = client.put("/api/profile", json={"fav_prompted": True}).get_json()
    assert p["fav_prompted"] == 1
    assert p["onboarded"] == 1 and p["restriction_list"] == ["latte"]

def test_migrazione_aggiunge_fav_prompted_a_un_db_esistente():
    """`CREATE TABLE IF NOT EXISTS` non tocca `profile`: la colonna va aggiunta a mano."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row  # come fa init_db
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                full_name TEXT NOT NULL DEFAULT '',
                restrictions TEXT NOT NULL DEFAULT '',
                onboarded INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO profile (id, full_name, onboarded) VALUES (1, 'Gianluca', 1);
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(profile)")}
        assert "fav_prompted" in cols
        row = db.execute("SELECT full_name, onboarded, fav_prompted FROM profile").fetchone()
        # i dati gia' presenti restano e la colonna nuova parte da 0
        assert tuple(row) == ("Gianluca", 1, 0)
        # rieseguire la migrazione non deve fallire
        app_module.migrate(db)

def test_migrazione_aggiunge_expires_at_a_un_db_esistente():
    """Un database creato prima non ha `expires_at` in `pantry`, e
    `CREATE TABLE IF NOT EXISTS` non aggiunge una colonna a una tabella che
    esiste gia': la migrazione deve farlo, senza toccare le scorte presenti."""
    path = os.path.join(tempfile.mkdtemp(), "vecchio-pantry.db")
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE recipes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);
            CREATE TABLE ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
            CREATE TABLE pantry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
                quantity REAL NOT NULL DEFAULT 0,
                unit TEXT NOT NULL DEFAULT 'pz',
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(ingredient_id, unit)
            );
            INSERT INTO ingredients (name) VALUES ('Farina');
            INSERT INTO pantry (ingredient_id, quantity, unit) VALUES (1, 500, 'g');
        """)
        app_module.migrate(db)
        cols = {r[1] for r in db.execute("PRAGMA table_info(pantry)")}
        assert "expires_at" in cols
        row = db.execute("SELECT quantity, unit, expires_at FROM pantry").fetchone()
        assert tuple(row) == (500, "g", None)
        app_module.migrate(db)  # rieseguire non deve fallire

def test_filtro_ricette_per_allergia(client):
    buona = ricetta(client, "Verdure", 2, [{"name": "Zucchine", "quantity": 300, "unit": "g"}])
    cattiva = ricetta(client, "Carbonara", 2, [
        {"name": "Spaghetti", "quantity": 180, "unit": "g"},
        {"name": "Parmigiano", "quantity": 50, "unit": "g"},
    ])

    full = client.get("/api/recipes?full=1").get_json()
    assert {r["id"] for r in full} == {buona, cattiva}
    # senza restrizioni dichiarate nessuna ricetta è in conflitto
    assert all(r["conflicts"] == [] for r in full)

    client.put("/api/profile", json={"restrictions": ["latte"], "onboarded": True})
    full = {r["id"]: r for r in client.get("/api/recipes?full=1").get_json()}
    assert full[cattiva]["conflicts"] == ["latte"]
    assert full[buona]["conflicts"] == []

    safe = client.get("/api/recipes?full=1&safe=1").get_json()
    assert [r["id"] for r in safe] == [buona]

def test_piano_segnala_i_conflitti(client):
    rid = ricetta(client, "Carbonara", 2, [{"name": "Parmigiano", "quantity": 50, "unit": "g"}])
    client.put("/api/profile", json={"restrictions": ["Latte e lattosio"], "onboarded": True})
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})
    plan = client.get("/api/plan").get_json()
    assert plan[0]["conflicts"] == ["Latte e lattosio"]

def test_riepilogo_ingredienti_per_allergene(client):
    ricetta(client, "X", 2, [{"name": "Parmigiano", "quantity": 1, "unit": "pz"},
                             {"name": "Zucchine", "quantity": 1, "unit": "pz"}])
    m = client.get("/api/profile/allergens").get_json()
    assert m["Parmigiano"] == ["latte"]
    assert m["Zucchine"] == []

def test_aceto_non_e_solfitato():
    """L'aceto non è di per sé un solfito: era un falso positivo."""
    assert allergens.allergens_for("Aceto di riso") == set()
    assert allergens.allergens_for("Aceto balsamico") == set()
    assert allergens.allergens_for("Vino bianco") == {"solfiti"}

def test_formati_di_pasta_sono_glutine():
    """Ogni formato di pasta di semola è glutine: un celiaco non deve poterlo ignorare."""
    for nome in ["Calamarata", "Bucatini", "Farfalle", "Orecchiette", "Maccheroni",
                 "Conchiglie", "Ditalini", "Trofie", "Vermicelli", "Capellini",
                 "Pappardelle", "Tagliatelle", "Penne", "Fusilli", "Rigatoni"]:
        assert allergens.allergens_for(nome) == {"glutine"}, nome

def test_verdure_e_condimenti_non_danno_falsi_positivi():
    for nome in ["Peperoni", "Peperoncino", "Pepe nero", "Patate", "Basilico",
                 "Rosmarino", "Prezzemolo", "Aglio", "Cipolla", "Carota"]:
        assert allergens.allergens_for(nome) == set(), nome

def test_foto_salvata_e_restituita(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg",
                       image_credit="Autore — CC BY 2.0 — Wikimedia Commons")
    assert ric["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert ric["image_credit"] == "Autore — CC BY 2.0 — Wikimedia Commons"

    letto = client.get(f"/api/recipes/{ric['id']}").get_json()
    assert letto["image"] == "1-pasta-al-pomodoro-2.jpg"

def test_foto_rifiuta_percorsi_e_traversal(client):
    """Solo un nome di file semplice: niente percorsi, niente risalita di cartelle."""
    for tentativo in ["../../etc/passwd", "../segreto.jpg", "static/recipes/x.jpg",
                      "/etc/passwd", "sottocartella/foto.jpg"]:
        ric = crea_ricetta(client, image=tentativo)
        assert ric["image"] == "", f"accettato pericoloso: {tentativo}"

def test_foto_rifiuta_estensioni_non_immagine(client):
    for tentativo in ["script.js", "file.svg", "pagina.html", "dati.json"]:
        ric = crea_ricetta(client, image=tentativo)
        assert ric["image"] == "", f"accettata estensione non immagine: {tentativo}"

def test_foto_senza_immagine_non_tiene_il_credito(client):
    ric = crea_ricetta(client, image="", image_credit="credito orfano")
    assert ric["image"] == ""
    assert ric["image_credit"] == ""

def test_credito_rimosso_quando_si_toglie_la_foto(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore X")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": ric["name"], "servings": 2, "instructions": "", "items": ric["items"],
        "image": "", "image_credit": "Autore X"})
    assert risposta.get_json()["image"] == ""
    assert risposta.get_json()["image_credit"] == ""

def test_salvataggio_senza_campo_foto_non_la_cancella(client):
    """Un salvataggio parziale non deve far sparire la foto."""
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore Y")
    risposta = client.put(f"/api/recipes/{ric['id']}", json={
        "name": "Nome cambiato", "servings": 3, "instructions": "Nuova", "items": ric["items"]})
    corpo = risposta.get_json()
    assert corpo["name"] == "Nome cambiato"
    assert corpo["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert corpo["image_credit"] == "Autore Y"

def test_elenco_immagini_disponibili(client):
    nomi = client.get("/api/recipe-images").get_json()
    assert isinstance(nomi, list)
    # nel repository le foto delle ricette ci sono e hanno nomi coerenti
    assert nomi, "nessuna immagine trovata in static/recipes/"
    assert all(n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) for n in nomi)

def test_pagina_ricette_espone_la_foto(client):
    ric = crea_ricetta(client, image="1-pasta-al-pomodoro-2.jpg", image_credit="Autore Z")
    elenco = client.get("/api/recipes?full=1").get_json()
    voce = next(r for r in elenco if r["id"] == ric["id"])
    assert voce["image"] == "1-pasta-al-pomodoro-2.jpg"
    assert "Autore Z" in voce["image_credit"]

def test_ricettario_di_partenza_e_coerente():
    """Le ricette del seed devono essere caricabili così come sono scritte."""
    import seed
    categorie_note = {"Frutta e Verdura", "Carne e Pesce", "Latticini", "Dispensa",
                      "Pane e Cereali", "Surgelati", "Bevande", "Dolci", "Altro"}
    nomi = [r["name"] for r in seed.RECIPES]
    assert len(nomi) == len(set(nomi)), "nomi duplicati nel ricettario"
    for r in seed.RECIPES:
        assert r["servings"] > 0
        assert r["time_minutes"] > 0
        assert r["difficulty"] in {"facile", "media", "difficile"}
        assert r["instructions"].strip()
        assert r["items"], f"{r['name']} senza ingredienti"
        for i in r["items"]:
            assert i["quantity"] > 0, f"{r['name']}: {i['name']} con quantità non valida"
            assert i["unit"] in {"pz", "g", "kg", "ml", "l", "cucchiaio", "cucchiaino",
                                 "confezione", "fetta"}, f"{r['name']}: unità {i['unit']}"
            assert i["category"] in categorie_note, f"{r['name']}: categoria {i['category']}"

def test_ogni_ricetta_ha_la_sua_foto():
    """Ogni ricetta del ricettario ha una foto che esiste davvero su disco.

    Una foto mancante non si nota leggendo il codice: si nota aprendo la
    scheda e trovando un riquadro vuoto. Il test guarda `PHOTOS` *e* il file,
    perche' un nome giusto con il file assente e' lo stesso difetto.

    La licenza deve essere libera e il credito completo: le foto arrivano da
    Wikimedia Commons e l'attribuzione (autore, licenza, pagina) e' un
    obbligo, non un abbellimento.
    """
    import seed
    cartella = os.path.join(os.path.dirname(app_module.__file__), "static", "recipes")
    for r in seed.RECIPES:
        nome = r["name"]
        assert nome in seed.PHOTOS, f"{nome} senza foto in PHOTOS"
        file_name, credito = seed.PHOTOS[nome]
        assert os.path.exists(os.path.join(cartella, file_name)), \
            f"{nome}: manca il file {file_name}"
        assert file_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")), \
            f"{nome}: {file_name} non e' un'immagine"
        assert "Wikimedia Commons" in credito and "CC" in credito.upper() \
            or "Public domain" in credito, f"{nome}: credito incompleto «{credito}»"
        assert "https://commons.wikimedia.org/" in credito, \
            f"{nome}: manca l'indirizzo della foto nel credito"

def test_ricettario_copre_primi_e_piatti_unici_recenti(client):
    """I piatti entrati in voga negli ultimi anni esistono e sono pianificabili.

    Il database di test nasce vuoto, quindi le ricette vengono caricate davvero
    via API: il test verifica sia la presenza nel ricettario sia che il formato
    del seed sia accettato dall'endpoint di creazione.
    """
    import seed
    attesi = {"Pasta alla Norma", "Spaghetti all'assassina", "Cacio e pepe",
              "Trofie al pesto", "Bucatini all'amatriciana", "Penne all'arrabbiata",
              "Pasta fredda alla mediterranea", "Calamarata",
              "Tagliolini al tartufo", "Poke bowl",
              "Gulasch", "Pizza napoletana", "Ramen"}
    assert attesi <= {r["name"] for r in seed.RECIPES}

    for r in seed.RECIPES:
        assert client.post("/api/recipes", json=r).status_code == 201, r["name"]

    elenco = client.get("/api/recipes").get_json()
    assert attesi <= {r["name"] for r in elenco}
    # una new entry si pianifica e finisce nella lista della spesa
    norma = next(r for r in elenco if r["name"] == "Pasta alla Norma")
    r = client.post("/api/plan", json={"date": "2026-09-21", "meal": "pranzo",
                                       "recipe_id": norma["id"], "servings": 2})
    assert r.status_code == 201
    r = client.post("/api/shopping/generate", json={"start": "2026-09-21", "end": "2026-09-21"})
    assert r.status_code == 200
    nomi = {v["name"] for v in client.get("/api/shopping").get_json()}
    assert {"Melanzane", "Penne", "Ricotta salata"} <= nomi

def test_i_due_tempi_e_il_costo_si_salvano_e_si_rileggono(client):
    r = client.post("/api/recipes", json={
        "name": "Prova tempi", "servings": 4,
        "prep_minutes": 20, "cook_minutes": 45, "cost": 2.5,
        "items": [{"name": "Farina", "quantity": 200, "unit": "g"}],
    })
    assert r.status_code == 201
    rec = r.get_json()
    assert rec["prep_minutes"] == 20
    assert rec["cook_minutes"] == 45
    assert rec["cost"] == 2.5
    # si rileggono dalla scheda, non solo dalla risposta della creazione
    letto = client.get(f"/api/recipes/{rec['id']}").get_json()
    assert (letto["prep_minutes"], letto["cook_minutes"], letto["cost"]) == (20, 45, 2.5)

def test_i_tempi_non_validi_non_diventano_numeri_inventati(client):
    """Vuoto, zero, negativo e testo non sono tempi: restano «non indicato».

    Zero e' il caso che conta: salvarlo mostrerebbe «0 min» al posto di niente,
    e l'utente crederebbe che la ricetta si faccia in zero minuti.
    """
    for valore in ("", 0, -10, "boh", None):
        rec = client.post("/api/recipes", json={
            "name": f"Prova {valore}", "prep_minutes": valore, "cook_minutes": valore,
        }).get_json()
        assert rec["prep_minutes"] is None, valore
        assert rec["cook_minutes"] is None, valore

def test_il_costo_non_valido_non_diventa_un_prezzo(client):
    """Un costo vuoto, negativo o non numerico resta «non indicato».

    Zero invece si tiene: e' un'informazione vera — «non costa niente», tipico di
    una ricetta fatta con gli avanzi — e non va confusa con «non lo so». Il
    campo vuoto e' l'unico modo per dire che il costo non si conosce.
    """
    for valore in ("", -1, "boh", None):
        rec = client.post("/api/recipes", json={
            "name": f"Costo {valore}", "cost": valore,
        }).get_json()
        assert rec["cost"] is None, valore
    zero = client.post("/api/recipes", json={"name": "Costo zero", "cost": 0}).get_json()
    assert zero["cost"] == 0, "lo zero e' un costo, non un dato mancante"

def test_il_totale_vecchio_non_si_perde_quando_i_due_tempi_sono_vuoti(client):
    """Le ricette salvate prima dei due tempi hanno solo `time_minutes`.

    Se il form lo azzerasse, aprire e salvare una ricetta vecchia cancellerebbe
    un dato che l'utente non ha mai toccato. Sparisce solo quando i due tempi
    vengono indicati, perche' allora il totale si ricava da quelli.
    """
    rec = client.post("/api/recipes", json={"name": "Vecchia", "time_minutes": 40}).get_json()
    assert rec["time_minutes"] == 40
    # salvataggio parziale: i due tempi restano vuoti, il totale resta
    rec2 = client.put(f"/api/recipes/{rec['id']}", json={"name": "Vecchia", "time_minutes": 40}).get_json()
    assert rec2["time_minutes"] == 40
    # indicando i due tempi, il totale non serve piu'
    rec3 = client.put(f"/api/recipes/{rec['id']}", json={
        "name": "Vecchia", "time_minutes": None, "prep_minutes": 15, "cook_minutes": 25,
    }).get_json()
    assert rec3["time_minutes"] is None
    assert rec3["prep_minutes"] == 15 and rec3["cook_minutes"] == 25

def test_tempi_e_costo_arrivano_anche_nell_elenco_completo(client):
    """La scheda mostra tempi e costo senza una seconda richiesta."""
    client.post("/api/recipes", json={"name": "Con tempi", "prep_minutes": 10,
                                      "cook_minutes": 20, "cost": 3})
    elenco = client.get("/api/recipes?full=1").get_json()
    rec = next(r for r in elenco if r["name"] == "Con tempi")
    assert rec["prep_minutes"] == 10
    assert rec["cook_minutes"] == 20
    assert rec["cost"] == 3

def test_le_colonne_dei_tempi_arrivano_ai_database_esistenti():
    """Un database creato prima non ha le colonne: `migrate()` le aggiunge."""
    import sqlite3 as sq
    from contextlib import closing as cl
    percorso = os.path.join(tempfile.mkdtemp(), "vecchio.db")
    with cl(sq.connect(percorso)) as db:
        db.executescript("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                servings INTEGER NOT NULL DEFAULT 2, time_minutes INTEGER,
                difficulty TEXT NOT NULL DEFAULT 'facile',
                instructions TEXT NOT NULL DEFAULT '');
        """)
        db.execute("INSERT INTO recipes (name, time_minutes) VALUES ('Vecchia', 40)")
        db.commit()
    app_module.init_db(percorso)
    with cl(sq.connect(percorso)) as db:
        colonne = {r[1] for r in db.execute("PRAGMA table_info(recipes)")}
        assert {"prep_minutes", "cook_minutes", "cost"} <= colonne
        riga = db.execute("SELECT time_minutes, prep_minutes, cost FROM recipes").fetchone()
        assert riga == (40, None, None), "il totale vecchio non e' stato toccato"

def test_tempiRicetta_e_costoRicetta_funzionano_davvero(client):
    """Le due funzioni del client, eseguite con node sul caso vero.

    Il totale e' la somma dei due tempi; con solo il totale vecchio si mostra
    quello; senza niente non si mostra nulla. Un test sulle stringhe non
    accorgerebbe di una somma sbagliata.
    """
    js = client.get("/static/app.js").get_data(as_text=True)
    inizio = js.index("function tempiRicetta")
    blocco = js[inizio:js.index("\n}\n", inizio) + 3]
    inizio2 = js.index("function costoRicetta")
    blocco += js[inizio2:js.index("\n}\n", inizio2) + 3]
    prova = blocco + """
const casi = [
  {prep_minutes: 20, cook_minutes: 45},
  {prep_minutes: 15},
  {time_minutes: 40},
  {},
];
console.log(JSON.stringify({
  tempi: casi.map((r) => tempiRicetta(r)),
  costi: [costoRicetta({cost: 2.5}), costoRicetta({cost: 0}), costoRicetta({cost: null})],
}));
"""
    import subprocess
    esito = subprocess.run(["node", "-e", prova], capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr
    # in JSON: una stringa vuota stampata da sola sparirebbe nello strip()
    esito_js = json.loads(esito.stdout)
    tempi = esito_js["tempi"]
    assert tempi[0] == {"totale": 65, "testo": "prep 20 min + cottura 45 min · totale 65 min"}
    assert tempi[1] == {"totale": 15, "testo": "prep 15 min · totale 15 min"}
    assert tempi[2] == {"totale": 40, "testo": "40 min"}
    assert tempi[3] is None
    assert esito_js["costi"] == ["€ 2,50 a porzione", "€ 0,00 a porzione", ""]

def test_magazzino_non_entra_nella_spesa(client):
    """Un detergente non e' un ingrediente: non deve finire in lista."""
    client.post("/api/storage", json={"name": "Sapone", "quantity": 1})
    rid = ricetta(client, "Pasta", 2, [{"name": "Pasta", "quantity": 400, "unit": "g"}])
    client.post("/api/plan", json={"date": "2026-09-16", "meal": "cena", "recipe_id": rid, "servings": 2})

    assert [i["name"] for i in client.get("/api/shopping").get_json()] == ["Pasta"]

def test_magazzino_non_tocca_la_dispensa(client):
    """Le due sezioni sono separate: riempire una non riempie l'altra."""
    client.post("/api/storage", json={"name": "Sapone", "quantity": 3})
    assert client.get("/api/pantry").get_json() == []

def test_magazzino_meta_ha_categorie_e_luoghi(client):
    meta = client.get("/api/magazzino/meta").get_json()
    assert "Pulizia casa" in meta["categories"]
    assert "Ripostiglio" in meta["places"]

def test_magazzino_ordina_prima_quello_che_manca(client):
    client.post("/api/storage", json={"name": "Abbondante", "quantity": 10, "min_quantity": 1})
    client.post("/api/storage", json={"name": "Scarso", "quantity": 1, "min_quantity": 5})
    assert [v["name"] for v in client.get("/api/storage").get_json()][0] == "Scarso"
